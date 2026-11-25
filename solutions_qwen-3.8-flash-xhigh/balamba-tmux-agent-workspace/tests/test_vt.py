import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lib"))

from balamba.vt import VT


def feed_all(v: VT, data: bytes) -> None:
    v.feed(data)
    v.replies.clear()


def test_plain_text_and_newline():
    v = VT(4, 10)
    feed_all(v, b"hello\r\nworld")
    assert v.line_text(0) == "hello     "
    assert v.line_text(1) == "world     "


def test_sgr_colors_and_reset():
    v = VT(2, 10)
    feed_all(v, b"\x1b[31mR\x1b[0mN")
    assert v.main.grid[0][0][1].color.triplet.hex == "#cd0000"
    assert v.main.grid[0][1][1].color is None


def test_256_and_truecolor():
    v = VT(2, 10)
    feed_all(v, b"\x1b[38;5;196mX\x1b[48;2;16;32;48mY")
    assert v.main.grid[0][0][1].color.triplet.hex == "#ff0000"
    assert v.main.grid[0][1][1].bgcolor.triplet.hex == "#102030"


def test_cursor_addressing_and_erase():
    v = VT(3, 8)
    feed_all(v, b"ABCD\x1b[2;3HC\x1b[1;1H\x1b[3D")   # move left past col0 clamps
    assert v.col == 0
    feed_all(v, b"\x1b[3;1HEL\x1b[K")
    assert v.line_text(2) == "EL      "
    feed_all(v, b"\x1b[2J")
    assert all(ln.strip() == "" for ln in v.screen_text())


def test_scroll_and_scrollback():
    v = VT(3, 5)
    feed_all(v, b"1\r\n2\r\n3\r\n4\r\n5")
    assert v.screen_text() == ["3", "4", "5"]
    assert v.scrollback[0][0][0] == "1"
    assert v.scrollback[1][0][0] == "2"


def test_scroll_region():
    v = VT(5, 5)
    feed_all(v, b"a\r\nb\r\nc\r\nd\r\ne\x1b[2;4r\x1b[4;1Hx\r\ny\r\nz")
    # rows 1..3 (0-based) scroll; row 0 and 4 untouched
    assert v.line_text(0) == "a    "
    assert v.line_text(4) == "e    "
    assert v.line_text(1) == "x    "   # only the region rows scroll
    assert v.line_text(2) == "y    "
    assert v.line_text(3) == "z    "
    assert v.mtop == 1 and v.mbot == 3


def test_insert_delete_lines():
    v = VT(3, 5)
    feed_all(v, b"one\r\ntwo\r\nthree\x1b[1;1H\x1b[1L")
    assert v.screen_text() == ["", "one", "two"]  # 'three' pushed off region
    feed_all(v, b"\x1b[1;1H\x1b[2M")
    assert v.screen_text()[0].strip() == "two"


def test_alt_screen_roundtrip():
    v = VT(2, 8)
    feed_all(v, b"MAIN")
    feed_all(v, b"\x1b[?1049h\x1b[HALT")
    assert v.on_alt and v.line_text(0) == "ALT     "
    feed_all(v, b"\x1b[?1049l")
    assert not v.on_alt and v.line_text(0) == "MAIN    "


def test_wrap_deferred():
    v = VT(2, 4)
    feed_all(v, b"abcdefg")
    assert v.line_text(0) == "abcd"
    assert v.line_text(1) == "efg "


def test_tabs_and_wide_chars():
    v = VT(2, 20)
    feed_all(v, b"a\tb")
    assert v.col == 9
    v2 = VT(2, 10)
    feed_all(v2, "日本語".encode())          # 6 columns, then wraps in rows of 10
    assert v2.line_text(0).startswith("日本")


def test_dsr_and_da_replies():
    v = VT(4, 10)
    v.feed(b"\x1b[3;4H\x1b[6n\x1b[c\x1b[>c")
    assert bytes(v.replies) == b"\x1b[3;4R\x1b[?1;2c\x1b[>0;95;0c"


def test_modes_captured():
    v = VT(2, 10)
    v.feed(b"\x1b[?2004h\x1b[?1000;1006h\x1b[?1h\x1b[?25l")
    assert v.bracketed_paste and v.mouse_mode == 1 and v.mouse_sgr
    assert v.app_cursor_keys and not v.cursor_visible


def test_osc_title_and_st_terminator():
    v = VT(2, 10)
    v.feed(b"\x1b]0;my title\x07")
    assert v.title == "my title"
    v.feed(b"\x1b]2;another\x1b\\")
    assert v.title == "another"
    assert v.line_text(0).strip() == ""


def test_dcs_discarded():
    v = VT(2, 10)
    v.feed(b"\x1bP0;q=6;2\x1b\\OK")
    assert v.line_text(0).startswith("OK")


def test_bs_and_cr_and_il():
    v = VT(2, 5)
    feed_all(v, b"abcde\b\bX")     # backspace twice, overwrite at col 3
    assert v.line_text(0) == "abcXe"


def test_resize_preserves_content():
    v = VT(4, 10)
    feed_all(v, b"line1\r\nline2")
    v.resize(6, 15)
    assert v.line_text(0).startswith("line1")
    v.resize(2, 4)
    assert v.line_text(0) == "line"


def test_rep_and_echo_and_chains():
    v = VT(2, 10)
    feed_all(v, b"a\x1b[3baa")      # 'a' + 4 more via REP? set 3 -> a + aaa
    assert v.line_text(0).startswith("aaaa")
    feed_all(v, b"\x1b[HXX\x1b[2X")  # ECH erases the two cells under the cursor
    assert v.line_text(0)[0] == "X"  # cursor sits at col 2 after printing; erase 2+
    assert v.line_text(0).startswith("XX")
