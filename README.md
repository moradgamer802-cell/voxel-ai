<div align="center">

```
██╗   ██╗ ██████╗ ██╗  ██╗███████╗██╗
██║   ██║██╔═══██╗╚██╗██╔╝██╔════╝██║
╚██╗ ██╔╝██║   ██║ ╚███╔╝ █████╗  ██║
 ╚████╔╝ ██║   ██║ ██╔██╗ ██╔══╝  ██║
  ╚██╔╝  ╚██████╔╝██╔╝ ██╗███████╗███████╗
   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝
```

**Free AI Agent CLI for Termux — কোনো key লাগবে না, কোনো account লাগবে না**

[![Version](https://img.shields.io/badge/version-4.0.1-blue)](voxel.py)
[![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Termux%20%7C%20Android-green?logo=android&logoColor=white)](https://termux.dev)
[![License](https://img.shields.io/badge/License-MIT-purple)](LICENSE)
[![Deps](https://img.shields.io/badge/Dependencies-stdlib%20only-lightgrey)](voxel.py)

</div>

---

## ◆ কী এটা?

**VOXEL AI** হলো Android/Termux-এর জন্য একটা AI agent CLI।  
[opencode](https://opencode.ai)-এর মতো UI, command set আর keybind — কিন্তু **সম্পূর্ণ বিনামূল্যে**, কোনো signup ছাড়া।

- ✅ Python stdlib ছাড়া কিছু লাগে না
- ✅ Built-in free API key — নিজের key লাগবে না
- ✅ File read/write, shell command, internet search — সব পারে
- ✅ Bangla + English দুই ভাষায় কথা বলে
- ✅ একটাই `.py` file — সহজ install, সহজ update

---

## ⚡ Installation (Termux)

**Step 1 — Termux খুলুন এবং নিচের command টা paste করুন:**

```bash
curl -fsSL https://raw.githubusercontent.com/moradgamer802-cell/voxel-ai/main/install.sh | bash
```

**Step 2 — Terminal restart করুন অথবা এটা run করুন:**

```bash
source ~/.bashrc
```

**Step 3 — VOXEL AI চালু করুন:**

```bash
voxel
```

> **curl নেই?** আগে এটা run করুন: `pkg install curl`

---

## 🔄 Update

নতুন version পেতে আবার same command চালান:

```bash
curl -fsSL https://raw.githubusercontent.com/moradgamer802-cell/voxel-ai/main/install.sh | bash
source ~/.bashrc
```

---

## 📸 কেমন দেখতে?

```
╭──────────────────────────────────────────────╮
│ ❯ storage e ki ache dekho                   │
╰──────────────────────────────────────────────╯

  → ls /storage/emulated/0/ ✓
    Download/   DCIM/   Music/   Documents/

  ◆  ds-v4  thought 1.2s
  ▏ তোমার storage এ এই folder গুলো আছে:
  ▏
  ▏ ● Download
  ▏ ● DCIM (photos)
  ▏ ● Music
  ▏ ● Documents

~/  │  main  │  ◆ build  │  ds-v4    ~0.8K tok  1%
```

---

## 🆓 Free Models

Built-in key সহ আসে — rate limit হলে automatically পরের model-এ চলে যায়।

| Model | বৈশিষ্ট্য |
|---|---|
| `deepseek-v4-flash-free` | **Default** — দ্রুত, smart |
| `big-pickle` | General purpose |
| `mimo-v2.5-free` | Code-friendly |
| `laguna-s-2.1-free` | Balanced |
| `ling-3.0-flash-free` | Fast replies |
| `north-mini-code-free` | Code-focused |
| `nemotron-3-ultra-free` | Powerful reasoning |

নিজের key থাকলে: `voxel --key sk-...`

---

## ✦ Commands

| Command | কাজ |
|---|---|
| `/help` | সব command দেখো |
| `/new` বা `/clear` | নতুন conversation শুরু |
| `/sessions` | আগের conversation গুলো দেখো |
| `/models` | model বদলাও |
| `/themes` | theme বদলাও |
| `/compact` | conversation ছোট করো (token বাঁচাও) |
| `/details` | tool output দেখাও/লুকাও |
| `/thinking` | AI reasoning দেখাও/লুকাও |
| `/undo` / `/redo` | last message ফেরত নাও |
| `/export` | markdown file-এ save করো |
| `/stats` | কত token খরচ হলো |
| `/key sk-...` | নিজের API key set করো |
| `/root` | root mode চালু/বন্ধ |
| `/exit` | বেরিয়ে যাও |

**Special input:**

| লিখলে | কী হয় |
|---|---|
| `@/path/to/file` | সেই file টা conversation-এ যোগ হয় |
| `!command` | shell command চালায়, output দেখায় |
| `\` (line-এর শেষে) | পরের line-এ continue করো |

---

## ⌨ Keyboard Shortcuts

`Ctrl+X` চাপলে shortcut menu দেখাবে।

| Shortcut | কাজ |
|---|---|
| `Ctrl+X` তারপর `Q` | বেরিয়ে যাও |
| `Ctrl+X` তারপর `N` | নতুন session |
| `Ctrl+X` তারপর `L` | session list |
| `Ctrl+X` তারপর `M` | model list |
| `Ctrl+X` তারপর `T` | theme list |
| `Ctrl+X` তারপর `Y` | last reply copy করো |
| `Ctrl+P` | command palette |
| `Ctrl+T` | পরের model-এ যাও |
| `Tab` | Plan ⇄ Build mode switch |
| `Esc` | AI বন্ধ করো / dialog বন্ধ করো |
| `PgUp` / `PgDn` | scroll করো |
| `↑` / `↓` | আগের message গুলো দেখো |

---

## ◇ দুটো Mode

`Tab` চেপে switch করো:

- 🔵 **build mode** — AI file লিখতে ও command চালাতে পারে *(default)*
- 🟢 **plan mode** — শুধু analyze করে, কিছু execute করে না

---

## 🤖 AI কী কী করতে পারে

AI নিজে থেকেই এই tools use করে:

| Tool | কাজ | Permission |
|---|---|---|
| `<run>` | যেকোনো shell command চালায় | তোমার permission লাগবে |
| `<write>` | file তৈরি বা edit করে | তোমার permission লাগবে |
| `<read>` | file পড়ে | automatic |
| `<ls>` | folder-এর list দেখে | automatic |
| `<search>` | internet-এ search করে | automatic |

Permission চাইলে ৪টা option থাকে: **once · session · always · reject**

> **Storage shortcut:** `storage`, `sdcard`, `~/storage` — সব লিখলে automatically `/storage/emulated/0/` হয়ে যায়।

---

## 🎨 Themes

```bash
voxel --theme tokyonight   # Tokyo Night
voxel --theme gruvbox      # Gruvbox
voxel --theme catppuccin   # Catppuccin
voxel --theme nord         # Nord
voxel --theme mono         # Monochrome
voxel --theme opencode     # Default
```

অথবা চলতে চলতে `/themes` command দাও।

---

## 🔧 Startup Flags

```bash
voxel                    # normal TUI mode
voxel --plain            # simple text mode (pipe বা dumb terminal-এ)
voxel --safe-fonts       # unicode সমস্যা হলে ASCII use করবে
voxel --models           # available model list দেখো
voxel --theme nord       # নির্দিষ্ট theme দিয়ে চালু করো
voxel --key sk-...       # API key save করো
```

---

## 📁 Files

| Path | কী আছে |
|---|---|
| `~/.voxel/config.json` | settings |
| `~/.voxel/sessions/` | conversation history |
| `~/.voxel/export-*.md` | exported conversations |

---

## ⚠️ কিছু জানার কথা

- Free model-এ rate limit আছে — limit হলে automatically পরের model-এ চলে যায়
- `run` ও `write` tool-এ সবসময় permission চাইবে — `always` দিলে আর চাইবে না
- Termux-এ storage access না থাকলে: `termux-setup-storage` run করো

---

## ❓ সমস্যা হলে

**`voxel` command পাওয়া যাচ্ছে না:**
```bash
source ~/.bashrc
```

**Screen ঠিকমতো দেখাচ্ছে না:**
```bash
voxel --safe-fonts
```

**নতুন করে install করতে:**
```bash
curl -fsSL https://raw.githubusercontent.com/moradgamer802-cell/voxel-ai/main/install.sh | bash
source ~/.bashrc
```

---

## 📄 License

[MIT](LICENSE) — free to use, modify and share.
