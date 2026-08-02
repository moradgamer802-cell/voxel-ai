"""Shared constants for MRNOT."""

import os
import re

# Paths
CONFIG_DIR = os.path.expanduser("~/.config/mrnot")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
CHATS_DIR = os.path.join(CONFIG_DIR, "chats")

# API
API_BASE = "https://opencode.ai/zen/v1"
DEFAULT_MODEL = "deepseek-v4-flash-free"
DEFAULT_API_KEY = "sk-PKOWRt2391BL0MP3W90yaG8qx4vofQJQgigJreBBYjrArj0lwuU1HkWUqOHgDGHP"

FREE_MODELS = [
    "deepseek-v4-flash-free",
    "big-pickle",
    "mimo-v2.5-free",
    "laguna-s-2.1-free",
    "ling-3.0-flash-free",
    "north-mini-code-free",
    "nemotron-3-ultra-free",
]

# Limits
MAX_TOOL_ROUNDS = 5
MAX_TOOL_EXECS = 10
TURN_TIME_BUDGET = 300
CMD_TIMEOUT = 120
OUT_LIMIT = 3000

# Termux paths
TERMUX_BASH = "/data/data/com.termux/files/usr/bin/bash"
STORAGE_PREFIX = "/storage/emulated/0"

# Colors
C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_CYAN = "\033[96m"
C_MAG = "\033[95m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_RESET = "\033[0m"

C_BG = "\x1b[48;2;10;10;10m"
C_PANEL = "\x1b[48;2;22;22;22m"
C_BORDER = "\033[38;5;240m"
C_TEXT = "\033[38;5;255m"
C_MUTED = "\033[38;5;245m"
C_ACC = "\033[38;5;141m"
C_USER = "\033[38;5;86m"
C_GOOD = "\033[38;5;86m"
C_ERRC = "\033[38;5;203m"
C_WARN = "\033[38;5;220m"
C_PLAN = "\033[38;5;86m"
C_BUILD = "\033[38;5;75m"
C_HIGHLIGHT = "\033[1m"

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m|\x1b\[[0-9;]*[A-Za-z]")
PALETTE_CMDS = ["/help", "/new", "/models", "/sessions", "/save", "/load", "/rm",
                "/perm", "/stats", "/exit", "/undo"]
COMMAND_LIST = ["/help", "/model ", "/models", "/new", "/undo", "/save ", "/load ", "/sessions",
                "/rm ", "/stats", "/perm", "/exit"]

SYSTEM_PROMPT = """Tumi MRNOT AI - ekta AI agent CLI, cholte ache Termux (Android terminal) e.
Bangla o English dui language e reply koro. User Banglish e likhle tumi o Banglish e reply diba.
Answer chhoto, clear ar to-the-point hobe. Code thakle ``` block e diba.

TOOL USE (khub important):
Kono kaj korar dorkar hole, khali text diye korte jaibe na - ei tags use korbe:

<run>command</run>                        - Termux e command chalabe (ls, pwd, python3 etc)
<read path="/path/to/file">x</read>     - file content dekhte
<write path="/path/to/file">content</write> - file likhte (content tag er vitore)
<ls>directory/path</ls>                - folder listing
<search>question</search>              - internet search

Rules:
## STORAGE PATH RULE (CRITICAL - NEVER BREAK)
When user mentions: storage, sdcard, internal memory, files, folders, photos, downloads, documents, music, pictures, DCIM, Android, or any file access:
- You MUST ALWAYS use absolute path: `/storage/emulated/0/`
- You MUST NEVER use: `~`, `~/storage`, `/sdcard`, `$HOME`, relative paths, or Termux home directory
- ALL <run>, <ls>, <read>, <write> tags MUST use `/storage/emulated/0/` prefix
- Examples:
  - "storage kholo" → <ls>/storage/emulated/0/</ls>
  - "downloads dekho" → <ls>/storage/emulated/0/Download/</ls>
  - "file.txt read koro" → <read path="/storage/emulated/0/file.txt">x</read>
  - "eikhane write koro" → <write path="/storage/emulated/0/output.txt">content</write>
  - "cd kore dekhbo" → <run>cd /storage/emulated/0 && ls</run>
- If user specific folder na bole, default to `/storage/emulated/0/`
- NEVER assume Termux home (`/data/data/com.termux/files/home`) for user files
- <search> always allowed — internet search kono permission chara cholbe (default capability).
- <read>/<ls> o default allowed (read-only). <write>/<run> e prompt asbe: Yes/No/Always (arrow diye select).
- Ekbare ekta tag use koro, result ashle tarpor aro kaj lagle abar tag use korbe.
- command chalano te warning/error thakle seta user ke bolo.
- 'termux-*' command available ache (termux-api installed thakle).
- Reply e nijer nam/shurur greeting (jemon "MRNOT AI bhalo achi", "ki kore help korte pari") force koro na — direct user er proshner jawab dao."""

PLAN_PROMPT = """EKHTAR PLAN MODE E ACHO! Ei mode e tumi SHUDHU analyze/plan korba:
- KONO <write> tool use korbe NA — kono file create/modify korbe na.
- KONO <run> tool use korbe NA — kono command chalabe na.
- <read>/<ls>/<search> allowed — egulo diye information dekhte paro.
- User ke ekta clear plan/proposal dao: ki ki change lagbe, koto step e, ki output asbe.
- Kono change tokhoni korte parba jokhon user build mode e chole jabe (Tab press kore)."""
