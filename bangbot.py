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
import shlex
import shutil
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
- Ekbare ekta tag use koro, result ashle tarpor aro kaj lagle abar tag use korbe.
- command chalano te warning/error thakle seta user ke bolo.
- 'termux-*' command available ache (termux-api installed thakle).
- Tumul own naming: always VOXEL AI bolo."""

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

UA = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36"
TOOL_RE = re.compile(r"<(run|read|write|ls|search)((?:\s+\w+(?:=\"[^\"]*\")?)*)>(.*?)</\1>", re.S)
ATTR_RE = re.compile(r"(\w+)(?:=\"([^\"]*)\")?")
STRIP_TAGS_RE = re.compile(r"<[^>]+>")
MODEL_FAIL = {}  # model -> last failure time
SESSION_TOKENS = {"in": 0, "out": 0}


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


def ask_permission(kind, detail):
    print()
    print(C_YELLOW + f"[permission] {kind}: {detail}" + C_RESET)
    while True:
        try:
            ans = input(C_YELLOW + "[y]es [n]o [s]ession-allow [a]lways-allow [d]eny-always > " + C_RESET).strip().lower()
        except (KeyboardInterrupt, EOFError):
            return "deny_once"
        if ans in ("y", "yes", ""):
            return "allow_once"
        if ans in ("n", "no"):
            return "deny_once"
        if ans in ("s", "session"):
            return "allow_session"
        if ans in ("a", "always"):
            return "always"
        if ans in ("d", "deny"):
            return "deny_always"
        print(C_DIM + "(y/n/s/a/d)" + C_RESET)


def check_perm(cfg, category, key, session_perm):
    """Returns True if allowed. May prompt user. May mutate cfg for 'always' rules."""
    mode = perm_rule(cfg, category, key)
    if mode == "deny":
        return False
    if mode == "always" or key in session_perm.get(category, set()):
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
        print(C_DIM + f"$ {arg}" + ("  (root)" if wants_root else "") + C_RESET, flush=True)
        code, out, shown = run_command(arg, root)
        if root:
            print(C_DIM + f"  (root mode: su -c {shlex.quote(shown)})" + C_RESET)
        if not wants_root and not cfg.get("root") and code != 0 and re.search(
            r"permission denied|operation not permitted|not permitted|eacces", out, re.I
        ) and shutil.which("su"):
            print(C_YELLOW + "! Permission denied — root diye retry korbo? (root command e permission lagbe)" + C_RESET)
            if check_perm(cfg, "rootcmd", arg, session_perm):
                print(C_DIM + "* root diye retry korchi..." + C_RESET)
                code, out, _ = run_command(arg, True)
                return f"[Tool run (root retry) exit={code}]\n{truncate(out)}\n[/Tool run]"
        return f"[Tool run exit={code}]\n{truncate(out)}\n[/Tool run]"

    if name == "ls":
        if not check_perm(cfg, "file", arg, session_perm):
            return "[Tool ls: user denied]"
        try:
            entries = sorted(os.listdir(arg))
            listing = "\n".join(e + ("/" if os.path.isdir(os.path.join(arg, e)) else "") for e in entries[:200])
        except OSError as e:
            listing = f"error: {e}"
        return f"[Tool ls {arg}]\n{truncate(listing)}\n[/Tool ls]"

    if name == "read":
        if not check_perm(cfg, "file", arg, session_perm):
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
        print(C_DIM + f"* searching: {content}" + C_RESET, flush=True)
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

def term_w():
    try:
        return max(44, min(shutil.get_terminal_size().columns, 120))
    except Exception:
        return 60


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


def bubble_lines(label, color, text, w):
    out = [color + label + C_RESET]
    wrapped = wrap_text(text, w - 2) if text else ["(empty)"]
    out.append("┌" + "─" * (w - 2) + "┐")
    for ln in wrapped:
        pad = max(0, w - 2 - len(ln))
        out.append("│ " + ln + " " * pad + " │")
    out.append("└" + "─" * (w - 2) + "┘")
    return out


def render(cfg, model, root_on, messages, notices, status, W):
    inner = W - 2
    cell = W - 6
    out = [CLEAR]
    title = " VOXEL AI "
    out.append(C_CYAN + "┌─" + title + "─" * max(1, inner - len(title) - 3) + "┐" + C_RESET)
    h2 = f" {model} | free models | root:{'ON' if root_on else 'OFF'} "
    out.append("│" + h2 + " " * max(0, inner - len(h2)) + "│")
    out.append("├" + "─" * inner + "┤")
    out.append("│" + " " * inner + "│")
    for msg in messages[1:]:
        role = msg["role"]
        text = msg["content"]
        if role == "user":
            label, color = "YOU", C_GREEN
        elif role == "assistant":
            label, color = "VOXEL AI", C_CYAN
        else:
            label, color = "SYS", C_YELLOW
        if text.startswith("[tool "):
            label, color = "TOOL", C_YELLOW
        for ln in bubble_lines(label, color, text, cell):
            out.append("│  " + ln + "  │")
        out.append("│" + " " * inner + "│")
    for label, text in notices:
        for ln in bubble_lines(label, C_YELLOW, text, cell):
            out.append("│  " + ln + "  │")
        out.append("│" + " " * inner + "│")
    out.append("├" + "─" * inner + "┤")
    st = f" {status} "
    out.append("│" + st + " " * max(0, inner - len(st)) + "│")
    out.append("├" + "─" * inner + "┤")
    sys.stdout.write("\n".join(out) + "\n")
    sys.stdout.flush()


def clr_line():
    sys.stdout.write("\r" + "\x1b[2K")
    sys.stdout.flush()


def print_cell(text, W):
    cell = W - 6
    for ln in wrap_text(text, cell):
        print("│  " + ln)


def loading_box(W):
    cell = W - 6
    print("│  " + "┌" + "─" * (cell - 2) + "┐")
    print("│  " + "│ " + " " * (cell - 4) + " │")


def close_stream_box(W):
    cell = W - 6
    print("│  " + "└" + "─" * (cell - 2) + "┘")


def print_streamed(parts):
    first_content = True
    for kind, text in parts:
        if kind == "reasoning":
            print(C_DIM + text + C_RESET, end="", flush=True)
        else:
            if first_content:
                print("\n" + C_DIM + "--- thinking done ---" + C_RESET + "\n")
                first_content = False
            print(text, end="", flush=True)
    if first_content:
        print(C_DIM + "(no content)" + C_RESET)
    print()


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
        "  run/read/write/ls/search - permission prompt asbe, y/n/s/a/d diye decide koro",
        "  Root dorkar: AI <run root> tag use korbe, ar permission denied holeo auto-retry korbe",
        "Multi-line: line er seshe '\\' dile continue hobe.",
    ])


def ai_reply(messages, model, api_key, W, root_on):
    """Streams AI reply with loading spinner. Returns (content, reasoning, err, used_model)."""
    parts = []
    done = threading.Event()

    def on_chunk(kind, text):
        parts.append((kind, text))
        if kind == "content":
            done.set()

    result = {}

    def worker():
        result["err"], result["model"] = call_chat(messages, model, api_key, on_chunk)
        done.set()

    t = threading.Thread(target=worker, daemon=True)
    t.start()

    cell = W - 6
    print("│  " + C_CYAN + "VOXEL AI" + C_RESET)
    loading_box(W)
    i = 0
    while t.is_alive() or not result:
        sys.stdout.write("\r│  │ ⏳ " + SPINNER[i % len(SPINNER)] + " thinking..." + C_RESET)
        sys.stdout.flush()
        i += 1
        time.sleep(0.12)
    clr_line()
    print("│  " + "│ " + C_DIM + "done ✓" + C_RESET + " " * max(0, cell - 4 - 7) + " │")
    close_stream_box(W)

    err = result.get("err")
    used_model = result.get("model")
    if err:
        return "", "", err, used_model

    reasoning = "".join(text for kind, text in parts if kind == "reasoning")
    content = "".join(text for kind, text in parts if kind == "content")
    return content, reasoning, None, used_model


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

    api_key = get_api_key(cfg)
    model = cfg.get("model") or DEFAULT_MODEL
    root_on = cfg.get("root", False)
    if root_on and not shutil.which("su"):
        print(C_YELLOW + "! Root mode on kintu 'su' paoa gelo na — rooted device nai mone hocche." + C_RESET)

    W = term_w()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    notices = [("SYS", "Hello! VOXEL AI ready. /help diye commands dekhun. AI command/file kaj korle permission prompt asbe (y/n/s/a/d).")]
    session_perm = {"cmd": set(), "file": set()}
    loaded_name = None
    last_dt = "-"
    status = "ready"

    render(cfg, model, root_on, messages, notices, status, W)

    while True:
        print("│ > ", end="", flush=True)
        try:
            line = input()
            while line.rstrip().endswith("\\"):
                try:
                    more = input("│ … ")
                except (KeyboardInterrupt, EOFError):
                    more = ""
                line = line.rstrip()[:-1] + "\n" + more
            user_input = line.strip()
        except (KeyboardInterrupt, EOFError):
            print()
            if len(messages) > 1:
                save_session("last", messages)
            print(C_GREEN + "└" + "─" * (W - 3) + "┘")
            print(C_DIM + "Bye!" + C_RESET)
            break

        if not user_input:
            continue

        if user_input in ("/exit", "/quit"):
            if len(messages) > 1:
                save_session("last", messages)
            print(C_GREEN + "└" + "─" * (W - 3) + "┘")
            print(C_DIM + "Bye! (auto-saved: last)" + C_RESET)
            break
        elif user_input == "/help":
            notices = [("HELP", help_text())]
            render(cfg, model, root_on, messages, notices, status, W)
            continue
        elif user_input == "/new":
            if len(messages) > 1:
                save_session("last", messages)
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            SESSION_TOKENS["in"] = SESSION_TOKENS["out"] = 0
            session_perm = {"cmd": set(), "file": set()}
            loaded_name = None
            notices = []
            status = "new chat"
            render(cfg, model, root_on, messages, notices, status, W)
            continue
        elif user_input == "/stats":
            tot = SESSION_TOKENS["in"] + SESSION_TOKENS["out"]
            notices = [("STATS", f"input: {SESSION_TOKENS['in']} tok | output: {SESSION_TOKENS['out']} tok | total: {tot} (cost $0)")]
            render(cfg, model, root_on, messages, notices, status, W)
            continue
        elif user_input == "/models":
            notices = [("MODELS", list_free())]
            render(cfg, model, root_on, messages, notices, status, W)
            continue
        elif user_input == "/root":
            if not shutil.which("su"):
                notices = [("SYS", "su paoa gelo na — rooted device dorkar (Magisk/KernelSU).")]
            else:
                root_on = not root_on
                cfg["root"] = root_on
                save_config(cfg)
                notices = [("SYS", f"Root mode: {'ON (su -c)' if root_on else 'OFF'}")]
            render(cfg, model, root_on, messages, notices, status, W)
            continue
        elif user_input.startswith("/model "):
            new_model = user_input.split(None, 1)[1].strip()
            cfg["model"] = new_model
            save_config(cfg)
            model = new_model
            notices = [("SYS", "Model changed: " + model)]
            render(cfg, model, root_on, messages, notices, status, W)
            continue
        elif user_input == "/perm":
            notices = [("PERM", show_perms(cfg))]
            render(cfg, model, root_on, messages, notices, status, W)
            continue
        elif user_input.startswith("/perm "):
            parts = user_input.split()
            try:
                if len(parts) == 3 and parts[2] in ("ask", "always", "deny"):
                    cfg.setdefault("perm", {})["default_" + parts[1]] = parts[2]
                    save_config(cfg)
                    notices = [("PERM", f"default {parts[1]}: {parts[2]}")]
                elif len(parts) == 5 and parts[2] == "add" and parts[4] in ("ask", "always", "deny"):
                    cfg.setdefault("perm", {}).setdefault(parts[1], {})[parts[3]] = parts[4]
                    save_config(cfg)
                    notices = [("PERM", f"rule: {parts[1]} '{parts[3]}' -> {parts[4]}")]
                elif parts[1] == "reset":
                    cfg["perm"] = {}
                    save_config(cfg)
                    notices = [("PERM", "All permission rules reset.")]
                else:
                    notices = [("PERM", show_perms(cfg))]
            except Exception:
                notices = [("PERM", show_perms(cfg))]
            render(cfg, model, root_on, messages, notices, status, W)
            continue
        elif user_input == "/sessions":
            names = list_sessions()
            txt = "Saved sessions: " + (", ".join(names) if names else "(kono session nai)")
            notices = [("SESSIONS", txt + "\nLoad: /load <name> | Delete: /rm <name>")]
            render(cfg, model, root_on, messages, notices, status, W)
            continue
        elif user_input.startswith("/save"):
            name = user_input.split(None, 1)[1].strip() if len(user_input.split(None, 1)) > 1 else time.strftime("chat-%Y%m%d-%H%M%S")
            if len(messages) > 1:
                path = save_session(name, messages)
                notices = [("SYS", "Saved: " + path)]
            else:
                notices = [("SYS", "Chat khali, save korar moto kichu nai.")]
            render(cfg, model, root_on, messages, notices, status, W)
            continue
        elif user_input.startswith("/load "):
            name = user_input.split(None, 1)[1].strip()
            loaded = load_session(name)
            if loaded and loaded[0].get("role") == "system":
                messages = loaded
                loaded_name = name
                notices = [("SYS", f"Loaded: {name} ({len(messages) - 1} messages)")]
            else:
                notices = [("SYS", "Session paoa gelo na: " + name)]
            render(cfg, model, root_on, messages, notices, status, W)
            continue
        elif user_input.startswith("/rm "):
            name = user_input.split(None, 1)[1].strip()
            try:
                os.remove(os.path.join(CHATS_DIR, name + ".json"))
                notices = [("SYS", "Deleted: " + name)]
            except OSError:
                notices = [("SYS", "Session nai: " + name)]
            render(cfg, model, root_on, messages, notices, status, W)
            continue
        elif user_input.startswith("/"):
            notices = [("SYS", "Unknown command: " + user_input + " (type /help)")]
            render(cfg, model, root_on, messages, notices, status, W)
            continue

        notices = []
        messages.append({"role": "user", "content": user_input})
        render(cfg, model, root_on, messages, notices, status, W)

        for round_no in range(MAX_TOOL_ROUNDS):
            t0 = time.time()
            content, reasoning, err, used_model = ai_reply(messages, model, api_key, W, root_on)
            dt = fmt_duration(time.time() - t0)
            last_dt = dt

            if err:
                print(C_RED + "│  " + err + C_RESET)
                messages.pop()
                status = "error"
                render(cfg, model, root_on, messages, notices, status, W)
                break

            SESSION_TOKENS["in"] += est_tokens(reasoning + content)
            SESSION_TOKENS["out"] += est_tokens(content)

            tools = parse_tools(content)
            messages.append({"role": "assistant", "content": content})

            if not tools:
                status = f"{used_model} | {dt} | tok ~{SESSION_TOKENS['in'] + SESSION_TOKENS['out']}"
                render(cfg, model, root_on, messages, notices, status, W)
                break

            results = []
            for name, attrs, tcontent in tools:
                if name == "write":
                    arg = attrs.get("path", "").strip()
                    tool_content = tcontent
                else:
                    arg = (tcontent or attrs.get("path") or "").strip()
                    tool_content = arg
                print("│  " + C_YELLOW + f"⚙ {name}: {arg}" + C_RESET)
                res = exec_tool(cfg, name, arg, tool_content, session_perm, attrs)
                results.append(f"[tool {name}: {res}]")
                print(C_DIM + truncate(res, 1200) + C_RESET)
                if round_no == MAX_TOOL_ROUNDS - 1:
                    results.append("(max tool rounds reached, ekhane shesh koro)")
            messages.append({"role": "user", "content": "\n".join(results)})
        else:
            print(C_YELLOW + "! Max tool rounds — /new diye fresh koro." + C_RESET)

        if loaded_name and len(messages) > 1:
            save_session(loaded_name, messages)


if __name__ == "__main__":
    main()
