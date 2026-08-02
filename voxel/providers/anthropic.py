"""Anthropic Claude provider."""

import json
import requests
from typing import Iterator, List, Dict, Any
from .base import BaseProvider, Message


class AnthropicProvider(BaseProvider):
    def chat(self, messages: List[Message], stream: bool = True) -> Iterator[str]:
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        system_prompt = ""
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_prompt = m.content
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": chat_messages,
            "stream": stream,
        }

        if stream:
            response = requests.post(url, headers=headers, json=payload, stream=True, timeout=120)
            for line in response.iter_lines():
                if not line:
                    continue
                if line.startswith(b"data: "):
                    data = line[6:].decode("utf-8", errors="ignore")
                    try:
                        event = json.loads(data)
                        if event.get("type") == "content_block_delta":
                            yield event.get("delta", {}).get("text", "")
                    except Exception:
                        continue
        else:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            data = response.json()
            content_blocks = data.get("content", [])
            yield "".join(block.get("text", "") for block in content_blocks)

    def chat_json(self, messages: List[Message], tools: list = None) -> Dict[str, Any]:
        url = f"{self.base_url}/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        system_prompt = ""
        chat_messages = []
        for m in messages:
            if m.role == "system":
                system_prompt = m.content
            else:
                chat_messages.append({"role": m.role, "content": m.content})

        payload = {
            "model": self.model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": chat_messages,
        }
        if tools:
            payload["tools"] = tools

        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
