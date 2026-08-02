"""CLI entry point for VOXEL."""

import sys
import click

from voxel.config import load_config, get_provider_config, set_provider_config
from voxel.providers import PROVIDER_DEFAULTS
from voxel.ui.term import TermUI
from voxel.tools import get_tool_definitions
from voxel.memory import init_memory, load_memory
from voxel.modes import list_modes
from voxel.session import list_sessions
from voxel.agent import Agent
from voxel.providers import get_provider


@click.group()
@click.version_option()
def cli():
    """VOXEL - AI Coding Assistant for Termux. Built like OpenCode / Kilo Code."""
    pass


@cli.command()
@click.option("--provider", "-p", type=click.Choice(["openai", "anthropic", "ollama", "gemini"]), help="AI provider")
@click.option("--api-key", "-k", help="API key")
@click.option("--base-url", "-u", help="Base URL for API")
@click.option("--model", "-m", help="Model name")
@click.option("--mode", type=click.Choice(["code", "plan", "ask", "debug", "review"]), help="Default agent mode")
def setup(provider, api_key, base_url, model, mode):
    """Configure VOXEL with your AI provider."""
    config = load_config()

    provider = provider or config.get("provider", "openai")
    api_key = api_key or config.get("api_key", "")
    base_url = base_url or config.get("base_url", "")
    model = model or config.get("model", "")

    if not base_url:
        base_url = PROVIDER_DEFAULTS.get(provider, {}).get("base_url", "")

    if not model:
        model = PROVIDER_DEFAULTS.get(provider, {}).get("model", "gpt-4o-mini")

    set_provider_config(provider, api_key, base_url, model, mode)
    click.echo(f"Configuration saved: {provider} / {model}")
    click.echo(f"Base URL: {base_url}")
    if mode:
        click.echo(f"Mode: {mode}")


@cli.command()
@click.argument("prompt", required=False)
@click.option("--auto", is_flag=True, help="Autonomous mode (no permission prompts)")
@click.option("--mode", "-m", type=click.Choice(["code", "plan", "ask", "debug", "review"]), help="Agent mode")
@click.option("--model", help="Override model")
@click.option("--output-format", "-f", type=click.Choice(["text", "json"]), default="text", help="Output format")
@click.option("--quiet", "-q", is_flag=True, help="Quiet mode (no spinner)")
@click.option("--continue", "-c", "continue_session", is_flag=True, help="Continue last session")
@click.option("--cwd", help="Working directory")
def run(prompt, auto, mode, model, output_format, quiet, continue_session, cwd):
    """Run VOXEL with a prompt (non-interactive)."""
    config = get_provider_config()
    provider_name = config.get("name", "openai")
    api_key = config.get("api_key", "")
    base_url = config.get("base_url", "")
    current_model = config.get("model", "gpt-4o-mini")
    current_mode = config.get("mode", "code")

    if model:
        current_model = model
    if mode:
        current_mode = mode

    if not api_key and provider_name != "ollama":
        click.echo("Error: No API key configured. Run: voxel setup", err=True)
        sys.exit(1)

    provider = get_provider(provider_name, api_key, base_url, current_model)
    agent = Agent(provider, current_mode)
    agent.init_context(cwd)

    if not quiet:
        click.echo(f"Running {provider_name}/{current_model} in {current_mode} mode...")

    try:
        response = agent.run(prompt, auto_approve=auto)
        if output_format == "json":
            click.echo(f'{{"response": "{response}", "tool_calls": {len(agent.tool_results)}}}')
        else:
            click.echo(response)
    except Exception as e:
        import traceback; traceback.print_exc()
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--mode", "-m", type=click.Choice(["code", "plan", "ask", "debug", "review"]), help="Agent mode")
@click.option("--model", help="Override model")
@click.option("--cwd", help="Working directory")
@click.option("--continue", "-c", "continue_session", is_flag=True, help="Continue last session")
def chat(mode, model, cwd, continue_session):
    """Start interactive chat session."""
    config = get_provider_config()
    provider_name = config.get("name", "openai")
    api_key = config.get("api_key", "")
    base_url = config.get("base_url", "")
    current_model = config.get("model", "gpt-4o-mini")
    current_mode = config.get("mode", "code")

    if model:
        current_model = model
    if mode:
        current_mode = mode

    if not api_key and provider_name != "ollama":
        click.echo("Error: No API key configured. Run: voxel setup", err=True)
        sys.exit(1)

    provider = get_provider(provider_name, api_key, base_url, current_model)
    agent = Agent(provider, current_mode)
    ui = TermUI(config, api_key, current_model)
    ui.enter()
    try:
        ui.input_loop(agent)
    finally:
        ui.exit()


@cli.command()
@click.argument("path", required=False)
def read(path):
    """Read a file."""
    from voxel.tools.filesystem import read_file
    content = read_file(path or ".")
    click.echo(content)


@cli.command()
@click.argument("command", required=True)
@click.option("--timeout", "-t", default=30, help="Timeout in seconds")
def exec_cmd(command, timeout):
    """Run a shell command (exec)."""
    from voxel.tools.terminal import run_command_safe
    result = run_command_safe(command, timeout=timeout)
    click.echo(result)


@cli.command()
@click.argument("path", required=False)
def ls(path):
    """List directory contents."""
    from voxel.tools.filesystem import list_directory
    result = list_directory(path or ".")
    click.echo(result)


@cli.command()
def sessions():
    """List sessions."""
    sessions = list_sessions()
    for s in sessions:
        click.echo(f"{s[0]}  {s[1]}  {s[2]} msgs  {s[3] or ''}")


@cli.command()
@click.argument("description", required=False)
def memory(description):
    """Initialize or view memory bank."""
    if description:
        content = init_memory(description)
        click.echo(f"Memory bank initialized at {get_memory_path()}")
    else:
        memory = load_memory()
        if memory:
            click.echo(memory)
        else:
            click.echo("No memory bank found. Use: voxel memory 'project description'")


@cli.command()
def modes():
    """List available agent modes."""
    modes = list_modes()
    for m in modes:
        click.echo(f"[cyan]{m['name']}[/cyan]: {m['description']}")


@cli.command()
def tools():
    """List available tools."""
    tools = get_tool_definitions()
    for tool in tools:
        func = tool.get("function", {})
        click.echo(f"[cyan]{func.get('name')}[/cyan]: {func.get('description')}")


@cli.command()
def auth():
    """Manage authentication."""
    config = load_config()
    provider = config.get("provider", "openai")
    api_key = config.get("api_key", "")
    base_url = config.get("base_url", "")

    click.echo(f"Provider: {provider}")
    click.echo(f"API Key: {'*' * len(api_key) if api_key else '(not set)'}")
    click.echo(f"Base URL: {base_url}")

    new_key = click.prompt("Enter new API key (or press Enter to skip)", default="", show_default=False)
    if new_key:
        set_provider_config(api_key=new_key)
        click.echo("API key updated.")


@cli.command()
@click.argument("path", required=False)
def edit(path):
    """Edit a file (opens in $EDITOR)."""
    import os
    editor = os.environ.get("EDITOR", "nano")
    if path:
        click.edit(filename=path, editor=editor)
    else:
        click.echo("Usage: voxel edit <file>")


def main():
    cli()


if __name__ == "__main__":
    main()
