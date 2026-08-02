"""Memory bank for MRNOT."""

from pathlib import Path
from typing import Optional
from voxel.config import get_memory_path


def load_memory() -> str:
    path = get_memory_path()
    if path.exists():
        with open(path, "r") as f:
            return f.read()
    return ""


def save_memory(content: str):
    path = get_memory_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(content)


def format_memory_as_context(memory: str) -> str:
    if not memory.strip():
        return ""
    return f"Project Memory Bank:\n{memory}\n"


def init_memory(project_description: str = "") -> str:
    path = get_memory_path()
    if path.exists():
        with open(path, "r") as f:
            return f.read()

    content = f"""# MRNOT Memory Bank

## Project Description
{project_description or "No description yet."}

## Architecture
(Add architecture notes here)

## Key Decisions
(Add important decisions here)

## Active Tasks
(Add current tasks here)

## Patterns & Conventions
(Add coding patterns here)
"""
    save_memory(content)
    return content
