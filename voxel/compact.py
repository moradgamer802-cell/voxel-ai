"""Auto-compact for VOXEL sessions."""

import tiktoken
from typing import List
from voxel.providers.base import Message


def count_tokens(messages: List[Message]) -> int:
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        total = 0
        for m in messages:
            total += len(enc.encode(m.content))
        return total
    except Exception:
        return sum(len(m.content.split()) * 1.3 for m in messages)


def maybe_compact(messages: List[Message], threshold: float = 0.8, max_tokens: int = 100000) -> bool:
    tokens = count_tokens(messages)
    if tokens > max_tokens * threshold:
        return True
    return False


def compact_session(messages: List[Message]):
    if len(messages) < 4:
        return

    system = messages[0]
    recent = messages[-6:]
    middle = messages[1:-6]

    if not middle:
        return

    summary_parts = []
    for i in range(0, len(middle), 4):
        chunk = middle[i:i+4]
        for msg in chunk:
            if msg.role == "user":
                summary_parts.append(f"User: {msg.content[:200]}")
            elif msg.role == "assistant":
                summary_parts.append(f"Assistant: {msg.content[:200]}")

    summary = "Previous conversation summary:\n" + "\n".join(summary_parts[:20])
    messages[:] = [system, Message("user", summary)] + recent
