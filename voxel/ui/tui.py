"""Textual TUI for MRNOT."""

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widgets import (
    Header, Footer, Static, TextArea, RichLog, Button, Input, Label,
    ContentSwitcher, TabbedContent, TabPane, DataTable, DirectoryTree
)
from textual.reactive import reactive
from textual import events
from textual.binding import Binding
from textual.screen import ModalScreen
from rich.text import Text
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax
import time
from typing import Optional, List
from voxel.agent import Agent
from voxel.providers import get_provider
from voxel.config import load_config, get_provider_config, set_provider_config, get_memory_path
from voxel.session import create_session, save_session, list_sessions, load_session, append_message
from voxel.modes import list_modes, get_mode_prompt
from voxel.permissions import check_permission, record_permission
from voxel.memory import init_memory, load_memory, save_memory
from voxel.tools import execute_tool
from voxel.providers.base import Message


class PermissionDialog(ModalScreen[bool]):
    def __init__(self, tool_name: str, args: dict, result_preview: str = ""):
        super().__init__()
        self.tool_name = tool_name
        self.args = args
        self.result_preview = result_preview
        self.result = False

    def compose(self) -> ComposeResult:
        with Container(id="permission-dialog"):
            yield Label(f"[bold red]Permission Required[/bold red]")
            yield Label(f"Tool: [cyan]{self.tool_name}[/cyan]")
            yield Label(f"Args: {self.args}")
            if self.result_preview:
                yield Label(f"Result: {self.result_preview[:200]}")
            with Horizontal():
                yield Button("Allow Once", id="allow_once", variant="primary")
                yield Button("Allow Session", id="allow_session", variant="success")
                yield Button("Deny", id="deny", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "allow_once":
            self.result = True
            self.dismiss(True)
        elif event.button.id == "allow_session":
            self.result = True
            record_permission(self.tool_name, allow_session=True)
            self.dismiss(True)
        elif event.button.id == "deny":
            self.result = False
            self.dismiss(False)


class ModelDialog(ModalScreen[str]):
    def __init__(self, current_model: str, providers: list):
        super().__init__()
        self.current_model = current_model
        self.providers = providers

    def compose(self) -> ComposeResult:
        with Container(id="model-dialog"):
            yield Label("[bold cyan]Select Model[/bold cyan]")
            with Vertical(id="model-list"):
                for provider in self.providers:
                    yield Button(f"{provider['name']}: {provider['model']}", id=f"model-{provider['name']}")
            yield Button("Close", id="close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close":
            self.dismiss(None)
        elif event.button.id.startswith("model-"):
            provider_name = event.button.id.replace("model-", "")
            for p in self.providers:
                if p["name"] == provider_name:
                    self.dismiss(p["model"])
                    return
            self.dismiss(None)


class SessionDialog(ModalScreen[str]):
    def __init__(self, sessions: list):
        super().__init__()
        self.sessions = sessions

    def compose(self) -> ComposeResult:
        with Container(id="session-dialog"):
            yield Label("[bold cyan]Select Session[/bold cyan]")
            with Vertical(id="session-list"):
                for session in self.sessions[:20]:
                    label = f"{session['id']} - {session.get('cwd', '')} ({session.get('created_at', '')[:19]})"
                    yield Button(label, id=f"session-{session['id']}")
                yield Button("New Session", id="new-session")
            yield Button("Close", id="close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "close":
            self.dismiss(None)
        elif event.button.id == "new-session":
            self.dismiss("__new__")
        elif event.button.id.startswith("session-"):
            self.dismiss(event.button.id.replace("session-", ""))


class VoxelTUI(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    #main-container {
        layout: horizontal;
        height: 1fr;
    }
    #sidebar {
        width: 30;
        dock: left;
        background: $surface;
        border: solid $primary;
    }
    #chat-area {
        height: 1fr;
    }
    #messages {
        height: 1fr;
        overflow-y: auto;
        padding: 1;
    }
    #input-area {
        height: 5;
        dock: bottom;
        background: $surface;
        border: solid $primary;
        padding: 1;
    }
    #input {
        width: 1fr;
    }
    #status-bar {
        height: 1;
        background: $primary;
        color: $text;
        content-align: center middle;
    }
    PermissionDialog {
        align: center middle;
    }
    #permission-dialog {
        width: 60;
        height: 15;
        background: $surface;
        border: thick $error;
        padding: 1;
    }
    ModelDialog {
        align: center middle;
    }
    #model-dialog {
        width: 60;
        height: 20;
        background: $surface;
        border: thick $primary;
        padding: 1;
    }
    SessionDialog {
        align: center middle;
    }
    #session-dialog {
        width: 70;
        height: 20;
        background: $surface;
        border: thick $primary;
        padding: 1;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+n", "new_session", "New Session", show=True),
        Binding("ctrl+a", "switch_session", "Sessions", show=True),
        Binding("ctrl+k", "command_palette", "Commands", show=True),
        Binding("ctrl+o", "switch_model", "Model", show=True),
        Binding("ctrl+m", "switch_mode", "Mode", show=True),
        Binding("ctrl+l", "clear_chat", "Clear", show=True),
        Binding("escape", "cancel", "Cancel", show=True),
        Binding("ctrl+x", "cancel", "Cancel", show=True),
    ]

    mode = reactive("code")
    session_id: Optional[str] = None
    is_streaming = reactive(False)
    auto_approve = False
    provider_name = "openai"
    current_model = "gpt-4o-mini"

    def __init__(self, provider_name: str, api_key: str, base_url: str, model: str, mode: str, cwd: str = None):
        super().__init__()
        self.provider_name = provider_name
        self.api_key = api_key
        self.base_url = base_url
        self.current_model = model
        self.mode = mode
        self.cwd = cwd
        self.provider = get_provider(provider_name, api_key, base_url, model)
        self.session_id = create_session(cwd)
        self.agent = Agent(self.provider, mode, self.session_id)
        self.agent.init_context(cwd)

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="main-container"):
            with Vertical(id="sidebar"):
                yield Static("[bold]Sessions[/bold]")
                yield RichLog(id="session-list", wrap=True, highlight=True)
            with Container(id="chat-area"):
                yield RichLog(id="messages", wrap=True, highlight=True, auto_scroll=True)
                yield Static("", id="status-bar")
                yield TextArea(id="input", placeholder="Type a message... (/ for commands)")
        yield Footer()

    def on_mount(self):
        self.update_sessions()
        self.update_status()
        self.query_one("#input").focus()

    def update_status(self):
        mode_desc = get_mode_prompt(self.mode).split('\n')[0]
        status = f"[{self.mode.upper()}] {self.provider_name}/{self.current_model} | Session: {self.session_id}"
        self.query_one("#status-bar").update(status)

    def update_sessions(self):
        sessions = list_sessions()
        log = self.query_one("#session-list", RichLog)
        log.clear()
        for s in sessions[:20]:
            log.write(f"[cyan]{s[0]}[/cyan] [dim]{s[3] or ''}[/dim]")

    def on_text_area_submitted(self, event: TextArea.Submitted):
        if self.is_streaming:
            return
        text = event.value.strip()
        if not text:
            return
        self.query_one("#input").clear()
        self.handle_input(text)

    def handle_input(self, text: str):
        if text.startswith("/"):
            self.handle_command(text)
            return

        messages = self.query_one("#messages", RichLog)
        messages.write(Panel(Text(text, style="bold green"), title="[bold green]You[/bold green]", border_style="green"))

        append_message(self.session_id, "user", text)
        self.is_streaming = True
        self.query_one("#status-bar").update(f"[{self.mode.upper()}] {self.provider_name}/{self.current_model} | Thinking...")

        try:
            response = self.agent.run(text, auto_approve=self.auto_approve)
            messages.write(Panel(Markdown(response), title="[bold cyan]MRNOT[/bold cyan]", border_style="cyan"))
            append_message(self.session_id, "assistant", response)
        except Exception as e:
            messages.write(f"[red]Error: {e}[/red]")
        finally:
            self.is_streaming = False
            self.update_status()
            self.update_sessions()

    def handle_command(self, text: str):
        parts = text.split()
        cmd = parts[0].lower()
        args = parts[1:]

        commands = {
            "/help": self.cmd_help,
            "/clear": self.cmd_clear,
            "/undo": self.cmd_undo,
            "/compact": self.cmd_compact,
            "/model": self.cmd_model,
            "/mode": self.cmd_mode,
            "/mcp": self.cmd_mcp,
            "/memory": self.cmd_memory,
            "/permissions": self.cmd_permissions,
            "/session": self.cmd_session,
            "/agents": self.cmd_agents,
            "/exit": self.action_quit,
            "/quit": self.action_quit,
        }

        handler = commands.get(cmd)
        if handler:
            handler(args)
        else:
            self.query_one("#messages", RichLog).write(f"[red]Unknown command: {cmd}[/red]")

    def cmd_help(self, args):
        help_text = """
[bold cyan]Available Commands:[/bold cyan]
  /help          - Show this help
  /clear         - Clear conversation
  /undo          - Undo last change
  /compact       - Compact session context
  /model <name>  - Switch model
  /mode <name>   - Switch agent mode (code/plan/ask/debug/review)
  /mcp           - Manage MCP servers
  /memory        - View/edit memory bank
  /permissions   - View permissions
  /session       - Switch sessions
  /agents        - List agent modes
  /exit, /quit   - Exit
"""
        self.query_one("#messages", RichLog).write(help_text)

    def cmd_clear(self, args):
        self.query_one("#messages", RichLog).clear()
        self.agent.messages = self.agent.messages[:1] if self.agent.messages else []
        self.query_one("#messages", RichLog).write("[dim]Context cleared.[/dim]")

    def cmd_undo(self, args):
        self.query_one("#messages", RichLog).write("[dim]Undo not yet implemented.[/dim]")

    def cmd_compact(self, args):
        from voxel.compact import compact_session
        compact_session(self.agent.messages)
        self.query_one("#messages", RichLog).write("[dim]Session compacted.[/dim]")

    def cmd_model(self, args):
        if args:
            model = args[0]
            self.current_model = model
            set_provider_config(model=model)
            self.provider = get_provider(self.provider_name, self.api_key, self.base_url, model)
            self.agent.provider = self.provider
            self.update_status()
            self.query_one("#messages", RichLog).write(f"[dim]Model switched to: {model}[/dim]")
        else:
            self.query_one("#messages", RichLog).write(f"[dim]Current model: {self.current_model}[/dim]")

    def cmd_mode(self, args):
        if args:
            mode = args[0].lower()
            from voxel.modes import MODES
            if mode in MODES:
                self.mode = mode
                self.agent.mode = mode
                self.agent.init_context(self.cwd)
                self.update_status()
                self.query_one("#messages", RichLog).write(f"[dim]Mode switched to: {mode}[/dim]")
            else:
                self.query_one("#messages", RichLog).write(f"[red]Unknown mode: {mode}. Available: {', '.join(MODES.keys())}[/red]")
        else:
            self.query_one("#messages", RichLog).write(f"[dim]Current mode: {self.mode}[/dim]")

    def cmd_mcp(self, args):
        config = load_config()
        servers = config.get("mcpServers", {})
        if not servers:
            self.query_one("#messages", RichLog).write("[dim]No MCP servers configured.[/dim]")
        else:
            for name, cfg in servers.items():
                self.query_one("#messages", RichLog).write(f"[cyan]{name}[/cyan]: {cfg}")

    def cmd_memory(self, args):
        memory = load_memory()
        if not memory:
            self.query_one("#messages", RichLog).write("[dim]No memory bank found. Use /memory init to create one.[/dim]")
        else:
            self.query_one("#messages", RichLog).write(Panel(Markdown(memory[:2000]), title="Memory Bank", border_style="yellow"))

    def cmd_permissions(self, args):
        config = load_config()
        perms = config.get("permissions", {})
        for tool, perm in perms.items():
            self.query_one("#messages", RichLog).write(f"[cyan]{tool}[/cyan]: {perm}")

    def cmd_session(self, args):
        if args and args[0] == "new":
            self.session_id = create_session(self.cwd)
            self.agent = Agent(self.provider, self.mode, self.session_id)
            self.agent.init_context(self.cwd)
            self.update_status()
            self.query_one("#messages", RichLog).write(f"[dim]New session: {self.session_id}[/dim]")
        else:
            self.action_switch_session()

    def cmd_agents(self, args):
        modes = list_modes()
        for m in modes:
            self.query_one("#messages", RichLog).write(f"[cyan]{m['name']}[/cyan]: {m['description']}")

    def action_new_session(self):
        self.session_id = create_session(self.cwd)
        self.agent = Agent(self.provider, self.mode, self.session_id)
        self.agent.init_context(self.cwd)
        self.query_one("#messages", RichLog).clear()
        self.query_one("#messages", RichLog).write(f"[dim]New session: {self.session_id}[/dim]")
        self.update_status()
        self.update_sessions()

    def action_switch_session(self):
        sessions = list_sessions()
        if not sessions:
            self.query_one("#messages", RichLog).write("[dim]No previous sessions.[/dim]")
            return
        self.push_screen(SessionDialog(sessions), self._on_session_selected)

    def _on_session_selected(self, session_id: Optional[str]):
        if session_id == "__new__":
            self.action_new_session()
            return
        if session_id:
            data = load_session(session_id)
            if data:
                self.session_id = session_id
                self.agent = Agent(self.provider, self.mode, session_id)
                self.agent.messages = [Message(m["role"], m["content"]) for m in data.get("messages", [])]
                self.query_one("#messages", RichLog).clear()
                for m in data.get("messages", []):
                    if m["role"] == "user":
                        self.query_one("#messages", RichLog).write(Panel(Text(m["content"], style="bold green"), title="[bold green]You[/bold green]", border_style="green"))
                    elif m["role"] == "assistant":
                        self.query_one("#messages", RichLog).write(Panel(Markdown(m["content"]), title="[bold cyan]MRNOT[/bold cyan]", border_style="cyan"))
                self.update_status()
                self.update_sessions()

    def action_switch_model(self):
        from voxel.config import PROVIDER_DEFAULTS
        providers = []
        for name, defaults in PROVIDER_DEFAULTS.items():
            providers.append({"name": name, "model": defaults["model"]})
        self.push_screen(ModelDialog(self.current_model, providers), self._on_model_selected)

    def _on_model_selected(self, model: Optional[str]):
        if model:
            self.current_model = model
            set_provider_config(model=model)
            self.provider = get_provider(self.provider_name, self.api_key, self.base_url, model)
            self.agent.provider = self.provider
            self.update_status()
            self.query_one("#messages", RichLog).write(f"[dim]Model switched to: {model}[/dim]")

    def action_switch_mode(self):
        modes = list_modes()
        for i, m in enumerate(modes):
            self.query_one("#messages", RichLog).write(f"[cyan]{m['name']}[/cyan]: {m['description']}")

    def action_clear_chat(self):
        self.query_one("#messages", RichLog).clear()
        self.agent.messages = self.agent.messages[:1] if self.agent.messages else []
        self.query_one("#messages", RichLog).write("[dim]Context cleared.[/dim]")

    def action_command_palette(self):
        self.query_one("#messages", RichLog).write("[dim]Commands: /help /clear /undo /compact /model /mode /mcp /memory /permissions /session /agents /exit[/dim]")

    def action_cancel(self):
        self.is_streaming = False
        self.query_one("#input").focus()

    def action_quit(self):
        save_session(self.session_id, {
            "id": self.session_id,
            "cwd": self.cwd or str(Path.cwd()),
            "messages": [{"role": m.role, "content": m.content} for m in self.agent.messages],
        })
        self.exit()
