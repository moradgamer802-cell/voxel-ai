# VOXEL AI

A free AI agent CLI for Termux (Android terminal). Powered by OpenCode Zen free models — no API key or registration needed.

## Overview

`bangbot.py` is a pure-Python TUI (terminal UI) app. No external pip dependencies — stdlib only. Designed for Termux on Android, but runs anywhere with a Python 3.x terminal.

## How to run

```bash
python3 bangbot.py
```

Or in Termux after installing:
```bash
voxel
```

## Key files

- `bangbot.py` — main application (2800+ lines, self-contained)
- `install.sh` — one-line Termux installer (creates `voxel` alias)

## Architecture

- **TUI class** (`class UI`) — full-screen terminal UI using raw mode / ANSI escape codes
- **Streaming** — server-sent events from OpenCode Zen API with typewriter reveal
- **Tool execution** — AI can run shell commands, read/write files, search the web
- **Session manager** — JSON chat history in `~/.bangbot/chats/`
- **Permission system** — per-command/file allow/deny rules stored in `~/.bangbot/config.json`

## Design (v5 — Claude Code / OpenCode aesthetic)

- `◆` as the universal AI indicator (header, responses, mode chip)
- `▎` thin left-border accent on AI response cards (replaces heavy box)
- `─────` separator lines under the header bar
- `C_SEP` (`\033[38;5;237m`) for subtle separators; `C_ACC` purple for brand accents
- Panel backgrounds removed — clean terminal feel
- Unicode box-drawing logo (`██╗ ██║ ╚═╝` style) replacing plain block chars

## User preferences

- UI style: Claude Code / OpenCode CLI aesthetic — minimal, clean, `◆` indicator
