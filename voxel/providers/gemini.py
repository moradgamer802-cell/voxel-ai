"""Gemini provider."""

import json
import requests
from typing import Iterator, List, Dict, Any
from .base import BaseProvider, Message


class GeminiProvider(BaseProvider):
    def chat(self, messages: List[Message], stream: bool = True) -> Iterator[str]:
        url = f"{self.base_url}/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        contents = []
        for m in messages:
            if m.role == "system":
                contents.append({"role": "user", "parts": [{"text": m.content}]})
            else:
                contents.append({"role": m.role, "parts": [{"text": m.content}]})
        payload = {"contents": contents}

        if stream:
            url += "&alt=sse"
            response = requests.post(url, headers=headers, json=payload, stream=True, timeout=120)
            for line in response.iter_lines():
                if not line:
                    continue
                if line.startswith(b"data: "):
                    data = line[6:].decode("utf-8", errors="ignore")
                    try:
                        chunk = json.loads(data)
                        text = chunk.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        if text:
                            yield text
                    except Exception:
                        continue
        else:
            response = requests.post(url, headers=headers, json=payload, timeout=120)
            data = response.json()
            yield data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")

    def chat_json(self, messages: List[Message], tools: list = None) -> Dict[str, Any]:
        url = f"{self.base_url}/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        contents = []
        for m in messages:
            if m.role == "system":
                contents.append({"role": "user", "parts": [{"text": m.content}]})
            else:
                contents.append({"role": m.role, "parts": [{"text": m.content}]})
        payload = {"contents": contents}
        if tools:
            payload["tools"] = tools

        response = requests.post(url, headers=headers, json=payload, timeout=120)
        response.raise_for_status()
        return response.json()
