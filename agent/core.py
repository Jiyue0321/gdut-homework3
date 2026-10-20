"""Agent 核心循环：大模型 ↔ MCP 工具，多次往返直到得到最终答复。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from openai import OpenAI

from agent.config import LLMConfig, load_config
from agent.mcp_client import MCPToolClient

SYSTEM_PROMPT = """你是一个中文 AI 办公助理，能够通过工具操作用户 workspace 目录中的文件。

工作准则：
1. 用户提出需求时，先判断是否需要调用工具；需要就直接调用，不要凭空编造文件内容或执行结果。
2. 涉及删除、覆盖等破坏性操作前，先用一句话向用户确认，得到同意后再执行。
3. 引用文件时使用相对 workspace 的路径。
4. 任务完成后用简洁的中文总结你做了什么，不要罗列工具调用的原始 JSON。
5. 你只能访问 workspace 目录，若用户要求越界操作，礼貌说明并拒绝。"""

MAX_ROUNDS = 8


@dataclass
class ToolCallRecord:
    """一次工具调用的轨迹，用于在界面上展示"会做"的过程。"""

    name: str
    arguments: dict
    result: str


@dataclass
class TurnResult:
    """一轮对话的最终结果与中间过程。"""

    answer: str
    tool_calls: list[ToolCallRecord] = field(default_factory=list)


def _build_client(config: LLMConfig) -> OpenAI:
    return OpenAI(base_url=config.base_url, api_key=config.api_key)


async def run_turn(
    user_message: str,
    history: list[dict],
    config: LLMConfig | None = None,
) -> TurnResult:
    """执行一轮对话：连接 MCP 工具服务器，与模型多轮往返直到得出答复。

    参数 history 为既有对话消息列表（role/content 字典），本函数会就地追加
    本轮新增的消息，以便调用方复用同一份上下文。
    """
    config = config or load_config()
    if not config.configured:
        raise RuntimeError("尚未配置大模型，请复制 .env.example 为 .env 并填入 API Key")

    client = _build_client(config)
    history.append({"role": "user", "content": user_message})

    messages = [{"role": "system", "content": SYSTEM_PROMPT}, *history]
    records: list[ToolCallRecord] = []

    async with MCPToolClient() as mcp:
        tools = await mcp.openai_tools()

        for _ in range(MAX_ROUNDS):
            response = client.chat.completions.create(
                model=config.model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
            message = response.choices[0].message
            messages.append(message)

            if not message.tool_calls:
                answer = message.content or "(模型未返回内容)"
                history.append({"role": "assistant", "content": answer})
                return TurnResult(answer=answer, tool_calls=records)

            for tool_call in message.tool_calls:
                name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}
                result = await mcp.call_tool(name, arguments)
                records.append(ToolCallRecord(name=name, arguments=arguments, result=result))
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )

    answer = "任务步骤过多，已停止。请把需求拆分成更小的步骤再试。"
    history.append({"role": "assistant", "content": answer})
    return TurnResult(answer=answer, tool_calls=records)
