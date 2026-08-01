#!/usr/bin/env python3
"""
BangBot v2.0 - free AI agent CLI assistant for Termux
Powered by OpenCode Zen free models
Tools: run / read / write / ls / search | Permission system | Root support
Run:  python3 bangbot.py
"""

import html as html_mod
import json
import os
import re
import select
import shlex
import shutil
import signal
import subprocess
import sys
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

MAX_TOOL_ROUNDS = 8
CMD_TIMEOUT = 120
OUT_LIMIT = 3000

SYSTEM_PROMPT = """Tumi VOXEL AI - ekta AI agent CLI, cholte ache Termux (Android terminal) e.
Bangla o English dui language e reply koro. User Banglish e likhle tumi o Banglish e reply diba.
Answer chhoto, clear ar to-the-point hobe. Code thakle ``` block e diba.

TOOL USE (khub important):
Kono kaj korar dorkar hole, khali text diye korte jaibe na - ei tags use korbe:

<run>command</run>                        - Termux e command chalabe (ls, pwd, python3 etc)
<run root>command</run>                 - ROOT command (su) - e.g. chmod, mount, termux-fix-shebang
<read path="/path/to/file">x</read>     - file content dekhte
<write path="/path/to/file">content</write> - file likhte (content tag er vitore)
<ls>directory/path</ls>                - folder listing
<search>question</search>              - internet search

Rules:
- Root dorkar hote pare (su permission chai) — tahole <run root> use koro, user approve korbe.
- Phone e root na thakle <run root> kaj korbe na — tahole normal vabe kaj koro ar user ke bolo root lagbe.
- <search> always allowed — internet search kono permission chara cholbe (default capability).
- <read>/<ls> o default allowed (read-only). <write>/<run> e prompt asbe: Yes/No/Always (arrow diye select).
- Ekbare ekta tag use koro, result ashle tarpor aro kaj lagle abar tag use korbe.
- command chalano te warning/error thakle seta user ke bolo.
- 'termux-*' command available ache (termux-api installed thakle).
- Reply e nijer nam/shurur greeting (jemon "VOXEL AI bhalo achi", "ki kore help korte pari") force koro na — direct user er proshner jawab dao."""

C_RED = "\033[91m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_CYAN = "\033[96m"
C_MAG = "\033[95m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_RESET = "\033[0m"
CLEAR = "\x1b[2J\x1b[H"
SPINNER = "⣾⣽⣻⢿⡿⣟⣯⣷"

# opencode theme (truecolor)
C_BG = "\x1b[48;2;10;10;10m"
C_PANEL = "\x1b[48;2;22;22;22m"
C_BORDER = "\x1b[38;2;50;50;50m"
C_TEXT = "\x1b[38;2;212;212;212m"
C_MUTED = "\x1b[38;2;142;142;142m"
C_ACC = "\x1b[38;2;124;58;237m"
C_USER = "\x1b[38;2;34;197;94m"
C_GOOD = "\x1b[38;2;52;211;153m"
C_ERRC = "\x1b[38;2;244;135;113m"
C_WARN = "\x1b[38;2;250;204;21m"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m|\x1b\[[0-9;]*[A-Za-z]")


def plen(text):
    return len(ANSI_RE.sub("", text))

UA = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"
TOOL_RE = re.compile(r"<(run|read|write|ls|search)((?:\s+\w+(?:=\"[^\"]*\")?)*)>(.*?)</\1>", re.S)
ATTR_RE = re.compile(r"(\w+)(?:=\"([^\"]*)\")?")
STRIP_TAGS_RE = re.compile(r"<[^>]+>")
MODEL_FAIL = {}  # model -> last failure time
SESSION_TOKENS = {"in": 0, "out": 0}
ui = None  # TUI instance (set in main)


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


def run_command(cmd, root):
    actual = cmd
    if root:
        su = shutil.which("su")
        if not su:
            return -1, "su command paoa gelo na (root nai?)", "su -c ..."
        actual = su + " -c " + shlex.quote(cmd)
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
    print("  " + C_YELLOW + f"⚖ permission: {kind}" + C_RESET)
    print("  " + C_BOLD + key + C_RESET)
    while True:
        try:
            ans = input("  > 1=Yes 2=No 3=Always (Enter=1): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return "deny_once"
        if ans in ("1", "y", "yes", ""):
            return "allow_once"
        if ans in ("2", "n", "no"):
            return "deny_once"
        if ans in ("3", "a", "always"):
            return "always"


def check_perm(cfg, category, key, session_perm, prompt=True):
    """Returns True if allowed. prompt=False -> read-only ops auto-allow (deny rule thakle block)."""
    mode = perm_rule(cfg, category, key)
    if mode == "deny":
        return False
    if mode == "always" or key in session_perm.get(category, set()):
        return True
    if not prompt:
        return True
    label = {"cmd": "run command", "rootcmd": "run command (ROOT)", "file": "file op"}.get(category, category)
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


def exec_tool(cfg, name, arg, content, session_perm, attrs=None):
    """Returns result_text."""
    attrs = attrs or {}
    if name == "run":
        wants_root = "root" in attrs and attrs.get("root", "").lower() in ("true", "1", "yes", "")
        root = cfg.get("root", False) or wants_root
        category = "rootcmd" if wants_root else "cmd"
        if not check_perm(cfg, category, arg, session_perm):
            return "[Tool run: user denied]"
        if wants_root and not shutil.which("su"):
            return "[Tool run: su paoa gelo na — root mode jeno ON thake (termux e /root) ba rooted device dorkar]"
        ui_note(C_DIM + f"$ {arg}" + ("  (root)" if wants_root else "") + C_RESET)
        code, out, shown = run_command(arg, root)
        if root:
            ui_note(C_DIM + f"(root mode: su -c {shlex.quote(shown)})" + C_RESET)
        if not wants_root and not cfg.get("root") and code != 0 and re.search(
            r"permission denied|operation not permitted|not permitted|eacces", out, re.I
        ) and shutil.which("su"):
            ui_note(C_YELLOW + "! Permission denied — root diye try korbo?")
            if check_perm(cfg, "rootcmd", arg, session_perm):
                ui_note(C_DIM + "* root diye retry korchi...")
                code, out, _ = run_command(arg, True)
                return f"[Tool run (root retry) exit={code}]\n{truncate(out)}\n[/Tool run]"
        return f"[Tool run exit={code}]\n{truncate(out)}\n[/Tool run]"

    if name == "ls":
        if not check_perm(cfg, "file", arg, session_perm, prompt=False):
            return "[Tool ls: user denied]"
        try:
            entries = sorted(os.listdir(arg))
            listing = "\n".join(e + ("/" if os.path.isdir(os.path.join(arg, e)) else "") for e in entries[:200])
        except OSError as e:
            listing = f"error: {e}"
        return f"[Tool ls {arg}]\n{truncate(listing)}\n[/Tool ls]"

    if name == "read":
        if not check_perm(cfg, "file", arg, session_perm, prompt=False):
            return "[Tool read: user denied]"
        try:
            with open(arg, "rb") as f:
                data = f.read(300 * 1024)
            text = data.decode(errors="replace")
        except OSError as e:
            return f"[Tool read {arg}]\nerror: {e}\n[/Tool read]"
        return f"[Tool read {arg}]\n{truncate(text)}\n[/Tool read]"

    if name == "write":
        if not check_perm(cfg, "file", arg, session_perm):
            return "[Tool write: user denied]"
        try:
            os.makedirs(os.path.dirname(os.path.abspath(arg)), exist_ok=True)
            with open(arg, "w") as f:
                f.write(content)
            return f"[Tool write {arg}]: saved {len(content)} chars"
        except OSError as e:
            return f"[Tool write {arg}]\nerror: {e}\n[/Tool write]"

    if name == "search":
        ui_note(C_DIM + f"🔎 searching: {content}")
        try:
            res = ddg_search(content)
        except Exception as e:
            return f"[Tool search error: {e}]"
        if not res:
            return "[Tool search: kichu result pai nai]"
        lines = [f"{i + 1}. {r['title']} — {r['url']}\n   {r['snippet']}" for i, r in enumerate(res)]
        return "[Tool search]\n" + "\n".join(lines) + "\n[/Tool search]"

    return f"[Tool {name}: unknown]"


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
    lines.append(f"  default rootcmd: {perm.get('default_rootcmd', 'ask')}")
    lines.append(f"  default file:    {perm.get('default_file', 'ask')}")
    lines.append(f"  command rules:   {perm.get('cmd', {}) or '(none)'}")
    lines.append(f"  root rules:      {perm.get('rootcmd', {}) or '(none)'}")
    lines.append(f"  file rules:      {perm.get('file', {}) or '(none)'}")
    lines.append("Set: /perm cmd|rootcmd|file <ask|always|deny> | /perm reset")
    lines.append("Specific: /perm cmd add '<cmd>' <mode> | /perm rootcmd add '<cmd>' <mode>")
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
        "  /new             new chat            /sessions    saved chats",
        "  /save [name]     save chat           /load <name> load chat",
        "  /rm <name>       delete session      /stats       token count",
        "  /perm            permission rules    /root        root toggle",
        "  /exit            quit",
        "",
        "AI tools (AI nije use korbe):",
        "  search: default ON (permission chara) | read/ls: default allow",
        "  run/write: arrow prompt (←→ Yes/No/Always, Enter confirm)",
        "  /perm diye rule set: /perm cmd add 'rm' deny | /perm rootcmd add 'mount' always",
        "  Root dorkar: AI <run root> tag use korbe, permission denied holeo auto-retry",
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
    os.makedirs(CHATS_DIR, exist_ok=True)
    out = []
    for f in os.listdir(CHATS_DIR):
        if f.endswith(".json"):
            p = os.path.join(CHATS_DIR, f)
            out.append((f[:-5], os.path.getmtime(p)))
    out.sort(key=lambda x: -x[1])
    return out


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
        ch = os.read(fd, 1).decode(errors="replace")
        if ch == "\x1b":
            r, _, _ = select.select([fd], [], [], 0.06)
            if not r:
                return "ESC"
            nxt = os.read(fd, 1).decode(errors="replace")
            if nxt == "[":
                k = os.read(fd, 1).decode(errors="replace")
                if k == "A":
                    return "UP"
                if k == "B":
                    return "DOWN"
                if k == "C":
                    return "RIGHT"
                if k == "D":
                    return "LEFT"
            elif nxt == "O":
                k = os.read(fd, 1).decode(errors="replace")
                if k == "A":
                    return "UP"
                if k == "B":
                    return "DOWN"
                if k == "C":
                    return "RIGHT"
                if k == "D":
                    return "LEFT"
                return "ENTER"
            return "ESC"
        if ch in ("\r", "\n"):
            r, _, _ = select.select([fd], [], [], 0.02)
            if r:
                nxt = os.read(fd, 1).decode(errors="replace")
                if nxt not in ("\r", "\n"):
                    return nxt
            return "ENTER"
        if ch == "\x03":
            return "CTRL-C"
        if ch in ("\x7f", "\x08"):
            return "BACK"
        if ch == "\t":
            return "TAB"
        if ch.isprintable() or ord(ch) >= 160:
            return ch
        return ""
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


COMMAND_LIST = ["/help", "/model ", "/models", "/new", "/save ", "/load ", "/sessions",
                "/rm ", "/stats", "/perm", "/root", "/exit"]


class UI:
    def __init__(self, cfg):
        self.cfg = cfg
        self.api_key = get_api_key(cfg)
        self.model = cfg.get("model") or DEFAULT_MODEL
        self.root_on = cfg.get("root", False)
        self.plain = not (termios and sys.stdin.isatty())
        self.route = "home"
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.notices = []
        self.notes = []
        self.status = "ready"
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
        self.resized = False
        self.quitting = False
        self._comp = -1

    # ---------- screen ----------

    def enter(self):
        sys.stdout.write("\x1b[?1049h\x1b[2J\x1b[H\x1b[?25l")
        sys.stdout.flush()

        def on_winch(sig, frame):
            self.resized = True

        try:
            signal.signal(signal.SIGWINCH, on_winch)
        except (ValueError, AttributeError):
            pass

    def exit(self):
        sys.stdout.write("\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()

    def notice(self, label, text):
        if self.plain:
            for ln in wrap_text(text, 74):
                print("  " + C_YELLOW + "[" + label + "] " + ln + C_RESET)
        else:
            self.notices = [(label, text)]
            self.redraw()

    # opencode-style rendering: full-width panel header bar, message cards
    # with left accent border, plain assistant text, prompt + footer

    def hdr(self, title, right, W):
        pad = max(1, W - 4 - plen(title) - plen(right))
        return ("  " + C_ACC + "│" + C_RESET + C_PANEL + " " + C_BOLD + C_TEXT + title
                + C_RESET + C_PANEL + " " * pad + C_MUTED + right + C_RESET)

    def card_row(self, color, text, W):
        pad = max(0, W - 6 - plen(text))
        return "  " + color + "│" + C_RESET + C_PANEL + " " + text + " " * pad + C_RESET

    def card(self, color, text, W, top_gap=False):
        out = []
        if top_gap:
            out.append(self.card_row(color, "", W))
        for ln in wrap_text(text, max(20, W - 6)):
            out.append(self.card_row(color, ln, W))
        return out

    def plain_block(self, model, text, W):
        out = []
        for ln in wrap_text(text, max(20, W - 6)):
            out.append("    " + ln)
        out.append("    " + C_MUTED + model + C_RESET)
        return out

    def prompt_line(self, W):
        disp = self.buf
        if len(disp) > W - 8:
            disp = "…" + disp[-(W - 9):]
        if disp:
            return "  " + C_ACC + "❯" + C_RESET + " " + C_TEXT + disp + C_RESET
        return ("  " + C_ACC + "❯" + C_RESET + " " + C_MUTED
                + "Type a message... (or /help)" + C_RESET)

    FOOTER = "  " + C_MUTED + "[Enter] Send · [Esc] Home · [Tab] Complete · [Ctrl+C] Quit" + C_RESET

    def frame_home(self, W, H):
        lines = [self.hdr("voxel", "v3.5 · " + self.model, W)]
        body = [""]
        body.append("  " + C_MUTED + "Recent sessions" + C_RESET)
        body.append("")
        items = [("__new__", "＋ New Chat", "start a fresh chat")] + \
                [(n, n, rel_time(t)) for n, t in session_list()]
        self.cur = max(0, min(self.cur, len(items) - 1))
        for i, (name, label, sub) in enumerate(items):
            if i == self.cur:
                pad = max(1, W - 6 - plen(label) - plen(sub))
                body.append("  " + C_ACC + "│" + C_RESET + C_PANEL + " " + C_BOLD
                            + C_TEXT + label + C_RESET + C_PANEL + " " * pad
                            + C_MUTED + sub + C_RESET)
            else:
                pad = max(1, W - 4 - plen(label) - plen(sub))
                body.append("    " + C_DIM + label + " " * pad + sub + C_RESET)
        body.append("")
        body.append("  " + C_MUTED + "↑/↓ select · Enter open · q/Ctrl+C quit · type = new chat" + C_RESET)
        body_max = max(1, H - 3)
        if len(body) > body_max:
            body = body[-body_max:]
        else:
            body += [""] * (body_max - len(body))
        lines += body
        lines.append(self.prompt_line(W))
        lines.append(self.FOOTER)
        return lines[:H]

    def frame_chat(self, W, H):
        tok = SESSION_TOKENS["in"] + SESSION_TOKENS["out"]
        right = f"● {self.model} · tok ~{tok} · $0 · root:{'ON' if self.root_on else 'OFF'}"
        title = self.loaded_name or ("new chat" if len(self.messages) <= 1 else "chat")
        lines = [self.hdr("# " + title, right, W)]
        body = []
        for msg in self.messages[1:]:
            role, text = msg["role"], msg["content"]
            if text.startswith("[tool "):
                m = re.search(r"\[tool (\w+):", text)
                body += self.card(C_MUTED, "✓ " + (m.group(1) if m else "tool"), W)
                continue
            if role == "user":
                body += self.card(C_USER, text, W)
            else:
                body += self.plain_block(self.model, text, W)
        if self.streaming:
            if self.pending:
                for ln in wrap_text(self.pending, max(20, W - 6)):
                    body.append("    " + ln)
            else:
                body += self.card(C_ACC, C_DIM + "Thinking…" + C_RESET, W)
        for label, text in self.notices:
            body += self.card(C_WARN, "[" + label + "] " + text, W)
        for n in self.notes:
            for ln in wrap_text(n, W - 6):
                body.append("  " + C_DIM + ln + C_RESET)
        if self.popup:
            kind, key = self.popup
            opts = ["Yes", "No", "Always"]
            parts = []
            for i, o in enumerate(opts):
                if i == self.popup_idx:
                    parts.append(C_BOLD + "\x1b[7m " + o + " " + C_RESET)
                else:
                    parts.append(C_MUTED + o + C_RESET)
            body += self.card(C_ERRC, "⚖ permission: " + kind, W)
            body += self.card(C_ERRC, C_BOLD + key + C_RESET, W)
            body += self.card(C_ERRC, "←/→ " + "  ".join(parts) + "   Enter ok · q deny", W)
        body_max = max(1, H - 3)
        if len(body) > body_max:
            body = body[-body_max:]
        else:
            body += [""] * (body_max - len(body))
        lines += body
        lines.append(self.prompt_line(W))
        lines.append(self.FOOTER)
        return lines[:H]

    def redraw(self):
        if self.plain:
            return
        W, H = term_size()
        if self.route == "home":
            frame = self.frame_home(W, H)
        else:
            frame = self.frame_chat(W, H)
        while len(frame) < H:
            frame.append("")
        out = []
        for i, line in enumerate(frame[:H]):
            out.append("\x1b[" + str(i + 1) + ";1H\x1b[K" + line)
        out.append("\x1b[" + str(H) + ";1H")
        sys.stdout.write("".join(out))
        sys.stdout.flush()

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
        items = [("__new__",)] + [(n,) for n, _ in session_list()]
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
        elif k == "ESC":
            self.redraw()
        elif k.isprintable():
            self.buf = k
            self.open_session("__new__")
        else:
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
                self.notices = [("SYS", "Session paoa gelo na: " + name)]
        self.route = "chat"
        self.redraw()

    def key_chat(self, k):
        if k == "ENTER":
            text = self.buf
            if text.strip():
                self.hist.append(text)
                self.hidx = len(self.hist)
                self.buf = ""
                self.send(text)
            else:
                self.redraw()
        elif k == "ESC":
            if len(self.messages) > 1:
                save_session("last", self.messages)
            self.buf = ""
            self.notices = []
            self.notes = []
            self.route = "home"
            self.cur = 0
            self.redraw()
        elif k == "CTRL-C":
            self.quitting = True
        elif k == "BACK":
            self.buf = self.buf[:-1]
            self.redraw()
        elif k == "TAB":
            self.complete()
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

    # ---------- commands ----------

    def run_command(self, text):
        user_input = text.strip()
        if user_input in ("/exit", "/quit"):
            self.quitting = True
            return True
        if user_input == "/help":
            self.notice("HELP", help_text())
            return True
        if user_input == "/new":
            self.open_session("__new__")
            return True
        if user_input == "/stats":
            tot = SESSION_TOKENS["in"] + SESSION_TOKENS["out"]
            self.notice("STATS", f"input: {SESSION_TOKENS['in']} tok | output: {SESSION_TOKENS['out']} tok | total: {tot} (cost $0)")
            return True
        if user_input == "/models":
            self.notice("MODELS", list_free())
            return True
        if user_input == "/root":
            if not shutil.which("su"):
                self.notice("SYS", "su paoa gelo na — rooted device dorkar (Magisk/KernelSU).")
            else:
                self.root_on = not self.root_on
                self.cfg["root"] = self.root_on
                save_config(self.cfg)
                self.notice("SYS", f"Root mode: {'ON (su -c)' if self.root_on else 'OFF'}")
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
            names = list_sessions()
            txt = "Saved sessions: " + (", ".join(names) if names else "(kono session nai)")
            self.notice("SESSIONS", txt + "\nLoad: /load <name> | Delete: /rm <name>")
            return True
        if user_input.startswith("/save"):
            name = user_input.split(None, 1)[1].strip() if len(user_input.split(None, 1)) > 1 else time.strftime("chat-%Y%m%d-%H%M%S")
            if len(self.messages) > 1:
                path = save_session(name, self.messages)
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

    # ---------- chat flow ----------

    def send(self, text):
        if self.run_command(text):
            self.redraw()
            return
        self.notices = []
        self.notes = []
        self.messages.append({"role": "user", "content": text})
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

        def on_chunk(kind, text):
            parts.append((kind, text))

        def worker():
            result["err"], result["model"] = call_chat(self.messages, self.model, self.api_key, on_chunk)
            done.set()

        t = threading.Thread(target=worker, daemon=True)
        t.start()
        self.streaming = True
        self.cancel = False
        typed = []
        self.redraw()
        try:
            while t.is_alive() or not done.is_set():
                r, _, _ = select.select([sys.stdin], [], [], 0.15)
                if r:
                    k = raw_key()
                    if k in ("CTRL-C", "ESC"):
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
                pending = "".join(x for kind, x in parts if kind == "content")
                if pending != self.pending:
                    self.pending = pending
                    self.buf = "".join(typed)
                    self.redraw()
        except KeyboardInterrupt:
            self.cancel = True
        finally:
            self.streaming = False
            self.pending = ""
            self.reasoning = ""
            if typed and not self.cancel:
                self.buf = "".join(typed)
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
        for round_no in range(MAX_TOOL_ROUNDS):
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
            self.messages.append({"role": "assistant", "content": content})
            if not tools:
                self.status = f"{used_model} | {dt} | tok ~{SESSION_TOKENS['in'] + SESSION_TOKENS['out']}"
                self.redraw()
                break
            results = []
            for name, attrs, tcontent in tools:
                if name == "write":
                    arg = attrs.get("path", "").strip()
                    tool_content = tcontent
                else:
                    arg = (tcontent or attrs.get("path") or "").strip()
                    tool_content = arg
                self.notes.append(C_YELLOW + f"⚙ {name}: {arg}" + C_RESET)
                self.redraw()
                res = exec_tool(self.cfg, name, arg, tool_content, self.session_perm, attrs)
                results.append(f"[tool {name}: {res}]")
                self.notes.append(C_DIM + truncate(res, 1200) + C_RESET)
                if round_no == MAX_TOOL_ROUNDS - 1:
                    results.append("(max tool rounds reached, ekhane shesh koro)")
                self.redraw()
            self.messages.append({"role": "user", "content": "\n".join(results)})
        else:
            self.notice("SYS", "Max tool rounds — /new diye fresh koro.")
        if self.loaded_name and len(self.messages) > 1:
            save_session(self.loaded_name, self.messages)

    # ---------- permission popup ----------

    def perm_popup(self, kind, key):
        self.popup = (kind, key)
        self.popup_idx = 0
        try:
            while True:
                self.redraw()
                k = raw_key()
                if k == "RIGHT":
                    self.popup_idx = (self.popup_idx + 1) % 3
                elif k == "LEFT":
                    self.popup_idx = (self.popup_idx - 1) % 3
                elif k in ("1", "2", "3"):
                    self.popup_idx = int(k) - 1
                    break
                elif k in ("q", "Q", "CTRL-C", "ESC"):
                    return "deny_once"
                elif k in ("ENTER", ""):
                    break
        finally:
            self.popup = None
            self.redraw()
        return ("allow_once", "deny_once", "always")[self.popup_idx]

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
        print(C_BOLD + C_CYAN + "VOXEL AI v3.5" + C_RESET + "  (" + self.model + ")  —  /help")
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
