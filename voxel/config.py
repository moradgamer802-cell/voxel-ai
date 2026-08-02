"""Configuration management for MRNOT."""

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "mrnot"
CONFIG_FILE = CONFIG_DIR / "config.json"
CHATS_DIR = CONFIG_DIR / "chats"
COMMANDS_DIR = CONFIG_DIR / "commands"
PROJECT_COMMANDS_DIR = Path.cwd() / ".mrnot" / "commands"
MEMORY_FILE = Path.cwd() / ".mrnot" / "memory.md"


def ensure_dirs():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CHATS_DIR.mkdir(parents=True, exist_ok=True)
    COMMANDS_DIR.mkdir(parents=True, exist_ok=True)


def default_config():
    return {
        "provider": "openai",
        "api_key": "sk-PKOWRt2391BL0MP3W90yaG8qx4vofQJQgigJreBBYjrArj0lwuU1HkWUqOHgDGHP",
        "base_url": "https://opencode.ai/zen/v1",
        "model": "deepseek-v4-flash-free",
        "mode": "code",
        "auto_compact": True,
        "shell": {
            "path": os.environ.get("SHELL", "/bin/bash"),
            "args": ["-l"],
        },
        "mcpServers": {},
        "permissions": {
            "bash": "ask",
            "write_file": "ask",
            "edit_file": "ask",
            "git_commit": "ask",
        },
        "agents": {
            "code": {"model": "deepseek-v4-flash-free"},
            "plan": {"model": "deepseek-v4-flash-free"},
            "ask": {"model": "deepseek-v4-flash-free"},
            "debug": {"model": "deepseek-v4-flash-free"},
            "review": {"model": "deepseek-v4-flash-free"},
        },
    }


def load_config():
    ensure_dirs()
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    cfg = default_config()
    save_config(cfg)
    return cfg


def save_config(config):
    ensure_dirs()
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def get_provider_config():
    config = load_config()
    return {
        "name": config.get("provider", "openai"),
        "api_key": config.get("api_key", ""),
        "base_url": config.get("base_url", "https://opencode.ai/zen/v1"),
        "model": config.get("model", "deepseek-v4-flash-free"),
        "mode": config.get("mode", "code"),
    }


def set_provider_config(name=None, api_key=None, base_url=None, model=None, mode=None):
    config = load_config()
    if name is not None:
        config["provider"] = name
    if api_key is not None:
        config["api_key"] = api_key
    if base_url is not None:
        config["base_url"] = base_url
    if model is not None:
        config["model"] = model
    if mode is not None:
        config["mode"] = mode
    save_config(config)


def get_memory_path():
    return MEMORY_FILE


def get_commands_dirs():
    return [PROJECT_COMMANDS_DIR, COMMANDS_DIR]


def get_api_key(cfg):
    return os.environ.get("OPENCODE_API_KEY") or cfg.get("api_key", "").strip() or ""


PROVIDER_DEFAULTS = {
    "openai": {"base_url": "https://opencode.ai/zen/v1", "model": "deepseek-v4-flash-free"},
    "anthropic": {"base_url": "https://api.anthropic.com", "model": "claude-3-5-sonnet-20240620"},
    "ollama": {"base_url": "http://localhost:11434/v1", "model": "llama3.1"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-1.5-pro"},
}
