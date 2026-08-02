"""Git integration tools for VOXEL."""

from .terminal import run_command_safe


def git_status() -> str:
    return run_command_safe("git status --short") or "(no changes)"


def git_log(limit: int = 10) -> str:
    return run_command_safe(f"git log --oneline -n {limit}") or "(no history)"


def git_diff(path: str = None) -> str:
    if path:
        return run_command_safe(f"git diff -- {path}") or "(no diff)"
    return run_command_safe("git diff --stat") or "(no diff)"


def git_branch() -> str:
    return run_command_safe("git branch --show-current") or "(not a repo)"


def git_diff_staged() -> str:
    return run_command_safe("git diff --cached --stat") or "(no staged changes)"


def git_commit(message: str) -> str:
    return run_command_safe(f'git commit -m "{message}"')
