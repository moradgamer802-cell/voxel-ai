<div align="center">

```
██╗   ██╗ ██████╗ ██╗  ██╗███████╗██╗
██║   ██║██╔═══██╗╚██╗██╔╝██╔════╝██║
╚██╗ ██╔╝██║   ██║ ╚███╔╝ █████╗  ██║
 ╚████╔╝ ██║   ██║ ██╔██╗ ██╔══╝  ██║
  ╚██╔╝  ╚██████╔╝██╔╝ ██╗███████╗███████╗
   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝
```

**opencode-style AI agent CLI for Termux · no key, no install, no registration**

[![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Termux%20%7C%20Android-green?logo=android&logoColor=white)](https://termux.dev)
[![License](https://img.shields.io/badge/License-MIT-purple)](LICENSE)
[![Deps](https://img.shields.io/badge/Dependencies-stdlib%20only-lightgrey)](voxel.py)

</div>

---

## ◆ কী এটা / What is this

VOXEL AI হলো Termux-এর জন্য একটা **AI agent CLI**, যার UI, command set, session model
আর keybind — সব [opencode](https://opencode.ai) এর TUI ফলো করে। Python stdlib ছাড়া
কিছু লাগে না, কোনো API key বা account লাগে না।

> An AI agent CLI for Android/Termux whose layout, commands, sessions and keybinds
> follow opencode's TUI. Pure stdlib, single file, no account needed.

**Reading hierarchy** — AI-এর reply পুরো brightness-এ normal text হিসেবে আসে।
Command execution আর tool call আসে **dim + lowercase** ছোট লাইনে, যাতে চোখ সবসময়
উত্তরের উপর পড়ে, tool noise-এ না।

```
  ❯ storage e ki ache dekho ar ekta note likho

  → ls /storage/emulated/0/download ✓          ← dim, lowercase
    notes.txt
    song.mp3
  → write /storage/emulated/0/notes.txt ✓
       1 + hello from voxel

  ◆  ds-v4  thought 1.4s
  ▏ Storage check                              ← bright, markdown rendered
  ▏
  ▏ Download folder e 3 ta file peyechi.
  ▏
  ▏ ● notes.txt banano hoyeche
  ▏ ● ls run korechi

  ╭──────────────────────────────────────────────╮
  │ ❯ Type a message, /help for commands         │
  ╰──────────────────────────────────────────────╯
  ~/proj  │  main  │  ◆ build  │  ds-v4    ~1.2K tok  2%
```

---

## ⚡ Install (Termux)

```bash
curl -fsSL https://raw.githubusercontent.com/moradgamer802-cell/voxel-ai/main/install.sh | bash
source ~/.bashrc
voxel
```

---

## ✦ Commands

opencode-এর command set, aliases সহ।

| Command | Aliases | কাজ |
|---|---|---|
| `/help` | | help dialog |
| `/new` | `/clear` | new session |
| `/sessions` | `/resume`, `/continue` | session list + switch |
| `/models` | | model picker |
| `/model <id>` | | model set |
| `/themes` | | theme picker |
| `/compact` | `/summarize` | session compact |
| `/details` | | tool output show/hide |
| `/thinking` | | reasoning block toggle |
| `/undo` `/redo` | | last message revert / restore |
| `/export` | | markdown export |
| `/editor` | | `$EDITOR` তে message লেখা |
| `/init` | | AGENTS.md তৈরি |
| `/stats` | | token count |
| `/key <sk-...>` | | API key set |
| `/perm` | | permission rules |
| `/root` | | root mode (`su -c`) |
| `/exit` | `/quit`, `/q` | quit |

**Input prefixes**

| Prefix | কাজ |
|---|---|
| `@path` | file content conversation-এ যোগ করে |
| `!cmd` | shell command চালায়, output tool result হিসেবে আসে |
| `\` (line শেষে) | multi-line input |

---

## ⌨ Keybinds

`ctrl+x` হলো leader key (opencode default), timeout 2s। Leader চাপলে which-key
overlay দেখাবে।

| Key | কাজ |
|---|---|
| `ctrl+x q` | quit |
| `ctrl+x n` | new session |
| `ctrl+x l` | session list |
| `ctrl+x m` | model list |
| `ctrl+x t` | theme list |
| `ctrl+x e` | editor |
| `ctrl+x c` | compact |
| `ctrl+x x` | export |
| `ctrl+x u` / `ctrl+x r` | undo / redo |
| `ctrl+x y` | copy last reply |
| `ctrl+x d` | tool details toggle |
| `ctrl+p` | command palette |
| `ctrl+t` | cycle model |
| `ctrl+r` | rename session |
| `ctrl+d` | delete session |
| `Tab` / `shift+Tab` | agent cycle (plan ⇄ build) |
| `Esc` | interrupt stream / close dialog |
| `pgup` / `pgdn` | scroll messages |
| `ctrl+a` / `ctrl+e` | line start / end |
| `ctrl+u` / `ctrl+k` | delete to start / end |
| `ctrl+w` | delete word back |
| `↑` / `↓` | input history |

---

## ◇ Modes

`Tab` দিয়ে toggle:

- **build** (blue) — AI file লিখতে ও command চালাতে পারে
- **plan** (green) — শুধু analyze; `run`/`write` block করা থাকে, `read`/`ls`/`search` চলে

---

## 🤖 Tools

AI নিজে থেকেই এগুলো use করে:

| Tool | কাজ | Permission |
|---|---|---|
| `<run>cmd</run>` | shell command | prompt |
| `<write path="…">` | file লেখা | prompt |
| `<read path="…">` | file পড়া | auto |
| `<ls>dir</ls>` | folder list | auto |
| `<search>q</search>` | DuckDuckGo search | auto |

Permission prompt-এ চারটা option: **once · session · always · reject**।
Rule set করতে: `/perm cmd add 'rm' deny`

**Storage** — `~`, `/sdcard`, `storage` — সব auto-correct হয়ে
`/storage/emulated/0/` হয়ে যায়, তাই Termux home আর shared storage মেশে না।

---

## 🎨 Themes

`opencode` (default) · `tokyonight` · `gruvbox` · `catppuccin` · `nord` · `mono`

```bash
voxel --theme gruvbox
```

---

## 🆓 Models (OpenCode Zen)

Built-in key সহ আসে। Rate limit হলে automatically পরের free model-এ fallback হয়।

`deepseek-v4-flash-free` (default) · `big-pickle` · `mimo-v2.5-free` ·
`laguna-s-2.1-free` · `ling-3.0-flash-free` · `north-mini-code-free` ·
`nemotron-3-ultra-free`

নিজের key: `voxel --key sk-...`

---

## 🔧 Flags

```bash
python3 voxel.py                 # TUI
python3 voxel.py --plain         # no-TUI fallback (pipes, dumb terminals)
python3 voxel.py --safe-fonts    # ASCII glyphs, broken unicode font হলে
python3 voxel.py --models        # live model list
python3 voxel.py --theme nord
python3 voxel.py --key sk-...
```

Session ফাইল থাকে `~/.voxel/sessions/`, config `~/.voxel/config.json`।
পুরনো `~/.bangbot/chats` প্রথম run-এ auto migrate হয়ে যায়।

---

## ⚠ Notes

- Free model-এ rate limit আছে — limit হলে fallback হয়, নাহলে কিছুক্ষণ wait
- Repo-তে embedded API key আছে; নিজের key use করলে `/key` দাও
- `run`/`write` সবসময় permission চায় (always দিলে আর চাইবে না)

---

## 📄 License

[MIT](LICENSE)
