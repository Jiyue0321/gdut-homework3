# AI 办公助理（Office Assistant Agent）

一个「能说会做」的中文 AI 智能体：用自然语言对话，自动完成 workspace 目录下的
文件读写、搜索、重命名、待办清单生成等办公操作。

- **能说**：基于大模型的自然语言对话（OpenAI 兼容接口，默认 DeepSeek，可切 Qwen / GLM）。
- **会做**：通过 **MCP（Model Context Protocol）** 连接工具服务器，真实操作文件系统。
- **安全**：所有文件操作被沙箱限制在 `workspace/` 目录内，拒绝任何路径穿越。

## 系统架构

```
┌──────────────┐   自然语言     ┌─────────────────┐   function calling  ┌──────────────────┐
│  用户 / 浏览器 │ ───────────▶ │  Streamlit 界面  │ ─────────────────▶ │  大模型（OpenAI 兼容）│
└──────────────┘               │   app.py        │ ◀───────────────── └──────────────────┘
                               └────────┬────────┘     工具调用请求
                                        │ agent/core.py 主循环
                                        ▼
                               ┌─────────────────┐   MCP (stdio)   ┌──────────────────────┐
                               │  MCP 客户端      │ ◀─────────────▶ │  MCP 工具服务器        │
                               │ mcp_client.py   │                 │ office_server.py      │
                               └─────────────────┘                 └──────────┬───────────┘
                                                                              │ 沙箱校验
                                                                              ▼
                                                                      workspace/ 目录
```

## 目录结构

| 路径 | 说明 |
| --- | --- |
| `app.py` | Streamlit Web 聊天界面 |
| `agent/config.py` | 读取 `.env` 中的大模型配置 |
| `agent/mcp_client.py` | MCP 客户端，并把工具 schema 转换为 OpenAI 格式 |
| `agent/core.py` | Agent 主循环：大模型 ↔ MCP 工具多次往返 |
| `mcp_server/office_server.py` | MCP 工具服务器，注册全部办公工具 |
| `mcp_server/sandbox.py` | 路径沙箱，保证所有操作不越出 `workspace/` |
| `workspace/` | 智能体可操作的文件沙箱目录 |

## 提供的工具

| 工具 | 功能 |
| --- | --- |
| `list_directory` | 列出目录内容 |
| `read_file` / `write_file` / `append_file` | 读取 / 写入 / 追加文件 |
| `search_files` | 按文件名与内容关键词搜索 |
| `rename_file` / `move_file` / `delete_file` | 重命名 / 移动 / 删除文件 |
| `create_todo_list` | 生成 Markdown 待办清单 |
| `count_text` | 文本字数统计 |
| `get_current_time` | 获取当前时间 |

## 快速开始

```bash
# 1. 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux
pip install -r requirements.txt

# 2. 配置大模型 API Key
copy .env.example .env          # Windows（macOS/Linux 用 cp）
# 打开 .env 填入你的 API Key，默认使用 DeepSeek，也可切换 Qwen / GLM

# 3. 启动
streamlit run app.py
```

浏览器打开 `http://localhost:8501` 即可对话。

## 使用示例

| 你说的话 | 智能体的动作 |
| --- | --- |
| 帮我在 workspace 新建一个 `notes.txt`，写入「明天交作业」 | 调用 `write_file` 创建文件 |
| 我都有哪些文件？ | 调用 `list_directory` 列出内容 |
| 帮我找找哪个文件提到了「作业」 | 调用 `search_files` 搜索内容 |
| 帮我生成今天的待办清单：写报告、开会、健身 | 调用 `create_todo_list` 生成 `todo.md` |
| 把 `notes.txt` 删掉 | （确认后）调用 `delete_file` |

每次执行过程都会在界面上展示调用了哪些工具、参数是什么、返回结果是什么。

## 安全设计

`mcp_server/sandbox.py` 的 `resolve_safe()` 会先解析用户路径，再校验其是否仍在
`workspace/` 内。任何 `../../etc/passwd` 形式的越界请求都会被拒绝，返回明确错误。

## GitHub

<https://github.com/Jiyue0321/gdut-homework3>

## 小组分工

| 成员 | 分工 |
| --- | --- |
| （待补充） | |
