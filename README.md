# VOXEL AI

Free AI agent CLI for Termux — amader moto AI assistant, terminal e thake. Powered by OpenCode Zen free models. Ready-to-use built-in key, install korar sathe sathe chole.

## One-line Install

```bash
curl -fsSL https://raw.githubusercontent.com/moradgamer802-cell/voxel-ai/main/install.sh | bash
```

Then:

```bash
source ~/.bashrc
voxel
```

Done! Kono API key, kono pip install, kono registration lagbe na.

## Update

Ager one-liner abar chalao — latest version update hobe:

```bash
curl -fsSL https://raw.githubusercontent.com/moradgamer802-cell/voxel-ai/main/install.sh | bash
```

## Features

- **Full-screen TUI (faithful opencode UI)** — `voxel` lekhlei terminal clear hoye nijosso interface khule: Home screen (recent sessions + New Chat), opencode-style panel header (`# title` + `● model · tok ~X · $0 · root` right side), message cards with left accent borders + panel background (green = You, purple = assistant/tool), muted model meta line, `❯` prompt, live streaming with animated `Thinking…` spinner + typewriter text reveal + progress bar, arrow-key permission popup, Esc = Home
- **Contextual footer** — prothomite relevant key hint sudhu: streaming er somoy `[Esc] Interrupt`, `[Ctrl+P] Commands` palette, home e `↑/↓ Navigate`
- **Command palette (`Ctrl+P`)** — commands er list popup: `↑/↓` select, `Enter` run, `Esc` close
- **`Esc` = Interrupt** — AI reply asar somoy Esc chapele reply stop hoy (chat exit hoy na); arobar Esc = Home
- **Touch scrollback** — chat e upor/dhon swipe korle purono messages dekha jay (mouse tracking on), niche swipe = notun messages; type korlei bottom e fere ase
- **Compact tool logs** — tool er full output chat e dekha jay na: `✓ run: <cmd>` / `✗ run: <cmd> — <error>` short line
- **Low-device friendly** — pure Python stdlib, no dependencies, kono pip install nai
- **Free AI models** — DeepSeek V4 Flash Free, Big Pickle, MiMo, Nemotron, etc. (OpenCode Zen)
- **AI agent tools** — AI nijei command chalao, file read/write, folder list, web search:
  - `<run>command</run>` — Termux e command
  - `<run root>command</run>` — root (su) command
  - `<read path="/path">x</read>` / `<write path="/path">content</write>`
  - `<ls>dir</ls>` / `<search>query</search>`
- **Permission system** — arrow-key prompt: `← →` Yes / No / Always, `Enter` confirm
  - Web search: default ON (permission chara) | read/ls: default allow
  - Rules: `/perm cmd add 'rm' deny`, `/perm rootcmd add 'mount' always`, `/perm cmd always` (default)
- **Root support** — rooted phone e `su -c` diye system-level kaj; non-rooted phone e automatic normal mode
- **Auto model fallback** — rate limit/error hole onno free model e automatic switch
- **Session manager** — `/save`, `/load`, `/sessions`, `/rm` + auto-save
- **Web search** — DuckDuckGo (real URLs)
- **Token counter** — `/stats`

## Commands

| Command | Kaj |
|---|---|
| `/help` | All commands |
| `/model <id>` | Model change |
| `/models` | Free model list |
| `/new` | New chat |
| `/save [name]` / `/load <name>` / `/sessions` / `/rm <name>` | Session manage |
| `/perm` | Permission rules |
| `/root` | Root mode toggle |
| `/stats` | Token count |
| `/exit` | Exit |

Multi-line: line er seshe `\` dile continue hobe. Up/down arrow: history. `Tab`: command autocomplete.

## Requirements

- Termux (free, [F-Droid](https://f-droid.org/packages/com.termux/))
- Python (`pkg install -y python` — installer auto kore dey)
- Root: sudhu rooted phone e `<run root>` kaj korbe

## Own API Key (optional)

Built-in free key ready-to-use. Nijer key set korte:

```bash
voxel --key sk-your-own-key-from-opencode.ai/auth
```

## Disclaimer

- Free models have rate limits — thakle kichu minute wait kore abar try koro.
- Repo e embedded API key ase — repo private rakhte paro, ba nijer key use koro.
- AI chalano command er dorkar e aapnar permission nibe, kintu `always` rule dile aar jiggesh korbe na.
