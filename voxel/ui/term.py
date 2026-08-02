"""Terminal UI for VOXEL - raw TUI rendering."""

import os
import re
import select
import signal
import struct
import sys
import termios
import time
import tty
from collections import defaultdict

from voxel.constants import (
    C_ACC, C_BG, C_BOLD, C_BUILD, C_CYAN, C_DIM, C_ERRC, C_GOOD,
    C_GREEN, C_HIGHLIGHT, C_MAG, C_MUTED, C_PANEL, C_PLAN,
    C_RED, C_RESET, C_TEXT, C_USER, C_WARN, C_YELLOW, SPINNER,
)
from voxel.session import list_sessions, load_session


class TermUI:
    def __init__(self, cfg: dict, api_key: str, model: str):
        self.cfg = cfg
        self.api_key = api_key
        self.model = model
        self.plain = not (termios and sys.stdin.isatty())
        self.route = "home"
        self.messages = []
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
        self.palette_filter = ""
        self.sess_pick = None
        self.sess_idx = 0
        self.model_pick = None
        self.model_idx = 0
        self.cmd_pick = False
        self.cmd_idx = 0
        self.mode = "build"
        self.session_perm = {"cmd": set(), "file": set()}
        self.notes = []
        self.notices = []
        self.status = "ready"
        self.auto_approve = False
        self.anim = True
        self.compact = False
        self.tiny_input = False
        self.tiny_rows = False
        self.wide = False
        self.scroll_off = 0
        self._old_termios = None
        self._draw_lock = type('Lock', (), {'acquire': lambda: None, 'release': lambda: None})()
        self.resized = False
        self.quitting = False
        self._last_key = 0.0
        self._mode_flash = 0.0
        self._entrance = None
        self.spin = SPINNER[0]
        self._revealed = 0
        self._acc = ""
        self._stream_start = 0.0
        self._stream_tokens = 0
        self._think_start = 0.0
        self._think_secs = None
        self._undo_msg = None
        self._esc_pending = False
        self._tool_progress = None
        self._boot_t = time.time()
        self._last_reply_dt = 0.0
        self.timing_panel = False
        self._render_hist = []
        self._stream_speeds = []
        self.expand_diffs = set()
        self.renaming = False
        self._route_fade = 0.0
        self._popup_birth = 0.0
        self._sec_anim = None
        self._notice_t = 0.0
        self._approve_pop = 0.0
        self.sec_focus = False

    def _term_size(self):
        rows = cols = 0
        try:
            import fcntl
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
                s = __import__("shutil").get_terminal_size()
                rows, cols = s.lines, s.columns
            except Exception:
                rows, cols = 24, 60
        return max(20, min(max(cols, 1), 120)), max(10, min(max(rows, 1), 200))

    def _safeify(self, line):
        return line

    def enter(self):
        sys.stdout.write("\x1b[?1049h\x1b[2J\x1b[H\x1b[?25l\x1b[?1000h\x1b[?1006h")
        sys.stdout.flush()
        if termios and sys.stdin.isatty():
            try:
                fd = sys.stdin.fileno()
                self._old_termios = termios.tcgetattr(fd)
                tty.setraw(fd)
            except Exception:
                self._old_termios = None
        try:
            signal.signal(signal.SIGWINCH, lambda s, f: setattr(self, "resized", True))
        except (ValueError, AttributeError):
            pass

    def exit(self):
        if self._old_termios is not None and termios and sys.stdin.isatty():
            try:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSADRAIN, self._old_termios)
            except Exception:
                pass
        sys.stdout.write("\x1b[?25h\x1b[?1000l\x1b[?1006l\x1b[?1049l")
        sys.stdout.flush()

    def _dlen(self, text):
        import unicodedata
        width = 0
        for ch in re.sub(r"\x1b\[[0-9;]*m|\x1b\[[0-9;]*[A-Za-z]", "", text):
            if unicodedata.combining(ch):
                continue
            width += 2 if unicodedata.east_asian_width(ch) in ("F", "W") else 1
        return width

    def _wrap(self, text, width):
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

    def _short(self, text, limit):
        flat = " ".join(text.split())
        if len(flat) > limit:
            return flat[: limit - 1] + "…"
        return flat

    def _hdr(self, title, right, W):
        avail = max(10, W - 6)
        if self._dlen(title) + self._dlen(right) > avail:
            right = self._short(right, max(4, avail - self._dlen(title)))
        if self._dlen(title) + self._dlen(right) > avail:
            title = self._short(title, max(4, avail - self._dlen(right)))
        pad = max(1, W - 4 - self._dlen(title) - self._dlen(right))
        return ("  " + C_ACC + "│" + C_RESET + C_PANEL + " " + C_BOLD + C_TEXT + title
                + C_RESET + C_PANEL + " " * pad + C_MUTED + right + C_RESET)

    def _card_row(self, color, text, W):
        pad = max(0, W - 6 - self._dlen(text))
        return "  " + color + "│" + C_RESET + C_PANEL + " " + text + " " * pad + C_RESET

    def _box_top(self, color, title, W, lead=2, bw=None):
        bw = bw or (W - lead)
        title = self._short(title, 14)
        X = max(0, bw - 5 - self._dlen(title))
        return " " * lead + color + "┌─ " + title + " " + "─" * X + "┐" + C_RESET

    def _box_row(self, color, text, W, lead=2, bw=None):
        bw = bw or (W - lead)
        pad = max(0, bw - 4 - self._dlen(text))
        return " " * lead + color + "│" + C_RESET + " " + text + " " * pad + " " + color + "│" + C_RESET

    def _box_bottom(self, color, W, lead=2, bw=None):
        bw = bw or (W - lead)
        return " " * lead + color + "└" + "─" * max(0, bw - 2) + "┘" + C_RESET

    def _card(self, color, text, W, top_gap=False, time_prefix=""):
        out = []
        if top_gap:
            out.append(self._card_row(color, "", W))
        lines = self._wrap(text, max(20, W - 6))
        for i, ln in enumerate(lines):
            if i == 0 and time_prefix:
                display = C_DIM + time_prefix + C_RESET + " " + ln
            else:
                display = ln
            out.append(self._card_row(color, display, W))
        return out

    def _notice_card(self, label, text, W):
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
        return self._card(color, " " * 0 + " " + icon + " [" + label + "] " + text, W)

    def _diff_card(self, d, W):
        out = []
        path = d["path"]
        title = ("← Edit " if d.get("exists") else "← Write ") + path
        out += self._card(C_ACC, C_BOLD + C_TEXT + title + C_RESET, W)
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
                num, b, mark = b, C_GOOD, "+"
            else:
                num, fg, mark = a, C_MUTED, " "
            txt = text.replace("\t", "  ")[: W - 12].replace("\n", " ")
            ln = fg + mark + str(num or " ").rjust(maxn) + " " + txt + C_RESET
            out.append(self._card_row(fg, ln, W))
        if collapsed:
            left = len(d["lines"]) - len(lines)
            out.append(self._card_row(C_ACC, C_BOLD + "… " + str(left) + " more" + C_RESET + stats + C_MUTED + "  [Enter] expand" + C_RESET, W))
        elif tail:
            out.append(self._card_row(C_MUTED, "… " + str(len(d["lines"]) - max_show) + " more", W))
        return out

    def frame_home(self, W, H):
        lines = [self._hdr("VOXEL AI", self._mode_chip() + "  v0.2 · " + self.model, W)]
        body = [""]
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
        body.append("  " + C_MUTED + "Sessions" + C_RESET)
        body.append("")
        from voxel.session import list_sessions
        items = [("__new__",)] + [(n,) for n, _, _, _ in list_sessions()]
        self.cur = max(0, min(self.cur, len(items) - 1))
        for i, item in enumerate(items[:10]):
            name = item[0]
            if name == "__new__":
                label = "+ New Chat"
                sub = "start a fresh conversation"
                is_new = True
            else:
                label = name
                sub = ""
                is_new = False
            if i == self.cur:
                if is_new:
                    pad = max(1, W - 6 - self._dlen(label) - self._dlen(sub))
                    body.append("  " + C_ACC + "│" + C_RESET + C_PANEL + " " + C_BOLD
                                + C_GOOD + label + C_RESET + C_PANEL + " " * pad
                                + C_MUTED + sub + C_RESET)
                else:
                    pad = max(1, W - 6 - self._dlen(label) - self._dlen(sub))
                    body.append("  " + C_ACC + "│" + C_RESET + C_PANEL + " " + C_BOLD
                                + C_TEXT + label + C_RESET + C_PANEL + " " * pad
                                + C_MUTED + sub + C_RESET)
            else:
                if is_new:
                    pad = max(1, W - 4 - self._dlen(label) - self._dlen(sub))
                    body.append("    " + C_GOOD + C_DIM + label + " " * pad + sub + C_RESET)
                else:
                    pad = max(1, W - 4 - self._dlen(label) - self._dlen(sub))
                    body.append("    " + C_DIM + label + " " * pad + sub + C_RESET)
        if not items:
            body.append("    " + C_DIM + "No sessions yet — type to start" + C_RESET)
        body.append("")
        if self.palette:
            body += self._palette_card(W)
        elif self.model_pick:
            body += self._model_pick_card(W)
        else:
            body.append("  " + C_MUTED + "↑/↓ select · Enter open · type = new chat · Ctrl+P = commands" + C_RESET)
        body.append("")
        body.append("  " + C_WARN + "● Tip" + C_RESET + " " + C_MUTED + "Type /help for commands · /models to change model" + C_RESET)
        for label, text in self.notices:
            body += self._notice_card(label, text, W)
        body_max = max(1, H - 3)
        if len(body) > body_max:
            body = body[-body_max:]
        else:
            body += [""] * (body_max - len(body))
        lines += body
        lines.append(self._prompt_line(W))
        lines.append(self._footer())
        return lines[:H]

    def frame_chat(self, W, H):
        tok = 0
        title = self.loaded_name or ("new chat" if len(self.messages) <= 1 else "chat")
        msg_count = len([m for m in self.messages if m.get("role") != "system"])
        right = f"{self._mode_chip()}  ● {self.model} · tok ~{tok} · $0"
        if msg_count > 0:
            title += f" · {msg_count} msgs"
        lines = [self._hdr("# " + title, right, W)]
        body = []
        for mi, msg in enumerate(self.messages[1:]):
            role, text = msg["role"], msg["content"]
            if role == "user":
                UW = max(28, int(W * 0.62))
                lead = max(4, W - UW)
                cw = W - lead - 2
                ulines = self._wrap(text, max(16, UW - 6))
                for i, ln in enumerate(ulines):
                    if i == 0:
                        content = C_BOLD + C_USER + "❯" + C_RESET + " " + C_TEXT + ln + C_RESET
                    else:
                        content = C_TEXT + ln + C_RESET
                    pad = max(0, cw - self._dlen(self._ansi_strip(content)))
                    body.append(" " * lead + content + " " * pad)
                body.append("")
            else:
                alines = self._assistant_block(msg.get("model") or self.model, text, W, msg_idx=mi + 1)
                body += alines
                body.append("")
        for label, text in self.notices:
            body += self._notice_card(label, text, W)
        for n in self.notes:
            if isinstance(n, dict):
                body += self._diff_card(n, W)
            else:
                for ln in self._wrap(self._short(n, W - 6), W - 6):
                    body.append("  " + C_DIM + ln + C_RESET)
        body_max = max(1, H - 5)
        if len(body) > body_max:
            max_scroll = len(body) - body_max
            self.scroll_off = max(0, min(self.scroll_off, max_scroll))
            start = len(body) - body_max - self.scroll_off
            body = body[start:len(body) - self.scroll_off]
            if self.scroll_off > 0:
                body[0] = "  " + C_MUTED + "↑ " + str(self.scroll_off) + " more · PgUp" + C_RESET
            if self.scroll_off < max_scroll:
                body[-1] = "  " + C_MUTED + "↓" + C_RESET
        else:
            self.scroll_off = 0
            body += [""] * (body_max - len(body))
        lines += body
        lines += self._prompt_box(W)
        lines.append(self._footer())
        return lines[:H]

    def _assistant_block(self, model, text, W, msg_idx=0):
        tag_re = re.compile(r"<(run|write|read|search)[^>]*>\s*(.*?)\s*</\1>", re.S)
        def tag_line(m):
            name = m.group(1)
            cmd = self._short(m.group(2), 45)
            return f"→ {name}" + (f": {cmd}" if cmd else "")
        text2 = tag_re.sub(tag_line, text)
        outside = []
        inner = []
        steps_lns = []
        has_text = False
        chunks = self._parse_sections(text2)
        for kind, title, content in chunks:
            if kind == "body":
                steps = [x for x in content.split("\n") if x.strip().startswith("→ ")]
                body = [x for x in content.split("\n") if not x.strip().startswith("→ ")]
                for s in steps:
                    steps_lns.append(self._status_line(s.strip(), W))
                body_txt = "\n".join(body).strip("\n")
                if body_txt.strip():
                    has_text = True
                    for ln in self._wrap(body_txt, max(20, W - 6)):
                        inner.append(C_TEXT + ln + C_RESET)
            elif kind == "head":
                has_text = True
                inner.append(C_HIGHLIGHT + C_TEXT + title + ":" + C_RESET)
                if content.strip():
                    for ln in self._wrap(content, max(20, W - 6)):
                        inner.append(C_TEXT + ln + C_RESET)
            elif kind == "sec":
                outside += self._section_block(title or "Details", content, W)
        if has_text:
            inner = steps_lns + ([""] if steps_lns else []) + inner
        else:
            for sln in steps_lns:
                outside.append("    " + C_MUTED + sln + C_RESET)
        if not inner:
            return outside
        bw = W - 2
        box = [self._box_top(C_ACC, "VOXEL", W)]
        for ln in inner:
            pad = max(0, bw - 4 - self._dlen(self._ansi_strip(ln)))
            box.append("  " + C_ACC + "│" + C_RESET + C_PANEL + " " + ln + " " * pad + C_RESET + " " + C_ACC + "│" + C_RESET)
        box.append("  " + C_ACC + "│" + C_RESET + C_PANEL + " " * (bw - 4) + C_RESET + " " + C_ACC + "│" + C_RESET)
        tag = C_DIM + self._short_tag(model) + C_RESET
        pad = max(0, bw - 4 - self._dlen(self._ansi_strip(tag)))
        box.append("  " + C_ACC + "│" + C_RESET + C_PANEL + " " * pad + tag + C_RESET + " " + C_ACC + "│" + C_RESET)
        box.append(self._box_bottom(C_ACC, W))
        return outside + box

    def _parse_sections(self, text):
        chunks = []
        cur_kind = "body"
        cur_title = None
        cur = []
        head_re = re.compile(r"^\*\*(.+?)\*\*:?\s*(.*)$")
        def push():
            content = "\n".join(cur).strip("\n")
            if content or cur_kind == "body":
                chunks.append((cur_kind, cur_title, content))
        lines = text.split("\n")
        i, n = 0, len(lines)
        while i < n:
            s = lines[i].strip()
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
            cur.append(lines[i])
            i += 1
        push()
        return chunks

    def _section_block(self, title, content, W, focused=False, no_suffix=False, pad=""):
        out = []
        suffix = "" if no_suffix else " (collapsed)"
        if focused:
            out.append(pad + C_ACC + "▸ " + C_RESET + C_MUTED + title + suffix + C_RESET + "  " + C_MUTED + "◄──" + C_RESET)
        else:
            out.append(pad + C_MUTED + "▸ " + title + suffix + C_RESET)
        return out

    def _status_line(self, ln, W):
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

    def _short_tag(self, model):
        parts = model.split("-")
        if not parts:
            return "ai"
        if parts[0].startswith("deepseek"):
            return "ds-" + (parts[1] if len(parts) > 1 else parts[0][:4])
        if len(parts) > 1:
            return parts[0][:2] + "-" + parts[1]
        return parts[0][:6]

    def _box_row_right(self, color, text, W, lead=2, bw=None):
        bw = bw or (W - lead)
        pad = max(0, bw - 4 - self._dlen(text))
        return " " * lead + color + "│" + C_RESET + " " * pad + text + " " + color + "│" + C_RESET

    def _ansi_strip(self, text):
        return re.sub(r"\x1b\[[0-9;]*m|\x1b\[[0-9;]*[A-Za-z]", "", text)

    def _prompt_line(self, W):
        disp = self.buf
        while self._dlen(disp) > W - 8:
            disp = disp[1:]
        if self._dlen(disp) > W - 9:
            disp = "…" + disp
        if disp:
            return "  " + C_ACC + "❯" + C_RESET + " " + C_TEXT + disp + C_RESET
        return ("  " + C_ACC + "❯" + C_RESET + " " + C_MUTED
                + "Type a message... (or /help)" + C_RESET)

    def _prompt_box(self, W):
        color = C_PLAN if self.mode == "plan" else C_BUILD
        disp = self.buf
        cursor = C_ACC + "▍" + C_RESET
        if self.tiny_input:
            if disp:
                inner = C_TEXT + disp + C_RESET + cursor
                plain = "❯ " + disp + "▍"
            else:
                inner = C_MUTED + "Type..." + C_RESET + cursor
                plain = "❯ Type...▍"
            pad = max(1, W - 4 - self._dlen(plain))
            return ["  " + color + "❯" + C_RESET + " " + inner + " " * pad]
        if disp:
            inner = C_TEXT + disp + C_RESET + cursor
            plain = "❯ " + disp + "▍"
        else:
            inner = C_MUTED + "Type a message... (or /help)" + C_RESET + cursor
            plain = "❯ " + "Type a message... (or /help)" + "▍"
        pad = max(1, W - 6 - self._dlen(plain))
        return [
            "  " + color + "┌" + "─" * (W - 4) + "┐" + C_RESET,
            "  " + color + "│" + C_RESET + " " + C_ACC + "❯" + C_RESET + " " + inner + " " * pad + " " + color + "│" + C_RESET,
            "  " + color + "└" + "─" * (W - 4) + "┘" + C_RESET,
        ]

    def _mode_chip(self):
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

    def _footer(self):
        if self.popup:
            return "  " + C_MUTED + "←/→ Select · Enter Confirm · q Deny" + C_RESET
        if self.palette:
            return "  " + C_MUTED + "↑/↓ Select · Enter Run · Esc Close" + C_RESET
        if self.streaming:
            return ("  " + C_ACC + self.spin + C_RESET + "  " + C_MUTED + "Thinking…" + C_RESET
                    + "  " + C_MUTED + "[Esc] Interrupt" + C_RESET)
        if self._tool_progress:
            name, arg, _ = self._tool_progress
            return ("  " + C_ACC + "⏳" + C_RESET + "  " + C_MUTED + f"{name}: {self._short(arg, 30)}" + C_RESET
                    + "  " + C_MUTED + "[Esc] Interrupt · [Ctrl+P] Commands" + C_RESET)
        if self.route == "home":
            return "  " + C_MUTED + "↑/↓ select · Enter open · type = new chat · Tab = Plan/Build" + C_RESET
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

    def _palette_card(self, W):
        out = []
        filter_txt = self.palette_filter
        shown = [c for c in _PALETTE_CMDS if filter_txt in c]
        title = "⌘ Commands" + (f" /{filter_txt}" if filter_txt else "")
        out += self._card(C_ACC, C_BOLD + title + C_RESET, W)
        if self.palette_idx >= len(shown):
            self.palette_idx = 0
        for i, c in enumerate(shown):
            if i == self.palette_idx:
                out.append(self._card_row(C_ACC, C_BOLD + "❯ " + c + C_RESET, W))
            else:
                out.append(self._card_row(C_MUTED, "  " + c, W))
        return out

    def _model_pick_card(self, W):
        out = []
        out += self._card(C_ACC, C_BOLD + "🤖 Models" + C_RESET, W)
        for i, m in enumerate(_FREE_MODELS):
            label = m
            if m == self.model:
                label += " ●"
            if i == self.model_idx:
                out.append(self._card_row(C_ACC, C_BOLD + "❯ " + label + C_RESET, W))
            else:
                out.append(self._card_row(C_MUTED, "  " + label, W))
        return out

    def redraw(self):
        if self.plain:
            return
        W, H = self._term_size()
        self.adaptive(W, H)
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
        with self._draw_lock:
            sys.stdout.write("".join(out))
            sys.stdout.flush()

    def adaptive(self, W, H):
        self.compact = W <= 50
        self.tiny_input = W <= 45
        self.tiny_rows = H <= 20
        self.wide = W >= 70

    def notice(self, label, text):
        if self.plain:
            for ln in text.split("\n"):
                print("  " + C_YELLOW + "[" + label + "] " + ln + C_RESET)
        else:
            self.notices = [(label, text)]
            self._notice_t = time.time()
            self.redraw()


_PALETTE_CMDS = ["/help", "/new", "/models", "/sessions", "/save", "/load", "/rm",
                 "/perm", "/stats", "/exit", "/undo"]
_FREE_MODELS = [
    "deepseek-v4-flash-free", "big-pickle", "mimo-v2.5-free",
    "laguna-s-2.1-free", "ling-3.0-flash-free", "north-mini-code-free",
    "nemotron-3-ultra-free",
]


# ---- session & permission helpers ----

def _safe_name(name):
    import re
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", str(name)).strip()
    return name or "chat"


def _open_session(self, name, agent):
    from voxel.session import save_session, load_session
    from voxel.constants import SYSTEM_PROMPT
    if name == "__new__":
        if len(self.messages) > 1:
            save_session("last", self.messages)
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
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
            self.notices = [("SYS", "Session not found: " + name)]
    if self.route != "chat":
        self.route = "chat"
    else:
        self.route = "chat"
        self.redraw()

TermUI.open_session = _open_session


def _delete_session(self):
    if not self.loaded_name:
        self.notice("SYS", "No saved session — Ctrl+D does nothing here.")
        self.redraw()
        return
    name = self.loaded_name
    self.popup = ("confirm", "Delete session '" + name + "'?")
    self.popup_idx = 0
    self._popup_birth_anim()
    try:
        while True:
            self.redraw()
            k = _tui_key_static()
            if k in ("RIGHT", "LEFT"):
                self.popup_idx = (self.popup_idx + 1) % 2
            elif k in ("q", "Q", "CTRL-C", "ESC"):
                break
            elif k in ("ENTER", ""):
                break
    finally:
        self.popup = None
        self.redraw()
    if self.popup_idx == 0:
        from voxel.session import delete_session
        from voxel.constants import SYSTEM_PROMPT
        delete_session(name)
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        self.session_perm = {"cmd": set(), "file": set()}
        self.loaded_name = None
        self.notices = []
        self.notes = []
        self.buf = ""
        self.status = "ready"
        self.notice("SYS", "Deleted: " + name)
        self.redraw()

TermUI.delete_session = _delete_session


def _commit_rename(self):
    from voxel.session import save_session
    from voxel.constants import CHATS_DIR
    name = self.buf.strip()
    self.renaming = False
    self.buf = ""
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        self.notice("SYS", "Invalid name: " + (name or "(empty)"))
        self.redraw()
        return
    old = self.loaded_name
    if old and old != name:
        import os
        src = os.path.join(CHATS_DIR, old + ".json")
        dst = os.path.join(CHATS_DIR, name + ".json")
        if not os.path.exists(src):
            self.notice("SYS", "Session not found: " + old)
        elif os.path.exists(dst):
            self.notice("SYS", "Name already exists: " + name)
        else:
            save_session(name, self.messages)
            os.remove(src)
            self.loaded_name = name
            self.notice("SYS", "Renamed: " + old + " -> " + name)
    elif not old:
        save_session(name, self.messages)
        self.loaded_name = name
        self.notice("SYS", "Saved as: " + name)
    self.redraw()

TermUI.commit_rename = _commit_rename


def _perm_popup(self, kind, key):
    self.popup = (kind, key)
    self.popup_idx = 0
    self._popup_birth_anim()
    try:
        while True:
            self.redraw()
            k = _tui_key_static()
            if k in ("RIGHT", "LEFT"):
                self.popup_idx = (self.popup_idx + 1) % 4
            elif k in ("1", "2", "3", "4"):
                self.popup_idx = int(k) - 1
                break
            elif k in ("q", "Q", "CTRL-C", "ESC"):
                self.popup_idx = 3
                break
            elif k in ("ENTER", ""):
                break
    finally:
        self.popup = None
        self.redraw()
    return ("allow_once", "allow_session", "always", "deny_once")[self.popup_idx]

TermUI.perm_popup = _perm_popup


# ---- raw key helper ----

def _tui_key_static():
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
        import os as _os
        import select as _select
        b = _os.read(fd, 1)
        if not b:
            return "CTRL-C"
        ch = b.decode("utf-8", errors="replace")
        if ch == "\x1b":
            r, _, _ = _select.select([fd], [], [], 0.06)
            if not r:
                return "ESC"
            nxt = _os.read(fd, 1).decode("utf-8", errors="replace")
            if nxt == "[":
                k = _os.read(fd, 1).decode("utf-8", errors="replace")
                if k == "A":
                    return "UP"
                if k == "B":
                    return "DOWN"
                if k == "C":
                    return "RIGHT"
                if k == "D":
                    return "LEFT"
                if k in ("5", "6"):
                    _os.read(fd, 1)
                    return "PGUP" if k == "5" else "PGDN"
                if k == "H":
                    return "HOME_K"
                if k == "F":
                    return "END_K"
                while True:
                    b2 = _os.read(fd, 1)
                    if not b2:
                        break
                    c2 = b2.decode("utf-8", errors="replace")
                    if c2 in "@ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz~`":
                        break
                return ""
            if nxt == "O":
                k = _os.read(fd, 1).decode("utf-8", errors="replace")
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
            r, _, _ = _select.select([fd], [], [], 0.02)
            if r:
                nxt = _os.read(fd, 1).decode("utf-8", errors="replace")
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
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ---- main input loop ----

def _input_loop(self, agent):
    from voxel.session import list_sessions, save_session
    import time
    while not self.quitting:
        try:
            if self.resized:
                self.resized = False
                self.redraw()
            k = _tui_key_static()
            if self.resized:
                self.resized = False
                self.redraw()
            if self.route == "home":
                self._key_home(k, agent)
            else:
                self._key_chat(k, agent)
        except Exception as e:
            self.notice("ERR", "Unexpected error: " + str(e))
            self.redraw()

TermUI.input_loop = _input_loop


def _key_home(self, k, agent):
    if self.palette:
        self._key_palette(k)
        return
    if self.model_pick:
        self._key_model_pick(k)
        return
    from voxel.session import list_sessions
    items = [("__new__",)] + [(n,) for n, _, _, _ in list_sessions()]
    if k == "UP":
        self.cur = max(0, self.cur - 1)
        self.redraw()
    elif k == "DOWN":
        self.cur = min(len(items) - 1, self.cur + 1)
        self.redraw()
    elif k == "ENTER":
        self.open_session(items[self.cur][0], agent)
    elif k in ("CTRL-C", "q", "Q"):
        self.quitting = True
    elif k == "CTRL-P":
        self.palette = True
        self.palette_idx = 0
        self.redraw()
    elif k == "TAB":
        self.mode = "plan" if self.mode == "build" else "build"
        self._mode_flash = time.time()
        self.notice("MODE", ("Plan mode ON" if self.mode == "plan" else "Build mode ON"))
        self.redraw()
    elif k == "ESC":
        self.redraw()
    elif k.isprintable():
        self.buf = k
        if k == "/":
            self.cmd_pick = True
            self.cmd_idx = 0
            self.redraw()
        else:
            self.open_session("__new__", agent)
    else:
        self.redraw()

TermUI._key_home = _key_home


def _key_chat(self, k, agent):
    self._cursor_on = True
    self._last_key = 0.0
    if self.palette:
        self._key_palette(k)
        return
    if self.sess_pick:
        self._key_sess_pick(k, agent)
        return
    if self.model_pick:
        self._key_model_pick(k)
        return
    if self.cmd_pick:
        self._key_cmd_pick(k, agent)
        return
    if k in ("WHEEL_UP", "WHEEL_DOWN", "PGUP", "PGDN"):
        step = 4 if k in ("WHEEL_UP", "WHEEL_DOWN") else 5
        if k in ("WHEEL_UP", "PGUP"):
            self.scroll_off += step
        else:
            self.scroll_off = max(0, self.scroll_off - step)
        self.redraw()
        return
    self.scroll_off = 0
    if k == "ENTER":
        if self.renaming:
            self.commit_rename()
            return
        text = self.buf
        if text.strip():
            self.hist.append(text)
            self.hidx = len(self.hist)
            self.buf = ""
            response = agent.run(text)
            if response:
                self.notice("SYS", response[:200])
            self.redraw()
        elif self.sec_focus:
            pass
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
        self.notice("SYS", "Auto-approve " + ("ON" if self.auto_approve else "OFF"))
        self.redraw()
    elif k == "CTRL-Z":
        agent._undo()
    elif k == "CTRL-T":
        self.timing_panel = not self.timing_panel
        self.redraw()
    elif k == "CTRL-A":
        self.anim = not self.anim
        self.notice("SYS", "Animations " + ("ON" if self.anim else "OFF"))
        self.redraw()
    elif k == "ESC":
        if self.renaming:
            self.renaming = False
            self.buf = ""
            self.redraw()
            return
        from voxel.session import save_session
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
        if self.buf.startswith("/"):
            self._complete()
        else:
            self.mode = "plan" if self.mode == "build" else "build"
            self._mode_flash = time.time()
            self.notice("MODE", ("Plan mode ON" if self.mode == "plan" else "Build mode ON"))
            self.redraw()
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

TermUI._key_chat = _key_chat


def _key_palette(self, k):
    from voxel.constants import PALETTE_CMDS
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
        self.buf = cmd + " " if cmd in ("/save", "/load", "/rm") else cmd
        self.redraw()
        return
    elif k == "BACK":
        self.palette_filter = self.palette_filter[:-1]
        self.palette_idx = 0
    elif k.isprintable():
        self.palette_filter += k
        self.palette_idx = 0
    elif k in ("ESC", "CTRL-C", "CTRL-P"):
        self.palette = False
        self.palette_filter = ""
        self._palette_t = 0.0
    self.redraw()

TermUI._key_palette = _key_palette


def _key_cmd_pick(self, k, agent):
    from voxel.constants import COMMAND_LIST
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
            self.notice("SYS", "Auto-approve ON")
        elif pick.startswith(("/save", "/load", "/rm")):
            self.buf = pick + " "
        else:
            self.buf = ""
            agent._run_command(pick)
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

TermUI._key_cmd_pick = _key_cmd_pick


def _key_sess_pick(self, k, agent):
    if k == "UP":
        self.sess_idx = max(0, self.sess_idx - 1)
    elif k == "DOWN":
        self.sess_idx = min(len(self.sess_pick) - 1, self.sess_idx + 1)
    elif k == "ENTER":
        from voxel.session import load_session
        name = self.sess_pick[self.sess_idx][0]
        self.sess_pick = None
        loaded = load_session(name)
        if loaded and loaded[0].get("role") == "system":
            self.messages = loaded
            self.loaded_name = name
            self.route = "chat"
            self.notices = [("SYS", f"Loaded: {name} ({len(loaded) - 1} messages)")]
        else:
            self.notice("SYS", "Session not found: " + name)
        self.redraw()
        return
    elif k in ("ESC", "CTRL-C", "CTRL-P"):
        self.sess_pick = None
    self.redraw()

TermUI._key_sess_pick = _key_sess_pick


def _key_model_pick(self, k):
    from voxel.constants import FREE_MODELS
    if k == "UP":
        self.model_idx = max(0, self.model_idx - 1)
    elif k == "DOWN":
        self.model_idx = min(len(FREE_MODELS) - 1, self.model_idx + 1)
    elif k == "ENTER":
        new_model = FREE_MODELS[self.model_idx]
        self.model = new_model
        self.cfg["model"] = new_model
        from voxel.config import save_config
        save_config(self.cfg)
        self.model_pick = None
        self.notice("SYS", "Model changed: " + new_model)
        self.redraw()
        return
    elif k in ("ESC", "CTRL-C", "CTRL-P"):
        self.model_pick = None
    self.redraw()

TermUI._key_model_pick = _key_model_pick


def _complete(self):
    from voxel.constants import COMMAND_LIST
    matches = [c for c in COMMAND_LIST if c.startswith(self.buf)]
    if not matches:
        return
    self._comp = (getattr(self, "_comp", -1) + 1) % len(matches)
    self.buf = matches[self._comp]
    self.redraw()

TermUI._complete = _complete
