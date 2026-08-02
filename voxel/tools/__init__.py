"""Tool registry for VOXEL."""

from typing import Callable, Dict, List

TOOLS: Dict[str, Callable] = {}
TOOL_DEFINITIONS: List[dict] = []


def register(name: str, description: str, parameters: dict = None):
    def decorator(func: Callable):
        TOOLS[name] = func
        TOOL_DEFINITIONS.append({
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters or {"type": "object", "properties": {}},
            }
        })
        return func
    return decorator


from . import filesystem, terminal, git, lsp  # noqa: F401


@register("read_file", "Read the contents of a file", {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Path to the file"},
        "max_lines": {"type": "integer", "description": "Maximum lines to read", "default": 200},
        "offset": {"type": "integer", "description": "Line offset to start from", "default": 0},
    },
    "required": ["path"],
})
def tool_read_file(args: dict) -> str:
    return filesystem.read_file(
        args.get("path", ""),
        max_lines=args.get("max_lines", 200),
        offset=args.get("offset", 0),
    )


@register("write_file", "Write content to a file", {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Path to the file"},
        "content": {"type": "string", "description": "Content to write"},
    },
    "required": ["path", "content"],
})
def tool_write_file(args: dict) -> str:
    return filesystem.write_file(args.get("path", ""), args.get("content", ""))


@register("list_directory", "List directory contents", {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Directory path", "default": "."},
        "ignore": {"type": "array", "items": {"type": "string"}, "description": "Glob patterns to ignore"},
    },
})
def tool_list_directory(args: dict) -> str:
    return filesystem.list_directory(args.get("path", "."), ignore=args.get("ignore"))


@register("glob", "Find files by pattern", {
    "type": "object",
    "properties": {
        "pattern": {"type": "string", "description": "Glob pattern to match"},
        "path": {"type": "string", "description": "Directory to search", "default": "."},
    },
    "required": ["pattern"],
})
def tool_glob(args: dict) -> str:
    return filesystem.glob_files(args.get("pattern", "*"), args.get("path", "."))


@register("grep", "Search file contents", {
    "type": "object",
    "properties": {
        "pattern": {"type": "string", "description": "Pattern to search for"},
        "path": {"type": "string", "description": "Directory to search", "default": "."},
        "include": {"type": "string", "description": "File glob to include"},
        "literal_text": {"type": "boolean", "description": "Use literal text search", "default": False},
    },
    "required": ["pattern"],
})
def tool_grep(args: dict) -> str:
    return filesystem.grep(
        args.get("pattern", ""),
        args.get("path", "."),
        include=args.get("include"),
        literal=args.get("literal_text", False),
    )


@register("bash", "Execute a shell command", {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "Shell command to run"},
        "timeout": {"type": "integer", "description": "Timeout in seconds", "default": 30},
    },
    "required": ["command"],
})
def tool_bash(args: dict) -> str:
    rc, out, err = terminal.run_command(
        args.get("command", ""),
        timeout=args.get("timeout", 30),
    )
    if rc != 0:
        return f"[exit {rc}]\n{err or out}"
    return out


@register("git_status", "Show git status", {"type": "object", "properties": {}})
def tool_git_status(args: dict) -> str:
    return git.git_status()


@register("git_log", "Show git log", {
    "type": "object",
    "properties": {
        "limit": {"type": "integer", "description": "Number of commits", "default": 10},
    },
})
def tool_git_log(args: dict) -> str:
    return git.git_log(args.get("limit", 10))


@register("git_diff", "Show git diff", {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Specific file to diff"},
    },
})
def tool_git_diff(args: dict) -> str:
    return git.git_diff(args.get("path"))


@register("git_commit", "Commit staged changes", {
    "type": "object",
    "properties": {
        "message": {"type": "string", "description": "Commit message"},
    },
    "required": ["message"],
})
def tool_git_commit(args: dict) -> str:
    return git.git_commit(args.get("message", ""))


@register("diagnostics", "Get LSP diagnostics for a file", {
    "type": "object",
    "properties": {
        "file_path": {"type": "string", "description": "Path to the file"},
    },
    "required": ["file_path"],
})
def tool_diagnostics(args: dict) -> str:
    return lsp.get_diagnostics(args.get("file_path", ""))


def get_tool_definitions() -> List[dict]:
    return TOOL_DEFINITIONS


def execute_tool(name: str, args: dict) -> str:
    func = TOOLS.get(name)
    if not func:
        return f"Unknown tool: {name}"
    try:
        return func(args)
    except Exception as e:
        return f"Tool error ({name}): {e}"
