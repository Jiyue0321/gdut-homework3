"""MCP 客户端封装：连接 stdio 工具服务器，并把工具暴露给大模型。

MCP 2.x 只提供原生 snake_case 字段（如 ``tool.input_schema``），而 OpenAI
的 function calling 要求驼峰 ``parameters``，转换逻辑集中在这里。
"""

from __future__ import annotations

import sys
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class MCPToolClient:
    """一个 MCP 工具服务器的会话（异步上下文管理器）。

    用法::

        async with MCPToolClient() as client:
            tools = await client.openai_tools()
            result = await client.call_tool("read_file", {"path": "a.txt"})
    """

    def __init__(self, module: str = "mcp_server.office_server") -> None:
        self._module = module
        self._stack: AsyncExitStack | None = None
        self._session: ClientSession | None = None
        self._tool_names: list[str] = []

    async def __aenter__(self) -> "MCPToolClient":
        params = StdioServerParameters(
            command=sys.executable,
            args=["-m", self._module],
            cwd=str(PROJECT_ROOT),
            encoding="utf-8",
        )
        self._stack = AsyncExitStack()
        read, write = await self._stack.enter_async_context(
            stdio_client(params, errlog=sys.stderr)
        )
        self._session = await self._stack.enter_async_context(ClientSession(read, write))
        await self._session.initialize()
        result = await self._session.list_tools()
        self._tool_names = [tool.name for tool in result.tools]
        return self

    async def __aexit__(self, *exc_info) -> None:
        if self._stack is not None:
            await self._stack.aclose()
        self._stack = None
        self._session = None

    async def openai_tools(self) -> list[dict]:
        """把 MCP 工具清单转换为 OpenAI ``tools`` 参数格式。"""
        assert self._session is not None
        result = await self._session.list_tools()
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description or "",
                    "parameters": tool.input_schema,
                },
            }
            for tool in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict) -> str:
        """调用一个 MCP 工具，返回纯文本结果。"""
        assert self._session is not None
        if name not in self._tool_names:
            return f"错误：不存在名为 {name} 的工具"

        result = await self._session.call_tool(name, arguments)
        texts = [
            block.text
            for block in result.content
            if getattr(block, "type", None) == "text"
        ]
        output = "\n".join(texts) if texts else "(工具无文本输出)"
        if result.is_error:
            return f"工具执行出错：{output}"
        return output
