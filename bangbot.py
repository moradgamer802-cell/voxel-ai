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


def call_chat(messages, model, api_key, fallback=True):
    """Returns (reply_list, err, used_model). Auto-switches model on errors."""
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
            parts = list(stream_chat(messages, m, api_key))
            MODEL_FAIL.pop(m, None)
            return parts, None, m
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
            return None, f"Network error: {e.reason}", m
        except Exception as e:
            return None, f"Error: {e}", m
        if not fallback:
            break
    if key_error and len(tried) == 1:
        return None, key_error, model
    return None, "Shob model e rate limit/error. Kichu minute pore abar try koro.", model


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
    print(C_BOLD + "Free models (OpenCode Zen):" + C_RESET)
    for m in FREE_MODELS:
        print(f"  {C_CYAN}{m}{C_RESET}")
    print(C_DIM + "Live list: python3 bangbot.py --models" + C_RESET)


def show_perms(cfg):
    perm = cfg.get("perm", {})
    print(C_BOLD + "Permission rules:" + C_RESET)
    print(f"  default command: {perm.get('default_cmd', 'ask')}")
    print(f"  default rootcmd: {perm.get('default_rootcmd', 'ask')}")
    print(f"  default file:    {perm.get('default_file', 'ask')}")
    cmds = perm.get("cmd", {})
    roots = perm.get("rootcmd", {})
    files = perm.get("file", {})
    print(f"  command rules:   {cmds or '(none)'}")
    print(f"  root rules:      {roots or '(none)'}")
    print(f"  file rules:      {files or '(none)'}")
    print(C_DIM + "Set: /perm cmd|rootcmd|file <ask|always|deny> | /perm reset" + C_RESET)
    print(C_DIM + "Specific: /perm cmd add '<cmd>' <mode> | /perm rootcmd add '<cmd>' <mode>" + C_RESET)


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
    print(C_BOLD + "Commands:" + C_RESET)
    print("  /model <id>      model change        /models      free model list")
    print("  /new             new chat            /sessions    saved chats")
    print("  /save [name]     save chat           /load <name> load chat")
    print("  /rm <name>       delete session      /stats       token count")
    print("  /perm            permission rules    /root        root toggle")
    print("  /exit            quit")
    print()
    print(C_BOLD + "AI tools (AI nije use korbe):" + C_RESET)
    print("  run/read/write/ls/search - permission prompt asbe, y/n/s/a/d diye decide koro")
    print("  Root dorkar: AI <run root> tag use korbe, ar permission denied holeo auto-retry korbe")
    print(C_DIM + "Multi-line: line er seshe '\\' dile continue hobe. Up/down arrow: history" + C_RESET)


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

    print(C_BOLD + C_MAG + r"""
     _   _  ___  _  __ _____ _
    | | | |/ _ \| |/ /| ____| |
    | |_| | | | | ' / |  _| | |
    |  _  | |_| | . \ | |___| |___
    |_| |_|\___/|_|\_\|_____|_____|
""" + C_RESET)
    print(C_CYAN + "VOXEL AI - free AI agent for Termux" + C_RESET)
    print(C_DIM + "Powered by OpenCode Zen free models | /help - commands" + C_RESET)
    print()

    api_key = get_api_key(cfg)
    if api_key == DEFAULT_API_KEY:
        print(C_YELLOW + "Built-in free key use hocche." + C_RESET)
    else:
        print(C_GREEN + "API key: configured" + C_RESET)

    model = cfg.get("model") or DEFAULT_MODEL
    root_on = cfg.get("root", False)
    if root_on and not shutil.which("su"):
        print(C_YELLOW + "! Root mode on kintu 'su' paoa gelo na — rooted device nai mone hocche." + C_RESET)
    print(C_GREEN + "Model: " + C_RESET + model + ("  | " + C_MAG + "ROOT: ON" + C_RESET if root_on else ""))

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    session_perm = {"cmd": set(), "file": set()}
    loaded_name = None

    while True:
        try:
            line = input(C_GREEN + "you > " + C_RESET)
            while line.rstrip().endswith("\\"):
                try:
                    more = input(C_CYAN + "...  > " + C_RESET)
                except (KeyboardInterrupt, EOFError):
                    more = ""
                line = line.rstrip()[:-1] + "\n" + more
            user_input = line.strip()
        except (KeyboardInterrupt, EOFError):
            print()
            if len(messages) > 1:
                save_session("last", messages)
                print(C_DIM + "auto-saved: last" + C_RESET)
            print(C_DIM + "Bye!" + C_RESET)
            break

        if not user_input:
            continue

        if user_input in ("/exit", "/quit"):
            if len(messages) > 1:
                save_session("last", messages)
                print(C_DIM + "auto-saved: last" + C_RESET)
            print(C_DIM + "Bye!" + C_RESET)
            break
        elif user_input == "/help":
            help_text()
            continue
        elif user_input == "/new":
            if len(messages) > 1:
                save_session("last", messages)
            messages = [{"role": "system", "content": SYSTEM_PROMPT}]
            SESSION_TOKENS["in"] = SESSION_TOKENS["out"] = 0
            session_perm = {"cmd": set(), "file": set()}
            loaded_name = None
            print(C_DIM + "New chat started (old ta 'last' e save holo)." + C_RESET)
            continue
        elif user_input == "/stats":
            print(f"  session input tokens:  {SESSION_TOKENS['in']}")
            print(f"  session output tokens: {SESSION_TOKENS['out']}")
            print(f"  total: {SESSION_TOKENS['in'] + SESSION_TOKENS['out']} (cost: $0, free models)")
            continue
        elif user_input == "/models":
            list_free()
            continue
        elif user_input == "/root":
            if not shutil.which("su"):
                print(C_YELLOW + "su paoa gelo na — rooted device dorkar (Magisk/KernelSU)." + C_RESET)
                cfg["root"] = False
                save_config(cfg)
                root_on = False
                continue
            root_on = not root_on
            cfg["root"] = root_on
            save_config(cfg)
            print(C_GREEN + "Root mode: " + ("ON (su -c)" if root_on else "OFF") + C_RESET)
            continue
        elif user_input.startswith("/model "):
            new_model = user_input.split(None, 1)[1].strip()
            cfg["model"] = new_model
            save_config(cfg)
            model = new_model
            print(C_GREEN + "Model changed: " + model + C_RESET)
            continue
        elif user_input == "/perm":
            show_perms(cfg)
            continue
        elif user_input.startswith("/perm "):
            parts = user_input.split()
            try:
                if len(parts) == 3 and parts[2] in ("ask", "always", "deny"):
                    cfg.setdefault("perm", {})["default_" + parts[1]] = parts[2]
                    save_config(cfg)
                    print(C_GREEN + f"default {parts[1]}: {parts[2]}" + C_RESET)
                elif len(parts) == 5 and parts[2] == "add" and parts[4] in ("ask", "always", "deny"):
                    cfg.setdefault("perm", {}).setdefault(parts[1], {})[parts[3]] = parts[4]
                    save_config(cfg)
                    print(C_GREEN + f"rule: {parts[1]} '{parts[3]}' -> {parts[4]}" + C_RESET)
                elif user_input.startswith("/perm reset"):
                    cfg["perm"] = {}
                    save_config(cfg)
                    print(C_GREEN + "All permission rules reset." + C_RESET)
                else:
                    show_perms(cfg)
            except Exception:
                show_perms(cfg)
            continue
        elif user_input == "/sessions":
            names = list_sessions()
            print(C_BOLD + "Saved sessions:" + C_RESET)
            print("  " + (", ".join(names) if names else "(kono session nai)"))
            print(C_DIM + "Load: /load <name> | Delete: /rm <name>" + C_RESET)
            continue
        elif user_input.startswith("/save"):
            name = user_input.split(None, 1)[1].strip() if len(user_input.split(None, 1)) > 1 else time.strftime("chat-%Y%m%d-%H%M%S")
            if len(messages) > 1:
                path = save_session(name, messages)
                print(C_GREEN + "Saved: " + path + C_RESET)
            else:
                print(C_YELLOW + "Chat khali, save korar moto kichu nai." + C_RESET)
            continue
        elif user_input.startswith("/load "):
            name = user_input.split(None, 1)[1].strip()
            loaded = load_session(name)
            if loaded and loaded[0].get("role") == "system":
                messages = loaded
                loaded_name = name
                print(C_GREEN + "Loaded: " + name + f" ({len(messages) - 1} messages)" + C_RESET)
            else:
                print(C_RED + "Session paoa gelo na: " + name + C_RESET)
            continue
        elif user_input.startswith("/rm "):
            name = user_input.split(None, 1)[1].strip()
            try:
                os.remove(os.path.join(CHATS_DIR, name + ".json"))
                print(C_GREEN + "Deleted: " + name + C_RESET)
            except OSError:
                print(C_RED + "Session nai: " + name + C_RESET)
            continue
        elif user_input.startswith("/"):
            print(C_YELLOW + "Unknown command: " + user_input + " (type /help)" + C_RESET)
            continue

        messages.append({"role": "user", "content": user_input})

        for round_no in range(MAX_TOOL_ROUNDS):
            print(C_CYAN + "bot > " + C_RESET, end="", flush=True)
            t0 = time.time()
            parts, err, used_model = call_chat(messages, model, api_key)
            dt = fmt_duration(time.time() - t0)

            if err:
                print()
                print(C_RED + err + C_RESET)
                messages.pop()
                break

            content = "".join(text for kind, text in parts if kind == "content")
            reasoning = "".join(text for kind, text in parts if kind == "reasoning")
            SESSION_TOKENS["in"] += est_tokens(reasoning + content)
            SESSION_TOKENS["out"] += est_tokens(reasoning + content)

            if reasoning:
                print(C_DIM + reasoning + C_RESET + "\n" + C_DIM + "--- thinking done ---" + C_RESET + "\n")
            for kind, text in parts:
                if kind == "content":
                    print(text, end="", flush=True)
            print()
            print(C_DIM + f"  [{used_model} | {dt} | tok ~{SESSION_TOKENS['in'] + SESSION_TOKENS['out']}]" + C_RESET)

            tools = parse_tools(content)
            if not tools:
                messages.append({"role": "assistant", "content": content})
                break

            messages.append({"role": "assistant", "content": content})
            results = []
            for name, attrs, tcontent in tools:
                if name == "write":
                    arg = attrs.get("path", "").strip()
                    tool_content = tcontent
                else:
                    arg = (tcontent or attrs.get("path") or "").strip()
                    tool_content = arg
                res = exec_tool(cfg, name, arg, tool_content, session_perm, attrs)
                print(C_DIM + truncate(res, 1200) + C_RESET)
                results.append(f"[tool {name}: {res}]")
                if round_no == MAX_TOOL_ROUNDS - 1:
                    results.append("(max tool rounds reached, ekhane shesh koro)")
            messages.append({"role": "user", "content": "\n".join(results)})
        else:
            print(C_YELLOW + "! Max tool rounds — new chat e /new." + C_RESET)

        if loaded_name and len(messages) > 1:
            save_session(loaded_name, messages)


if __name__ == "__main__":
    main()
