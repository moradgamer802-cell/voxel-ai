# VOXEL

AI Coding Assistant CLI for Termux. Lightweight, fast, and built for Android development environments.

## One-Click Install (Termux)

```bash
curl -fsSL https://raw.githubusercontent.com/moradgamer802-cell/voxel-v2/master/install.sh | bash
```

Then restart Termux or run `source ~/.bashrc`, and start with:

```bash
voxel chat
```

**Default config (pre-installed):**
- Model: `deepseek-v4-flash-free`
- Provider: `https://opencode.ai/zen/v1`
- API key: built-in (no setup needed)

## Installation (Manual)

```bash
pkg update -y
pkg install -y python python-pip git termux-api

pip install click rich requests textual tiktoken

# Run from source
python -m voxel.cli setup
python -m voxel.cli chat
```

## Usage

```bash
# Start interactive chat (default: DeepSeek V4 Flash Free, no API key needed)
voxel chat

# Configure custom provider
voxel setup --provider openai --api-key YOUR_KEY --model gpt-4o-mini

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
