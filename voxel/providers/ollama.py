"""Ollama local provider."""

import json
import requests
from typing import Iterator, List, Dict, Any
from .base import BaseProvider, Message


class OllamaProvider(BaseProvider):
    def chat(self, messages: List[Message], stream: bool = True) -> Iterator[str]:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "stream": stream,
        }

        if stream:
            response = requests.post(url, json=payload, stream=True, timeout=120)
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "message" in data:
                        yield data["message"].get("content", "")
                except Exception:
                    continue
        else:
            response = requests.post(url, json=payload, timeout=120)
            data = response.json()
            yield data.get("message", {}).get("content", "")

    def chat_json(self, messages: List[Message], tools: list = None) -> Dict[str, Any]:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "stream": False,
        }
        if tools:
            payload["tools"] = tools

        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
