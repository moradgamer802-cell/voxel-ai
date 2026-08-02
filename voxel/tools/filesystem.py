"""File system tools for VOXEL."""

import os
import fnmatch
from pathlib import Path
from typing import List, Optional


def read_file(path: str, max_lines: int = 200, offset: int = 0) -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: file not found: {path}"
    if not p.is_file():
        return f"Error: not a file: {path}"
    try:
        with open(p, "r", errors="replace") as f:
            lines = []
            for i, line in enumerate(f):
                if i < offset:
                    continue
                if len(lines) >= max_lines:
                    lines.append(f"\n... (truncated, {max_lines} lines shown)")
                    break
                lines.append(line)
        return "".join(lines)
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str) -> str:
    p = Path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            f.write(content)
        return f"Written to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def list_directory(path: str = ".", ignore: List[str] = None) -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: path not found: {path}"
    if not p.is_dir():
        return f"Error: not a directory: {path}"
    ignore = ignore or []
    entries = []
    for entry in sorted(p.iterdir()):
        name = entry.name
        if any(fnmatch.fnmatch(name, pattern) for pattern in ignore):
            continue
        if entry.is_dir():
            entries.append(f"[DIR]  {name}/")
        else:
            entries.append(f"[FILE] {name}")
    return "\n".join(entries)


def glob_files(pattern: str, path: str = ".") -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: path not found: {path}"
    matches = []
    for root, dirs, files in os.walk(p):
        for f in files:
            filepath = Path(root) / f
            relpath = filepath.relative_to(p)
            if fnmatch.fnmatch(str(relpath), pattern) or fnmatch.fnmatch(f, pattern):
                matches.append(str(relpath))
    return "\n".join(sorted(matches)) if matches else "(no matches)"


def grep(pattern: str, path: str = ".", include: str = None, literal: bool = False) -> str:
    import re
    p = Path(path)
    if not p.exists():
        return f"Error: path not found: {path}"
    results = []
    for root, dirs, files in os.walk(p):
        for f in files:
            filepath = Path(root) / f
            if include and not fnmatch.fnmatch(f, include):
                continue
            try:
                with open(filepath, "r", errors="replace") as fh:
                    for i, line in enumerate(fh, 1):
                        if literal:
                            if pattern in line:
                                results.append(f"{filepath}:{i}:{line.rstrip()}")
                        else:
                            if re.search(pattern, line):
                                results.append(f"{filepath}:{i}:{line.rstrip()}")
            except Exception:
                continue
    return "\n".join(results[:100]) if results else "(no matches)"
