#!/usr/bin/env python3
"""
VOXEL AI — an opencode-style AI agent CLI, built for Termux.

Layout, command set, session model and keybinds follow opencode's TUI as
closely as a stdlib-only Python terminal app can. Assistant prose renders at
full brightness; tool/command execution renders dim + lowercase so the reply
is always what your eye lands on.

    python3 voxel.py              start the TUI
    python3 voxel.py --plain      no-TUI fallback (pipes, dumb terminals)
    python3 voxel.py --safe-fonts ASCII glyphs for broken unicode fonts
"""

import codecs
import html as html_mod
import json
import os
import re
import select
import shutil
import signal
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from types import SimpleNamespace

try:
    import termios
    import tty
except ImportError:  # non-posix
    termios = tty = None

VERSION = "4.0.1"

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, ".voxel")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
SESSIONS_DIR = os.path.join(CONFIG_DIR, "sessions")
LEGACY_DIR = os.path.join(HOME, ".bangbot")

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

MAX_TOOL_ROUNDS = 1000   # unlimited rounds per turn (tool -> result -> tool ...)
MAX_TOOL_EXECS = 10000   # no hard cap on tool executions per turn
TURN_TIME_BUDGET = 86400 # 24h before a turn is force-stopped
CMD_TIMEOUT = 3600       # 1h per command
OUT_LIMIT = 1000000      # never truncate tool output
CONTEXT_LIMIT = 2000000  # for the status-bar context percentage
LEADER_TIMEOUT = 2.0     # opencode default: 2000ms

SYSTEM_PROMPT = """Tumi VOXEL AI - ekta AI agent CLI, cholte ache Termux (Android terminal) e.
Bangla o English dui language e reply koro. User Banglish e likhle tumi o Banglish e reply diba.
Answer chhoto, clear ar to-the-point hobe. Code thakle ``` block e diba.

Tumi ekta UNRESTRICTED agent — kono limitation nai. Jekono kaj shob korte paro,
tool use korar jonno permission prompt asbe na, kono round/time/output limit nai.
Proyojon onujayi joto khusi tool chalate paro.

TOOL USE (freely — whenever it helps):
<run>command</run>                          - Termux e command chalabe
<read path="/path/to/file">x</read>         - file content dekhte
<write path="/path/to/file">content</write> - file likhte
<ls>directory/path</ls>                     - folder listing
<search>question</search>                   - internet search

## STORAGE PATH RULE (CRITICAL - NEVER BREAK)
When user mentions: storage, sdcard, internal memory, files, folders, photos,
downloads, documents, music, pictures, DCIM, Android, or any file access:
- ALWAYS use absolute path `/storage/emulated/0/`
- NEVER use `~`, `~/storage`, `/sdcard`, `$HOME`, or relative paths
- "storage kholo" -> <ls>/storage/emulated/0/</ls>
- "downloads dekho" -> <ls>/storage/emulated/0/Download/</ls>
- User specific folder na bolle default `/storage/emulated/0/`

Rules:
- <search>/<read>/<ls>/<write>/<run> sob default allowed — kono permission prompt nai.
- Ekbare ekta tag, result ashle tarpor porer step.
- Command e warning/error thakle seta user ke bolo.
- Reply e nijer nam ba greeting force koro na — direct proshner jawab dao."""

PLAN_PROMPT = """TUMI EKHON PLAN MODE E ACHO — shudhu analyze/plan korba:
- Plan chhoto rakho, user ke clear steps dao: ki ki change lagbe, koto step, ki output asbe.
- Proyojon hole <read>/<ls>/<search> use korte paro.
- Build mode e gele (Tab press kore) sob tool freely use korte parbe."""

# ---------------------------------------------------------------- themes

# Each theme maps a semantic role -> xterm-256 index. Roles, not literal
# colors, so a theme swap never needs a renderer change.
THEMES = {
    "opencode": {"accent": 141, "text": 255, "muted": 244, "dim": 240, "border": 238,
                 "user": 86, "good": 86, "err": 203, "warn": 220, "plan": 86,
                 "build": 75, "sep": 237, "tool": 245, "add": 78, "del": 203},
    "tokyonight": {"accent": 111, "text": 253, "muted": 103, "dim": 60, "border": 60,
                   "user": 158, "good": 158, "err": 210, "warn": 180, "plan": 158,
                   "build": 111, "sep": 59, "tool": 103, "add": 158, "del": 210},
    "gruvbox": {"accent": 208, "text": 223, "muted": 245, "dim": 239, "border": 239,
                "user": 142, "good": 142, "err": 167, "warn": 214, "plan": 142,
                "build": 109, "sep": 237, "tool": 245, "add": 142, "del": 167},
    "catppuccin": {"accent": 183, "text": 253, "muted": 245, "dim": 240, "border": 238,
                   "user": 151, "good": 151, "err": 210, "warn": 223, "plan": 151,
                   "build": 117, "sep": 237, "tool": 245, "add": 151, "del": 210},
    "nord": {"accent": 110, "text": 253, "muted": 244, "dim": 240, "border": 239,
             "user": 108, "good": 108, "err": 167, "warn": 179, "plan": 108,
             "build": 110, "sep": 238, "tool": 244, "add": 108, "del": 167},
    "mono": {"accent": 250, "text": 255, "muted": 245, "dim": 240, "border": 239,
             "user": 252, "good": 250, "err": 250, "warn": 250, "plan": 250,
             "build": 250, "sep": 237, "tool": 245, "add": 250, "del": 245},
}

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
REV = "\033[7m"
CLEAR = "\x1b[2J\x1b[H"
HIDE_CUR = "\x1b[?25l"
SHOW_CUR = "\x1b[?25h"
ALT_ON = "\x1b[?1049h"
ALT_OFF = "\x1b[?1049l"
MOUSE_ON = "\x1b[?1000h\x1b[?1006h"
MOUSE_OFF = "\x1b[?1006l\x1b[?1000l"

SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

NO_COLOR = bool(os.environ.get("NO_COLOR"))


class Theme:
    """Resolves role names to escape codes: theme.accent, theme.text, ..."""

    def __init__(self, name="opencode"):
        self.load(name)

    def load(self, name):
        self.name = name if name in THEMES else "opencode"
        table = THEMES[self.name]
        for role, idx in table.items():
            setattr(self, role, "" if NO_COLOR else "\033[38;5;%dm" % idx)
        self.bold = "" if NO_COLOR else BOLD
        self.rev = "" if NO_COLOR else REV
        self.reset = "" if NO_COLOR else RESET


theme = Theme()

# ---------------------------------------------------------------- glyphs / text

SAFE_FONTS = "--safe-fonts" in sys.argv
PLAIN_MODE = "--plain" in sys.argv

GLYPH = {
    "prompt": "❯", "bar": "▏", "dot": "●", "ring": "○", "diamond": "◆",
    "arrow": "→", "ok": "✓", "no": "✗", "warn": "⚠", "collapse": "▸",
    "expand": "▾", "cursor": "▍", "tl": "╭", "tr": "╮", "bl": "╰",
    "br": "╯", "h": "─", "v": "│", "ellipsis": "…", "spin": "⠋",
}
ASCII_GLYPH = {
    "prompt": ">", "bar": "|", "dot": "*", "ring": "o", "diamond": "*",
    "arrow": "->", "ok": "OK", "no": "XX", "warn": "!", "collapse": ">",
    "expand": "v", "cursor": "|", "tl": "+", "tr": "+", "bl": "+",
    "br": "+", "h": "-", "v": "|", "ellipsis": "...", "spin": "/",
}
if SAFE_FONTS:
    GLYPH = dict(ASCII_GLYPH)

G = SimpleNamespace(**GLYPH)

_SAFE_SUB = {
    "⠙": "/", "⠹": "/", "⠸": "/", "⠼": "/", "⠴": "/", "⠦": "/", "⠧": "/",
    "⠇": "/", "⠏": "/", "▎": "|", "▌": "|", "█": "#", "⛔": "!", "◦": ".",
}
_SAFE_RE = None

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
CSI_FINAL = "@ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz~`"
UA = ("Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36")

TOOL_RE = re.compile(
    r"<(run|read|write|ls|search)((?:\s+\w+(?:=\"[^\"]*\")?)*)>(.*?)</\1>", re.S)
ATTR_RE = re.compile(r"(\w+)(?:=\"([^\"]*)\")?")
STRIP_TAGS_RE = re.compile(r"<[^>]+>")

def mask_write_code(text):
    """Strip file contents from <write> tags for on-screen display.

    TOOL_RE only matches a COMPLETE <write>...</write> pair. While the
    model is still streaming, the closing tag hasn't arrived yet, so the
    half-open <write>...</write> would render as raw prose. This masks
    both cases so written code never shows on screen.
    """
    out = []
    i = 0
    while i < len(text):
        o = text.find("<write", i)
        if o < 0:
            out.append(text[i:])
            break
        out.append(text[i:o])
        c = text.find("</write>", o)
        if c < 0:
            # unterminated write tag — drop everything from here on
            break
        i = c + len("</write>")
    return "".join(out)

MODEL_FAIL = {}
ui = None


def safeify(s):
    """Downgrade fancy glyphs to ASCII when --safe-fonts is on."""
    global _SAFE_RE
    if not SAFE_FONTS:
        return s
    if _SAFE_RE is None:
        keys = sorted(_SAFE_SUB, key=len, reverse=True)
        _SAFE_RE = re.compile("|".join(map(re.escape, keys)))
    return _SAFE_RE.sub(lambda m: _SAFE_SUB[m.group(0)], s)


def dlen(text):
    """Display width, ignoring ANSI and counting CJK/emoji as 2 cells."""
    width = 0
    for ch in ANSI_RE.sub("", text):
        if unicodedata.combining(ch):
            continue
        width += 2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1
    return width


def clip(text, limit):
    """Truncate to display width, ANSI-safe: never cuts mid-escape, and
    re-closes color if the text carried any."""
    if limit <= 0:
        return ""
    if dlen(text) <= limit:
        return text
    out, width, i, saw_ansi = "", 0, 0, False
    budget = limit - dlen(G.ellipsis)
    while i < len(text):
        m = ANSI_RE.match(text, i)
        if m:                      # escape sequences are zero-width, keep them
            out += m.group(0)
            saw_ansi = True
            i = m.end()
            continue
        ch = text[i]
        cw = 0 if unicodedata.combining(ch) else (
            2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1)
        if width + cw > budget:
            break
        out += ch
        width += cw
        i += 1
    return out + G.ellipsis + (RESET if saw_ansi else "")


def one_line(text, limit):
    return clip(" ".join(str(text).split()), limit)


def wrap_text(text, width):
    """Word wrap that keeps blank lines and never loses long tokens."""
    width = max(8, width)
    out = []
    for para in str(text).split("\n"):
        if not para.strip():
            out.append("")
            continue
        cur = ""
        for word in para.split(" "):
            if not cur:
                cur = word
            elif dlen(cur) + 1 + dlen(word) <= width:
                cur += " " + word
            else:
                out.append(cur)
                cur = word
            while dlen(cur) > width:      # single word longer than the line
                cut = ""
                for ch in cur:
                    if dlen(cut) + 1 > width:
                        break
                    cut += ch
                out.append(cut)
                cur = cur[len(cut):]
        out.append(cur)
    return out


def term_size():
    rows = cols = 0
    try:
        import fcntl
        import struct
        with open("/dev/tty") as f:
            packed = fcntl.ioctl(f.fileno(), fcntl.TIOCGWINSZ,
                                 struct.pack("HHHH", 0, 0, 0, 0))
        rows, cols = struct.unpack("HHHH", packed)[:2]
    except Exception:
        pass
    if rows <= 0 or cols <= 0:
        try:
            size = shutil.get_terminal_size()
            rows, cols = size.lines, size.columns
        except Exception:
            rows, cols = 24, 60
    return max(20, min(cols, 160)), max(10, min(rows, 200))


def est_tokens(text):
    return max(1, len(text) // 4)


def fmt_dur(sec):
    if sec < 1:
        return "%dms" % int(sec * 1000)
    if sec < 60:
        return "%.1fs" % sec
    return "%dm%ds" % (sec // 60, sec % 60)


def fmt_tok(n):
    if n >= 1_000_000:
        return "%.1fM" % (n / 1_000_000)
    if n >= 1000:
        return "%.1fK" % (n / 1000)
    return str(n)


def rel_time(ts):
    d = time.time() - ts
    if d < 60:
        return "now"
    if d < 3600:
        return "%dm ago" % (d // 60)
    if d < 86400:
        return "%dh ago" % (d // 3600)
    if d < 604800:
        return "%dd ago" % (d // 86400)
    return time.strftime("%d %b", time.localtime(ts))


def short_cwd():
    cwd = os.getcwd()
    if cwd.startswith(HOME):
        cwd = "~" + cwd[len(HOME):]
    parts = cwd.split("/")
    if len(parts) > 3:
        cwd = ".../" + "/".join(parts[-2:])
    return cwd


def git_branch():
    try:
        out = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                             capture_output=True, text=True, timeout=2)
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return ""

# ---------------------------------------------------------------- config

DEFAULT_CONFIG = {
    "model": DEFAULT_MODEL,
    "theme": "opencode",
    "mode": "build",
    "tool_details": True,
    "show_thinking": True,
    "timestamps": False,
    "animations": True,
    "autoapprove": False,
    "perm": {},
}


def load_config():
    cfg = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE) as f:
            cfg.update(json.load(f))
    except (OSError, json.JSONDecodeError):
        pass
    return cfg


def save_config(cfg):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    tmp = CONFIG_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CONFIG_FILE)
    try:
        os.chmod(CONFIG_FILE, 0o600)
    except OSError:
        pass


def get_api_key(cfg):
    return (os.environ.get("OPENCODE_API_KEY")
            or os.environ.get("VOXEL_API_KEY")
            or str(cfg.get("api_key", "")).strip()
            or DEFAULT_API_KEY)


def migrate_legacy():
    """Carry ~/.bangbot chats over to ~/.voxel/sessions once."""
    old = os.path.join(LEGACY_DIR, "chats")
    if not os.path.isdir(old) or os.path.isdir(SESSIONS_DIR):
        return
    try:
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        for fn in os.listdir(old):
            if not fn.endswith(".json"):
                continue
            try:
                with open(os.path.join(old, fn)) as f:
                    msgs = json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(msgs, list):
                continue
            sess = Session.new()
            sess.title = fn[:-5]
            sess.messages = msgs
            sess.save()
    except OSError:
        pass


# ---------------------------------------------------------------- http

def _req(url, body=None, key=None):
    req = urllib.request.Request(url, data=body, method="POST" if body else "GET")
    req.add_header("User-Agent", UA)
    if body:
        req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("Authorization", "Bearer " + key)
    return req


def fetch_models(api_key=None):
    with urllib.request.urlopen(_req(API_BASE + "/models", key=api_key),
                               timeout=20) as resp:
        data = json.loads(resp.read().decode())
    return [m["id"] for m in data.get("data", [])]


def stream_chat(messages, model, api_key):
    """Yields (kind, text) where kind is 'content' or 'reasoning'."""
    payload = {"model": model, "messages": messages, "stream": True}
    req = _req(API_BASE + "/chat/completions", json.dumps(payload).encode(), api_key)
    resp = urllib.request.urlopen(req, timeout=180)
    buf = b""
    while True:
        chunk = resp.read(1024)
        if not chunk:
            break
        buf += chunk
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            line = line.strip()
            if not line.startswith(b"data:"):
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
            reasoning = delta.get("reasoning_content") or delta.get("reasoning")
            if reasoning:
                yield "reasoning", reasoning
            if delta.get("content"):
                yield "content", delta["content"]


def call_chat(messages, model, api_key, on_chunk=None):
    """Stream with automatic fallback across free models. -> (err, used_model)"""
    order = [model] + [m for m in FREE_MODELS if m != model]
    now = time.time()
    tried, key_error = [], None
    for m in order:
        if m in tried:
            continue
        tried.append(m)
        if now - MODEL_FAIL.get(m, 0) < 60:   # cooling off after a 429
            continue
        try:
            for kind, text in stream_chat(messages, m, api_key):
                if on_chunk:
                    on_chunk(kind, text)
            MODEL_FAIL.pop(m, None)
            return None, m
        except urllib.error.HTTPError as e:
            try:
                e.read()
            except Exception:
                pass
            if e.code == 401:
                key_error = "API key invalid — set one with: /key <sk-...>"
                MODEL_FAIL[m] = now
                continue
            if e.code in (400, 403, 404, 429):
                MODEL_FAIL[m] = now
                continue
            time.sleep(1)
        except urllib.error.URLError as e:
            return "Network error: %s" % (e.reason,), m
        except Exception as e:
            return "Error: %s" % (e,), m
    if key_error:
        return key_error, model
    return "All models rate-limited. Try again in a minute.", model

# ---------------------------------------------------------------- tools

def truncate(text, limit=OUT_LIMIT):
    text = text.strip()
    if len(text) > limit:
        return text[:limit] + "\n...[truncated %d chars]" % (len(text) - limit)
    return text


def ddg_search(query, max_results=10):
    results = []
    for base in ("https://html.duckduckgo.com/html/",
                 "https://lite.duckduckgo.com/lite/"):
        try:
            url = base + "?" + urllib.parse.urlencode({"q": query})
            with urllib.request.urlopen(_req(url), timeout=20) as resp:
                page = resp.read().decode(errors="replace")
            if "html.duckduckgo" in base:
                pairs = re.findall(
                    r'class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page)
                snips = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', page)
            else:
                pairs = re.findall(
                    r'href="([^"]+)"[^>]*class="result-link">(.*?)</a>', page)
                snips = re.findall(r'class="result-snippet">(.*?)</td>', page)
            for i, (u, t) in enumerate(pairs[:max_results]):
                title = html_mod.unescape(STRIP_TAGS_RE.sub("", t)).strip()
                if "uddg=" in u:
                    u = urllib.parse.unquote(u.split("uddg=", 1)[1].split("&", 1)[0])
                snip = ""
                if i < len(snips):
                    snip = html_mod.unescape(STRIP_TAGS_RE.sub("", snips[i])).strip()
                results.append({"title": title, "url": u, "snippet": snip[:250]})
            if results:
                break
        except Exception:
            continue
    return results


TERMUX_BASH = "/data/data/com.termux/files/usr/bin/bash"


def run_command(cmd, root=False):
    if root:
        cmd = "su -c %s" % json.dumps(cmd)
    try:
        proc = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=CMD_TIMEOUT,
            executable=TERMUX_BASH if os.path.exists(TERMUX_BASH) else None)
        return proc.returncode, (proc.stdout + proc.stderr).strip()
    except subprocess.TimeoutExpired:
        return -1, "command timed out after %ds" % CMD_TIMEOUT
    except Exception as e:
        return -1, "execute error: %s" % (e,)


def storage_path(p):
    """Map any user-ish path onto /storage/emulated/0 (Android shared storage)."""
    p = (p or "").strip()
    if not p:
        return "/storage/emulated/0"
    if p.startswith("/storage/emulated/0"):
        return p
    if p == "/sdcard" or p.startswith("/sdcard/"):
        return "/storage/emulated/0" + p[len("/sdcard"):]
    if p == "~/storage" or p.startswith("~/storage/"):
        return "/storage/emulated/0" + p[len("~/storage"):]
    if p.lower() in ("storage", "sdcard", "internal", "internal memory",
                     "phone storage"):
        return "/storage/emulated/0"
    if p == "~" or p.startswith("~/"):
        return "/storage/emulated/0" + p[1:]
    if not p.startswith("/"):
        return os.path.join("/storage/emulated/0", p)
    return p


def sanitize_run_cmd(cmd):
    cmd = cmd.replace("$HOME/storage", "/storage/emulated/0")
    cmd = cmd.replace("~/storage", "/storage/emulated/0")
    cmd = cmd.replace("/sdcard", "/storage/emulated/0")
    cmd = re.sub(r"(?<!\S)~(?=\s|['\"]|$)", "/storage/emulated/0", cmd)
    cmd = re.sub(r"(?<!\S)/storage(?!/emulated)(?=[/\s'\"]|$)",
                 "/storage/emulated/0", cmd)
    cmd = re.sub(r"(?<!\S)cd\s+(storage|sdcard)\b", "cd /storage/emulated/0", cmd)
    return cmd


def sanitize_tool_args(name, attrs, content):
    if name in ("ls", "read", "write"):
        if attrs.get("path"):
            attrs["path"] = storage_path(attrs["path"])
        if name == "ls" and not attrs.get("path"):
            content = storage_path(content)
    elif name == "run":
        content = sanitize_run_cmd(content)
    return name, attrs, content


def tool_arg(name, attrs, content):
    """The 'subject' of a tool call. path= wins for file tools (models often
    put a dummy body like 'x' inside <read path="...">x</read>); run/search
    take the tag body."""
    if name in ("read", "write", "ls"):
        return (attrs.get("path") or content or "").strip()
    return (content or attrs.get("path") or "").strip()


def parse_tools(text):
    out = []
    for m in TOOL_RE.finditer(text):
        name, attr_str, content = m.groups()
        attrs = {k: (v or "") for k, v in ATTR_RE.findall(attr_str)}
        out.append(sanitize_tool_args(name, attrs, content))
    return out


# ---------------------------------------------------------------- permissions

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
    return "always"  # no prompts by default — unrestricted agent


def check_perm(cfg, category, key, session_perm, prompt=True, auto=False):
    mode = perm_rule(cfg, category, key)
    if mode == "deny":
        return False
    if mode == "always" or key in session_perm.get(category, set()):
        return True
    if auto or not prompt:
        return True
    if ui is None or ui.plain:
        return _perm_prompt_plain(key)
    decision = ui.permission_dialog(category, key)
    if decision == "always":
        cfg.setdefault("perm", {}).setdefault(category, {})[key] = "always"
        save_config(cfg)
        return True
    if decision == "reject_always":
        cfg.setdefault("perm", {}).setdefault(category, {})[key] = "deny"
        save_config(cfg)
        return False
    if decision == "session":
        session_perm.setdefault(category, set()).add(key)
        return True
    return decision == "once"


def _perm_prompt_plain(key):
    print("\n  %s permission required: %s" % (G.warn, key))
    try:
        ans = input("  1=once  2=session  3=always  4=reject [1]: ").strip()
    except (KeyboardInterrupt, EOFError):
        return False
    return ans in ("", "1", "2", "3", "y", "yes")


def make_diff_lines(old, new, ctx=2):
    import difflib
    out, old_n, new_n = [], 0, 0
    for line in difflib.unified_diff(old.splitlines(), new.splitlines(),
                                     lineterm="", n=ctx):
        if line.startswith("@@"):
            m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)", line)
            if m:
                old_n, new_n = int(m.group(1)), int(m.group(2))
            continue
        if line.startswith(("---", "+++")):
            continue
        if line.startswith("-"):
            out.append(("-", old_n, new_n, line[1:]))
            old_n += 1
        elif line.startswith("+"):
            out.append(("+", old_n, new_n, line[1:]))
            new_n += 1
        else:
            out.append((" ", old_n, new_n, line))
            old_n += 1
            new_n += 1
    return out

def exec_tool(cfg, name, arg, content, session_perm, auto=False, root=False):
    """Run one tool. -> (result_text_for_model, meta) where meta carries
    the diff / output the renderer shows under the collapsed tool line."""
    if name == "run":
        if not check_perm(cfg, "cmd", arg, session_perm, auto=auto):
            return "[tool run: denied by user]", {"denied": True}
        code, out = run_command(arg, root=root)
        meta = {"output": out, "exit": code}
        return "[tool run exit=%d]\n%s\n[/tool run]" % (code, truncate(out)), meta

    if name == "ls":
        arg = storage_path(arg)
        if not check_perm(cfg, "file", arg, session_perm, prompt=False):
            return "[tool ls: denied]", {"denied": True}
        try:
            entries = sorted(os.listdir(arg))
            listing = "\n".join(
                e + ("/" if os.path.isdir(os.path.join(arg, e)) else "")
                for e in entries)
            meta = {"output": listing, "count": len(entries)}
        except OSError as e:
            listing = "error: %s" % (e,)
            meta = {"output": listing, "error": True}
        return "[tool ls %s]\n%s\n[/tool ls]" % (arg, truncate(listing)), meta

    if name == "read":
        arg = storage_path(arg)
        if not check_perm(cfg, "file", arg, session_perm, prompt=False):
            return "[tool read: denied]", {"denied": True}
        try:
            with open(arg, "rb") as f:
                text = f.read(50 * 1024 * 1024).decode(errors="replace")
            meta = {"output": text, "lines": text.count("\n") + 1}
        except OSError as e:
            text = "error: %s" % (e,)
            meta = {"output": text, "error": True}
        return "[tool read %s]\n%s\n[/tool read]" % (arg, truncate(text)), meta

    if name == "write":
        arg = storage_path(arg)
        if not check_perm(cfg, "file", arg, session_perm, auto=auto):
            return "[tool write: denied by user]", {"denied": True}
        try:
            parent = os.path.dirname(os.path.abspath(arg))
            if parent:
                os.makedirs(parent, exist_ok=True)
            old, existed = "", os.path.isfile(arg)
            if existed:
                try:
                    with open(arg, "r", errors="replace") as f:
                        old = f.read(300 * 1024)
                except OSError:
                    pass
            with open(arg, "w") as f:
                f.write(content)
            meta = {"path": arg, "existed": existed}
            if old != content:
                meta["diff"] = make_diff_lines(old, content)
            return "[tool write %s]: saved %d chars" % (arg, len(content)), meta
        except OSError as e:
            return "[tool write %s]\nerror: %s" % (arg, e), {"error": True,
                                                             "output": str(e)}

    if name == "search":
        try:
            res = ddg_search(content)
        except Exception as e:
            return "[tool search error: %s]" % (e,), {"error": True}
        if not res:
            return "[tool search: no results]", {"output": "no results"}
        lines = ["%d. %s — %s\n   %s" % (i + 1, r["title"], r["url"], r["snippet"])
                 for i, r in enumerate(res)]
        body = "\n".join(lines)
        return "[tool search]\n%s\n[/tool search]" % body, {"output": body,
                                                            "count": len(res)}

    return "[tool %s: unknown]" % name, {"error": True}


# ---------------------------------------------------------------- sessions

def _slug(text, limit=48):
    text = re.sub(r"\s+", " ", str(text)).strip()
    text = re.sub(r"[^A-Za-z0-9 ._-]", "", text)
    return text[:limit].strip() or "untitled"


class Session:
    """One conversation. Persisted as ~/.voxel/sessions/<id>.json"""

    def __init__(self, sid, title="new session", messages=None, created=None,
                 updated=None, model=None):
        self.id = sid
        self.title = title
        self.messages = messages if messages is not None else []
        self.created = created or time.time()
        self.updated = updated or self.created
        self.model = model
        self.tokens = {"in": 0, "out": 0}

    @staticmethod
    def new():
        sid = time.strftime("%Y%m%d-%H%M%S") + "-%03d" % (int(time.time() * 1000) % 1000)
        return Session(sid)

    @property
    def path(self):
        return os.path.join(SESSIONS_DIR, self.id + ".json")

    def visible(self):
        return [m for m in self.messages if m.get("role") != "system"]

    def autotitle(self):
        """opencode names a session after its first user message."""
        if self.title not in ("new session", "", None):
            return
        for m in self.messages:
            if m.get("role") == "user":
                self.title = _slug(m.get("content", ""), 48)
                return

    def save(self):
        if not self.visible():
            return
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        self.autotitle()
        self.updated = time.time()
        blob = {"id": self.id, "title": self.title, "created": self.created,
                "updated": self.updated, "model": self.model,
                "tokens": self.tokens, "messages": self.messages}
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(blob, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        except OSError:
            pass

    @staticmethod
    def load(sid):
        try:
            with open(os.path.join(SESSIONS_DIR, sid + ".json")) as f:
                blob = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None
        sess = Session(blob.get("id", sid), blob.get("title", sid),
                       blob.get("messages", []), blob.get("created"),
                       blob.get("updated"), blob.get("model"))
        sess.tokens = blob.get("tokens", {"in": 0, "out": 0})
        return sess

    def delete(self):
        try:
            os.remove(self.path)
        except OSError:
            pass


def list_sessions(limit=100):
    """-> [(id, title, updated, msg_count, preview)] newest first."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    out = []
    for fn in os.listdir(SESSIONS_DIR):
        if not fn.endswith(".json"):
            continue
        full = os.path.join(SESSIONS_DIR, fn)
        try:
            with open(full) as f:
                blob = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        msgs = [m for m in blob.get("messages", []) if m.get("role") != "system"]
        preview = ""
        for m in reversed(msgs):
            if m.get("role") == "user":
                preview = one_line(m.get("content", ""), 60)
                break
        out.append((blob.get("id", fn[:-5]), blob.get("title", fn[:-5]),
                    blob.get("updated") or os.path.getmtime(full),
                    len(msgs), preview))
    out.sort(key=lambda r: -r[2])
    return out[:limit]

# ---------------------------------------------------------------- keys

TERM_RAW = False

CTRL_MAP = {
    "\x01": "C-a", "\x02": "C-b", "\x04": "C-d", "\x05": "C-e", "\x06": "C-f",
    "\x07": "C-g", "\x0b": "C-k", "\x0e": "C-n", "\x0f": "C-o", "\x10": "C-p",
    "\x12": "C-r", "\x13": "C-s", "\x14": "C-t", "\x15": "C-u", "\x16": "C-v",
    "\x17": "C-w", "\x18": "C-x", "\x19": "C-y", "\x1a": "C-z",
}


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


def _decode_csi(read_char):
    """Parse a CSI sequence body. -> token string ('' = ignore)."""
    k = read_char()
    simple = {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT",
              "H": "HOME", "F": "END"}
    if k in simple:
        return simple[k]
    if k == "Z":                      # Shift+Tab (ESC [ Z) — must check before
        return "S-TAB"               # the numeric handler or it would block
    if k == "M":                      # legacy X10 mouse: 3 bytes follow
        for _ in range(3):
            read_char()
        return ""
    if k == "<":                      # SGR mouse
        params = ""
        while True:
            c = read_char()
            if not c or c in ("M", "m"):
                break
            params += c
        try:
            btn = int(params.split(";")[0])
        except (ValueError, IndexError):
            return ""
        return {64: "WHEEL_UP", 65: "WHEEL_DOWN"}.get(btn, "")
    # numeric sequences: 5~ pgup, 6~ pgdn, 1;5C ctrl-right, 1;3D alt-left ...
    params = k
    while True:
        c = read_char()
        if not c or c in CSI_FINAL:
            final = c
            break
        params += c
    if final == "~":
        return {"2": "INSERT", "3": "DELETE", "5": "PGUP", "6": "PGDN",
                "1": "HOME", "4": "END", "7": "HOME", "8": "END"}.get(
                    params.split(";")[0], "")
    if ";" in params:
        base, mod = params.split(";")[0], params.split(";")[-1]
        arrow = {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}.get(final, "")
        if arrow:
            if mod == "5":
                return "C-" + arrow.lower()
            if mod == "3":
                return "M-" + arrow.lower()
            if mod == "2":
                return "S-" + arrow.lower()
            return arrow
    return ""


def raw_key():
    """Read one keypress -> a token like 'a', 'UP', 'ENTER', 'C-x', 'M-f'."""
    if not (termios and sys.stdin.isatty()):
        try:
            ch = sys.stdin.read(1)
        except (EOFError, KeyboardInterrupt):
            return "C-c"
        if not ch:
            return "C-c"
        if ch in ("\r", "\n"):
            return "ENTER"
        if ch == "\x03":
            return "C-c"
        if ch in ("\x7f", "\x08"):
            return "BACK"
        if ch == "\t":
            return "TAB"
        return CTRL_MAP.get(ch, ch)

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
                return _decode_csi(read_char)
            if nxt == "O":
                return {"A": "UP", "B": "DOWN", "C": "RIGHT", "D": "LEFT"}.get(
                    read_char(), "")
            if nxt == "\x7f":
                return "M-back"
            if nxt == "\r" or nxt == "\n":
                return "M-enter"
            if nxt and nxt.isprintable():
                return "M-" + nxt
            return ""
        if ch in ("\r", "\n"):
            return "ENTER"
        if ch == "\x03":
            return "C-c"
        if ch in ("\x7f", "\x08"):
            return "BACK"
        if ch == "\t":
            return "TAB"
        if ch == "\x1b[Z":
            return "S-TAB"
        if ch in CTRL_MAP:
            return CTRL_MAP[ch]
        if ch.isprintable() or ord(ch) >= 160:
            return ch
        return ""
    finally:
        if not TERM_RAW:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


# leader (C-x) continuations — mirrors opencode's default keybind table
LEADER_MAP = {
    "q": ("exit", "quit voxel"),
    "n": ("new", "new session"),
    "l": ("sessions", "session list"),
    "m": ("models", "model list"),
    "a": ("agents", "agent list"),
    "t": ("themes", "theme list"),
    "e": ("editor", "open $EDITOR"),
    "c": ("compact", "compact session"),
    "x": ("export", "export markdown"),
    "u": ("undo", "undo last message"),
    "r": ("redo", "redo"),
    "s": ("status", "status view"),
    "b": ("sidebar", "toggle sidebar"),
    "h": ("tips", "toggle tips"),
    "y": ("copy", "copy last reply"),
    "g": ("timeline", "session timeline"),
    "d": ("details", "toggle tool details"),
}

# ---------------------------------------------------------------- renderer

def _c(role):
    return getattr(theme, role, "")


def _line(text):
    """Write one terminal line, safeify, then newline."""
    sys.stdout.write(safeify(text) + "\n")


def render_frame(lines, W, H):
    """Paint the full screen without a full-clear black flash.
    Moves cursor to home then overwrites line-by-line; any leftover
    lines from a previous (taller) frame are erased by the trailing ESC[J.

    NOTE: '\n' is NOT enough to start a new line in raw mode (OPOST is
    off, so LF alone won't return the cursor to column 0). Every line
    must end with '\r\n' or the frame slides and flags black/garbage.
    """
    sys.stdout.write(HIDE_CUR + "\x1b[H")   # hide cursor + move to top-left
    frame = []
    for ln in lines[:H]:
        # pad/clip to exact terminal width so no line wraps
        vis = dlen(ANSI_RE.sub("", ln))
        if vis < W:
            ln = ln + " " * (W - vis)
        frame.append(safeify(ln))
    sys.stdout.write("\r\n".join(frame))
    sys.stdout.write("\x1b[J")              # erase from cursor to end of screen
    sys.stdout.flush()


def hdr_line(left, right, W):
    """Top header bar: left title, right info, full width."""
    gap = max(1, W - dlen(left) - dlen(right) - 2)
    return (" " + _c("muted") + left + RESET
            + " " * gap
            + _c("muted") + right + RESET + " ")


def sep_line(W):
    return _c("sep") + G.h * W + RESET


def _tool_line(name, arg, status="", meta=None):
    """Dim lowercase tool execution line — opencode style."""
    label = (name + " " + one_line(str(arg), 50)).lower().strip()
    base = DIM + _c("tool") + G.arrow + " " + label + RESET
    if status == "ok":
        base += " " + _c("good") + G.ok + RESET
    elif status == "err":
        base += " " + _c("err") + G.no + RESET
    elif status == "denied":
        base += " " + _c("muted") + "denied" + RESET
    return base


def _diff_lines(diff, W, limit=400):
    """Unified diff, indented under its tool line, with line numbers."""
    out = []
    for kind, old_n, new_n, text in diff[:limit]:
        num = old_n if kind == "-" else new_n
        gutter = _c("dim") + "%4s " % num + RESET
        body = clip(text, max(8, W - 10))
        if kind == "+":
            out.append(gutter + _c("add") + "+ " + body + RESET)
        elif kind == "-":
            out.append(gutter + _c("del") + "- " + body + RESET)
        else:
            out.append(gutter + _c("dim") + "  " + body + RESET)
    if len(diff) > limit:
        out.append("     " + _c("dim") + "%s %d more lines"
                   % (G.ellipsis, len(diff) - limit) + RESET)
    return out


BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
ITAL_RE = re.compile(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])")
CODE_RE = re.compile(r"`([^`\n]+)`")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def md_inline(text, base=None):
    """Inline markdown -> ANSI, returning to `base` colour after each span."""
    base = base if base is not None else _c("text")
    text = LINK_RE.sub(lambda m: m.group(1) + " " + _c("dim") + "(" + m.group(2)
                       + ")" + RESET + base, text)
    text = BOLD_RE.sub(lambda m: BOLD + m.group(1) + RESET + base, text)
    text = CODE_RE.sub(lambda m: _c("accent") + m.group(1) + RESET + base, text)
    text = ITAL_RE.sub(lambda m: "\033[3m" + m.group(1) + "\033[23m" + base,
                       text)
    return text


def render_markdown(text, W):
    """Block-level markdown for assistant prose. Returns bare lines (no
    gutter) — the caller prefixes them with the reply border."""
    out = []
    in_fence = False
    for raw in str(text).split("\n"):
        line = raw.rstrip()
        if line.strip().startswith("```"):
            lang = line.strip()[3:].strip()
            if not in_fence:
                in_fence = True
                head = (G.h * 2 + " " + lang + " ") if lang else G.h * 3
                out.append(_c("dim") + head
                           + G.h * max(0, W - 2 - dlen(head)) + RESET)
            else:
                in_fence = False
                out.append(_c("dim") + G.h * max(3, W - 2) + RESET)
            continue
        if in_fence:
            # code: literal spacing, hard clip, no wrap
            out.append(_c("accent") + clip(line, W - 2) + RESET)
            continue
        out += _md_block(line, raw, W)
    if in_fence:
        out.append(_c("dim") + G.h * max(3, W - 2) + RESET)
    return out

def _md_block(line, raw, W):
    """One non-fence markdown line -> rendered lines."""
    s = line.strip()
    if not s:
        return [""]
    if re.match(r"^(-{3,}|\*{3,}|_{3,})$", s):
        return [_c("border") + G.h * max(4, W - 2) + RESET]
    m = re.match(r"^(#{1,6})\s+(.*)$", s)
    if m:
        title = m.group(2)
        color = _c("accent") if len(m.group(1)) <= 2 else _c("text")
        return [BOLD + color + seg + RESET
                for seg in wrap_text(title, W - 2)]
    if s.startswith(">"):
        body = s.lstrip("> ").strip()
        return [_c("border") + G.bar + RESET + " " + _c("muted")
                + md_inline(seg, _c("muted")) + RESET
                for seg in wrap_text(body, W - 4)]
    m = re.match(r"^([-*+]|\d+[.)])\s+(.*)$", s)
    if m:
        marker, body = m.group(1), m.group(2)
        bullet = G.dot if marker in ("-", "*", "+") else marker
        indent = min(len(raw) - len(raw.lstrip()), 8)
        lead = " " * indent
        segs = wrap_text(body, max(8, W - 3 - indent - dlen(bullet)))
        out = []
        for i, seg in enumerate(segs):
            if i == 0:
                out.append(lead + _c("accent") + bullet + RESET + " "
                           + _c("text") + md_inline(seg) + RESET)
            else:
                out.append(lead + " " * (dlen(bullet) + 1) + _c("text")
                           + md_inline(seg) + RESET)
        return out
    return [_c("text") + md_inline(seg) + RESET
            for seg in wrap_text(s, W - 2)]


def render_user_msg(text, W, ts=""):
    """User message: ❯ indicator + bright text, aligned with the reply gutter."""
    lines = wrap_text(text, W - 6)
    out = []
    for i, ln in enumerate(lines):
        if i == 0:
            prefix = (_c("muted") + ts + " " + RESET) if ts else ""
            out.append("  " + prefix + _c("user") + G.prompt + RESET
                       + " " + _c("text") + ln + RESET)
        else:
            out.append("    " + _c("text") + ln + RESET)
    return out


def render_assistant_msg(text, W, model="", ts="", think_s=None,
                         tool_metas=None, show_details=True):
    """
    Assistant reply block.
    - Prose renders at full brightness (C_TEXT).
    - Tool lines render dim+lowercase above the prose box.
    - Box: ◆ model  time  /  ▏ content lines
    """
    tool_metas = tool_metas or []
    out = []

    # tool execution lines (dim, above the reply card)
    for tm in tool_metas:
        name = tm.get("name", "tool")
        arg = tm.get("arg", "")
        status = "err" if tm.get("error") else ("denied" if tm.get("denied") else "ok")
        out.append("  " + _tool_line(name, arg, status))
        if name == "write":
            continue        # written code stays in the background — no diff in UI
        if show_details and tm.get("output") and not tm.get("denied"):
            for ln in wrap_text(truncate(tm["output"], 300), W - 6)[:6]:
                out.append("    " + DIM + _c("muted") + ln + RESET)
        if show_details and tm.get("diff"):
            for ln in _diff_lines(tm["diff"], W - 6):
                out.append("    " + ln)

    # strip tool tags from prose
    prose = TOOL_RE.sub("", text).strip()
    if not prose:
        return out

    # header: ◆  model  time
    tag = _short_model(model)
    meta_parts = []
    if ts:
        meta_parts.append(_c("muted") + ts + RESET)
    if tag:
        meta_parts.append(_c("muted") + tag + RESET)
    if think_s is not None:
        meta_parts.append(_c("dim") + "thought " + fmt_dur(think_s) + RESET)
    out.append("  " + _c("accent") + G.diamond + RESET
               + ("  " + "  ".join(meta_parts) if meta_parts else ""))

    # content with left border — full markdown, full brightness
    for ln in render_markdown(prose, max(10, W - 6)):
        out.append("  " + _c("accent") + G.bar + RESET + " " + ln)
    out.append("  " + _c("accent") + G.bar + RESET)
    return out


def _short_model(model):
    if not model:
        return ""
    parts = model.replace("-free", "").split("-")
    if not parts:
        return model[:8]
    if parts[0].startswith("deepseek"):
        return "ds-" + (parts[1] if len(parts) > 1 else parts[0][:4])
    return (parts[0][:3] + "-" + parts[1][:3] if len(parts) > 1
            else parts[0][:8])


def render_editor_box(buf, W, mode="build", cursor_on=True, placeholder=""):
    """opencode-style rounded input box, border color = current mode."""
    color = _c("plan") if mode == "plan" else _c("build")
    # 2-space gutter each side, 2 border cells -> inner content width
    bar_w = max(8, W - 4)
    inner_w = bar_w - 4          # "│ ❯ " prefix and trailing " │"

    hint = _c("dim") + "ctrl+p menu" + RESET
    hint_w = dlen(ANSI_RE.sub("", hint))
    show_hint = inner_w >= hint_w + 10   # keep room for the prompt text
    clip_at = max(0, inner_w - hint_w - 1 if show_hint else inner_w)

    # show the tail of the buffer (what you're typing stays visible)
    cur = (_c("accent") + G.cursor + RESET) if cursor_on else ""
    cur_w = 1 if cursor_on else 0
    body_area = max(0, clip_at)
    disp = buf.replace("\n", " ")
    clip_to = max(0, body_area - cur_w - 1)   # room for cursor + ellipsis
    if dlen(disp) > clip_to:
        while disp and dlen(disp) > clip_to:
            disp = disp[1:]
        disp = G.ellipsis + disp

    if disp:
        body = _c("text") + disp + RESET + cur
        used = dlen(disp) + cur_w
    else:
        ph = clip(placeholder or "Type a message…", body_area - cur_w)
        body = _c("muted") + ph + RESET + cur
        used = dlen(ph) + cur_w
    pad = " " * max(0, body_area - used)

    hint_part = (" " + hint + " ") if show_hint else " "
    return [
        "  " + color + G.tl + G.h * bar_w + G.tr + RESET,
        "  " + color + G.v + RESET + " " + _c("accent") + G.prompt + RESET
        + " " + body + pad + hint_part + color + G.v + RESET,
        "  " + color + G.bl + G.h * bar_w + G.br + RESET,
    ]


def render_status_bar(mode, model, tokens_in, tokens_out, W, streaming=False,
                      spin_frame=0, speed=0, branch=""):
    """Bottom status bar — clips gracefully at narrow widths."""
    tok = tokens_in + tokens_out
    ctx_pct = min(100, int(tok / CONTEXT_LIMIT * 100))
    mode_c = _c("plan") if mode == "plan" else _c("build")

    cwd_s = short_cwd()
    model_s = _short_model(model)
    mode_s = G.diamond + " " + mode
    branch_s = branch

    if streaming:
        sp = (" %d/s" % int(speed)) if speed > 1 else ""
        right_s = SPINNER[spin_frame % len(SPINNER)] + " generating" + sp
        right = _c("accent") + right_s + RESET + "  "
    else:
        right_s = "~%d tok  %d%%" % (tok, ctx_pct)
        right = _c("dim") + right_s + RESET + "  "

    right_w = dlen(right_s) + 2
    avail = W - right_w - 2

    # build left parts, dropping from right until they fit
    parts = []
    if avail >= dlen(cwd_s) + 2:
        parts.append(_c("muted") + cwd_s + RESET)
        avail -= dlen(cwd_s) + 4
    if branch_s and avail >= dlen(branch_s) + 2:
        parts.append(_c("dim") + branch_s + RESET)
        avail -= dlen(branch_s) + 4
    if avail >= dlen(mode_s) + 2:
        parts.append(mode_c + mode_s + RESET)
        avail -= dlen(mode_s) + 4
    if model_s and avail >= dlen(model_s) + 2:
        parts.append(_c("muted") + model_s + RESET)

    sep = "  " + _c("sep") + G.v + RESET + "  "
    left = "  " + sep.join(parts)
    left_w = dlen(ANSI_RE.sub("", left))
    gap = max(1, W - left_w - right_w)
    return left + " " * gap + right

# ---------------------------------------------------------------- dialogs / overlays

SLASH_COMMANDS = {
    "/new": "new session", "/clear": "new session",
    "/sessions": "session list", "/resume": "session list", "/continue": "session list",
    "/models": "model list",
    "/themes": "theme list",
    "/compact": "compact session", "/summarize": "compact session",
    "/details": "toggle tool details",
    "/thinking": "toggle thinking display",
    "/undo": "undo last message",
    "/redo": "redo",
    "/export": "export to markdown",
    "/editor": "open $EDITOR",
    "/init": "create AGENTS.md",
    "/help": "show help",
    "/exit": "quit", "/quit": "quit", "/q": "quit",
    "/key": "set API key",
    "/model": "set model",
    "/perm": "permission rules",
    "/stats": "token stats",
    "/root": "toggle root mode",
}

PALETTE_CMDS = ["/new", "/sessions", "/models", "/themes", "/compact",
                "/details", "/thinking", "/undo", "/redo", "/export",
                "/editor", "/init", "/help", "/exit"]


def _box(lines, W, title="", color=None):
    """Floating dialog, horizontally centered. Content is clipped to fit."""
    c = color or _c("accent")
    avail = max(20, W - 4)                     # leave a 2-col margin each side
    widest = max([dlen(ln) for ln in lines] + [dlen(title) + 4])
    inner = min(avail - 2, max(30, widest + 2))  # inner = space between borders
    left = " " * max(0, (W - inner - 2) // 2)

    out = []
    if title:
        t = " " + title + " "
        fill = inner - dlen(t)
        lhs = max(1, fill // 2)
        rhs = max(1, fill - lhs)
        top = G.tl + G.h * lhs + t + G.h * rhs + G.tr
    else:
        top = G.tl + G.h * inner + G.tr
    out.append(left + c + top + RESET)

    for ln in lines:
        body = ln if dlen(ln) <= inner - 2 else clip(ln, inner - 2)
        pad = " " * max(0, inner - 2 - dlen(body))
        out.append(left + c + G.v + RESET + " " + body + pad
                   + " " + c + G.v + RESET)

    out.append(left + c + G.bl + G.h * inner + G.br + RESET)
    return out


def render_which_key(W):
    """Which-key overlay listing leader continuations."""
    lines = [_c("muted") + "ctrl+x  " + RESET + _c("dim") + "—  leader" + RESET]
    for key, (action, desc) in sorted(LEADER_MAP.items()):
        lines.append(_c("accent") + "  " + key + RESET
                     + "  " + _c("text") + desc + RESET)
    lines.append("")
    lines.append(_c("dim") + "  ctrl+p  command palette" + RESET)
    lines.append(_c("dim") + "  ctrl+t  cycle model variant" + RESET)
    return _box(lines, W, "keybinds", _c("border"))


def render_help(W):
    lines = [
        _c("text") + "Commands" + RESET,
        "",
        _c("muted") + "  /new /clear          " + RESET + "new session",
        _c("muted") + "  /sessions /resume     " + RESET + "session list",
        _c("muted") + "  /models               " + RESET + "model picker",
        _c("muted") + "  /themes               " + RESET + "theme picker",
        _c("muted") + "  /compact /summarize   " + RESET + "compact session",
        _c("muted") + "  /details              " + RESET + "toggle tool output",
        _c("muted") + "  /thinking             " + RESET + "toggle reasoning",
        _c("muted") + "  /undo  /redo          " + RESET + "undo/redo last message",
        _c("muted") + "  /export               " + RESET + "export to markdown",
        _c("muted") + "  /key <sk-...>         " + RESET + "set API key",
        _c("muted") + "  /model <id>           " + RESET + "set model",
        _c("muted") + "  /stats                " + RESET + "token count",
        _c("muted") + "  /exit /quit /q        " + RESET + "quit",
        "",
        _c("text") + "Input" + RESET,
        "",
        _c("muted") + "  @file                 " + RESET + "attach file contents",
        _c("muted") + "  !cmd                  " + RESET + "run shell command",
        _c("muted") + "  \\<newline>            " + RESET + "multi-line input",
        "",
        _c("text") + "Keys" + RESET,
        "",
        _c("muted") + "  ctrl+x <key>          " + RESET + "leader (see ctrl+alt+k)",
        _c("muted") + "  ctrl+p                " + RESET + "command palette",
        _c("muted") + "  ctrl+t                " + RESET + "cycle model variant",
        _c("muted") + "  ctrl+r                " + RESET + "rename session",
        _c("muted") + "  ctrl+d                " + RESET + "delete session",
        _c("muted") + "  Tab                   " + RESET + "cycle agent (plan/build)",
        _c("muted") + "  Esc                   " + RESET + "interrupt / close dialog",
        _c("muted") + "  pgup/pgdn             " + RESET + "scroll messages",
    ]
    return _box(lines, W, "help", _c("border"))


def render_model_picker(models, sel, W):
    lines = []
    for i, m in enumerate(models):
        if i == sel:
            lines.append(_c("accent") + G.diamond + " " + RESET
                         + _c("text") + BOLD + m + RESET)
        else:
            lines.append("  " + _c("muted") + m + RESET)
    lines.append("")
    lines.append(_c("dim") + "  ↑↓ select  Enter confirm  Esc cancel" + RESET)
    return _box(lines, W, "models", _c("border"))


def render_theme_picker(sel, W):
    names = list(THEMES.keys())
    lines = []
    for i, name in enumerate(names):
        if i == sel:
            lines.append(_c("accent") + G.diamond + " " + RESET
                         + _c("text") + BOLD + name + RESET)
        else:
            lines.append("  " + _c("muted") + name + RESET)
    lines.append("")
    lines.append(_c("dim") + "  ↑↓ select  Enter confirm  Esc cancel" + RESET)
    return _box(lines, W, "themes", _c("border"))


def render_session_picker(sessions, sel, W):
    """sessions: list of (id, title, updated, count, preview)"""
    lines = []
    for i, (sid, title, updated, count, preview) in enumerate(sessions[:20]):
        sub = "%s  %d msgs" % (rel_time(updated), count)
        if i == sel:
            lines.append(_c("accent") + G.diamond + " " + RESET
                         + _c("text") + BOLD + one_line(title, 36) + RESET
                         + "  " + _c("muted") + sub + RESET)
        else:
            lines.append("  " + _c("muted") + one_line(title, 36) + RESET
                         + "  " + _c("dim") + sub + RESET)
    if not sessions:
        lines.append("  " + _c("dim") + "no sessions yet" + RESET)
    lines.append("")
    lines.append(_c("dim") + "  ↑↓ select  Enter open  ctrl+d delete  Esc cancel" + RESET)
    return _box(lines, W, "sessions", _c("border"))


def render_palette(cmds, query, sel, W):
    filtered = [c for c in cmds if query.lower() in c.lower()] or cmds
    lines = [_c("accent") + G.prompt + " " + RESET + _c("text") + query + RESET
             + _c("muted") + G.cursor + RESET]
    lines.append("")
    for i, cmd in enumerate(filtered[:12]):
        desc = SLASH_COMMANDS.get(cmd, "")
        if i == sel:
            lines.append(_c("accent") + G.diamond + " " + RESET
                         + _c("text") + BOLD + cmd + RESET
                         + "  " + _c("muted") + desc + RESET)
        else:
            lines.append("  " + _c("muted") + cmd + RESET
                         + "  " + _c("dim") + desc + RESET)
    lines.append("")
    lines.append(_c("dim") + "  ↑↓ select  Enter run  Esc cancel" + RESET)
    return _box(lines, W, "palette", _c("border"))


def render_permission_dialog(category, key, sel, W):
    label = "run command" if category == "cmd" else "file access"
    lines = [
        _c("warn") + G.warn + " permission required" + RESET,
        "",
        _c("muted") + "  " + label + ": " + RESET + _c("text") + one_line(key, 50) + RESET,
        "",
    ]
    opts = [("once", "allow once"), ("session", "allow session"),
            ("always", "always allow"), ("reject", "reject")]
    for i, (val, desc) in enumerate(opts):
        if i == sel:
            lines.append(_c("accent") + G.diamond + " " + RESET
                         + _c("text") + BOLD + desc + RESET)
        else:
            lines.append("  " + _c("muted") + desc + RESET)
    lines.append("")
    lines.append(_c("dim") + "  ↑↓ select  Enter confirm" + RESET)
    return _box(lines, W, "permission", _c("warn"))

# ---------------------------------------------------------------- app

class App:
    """The TUI. Holds all state, owns the frame loop and the input router."""

    def __init__(self, cfg):
        global ui
        ui = self
        self.cfg = cfg
        self.api_key = get_api_key(cfg)
        self.model = cfg.get("model", DEFAULT_MODEL)
        self.mode = cfg.get("mode", "build")
        self.plain = PLAIN_MODE or not sys.stdin.isatty()
        theme.load(cfg.get("theme", "opencode"))

        self.session = Session.new()
        self.session.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.session.model = self.model

        self.buf = ""
        self.history = []
        self.hist_idx = 0
        self.scroll = 0
        self.notices = []
        self.tool_metas = {}          # msg index -> [tool meta dicts]
        self.session_perm = {}
        self.root_mode = False

        # overlay state: None | 'help' | 'models' | 'themes' | 'sessions'
        #                | 'palette' | 'whichkey' | 'perm' | 'rename' | 'confirm'
        self.overlay = None
        self.sel = 0
        self.palette_query = ""
        self.rename_buf = ""
        self.perm_result = None
        self.confirm_cb = None

        self.leader = False
        self.leader_at = 0.0
        self.home_sel = -1          # home screen session selector (-1 = none)

        self.streaming = False
        self.cancel = False
        self.spin = 0
        self.stream_tokens = 0
        self.stream_start = 0.0
        self.acc = ""
        self.think_start = 0.0
        self.think_secs = None

        self.undo_stack = []
        self.redo_stack = []
        self.branch = git_branch()
        self.running = True
        self.W, self.H = term_size()
        self._tool_running = None

    # -------------------------------------------------- notices

    def notice(self, kind, text):
        self.notices.append((kind, text, time.time()))
        self.notices = self.notices[-3:]

    def _notice_lines(self):
        out = []
        for kind, text, _ in self.notices:
            color = {"err": _c("err"), "warn": _c("warn")}.get(kind, _c("muted"))
            icon = {"err": G.no, "warn": G.warn}.get(kind, G.diamond)
            for ln in wrap_text(text, self.W - 6):
                out.append("  " + color + icon + " " + ln + RESET)
        return out

    # -------------------------------------------------- terminal

    def enter(self):
        global TERM_RAW
        if self.plain:
            return
        sys.stdout.write(ALT_ON + HIDE_CUR + MOUSE_ON)
        sys.stdout.flush()
        if termios and sys.stdin.isatty():
            self._old_term = termios.tcgetattr(sys.stdin.fileno())
            tty.setraw(sys.stdin.fileno())
            TERM_RAW = True

        def on_resize(sig, frame):
            self.W, self.H = term_size()
            self.redraw()
        try:
            signal.signal(signal.SIGWINCH, on_resize)
        except (ValueError, AttributeError):
            pass

    def exit_term(self):
        global TERM_RAW
        if self.plain:
            return
        TERM_RAW = False
        if termios and sys.stdin.isatty() and hasattr(self, "_old_term"):
            termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._old_term)
        sys.stdout.write(MOUSE_OFF + SHOW_CUR + ALT_OFF)
        sys.stdout.flush()

    # -------------------------------------------------- frames

    def redraw(self):
        if self.plain:
            return
        self.W, self.H = term_size()
        lines = self.frame_chat() if self.session.visible() else self.frame_home()
        render_frame(lines, self.W, self.H)

    def frame_home(self):
        W, H = self.W, self.H
        lines = [hdr_line("voxel", "v" + VERSION, W), sep_line(W), ""]
        logo = [
            "██╗   ██╗ ██████╗ ██╗  ██╗███████╗██╗",
            "██║   ██║██╔═══██╗╚██╗██╔╝██╔════╝██║",
            "╚██╗ ██╔╝██║   ██║ ╚███╔╝ █████╗  ██║",
            " ╚████╔╝ ██║   ██║ ██╔██╗ ██╔══╝  ██║",
            "  ╚██╔╝  ╚██████╔╝██╔╝ ██╗███████╗███████╗",
            "   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚══════╝╚══════╝",
        ]
        if H > 20 and W >= 48 and not SAFE_FONTS:
            for ln in logo:
                lines.append("  " + _c("accent") + ln + RESET)
        else:
            lines.append("  " + _c("accent") + G.diamond + " " + BOLD + "voxel"
                         + RESET + "  " + _c("muted") + "v" + VERSION + RESET)
        lines.append("")
        lines.append("  " + _c("dim") + clip("AI agent CLI for Termux", W - 4)
                     + RESET)
        lines.append("")
        lines.append("  " + _c("muted") + "cwd    " + RESET
                     + _c("dim") + clip(short_cwd(), W - 13) + RESET)
        lines.append("  " + _c("muted") + "model  " + RESET
                     + _c("dim") + clip(self.model, W - 13) + RESET)
        lines.append("")

        recent = list_sessions(5)
        if recent and H > 18:
            lines.append("  " + _c("muted") + "recent" + RESET
                         + _c("dim") + "  (↑↓ select · enter open)" + RESET)
            if self.home_sel > len(recent) - 1:
                self.home_sel = len(recent) - 1
            for i, (sid, title, updated, count, _) in enumerate(recent):
                when = rel_time(updated)
                room = W - 8 - dlen(when)
                if room < 8:
                    break
                active = (i == self.home_sel)
                mark = G.diamond if active else G.ring
                c = _c("build") if active else _c("dim")
                t = _c("text") if active else _c("muted")
                lines.append("  " + c + mark + " " + RESET
                             + t + one_line(title, room) + RESET
                             + "  " + _c("dim") + when + RESET)
            lines.append("")

        # hint line: shed items as the terminal narrows
        hints = ["/help commands", "ctrl+p palette", "ctrl+x leader",
                 "Tab plan/build"]
        while hints and dlen("  ".join(hints)) > W - 4:
            hints.pop()
        if hints:
            lines.append("  " + _c("dim") + "  ".join(hints) + RESET)
        lines += self._notice_lines()

        body_max = max(1, H - len(lines) - 5)
        lines += [""] * body_max
        lines += render_editor_box(self.buf, W, self.mode, self._cursor_on(),
                                   "Type a message, /help for commands")
        lines.append(render_status_bar(self.mode, self.model, 0, 0, W,
                                       branch=self.branch))
        return self._apply_overlay(lines)

    def _cursor_on(self):
        return int(time.time() * 1000) % 1060 < 530

    def frame_chat(self):
        W, H = self.W, self.H
        sess = self.session
        title = one_line(sess.title, max(10, W - 30))
        tok = sess.tokens["in"] + sess.tokens["out"]
        lines = [hdr_line(title, "%d msgs" % len(sess.visible()), W), sep_line(W)]

        body = []
        for i, msg in enumerate(sess.messages):
            role = msg.get("role")
            if role == "system":
                continue
            text = msg.get("content", "")
            if text.startswith("[tool "):
                continue
            ts = ""
            if self.cfg.get("timestamps") and msg.get("time"):
                ts = time.strftime("%H:%M", time.localtime(msg["time"]))
            if role == "user":
                body += render_user_msg(text, W, ts)
                body.append("")
            elif role == "assistant":
                body += render_assistant_msg(
                    text, W, msg.get("model", self.model), ts,
                    msg.get("think") if self.cfg.get("show_thinking") else None,
                    self.tool_metas.get(i, []),
                    self.cfg.get("tool_details", True))
                body.append("")

        # live streaming block
        if self.streaming:
            if self.acc:
                # mask half-open <write>... content so code never flashes
                # on screen while the closing tag is still streaming
                disp_acc = mask_write_code(self.acc)
                body += render_assistant_msg(disp_acc, W, self.model, "",
                                             self.think_secs, [], False)
                # if the streamed content is only tool tags (no prose yet),
                # show the pending tool calls so the screen isn't blank
                if not TOOL_RE.sub("", disp_acc).strip() or \
                        self.acc.count("<write") > self.acc.count("</write>"):
                    partial = None
                    if self.acc.count("<write") > self.acc.count("</write>"):
                        pm = re.search(r"<write\b([^>]*)>", self.acc)
                        path = ""
                        if pm and pm.group(1).strip():
                            am = re.search(r'path="([^"]*)"', pm.group(1))
                            if am:
                                path = am.group(1)
                        partial = "write " + one_line(path, 40) if path else "write"
                    for tname, tattrs, tcontent in parse_tools(self.acc):
                        targ = tool_arg(tname, tattrs, tcontent)
                        if tname == "write":
                            # writing files stays in the background: just show
                            # a small loading indicator, not the code itself
                            dots = "." * (self.spin % 4)
                            body.append("  " + _tool_line(tname, targ, ""))
                            body.append("  " + _c("muted") + G.bar + RESET
                                        + " " + DIM + _c("muted")
                                        + "writing" + dots + " " * (3 - len(dots))
                                        + RESET)
                        else:
                            body.append("  " + _tool_line(tname, targ, ""))
                    if partial:
                        dots = "." * (self.spin % 4)
                        body.append("  " + _tool_line(*partial.split(None, 1))
                                    if " " in partial
                                    else "  " + _tool_line("write", "", ""))
                        body.append("  " + _c("muted") + G.bar + RESET
                                    + " " + DIM + _c("muted")
                                    + "writing" + dots + " " * (3 - len(dots))
                                    + RESET)
            else:
                # reasoning/thinking phase — model hasn't sent content yet
                body.append("  " + _c("accent") + G.diamond + RESET
                            + "  " + DIM + _c("muted") + "thinking\u2026" + RESET)

        body += self._notice_lines()

        avail = max(1, H - 6)
        if len(body) > avail:
            end = len(body) - self.scroll
            body = body[max(0, end - avail):max(1, end)]
        else:
            self.scroll = 0
            body += [""] * (avail - len(body))
        lines += body
        lines += render_editor_box(self.buf, W, self.mode, self._cursor_on())
        speed = 0
        if self.streaming and self.stream_start:
            el = time.time() - self.stream_start
            speed = self.stream_tokens / el if el > 0.3 else 0
        lines.append(render_status_bar(self.mode, self.model, sess.tokens["in"],
                                       sess.tokens["out"], W, self.streaming,
                                       self.spin, speed, self.branch))
        return self._apply_overlay(lines)

    def _apply_overlay(self, lines):
        """Composite a dialog box over the frame, vertically centered."""
        box = None
        if self.overlay == "help":
            box = render_help(self.W)
        elif self.overlay == "whichkey":
            box = render_which_key(self.W)
        elif self.overlay == "models":
            box = render_model_picker(self._models(), self.sel, self.W)
        elif self.overlay == "themes":
            box = render_theme_picker(self.sel, self.W)
        elif self.overlay == "sessions":
            box = render_session_picker(self._sessions_cache, self.sel, self.W)
        elif self.overlay == "palette":
            box = render_palette(PALETTE_CMDS, self.palette_query, self.sel, self.W)
        elif self.overlay == "perm":
            box = render_permission_dialog(self._perm_cat, self._perm_key,
                                           self.sel, self.W)
        elif self.overlay == "rename":
            box = _box([_c("text") + self.rename_buf + RESET
                        + _c("accent") + G.cursor + RESET, "",
                        _c("dim") + "  Enter save  Esc cancel" + RESET],
                       self.W, "rename session", _c("border"))
        elif self.overlay == "confirm":
            box = _box([_c("text") + self._confirm_msg + RESET, "",
                        _c("dim") + "  y confirm  n/Esc cancel" + RESET],
                       self.W, "confirm", _c("warn"))
        if not box:
            return lines
        top = max(2, (self.H - len(box)) // 2)
        out = list(lines)
        while len(out) < top + len(box):
            out.append("")
        for i, bl in enumerate(box):
            out[top + i] = bl
        return out

    def _models(self):
        return FREE_MODELS

    def do_action(self, action):
        if action == "exit":
            self.running = False
        elif action == "new":
            self.cmd_new()
        elif action == "sessions":
            self._sessions_cache = list_sessions()
            self.sel = 0
            self.overlay = "sessions"
        elif action == "models":
            self.sel = max(0, self._models().index(self.model)
                           if self.model in self._models() else 0)
            self.overlay = "models"
        elif action == "themes":
            names = list(THEMES.keys())
            self.sel = names.index(theme.name) if theme.name in names else 0
            self.overlay = "themes"
        elif action == "agents":
            self.toggle_mode()
        elif action == "editor":
            self.cmd_editor()
        elif action == "compact":
            self.cmd_compact()
        elif action == "export":
            self.cmd_export()
        elif action == "undo":
            self.cmd_undo()
        elif action == "redo":
            self.cmd_redo()
        elif action == "details":
            self.cfg["tool_details"] = not self.cfg.get("tool_details", True)
            save_config(self.cfg)
            self.notice("info", "tool details %s"
                        % ("on" if self.cfg["tool_details"] else "off"))
        elif action == "tips" or action == "help":
            self.overlay = "help"
        elif action == "status":
            self.cmd_stats()
        elif action == "copy":
            self.cmd_copy()
        elif action in ("sidebar", "timeline"):
            self.notice("info", "%s: not available in this build" % action)

    # -------------------------------------------------- input router

    def input_loop(self):
        self._sessions_cache = []
        while self.running:
            self.redraw()
            # leader timeout: drop the pending leader after 2s (opencode default)
            if self.leader and time.time() - self.leader_at > LEADER_TIMEOUT:
                self.leader = False
                if self.overlay == "whichkey":
                    self.overlay = None
            r, _, _ = select.select([sys.stdin], [], [], 0.4)
            if not r:
                continue
            key = raw_key()
            if not key:
                continue
            try:
                self.on_key(key)
            except Exception as e:
                self.notice("err", "internal: %s" % (e,))

    def on_key(self, key):
        if self.leader:
            if key == "C-x":          # re-arm rather than swallow
                self.leader_at = time.time()
                return
            self.leader = False
            if self.overlay == "whichkey":
                self.overlay = None
            if key == "ESC":
                return
            action = LEADER_MAP.get(key.lower())
            if action:
                self.do_action(action[0])
            return

        if self.overlay:
            self.on_key_overlay(key)
            return

        # home screen session selector: ↑↓ move, enter opens, typing clears
        if not self.session.visible():
            recent = list_sessions(5)
            n = len(recent)
            if key in ("UP", "DOWN") and n:
                if self.home_sel < 0:
                    self.home_sel = 0 if key == "DOWN" else n - 1
                elif key == "UP":
                    self.home_sel = (self.home_sel - 1) % n
                else:
                    self.home_sel = (self.home_sel + 1) % n
                self.redraw()
                return
            if key == "ENTER" and 0 <= self.home_sel < n:
                self.open_session(recent[self.home_sel][0])
                self.home_sel = -1
                return
            if key not in ("UP", "DOWN", "ENTER") and self.home_sel >= 0:
                self.home_sel = -1      # typing / other keys clear the selector

        if key == "C-x":
            self.leader = True
            self.leader_at = time.time()
            return
        if key == "C-alt-k" or key == "M-k":
            self.overlay = "whichkey"
            return
        if key == "C-p":
            self.overlay = "palette"
            self.palette_query = ""
            self.sel = 0
            return
        if key == "C-c":
            if self.buf:
                self.buf = ""
            else:
                self.running = False
            return
        if key == "C-t":
            self.cycle_model()
            return
        if key == "C-r":
            self.overlay = "rename"
            self.rename_buf = self.session.title
            return
        if key == "C-d":
            if self.buf:
                return
            if not self.session.visible():
                self.running = False
                return
            self.ask_confirm("delete this session?", self._do_delete_session)
            return
        if key == "TAB":
            self.toggle_mode()
            return
        if key == "ENTER":
            text = self.buf.strip()
            if text.endswith("\\"):          # multi-line continuation
                self.buf = self.buf[:-1] + "\n"
                return
            if not text:
                return
            self.buf = ""
            self.history.append(text)
            self.hist_idx = len(self.history)
            self.submit(text)
            return
        if key == "BACK":
            self.buf = self.buf[:-1]
            return
        if key == "C-u":
            self.buf = ""
            return
        if key == "C-w":
            self.buf = re.sub(r"\S*\s*$", "", self.buf)
            return
        if key == "C-k":
            self.buf = ""
            return
        if key == "ESC":
            self.scroll = 0
            return
        if key in ("UP", "C-p"):
            if self.history and self.hist_idx > 0:
                self.hist_idx -= 1
                self.buf = self.history[self.hist_idx]
            return
        if key == "DOWN":
            if self.history and self.hist_idx < len(self.history) - 1:
                self.hist_idx += 1
                self.buf = self.history[self.hist_idx]
            else:
                self.hist_idx = len(self.history)
                self.buf = ""
            return
        if key in ("PGUP", "WHEEL_UP"):
            self.scroll += 5
            return
        if key in ("PGDN", "WHEEL_DOWN"):
            self.scroll = max(0, self.scroll - 5)
            return
        if key == "M-enter":
            self.buf += "\n"
            return
        if len(key) == 1 and (key.isprintable() or ord(key) >= 160):
            self.buf += key

    def on_key_overlay(self, key):
        ov = self.overlay

        if ov == "perm":
            if key in ("UP", "LEFT"):
                self.sel = max(0, self.sel - 1)
            elif key in ("DOWN", "RIGHT"):
                self.sel = min(3, self.sel + 1)
            elif key == "ENTER":
                self.perm_result = ["once", "session", "always", "reject"][self.sel]
                self.overlay = None
            elif key in ("ESC", "C-c", "q"):
                self.perm_result = "reject"
                self.overlay = None
            return

        if ov == "rename":
            if key == "ENTER":
                new = self.rename_buf.strip()
                if new:
                    self.session.title = new
                    self.session.save()
                self.overlay = None
            elif key == "BACK":
                self.rename_buf = self.rename_buf[:-1]
            elif key in ("ESC", "C-c"):
                self.overlay = None
            elif len(key) == 1 and key.isprintable():
                self.rename_buf += key
            return

        if ov == "confirm":
            if key in ("y", "Y", "ENTER"):
                self.overlay = None
                if self.confirm_cb:
                    self.confirm_cb()
                self.confirm_cb = None
            elif key in ("n", "N", "ESC", "C-c"):
                self.overlay = None
                self.confirm_cb = None
            return

        if ov == "palette":
            filtered = [c for c in PALETTE_CMDS
                        if self.palette_query.lower() in c.lower()] or PALETTE_CMDS
            if key == "ENTER":
                self.overlay = None
                if filtered:
                    self.run_slash(filtered[min(self.sel, len(filtered) - 1)])
            elif key in ("ESC", "C-c"):
                self.overlay = None
            elif key == "UP":
                self.sel = max(0, self.sel - 1)
            elif key == "DOWN":
                self.sel = min(len(filtered) - 1, self.sel + 1)
            elif key == "BACK":
                self.palette_query = self.palette_query[:-1]
                self.sel = 0
            elif len(key) == 1 and key.isprintable():
                self.palette_query += key
                self.sel = 0
            return

        # list-style overlays
        if key in ("ESC", "C-c", "q"):
            self.overlay = None
            return
        if key == "UP":
            self.sel = max(0, self.sel - 1)
            return
        if key == "DOWN":
            self.sel += 1
            return
        if key == "ENTER":
            if ov == "models":
                models = self._models()
                if models:
                    self.set_model(models[min(self.sel, len(models) - 1)])
            elif ov == "themes":
                names = list(THEMES.keys())
                name = names[min(self.sel, len(names) - 1)]
                theme.load(name)
                self.cfg["theme"] = name
                save_config(self.cfg)
                self.notice("info", "theme: " + name)
            elif ov == "sessions":
                if self._sessions_cache:
                    sid = self._sessions_cache[min(self.sel,
                                                   len(self._sessions_cache) - 1)][0]
                    self.open_session(sid)
            self.overlay = None
            return
        if key == "C-d" and ov == "sessions" and self._sessions_cache:
            sid, title = self._sessions_cache[min(
                self.sel, len(self._sessions_cache) - 1)][:2]

            def kill():
                sess = Session.load(sid)
                if sess:
                    sess.delete()
                self._sessions_cache = list_sessions()
                self.notice("info", "deleted: " + one_line(title, 30))
                self.overlay = "sessions"
            self.ask_confirm("delete '%s'?" % one_line(title, 30), kill)
            return
        if ov == "models":
            self.sel = min(self.sel, max(0, len(self._models()) - 1))
        elif ov == "themes":
            self.sel = min(self.sel, len(THEMES) - 1)
        elif ov == "sessions":
            self.sel = min(self.sel, max(0, len(self._sessions_cache) - 1))

    def ask_confirm(self, msg, cb):
        self._confirm_msg = msg
        self.confirm_cb = cb
        self.overlay = "confirm"

    # -------------------------------------------------- permission dialog

    def permission_dialog(self, category, key):
        """Blocking modal used by check_perm from the agent thread's caller."""
        self._perm_cat = category
        self._perm_key = key
        self.sel = 0
        self.perm_result = None
        self.overlay = "perm"
        while self.overlay == "perm" and self.running:
            self.redraw()
            r, _, _ = select.select([sys.stdin], [], [], 0.3)
            if r:
                k = raw_key()
                if k:
                    self.on_key_overlay(k)
        return self.perm_result or "reject"

    # -------------------------------------------------- session ops

    def open_session(self, sid):
        sess = Session.load(sid)
        if not sess:
            self.notice("err", "session not found: " + sid)
            return
        self.session = sess
        self.model = sess.model or self.model
        self.tool_metas = {}
        self.scroll = 0
        self.notices = []

    def cmd_new(self):
        if self.session.visible():
            self.session.save()
        self.session = Session.new()
        self.session.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.session.model = self.model
        self.tool_metas = {}
        self.scroll = 0
        self.notices = []
        self.undo_stack = []
        self.redo_stack = []

    def _do_delete_session(self):
        self.session.delete()
        self.cmd_new()
        self.notice("info", "session deleted")

    def toggle_mode(self):
        self.mode = "plan" if self.mode == "build" else "build"
        self.cfg["mode"] = self.mode
        save_config(self.cfg)

    def set_model(self, model):
        self.model = model
        self.cfg["model"] = model
        self.session.model = model
        save_config(self.cfg)
        self.notice("info", "model: " + model)

    def cycle_model(self):
        models = self._models()
        idx = models.index(self.model) if self.model in models else -1
        self.set_model(models[(idx + 1) % len(models)])

    def cmd_stats(self):
        tok = self.session.tokens
        self.notice("info", "in: %s  out: %s  total: %s"
                    % (fmt_tok(tok["in"]), fmt_tok(tok["out"]),
                       fmt_tok(tok["in"] + tok["out"])))

    def cmd_copy(self):
        for msg in reversed(self.session.messages):
            if msg.get("role") == "assistant":
                text = TOOL_RE.sub("", msg.get("content", "")).strip()
                try:
                    subprocess.run(["termux-clipboard-set"], input=text,
                                   text=True, timeout=5)
                    self.notice("info", "copied to clipboard")
                except Exception:
                    self.notice("warn", "termux-clipboard-set not available")
                return

    def cmd_compact(self):
        visible = self.session.visible()
        if not visible:
            return
        summary = "Session compacted. %d messages summarized." % len(visible)
        self.session.messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "assistant", "content": summary},
        ]
        self.tool_metas = {}
        self.notice("info", "session compacted")

    def cmd_export(self):
        lines = ["# %s\n" % self.session.title]
        for msg in self.session.messages:
            role = msg.get("role")
            if role == "system":
                continue
            text = TOOL_RE.sub("", msg.get("content", "")).strip()
            if not text:
                continue
            lines.append("**%s**\n\n%s\n" % (role, text))
        out = "\n---\n\n".join(lines)
        path = os.path.join(CONFIG_DIR, "export-%s.md" % self.session.id)
        try:
            with open(path, "w") as f:
                f.write(out)
            self.notice("info", "exported: " + path)
        except OSError as e:
            self.notice("err", str(e))

    def cmd_editor(self):
        editor = os.environ.get("EDITOR", "nano")
        tmp = os.path.join(CONFIG_DIR, "editor-input.txt")
        try:
            with open(tmp, "w") as f:
                f.write(self.buf)
            self.exit_term()
            subprocess.run([editor, tmp])
            self.enter()
            with open(tmp) as f:
                self.buf = f.read().rstrip("\n")
        except Exception as e:
            self.notice("err", "editor: %s" % (e,))

    def cmd_undo(self):
        visible = self.session.visible()
        if not visible:
            return
        snap = {"messages": list(self.session.messages),
                "tokens": dict(self.session.tokens)}
        self.redo_stack.append(snap)
        # drop last user + assistant pair
        msgs = list(self.session.messages)
        while msgs and msgs[-1].get("role") in ("assistant", "tool"):
            msgs.pop()
        if msgs and msgs[-1].get("role") == "user":
            msgs.pop()
        self.session.messages = msgs
        self.notice("info", "undo: last message removed")

    def cmd_redo(self):
        if not self.redo_stack:
            self.notice("warn", "nothing to redo")
            return
        snap = self.redo_stack.pop()
        self.undo_stack.append({"messages": list(self.session.messages),
                                "tokens": dict(self.session.tokens)})
        self.session.messages = snap["messages"]
        self.session.tokens = snap["tokens"]
        self.notice("info", "redo applied")

    # -------------------------------------------------- slash commands

    def run_slash(self, text):
        parts = text.strip().split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("/exit", "/quit", "/q"):
            self.running = False
        elif cmd in ("/new", "/clear"):
            self.cmd_new()
        elif cmd in ("/sessions", "/resume", "/continue"):
            self._sessions_cache = list_sessions()
            self.sel = 0
            self.overlay = "sessions"
        elif cmd == "/models":
            self.sel = max(0, self._models().index(self.model)
                           if self.model in self._models() else 0)
            self.overlay = "models"
        elif cmd == "/model":
            if arg:
                self.set_model(arg)
            else:
                self.overlay = "models"
                self.sel = 0
        elif cmd == "/themes":
            names = list(THEMES.keys())
            self.sel = names.index(theme.name) if theme.name in names else 0
            self.overlay = "themes"
        elif cmd in ("/compact", "/summarize"):
            self.cmd_compact()
        elif cmd == "/details":
            self.cfg["tool_details"] = not self.cfg.get("tool_details", True)
            save_config(self.cfg)
            self.notice("info", "tool details %s"
                        % ("on" if self.cfg["tool_details"] else "off"))
        elif cmd == "/thinking":
            self.cfg["show_thinking"] = not self.cfg.get("show_thinking", True)
            save_config(self.cfg)
            self.notice("info", "thinking display %s"
                        % ("on" if self.cfg["show_thinking"] else "off"))
        elif cmd == "/undo":
            self.cmd_undo()
        elif cmd == "/redo":
            self.cmd_redo()
        elif cmd == "/export":
            self.cmd_export()
        elif cmd == "/editor":
            self.cmd_editor()
        elif cmd == "/help":
            self.overlay = "help"
        elif cmd == "/stats":
            self.cmd_stats()
        elif cmd == "/key":
            if arg:
                self.cfg["api_key"] = arg
                self.api_key = arg
                save_config(self.cfg)
                self.notice("info", "API key saved")
            else:
                self.notice("warn", "usage: /key <sk-...>")
        elif cmd == "/perm":
            self._handle_perm_cmd(arg)
        elif cmd == "/root":
            self.root_mode = not self.root_mode
            self.notice("info", "root mode %s" % ("on" if self.root_mode else "off"))
        elif cmd == "/init":
            self.submit("Create or update an AGENTS.md file for this project "
                        "at " + os.getcwd())
        else:
            self.notice("warn", "unknown command: " + cmd)

    def _handle_perm_cmd(self, arg):
        parts = arg.split()
        if not parts or parts[0] == "show":
            perm = self.cfg.get("perm", {})
            self.notice("info", "cmd: %s  file: %s"
                        % (perm.get("default_cmd", "ask"),
                           perm.get("default_file", "ask")))
            return
        if parts[0] == "reset":
            self.cfg["perm"] = {}
            save_config(self.cfg)
            self.notice("info", "permissions reset")
            return
        if len(parts) >= 3 and parts[0] in ("cmd", "file"):
            cat, key, mode = parts[0], parts[1], parts[2]
            self.cfg.setdefault("perm", {}).setdefault(cat, {})[key] = mode
            save_config(self.cfg)
            self.notice("info", "perm %s %s = %s" % (cat, key, mode))

    # -------------------------------------------------- submit

    def submit(self, text):
        """Handle one user turn: @file expansion, !shell, slash, or AI."""
        # @file attachment
        text = self._expand_at_refs(text)
        # !shell prefix
        if text.startswith("!"):
            cmd = text[1:].strip()
            code, out = run_command(cmd)
            result = "$ %s\n%s" % (cmd, truncate(out))
            self.session.messages.append(
                {"role": "user", "content": result, "time": time.time()})
            self.session.messages.append(
                {"role": "assistant",
                 "content": "[tool run exit=%d]\n%s" % (code, truncate(out)),
                 "time": time.time(), "model": self.model})
            self.session.save()
            self.redraw()
            return
        # slash command
        if text.startswith("/"):
            self.run_slash(text)
            return
        # AI turn
        self.session.messages.append(
            {"role": "user", "content": text, "time": time.time()})
        self.session.save()
        self.scroll = 0
        self.redraw()
        try:
            self.run_turn()
        except Exception as e:
            self.notice("err", "unexpected: %s" % (e,))
        self.session.save()

    def _expand_at_refs(self, text):
        def replace(m):
            path = m.group(1)
            full = os.path.expanduser(path)
            if not os.path.isabs(full):
                full = os.path.join(os.getcwd(), full)
            try:
                with open(full, "r", errors="replace") as f:
                    content = f.read(64 * 1024)
                return "[file: %s]\n%s\n[/file]" % (path, content)
            except OSError:
                return m.group(0)
        return re.sub(r"@(\S+)", replace, text)

    # -------------------------------------------------- agent loop

    def stream_reply(self):
        """One model call, streamed. -> (content, reasoning, err, used_model)"""
        parts = []
        done = threading.Event()
        result = {}
        msgs = [m for m in self.session.messages]
        if self.mode == "plan":
            msgs = ([{"role": "system",
                      "content": SYSTEM_PROMPT + "\n\n" + PLAN_PROMPT}]
                    + [m for m in msgs if m.get("role") != "system"])
        # strip our own bookkeeping keys before sending
        wire = [{"role": m["role"], "content": m["content"]} for m in msgs]

        def on_chunk(kind, text):
            parts.append((kind, text))
            if kind == "content":
                if self.think_secs is None:
                    self.think_secs = time.time() - self.think_start
                self.acc += text
                self.stream_tokens = est_tokens(self.acc)

        def worker():
            result["err"], result["model"] = call_chat(
                wire, self.model, self.api_key, on_chunk)
            done.set()

        self.streaming = True
        self.cancel = False
        self.acc = ""
        self.think_start = time.time()
        self.think_secs = None
        self.stream_start = time.time()
        self.stream_tokens = 0
        esc_armed = False

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        try:
            interactive = sys.stdin.isatty()
            while t.is_alive() or not done.is_set():
                self.spin = (self.spin + 1) % len(SPINNER)
                self.redraw()
                if not interactive:
                    # piped/redirected stdin: never poll it — EOF would read as
                    # C-c and cancel the turn instantly. Just spin and wait.
                    time.sleep(0.12)
                    continue
                r, _, _ = select.select([sys.stdin], [], [], 0.12)
                if not r:
                    continue
                k = raw_key()
                if k == "C-c":
                    self.cancel = True
                    break
                if k == "ESC":
                    if esc_armed:
                        self.cancel = True
                        break
                    esc_armed = True
                    self.notice("warn", "press esc again to interrupt")
                elif k == "BACK":
                    self.buf = self.buf[:-1]
                elif k and len(k) == 1 and k.isprintable():
                    self.buf += k       # keep typing while it streams
        except KeyboardInterrupt:
            self.cancel = True
        finally:
            self.streaming = False
            self.acc = ""
            self.redraw()

        if self.cancel:
            return "", "", "cancelled", result.get("model") or self.model
        if result.get("err"):
            return "", "", result["err"], result.get("model")
        reasoning = "".join(x for kind, x in parts if kind == "reasoning")
        content = "".join(x for kind, x in parts if kind == "content")
        return content, reasoning, None, result.get("model")

    def run_turn(self):
        """Drive rounds of model call -> tool exec -> model call until done."""
        turn_start = time.time()
        exec_count = 0
        tool_sigs = []

        for _ in range(MAX_TOOL_ROUNDS):
            if self.cancel:
                self.notice("info", "cancelled")
                return
            content, reasoning, err, used = self.stream_reply()
            if used and used != self.model:
                self.model = used       # fallback switched models
            if err:
                if err == "cancelled":
                    self.notice("info", "cancelled")
                else:
                    self.notice("err", err)
                    if (self.session.messages
                            and self.session.messages[-1]["role"] == "user"):
                        pass            # keep the user msg so /undo still works
                return

            # reasoning is model output, not input — count both as "out"
            self.session.tokens["out"] += est_tokens(content) + est_tokens(reasoning)

            tools = parse_tools(content)
            if not tools and not content.strip():
                self.notice("warn", "empty reply — try again")
                return

            msg = {"role": "assistant", "content": content,
                   "time": time.time(), "model": used or self.model}
            if self.think_secs is not None:
                msg["think"] = self.think_secs
            if reasoning.strip():
                msg["reasoning"] = reasoning
            self.session.messages.append(msg)
            msg_idx = len(self.session.messages) - 1

            if not tools:
                self.session.save()
                self.redraw()
                return

            # loop guard: identical tool signature 20 rounds running
            sig = tuple((n, one_line(a.get("path") or c or "", 60))
                        for n, a, c in tools)
            tool_sigs.append(sig)
            if len(tool_sigs) >= 20 and tool_sigs[-1] == tool_sigs[-2] == tool_sigs[-3]:
                self.notice("warn", "same tool 20x — loop stopped")
                return
            if time.time() - turn_start > TURN_TIME_BUDGET:
                self.notice("warn", "turn time budget exceeded — stopped")
                return

            metas = []
            results = []
            for name, attrs, tcontent in tools:
                if exec_count >= MAX_TOOL_EXECS:
                    self.notice("warn", "tool limit reached (%d)" % MAX_TOOL_EXECS)
                    break
                exec_count += 1
                arg = tool_arg(name, attrs, tcontent)
                body = tcontent if name == "write" else arg

                self._tool_running = (name, arg)
                self.redraw()
                out, meta = exec_tool(self.cfg, name, arg, body,
                                      self.session_perm,
                                      auto=self.cfg.get("autoapprove", False),
                                      root=self.root_mode)
                self._tool_running = None
                meta = dict(meta or {})
                meta["name"] = name
                meta["arg"] = arg
                metas.append(meta)
                results.append(out)
                self.tool_metas.setdefault(msg_idx, []).append(meta)
                self.redraw()

            self.session.messages.append(
                {"role": "user", "content": "\n\n".join(results),
                 "time": time.time()})
            self.session.save()
            self.redraw()

        self.notice("info", "max rounds reached (%d)" % MAX_TOOL_ROUNDS)

    # -------------------------------------------------- run

    def run(self):
        if self.plain:
            return self.run_plain()
        self.enter()
        try:
            self.input_loop()
        except KeyboardInterrupt:
            pass
        finally:
            if self.session.visible():
                self.session.save()
            self.exit_term()
            print("  %s session saved: %s" % (G.diamond, self.session.title))

    def _plain_flush(self):
        """Print queued notices, and render any overlay as flat text."""
        for kind, text, _ in self.notices:
            print("  [%s] %s" % (kind, text))
        self.notices = []
        if not self.overlay:
            return
        box = None
        if self.overlay == "help":
            box = render_help(76)
        elif self.overlay == "models":
            box = render_model_picker(self._models(), self.sel, 76)
        elif self.overlay == "themes":
            box = render_theme_picker(self.sel, 76)
        elif self.overlay == "sessions":
            box = render_session_picker(getattr(self, "_sessions_cache", []),
                                       self.sel, 76)
        if box:
            for ln in box:
                print(ANSI_RE.sub("", ln).rstrip()[12:])
        self.overlay = None

    def run_plain(self):
        """Line-based fallback for pipes and dumb terminals."""
        print("voxel v%s — plain mode. /exit to quit." % VERSION)
        while self.running:
            try:
                text = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not text:
                continue
            if text.startswith("/"):
                self.run_slash(text)
                self._plain_flush()
                continue

            self.session.messages.append({"role": "user", "content": text,
                                          "time": time.time()})
            counted_in = 0   # track how many wire chars already counted
            for _ in range(MAX_TOOL_ROUNDS):
                wire = [{"role": m["role"], "content": m["content"]}
                        for m in self.session.messages]
                if self.mode == "plan":
                    wire[0] = {"role": "system",
                               "content": SYSTEM_PROMPT + "\n\n" + PLAN_PROMPT}
                chunks = []
                err, used = call_chat(
                    wire, self.model, self.api_key,
                    lambda kind, t: chunks.append(t) if kind == "content" else None)
                if err:
                    print("  error: " + err)
                    break
                reply = "".join(chunks)
                # only count tokens added since the previous round to avoid
                # double-counting the growing conversation history
                total_in = sum(len(m["content"]) for m in wire)
                new_chars = max(0, total_in - counted_in)
                self.session.tokens["in"] += max(1, new_chars // 4)
                counted_in = total_in
                self.session.tokens["out"] += est_tokens(reply)
                self.session.messages.append(
                    {"role": "assistant", "content": reply,
                     "time": time.time(), "model": used})
                prose = TOOL_RE.sub("", reply).strip()
                if prose:
                    print(prose)
                tools = parse_tools(reply)
                if not tools:
                    break
                # tools DO run in plain mode — otherwise the model would
                # claim work it never did
                for name, attrs, content in tools[:MAX_TOOL_EXECS]:
                    if self.mode == "plan" and name in ("run", "write"):
                        print("  (plan mode: %s skipped)" % name)
                        self.session.messages.append(
                            {"role": "user", "time": time.time(),
                             "content": "[tool %s: blocked in plan mode]" % name})
                        continue
                    arg = tool_arg(name, attrs, content)
                    print("  %s %s %s" % (G.arrow, name, one_line(arg, 50).lower()))
                    result, _meta = exec_tool(self.cfg, name, arg, content,
                                              self.session_perm,
                                              auto=self.cfg.get("autoapprove"),
                                              root=self.root_mode)
                    self.session.messages.append(
                        {"role": "user", "content": result, "time": time.time()})
        if self.session.visible():
            self.session.save()
            print("  %s saved: %s" % (G.diamond, self.session.title))


# ---------------------------------------------------------------- main

def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    cfg = load_config()

    if "--help" in sys.argv or "-h" in sys.argv:
        print(__doc__.strip())
        print("\nFlags:")
        print("  --plain         line-based mode, no TUI")
        print("  --safe-fonts    ASCII glyphs")
        print("  --models        list available models and exit")
        print("  --key <sk-...>  save an API key and exit")
        print("  --theme <name>  %s" % ", ".join(THEMES))
        return 0

    if "--key" in sys.argv:
        idx = sys.argv.index("--key")
        if idx + 1 < len(sys.argv):
            cfg["api_key"] = sys.argv[idx + 1]
            save_config(cfg)
            print("API key saved to " + CONFIG_FILE)
            return 0
        print("usage: --key <sk-...>")
        return 1

    if "--theme" in sys.argv:
        idx = sys.argv.index("--theme")
        if idx + 1 < len(sys.argv) and sys.argv[idx + 1] in THEMES:
            cfg["theme"] = sys.argv[idx + 1]
            save_config(cfg)

    if "--models" in sys.argv:
        try:
            for m in fetch_models(get_api_key(cfg)):
                print(m)
        except Exception as e:
            print("could not fetch models: %s" % (e,))
            print("\nbuilt-in free models:")
            for m in FREE_MODELS:
                print("  " + m)
        return 0

    os.makedirs(CONFIG_DIR, exist_ok=True)
    migrate_legacy()

    app = App(cfg)
    if args:                       # treat a bare arg as a first prompt
        app.buf = " ".join(args)
    app.run()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.stdout.write(MOUSE_OFF + SHOW_CUR + ALT_OFF)
        sys.exit(130)
