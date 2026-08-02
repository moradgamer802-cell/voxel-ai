"""AI provider registry."""

from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from .ollama import OllamaProvider
from .gemini import GeminiProvider

PROVIDERS = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "ollama": OllamaProvider,
    "gemini": GeminiProvider,
}

PROVIDER_DEFAULTS = {
    "openai": {"base_url": "https://opencode.ai/zen/v1", "model": "deepseek-v4-flash-free"},
    "anthropic": {"base_url": "https://api.anthropic.com", "model": "claude-3-5-sonnet-20240620"},
    "ollama": {"base_url": "http://localhost:11434/v1", "model": "llama3.1"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-1.5-pro"},
}


def get_provider(name: str, api_key: str, base_url: str, model: str):
    cls = PROVIDERS.get(name)
    if not cls:
        raise ValueError(f"Unknown provider: {name}")
    return cls(api_key=api_key, base_url=base_url, model=model)
