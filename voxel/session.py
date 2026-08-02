"""Session management for VOXEL."""

import json
import uuid
import os
import re
import time
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from voxel.config import load_config, CHATS_DIR


def _safe_name(name: str) -> str:
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", str(name)).strip()
    return name or "chat"


def ensure_dir():
    Path(CHATS_DIR).mkdir(parents=True, exist_ok=True)


def create_session(session_id: str = None, mode: str = "code") -> dict:
    ensure_dir()
    if not session_id:
        session_id = str(uuid.uuid4())[:8]
    session = {
        "id": session_id,
        "mode": mode,
        "messages": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    path = os.path.join(CHATS_DIR, session_id + ".json")
    with open(path, "w") as f:
        json.dump(session, f, ensure_ascii=False, indent=2)
    return session


def save_session(name: str, messages: list):
    ensure_dir()
    name = _safe_name(name)
    path = os.path.join(CHATS_DIR, name + ".json")
    with open(path, "w") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
    return path


def load_session(name: str):
    name = _safe_name(name)
    path = os.path.join(CHATS_DIR, name + ".json")
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def append_message(session_id: str, role: str, content: str):
    session = load_session(session_id)
    if session is None:
        session = create_session(session_id)
    session.setdefault("messages", []).append({
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat(),
    })
    session["updated_at"] = datetime.now().isoformat()
    save_session(session_id, session)
    return session


def list_sessions():
    ensure_dir()
    out = []
    for f in os.listdir(CHATS_DIR):
        if f.endswith(".json"):
            p = os.path.join(CHATS_DIR, f)
            try:
                with open(p, "r") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    messages = data.get("messages", [])
                elif isinstance(data, list):
                    messages = data
                else:
                    continue
                mtime = os.path.getmtime(p)
                count = len([m for m in messages if m.get("role") != "system"])
                preview = ""
                for m in reversed(messages):
                    if m.get("role") == "user":
                        preview = m.get("content", "")[:30]
                        break
                out.append((f[:-5], mtime, count, preview))
            except Exception:
                continue
    out.sort(key=lambda x: -x[1])
    return out


def delete_session(name: str):
    name = _safe_name(name)
    path = os.path.join(CHATS_DIR, name + ".json")
    try:
        os.remove(path)
    except OSError:
        pass
