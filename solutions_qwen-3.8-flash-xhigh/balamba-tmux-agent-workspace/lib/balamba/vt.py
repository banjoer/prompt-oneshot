"""vt.py — a pragmatic VT100/xterm screen model (stdlib only).

Reinterpretation note (README): the spec's middle column hosts live tmux panes;
in the Textual version it hosts *plain terminal sessions*, so the screen content
must be modelled here to paint it.  This module emulates the subset of xterm
that shells, `opencode`, vim and htop use: CSI/SGR colours (16/256/truecolor),
cursor addressing, scroll regions, insert/delete, alternate screens, tabs,
deferred wrap, OSC titles, DSR/DA replies, bracketed paste, mouse-reporting
flags and DEC private modes.  Unknown sequences are consumed, never printed.
"""

from __future__ import annotations

import codecs
import unicodedata
from rich.style import Style

# ---------------------------------------------------------------------------
# Colour palette (xterm values)
# ---------------------------------------------------------------------------

_BASE16 = [
    "#000000", "#cd0000", "#00cd00", "#cdcd00",
    "#0000ee", "#cd00cd", "#00cdcd", "#e5e5e5",
    "#7f7f7f", "#ff0000", "#00ff00", "#ffff00",
    "#5c5cff", "#ff00cd", "#00ffff", "#ffffff",
]


def _build_palette() -> list[str]:
    pal = list(_BASE16)
    levels = (0, 95, 135, 175, 215, 255)
    for r in levels:
        for g in levels:
            for b in levels:
                pal.append(f"#{r:02x}{g:02x}{b:02x}")
    for i in range(24):
        v = 8 + i * 10
        pal.append(f"#{v:02x}{v:02x}{v:02x}")
    return pal


PALETTE = _build_palette()

A_BOLD, A_DIM, A_ITALIC, A_UNDER, A_BLINK, A_REVERSE, A_STRIKE = (
    1, 2, 4, 8, 16, 32, 64)

BLANK_CELL: tuple[str, Style] = (" ", Style())
WIDE_SPARE: tuple[None, Style] = (None, Style())

_STYLE_CACHE: dict[tuple, Style] = {}


def _style_for(fg, bg, mask) -> Style:
    key = (fg, bg, mask)
    st = _STYLE_CACHE.get(key)
    if st is None:
        st = Style(
            color=fg,
            bgcolor=bg,
            bold=bool(mask & A_BOLD),
            dim=bool(mask & A_DIM),
            italic=bool(mask & A_ITALIC),
            underline=bool(mask & A_UNDER),
            blink=bool(mask & A_BLINK),
            reverse=bool(mask & A_REVERSE),
            strike=bool(mask & A_STRIKE),
        )
        if len(_STYLE_CACHE) < 20000:
            _STYLE_CACHE[key] = st
    return st


def cell_width(ch: str) -> int:
    if not ch:
        return 1
    if unicodedata.combining(ch):
        return 0
    return 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1


# parser states
GROUND, ESCAPE, ESC_INTER, CSI, OSC, DCS, ST_WAIT = 0, 1, 2, 3, 4, 5, 6


class ScreenBuffer:
    def __init__(self, rows: int, cols: int) -> None:
        self.rows = rows
        self.cols = cols
        self.grid: list[list[tuple]] = []
        self.clear_all()

    def clear_all(self) -> None:
        self.grid = [[BLANK_CELL] * self.cols for _ in range(self.rows)]

    def resize(self, rows: int, cols: int) -> None:
        old = self.grid
        self.rows, self.cols = rows, cols
        new = []
        for r in range(rows):
            line = old[r][:cols] if r < len(old) else []
            line = list(line) + [BLANK_CELL] * (cols - len(line))
            new.append(line)
        self.grid = new

    def blank_row(self) -> list[tuple]:
        return [BLANK_CELL] * self.cols


class VT:
    """Byte-in, screen-out terminal emulator (not a thread — UI thread only)."""

    MAX_SCROLLBACK = 2000

    def __init__(self, rows: int = 24, cols: int = 80) -> None:
        self.rows, self.cols = rows, cols
        self.main = ScreenBuffer(rows, cols)
        self.alt: ScreenBuffer | None = None
        self.buf = self.main
        self.on_alt = False

        self.row = 0
        self.col = 0
        self._saved = (0, 0)
        self.wrap_next = False
        self.mtop, self.mbot = 0, rows - 1

        self.fg: str | None = None
        self.bg: str | None = None
        self.mask = 0
        self.modes: dict[str, bool] = {
            "?7": True,    # autowrap on
            "20": False,   # LF acts as CRLF
        }
        self.title = ""
        self.tab_stops: set[int] = set(range(8, cols, 8))

        self.scrollback: list[list[tuple]] = []
        self.last_char = ""

        self.replies = bytearray()   # bytes the host must write back to the child
        self.changed = False
        self.bell_count = 0
        self.exited_note = ""

        self._state = GROUND
        self._params = bytearray()
        self._inter = bytearray()
        self._private = False
        self._gt = False
        self._osc = bytearray()
        self._osc_by_esc = False
        self._decoder = codecs.getincrementaldecoder("utf-8")("replace")

    # -- properties used by the widget ---------------------------------------
    @property
    def cursor_visible(self) -> bool:
        return self.modes.get("?25", True)

    @property
    def app_cursor_keys(self) -> bool:
        return self.modes.get("?1", False)

    @property
    def bracketed_paste(self) -> bool:
        return self.modes.get("?2004", False)

    @property
    def focus_tracking(self) -> bool:
        return self.modes.get("?1004", False)

    @property
    def mouse_mode(self) -> int:
        """0 none · 1 clicks · 2 + drag · 3 + any motion."""
        if self.modes.get("?1003"):
            return 3
        if self.modes.get("?1002"):
            return 2
        if self.modes.get("?1000") or self.modes.get("?9"):
            return 1
        return 0

    @property
    def mouse_sgr(self) -> bool:
        return bool(self.modes.get("?1006"))

    def style(self) -> Style:
        return _style_for(self.fg, self.bg, self.mask)

    # -- feed ------------------------------------------------------------------
    def feed(self, data: bytes) -> None:
        i, n = 0, len(data)
        while i < n:
            b = data[i]
            st = self._state
            if st == GROUND:
                if b == 0x1B:
                    self._enter_escape()
                    i += 1
                elif b < 0x20:
                    self._do_control(b)
                    i += 1
                else:
                    j = i
                    while j < n:
                        b2 = data[j]
                        if b2 == 0x1B or b2 < 0x20:
                            break
                        j += 1
                    # 0x7f (DEL) is skipped rather than printed
                    run = bytes(x for x in data[i:j] if x != 0x7F)
                    if run:
                        text = self._decoder.decode(run)
                        for ch in text:
                            self._put_char(ch)
                    i = j
            elif st in (ESCAPE, ESC_INTER):
                if 0x20 <= b <= 0x2F:
                    self._inter.append(b)
                    self._state = ESC_INTER
                    i += 1
                else:
                    self._do_escape(b)
                    i += 1
            elif st == CSI:
                if 0x40 <= b <= 0x7E:
                    self._do_csi(b)
                    i += 1
                elif b in (0x3C, 0x3D, 0x3E):      # < = >  (e.g. CSI > c)
                    self._gt = True
                    i += 1
                elif b == 0x3F:                     # ?  private
                    self._private = True
                    i += 1
                elif 0x20 <= b <= 0x2F:             # intermediates
                    self._inter.append(b)
                    i += 1
                else:
                    self._params.append(b)
                    i += 1
            elif st == OSC:
                if b == 0x07:
                    self._finish_osc()
                    i += 1
                elif b == 0x1B:
                    self._osc_by_esc = True
                    self._state = ST_WAIT
                    i += 1
                else:
                    self._osc.append(b)
                    i += 1
            elif st == DCS:
                if b == 0x07:
                    self._state = GROUND
                    i += 1
                elif b == 0x1B:
                    self._osc_by_esc = False
                    self._state = ST_WAIT
                    i += 1
                else:
                    i += 1
            elif st == ST_WAIT:                     # waiting for the '\' of ESC '\'
                self._state = GROUND
                if b == 0x5C:
                    if self._osc_by_esc:
                        self._finish_osc()
                elif b == 0x1B:
                    i += 1
                    continue                        # another ESC: stay waiting
                i += 1
        # leave the decoder ready for the next chunk

    def _enter_escape(self) -> None:
        self._decoder.reset()
        self._state = ESCAPE
        self._inter.clear()

    def _do_control(self, b: int) -> None:
        if b == 0x07:
            self.bell_count += 1
        elif b == 0x08:
            self._backspace()
        elif b == 0x09:
            self._tab_forward()
        elif b in (0x0A, 0x0B, 0x0C):
            self._line_feed(cr=(b == 0x0A and self.modes.get("20", False)))
        elif b == 0x0D:
            self._carriage_return()
        else:
            pass  # remaining C0 bytes are ignored

    def _mark(self) -> None:
        self.changed = True

    # -- character placement ------------------------------------------------------
    def _put_char(self, ch: str) -> None:
        if not ch or unicodedata.combining(ch):
            return
        w = cell_width(ch)
        if self.wrap_next:
            self.wrap_next = False
            self._line_feed()
            self.col = 0
        if self.col + w > self.cols:
            if self.modes.get("?7", True):
                self._line_feed()
                self.col = 0
            else:
                return
        self._put_cell(ch, w)
        self.last_char = ch

    def _put_cell(self, ch: str, w: int) -> None:
        style = self.style()
        line = self.buf.grid[self.row]
        if self.modes.get("4"):
            for _ in range(w):
                line.insert(self.col, BLANK_CELL)
            del line[self.cols:]
        line[self.col] = (ch, style)
        if w == 2 and self.col + 1 < self.cols:
            line[self.col + 1] = WIDE_SPARE
        self.col += w
        if self.col >= self.cols:
            if self.modes.get("?7", True):
                self.col = self.cols - w
                self.wrap_next = True
            else:
                self.col = self.cols - 1
        self._mark()

    # -- cursor movement / scrolling --------------------------------------------------
    def _carriage_return(self) -> None:
        self.col = 0
        self.wrap_next = False

    def _backspace(self) -> None:
        if self.wrap_next:
            self.wrap_next = False
            self.col = self.cols - 1
        elif self.col > 0:
            self.col -= 1

    def _tab_forward(self) -> None:
        col = self.col
        while col + 1 < self.cols:
            col += 1
            if col in self.tab_stops:
                self.col = col
                self.wrap_next = False
                return
        self.col = self.cols - 1
        self.wrap_next = False

    def _line_feed(self, cr: bool = False) -> None:
        if self.row == self.mbot:
            self._scroll_up(1)
        elif self.row < self.rows - 1:
            self.row += 1
        if cr:
            self.col = 0
        self.wrap_next = False

    def _reverse_index(self) -> None:
        if self.row == self.mtop:
            self._scroll_down(1)
        elif self.row > 0:
            self.row -= 1
        self.wrap_next = False

    def _scroll_up(self, n: int) -> None:
        top, bot = self.mtop, self.mbot
        n = min(n, bot - top + 1)
        blank = self._blank_cell()
        for _ in range(n):
            removed = self.buf.grid.pop(top)
            if self.buf is self.main and top == 0 and bot == self.buf.rows - 1:
                self.scrollback.append(removed)
                if len(self.scrollback) > self.MAX_SCROLLBACK:
                    self.scrollback.pop(0)
            self.buf.grid.insert(bot, [blank] * self.buf.cols)
        self._mark()

    def _scroll_down(self, n: int) -> None:
        top, bot = self.mtop, self.mbot
        n = min(n, bot - top + 1)
        blank = self._blank_cell()
        for _ in range(n):
            self.buf.grid.pop(bot)
            self.buf.grid.insert(top, [blank] * self.buf.cols)
        self._mark()

    def _move(self, row: int | None = None, col: int | None = None) -> None:
        if row is not None:
            self.row = max(0, min(self.rows - 1, row))
        if col is not None:
            self.col = max(0, min(self.cols - 1, col))
        self.wrap_next = False

    # -- erase -----------------------------------------------------------------------
    def _blank_cell(self) -> tuple:
        return (" ", _style_for(None, self.bg, 0)) if self.bg else BLANK_CELL

    def _erase_line(self, mode: int) -> None:
        line = self.buf.grid[self.row]
        blank = self._blank_cell()
        if mode == 0:
            for c in range(self.col, self.cols):
                line[c] = blank
        elif mode == 1:
            for c in range(0, min(self.col, self.cols - 1) + 1):
                line[c] = blank
        else:
            self.buf.grid[self.row] = [blank] * self.cols
        self._mark()

    def _erase_display(self, mode: int) -> None:
        blank = self._blank_cell()
        if mode == 0:
            self._erase_line(0)
            for r in range(self.row + 1, self.rows):
                self.buf.grid[r] = [blank] * self.cols
        elif mode == 1:
            self._erase_line(1)
            for r in range(0, self.row):
                self.buf.grid[r] = [blank] * self.cols
        elif mode in (2, 3):
            for r in range(self.rows):
                self.buf.grid[r] = [blank] * self.cols
            if mode == 3:
                self.scrollback.clear()
        self._mark()

    def _insert_lines(self, n: int) -> None:
        if not (self.mtop <= self.row <= self.mbot):
            return
        blank = self._blank_cell()
        for _ in range(n):
            self.buf.grid.pop(self.mbot)
            self.buf.grid.insert(self.row, [blank] * self.buf.cols)
        self._mark()

    def _delete_lines(self, n: int) -> None:
        if not (self.mtop <= self.row <= self.mbot):
            return
        for _ in range(n):
            self.buf.grid.pop(self.row)
            self.buf.grid.insert(self.mbot, self.buf.blank_row())
        self._mark()

    # -- ESC sequences -------------------------------------------------------------------
    def _do_escape(self, b: int) -> None:
        self._state = GROUND
        self._inter.clear()
        if b == ord("["):
            self._state = CSI
            self._params.clear()
            self._private = False
            self._gt = False
            return
        if b == ord("]"):
            self._state = OSC
            self._osc = bytearray()
            return
        if b in (ord("P"), ord("_"), ord("^")):      # DCS / APC / PM — discard
            self._state = DCS
            return
        if b in (ord("("), ord(")"), ord("*"), ord("+")):
            self._state = ESC_INTER                  # swallow designator byte
            return
        if b == ord("7"):
            self._saved = (self.row, self.col)
        elif b == ord("8"):
            self.row, self.col = self._saved
            self.wrap_next = False
        elif b == ord("="):
            self.modes["?1"] = True
        elif b == ord(">"):
            self.modes["?1"] = False
        elif b == ord("D"):
            self._line_feed()                        # Index
        elif b == ord("E"):
            self._carriage_return()
            self._line_feed()                        # NEL
        elif b == ord("M"):
            self._reverse_index()                    # RI
        elif b == ord("H"):
            self.tab_stops.add(self.col)             # HTS
        elif b == ord("c"):
            self._hard_reset()

    def _finish_osc(self) -> None:
        payload = self._osc.decode("utf-8", "replace")
        self._osc = bytearray()
        self._osc_by_esc = False
        self._state = GROUND
        code, _, data = payload.partition(";")
        if code in ("0", "1", "2"):
            self.title = data
        # other OSCs (colours, hyperlinks, clipboard) are accepted and ignored

    # -- CSI -----------------------------------------------------------------------------
    def _params_list(self) -> list[int]:
        if not self._params:
            return []
        out = []
        for token in self._params.split(b";"):
            head = token.split(b":")[0]
            try:
                out.append(int(head) if head else 0)
            except ValueError:
                out.append(0)
        return out

    def _p(self, params: list[int], idx: int, default: int = 0) -> int:
        return params[idx] if idx < len(params) else default

    def _do_csi(self, b: int) -> None:
        self._state = GROUND
        params = self._params_list()
        private, gt = self._private, self._gt
        self._params.clear()
        self._inter.clear()
        self._private = False
        self._gt = False

        if b == ord("@"):
            self._insert_chains(self._p(params, 0, 1) or 1)
        elif b == ord("A"):
            self._move(row=self.row - max(1, self._p(params, 0, 1)))
        elif b == ord("B"):
            self._move(row=self.row + max(1, self._p(params, 0, 1)))
        elif b == ord("C"):
            self._move(col=self.col + max(1, self._p(params, 0, 1)))
        elif b == ord("D"):
            self._move(col=self.col - max(1, self._p(params, 0, 1)))
        elif b == ord("E"):
            self._move(row=self.row + (self._p(params, 0, 1) or 1))
            self._carriage_return()
        elif b == ord("F"):
            self._move(row=self.row - (self._p(params, 0, 1) or 1))
            self._carriage_return()
        elif b == ord("G"):
            self._move(col=self._p(params, 0, 1) - 1)
        elif b in (ord("H"), ord("f")):
            self._move(self._p(params, 0, 1) - 1, self._p(params, 1, 1) - 1)
        elif b == ord("J"):
            self._erase_display(self._p(params, 0, 0))
        elif b == ord("K"):
            self._erase_line(self._p(params, 0, 0))
        elif b == ord("L"):
            self._insert_lines(self._p(params, 0, 1) or 1)
        elif b == ord("M"):
            self._delete_lines(self._p(params, 0, 1) or 1)
        elif b == ord("P"):
            self._delete_chains(self._p(params, 0, 1) or 1)
        elif b == ord("S"):
            self._scroll_up(self._p(params, 0, 1) or 1)
        elif b == ord("T"):
            self._scroll_down(self._p(params, 0, 1) or 1)
        elif b == ord("X"):
            n = self._p(params, 0, 1) or 1
            line = self.buf.grid[self.row]
            blank = self._blank_cell()
            for c in range(self.col, min(self.col + n, self.cols)):
                line[c] = blank
            self._mark()
        elif b == ord("Z"):
            col = self.col
            while col > 0 and col not in self.tab_stops:
                col -= 1
            self.col = max(0, col)
            self.wrap_next = False
        elif b == ord("b"):
            if self.last_char:
                for _ in range(self._p(params, 0, 1) or 1):
                    self._put_char(self.last_char)
        elif b == ord("d"):
            self._move(row=self._p(params, 0, 1) - 1)
        elif b == ord("g"):
            mode = self._p(params, 0, 0)
            if mode == 0:
                self.tab_stops.discard(self.col)
            elif mode in (3, 5):
                self.tab_stops.clear()
        elif b == ord("m"):
            self._sgr(params)
        elif b == ord("r"):
            top = self._p(params, 0, 1) - 1
            bot = self._p(params, 1, self.rows) - 1
            if 0 <= top < bot < self.rows:
                self.mtop, self.mbot = top, bot
                self._move(0, 0)
        elif b == ord("s"):
            self._saved = (self.row, self.col)
        elif b == ord("u"):
            self.row, self.col = self._saved
            self.wrap_next = False
        elif b == ord("n"):
            if self._p(params, 0, 0) == 5:
                self.replies.extend(b"\x1b[0n")
            elif self._p(params, 0, 0) == 6:
                self.replies.extend(
                    f"\x1b[{self.row + 1};{self.col + 1}R".encode())
        elif b == ord("c"):
            self.replies.extend(
                b"\x1b[>0;95;0c" if gt else b"\x1b[?1;2c")
        elif b in (ord("h"), ord("l")):
            self._set_modes(params, on=(b == ord("h")), private=private)
        # window ops (t), DECSTR (soft reset $p), DECRQM, DECSCUSR ( q) — ignored

    def _insert_chains(self, n: int) -> None:
        line = self.buf.grid[self.row]
        for _ in range(n):
            line.insert(self.col, BLANK_CELL)
            if len(line) > self.cols:
                line.pop()
        self._mark()

    def _delete_chains(self, n: int) -> None:
        line = self.buf.grid[self.row]
        for _ in range(n):
            if self.col < len(line):
                line.pop(self.col)
            line.append(BLANK_CELL)
        self._mark()

    # -- SGR -------------------------------------------------------------------------------
    def _sgr(self, params: list[int]) -> None:
        if not params:
            params = [0]
        i = 0
        while i < len(params):
            p = params[i]
            if p == 0:
                self.fg = self.bg = None
                self.mask = 0
            elif p in (1, 2, 3, 4, 5, 7):
                self.mask |= {1: A_BOLD, 2: A_DIM, 3: A_ITALIC,
                              4: A_UNDER, 5: A_BLINK, 7: A_REVERSE}[p]
            elif p == 6:
                self.mask |= A_BLINK
            elif p == 9:
                self.mask |= A_STRIKE
            elif p == 21:
                self.mask |= A_UNDER
            elif p == 22:
                self.mask &= ~(A_BOLD | A_DIM)
            elif p == 23:
                self.mask &= ~A_ITALIC
            elif p == 24:
                self.mask &= ~A_UNDER
            elif p == 25:
                self.mask &= ~A_BLINK
            elif p == 27:
                self.mask &= ~A_REVERSE
            elif p == 28:
                self.mask &= ~A_DIM
            elif p == 29:
                self.mask &= ~A_STRIKE
            elif 30 <= p <= 37:
                self.fg = PALETTE[p - 30]
            elif p == 38:
                self.fg, i = self._extended_color(params, i, self.fg)
            elif p == 39:
                self.fg = None
            elif 40 <= p <= 47:
                self.bg = PALETTE[p - 40]
            elif p == 48:
                self.bg, i = self._extended_color(params, i, self.bg)
            elif p == 49:
                self.bg = None
            elif 90 <= p <= 97:
                self.fg = PALETTE[p - 82]
            elif 100 <= p <= 107:
                self.bg = PALETTE[p - 92]
            i += 1

    @staticmethod
    def _extended_color(params: list[int], i: int, current):
        kind = params[i + 1] if i + 1 < len(params) else None
        if kind == 5 and i + 2 < len(params):
            return PALETTE[min(255, max(0, params[i + 2]))], i + 2
        if kind == 2 and i + 4 < len(params):
            r, g, b = params[i + 2], params[i + 3], params[i + 4]
            return f"#{r & 255:02x}{g & 255:02x}{b & 255:02x}", i + 4
        return current, i

    # -- modes --------------------------------------------------------------------------------
    def _set_modes(self, params: list[int], on: bool, private: bool) -> None:
        for p in (params or [0]):
            key = f"?{p}" if private else str(p)
            if private and p in (47, 1047, 1049):
                self._alternate_screen(on, full=(p == 1049))
                continue
            self.modes[key] = on
            if not private and p == 4:
                pass  # IRM already keyed as "4"

    def _alternate_screen(self, on: bool, full: bool = False) -> None:
        if on:
            if self.on_alt:
                return
            if full:
                self._saved = (self.row, self.col)
            if self.alt is None:
                self.alt = ScreenBuffer(self.rows, self.cols)
            self.alt.clear_all()
            self.buf = self.alt
            self.on_alt = True
        else:
            if not self.on_alt:
                return
            self.buf = self.main
            self.on_alt = False
            if full:
                self.row, self.col = self._saved
        self._mark()

    def _hard_reset(self) -> None:
        rows, cols = self.rows, self.cols
        self.__init__(rows, cols)  # type: ignore[misc]

    # -- resize ---------------------------------------------------------------------------------
    def resize(self, rows: int, cols: int) -> None:
        if (rows, cols) == (self.rows, self.cols):
            return
        self.rows, self.cols = rows, cols
        self.main.resize(rows, cols)
        if self.alt:
            self.alt.resize(rows, cols)
        self.tab_stops = set(range(8, cols, 8))
        self.mtop, self.mbot = 0, rows - 1
        self.row = min(self.row, rows - 1)
        self.col = min(self.col, cols - 1)
        self._mark()

    # -- render / test helpers ---------------------------------------------------------------------
    def line_text(self, r: int) -> str:
        line = self.buf.grid[r]
        chars = []
        for ch, _ in line:
            if ch is None:
                continue  # wide-character spare
            chars.append(" " if ch == "" else ch)
        return "".join(chars)

    def screen_text(self) -> list[str]:
        return [self.line_text(r).rstrip() for r in range(self.rows)]
