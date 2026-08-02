"""Base provider class for AI providers."""

from abc import ABC, abstractmethod
from typing import Iterator, List


class Message:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def to_dict(self):
        return {"role": self.role, "content": self.content}


class BaseProvider(ABC):
    def __init__(self, api_key: str, base_url: str, model: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    @abstractmethod
    def chat(self, messages: List[Message], stream: bool = True) -> Iterator[tuple]:
        """Yield (kind, text) where kind is 'content' or 'reasoning'."""
        pass
