"""Terminal execution tool for MRNOT."""

import subprocess
import os
from typing import Tuple


def run_command(command: str, timeout: int = 30, shell_path: str = None, shell_args: list = None) -> Tuple[int, str, str]:
    shell = shell_path or os.environ.get("SHELL", "/bin/bash")
    args = shell_args or ["-l", "-c"]
    try:
        result = subprocess.run(
            [shell] + args + [command],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout}s"
    except Exception as e:
        return -1, "", str(e)


def run_command_safe(command: str, timeout: int = 30) -> str:
    rc, out, err = run_command(command, timeout=timeout)
    if rc != 0:
        return f"[exit {rc}]\n{err or out}"
    return out
