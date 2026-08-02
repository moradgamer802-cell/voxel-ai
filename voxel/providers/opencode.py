"""OpenCode Zen provider with fallback logic."""

import time
import urllib.error
from typing import List, Tuple

from voxel.providers.base import BaseProvider, Message
from voxel.constants import FREE_MODELS


class ProviderPool:
    def __init__(self, api_key: str, base_url: str, start_model: str):
        self.api_key = api_key
        self.base_url = base_url
        self.current_model = start_model
        self._fail = {}

    def chat(self, messages: List[Message]) -> Tuple[str, str, str]:
        """Returns (content, reasoning, error)."""
        order = [self.current_model] + [m for m in FREE_MODELS if m != self.current_model]
        now = time.time()
        tried = []
        key_error = None

        for m in order:
            if m in tried:
                continue
            if now - self._fail.get(m, 0) < 60:
                tried.append(m)
                continue
            tried.append(m)
            try:
                from voxel.providers.opencode import OpenCodeProvider
                p = OpenCodeProvider(self.api_key, self.base_url, m)
                parts = []
                reasoning_parts = []
                for kind, text in p.chat(messages):
                    if kind == "reasoning":
                        reasoning_parts.append(text)
                    else:
                        parts.append(text)
                self._fail.pop(m, None)
                self.current_model = m
                return "".join(parts), "".join(reasoning_parts), None
            except urllib.error.HTTPError as e:
                body = e.read().decode(errors="replace")[:200]
                if e.code == 401:
                    key_error = "API key invalid"
                    self._fail[m] = now
                    continue
                if e.code in (429, 403, 404, 400):
                    self._fail[m] = now
                    continue
                return "", "", f"HTTP {e.code}: {body}"
            except urllib.error.URLError as e:
                return "", "", f"Network error: {e.reason}"
            except Exception as e:
                return "", "", f"Error: {e}"

        if key_error and len(tried) == 1:
            return "", "", key_error
        return "", "", "All models rate-limited/error. Try later."
