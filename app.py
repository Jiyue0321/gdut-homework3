"""AI 办公助理 —— Streamlit 聊天界面入口。

运行：
    streamlit run app.py
"""

import asyncio
import shutil
from pathlib import Path

import streamlit as st

from agent.config import load_config
from agent.core import run_turn

WORKSPACE = Path(__file__).resolve().parent / "workspace"

st.set_page_config(page_title="AI 办公助理", page_icon="🗂️", layout="centered")


def _init_state() -> None:
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("display", [])


def _render_tool_calls(tool_calls) -> None:
    if not tool_calls:
        return
    with st.expander(f"🔧 本次执行了 {len(tool_calls)} 次工具调用", expanded=False):
        for record in tool_calls:
            st.markdown(f"**调用工具：** `{record.name}`")
            st.caption(f"参数：{record.arguments}")
            st.code(record.result, language="text")


def _render_sidebar(config) -> None:
    with st.sidebar:
        st.title("🗂️ AI 办公助理")
        st.caption("自然语言驱动的文件管理与待办助手 · 基于 MCP")

        st.subheader("当前模型")
        if config.configured:
            st.success(f"{config.model}")
            st.caption(f"接口：{config.base_url}")
        else:
            st.error("未配置 API Key")
            st.caption("请复制 .env.example 为 .env 并填入密钥后重启")

        st.divider()
        st.subheader("可用工具")
        st.caption(
            "list_directory · read_file · write_file · append_file · "
            "search_files · rename_file · move_file · delete_file · "
            "create_todo_list · count_text · get_current_time"
        )

        st.divider()
        st.subheader("workspace 内容")
        files = sorted(p for p in WORKSPACE.rglob("*") if p.is_file())
        files = [p for p in files if p.name != ".gitkeep"]
        if files:
            for path in files:
                st.caption(f"• {path.relative_to(WORKSPACE).as_posix()}")
        else:
            st.caption("（空）")

        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            if st.button("清空对话", use_container_width=True):
                st.session_state.history = []
                st.session_state.display = []
                st.rerun()
        with col2:
            if st.button("清空文件", use_container_width=True):
                for item in WORKSPACE.iterdir():
                    if item.name == ".gitkeep":
                        continue
                    shutil.rmtree(item) if item.is_dir() else item.unlink()
                st.rerun()


def main() -> None:
    _init_state()
    config = load_config()
    _render_sidebar(config)

    st.title("AI 办公助理")
    st.caption("试着说：帮我在 workspace 新建一个 notes.txt 并写入一段话；或者让我生成今天的待办清单。")

    if not st.session_state.display:
        st.info("在下方输入你的需求，我会调用工具帮你完成文件操作。")

    for item in st.session_state.display:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])
            if item["role"] == "assistant":
                _render_tool_calls(item.get("tool_calls", []))

    prompt = st.chat_input("请输入你的需求…")
    if not prompt:
        return

    st.session_state.display.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        if not config.configured:
            answer = "尚未配置大模型 API Key，请按侧边栏提示配置 .env 后重试。"
            st.error(answer)
            st.session_state.display.append({"role": "assistant", "content": answer})
            return

        with st.spinner("正在思考并调用工具…"):
            try:
                result = asyncio.run(run_turn(prompt, st.session_state.history, config))
            except Exception as exc:  # noqa: BLE001 - 面向用户显示友好错误
                answer = f"执行出错：{exc}"
                st.error(answer)
                st.session_state.display.append({"role": "assistant", "content": answer})
                return

        st.markdown(result.answer)
        _render_tool_calls(result.tool_calls)
        st.session_state.display.append(
            {
                "role": "assistant",
                "content": result.answer,
                "tool_calls": result.tool_calls,
            }
        )


if __name__ == "__main__":
    main()
