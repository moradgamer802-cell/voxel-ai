"""Permission system for MRNOT."""

from typing import Tuple
from voxel.config import load_config


def check_permission(tool_name: str, auto_approve: bool = False) -> Tuple[bool, str]:
    if auto_approve:
        return True, "auto-approved"

    config = load_config()
    permissions = config.get("permissions", {})

    session_allowed = getattr(check_permission, "_session_allowed", set())
    if tool_name in session_allowed:
        return True, "session-allowed"

    perm = permissions.get(tool_name, "ask")

    if perm == "allow":
        return True, "always-allowed"
    if perm == "deny":
        return False, "denied by config"

    return None, "needs-confirmation"


def record_permission(tool_name: str, allow_session: bool = False):
    if allow_session:
        allowed = getattr(record_permission, "_session_allowed", set())
        allowed.add(tool_name)
        setattr(record_permission, "_session_allowed", allowed)


def get_permission_prompt(tool_name: str, args: dict, result: str = "") -> str:
    return f"Allow {tool_name} with args: {args}?\nResult preview: {result[:100]}"
