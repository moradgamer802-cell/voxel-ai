"""Plain (non-TUI) fallback UI for MRNOT."""

from voxel.constants import C_BOLD, C_CYAN, C_DIM, C_GREEN, C_RED, C_RESET
import time


class PlainUI:
    def __init__(self, cfg, api_key, model):
        self.cfg = cfg
        self.api_key = api_key
        self.model = model
        self.plain = True
        self.route = "chat"
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
        self.resized = False
        self.quitting = False
        self._last_key = 0.0
        self._mode_flash = 0.0
        self._entrance = None
        self.spin = "⠋"
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

    def notice(self, label, text):
        for ln in text.split("\n"):
            print("  " + "\033[93m" + "[" + label + "] " + ln + "\033[0m")

    def perm_popup(self, kind, key):
        print(f"\n  \033[93m⚠ Permission required\033[0m: {key}")
        try:
            ans = input("  > Allow? (y/n): ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            return "deny_once"
        return "allow_once" if ans in ("y", "yes", "") else "deny_once"

    def redraw(self):
        pass

    def enter(self):
        pass

    def exit(self):
        pass

    def input_loop(self):
        pass
