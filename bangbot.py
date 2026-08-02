#!/usr/bin/env python3
"""
BangBot v2.0 - free AI agent CLI assistant for Termux
Powered by OpenCode Zen free models
Tools: run / read / write / ls / search | Permission system
Run:  python3 bangbot.py
"""

import html as html_mod
import codecs
import json
import os
import re
import select
import shlex
import shutil
import signal
import subprocess
import sys
import unicodedata
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    import readline
except ImportError:
    readline = None

try:
    import termios
    import tty
except ImportError:
    termios = tty = None

CONFIG_DIR = os.path.expanduser("~/.bangbot")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
CHATS_DIR = os.path.join(CONFIG_DIR, "chats")
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

MAX_TOOL_ROUNDS = 5          # ek turn e max AI-round (8->5: thinking time half)
MAX_TOOL_EXECS = 10          # ek turn e max tool execution (hard cap)
TURN_TIME_BUDGET = 300       # ek turn max 5 min (thinking+tools) — loop e jome jabe na
CMD_TIMEOUT = 120
OUT_LIMIT = 3000

SYSTEM_PROMPT = """Tumi VOXEL AI - ekta AI agent CLI, cholte ache Termux (Android terminal) e.
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
- Reply e nijer nam/shurur greeting (jemon "VOXEL AI bhalo achi", "ki kore help korte pari") force koro na — direct user er proshner jawab dao."""

PLAN_PROMPT = """EKHTAR PLAN MODE E ACHO! Ei mode e tumi SHUDHU analyze/plan korba:
- KONO <write> tool use korbe NA — kono file create/modify korbe na.
- KONO <run> tool use korbe NA — kono command chalabe na.
- <read>/<ls>/<search> allowed — egulo diye information dekhte paro.
- User ke ekta clear plan/proposal dao: ki ki change lagbe, koto step e, ki output asbe.
- Kono change tokhoni korte parba jokhon user build mode e chole jabe (Tab press kore)."""

C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_CYAN = "\033[96m"
C_MAG = "\033[95m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_RESET = "\033[0m"
CLEAR = "\x1b[2J\x1b[H"
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"  # 10-frame braille spinner (v4 spec)

# v4 semantic palette (spec: ANSI 256 + truecolor bg)
C_BG = "\x1b[48;2;10;10;10m"
C_PANEL = "\x1b[48;2;22;22;22m"
C_BORDER = "\033[38;5;240m"         # box borders
C_TEXT = "\033[38;5;255m"           # main reply body — sole BRIGHT white
C_MUTED = "\033[38;5;245m"          # DIM gray — headers/labels/meta
C_GRAY = "\033[38;5;245m"           # section content — DIM gray
C_ACC = "\033[38;5;141m"            # BRAND #a78bfa (AI accent, logo)
C_USER = "\033[38;5;86m"            # USER green #34d399
C_GOOD = "\033[38;5;86m"            # ● info green
C_ERRC = "\033[38;5;203m"           # ✗ error red #f87171
C_WARN = "\033[38;5;220m"           # ⚠ warning yellow #fbbf24
C_PLAN = "\033[38;5;86m"            # plan mode = USER green
C_BUILD = "\033[38;5;75m"           # build mode blue #60a5fa
C_HIGHLIGHT = "\033[1m"             # bold headers inside body
CSI_FINAL_CHARS = "@ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz~`"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m|\x1b\[[0-9;]*[A-Za-z]")


def plen(text):
    return len(ANSI_RE.sub("", text))


def dlen(text):
    width = 0
    for ch in ANSI_RE.sub("", text):
        if unicodedata.combining(ch):
            continue
        width += 2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1
    return width

UA = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"
TOOL_RE = re.compile(r"<(run|read|write|ls|search)((?:\s+\w+(?:=\"[^\"]*\")?)*)>(.*?)</\1>", re.S)
ATTR_RE = re.compile(r"(\w+)(?:=\"([^\"]*)\")?")
STRIP_TAGS_RE = re.compile(r"<[^>]+>")
MODEL_FAIL = {}  # model -> last failure time
SESSION_TOKENS = {"in": 0, "out": 0}
ui = None  # TUI instance (set in main)

# --safe-fonts: broken unicode fallback (portrait/ASCII terminals)
SAFE_FONTS = "--safe-fonts" in sys.argv
SAFE_GLYPHS = {
    "▸": ">", "▾": "v", "│": "|", "❯": ">", "●": "*", "⠋": "/",
    "▍": "|", "→": "->", "✓": "OK", "✗": "XX", "⚠": "!", "ℹ": "i",
    "◄": "<", "▶": ">", "○": "o", "▰": "=", "⬝": ".", "█": "#",
    "▏": "|", "▎": "|", "▌": "|", "▋": "|", "▊": "|", "▉": "|",
    "⣾": "/", "⣽": "/", "⣻": "/", "⢿": "/", "⡿": "/", "⣟": "/",
    "⣯": "/", "⣷": "/", "⚡": "!", "⛔": "!", "⏳": "!",
}
SAFE_RE = None


def safeify(line):
    """Broken unicode terminal e fancy glyph -> ASCII fallback."""
    global SAFE_RE
    if not SAFE_FONTS:
        return line
    if SAFE_RE is None:
        SAFE_RE = re.compile("|".join(map(re.escape, sorted(SAFE_GLYPHS, key=len, reverse=True))))
    return SAFE_RE.sub(lambda m: SAFE_GLYPHS[m.group(0)], line)


def ui_note(line):
    """Transient status line — TUI te frame er vitore, plain mode e print."""
    if ui is not None and not ui.plain:
        ui.notes.append(line)
        ui.redraw()
    else:
        print("  " + line, flush=True)


# ---------------- config ----------------

def load_config():
    try:
        with open(CONFIG_FILE) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.chmod(CONFIG_FILE, 0o600)


def get_api_key(cfg):
    return os.environ.get("OPENCODE_API_KEY") or cfg.get("api_key", "").strip() or DEFAULT_API_KEY


# ---------------- http ----------------

def _req(url, body=None):
    req = urllib.request.Request(url, data=body, method="POST" if body else "GET")
    req.add_header("User-Agent", UA)
    return req


def fetch_models(api_key=None):
    req = _req(API_BASE + "/models")
    if api_key:
        req.add_header("Authorization", "Bearer " + api_key)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode())
    return [m["id"] for m in data.get("data", [])]


def stream_chat(messages, model, api_key):
    body = json.dumps({"model": model, "messages": messages, "stream": True}).encode()
    req = _req(API_BASE + "/chat/completions", body)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", "Bearer " + api_key)
    resp = urllib.request.urlopen(req, timeout=180)
    buffer = b""
    while True:
        chunk = resp.read(1024)
        if not chunk:
            break
        buffer += chunk
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            line = line.strip()
            if not line or not line.startswith(b"data:"):
                continue
            data = line[5:].strip()
            if data == b"[DONE]":
                return
            try:
                obj = json.loads(data)
            except json.JSONDecodeError:
                continue
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta", {})
            content = delta.get("content")
            reasoning = delta.get("reasoning_content")
            if reasoning:
                yield "reasoning", reasoning
            if content:
                yield "content", content


def call_chat(messages, model, api_key, on_chunk=None):
    """Returns (err, used_model). Streams via on_chunk(kind, text) callback."""
    order = [model] + [m for m in FREE_MODELS if m != model]
    now = time.time()
    tried = []
    key_error = None
    for m in order:
        if m in tried:
            continue
        if now - MODEL_FAIL.get(m, 0) < 60:
            tried.append(m)
            continue
        tried.append(m)
        try:
            for kind, text in stream_chat(messages, m, api_key):
                if on_chunk:
                    on_chunk(kind, text)
            MODEL_FAIL.pop(m, None)
            return None, m
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:200]
            if e.code == 401:
                key_error = "API key thik na! `python3 bangbot.py --key <key>` diye nijer key set koro."
                MODEL_FAIL[m] = now
                continue
            if e.code in (429, 403, 404, 400):
                MODEL_FAIL[m] = now
                continue
            time.sleep(1)
        except urllib.error.URLError as e:
            return f"Network error: {e.reason}", m
        except Exception as e:
            return f"Error: {e}", m
    if key_error and len(tried) == 1:
        return key_error, model
    return "Shob model e rate limit/error. Kichu minute pore abar try koro.", model


# ---------------- tools ----------------

def est_tokens(text):
    return max(1, len(text) // 4)


def ddg_search(query, max_results=5):
    results = []
    for base in ("https://html.duckduckgo.com/html/", "https://lite.duckduckgo.com/lite/"):
        try:
            url = base + "?" + urllib.parse.urlencode({"q": query})
            req = _req(url)
            with urllib.request.urlopen(req, timeout=20) as resp:
                page = resp.read().decode(errors="replace")
            if "html.duckduckgo.com" in base:
                pairs = re.findall(r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page)
                snips = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', page)
            else:
                pairs = re.findall(r'href="([^"]+)"[^>]*class="result-link">(.*?)</a>', page)
                snips = re.findall(r'class="result-snippet">(.*?)</td>', page)
            for i, (u, t) in enumerate(pairs[:max_results]):
                title = html_mod.unescape(STRIP_TAGS_RE.sub("", t)).strip()
                real_url = u
                if "uddg=" in u:
                    real_url = urllib.parse.unquote(u.split("uddg=", 1)[1].split("&", 1)[0])
                sn = html_mod.unescape(STRIP_TAGS_RE.sub("", snips[i])).strip() if i < len(snips) else ""
                results.append({"title": title, "url": real_url, "snippet": sn[:250]})
            if results:
                break
        except Exception:
            continue
    return results


def run_command(cmd, root=False):
    actual = cmd
    try:
        proc = subprocess.run(
            actual, shell=True, capture_output=True, text=True,
            timeout=CMD_TIMEOUT, executable="/data/data/com.termux/files/usr/bin/bash"
            if os.path.exists("/data/data/com.termux/files/usr/bin/bash") else None,
        )
        out = (proc.stdout + proc.stderr).strip()
        return proc.returncode, out, cmd
    except subprocess.TimeoutExpired:
        return -1, f"Command timeout ({CMD_TIMEOUT}s)", cmd
    except Exception as e:
        return -1, f"Execute error: {e}", cmd


def truncate(text, limit=OUT_LIMIT):
    text = text.strip()
    if len(text) > limit:
        return text[:limit] + f"\n...[truncated {len(text) - limit} chars]"
    return text


def short(text, limit):
    """Clean single-line truncation with ellipsis."""
    flat = " ".join(text.split())
    if len(flat) > limit:
        return flat[:limit - 1] + "…"
    return flat


# ---------------- permissions ----------------

def perm_rule(cfg, category, key):
    rules = cfg.get("perm", {}).get(category, {})
    if key in rules:
        return rules[key]
    if category == "cmd":
        first = key.split()[0] if key.split() else key
        if first in rules:
            return rules[first]
    for prefix, mode in rules.items():
        if key.startswith(prefix):
            return mode
    return cfg.get("perm", {}).get("default_" + category, "ask")


def ask_permission(kind, key):
    if ui is not None and not ui.plain:
        return ui.perm_popup(kind, key)
    print()
    print("  " + C_WARN + "⚠ Permission required" + C_RESET)
    print("  " + C_DIM + " - Access " + C_BOLD + C_TEXT + key + C_RESET)
    while True:
        try:
            ans = input("  > 1=Allow once  2=Allow session  3=Always  4=Reject (Enter=1): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return "deny_once"
        if ans in ("1", "y", "yes", ""):
            return "allow_once"
        if ans in ("2", "s", "session"):
            return "allow_session"
        if ans in ("3", "a", "always"):
            return "always"
        if ans in ("4", "n", "no"):
            return "deny_once"


def check_perm(cfg, category, key, session_perm, prompt=True, auto_approve=False):
    """Returns True if allowed. prompt=False -> read-only ops auto-allow (deny rule thakle block)."""
    mode = perm_rule(cfg, category, key)
    if mode == "deny":
        return False
    if mode == "always" or key in session_perm.get(category, set()):
        return True
    if auto_approve:
        return True
    if not prompt:
        return True
    label = {"cmd": "run command", "file": "file op"}.get(category, category)
    decision = ask_permission(label, key)
    if decision == "always":
        cfg.setdefault("perm", {}).setdefault(category, {})[key] = "always"
        save_config(cfg)
        return True
    if decision == "deny_always":
        cfg.setdefault("perm", {}).setdefault(category, {})[key] = "deny"
        save_config(cfg)
        return False
    if decision == "allow_session":
        session_perm.setdefault(category, set()).add(key)
        return True
    return decision == "allow_once"


def make_diff_lines(old, new, ctx=2):
    """Unified diff with per-line numbers -> [(kind, old_n, new_n, text)] (kind in -,+,' ')"""
    import difflib
    diff = difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=ctx)
    lines, old_n, new_n = [], 0, 0
    for line in diff:
        if line.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)", line)
            if m:
                old_n, new_n = int(m.group(1)), int(m.group(2))
            continue
        if line.startswith(("---", "+++")):
            continue
        if line.startswith("-"):
            lines.append(("-", old_n, new_n, line[1:]))
            old_n += 1
        elif line.startswith("+"):
            lines.append(("+", old_n, new_n, line[1:]))
            new_n += 1
        else:
            lines.append((" ", old_n, new_n, line))
            old_n += 1
            new_n += 1
    return lines


def storage_path(p: str) -> str:
    """User er path ke ALWAYS /storage/emulated/0 te map kore.
    /sdcard, ~/storage, ~, relative path — sob handle kore. (User files storage e, Termux home NA)"""
    if p.startswith("/storage/emulated/0"):
        return p
    if p == "/sdcard" or p.startswith("/sdcard/"):
        return "/storage/emulated/0" + p[len("/sdcard"):]
    if p == "~/storage" or p.startswith("~/storage/"):
        return "/storage/emulated/0" + p[len("~/storage"):]
    if p in ("storage", "sdcard", "internal", "internal memory", "phone storage"):
        return "/storage/emulated/0"
    if p == "~" or p.startswith("~/"):
        return "/storage/emulated/0" + p[1:]
    if not p.startswith("/"):
        return os.path.join("/storage/emulated/0", p)
    return p


def sanitize_run_cmd(cmd):
    """run command er bhul path patterns -> /storage/emulated/0 (cd /storage, ~, /sdcard...)."""
    cmd = cmd.replace("$HOME/storage", "/storage/emulated/0")
    cmd = cmd.replace("~/storage", "/storage/emulated/0")
    cmd = cmd.replace("/sdcard", "/storage/emulated/0")
    cmd = re.sub(r"(?<!\S)~(?=\s|['\"]|$)", "/storage/emulated/0", cmd)
    cmd = re.sub(r"(?<!\S)/storage(?!/emulated)(?=[/\s'\"]|$)", "/storage/emulated/0", cmd)
    cmd = re.sub(r"(?<!\S)cd\s+(storage|sdcard)\b", "cd /storage/emulated/0", cmd)
    return cmd


def sanitize_tool_args(name, attrs, content):
    """parse_tools er por — prottek tool er path auto-correct kore storage te."""
    if name in ("ls", "read", "write"):
        if "path" in attrs:
            attrs["path"] = storage_path(attrs["path"])
        if name == "ls" and not attrs.get("path"):
            content = storage_path(content)
    elif name == "run":
        content = sanitize_run_cmd(content)
    return name, attrs, content


def exec_tool(cfg, name, arg, content, session_perm, attrs=None, auto_approve=False):
    """Returns (result_text, diff_info_or_None)."""
    attrs = attrs or {}
    if name == "run":
        if not check_perm(cfg, "cmd", arg, session_perm, auto_approve=auto_approve):
            return "[Tool run: user denied]", None
        ui_note(C_DIM + f"$ {short(arg, 40)}" + C_RESET)
        code, out, shown = run_command(sanitize_run_cmd(arg), False)
        if code != 0 and re.search(
            r"permission denied|operation not permitted|not permitted|eacces", out, re.I
        ):
            ui_note(C_YELLOW + "! Permission denied — kono kichu korar dorkar nei, AI ke bolo.")
        return f"[Tool run exit={code}]\n{truncate(out)}\n[/Tool run]", None

    if name == "ls":
        arg = storage_path(arg)
        if not check_perm(cfg, "file", arg, session_perm, prompt=False):
            return "[Tool ls: user denied]", None
        try:
            entries = sorted(os.listdir(arg))
            listing = "\n".join(e + ("/" if os.path.isdir(os.path.join(arg, e)) else "") for e in entries[:200])
        except OSError as e:
            listing = f"error: {e}"
        return f"[Tool ls {arg}]\n{truncate(listing)}\n[/Tool ls]", None

    if name == "read":
        arg = storage_path(arg)
        if not check_perm(cfg, "file", arg, session_perm, prompt=False):
            return "[Tool read: user denied]", None
        try:
            with open(arg, "rb") as f:
                data = f.read(300 * 1024)
            text = data.decode(errors="replace")
        except OSError as e:
            return f"[Tool read {arg}]\nerror: {e}\n[/Tool read]", None
        return f"[Tool read {arg}]\n{truncate(text)}\n[/Tool read]", None

    if name == "write":
        arg = storage_path(arg)
        if not check_perm(cfg, "file", arg, session_perm, auto_approve=auto_approve):
            return "[Tool write: user denied]", None
        try:
            os.makedirs(os.path.dirname(os.path.abspath(arg)), exist_ok=True)
            old = ""
            exists = os.path.isfile(arg)
            if exists:
                try:
                    with open(arg, "r", errors="replace") as f:
                        old = f.read(300 * 1024)
                except OSError:
                    pass
            with open(arg, "w") as f:
                f.write(content)
            diff = None
            if old != content:
                lines = make_diff_lines(old, content)
                if lines:
                    diff = {"path": arg, "exists": exists, "lines": lines}
            return f"[Tool write {arg}]: saved {len(content)} chars", diff
        except OSError as e:
            return f"[Tool write {arg}]\nerror: {e}\n[/Tool write]", None

    if name == "search":
        ui_note(C_DIM + f"🔎 searching: {short(content, 40)}")
        try:
            res = ddg_search(content)
        except Exception as e:
            return f"[Tool search error: {e}]", None
        if not res:
            return "[Tool search: kichu result pai nai]", None
        lines = [f"{i + 1}. {r['title']} — {r['url']}\n   {r['snippet']}" for i, r in enumerate(res)]
        return "[Tool search]\n" + "\n".join(lines) + "\n[/Tool search]", None

    return f"[Tool {name}: unknown]", None


def parse_tools(text):
    tools = []
    for m in TOOL_RE.finditer(text):
        name, attrs_str, content = m.groups()
        attrs = {k: (v or "") for k, v in ATTR_RE.findall(attrs_str)}
        tools.append((name, attrs, content))
    return tools


# ---------------- ui ----------------

def fmt_duration(sec):
    if sec < 60:
        return f"{sec:.0f}s"
    return f"{sec // 60}m {sec % 60:.0f}s"


def fmt_thought(sec):
    if sec < 1:
        return f"{int(round(sec * 1000))}ms"
    return f"{sec:.1f}s"


# ---------------- TUI ----------------

def term_size():
    rows = cols = 0
    try:
        import fcntl
        import struct
        with open("/dev/tty") as f:
            s = fcntl.ioctl(f.fileno(), fcntl.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0))
        rows, cols = struct.unpack("HHHH", s)[:2]
    except Exception:
        pass
    if rows <= 0 or cols <= 0:
        try:
            cols = int(os.environ.get("COLUMNS") or 0)
            rows = int(os.environ.get("LINES") or 0)
        except Exception:
            pass
    if rows <= 0 or cols <= 0:
        try:
            s = shutil.get_terminal_size()
            rows, cols = s.lines, s.columns
        except Exception:
            rows, cols = 24, 60
    return max(20, min(max(cols, 1), 120)), max(10, min(max(rows, 1), 200))


def wrap_text(text, width):
    lines = []
    for para in text.split("\n"):
        if not para:
            lines.append("")
            continue
        words = para.split(" ")
        cur = ""
        for w in words:
            if not cur:
                cur = w
            elif len(cur) + 1 + len(w) <= width:
                cur += " " + w
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def short_path():
    cwd = os.getcwd()
    home = os.path.expanduser("~")
    if cwd.startswith(home):
        return "~" + cwd[len(home):]
    return cwd


def list_free():
    lines = ["Free models (OpenCode Zen):"]
    for m in FREE_MODELS:
        lines.append("  " + m)
    lines.append("Live list: python3 bangbot.py --models")
    return "\n".join(lines)


def show_perms(cfg):
    perm = cfg.get("perm", {})
    lines = ["Permission rules:"]
    lines.append(f"  default command: {perm.get('default_cmd', 'ask')}")
    lines.append(f"  default file:    {perm.get('default_file', 'ask')}")
    lines.append(f"  command rules:   {perm.get('cmd', {}) or '(none)'}")
    lines.append(f"  file rules:      {perm.get('file', {}) or '(none)'}")
    lines.append("Set: /perm cmd|file <ask|always|deny> | /perm reset")
    lines.append("Specific: /perm cmd add '<cmd>' <mode>")
    return "\n".join(lines)


def save_session(name, messages):
    os.makedirs(CHATS_DIR, exist_ok=True)
    path = os.path.join(CHATS_DIR, name + ".json")
    with open(path, "w") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
    return path


def list_sessions():
    os.makedirs(CHATS_DIR, exist_ok=True)
    return sorted(f[:-5] for f in os.listdir(CHATS_DIR) if f.endswith(".json"))


def load_session(name):
    path = os.path.join(CHATS_DIR, name + ".json")
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def help_text():
    return "\n".join([
        "Commands:",
        "  /model <id>      model change        /models      free model list",
        "  /new             new chat            /sessions    popup session list",
        "  /save [name]     save chat           /load <name> load chat",
        "  /rm <name>       delete session      /stats       token count",
        "  Session e: Ctrl+D = delete (confirm) · Ctrl+R = rename (Enter save)",
        "  /perm            permission rules    /undo        last message revert",
        "  /mode            Plan/Build toggle (Tab o kaj kore)",
        "  /exit            quit",
        "",
        "Modes:",
        "  Plan mode (green): AI shudhu analyze/plan kore — file/command kono change na",
        "  Build mode (blue): AI file likhte / command chalate pare",
        "",
        "AI tools (AI nije use korbe):",
        "  search: default ON (permission chara) | read/ls: default allow",
        "  run/write: arrow prompt (←→ Yes/No/Always, Enter confirm)",
        "  /perm diye rule set: /perm cmd add 'rm' deny",
        "  Permission options: Allow once | Allow session (current chat) | Always (save) | Reject",
        "  Ctrl+E: toggle auto-approve (all permissions auto-allow, no prompts)",
        "  Ctrl+Z: last sent message revert",
        "Multi-line: line er seshe '\\' dile continue hobe.",
    ])


def rel_time(ts):
    d = time.time() - ts
    if d < 60:
        return "now"
    if d < 3600:
        return f"{int(d // 60)}m ago"
    if d < 86400:
        return f"{int(d // 3600)}h ago"
    return f"{int(d // 86400)}d ago"


def session_list():
    """Returns list of (name, mtime, msg_count, preview) sorted by most recent."""
    os.makedirs(CHATS_DIR, exist_ok=True)
    out = []
    for f in os.listdir(CHATS_DIR):
        if f.endswith(".json"):
            p = os.path.join(CHATS_DIR, f)
            mtime = os.path.getmtime(p)
            msgs = load_session(f[:-5])
            if msgs and isinstance(msgs, list):
                count = len([m for m in msgs if m.get("role") != "system"])
                preview = ""
                for m in reversed(msgs):
                    if m.get("role") == "user":
                        preview = m.get("content", "")[:40].replace("\n", " ")
                        break
                if not preview:
                    for m in reversed(msgs):
                        if m.get("role") == "assistant":
                            preview = m.get("content", "")[:40].replace("\n", " ")
                            break
                out.append((f[:-5], mtime, count, preview))
            else:
                out.append((f[:-5], mtime, 0, ""))
    out.sort(key=lambda x: -x[1])
    return out


BB_TERM_RAW = False


def _utf8_reader(fd):
    dec = codecs.getincrementaldecoder("utf-8")(errors="replace")

    def read_char():
        while True:
            b = os.read(fd, 1)
            if not b:
                return ""
            ch = dec.decode(b)
            if ch:
                return ch

    return read_char


def raw_key():
    """Read one key (raw mode). Returns token: char / UP/DOWN/LEFT/RIGHT/TAB/ENTER/ESC/BACK/CTRL-C."""
    if not (termios and sys.stdin.isatty()):
        try:
            ch = sys.stdin.read(1)
        except EOFError:
            return "CTRL-C"
        if ch in ("\r", "\n"):
            return "ENTER"
        if ch == "\x03":
            return "CTRL-C"
        if ch == "\x10":
            return "CTRL-P"
        if ch == "\x04":
            return "CTRL-D"
        if ch == "\x05":
            return "CTRL-E"
        if ch == "\x12":
            return "CTRL-R"
        if ch == "\x1a":
            return "CTRL-Z"
        if ch in ("\x7f", "\x08"):
            return "BACK"
        if ch == "\x1b":
            return "ESC"
        if ch == "\t":
            return "TAB"
        return ch
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        read_char = _utf8_reader(fd)
        ch = read_char()
        if ch == "\x1b":
            r, _, _ = select.select([fd], [], [], 0.06)
            if not r:
                return "ESC"
            nxt = read_char()
            if nxt == "[":
                k = read_char()
                if k == "A":
                    return "UP"
                if k == "B":
                    return "DOWN"
                if k == "C":
                    return "RIGHT"
                if k == "D":
                    return "LEFT"
                if k == "5":
                    read_char()
                    return "PGUP"
                if k == "6":
                    read_char()
                    return "PGDN"
                if k == "H":
                    return "HOME_K"
                if k == "F":
                    return "END_K"
                if k == "M":
                    for _ in range(3):
                        read_char()
                    return ""
                if k == "<":
                    btn = ""
                    while True:
                        c = read_char()
                        if not c:
                            return ""
                        if c == ";":
                            break
                        btn += c
                    while True:
                        c = read_char()
                        if not c:
                            return ""
                        if c in ("M", "m"):
                            break
                    try:
                        b = int(btn)
                    except ValueError:
                        return ""
                    if b == 64:
                        return "WHEEL_UP"
                    if b == 65:
                        return "WHEEL_DOWN"
                    return ""
                while True:
                    b = read_char()
                    if not b or b in CSI_FINAL_CHARS:
                        break
                return ""
            if nxt == "O":
                k = read_char()
                if k == "A":
                    return "UP"
                if k == "B":
                    return "DOWN"
                if k == "C":
                    return "RIGHT"
                if k == "D":
                    return "LEFT"
                return ""
            return ""
        if ch in ("\r", "\n"):
            r, _, _ = select.select([fd], [], [], 0.02)
            if r:
                nxt = read_char()
                if nxt not in ("\r", "\n"):
                    return nxt
            return "ENTER"
        if ch == "\x03":
            return "CTRL-C"
        if ch == "\x10":
            return "CTRL-P"
        if ch == "\x04":
            return "CTRL-D"
        if ch == "\x05":
            return "CTRL-E"
        if ch == "\x12":
            return "CTRL-R"
        if ch == "\x1a":
            return "CTRL-Z"
        if ch in ("\x7f", "\x08"):
            return "BACK"
        if ch == "\t":
            return "TAB"
        if ch.isprintable() or ord(ch) >= 160:
            return ch
        return ""
    finally:
        if not BB_TERM_RAW:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


COMMAND_LIST = ["/help", "/model ", "/models", "/new", "/undo", "/save ", "/load ", "/sessions",
                "/rm ", "/stats", "/perm", "/exit"]

PALETTE_CMDS = ["/help", "/new", "/models", "/sessions", "/save", "/load", "/rm",
                "/perm", "/stats", "/exit", "/undo"]
NEEDS_ARG = ("/save", "/load", "/rm")

TYPESTEP = 6
# v4 typewriter speed profile: (limit, ms/char) — first 20 fast, next 100 readable, rest scannable
TYPE_PROFILE = [(20, 0.015), (120, 0.025), (10 ** 9, 0.008)]
PUNCT_PAUSE = 0.08  # extra pause after punctuation (v4 spec)


class UI:
    def __init__(self, cfg):
        self.cfg = cfg
        self.api_key = get_api_key(cfg)
        self.model = DEFAULT_MODEL
        self.root_on = False
        self.plain = not (termios and sys.stdin.isatty())
        self.route = "home"
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.notices = []
        self.notes = []
        self.status = "ready"
        self.mode = "build"
        self.session_perm = {"cmd": set(), "file": set()}
        self.loaded_name = None
        self.buf = ""
        self.hist = []
        self.hidx = 0
        self.cur = 0
        self.streaming = False
        self.cancel = False
        self.pending = ""
        self.reasoning = ""
        self.popup = None
        self.popup_idx = 0
        self.palette = False
        self.palette_idx = 0
        self.sess_pick = None
        self.sess_idx = 0
        self.model_pick = None
        self.model_idx = 0
        self.cmd_pick = False
        self.cmd_idx = 0
        self.expand_diffs = set()
        self.renaming = False
        self.scroll_off = 0
        self._acc = ""
        self._esc_pending = False
        self.auto_approve = False
        self.spin = "⠋"
        self._draw_lock = threading.Lock()
        self.resized = False
        self.quitting = False
        self._comp = -1
        self._undo_msg = None
        self.compact = False
        self.tiny_input = False
        self.tiny_rows = False
        self.wide = False
        self._anim_hdr = None
        self._anim_t0 = 0.0
        self._hdr_override = None
        self.sec_focus = None
        self._cursor_on = True
        self._last_key = 0.0
        self._notice_t = 0.0
        self._mode_flash = 0.0
        self._approve_pop = 0.0
        self._tool_progress = None  # v4.5: (name, arg, start_time) — tool exec animation
        self._popup_birth = 0.0
        self._route_fade = 0.0
        self.palette_filter = ""
        self._palette_prev = -1
        self._palette_t = 0.0
        self.sess_expand = None
        self.anim = True
        self._entrance = None
        self._sec_anim = None
        self._suck = 0.0
        self._render_hist = []
        self._stream_speeds = []
        self._boot_t = time.time()
        self._last_reply_dt = 0.0
        self.timing_panel = False

    def anim_header(self, new_title, W):
        """v4 session-switch header animation — typewriter reveal, 7 frames x 40ms."""
        if self.plain or new_title == self._anim_hdr:
            return
        self._anim_hdr = new_title
        for frame in range(1, 8):
            n = max(1, int(len(new_title) * frame / 7))
            self._hdr_override = new_title[:n]
            self.redraw()
            time.sleep(0.04)
        self._hdr_override = None
        self.redraw()

    def _popup_birth_anim(self):
        """v4: popup birth — 4-frame grow-in (120ms)."""
        if not self.anim:
            self.redraw()
            return
        for f in range(1, 5):
            self._popup_birth = f / 4
            self.redraw()
            time.sleep(0.03)
        self._popup_birth = 0.0
        self.redraw()

    def _route_transition(self):
        """v4: home<->chat fade — 3 dim frames (105ms)."""
        if not self.anim:
            self.redraw()
            return
        for _ in range(3):
            self._route_fade = time.time()
            self.redraw()
            time.sleep(0.035)
        self._route_fade = 0.0
        self.redraw()

    # ---------- screen ----------

    def enter(self):
        global BB_TERM_RAW
        sys.stdout.write("\x1b[?1049h\x1b[2J\x1b[H\x1b[?25l\x1b[?1000h\x1b[?1006h")
        sys.stdout.flush()
        self._old_termios = None
        if termios and sys.stdin.isatty():
            try:
                fd = sys.stdin.fileno()
                self._old_termios = termios.tcgetattr(fd)
                tty.setraw(fd)
                BB_TERM_RAW = True
            except Exception:
                self._old_termios = None

        def on_winch(sig, frame):
            self.resized = True

        try:
            signal.signal(signal.SIGWINCH, on_winch)
        except (ValueError, AttributeError):
            pass

        if not self.plain:
            threading.Thread(target=self.anim_loop, daemon=True).start()

    def anim_loop(self):
        """v4 spinner + typewriter reveal while streaming; v4.5 tool-work progress bar."""
        tick = 0
        while not self.quitting:
            if not (self.streaming or getattr(self, "_tool_progress", None)) or self.plain:
                time.sleep(0.1)
                continue
            tick += 1
            if not self.streaming:
                # v4.5: tool exec hoitache — box er niche ■/⬝ bar anim (main thread blocked)
                if self.anim:
                    self.redraw()
                time.sleep(0.05)
                continue
            acc = self._acc
            n = len(acc) - self._revealed
            if n > 0 and not self.anim:
                # v4: animations OFF — instant reveal
                self.pending += acc[self._revealed:]
                self._revealed = len(acc)
                self.redraw()
                time.sleep(0.05)
            elif n > 0:
                idx = self._revealed
                limit, delay = TYPE_PROFILE[0]
                for lm, d in TYPE_PROFILE:
                    if idx < lm:
                        delay = d
                        break
                step = min(TYPESTEP, n)
                chunk = acc[self._revealed:self._revealed + step]
                self.pending += chunk
                self._revealed += step
                self.redraw()
                time.sleep(delay)
                if chunk and chunk[-1] in ".!?।।":
                    time.sleep(PUNCT_PAUSE)
            elif not self.pending:
                self.spin = SPINNER[tick % len(SPINNER)] if self.anim else SPINNER[0]
                self.redraw()
                time.sleep(0.12)
            else:
                time.sleep(0.1)

    def exit(self):
        global BB_TERM_RAW
        if BB_TERM_RAW and self._old_termios is not None:
            try:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._old_termios)
            except Exception:
                pass
            BB_TERM_RAW = False
        sys.stdout.write("\x1b[?25h\x1b[?1000l\x1b[?1006l\x1b[?1049l")
        sys.stdout.flush()

    def notice(self, label, text):
        if self.plain:
            for ln in wrap_text(text, 74):
                print("  " + C_YELLOW + "[" + label + "] " + ln + C_RESET)
        else:
            self.notices = [(label, text)]
            self._notice_t = time.time()
            self.redraw()

    # opencode-style rendering: full-width panel header bar, message cards
    # with left accent border, plain assistant text, prompt + footer

    def hdr(self, title, right, W):
        pad = max(1, W - 4 - dlen(title) - dlen(right))
        return ("  " + C_ACC + "│" + C_RESET + C_PANEL + " " + C_BOLD + C_TEXT + title
                + C_RESET + C_PANEL + " " * pad + C_MUTED + right + C_RESET)

    def card_row(self, color, text, W):
        pad = max(0, W - 6 - dlen(text))
        return "  " + color + "│" + C_RESET + C_PANEL + " " + text + " " * pad + C_RESET

    def box_top(self, color, title, W, lead=2, bw=None):
        bw = bw or (W - lead)
        title = short(title, 14)
        X = max(0, bw - 5 - dlen(title))
        return " " * lead + color + "┌─ " + title + " " + "─" * X + "┐" + C_RESET

    def box_row(self, color, text, W, lead=2, bw=None):
        bw = bw or (W - lead)
        pad = max(0, bw - 4 - dlen(text))
        return " " * lead + color + "│" + C_RESET + " " + text + " " * pad + " " + color + "│" + C_RESET

    def box_row_right(self, color, text, W, lead=2, bw=None):
        bw = bw or (W - lead)
        pad = max(0, bw - 4 - dlen(text))
        return " " * lead + color + "│" + C_RESET + " " * pad + text + " " + color + "│" + C_RESET

    def box_bottom(self, color, W, lead=2, bw=None):
        bw = bw or (W - lead)
        return " " * lead + color + "└" + "─" * max(0, bw - 2) + "┘" + C_RESET

    def card(self, color, text, W, top_gap=False, time_prefix=""):
        out = []
        if top_gap:
            out.append(self.card_row(color, "", W))
        lines = wrap_text(text, max(20, W - 6))
        for i, ln in enumerate(lines):
            if i == 0 and time_prefix:
                display = C_DIM + time_prefix + C_RESET + " " + ln
            else:
                display = ln
            out.append(self.card_row(color, display, W))
        return out

    def notice_card(self, label, text, W):
        """v4 micro: notice slide-in (180ms) + ERR shake (250ms) + SYS pulse."""
        if label == "ERR":
            color, icon = C_ERRC, "✗"
        elif label == "SYS":
            color, icon = C_ACC, "●"
        elif label == "WARN":
            color, icon = C_WARN, "⚠"
        elif label == "GOOD":
            color, icon = C_GOOD, "✓"
        else:
            color, icon = C_MUTED, "ℹ"
        nt = time.time() - self._notice_t
        pad = int(6 * max(0.0, 1.0 - nt / 0.18))
        if label == "ERR" and nt < 0.25:
            pad += max(0, int(2 * (1 - nt / 0.25)))
        shown = text
        if label == "SYS" and nt < 0.6 and int(nt * 12) % 2 == 0:
            shown = C_BOLD + text
        return self.card(color, " " * pad + " " + icon + " [" + label + "] " + shown, W)

    def diff_card(self, d, W):
        out = []
        path = d["path"]
        title = ("← Edit " if d.get("exists") else "← Write ") + path
        out += self.card(C_ACC, C_BOLD + C_TEXT + title + C_RESET, W)
        lines = d["lines"]
        adds = sum(1 for k, *_ in lines if k == "+")
        dels = sum(1 for k, *_ in lines if k == "-")
        stats = C_MUTED + "  +" + str(adds) + " −" + str(dels) + C_RESET
        expanded = path in self.expand_diffs
        tail = False
        if len(lines) > 6 and not expanded:
            lines = lines[:4]
            collapsed = True
        else:
            collapsed = False
            max_show = 40
            if len(lines) > max_show:
                lines = lines[:max_show]
                tail = True
        maxn = max((len(str(a or b)) for _, a, b, _ in lines), default=0)
        for kind, a, b, text in lines:
            if kind == "-":
                num, fg, mark = a, C_RED, "-"
            elif kind == "+":
                num, fg, mark = b, C_GOOD, "+"
            else:
                num, fg, mark = a, C_MUTED, " "
            txt = truncate(text.replace("\t", "  "), W - 12).replace("\n", " ")
            ln = fg + mark + str(num or " ").rjust(maxn) + " " + txt + C_RESET
            out.append(self.card_row(fg, ln, W))
        if collapsed:
            left = len(d["lines"]) - len(lines)
            out.append(self.card_row(C_ACC, C_BOLD + "… " + str(left) + " more" + C_RESET
                                     + stats + C_MUTED + "  [Enter] expand" + C_RESET, W))
        elif tail:
            out.append(self.card_row(C_MUTED, "… " + str(len(d["lines"]) - max_show) + " more", W))
        return out

    def _sec_toggle_anim(self, key, expand):
        """v4: section line-by-line expand/collapse — 6 frames x 30ms."""
        if not self.anim:
            self.redraw()
            return
        steps = 6
        for f in range(1, steps + 1):
            frac = f / steps if expand else 1.0 - f / steps + 1 / steps
            self._sec_anim = (key, frac)
            self.redraw()
            time.sleep(0.03)
        self._sec_anim = None
        self.redraw()

    def toggle_diff_expand(self):
        """Enter on empty buf: expand/collapse the most recent big diff card / summary section."""
        for n in reversed(self.notes):
            if isinstance(n, dict) and len(n["lines"]) > 6:
                path = n["path"]
                if path in self.expand_diffs:
                    self.expand_diffs.discard(path)
                else:
                    self.expand_diffs.add(path)
                return True
        for i in range(len(self.messages) - 1, 0, -1):
            msg = self.messages[i]
            if msg.get("role") == "assistant":
                n_secs = sum(1 for k, t, c in self._parse_sections(msg["content"]) if k == "sec")
                if n_secs:
                    keys = [f"sec:{i}:{j}" for j in range(n_secs)]
                    if all(k in self.expand_diffs for k in keys):
                        for k in keys:
                            self.expand_diffs.discard(k)
                    else:
                        for k in keys:
                            self.expand_diffs.add(k)
                    return True
        return False

    def _parse_sections(self, text):
        """v4 reply structure -> [(kind, title, content)].
        kind: 'body' bright normal | 'head' bold header | 'sec' collapsible dim | 'meta' dim footer."""
        chunks = []
        cur_kind = "body"
        cur_title = None
        cur = []
        head_re = re.compile(r"^\*\*(.+?)\*\*:?\s*(.*)$")

        def push():
            content = "\n".join(cur).strip("\n")
            if content or cur_kind == "body":
                chunks.append((cur_kind, cur_title, content))

        i, n = 0, len(text.split("\n"))
        lines = text.split("\n")
        while i < n:
            raw = lines[i]
            s = raw.strip()
            if s.startswith("**Summary:**"):
                push()
                cur_kind = "sec"
                cur_title = None
                cur = []
                i += 1
                continue
            m = re.match(r"^▸\s+(.+?)\s*$", s)
            if m and cur_kind == "sec":
                title = re.sub(r"\s*\(collapsed\)\s*$", "", m.group(1).strip())
                push()
                cur_title = title
                cur = []
                i += 1
                continue
            mh = head_re.match(s)
            if mh and not s.startswith("**Summary:**"):
                push()
                chunks.append(("head", mh.group(1).strip().rstrip(":"), mh.group(2)))
                cur_kind = "body"
                cur_title = None
                cur = []
                i += 1
                continue
            cur.append(raw)
            i += 1
        push()
        out = []
        for kind, title, content in chunks:
            if kind in ("body", "head", "sec") and content:
                keep, metas = [], []
                for ln in content.split("\n"):
                    if re.match(r"^\s*Location:\s*\S", ln):
                        metas.append(ln.strip())
                    else:
                        keep.append(ln)
                if "".join(keep).strip():
                    out.append((kind, title, "\n".join(keep)))
                for ml in metas:
                    out.append(("meta", None, ml))
            else:
                out.append((kind, title, content))
        return out

    def _body_only(self, pend):
        """Streaming: body part only (sections + tool lines hidden until done)."""
        cut = pend.split("**Summary:**", 1)[0]
        lines = []
        for l in cut.split("\n"):
            if l.strip().startswith("→ ") or re.search(r"<(run|write|read|search)>", l):
                continue
            l = re.sub(r"\*\*(.+?)\*\*\s*:?\s*(.*)", lambda m: m.group(1) + ": " + m.group(2), l)
            lines.append(l)
        return "\n".join(lines)

    def assistant_block(self, model, text, W, think=None, reasoning="", time_prefix="", msg_idx=0):
        """v4.5 redesigned: tool work DIM outside (no box), reply body + sections INSIDE
        purple VOXEL box, model tag bottom-right inside, 1 turn = 1 box."""
        tag_re = re.compile(r"<(run|write|read|search)[^>]*>\s*(.*?)\s*</\1>", re.S)
        def tag_line(m):
            name = m.group(1)
            cmd = short(m.group(2), 45)
            return f"→ {name}" + (f": {cmd}" if cmd else "")
        text2 = tag_re.sub(tag_line, text)
        outside = []
        inner = []
        sec_idx = 0
        sec_keys = []
        sections = self._parse_sections(text2)
        if think is not None:
            key = f"sec:{msg_idx}:think"
            sec_keys.append(key)
            outside.append("    " + C_MUTED + "▸ Thought: " + fmt_thought(think) + C_RESET)
            if key in self.expand_diffs and reasoning.strip():
                for ln in wrap_text(reasoning, max(20, W - 8)):
                    outside.append("      " + C_MUTED + ln + C_RESET)
        for kind, title, content in sections:
            if kind == "body":
                steps = [x for x in content.split("\n") if x.strip().startswith("→ ")]
                body = [x for x in content.split("\n") if not x.strip().startswith("→ ")]
                for s in steps:
                    outside.append("    " + self._status_line(s.strip(), W))
                if "".join(body).strip():
                    for ln in wrap_text("\n".join(body), max(20, W - 6)):
                        inner.append(C_TEXT + ln + C_RESET)
            elif kind == "head":
                inner.append(C_HIGHLIGHT + C_TEXT + title + ":" + C_RESET)
                if content.strip():
                    for ln in wrap_text(content, max(20, W - 6)):
                        inner.append(C_TEXT + ln + C_RESET)
            elif kind == "sec":
                key = f"sec:{msg_idx}:{sec_idx}"
                sec_idx += 1
                sec_keys.append(key)
                # v4.5: tool/cmd sections BOX ER BAIRE — dim collapsible lines (box e dekhte kharap)
                outside += self.section_block(key, title or "Details", content, W,
                                              focused=(key == self.sec_focus), pad="    ")
            elif kind == "meta":
                inner.append(C_MUTED + content + C_RESET)
        if not inner:
            self._sec_keys = sec_keys
            return outside
        box = [self.box_top(C_ACC, "VOXEL", W)]
        if time_prefix:
            box.append(self.box_row(C_ACC, C_DIM + time_prefix + C_RESET, W))
            box.append(self.box_row(C_ACC, "", W))
        for ln in inner:
            box.append(self.box_row(C_ACC, ln, W))
        box.append(self.box_row(C_ACC, "", W))
        tag = C_DIM + "-".join(model.split("-")[:2]) + C_RESET
        box.append(self.box_row_right(C_ACC, tag, W))
        box.append(self.box_bottom(C_ACC, W))
        self._sec_keys = sec_keys
        return outside + box

    def section_block(self, key, title, content, W, focused=False, no_suffix=False, pad=""):
        """v4.5 collapsible dim section — pad="    " box er baire, pad="" box er vitore."""
        out = []
        expanded = key in self.expand_diffs
        c_lines = [l for l in content.split("\n") if l.strip() not in ("```", "```bash", "```text")]
        c_text = "\n".join(c_lines)
        suffix = "" if no_suffix else " (collapsed)"
        if expanded:
            header = C_MUTED + "▾ " + title + C_RESET
            if focused:
                header += "  " + C_MUTED + "◄──" + C_RESET
            out.append(pad + header)
            w_lines = wrap_text(c_text, max(20, W - 8))
            # v4: line-by-line expand/collapse anim slice
            if self._sec_anim and self._sec_anim[0] == key:
                w_lines = w_lines[:max(1, int(len(w_lines) * self._sec_anim[1]))]
            for ln in w_lines:
                out.append(pad + "  " + self._status_line(ln, W))
        else:
            if focused:
                out.append(pad + C_ACC + "▸ " + C_RESET + C_MUTED + title + suffix + C_RESET
                           + "  " + C_MUTED + "◄──" + C_RESET)
            else:
                out.append(pad + C_MUTED + "▸ " + title + suffix + C_RESET)
        return out

    def _status_line(self, ln, W):
        """→ run: cmd ✓ 0.3s — status icon colored (✓ green / ✗ red), baki gray."""
        m = re.search(r"\s(✓|✗)(?:\s+(.+))?$", ln)
        if not m:
            return C_MUTED + ln + C_RESET
        rest = ln[:m.start()].rstrip()
        icon = m.group(1)
        extra = (m.group(2) or "").strip()
        base = C_MUTED + rest + " " + (C_GOOD if icon == "✓" else C_ERRC) + icon + C_RESET
        if extra:
            base += " " + C_MUTED + extra + C_RESET
        return base

    def plain_block(self, model, text, W, think=None, time_prefix="", show_model=True):
        """Main reply body — BRIGHT white (sole bright element, v4 spec)."""
        out = []
        if think is not None:
            out.append("    " + C_MUTED + "+ Thought: " + fmt_thought(think) + C_RESET)
        lines = wrap_text(text, max(20, W - 6))
        for i, ln in enumerate(lines):
            if i == 0 and time_prefix:
                display = "    " + C_MUTED + time_prefix + C_RESET + " " + C_TEXT + ln + C_RESET
            else:
                display = "    " + C_TEXT + ln + C_RESET
            out.append(display)
        if show_model:
            out.append("    " + C_MUTED + model + C_RESET)
        return out

    def steps_block(self, text, W):
        """Compact dim tool/step lines (→ ...) — v4: gray 245."""
        out = []
        for ln in text.split("\n"):
            s = ln.strip()
            if not s:
                continue
            s = truncate(s, W - 8)
            out.append("    " + C_MUTED + s + C_RESET)
        return out

    def prompt_line(self, W):
        disp = self.buf
        while dlen(disp) > W - 8:
            disp = disp[1:]
        if dlen(disp) > W - 9:
            disp = "…" + disp
        if disp:
            return "  " + C_ACC + "❯" + C_RESET + " " + C_TEXT + disp + C_RESET
        return ("  " + C_ACC + "❯" + C_RESET + " " + C_MUTED
                + "Type a message... (or /help)" + C_RESET)

    def prompt_box(self, W):
        """opencode-style input box, border color = mode (plan green / build blue)."""
        color = C_PLAN if self.mode == "plan" else C_BUILD
        disp = self.buf
        # v4: send suck-in — trailing chars collapse into the prompt arrow
        if self._suck > 0 and disp:
            disp = disp[:max(1, int(len(disp) * (1 - self._suck)))]
        # v4: cursor blink 530/530, typing e freeze, 1s por resume
        if time.time() - self._last_key < 1.0:
            self._cursor_on = True
        elif int(time.time() * 1000) % 1060 < 530:
            self._cursor_on = True
        else:
            self._cursor_on = False
        cursor = C_ACC + "▍" + C_RESET if self._cursor_on else ""
        while dlen(disp) > W - 12:
            disp = disp[1:]
        if dlen(disp) > W - 13:
            disp = "…" + disp
        if self.tiny_input:
            if disp:
                inner = C_TEXT + disp + C_RESET + cursor
                plain = "❯ " + disp + "▍"
            else:
                inner = C_MUTED + "Type..." + C_RESET + cursor
                plain = "❯ Type...▍"
            pad = max(1, W - 4 - dlen(plain))
            return ["  " + color + "❯" + C_RESET + " " + inner + " " * pad]
        if disp:
            inner = C_TEXT + disp + C_RESET + cursor
            plain = "❯ " + disp + "▍"
        else:
            inner = C_MUTED + "Type a message... (or /help)" + C_RESET + cursor
            plain = "❯ " + "Type a message... (or /help)" + "▍"
        pad = max(1, W - 6 - dlen(plain))
        return [
            "  " + color + "┌" + "─" * (W - 4) + "┐" + C_RESET,
            "  " + color + "│" + C_RESET + " " + C_ACC + "❯" + C_RESET + " " + inner + " " * pad + " " + color + "│" + C_RESET,
            "  " + color + "└" + "─" * (W - 4) + "┘" + C_RESET,
        ]

    def mode_chip(self):
        # v4: mode switch e brief reverse-video flash (cross-fade)
        if self.mode == "plan":
            chip = C_PLAN + "● plan" + C_RESET
        else:
            chip = C_BUILD + "● build" + C_RESET
        age = time.time() - self._mode_flash
        if age < 0.15:
            chip = "\x1b[7m" + C_BOLD + chip + C_RESET
        elif age < 0.5:
            chip = C_BOLD + chip
        return chip

    def footer_line(self):
        if self.popup:
            return "  " + C_MUTED + "←/→ Select · Enter Confirm · q Deny" + C_RESET
        if self.palette:
            return "  " + C_MUTED + "↑/↓ Select · Enter Run · Esc Close" + C_RESET
        if self.streaming:
            # v4: loading bar removed — simple spinner + counter
            speed_info = ""
            if self._stream_tokens > 0:
                elapsed = time.time() - self._stream_start
                speed = self._stream_tokens / elapsed if elapsed > 0 else 0
                if speed > 0:
                    speed_info = f" · ~{self._stream_tokens} tok · {speed:.0f}/s"
            return ("  " + C_ACC + self.spin + C_RESET + "  " + C_MUTED + "Thinking…" + C_RESET
                    + "  " + C_MUTED + "[Esc] Interrupt" + speed_info + C_RESET)
        if getattr(self, "_tool_progress", None):
            name, arg, _ = self._tool_progress
            return ("  " + C_ACC + "⏳" + C_RESET + "  " + C_MUTED + f"{name}: {truncate(arg, 30)}" + C_RESET
                    + "  " + C_MUTED + "[Esc] Interrupt · [Ctrl+P] Commands" + C_RESET)
        if self.route == "home":
            return "  " + C_MUTED + "↑/↓ select · Enter open · type = new chat · Tab = Plan/Build" + C_RESET
        if self.scroll_off > 0:
            return "  " + C_MUTED + "[↓ Newer] swipe down / wheel · [Ctrl+P] Commands" + C_RESET
        if self.renaming:
            return "  " + C_MUTED + "Name edit kore [Enter] Save · [Esc] Cancel" + C_RESET
        parts = []
        if self.buf.startswith("/"):
            parts.append("[Tab] Complete")
        elif self.buf:
            parts.append("[Tab] Plan/Build")
        if self._undo_msg:
            parts.append("[Ctrl+Z] Undo")
        if self.loaded_name:
            parts.append("[Ctrl+D] Del · [Ctrl+R] Rename")
        if self.auto_approve:
            parts.append("[Ctrl+E] Auto ✓")
        else:
            parts.append("[Ctrl+E] Auto")
        parts.append("[Ctrl+P]")
        return "  " + C_MUTED + " · ".join(parts) + C_RESET

    def palette_card(self, W):
        out = []
        filter_txt = self.palette_filter
        shown = [c for c in PALETTE_CMDS if filter_txt in c]
        title = "⌘ Commands" + (f" /{filter_txt}" if filter_txt else "")
        out += self.card(C_ACC, C_BOLD + title + C_RESET, W)
        if self.palette_idx >= len(shown):
            self.palette_idx = 0
        for i, c in enumerate(shown):
            if i == self.palette_idx:
                out.append(self.card_row(C_ACC, C_BOLD + "❯ " + c + C_RESET, W))
            elif self._palette_t and time.time() - self._palette_t < 0.12 and i == self._palette_prev:
                # v4: cursor slide — old row briefly dims with ❯
                out.append(self.card_row(C_DIM, "❯ " + c, W))
            else:
                out.append(self.card_row(C_MUTED, "  " + c, W))
        return out

    def cmd_pick_card(self, W):
        out = []
        out += self.card(C_ACC, C_BOLD + "Commands" + C_RESET, W)
        items = ["AUTO"] + [c for c in COMMAND_LIST if c.startswith(self.buf)]
        if self.cmd_idx >= len(items):
            self.cmd_idx = 0
        for i, c in enumerate(items):
            label = "⚡ Auto-approve this session" if c == "AUTO" else c
            if i == self.cmd_idx:
                out.append(self.card_row(C_ACC, C_BOLD + "❯ " + label + C_RESET, W))
            else:
                out.append(self.card_row(C_MUTED, "  " + label, W))
        return out

    def session_pick_card(self, W):
        out = []
        out += self.card(C_ACC, C_BOLD + "Sessions" + C_RESET + " " * (W - 15) + C_MUTED + "esc" + C_RESET, W)
        out.append(self.card_row(C_MUTED, "Search", W))
        out.append(self.card_row(C_MUTED, "", W))
        # Group by date
        from collections import defaultdict
        by_date = defaultdict(list)
        for item in self.sess_pick:
            name = item[0]
            mtime = item[1]
            count = item[2] if len(item) > 2 else 0
            preview = item[3] if len(item) > 3 else ""
            dt = time.strftime("%a %b %d %Y", time.localtime(mtime))
            by_date[dt].append((name, count, preview))
        for date, sessions in by_date.items():
            out.append(self.card_row(C_ACC, C_BOLD + date + C_RESET, W))
            for name, count, preview in sessions:
                selected = name == self.sess_pick[self.sess_idx][0]
                marker = "▶" if selected else "○"
                label = f"{marker} {name}" + (f" — {preview[:25]}" if preview else "")
                out.append(self.card_row(C_ACC if selected else C_MUTED,
                                         (C_BOLD if selected else "") + label + C_RESET, W))
                # v4: preview expand — selected session er preview lines
                if selected and self.sess_expand == name:
                    loaded = load_session(name) or []
                    for msg in loaded[1:4]:
                        if msg.get("role") in ("user", "assistant"):
                            out.append(self.card_row(C_DIM, "    " + short(msg.get("content", ""), 50), W))
        out.append(self.card_row(C_MUTED, "", W))
        out.append(self.card_row(C_MUTED, "pin/unpin " + C_BOLD + "ctrl+f" + C_RESET + "  delete " + C_BOLD + "ctrl+d" + C_RESET + "  rename " + C_BOLD + "ctrl+r" + C_RESET, W))
        return out

    def key_sess_pick(self, k):
        if k == "UP":
            self.sess_idx = max(0, self.sess_idx - 1)
        elif k == "DOWN":
            self.sess_idx = min(len(self.sess_pick) - 1, self.sess_idx + 1)
        elif k == "RIGHT":
            # v4: preview expand of selected session
            name = self.sess_pick[self.sess_idx][0]
            self.sess_expand = name if self.sess_expand != name else None
        elif k == "LEFT":
            self.sess_expand = None
        elif k == "ENTER":
            name = self.sess_pick[self.sess_idx][0]
            self.sess_pick = None
            self.sess_expand = None
            self.open_session(name)
            return
        elif k in ("ESC", "CTRL-C", "CTRL-P"):
            self.sess_pick = None
            self.sess_expand = None
        self.redraw()

    def model_pick_card(self, W):
        out = []
        out += self.card(C_ACC, C_BOLD + "🤖 Models — select kore Enter (Esc close)" + C_RESET, W)
        current = self.model
        for i, m in enumerate(FREE_MODELS):
            label = m
            if m == current:
                label += " ●"
            if i == self.model_idx:
                out.append(self.card_row(C_ACC, C_BOLD + "❯ " + label + C_RESET, W))
            else:
                out.append(self.card_row(C_MUTED, "  " + label, W))
        return out

    def key_model_pick(self, k):
        if k == "UP":
            self.model_idx = max(0, self.model_idx - 1)
        elif k == "DOWN":
            self.model_idx = min(len(FREE_MODELS) - 1, self.model_idx + 1)
        elif k == "ENTER":
            new_model = FREE_MODELS[self.model_idx]
            self.model = new_model
            self.cfg["model"] = new_model
            save_config(self.cfg)
            self.model_pick = None
            self.notice("SYS", "Model changed: " + new_model)
            self.redraw()
            return
        elif k in ("ESC", "CTRL-C", "CTRL-P"):
            self.model_pick = None
        self.redraw()

    def frame_home(self, W, H):
        lines = [self.hdr("VOXEL AI", self.mode_chip() + "  v3.8.3 · " + self.model, W)]
        body = [""]
        # ASCII art logo (hidden on tiny rows — portrait compact)
        if self.tiny_rows:
            body.append("  " + C_BOLD + C_TEXT + "VOXEL AI" + C_RESET)
        else:
            logo = [
                "  " + C_BOLD + C_TEXT + "██    ██  ██████  ██   ██ ███████ ██" + C_RESET,
                "  " + C_BOLD + C_TEXT + "██    ██ ██    ██  ██ ██  ██      ██" + C_RESET,
                "  " + C_BOLD + C_TEXT + "██    ██ ██    ██   ███   █████   ██" + C_RESET,
                "  " + C_BOLD + C_TEXT + " ██  ██  ██    ██  ██ ██  ██      ██" + C_RESET,
                "  " + C_BOLD + C_TEXT + "  ████    ██████  ██   ██ ███████ ███████" + C_RESET,
            ]
            body.extend(logo)
        body.append("")
        # Sessions list
        body.append("  " + C_MUTED + "Sessions" + C_RESET)
        body.append("")
        items = session_list()
        self.cur = max(0, min(self.cur, len(items) - 1))
        for i, (name, t, count, preview) in enumerate(items[:10]):
            label = name
            sub = f"{count} msgs · {preview[:30]}" if preview else f"{count} msgs"
            if i == self.cur:
                pad = max(1, W - 6 - dlen(label) - dlen(sub))
                body.append("  " + C_ACC + "│" + C_RESET + C_PANEL + " " + C_BOLD
                            + C_TEXT + label + C_RESET + C_PANEL + " " * pad
                            + C_MUTED + sub + C_RESET)
            else:
                pad = max(1, W - 4 - dlen(label) - dlen(sub))
                body.append("    " + C_DIM + label + " " * pad + sub + C_RESET)
        if not items:
            body.append("    " + C_DIM + "No sessions yet — type to start" + C_RESET)
        body.append("")
        if self.palette:
            body += self.palette_card(W)
        elif self.model_pick:
            body += self.model_pick_card(W)
        else:
            body.append("  " + C_MUTED + "↑/↓ select · Enter open · type = new chat · Ctrl+P = commands" + C_RESET)
        # Tip section
        body.append("")
        body.append("  " + C_WARN + "● Tip" + C_RESET + " " + C_MUTED + "Type /help for commands · /models to change model" + C_RESET)
        for label, text in self.notices:
            body += self.notice_card(label, text, W)
        body_max = max(1, H - 3)
        if len(body) > body_max:
            body = body[-body_max:]
        else:
            body += [""] * (body_max - len(body))
        lines += body
        lines.append(self.prompt_line(W))
        lines.append(self.footer_line())
        return lines[:H]

    def frame_chat(self, W, H):
        tok = SESSION_TOKENS["in"] + SESSION_TOKENS["out"]
        title = self._hdr_override or self.loaded_name or ("new chat" if len(self.messages) <= 1 else "chat")
        msg_count = len([m for m in self.messages if m.get("role") != "system"])
        if self.compact:
            right = "●" + ("P" if self.mode == "plan" else "B") + "·" + self.short_model() \
                    + "·" + self.fmt_tok(tok) + "·$0"
            if msg_count > 0:
                title += f"·{msg_count}m"
            lines = [self.hdr("# " + title, right, W)]
        else:
            right = f"{self.mode_chip()}  ● {self.model} · tok ~{tok} · $0"
            if msg_count > 0:
                title += f" · {msg_count} msgs"
            lines = [self.hdr("# " + title, right, W)]
        body = []
        for mi, msg in enumerate(self.messages[1:]):
            role, text = msg["role"], msg["content"]
            ts = msg.get("time")
            time_str = time.strftime("%H:%M", time.localtime(ts)) if ts else ""
            if text.startswith("[tool "):
                # v4: tool results hidden — Commands Executed section e fold
                continue
            if role == "user":
                # v4.5: green YOU box — RIGHT side (WhatsApp style), time inside, ❯ bold
                UW = max(28, int(W * 0.62))
                lead = max(4, W - UW)
                ulines = wrap_text(text, max(16, UW - 6))
                body.append(self.box_top(C_USER, "YOU", W, lead=lead, bw=UW))
                if time_str:
                    body.append(self.box_row(C_USER, C_DIM + time_str + C_RESET, W, lead=lead, bw=UW))
                for i, ln in enumerate(ulines):
                    if i == 0:
                        body.append(self.box_row(C_USER, C_BOLD + C_USER + "❯" + C_RESET + " " + C_TEXT + ln + C_RESET, W, lead=lead, bw=UW))
                    else:
                        body.append(self.box_row(C_USER, C_TEXT + ln + C_RESET, W, lead=lead, bw=UW))
                body.append(self.box_bottom(C_USER, W, lead=lead, bw=UW))
                body.append("")
            else:
                alines = self.assistant_block(msg.get("model") or self.model, text, W,
                                              think=msg.get("think"), reasoning=msg.get("reasoning", ""),
                                              time_prefix=time_str, msg_idx=mi + 1)
                # v4: card entrance — last reply grows in
                if self._entrance and self._entrance[0] == mi:
                    alines = alines[:max(1, int(len(alines) * self._entrance[1]))]
                body += alines
                body.append("")
        if self.timing_panel:
            # v4: central timing table
            hist = self._render_hist[-10:]
            avg_render = sum(hist) / max(1, len(hist))
            avg_speed = sum(self._stream_speeds[-5:]) / max(1, len(self._stream_speeds[-5:]))
            up = time.time() - self._boot_t
            body += self.card(C_ACC, C_BOLD + "⏱ Timing — Ctrl+T" + C_RESET, W)
            for rtext in (f"  session uptime: {int(up // 60)}m {int(up % 60)}s",
                          f"  avg render: {avg_render:.1f}ms",
                          f"  stream avg: {avg_speed:.0f} tok/s",
                          f"  last reply: {self._last_reply_dt}",
                          f"  tokens: {SESSION_TOKENS['in'] + SESSION_TOKENS['out']}",
                          f"  animations: {'ON (Ctrl+A off)' if self.anim else 'OFF (Ctrl+A on)'}"):
                body.append(self.card_row(C_MUTED, rtext, W))
        if self.streaming:
            elapsed = time.time() - self._stream_start
            speed = self._stream_tokens / elapsed if elapsed > 0 and self._stream_tokens > 0 else 0
            if self.pending:
                body_only = self._body_only(self.pending)
                plines = wrap_text(body_only, max(20, W - 6))
                if plines:
                    while plines and plines[-1] == "":
                        plines.pop()
                    for i, ln in enumerate(plines):
                        if i == len(plines) - 1:
                            body.append("    " + C_TEXT + ln + C_RESET + C_ACC + "▍" + C_RESET)
                        else:
                            body.append("    " + C_TEXT + ln + C_RESET)
                if speed > 0:
                    body.append("    " + C_MUTED + f"~{self._stream_tokens} tok · {speed:.0f} tok/s" + C_RESET)
            else:
                body.append("    " + C_MUTED + self.spin + " Thinking…" + C_RESET)
        for label, text in self.notices:
            body += self.notice_card(label, text, W)
        for i, n in enumerate(self.notes):
            if isinstance(n, dict):
                body += self.diff_card(n, W)
            else:
                # v4: auto-approve ✓ pop — last note line flashes bold 0.5s
                if (self._approve_pop and i == len(self.notes) - 1
                        and time.time() - self._approve_pop < 0.5
                        and n.strip().startswith("✓")):
                    n = C_BOLD + n + C_RESET
                for ln in wrap_text(short(n, W - 6), W - 6):
                    body.append("  " + C_DIM + ln + C_RESET)
        # v4.5: tool work progress — box er niche ■■■■■⬝⬝⬝ animates jokhon AI kaj korbe
        if getattr(self, "_tool_progress", None) and time.time() - self._tool_progress[2] > 0.15:
            name, arg, _ = self._tool_progress
            n_seg, w = 12, 5
            if self.anim:
                pos = int(time.time() * 6) % n_seg
                segs = "".join("█" if ((i - pos) % n_seg) < w else "⬝" for i in range(n_seg))
            else:
                segs = "█" * w + "⬝" * (n_seg - w)
            body.append("    " + C_ACC + segs + C_RESET + "  " + C_MUTED
                        + name + ": " + truncate(arg, 40) + C_RESET)
        pop_all = []
        if self.popup:
            kind, key = self.popup
            if kind == "perm":
                opts = ["Allow once", "Allow session", "Always", "Reject"]
                opt_colors = [C_GOOD, C_ACC, C_WARN, C_ERRC]
            else:
                opts = ["Yes", "No"]
                opt_colors = [C_GOOD, C_ERRC]
            parts = []
            for i, o in enumerate(opts):
                if i == self.popup_idx:
                    # v4: BRAND selection bg
                    parts.append(C_BOLD + "\x1b[48;5;141m\x1b[38;5;0m " + o + " " + C_RESET)
                else:
                    parts.append(opt_colors[i] + o + C_RESET)
            pop_all += self.card(C_ERRC, C_WARN + "⚠ Permission required" + C_RESET, W)
            pop_all += self.card(C_ERRC, C_DIM + " - Access " + C_BOLD + C_TEXT + key + C_RESET, W)
            if kind == "perm" and "/" in key:
                pattern = key.rsplit("/", 1)[0] + "/*"
                pop_all += self.card(C_DIM, C_DIM + "  Patterns: " + C_TEXT + pattern + C_RESET, W)
            hint = "   ←/→ select · enter confirm" if kind == "perm" else "   Enter confirm · Esc cancel"
            pop_all += self.card(C_ERRC, "  ".join(parts) + hint, W)
        if pop_all:
            if self._popup_birth > 0:
                # v4: birth anim — popup grows in line by line
                body += pop_all[:max(1, int(len(pop_all) * self._popup_birth))]
            else:
                body += pop_all
        elif self.palette:
            body += self.palette_card(W)
        elif self.sess_pick:
            body += self.session_pick_card(W)
        elif self.model_pick:
            body += self.model_pick_card(W)
        elif self.cmd_pick:
            body += self.cmd_pick_card(W)
        body_max = max(1, H - 5)
        if len(body) > body_max:
            max_scroll = len(body) - body_max
            self.scroll_off = max(0, min(self.scroll_off, max_scroll))
            start = len(body) - body_max - self.scroll_off
            body = body[start:len(body) - self.scroll_off]
            # v4: scroll indicator — ↑ more above (text gone), ↓ bare marker only
            if self.scroll_off > 0:
                body[0] = "  " + C_MUTED + "↑ " + str(self.scroll_off) + " more · PgUp" + C_RESET
            if self.scroll_off < max_scroll:
                body[-1] = "  " + C_MUTED + "↓" + C_RESET
        else:
            self.scroll_off = 0
            body += [""] * (body_max - len(body))
        if pop_all and body:
            # v4: backdrop dim — background content dimmed behind popup
            body[0] = "\x1b[2m" + body[0]
            body[-1] += "\x1b[22m"
        if self.streaming and self._esc_pending:
            body.append("  " + C_WARN + "⚠ ESC abar chaple interrupt hobe (Ctrl+C = direct)" + C_RESET)
        lines += body
        lines += self.prompt_box(W)
        lines.append(self.footer_line())
        return lines[:H]

    def redraw(self):
        if self.plain:
            return
        _r0 = time.time()
        # v4: notice auto-dismiss after 3s
        if self.notices and time.time() - self._notice_t > 3.0:
            self.notices = []
        W, H = term_size()
        self.adaptive(W, H)
        if self.route == "home":
            frame = self.frame_home(W, H)
        else:
            frame = self.frame_chat(W, H)
        while len(frame) < H:
            frame.append("")
        out = []
        for i, line in enumerate(frame[:H]):
            out.append("\x1b[" + str(i + 1) + ";1H\x1b[K" + safeify(line))
        out.append("\x1b[" + str(H) + ";1H")
        if self._route_fade and time.time() - self._route_fade < 0.1:
            out = ["\x1b[2m"] + out + ["\x1b[22m"]
        with self._draw_lock:
            sys.stdout.write("".join(out))
            sys.stdout.flush()
        # v4: render timing histogram (for timing table)
        self._render_hist.append((time.time() - _r0) * 1000)
        if len(self._render_hist) > 20:
            self._render_hist.pop(0)

    def adaptive(self, W, H):
        """v4 adaptive layout — portrait/landscape state (spec section 15)."""
        self.compact = W <= 50          # compact header mode
        self.tiny_input = W <= 45       # single-row input, no border
        self.tiny_rows = H <= 20        # no-logo home, always-collapsed sections
        self.wide = W >= 70             # full header mode

    def fmt_tok(self, n):
        if n >= 1_000_000:
            return f"~{n / 1e6:.1f}M"
        if n >= 1000:
            return f"~{n / 1e3:.1f}K"
        return f"~{n}"

    def short_model(self):
        parts = self.model.split("-")
        if len(parts) >= 2 and len(parts[0]) >= 2:
            ab = {"deepseek": "ds", "nemotron": "nt", "north": "no", "laguna": "lg"}.get(parts[0], parts[0][:2])
            return ab + "-" + parts[1][:4]
        return self.model[:6]

    # ---------- input ----------

    def input_loop(self):
        while not self.quitting:
            try:
                if self.resized:
                    self.resized = False
                    self.redraw()
                k = raw_key()
                if self.resized:
                    self.resized = False
                if self.route == "home":
                    self.key_home(k)
                else:
                    self.key_chat(k)
            except Exception as e:
                self.notice("ERR", "Unexpected error: " + str(e))
                self.redraw()

    def key_home(self, k):
        if self.palette:
            self.key_palette(k)
            return
        if self.model_pick:
            self.key_model_pick(k)
            return
        items = [("__new__",)] + [(n,) for n, _, _, _ in session_list()]
        if k == "UP":
            self.cur = max(0, self.cur - 1)
            self.redraw()
        elif k == "DOWN":
            self.cur = min(len(items) - 1, self.cur + 1)
            self.redraw()
        elif k == "ENTER":
            self.open_session(items[self.cur][0])
        elif k in ("CTRL-C", "q", "Q"):
            self.quitting = True
        elif k == "CTRL-P":
            self.palette = True
            self.palette_idx = 0
            self.redraw()
        elif k == "TAB":
            self.toggle_mode()
        elif k == "ESC":
            self.redraw()
        elif k.isprintable():
            self.buf = k
            if k == "/":
                self.cmd_pick = True
                self.cmd_idx = 0
            self.open_session("__new__")
        else:
            self.redraw()

    def key_palette(self, k):
        shown = [c for c in PALETTE_CMDS if self.palette_filter in c]
        if k == "UP":
            self._palette_prev = self.palette_idx
            self.palette_idx = max(0, self.palette_idx - 1)
            self._palette_t = time.time()
        elif k == "DOWN":
            self._palette_prev = self.palette_idx
            self.palette_idx = min(len(shown) - 1, self.palette_idx + 1)
            self._palette_t = time.time()
        elif k == "ENTER":
            cmd = shown[self.palette_idx]
            self.palette = False
            self.palette_filter = ""
            self._palette_t = 0.0
            if cmd in NEEDS_ARG:
                self.buf = cmd + " "
            else:
                self.run_command(cmd)
            self.redraw()
            return
        elif k == "BACK":
            self.palette_filter = self.palette_filter[:-1]
            self.palette_idx = 0
        elif k.isprintable():
            # v4: filter-as-you-type
            self.palette_filter += k
            self.palette_idx = 0
        elif k in ("ESC", "CTRL-C", "CTRL-P"):
            self.palette = False
            self.palette_filter = ""
            self._palette_t = 0.0
        self.redraw()

    def key_cmd_pick(self, k):
        items = ["AUTO"] + [c for c in COMMAND_LIST if c.startswith(self.buf)]
        if k == "UP":
            self.cmd_idx = max(0, self.cmd_idx - 1)
        elif k == "DOWN":
            self.cmd_idx = min(len(items) - 1, self.cmd_idx + 1)
        elif k == "ENTER":
            pick = items[self.cmd_idx]
            self.cmd_pick = False
            if pick == "AUTO":
                self.auto_approve = True
                self.buf = ""
                self.notice("SYS", "Auto-approve ON — this session e kono permission ask korbe na")
            elif pick in NEEDS_ARG:
                self.buf = pick + " "
            else:
                self.buf = ""
                self.run_command(pick)
            self.redraw()
            return
        elif k in ("ESC", "CTRL-C"):
            self.cmd_pick = False
        elif k == "BACK":
            self.buf = self.buf[:-1]
            if not self.buf.startswith("/"):
                self.cmd_pick = False
        elif k.isprintable():
            self.buf += k
        self.redraw()

    def open_session(self, name):
        if name == "__new__":
            if len(self.messages) > 1:
                save_session("last", self.messages)
            self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            SESSION_TOKENS["in"] = SESSION_TOKENS["out"] = 0
            self.session_perm = {"cmd": set(), "file": set()}
            self.loaded_name = None
            self.notices = []
            self.notes = []
            self.status = "ready"
        else:
            loaded = load_session(name)
            if loaded and loaded[0].get("role") == "system":
                self.messages = loaded
                self.loaded_name = name
                self.notices = [("SYS", f"Loaded: {name} ({len(loaded) - 1} messages)")]
            else:
                self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                self.loaded_name = None
                self.session_perm = {"cmd": set(), "file": set()}
                self.notes = []
                self.notices = [("SYS", "Session paoa gelo na: " + name)]
        if self.route != "chat":
            self.route = "chat"
            # v4: home->chat fade transition (typing e bar-bar na, sudhu first)
            self._route_transition()
        else:
            self.route = "chat"
            self.redraw()
        W, _ = term_size()
        self.anim_header(self.loaded_name or ("new chat" if len(self.messages) <= 1 else "chat"), W)

    def key_chat(self, k):
        self._cursor_on = True
        self._last_key = 0.0
        if self.palette:
            self.key_palette(k)
            return
        if self.sess_pick:
            self.key_sess_pick(k)
            return
        if self.model_pick:
            self.key_model_pick(k)
            return
        if self.cmd_pick:
            self.key_cmd_pick(k)
            return
        if k in ("WHEEL_UP", "WHEEL_DOWN", "PGUP", "PGDN"):
            step = 4 if k in ("WHEEL_UP", "WHEEL_DOWN") else 5
            if k in ("WHEEL_UP", "PGUP"):
                self.scroll_off += step
            else:
                self.scroll_off -= step
            self.scroll_off = max(0, self.scroll_off)
            self.redraw()
            return
        self.scroll_off = 0
        if k == "ENTER":
            if self.renaming:
                self.commit_rename()
                return
            text = self.buf
            if text.strip():
                # v4: send suck-in — text collapses into the prompt (150ms)
                if self.anim:
                    for f in range(1, 7):
                        self._suck = f / 6
                        self.redraw()
                        time.sleep(0.025)
                    self._suck = 0.0
                self.hist.append(text)
                self.hidx = len(self.hist)
                self.buf = ""
                self.send(text)
            elif self.sec_focus:
                if self.sec_focus in self.expand_diffs:
                    self.expand_diffs.discard(self.sec_focus)
                    self._sec_toggle_anim(self.sec_focus, False)
                else:
                    self.expand_diffs.add(self.sec_focus)
                    self._sec_toggle_anim(self.sec_focus, True)
            elif self.toggle_diff_expand():
                self.redraw()
            else:
                self.redraw()
        elif k == "CTRL-D":
            self.delete_session()
        elif k == "CTRL-R":
            self.renaming = True
            self.buf = self.loaded_name or ""
            self.redraw()
        elif k == "CTRL-P":
            self.palette = True
            self.palette_idx = 0
            self.redraw()
        elif k == "CTRL-E":
            self.auto_approve = not self.auto_approve
            if self.auto_approve:
                self.notice("SYS", "Auto-approve ON — all permissions auto-allow")
            else:
                self.notice("SYS", "Auto-approve OFF — permissions will ask again")
            self.redraw()
        elif k == "CTRL-Z":
            self.undo_last()
        elif k == "CTRL-T":
            self.timing_panel = not self.timing_panel
            self.redraw()
        elif k == "CTRL-A":
            self.anim = not self.anim
            self.notice("SYS", "Animations " + ("ON" if self.anim else "OFF") + " (Ctrl+A)")
        elif k == "ESC":
            if self.renaming:
                self.renaming = False
                self.buf = ""
                self.redraw()
                return
            # v4: ESC = collapse all sections (first), home (second)
            sec_keys = [k2 for k2 in self.expand_diffs if k2.startswith("sec:")]
            if sec_keys:
                for k2 in sec_keys:
                    self.expand_diffs.discard(k2)
                self.sec_focus = None
                self.redraw()
                return
            if len(self.messages) > 1:
                save_session("last", self.messages)
            self.buf = ""
            self.notices = []
            self.notes = []
            self.route = "home"
            self.cur = 0
            # v4: chat->home fade transition
            self._route_transition()
        elif k == "CTRL-C":
            self.quitting = True
        elif k == "BACK":
            self.buf = self.buf[:-1]
            self.redraw()
        elif k == "TAB":
            if self.buf.startswith("/"):
                self.complete()
            elif self._sec_keys:
                # v4: Tab = jump between sections (focus indicator)
                if self.sec_focus is None or self.sec_focus not in self._sec_keys:
                    self.sec_focus = self._sec_keys[0]
                else:
                    idx = self._sec_keys.index(self.sec_focus)
                    self.sec_focus = self._sec_keys[(idx + 1) % len(self._sec_keys)]
                self.redraw()
            else:
                self.toggle_mode()
        elif k == "UP":
            if self.hist:
                self.hidx = max(0, self.hidx - 1)
                self.buf = self.hist[self.hidx]
            self.redraw()
        elif k == "DOWN":
            self.hidx = min(len(self.hist), self.hidx + 1)
            self.buf = self.hist[self.hidx] if self.hidx < len(self.hist) else ""
            self.redraw()
        elif k in ("RIGHT", "LEFT", ""):
            self.redraw()
        elif k.isprintable():
            self.buf += k
            if self.buf.startswith("/") and not self.renaming:
                self.cmd_pick = True
                self.cmd_idx = 0
            self.redraw()
        else:
            self.redraw()

    def complete(self):
        if self.buf.startswith("/"):
            matches = [c for c in COMMAND_LIST if c.startswith(self.buf)]
        elif self.buf:
            matches = [c for c in COMMAND_LIST if c.startswith(self.buf)]
        else:
            matches = []
        if not matches:
            self._comp = -1
            return
        self._comp = (self._comp + 1) % len(matches)
        self.buf = matches[self._comp]
        self.redraw()

    def toggle_mode(self):
        self.mode = "plan" if self.mode == "build" else "build"
        self._mode_flash = time.time()
        if self.mode == "plan":
            self.notice("MODE", "Plan mode ON — AI shudhu analyze/plan korbe, kono file/command change korbe na. Build mode e firtte Tab.")
        else:
            self.notice("MODE", "Build mode ON — AI kaj korte parbe (files, commands).")
        self.redraw()

    # ---------- session delete / rename ----------

    def confirm_popup(self, prompt):
        """Yes/No confirm popup. Returns True on Yes."""
        self.popup = ("confirm", prompt)
        self.popup_idx = 0
        self._popup_birth_anim()
        try:
            while True:
                self.redraw()
                k = raw_key()
                if k in ("RIGHT", "LEFT"):
                    self.popup_idx = (self.popup_idx + 1) % 2
                elif k in ("q", "Q", "CTRL-C", "ESC"):
                    return False
                elif k in ("ENTER", ""):
                    break
        finally:
            self.popup = None
        return self.popup_idx == 0

    def delete_session(self):
        if not self.loaded_name:
            self.notice("SYS", "Kono saved session nai — Ctrl+D kichu korbe na.")
            self.redraw()
            return
        name = self.loaded_name
        if not self.confirm_popup("Delete session '" + name + "'?"):
            self.notice("SYS", "Delete cancelled.")
            self.redraw()
            return
        try:
            os.remove(os.path.join(CHATS_DIR, name + ".json"))
        except OSError:
            pass
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        SESSION_TOKENS["in"] = SESSION_TOKENS["out"] = 0
        self.session_perm = {"cmd": set(), "file": set()}
        self.loaded_name = None
        self.notices = []
        self.notes = []
        self.buf = ""
        self.status = "ready"
        self.notice("SYS", "Deleted: " + name)
        self.redraw()

    def commit_rename(self):
        name = self.buf.strip()
        self.renaming = False
        self.buf = ""
        if not name or "/" in name or "\\" in name or name in (".", ".."):
            self.notice("SYS", "Invalid name: " + (name or "(khali)"))
            self.redraw()
            return
        old = self.loaded_name
        if old and old != name:
            src = os.path.join(CHATS_DIR, old + ".json")
            dst = os.path.join(CHATS_DIR, name + ".json")
            if not os.path.exists(src):
                self.notice("SYS", "Session nai: " + old)
            elif os.path.exists(dst):
                self.notice("SYS", "Name ta already ache: " + name)
            else:
                os.rename(src, dst)
                self.loaded_name = name
                self.notice("SYS", "Renamed: " + old + " → " + name)
        elif not old:
            save_session(name, self.messages)
            self.loaded_name = name
            self.notice("SYS", "Saved as: " + name)
        self.redraw()

    # ---------- commands ----------

    def run_command(self, text):
        user_input = text.strip()
        if user_input in ("/exit", "/quit"):
            self.quitting = True
            return True
        if user_input == "/help":
            self.notice("HELP", help_text())
            return True
        if user_input in ("/mode", "/plan", "/build"):
            self.mode = "plan" if user_input == "/plan" or (user_input == "/mode" and self.mode == "build") else "build"
            if self.mode == "plan":
                self.notice("MODE", "Plan mode ON — AI shudhu analyze/plan korbe, kono file/command change korbe na. Build mode e firtte Tab.")
            else:
                self.notice("MODE", "Build mode ON — AI kaj korte parbe (files, commands).")
            return True
        if user_input == "/new":
            self.open_session("__new__")
            return True
        if user_input == "/undo":
            self.undo_last()
            return True
        if user_input == "/stats":
            tot = SESSION_TOKENS["in"] + SESSION_TOKENS["out"]
            self.notice("STATS", f"input: {SESSION_TOKENS['in']} tok | output: {SESSION_TOKENS['out']} tok | total: {tot} (cost $0)")
            return True
        if user_input == "/models":
            if self.plain:
                self.notice("MODELS", list_free())
            else:
                self.model_pick = FREE_MODELS
                self.model_idx = 0
            return True
        if user_input.startswith("/model "):
            new_model = user_input.split(None, 1)[1].strip()
            self.cfg["model"] = new_model
            save_config(self.cfg)
            self.model = new_model
            self.notice("SYS", "Model changed: " + self.model)
            return True
        if user_input == "/perm":
            self.notice("PERM", show_perms(self.cfg))
            return True
        if user_input.startswith("/perm "):
            parts = user_input.split()
            try:
                if len(parts) == 3 and parts[2] in ("ask", "always", "deny"):
                    self.cfg.setdefault("perm", {})["default_" + parts[1]] = parts[2]
                    save_config(self.cfg)
                    self.notice("PERM", f"default {parts[1]}: {parts[2]}")
                elif len(parts) == 5 and parts[2] == "add" and parts[4] in ("ask", "always", "deny"):
                    self.cfg.setdefault("perm", {}).setdefault(parts[1], {})[parts[3]] = parts[4]
                    save_config(self.cfg)
                    self.notice("PERM", f"rule: {parts[1]} '{parts[3]}' -> {parts[4]}")
                elif parts[1] == "reset":
                    self.cfg["perm"] = {}
                    save_config(self.cfg)
                    self.notice("PERM", "All permission rules reset.")
                else:
                    self.notice("PERM", show_perms(self.cfg))
            except Exception:
                self.notice("PERM", show_perms(self.cfg))
            return True
        if user_input == "/sessions":
            lst = session_list()
            if not lst:
                self.notice("SESSIONS", "Kono saved session nai.")
                return True
            if self.plain:
                txt = "Saved sessions: " + (", ".join(f"{n} ({c} msgs)" for n, _, c, _ in lst))
                self.notice("SESSIONS", txt + "\nLoad: /load <name> | Delete: /rm <name>")
            else:
                self.sess_pick = lst
                self.sess_idx = 0
                self.palette = False
            return True
        if user_input.startswith("/save"):
            name = user_input.split(None, 1)[1].strip() if len(user_input.split(None, 1)) > 1 else time.strftime("chat-%Y%m%d-%H%M%S")
            if len(self.messages) > 1:
                path = save_session(name, self.messages)
                self.loaded_name = name
                self.notice("SYS", "Saved: " + path)
            else:
                self.notice("SYS", "Chat khali, save korar moto kichu nai.")
            return True
        if user_input.startswith("/load "):
            name = user_input.split(None, 1)[1].strip()
            loaded = load_session(name)
            if loaded and loaded[0].get("role") == "system":
                self.messages = loaded
                self.loaded_name = name
                self.notice("SYS", f"Loaded: {name} ({len(loaded) - 1} messages)")
            else:
                self.notice("SYS", "Session paoa gelo na: " + name)
            return True
        if user_input.startswith("/rm "):
            name = user_input.split(None, 1)[1].strip()
            try:
                os.remove(os.path.join(CHATS_DIR, name + ".json"))
                self.notice("SYS", "Deleted: " + name)
            except OSError:
                self.notice("SYS", "Session nai: " + name)
            return True
        if user_input.startswith("/"):
            self.notice("SYS", "Unknown command: " + user_input + " (type /help)")
            return True
        return False

    def undo_last(self):
        """Revert the last sent message (remove it + AI reply, restore buffer)."""
        if self.streaming or not self._undo_msg:
            self.notice("SYS", "Kichu revert korar nei — message pathaobar por Ctrl+Z")
            return
        u = self._undo_msg
        self.messages = self.messages[: u["idx"]]
        self.buf = u["text"]
        self.notices = []
        self.notes = []
        self._undo_msg = None
        if u["name"] and len(self.messages) > 1:
            save_session(u["name"], self.messages)
        self.notice("SYS", "↶ Message revert — abar edit kore pathate paren")
        self.redraw()

    # ---------- chat flow ----------

    def send(self, text):
        if self.run_command(text):
            self.redraw()
            return
        self.notices = []
        self.notes = []
        self._undo_msg = {"idx": len(self.messages), "text": text, "name": self.loaded_name}
        self.messages.append({"role": "user", "content": text, "time": time.time()})
        self.status = self.model
        self.redraw()
        try:
            self.run_turn()
        except Exception as e:
            self.notice("ERR", "Unexpected error: " + str(e))
            self.redraw()

    def stream_reply(self):
        parts = []
        done = threading.Event()
        result = {}
        msgs = self.messages
        if self.mode == "plan":
            msgs = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + PLAN_PROMPT}] + list(self.messages[1:])

        def on_chunk(kind, text):
            parts.append((kind, text))
            if kind == "content":
                if self._think_secs is None:
                    self._think_secs = time.time() - self._think_start
                self._acc += text
                self._stream_tokens = est_tokens(self._acc)

        def worker():
            result["err"], result["model"] = call_chat(msgs, self.model, self.api_key, on_chunk)
            done.set()

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        self.streaming = True
        self.cancel = False
        self._acc = ""
        self._think_start = time.time()
        self._think_secs = None
        self._revealed = 0
        self._stream_start = time.time()
        self._stream_tokens = 0
        self._esc_pending = False
        self.pending = ""
        typed = []
        self.redraw()
        try:
            while t.is_alive() or not done.is_set():
                r, _, _ = select.select([sys.stdin], [], [], 0.15)
                if r:
                    k = raw_key()
                    if k == "CTRL-C":
                        self.cancel = True
                        break
                    elif k == "ESC":
                        if not self._esc_pending:
                            self._esc_pending = True
                            self.notice("SYS", "ESC pressed again to interrupt")
                            self.redraw()
                        else:
                            self.cancel = True
                            break
                    elif k in ("CTRL-P",):
                        self.cancel = True
                        break
                    elif k == "BACK":
                        if typed:
                            typed.pop()
                            self.buf = "".join(typed)
                            self.redraw()
                    elif k and len(k) == 1 and k.isprintable():
                        typed.append(k)
                        self.buf = "".join(typed)
                        self.redraw()
        except KeyboardInterrupt:
            self.cancel = True
        finally:
            self.streaming = False
            self.pending = self._acc
            self._acc = ""
            self._revealed = 0
            self.reasoning = ""
            if typed and not self.cancel:
                self.buf = "".join(typed)
            self.redraw()
            # v4: model meta fade-in + bottom seal — kono sections na thakleo meta line late ashe
            if not self.cancel and not result.get("err"):
                time.sleep(0.06)
                self.redraw()
        err = result.get("err")
        used_model = result.get("model")
        if self.cancel:
            return "", "", "cancelled", used_model or self.model
        if err:
            return "", "", err, used_model
        reasoning = "".join(x for kind, x in parts if kind == "reasoning")
        content = "".join(x for kind, x in parts if kind == "content")
        return content, reasoning, None, used_model

    def run_turn(self):
        cmd_log = []
        self._last_tools = []
        exec_count = 0
        t_turn0 = time.time()
        for round_no in range(MAX_TOOL_ROUNDS):
            if getattr(self, "cancel", False):
                # v4.5: Esc during tool work — turn ekhanei shesh (stream_reply cancel reset kore dibe na)
                self.notice("SYS", "cancelled")
                self.status = "cancelled"
                self.redraw()
                return
            t0 = time.time()
            content, reasoning, err, used_model = self.stream_reply()
            dt = fmt_duration(time.time() - t0)
            if used_model and used_model != self.model:
                self.model = used_model
            if err:
                if err == "cancelled":
                    self.notice("SYS", "cancelled")
                    self.status = "cancelled"
                else:
                    if self.messages and self.messages[-1]["role"] == "user":
                        self.messages.pop()
                    self.notice("ERR", err)
                    self.status = "error"
                self.redraw()
                return
            SESSION_TOKENS["in"] += est_tokens(reasoning + content)
            SESSION_TOKENS["out"] += est_tokens(content)
            tools = parse_tools(content)
            # v4.5 storage fix: AI er bhul path (~, /sdcard, relative) auto-correct kore /storage/emulated/0
            tools = [sanitize_tool_args(n, a, c) for n, a, c in tools]
            if not tools and not content.strip():
                # v4: empty reply guard — kono content nei, loop e jamabo na
                if self.messages and self.messages[-1].get("role") == "assistant":
                    self.messages.pop()
                self.notice("SYS", "AI kichu respond koreni — abar try korun")
                self.status = "empty"
                self.redraw()
                return
            self.messages.append({"role": "assistant", "content": content, "time": time.time(), "model": used_model})
            if getattr(self, "_think_secs", None) is not None:
                self.messages[-1]["think"] = self._think_secs
            if reasoning.strip():
                self.messages[-1]["reasoning"] = reasoning
            if not tools:
                if cmd_log:
                    self.messages[-1]["content"] += ("\n\n**Summary:**\n▸ Commands Executed (collapsed)\n"
                                                     + "\n".join(cmd_log))
                self.status = f"{used_model} | {dt} | tok ~{SESSION_TOKENS['in'] + SESSION_TOKENS['out']}"
                self._last_reply_dt = dt
                spd = est_tokens(content) / max(0.1, time.time() - t0)
                self._stream_speeds.append(spd)
                if len(self._stream_speeds) > 10:
                    self._stream_speeds.pop(0)
                self.redraw()
                # v4: card entrance — final reply grows in 8 frames x 30ms
                if self.anim:
                    mi = len(self.messages) - 2
                    for f in range(1, 9):
                        self._entrance = (mi, f / 8)
                        self.redraw()
                        time.sleep(0.03)
                    self._entrance = None
                    self.redraw()
                break
            # v4.5: turn time budget — AI stuck thakle turn jome jabe na
            if time.time() - t_turn0 > TURN_TIME_BUDGET:
                self.messages[-1]["content"] += "\n\n⛔ Turn time budget exceeded — loop stop (auto)"
                self.notice("SYS", "Turn time budget exceeded — loop stop")
                self.status = "loop-stopped"
                self.redraw()
                return
            results = []
            # v4: repeated-call guard — same tool+arg 3 bar mane AI loop e, stop
            if not hasattr(self, "_last_tools"):
                self._last_tools = []
            sig = []
            for n, a, c in tools:
                if n in ("run", "ls"):
                    sig.append((n, (c or a.get("path", ""))[:60]))
                else:
                    sig.append((n, a.get("path", "")))
            self._last_tools.append(sig)
            if len(self._last_tools) > 4:
                self._last_tools.pop(0)
            if len(self._last_tools) >= 3 and self._last_tools[-1] == self._last_tools[-2] == self._last_tools[-3]:
                self.messages[-1]["content"] += "\n\n⛔ AI loop e feshe geche (same tool 3 bar) — break"
                self.notes.append(C_RED + "⛔ AI loop e feshe geche (same tool 3 bar) — break" + C_RESET)
                self.status = "loop-stopped"
                self.redraw()
                return
            for name, attrs, tcontent in tools:
                if self.mode == "plan" and name in ("write", "run"):
                    self.notes.append(C_RED + "⛔ plan mode: " + name + " skip — shudhu plan/analyze" + C_RESET)
                    results.append(f"[tool {name}: plan mode e nishedh — user shudhu plan/analysis chaiche, kono change koro na]")
                    self.redraw()
                    continue
                if name == "write":
                    arg = attrs.get("path", "").strip()
                    tool_content = tcontent
                else:
                    arg = (tcontent or attrs.get("path") or "").strip()
                    tool_content = arg
                note_idx = len(self.notes)
                exec_count += 1
                if exec_count > MAX_TOOL_EXECS:
                    self.messages[-1]["content"] += "\n\n⛔ Tool call cap reached — loop stop (auto)"
                    self.notice("SYS", f"Max {MAX_TOOL_EXECS} tool calls — loop stop")
                    self.status = "loop-stopped"
                    self.redraw()
                    return
                self.notes.append(C_YELLOW + "⚙ " + name + ": " + truncate(arg, 50) + C_RESET)
                self.redraw()
                t_tool = time.time()
                self._tool_progress = (name, arg, t_tool)
                try:
                    res, diff_info = exec_tool(self.cfg, name, arg, tool_content, self.session_perm, attrs, auto_approve=self.auto_approve)
                finally:
                    self._tool_progress = None
                dur = time.time() - t_tool
                results.append(f"[tool {name}: {res}]")
                code_m = re.search(r"exit=(-?\d+)", res)
                ok = not code_m or code_m.group(1) == "0"
                inner = res.split("]\n", 1)[1] if "]\n" in res else ""
                first_line = inner.split("[/Tool", 1)[0].strip().split("\n", 1)[0][:60] if inner.strip() else ""
                if ok:
                    self.notes[note_idx] = C_GREEN + "✓ " + name + ": " + truncate(arg, 50) + C_RESET
                else:
                    self.notes[note_idx] = (C_RED + "✗ " + name + ": " + truncate(arg, 50)
                                            + (" — " + first_line if first_line else "") + C_RESET)
                if diff_info:
                    self.notes[note_idx] = diff_info
                icon = "✓" if ok else "✗"
                cmd_log.append(f"→ {name}: {short(arg, 40)} {icon} {fmt_duration(dur)}")
                if ok and self.auto_approve:
                    self._approve_pop = time.time()
                if round_no == MAX_TOOL_ROUNDS - 1:
                    results.append("(max tool rounds reached, ekhane shesh koro)")
                self.redraw()
            results_txt = "\n".join(r for r in results if r.strip())
            if results and all(("denied" in r or "nishedh" in r) for r in results):
                # sob tool deny/skip — AI ar jiggesh korte thakbe na
                self.messages[-1]["content"] += "\n\n⛔ Sob tool deny/skip hoyeche — loop stop"
                self.notice("SYS", "Sob tool deny/skip — loop stop")
                self.status = "loop-stopped"
                self.redraw()
                return
            if not results_txt.strip():
                # v4: tool results khaali — empty user message append korbo na
                self.notice("SYS", "Tool results khaali chilo — loop stop")
                self.status = "done"
                self.redraw()
                return
            self.messages.append({"role": "user", "content": results_txt, "time": time.time()})
        else:
            self.notice("SYS", "Max tool rounds — /new diye fresh koro.")
        if self.loaded_name and len(self.messages) > 1:
            save_session(self.loaded_name, self.messages)

    # ---------- permission popup ----------

    def perm_popup(self, kind, key):
        self.popup = (kind, key)
        self.popup_idx = 0
        self._popup_birth_anim()
        try:
            while True:
                self.redraw()
                k = raw_key()
                if k == "RIGHT":
                    self.popup_idx = (self.popup_idx + 1) % 4
                elif k == "LEFT":
                    self.popup_idx = (self.popup_idx - 1) % 4
                elif k in ("1", "2", "3", "4"):
                    self.popup_idx = int(k) - 1
                    break
                elif k in ("q", "Q", "CTRL-C", "ESC"):
                    return "deny_once"
                elif k in ("ENTER", ""):
                    break
        finally:
            self.popup = None
            self.redraw()
        return ("allow_once", "allow_session", "always", "deny_once")[self.popup_idx]

    # ---------- run ----------

    def run(self):
        if self.plain:
            self.run_plain()
            return
        self.enter()
        try:
            self.redraw()
            self.input_loop()
        finally:
            if len(self.messages) > 1:
                save_session("last", self.messages)
            self.exit()
        print(C_DIM + "Bye!" + C_RESET)

    def run_plain(self):
        print(C_BOLD + C_CYAN + "VOXEL AI v3.8.3" + C_RESET + "  (" + self.model + ")  —  /help")
        while not self.quitting:
            try:
                text = input("❯ ").strip()
            except (KeyboardInterrupt, EOFError):
                print()
                break
            if not text:
                continue
            if text in ("/exit", "/quit"):
                break
            self.send(text)
            self.notes = []


def main():
    cfg = load_config()
    args = sys.argv[1:]
    if args and args[0] == "--key":
        if len(args) < 2:
            print("Usage: python3 bangbot.py --key <YOUR_API_KEY>")
            return
        cfg["api_key"] = args[1]
        save_config(cfg)
        print(C_GREEN + "API key saved to ~/.bangbot/config.json" + C_RESET)
        return

    if args and args[0] == "--models":
        try:
            ids = fetch_models(cfg.get("api_key") or None)
            for m in ids:
                print("  " + m)
        except Exception as e:
            print(C_RED + "Fetch fail: " + str(e) + C_RESET)
        return

    global ui
    ui = UI(cfg)
    ui.run()


if __name__ == "__main__":
    main()
