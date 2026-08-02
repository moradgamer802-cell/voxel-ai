# VOXEL

AI Coding Assistant CLI for Termux. Lightweight, fast, and built for Android development environments.

## Features

- Interactive chat with streaming responses
- Multiple AI providers (OpenAI, Anthropic, Ollama, Gemini)
- File system tools (read, write, list, glob, grep)
- Terminal command execution
- Git integration (status, log, diff, commit)
- LSP diagnostics
- Session management
- Memory bank
- Auto-compact for long conversations
- Permission system
- Agent modes (code, plan, ask, debug, review)
- Works offline with local models (Ollama)
- Termux-specific path handling

## Installation (Termux)

```bash
# Clone or copy VOXEL to your device
pkg update -y
pkg install -y python python-pip git termux-api

pip install click rich requests textual tiktoken

# Run from source
python -m voxel.cli setup
python -m voxel.cli chat
```

## Usage

```bash
# Configure
voxel setup --provider openai --api-key YOUR_KEY --model gpt-4o-mini

# Interactive chat
voxel chat

# Single prompt
voxel run "Write a hello world in Python"

# Read a file
voxel read main.py

# Run a command
voxel run_cmd "ls -la"

# List sessions
voxel sessions

# Initialize memory bank
voxel memory "My project description"
```

## Supported Providers

- **OpenAI** - GPT-4o, GPT-4o-mini, etc.
- **Anthropic** - Claude 3.5 Sonnet, etc.
- **Ollama** - Local models (Llama 3, etc.)
- **Gemini** - Google Gemini models

## Agent Modes

- **code** - Implements and edits code
- **plan** - Designs architecture and plans
- **ask** - Answers questions about codebase
- **debug** - Troubleshoots and traces issues
- **review** - Reviews code changes

## Tools

- `read_file` - Read file contents
- `write_file` - Write content to file
- `list_directory` - List directory contents
- `glob` - Find files by pattern
- `grep` - Search file contents
- `bash` - Execute shell commands
- `git_status`, `git_log`, `git_diff`, `git_commit` - Git operations
- `diagnostics` - LSP diagnostics

## Commands

- `/help` - Show help
- `/clear` - Clear conversation
- `/undo` - Undo last change
- `/compact` - Compact session context
- `/model <name>` - Switch model
- `/mode <name>` - Switch agent mode
- `/mcp` - Manage MCP servers
- `/memory` - View memory bank
- `/permissions` - View permissions
- `/session` - Switch sessions
- `/agents` - List agent modes
- `/exit` - Exit

## License

MIT
