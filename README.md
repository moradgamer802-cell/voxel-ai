<div align="center">

```
██╗   ██╗ ██████╗ ██╗  ██╗███████╗██╗      █████╗ ██╗
██║   ██║██╔═══██╗╚██╗██╔╝██╔════╝██║     ██╔══██╗██║
╚██╗ ██╔╝██║   ██║ ╚███╔╝ █████╗  ██║     ███████║██║
 ╚████╔╝ ██║   ██║ ██╔██╗ ██╔══╝  ██║     ██╔══██║██║
  ╚██╔╝  ╚██████╔╝██╔╝ ██╗███████╗███████╗██║  ██║██║
   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝╚═╝  ╚═╝╚═╝
```

**Free AI agent CLI for Termux · No key, no install, no registration**

[![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Termux%20%7C%20Android-green?logo=android&logoColor=white)](https://termux.dev)
[![License](https://img.shields.io/badge/License-MIT-purple)](LICENSE)
[![Models](https://img.shields.io/badge/Models-OpenCode%20Zen%20Free-orange)](https://opencode.ai)
[![No Dependencies](https://img.shields.io/badge/Dependencies-None%20(stdlib%20only)-lightgrey)](bangbot.py)

</div>

---

## ◆ কী এটা? / What is this?

VOXEL AI হলো Termux (Android terminal) এর জন্য একটা **free, full-featured AI agent CLI** — Claude Code / OpenCode এর মতো clean TUI interface, সাথে AI tool execution (command চালানো, file read/write, web search)। কোনো API key লাগবে না, কোনো pip install দরকার নেই, কোনো account খুলতে হবে না।

> A free, full-screen AI agent terminal app for Android (Termux). Looks like Claude Code/OpenCode, works offline-first, runs on any Python 3 terminal — no API key, no pip installs, no account needed.

---

## ⚡ One-line Install (Termux)

```bash
curl -fsSL https://raw.githubusercontent.com/moradgamer802-cell/voxel-ai/main/install.sh | bash
```

তারপর / Then:

```bash
source ~/.bashrc
voxel
```

---

## ✦ Features

### 🖥️ Full-screen TUI
- **Clean Claude Code / OpenCode aesthetic** — `◆` indicator, `▎` left-border response cards, `─────` separator bars
- **Animated streaming** — braille spinner + typewriter reveal, live tok/s counter
- **Plan / Build mode** — Tab দিয়ে toggle: Plan (AI শুধু analyze করে), Build (AI file/command change করতে পারে)
- **Adaptive layout** — portrait/landscape, compact/wide, tiny terminal সব handle করে

### 🤖 AI Agent Tools
AI নিজেই এগুলো use করে — আলাদাভাবে কিছু করতে হয় না:

| Tool | কী করে |
|------|---------|
| `<run>command</run>` | Termux এ shell command চালায় |
| `<run root>cmd</run>` | Root command (rooted phone এ) |
| `<read path="/...">` | File পড়ে |
| `<write path="/...">content</write>` | File লেখে |
| `<ls>dir</ls>` | Folder list করে |
| `<search>query</search>` | DuckDuckGo web search |

### 🔒 Permission System
- `<search>` / `<read>` / `<ls>` → default allow
- `<run>` / `<write>` → arrow-key popup: **Allow once · Allow session · Always · Reject**
- `Ctrl+E` → auto-approve toggle (সব permission auto-allow)
- Rules: `/perm cmd add 'rm' deny` — specific command block করো

### 💾 Session Manager
- Auto-save, manual `/save [name]`, `/load`, `/sessions`, `/rm`
- Session list on home screen with timestamps + message preview
- `Ctrl+D` = delete session, `Ctrl+R` = rename

### 🎛️ More
- **Model picker** — `/models` দিয়ে interactive popup, free model list
- **Diff view** — AI file লিখলে `← Edit path` diff card দেখাবে (colored +/-)
- **Collapsible sections** — `**Summary:**` blocks collapse by default, Enter দিয়ে expand
- **Root support** — `su -c` দিয়ে system-level commands
- **Auto model fallback** — rate limit হলে automatically অন্য free model এ switch
- **Touch scrollback** — swipe করে পুরনো messages দেখো

---

## 🆓 Free Models (OpenCode Zen)

Built-in key সহ আসে — কোনো registration ছাড়াই কাজ করে:

| Model | বিশেষত্ব |
|-------|---------|
| `deepseek-v4-flash-free` | Default, fast reasoning |
| `big-pickle` | Strong coding |
| `mimo-v2.5-free` | Lightweight |
| `laguna-s-2.1-free` | Balanced |
| `nemotron-3-ultra-free` | Large context |
| `north-mini-code-free` | Code specialist |

নিজের key set করতে (optional):
```bash
voxel --key sk-your-key-from-opencode.ai
```

---

## 📋 Commands

| Command | কাজ |
|---------|-----|
| `/help` | সব commands দেখো |
| `/new` | নতুন chat |
| `/model <id>` | Model change |
| `/models` | Free model picker popup |
| `/save [name]` | Chat save করো |
| `/load <name>` | Saved chat load করো |
| `/sessions` | Sessions popup |
| `/rm <name>` | Session delete |
| `/perm` | Permission rules দেখো/set করো |
| `/root` | Root mode toggle |
| `/stats` | Token count |
| `/undo` | Last message revert |
| `/exit` | বের হও |

**Shortcuts:**
- `Tab` — Plan/Build mode toggle
- `Ctrl+P` — Command palette
- `Ctrl+E` — Auto-approve toggle
- `Ctrl+Z` — Undo last message
- `Ctrl+D` — Delete current session
- `Ctrl+R` — Rename current session
- `Esc` — Interrupt streaming / Go home
- `↑↓` — Input history / Session navigation

**Multi-line input:** Line এর শেষে `\` দিলে পরের লাইনে continue হবে।

---

## 📋 Requirements

- **[Termux](https://f-droid.org/packages/com.termux/)** — F-Droid থেকে install করো (Play Store version পুরনো)
- **Python 3** — installer auto install করে দেয়
- **Root** (optional) — `<run root>` tool ব্যবহার করতে চাইলে

---

## 🔧 Manual / Non-Termux Run

যেকোনো Python 3 terminal এ:

```bash
python3 bangbot.py
```

Safe fonts mode (broken unicode terminal এ):
```bash
python3 bangbot.py --safe-fonts
```

---

## ⚠️ Disclaimer

- Free models এ rate limit আছে — limit হলে কিছুক্ষণ wait করো বা অন্য model try করো
- Repo তে embedded API key আছে — চাইলে repo private রাখো অথবা নিজের key use করো
- AI যে command চালাবে সেটার জন্য তোমার permission নেবে (Always দিলে আর জিজ্ঞেস করবে না)

---

## 📄 License

[MIT](LICENSE) — free to use, modify, and distribute.
