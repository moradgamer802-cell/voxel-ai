"""LSP integration tools for MRNOT."""

import json
import subprocess
from typing import List, Tuple


def get_diagnostics(file_path: str, lsp_command: str = None) -> str:
    cmd = lsp_command or "pylsp"
    try:
        proc = subprocess.Popen(
            [cmd, "--stdio"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        init_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "processId": None,
                "rootUri": f"file://{file_path}",
                "capabilities": {}
            }
        }) + "\n"
        proc.stdin.write(init_request)
        proc.stdin.flush()
        proc.stdin.read()

        open_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "textDocument/didOpen",
            "params": {
                "textDocument": {"uri": f"file://{file_path}", "languageId": "python", "version": 1, "text": ""}
            }
        }) + "\n"
        proc.stdin.write(open_request)
        proc.stdin.flush()

        diag_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "textDocument/diagnostic",
            "params": {"textDocument": {"uri": f"file://{file_path}"}}
        }) + "\n"
        proc.stdin.write(diag_request)
        proc.stdin.flush()

        result = proc.stdout.readline()
        proc.terminate()
        return result.strip() or "(no diagnostics)"
    except Exception as e:
        return f"LSP error: {e}"
