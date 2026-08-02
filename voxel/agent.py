"""Agent loop for MRNOT."""

import json
from typing import List, Dict, Any, Optional
from voxel.providers.base import Message, BaseProvider
from voxel.tools import get_tool_definitions, execute_tool
from voxel.config import load_config, get_memory_path, get_commands_dirs
from voxel.memory import load_memory, format_memory_as_context
from voxel.compact import maybe_compact
from voxel.permissions import check_permission, record_permission
from voxel.modes import get_mode_prompt


class Agent:
    def __init__(self, provider: BaseProvider, mode: str = "code", session_id: str = None):
        self.provider = provider
        self.mode = mode
        self.session_id = session_id
        self.messages: List[Message] = []
        self.tool_results: List[Dict] = []
        self.max_iterations = 20
        self.compact_threshold = 0.8

    def init_context(self, cwd: str = None):
        config = load_config()
        mode_prompt = get_mode_prompt(self.mode)
        memory = load_memory()
        memory_context = format_memory_as_context(memory)

        system_parts = [
            mode_prompt,
            "You are MRNOT, an AI coding assistant running in the terminal.",
            "You have access to tools to read files, write files, search code, run commands, and use git.",
            "When you need to use a tool, respond with a JSON object in this format:",
            '{"tool": "tool_name", "args": {"param": "value"}, "thought": "why you are using this tool"}',
            "After using a tool, you will see the result and can continue.",
            "Keep responses concise. When the task is complete, say DONE.",
            memory_context,
        ]

        commands_context = self._load_commands()
        if commands_context:
            system_parts.append(f"\nAvailable custom commands:\n{commands_context}")

        system = "\n".join(system_parts)
        self.messages = [Message("system", system)]

    def _load_commands(self) -> str:
        config = load_config()
        commands = []
        for cmd_dir in get_commands_dirs():
            if cmd_dir.exists():
                for cmd_file in cmd_dir.glob("*.md"):
                    cmd_name = cmd_file.stem
                    with open(cmd_file, "r") as f:
                        content = f.read().strip()
                    commands.append(f"- {cmd_name}: {content[:100]}...")
        return "\n".join(commands) if commands else ""

    def run(self, user_input: str, auto_approve: bool = False) -> str:
        self.messages.append(Message("user", user_input))
        iterations = 0
        final_response = ""

        while iterations < self.max_iterations:
            iterations += 1

            if maybe_compact(self.messages, threshold=self.compact_threshold):
                self._compact_session()

            response = self._call_provider_with_tools()

            if response.get("tool_calls"):
                tool_results = []
                for tc in response["tool_calls"]:
                    tool_name = tc.get("tool")
                    tool_args = tc.get("args", {})
                    thought = tc.get("thought", "")

                    if thought:
                        self._append_assistant(f"💭 {thought}\n")

                    allowed, reason = check_permission(tool_name, auto_approve=auto_approve)
                    if not allowed:
                        result = f"Permission denied: {reason}"
                        self._append_assistant(f"⚠ {result}\n")
                    else:
                        result = execute_tool(tool_name, tool_args)
                        self._append_assistant(f"🔧 {tool_name}: {result[:500]}\n")

                    tool_results.append({
                        "tool": tool_name,
                        "args": tool_args,
                        "result": result[:2000],
                    })
                    self.tool_results.append(tool_results[-1])

                tool_msg = "\n".join(
                    f"Tool {tr['tool']} returned:\n{tr['result']}"
                    for tr in tool_results
                )
                self.messages.append(Message("user", tool_msg))
                continue

            content = response.get("content", "")
            self.messages.append(Message("assistant", content))
            final_response = content
            break

        return final_response

    def _call_provider_with_tools(self) -> Dict[str, Any]:
        tools = get_tool_definitions()
        try:
            response = self.provider.chat_json(self.messages, tools=tools)
            message = response.get("choices", [{}])[0].get("message", {})
            content = message.get("content", "") or ""

            tool_calls = []
            if message.get("tool_calls"):
                for tc in message["tool_calls"]:
                    func = tc.get("function", {})
                    try:
                        args = json.loads(func.get("arguments", "{}"))
                    except Exception:
                        args = {}
                    tool_calls.append({
                        "tool": func.get("name"),
                        "args": args,
                    })
            elif "{" in content and "tool" in content:
                try:
                    start = content.index("{")
                    end = content.rindex("}") + 1
                    parsed = json.loads(content[start:end])
                    if "tool" in parsed:
                        tool_calls.append(parsed)
                except Exception:
                    pass

            return {"content": content, "tool_calls": tool_calls}
        except Exception as e:
            return {"content": f"Error: {e}", "tool_calls": []}

    def _append_assistant(self, text: str):
        if self.messages and self.messages[-1].role == "assistant":
            self.messages[-1].content += text
        else:
            self.messages.append(Message("assistant", text))

    def _compact_session(self):
        if len(self.messages) < 4:
            return
        from voxel.compact import compact_session
        compact_session(self.messages)

    def send(self, text: str, ui=None) -> str:
        result = self.run(text, auto_approve=getattr(ui, 'auto_approve', False))
        if ui:
            ui.messages = [{"role": m.role, "content": m.content} for m in self.messages]
        return result

    def _undo(self):
        if len(self.messages) > 2:
            self.messages = self.messages[:-2]
            return "Undo: removed last exchange"
        return "Nothing to undo"

    def _run_command(self, cmd: str) -> str:
        if cmd == "/new":
            self.messages = [self.messages[0]]
            return "New session started"
        if cmd == "/clear":
            self.messages = [self.messages[0]]
            return "Context cleared"
        if cmd == "/compact":
            from voxel.compact import compact_session
            compact_session(self.messages)
            return "Session compacted"
        return f"Command: {cmd}"
