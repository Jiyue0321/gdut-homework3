"""AI 办公助理的 MCP 工具服务器。

以 stdio 传输运行，向上层 Agent 暴露一系列办公相关工具（文件读写、
搜索、重命名、待办清单等）。所有文件操作都被限制在 workspace/ 沙箱内。

启动方式（一般由 Agent 作为子进程拉起，无需手动运行）：
    python -m mcp_server.office_server
"""

from datetime import datetime

from mcp.server.mcpserver import MCPServer

from mcp_server.sandbox import WORKSPACE, SandboxError, display_path, resolve_safe

mcp = MCPServer("office-assistant")


@mcp.tool()
def list_directory(path: str = ".") -> str:
    """列出指定目录下的文件和子目录。

    参数 path 为相对 workspace 的目录路径，默认为根目录 "."。
    返回每行的格式为 "[目录] 名称" 或 "[文件] 名称 (字节数)"。
    """
    try:
        target = resolve_safe(path)
    except SandboxError as exc:
        return f"错误：{exc}"

    if not target.exists():
        return f"错误：目录不存在：{path}"
    if not target.is_dir():
        return f"错误：{path} 不是目录"

    entries = sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower()))
    if not entries:
        return f"目录 {display_path(target)} 为空"

    lines = [f"目录 {display_path(target)} 的内容："]
    for entry in entries:
        if entry.is_dir():
            lines.append(f"[目录] {entry.name}")
        else:
            lines.append(f"[文件] {entry.name} ({entry.stat().st_size} 字节)")
    return "\n".join(lines)


@mcp.tool()
def read_file(path: str) -> str:
    """读取指定文件的全部文本内容。

    参数 path 为相对 workspace 的文件路径，例如 "notes.txt"。
    """
    try:
        target = resolve_safe(path)
    except SandboxError as exc:
        return f"错误：{exc}"

    if not target.is_file():
        return f"错误：文件不存在：{path}"

    try:
        return target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"错误：{path} 不是 UTF-8 文本文件，无法读取"


@mcp.tool()
def write_file(path: str, content: str) -> str:
    """创建或覆盖写入一个文本文件（若父目录不存在会自动创建）。

    参数 path 为相对 workspace 的文件路径，content 为要写入的完整文本内容。
    """
    try:
        target = resolve_safe(path)
    except SandboxError as exc:
        return f"错误：{exc}"

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"已写入 {display_path(target)}（{len(content)} 字符）"


@mcp.tool()
def append_file(path: str, content: str) -> str:
    """在文件末尾追加文本内容（文件不存在则创建）。

    参数 path 为相对 workspace 的文件路径，content 为要追加的文本。
    """
    try:
        target = resolve_safe(path)
    except SandboxError as exc:
        return f"错误：{exc}"

    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as fp:
        fp.write(content)
    return f"已追加内容到 {display_path(target)}"


@mcp.tool()
def search_files(keyword: str, path: str = ".") -> str:
    """按关键词搜索文件：同时匹配文件名和文件内容。

    参数 keyword 为搜索关键词，path 为搜索起始目录（默认 workspace 根目录）。
    返回匹配到的文件路径列表；若为内容匹配，会附带命中的行。
    """
    try:
        root = resolve_safe(path)
    except SandboxError as exc:
        return f"错误：{exc}"

    if not root.is_dir():
        return f"错误：目录不存在：{path}"

    lowered = keyword.lower()
    hits: list[str] = []
    for item in root.rglob("*"):
        if not item.is_file():
            continue
        if lowered in item.name.lower():
            hits.append(f"[文件名匹配] {display_path(item)}")
            continue
        try:
            text = item.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if lowered in line.lower():
                hits.append(f"[内容匹配] {display_path(item)}:{lineno}: {line.strip()}")
                break

    if not hits:
        return f"未找到与「{keyword}」匹配的文件"
    return f"共找到 {len(hits)} 条匹配：\n" + "\n".join(hits)


@mcp.tool()
def rename_file(old_path: str, new_name: str) -> str:
    """重命名文件（保持所在目录不变）。

    参数 old_path 为原文件路径，new_name 为新的文件名（不含目录部分）。
    """
    try:
        source = resolve_safe(old_path)
    except SandboxError as exc:
        return f"错误：{exc}"

    if not source.is_file():
        return f"错误：文件不存在：{old_path}"
    if "/" in new_name or "\\" in new_name:
        return "错误：new_name 只能是文件名，不能包含路径分隔符"

    destination = source.with_name(new_name)
    source.rename(destination)
    return f"已将 {display_path(source)} 重命名为 {new_name}"


@mcp.tool()
def move_file(src: str, dst: str) -> str:
    """移动或复制文件到新路径。

    参数 src 为源文件路径，dst 为目标路径（相对 workspace）。
    若目标已存在会被覆盖。
    """
    try:
        source = resolve_safe(src)
        destination = resolve_safe(dst)
    except SandboxError as exc:
        return f"错误：{exc}"

    if not source.is_file():
        return f"错误：文件不存在：{src}"

    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)
    return f"已将 {display_path(source)} 移动到 {display_path(destination)}"


@mcp.tool()
def delete_file(path: str) -> str:
    """删除 workspace 内的一个文件。

    参数 path 为要删除的文件路径。删除前请先与用户确认。
    """
    try:
        target = resolve_safe(path)
    except SandboxError as exc:
        return f"错误：{exc}"

    if target.is_dir():
        return f"错误：{path} 是目录，本工具只能删除文件"
    if not target.is_file():
        return f"错误：文件不存在：{path}"

    target.unlink()
    return f"已删除 {path}"


@mcp.tool()
def create_todo_list(items: str, filename: str = "todo.md") -> str:
    """根据待办事项生成 Markdown 待办清单文件并保存。

    参数 items 为待办事项，多个事项用中文或英文逗号分隔；
    filename 为保存的文件名，默认 "todo.md"。
    """
    try:
        target = resolve_safe(filename)
    except SandboxError as exc:
        return f"错误：{exc}"

    normalized = items.replace("，", ",").replace("、", ",")
    todos = [item.strip() for item in normalized.split(",") if item.strip()]
    if not todos:
        return "错误：未解析到任何待办事项"

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = [f"# 待办清单（{now}）", ""]
    lines += [f"- [ ] {todo}" for todo in todos]
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return f"已生成待办清单 {display_path(target)}，共 {len(todos)} 项：\n" + "\n".join(todos)


@mcp.tool()
def count_text(text: str) -> str:
    """统计一段文本的字数和字符数（中文字符按字计）。

    参数 text 为要统计的文本内容。
    """
    chars = len(text)
    cjk = sum(1 for ch in text if "一" <= ch <= "鿿")
    words = len(text.split())
    return f"字符数（含空格）：{chars}，中文字数：{cjk}，英文单词数：{words}"


@mcp.tool()
def get_current_time() -> str:
    """获取当前日期和时间（本地时区）。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S %A")


def main() -> None:
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
