"""OpenAI-compatible provider."""

import json
import requests
from typing import Iterator, List, Dict, Any
from .base import BaseProvider, Message


class OpenAIProvider(BaseProvider):
    def chat(self, messages: List[Message], stream: bool = True) -> Iterator[str]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "stream": stream,
        }

        if stream:
            response = requests.post(url, headers=headers, json=payload, stream=True, timeout=120)
            for line in response.iter_lines():
                if not line:
                    continue
                if line.startswith(b"data: "):
                    data = line[6:].decode("utf-8", errors="ignore")
                    if data.strip() == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except Exception:
                        continue
        else:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            data = response.json()
            yield data.get("choices", [{}])[0].get("message", {}).get("content", "")

    def chat_json(self, messages: List[Message], tools: list = None) -> Dict[str, Any]:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
