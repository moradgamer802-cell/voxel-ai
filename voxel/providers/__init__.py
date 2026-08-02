"""OpenCode Zen provider implementation."""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterator, List

from voxel.providers.base import BaseProvider, Message
from voxel.constants import FREE_MODELS, API_BASE


class OpenCodeProvider(BaseProvider):
    def chat(self, messages: List[Message], stream: bool = True) -> Iterator[tuple]:
        body = json.dumps({
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "stream": True,
        }).encode()

        req = urllib.request.Request(
            API_BASE + "/chat/completions",
            data=body,
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("User-Agent", "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36")

        resp = urllib.request.urlopen(req, timeout=180)
        buffer = b""
        while True:
            chunk = resp.read(1024)
            if not chunk:
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                line = line.strip()
                if not line or not line.startswith(b"data:"):
                    continue
                data = line[5:].strip()
                if data == b"[DONE]":
                    return
                try:
                    obj = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = obj.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                content = delta.get("content")
                reasoning = delta.get("reasoning_content")
                if reasoning:
                    yield "reasoning", reasoning
                if content:
                    yield "content", content

    def chat_json(self, messages, tools=None):
        body = json.dumps({
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "stream": False,
            "tools": tools or [],
            "tool_choice": "auto" if tools else None,
        }).encode()

        req = urllib.request.Request(
            API_BASE + "/chat/completions",
            data=body,
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("User-Agent", "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36")

        resp = urllib.request.urlopen(req, timeout=180)
        return json.loads(resp.read().decode())


def fetch_models(api_key: str = "") -> List[str]:
    req = urllib.request.Request(API_BASE + "/models")
    if api_key:
        req.add_header("Authorization", f"Bearer {api_key}")
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode())
    return [m["id"] for m in data.get("data", [])]


PROVIDER_DEFAULTS = {
    "openai": {"base_url": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "anthropic": {"base_url": "https://api.anthropic.com", "model": "claude-3-5-sonnet-20240620"},
    "ollama": {"base_url": "http://localhost:11434/v1", "model": "llama3.1"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-1.5-pro"},
}


def get_provider(name: str, api_key: str, base_url: str, model: str):
    name = name.lower()
    if name == "opencode" or name == "openai":
        return OpenCodeProvider(api_key, base_url, model)
    if name == "anthropic":
        from voxel.providers.anthropic import AnthropicProvider
        return AnthropicProvider(api_key, base_url, model)
    if name == "ollama":
        from voxel.providers.ollama import OllamaProvider
        return OllamaProvider(api_key, base_url, model)
    if name == "gemini":
        from voxel.providers.gemini import GeminiProvider
        return GeminiProvider(api_key, base_url, model)
    return OpenCodeProvider(api_key, base_url, model)
