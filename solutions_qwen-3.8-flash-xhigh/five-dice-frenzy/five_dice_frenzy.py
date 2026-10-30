#!/usr/bin/env python3
# ===========================================================================
# Five-Dice Frenzy — a Yahtzee-lite dice game for the terminal.
#
#   Produced : 2026-10-30 00:06 CET  (2026-10-29 23:06 UTC)
#   Author   : Qwen3.8 Flash, thinking effort "xhigh", via OpenCode
#   Stack    : Python 3.8+ standard library only (argparse, os, random, sys,
#              time) — no installs, no network, nothing written to disk.
#
#   Run      : python3 five_dice_frenzy.py [--fast] [--chance] [--seed N]
#
# Five dice, one optional re-roll per turn, six scorecard categories, six
# turns, one honest total.  This file reads top to bottom: dice art and the
# roll animation, the scoring rules, the scorecard rendering, validated
# input helpers, the game loop, and a self-test.
# ===========================================================================
"""Five-Dice Frenzy — a pocket dice-poker game, played against the sheet.

Usage:
    python3 five_dice_frenzy.py [options]

Options:
    --fast        skip the ~1s dice-roll animation (impatient players)
    --chance      stretch rule: a 7th "Chance" category (sum of all dice),
                  which extends the game to 7 turns
    --no-color    disable ANSI colours (also auto-off when not a terminal,
                  or when the NO_COLOR environment variable is set)
    --seed N      deterministic dice, for reproducible games and testing
    --self-test   verify the scoring rules against the challenge examples
    -h, --help    show this help

Notes on behaviour:
    * The animation redraws the dice block in place using carriage returns
      and cursor-up escapes, so it only runs when stdout is a terminal.
      When output is redirected the settled hand is printed plainly, and the
      game itself is identical.
    * Held dice keep their faces while the re-rolled ones flash.
    * Scoring follows the written rules: Three of a Kind is the sum of *all*
      five dice; a Full House is exactly three-of-a-kind plus a pair (five
      alike is not a house); a Small Straight needs four consecutive values.
"""

import argparse
import os
import random
import sys
import time

# ---------------------------------------------------------------------------
# Sign-off — repeated in the welcome banner so it is easy to spot.
# ---------------------------------------------------------------------------
BUILT_AT = "2026-10-30 00:06 CET"
AUTHOR = "Qwen3.8 Flash (xhigh)"   # thinking effort in the header above
SIGN_OFF = "Built " + BUILT_AT + " by " + AUTHOR + " · OpenCode"

# ---------------------------------------------------------------------------
# ANSI helpers: colour and cursor movement, both switch-offable.
# ---------------------------------------------------------------------------
_RESET = "\033[0m"
_BOLD = "\033[1m"
_PALETTE = {
    "dice": "\033[96m",   # bright cyan — die frames
    "hold": "\033[90m",   # grey        — held dice, table chrome
    "good": "\033[92m",   # green       — points scored
    "bad": "\033[93m",    # yellow      — zeroes, gentle warnings
    "head": "\033[95m",   # magenta     — titles, banners, table rules
    "info": "\033[94m",   # blue        — prompts and roll chatter
}

USE_COLOR = False   # set by main(): off for pipes, --no-color, self-test
ANIMATING = False   # set by main(): only when the block can be redrawn


def paint(text, key):
    """Colour `text`.  Pad or centre the plain string *first* — widths must
    never have to account for escape codes."""
    if not USE_COLOR:
        return text
    return _PALETTE.get(key, "") + text + _RESET


def bold(text):
    return (_BOLD + text + _RESET) if USE_COLOR else text


def rule(text="", char="─", width=44):
    """A labelled divider: `── Turn 2/6 ──────────────`."""
    lead = f" {text} " if text else ""
    return char * 2 + lead + char * max(0, width - 2 - len(lead))


# ---------------------------------------------------------------------------
# Dice faces: five art lines per die, drawn side by side as boxes.
# ---------------------------------------------------------------------------
PIP_ROWS = {
    1: ("     ", "  ●  ", "     "),
    2: ("   ● ", "     ", " ●   "),
    3: ("   ● ", "  ●  ", " ●   "),
    4: (" ● ● ", "     ", " ● ● "),
    5: (" ● ● ", "  ●  ", " ● ● "),
    6: (" ● ● ", " ● ● ", " ● ● "),
}
BOX_GAP = "  "      # two spaces between neighbouring dice
# One die is 7 columns wide, so a hand is 5 x 7 + 4 x 2 = 43 columns plus a
# two-space indent — comfortably inside the assumed 80x24 terminal.


def die_lines(value, index, held=False):
    """The five art lines for one die; its index sits in the top border.

    Dice the player decided to keep are dimmed so a re-roll reads clearly.
    """
    interior = PIP_ROWS[value]
    rows = [f"┌──{index}──┐", f"│{interior[0]}│", f"│{interior[1]}│",
            f"│{interior[2]}│", "└─────┘"]
    return [paint(row, "hold" if held else "dice") for row in rows]


def hand_lines(dice, held_indexes=()):
    """Render the row of dice plus a compact numeric read-out."""
    rows = [die_lines(v, i + 1, (i + 1) in held_indexes)
            for i, v in enumerate(dice)]
    lines = [BOX_GAP.join(row[n] for row in rows) for n in range(5)]
    faces = "  ".join(str(v) for v in dice)
    lines.append(paint(f"[ {faces} ]", "info"))
    return ["  " + line for line in lines]


def draw_block(lines, redraw):
    """Write the dice block, overwriting the previous frame in place."""
    tail = "\033[K" if ANIMATING else ""
    out = [f"\r\033[{len(lines)}A"] if (redraw and ANIMATING) else []
    for line in lines:
        out.append(f"\r{line}{tail}\n")
    sys.stdout.write("".join(out))
    sys.stdout.flush()


def roll_five(rng):
    return [rng.randint(1, 6) for _ in range(5)]


FRAME_COUNT = 14
FRAME_DELAY = 0.07          # 14 x 0.07s ≈ 1.0s of flashing, then it settles


def animate_roll(dice, reroll_indexes, rng, fast, title):
    """Flash random faces for about a second, then settle on `dice`.

    `reroll_indexes` are the dice being re-rolled; the others are shown as
    held.  With --fast, or when stdout is not a terminal, the settled hand is
    printed once instead.
    """
    held = ({i for i in range(1, len(dice) + 1)} - set(reroll_indexes)
            if reroll_indexes else set())
    print(title)
    if not (ANIMATING and not fast):
        draw_block(hand_lines(dice, held), redraw=False)
        return
    for frame in range(FRAME_COUNT + 1):
        settling = frame == FRAME_COUNT
        display = list(dice) if settling else [
            d if (i + 1) in held else rng.randint(1, 6)
            for i, d in enumerate(dice)
        ]
        draw_block(hand_lines(display, held), redraw=frame > 0)
        if not settling:
            time.sleep(FRAME_DELAY)


# ---------------------------------------------------------------------------
# The scorecard: six categories, or seven with --chance.
# ---------------------------------------------------------------------------
def score_ones(dice):
    return sum(v for v in dice if v == 1)


def score_twos(dice):
    return sum(v for v in dice if v == 2)


def score_threes(dice):
    return sum(v for v in dice if v == 3)


def score_three_of_a_kind(dice):
    """Sum of ALL five dice when some value appears three times or more."""
    return sum(dice) if max(dice.count(v) for v in set(dice)) >= 3 else 0


def score_full_house(dice):
    """Exactly three of one value and two of another: 25, else 0."""
    return 25 if sorted(dice.count(v) for v in set(dice)) == [2, 3] else 0


def score_small_straight(dice):
    """Four consecutive values anywhere in the hand: 30, else 0."""
    unique = sorted(set(dice))
    return 30 if any(unique[i:i + 4] == [unique[i] + k for k in range(4)]
                     for i in range(len(unique) - 3)) else 0


def score_chance(dice):
    return sum(dice)


CATEGORIES = [
    ("Ones", score_ones, 5),
    ("Twos", score_twos, 10),
    ("Threes", score_threes, 15),
    ("Three of a Kind", score_three_of_a_kind, 30),
    ("Full House", score_full_house, 25),
    ("Small Straight", score_small_straight, 30),
]
CHANCE_CATEGORY = ("Chance", score_chance, 30)


def build_card(use_chance):
    """[(name, scorer, best)] for this game."""
    return CATEGORIES + ([CHANCE_CATEGORY] if use_chance else [])


# ---------------------------------------------------------------------------
# Rendering the score table (the layout from the challenge, exactly).
# ---------------------------------------------------------------------------
NAME_COL = 15   # exactly wide enough for "Three of a Kind"
SCORE_COL = 5   # "Score"/"open"/points, centred — reproduces the sample table


def centered(text, width):
    """Centre `text` in `width`, extra space on the right (like the sample)."""
    pad = width - len(text)
    left = pad // 2
    return " " * left + text + " " * (pad - left)


def score_table(card, filled):
    """Bordered table: every category, its score or 'open', and the total.

    Cells are padded while still plain text and only then decorated, so ANSI
    codes can never shift a column.
    """
    def decorate(text, strong=False, key=None):
        if not USE_COLOR:
            return text
        prefix = _BOLD if strong else ""
        prefix += _PALETTE.get(key, "") if key else ""
        return prefix + text + (_RESET if prefix else "")

    def row(left, right, strong_left=False, right_key=None):
        left_cell = decorate(f" {left:<{NAME_COL}} ", strong_left)
        right_cell = decorate(f" {centered(right, SCORE_COL)} ",
                              right_key is not None, right_key)
        return f"│{left_cell}│{right_cell}│"

    def bar(left, middle, right):
        return (left + "─" * (NAME_COL + 2) + middle +
                "─" * (SCORE_COL + 2) + right)

    lines = [paint(bar("┌", "┬", "┐"), "head"),
             row("Category", "Score", strong_left=True),
             paint(bar("├", "┼", "┤"), "head")]
    for name, _, _ in card:
        if name in filled:
            points = filled[name]
            lines.append(row(name, str(points),
                             right_key="good" if points else "bad"))
        else:
            lines.append(row(name, "open", right_key="hold"))
    lines.append(paint(bar("├", "┼", "┤"), "head"))
    lines.append(row("TOTAL", str(sum(filled.values())),
                     strong_left=True, right_key="good"))
    lines.append(paint(bar("└", "┴", "┘"), "head"))
    return lines


def render_card(card, filled, title=None):
    if title:
        print(paint(title, "head"))
    for line in score_table(card, filled):
        print(line)


# ---------------------------------------------------------------------------
# Input: every prompt validates and re-asks.  Nothing crashes the game.
# ---------------------------------------------------------------------------
class Abandoned(Exception):
    """Raised when the player quits (Ctrl-C) or input runs out."""


def ask(prompt):
    """Read a line, echoing it when stdin is a pipe so scripted games read
    like a transcript (an interactive terminal echoes for us already)."""
    try:
        answer = input(prompt)
    except KeyboardInterrupt:
        raise Abandoned
    except EOFError:
        print()
        raise Abandoned
    if not sys.stdin.isatty():
        sys.stdout.write(answer + "\n")
    return answer.strip()


DIGITS = frozenset("0123456789")


def as_int(text):
    """int(text) for plain ASCII digits only, else None.

    `str.isdigit()` also answers True for glyphs like '²' or '٣' that `int()`
    rejects, and a pasted funny character must not be able to crash the game.
    """
    if not text or not all(char in DIGITS for char in text):
        return None
    return int(text)


def parse_indexes(text, count):
    """Read dice indexes: '1 3 5', '1,3,5', '135' or '' (keep everything).

    Returns (indexes, error) — exactly one of the two is None.  An empty
    selection is the legal answer that means "no re-roll".  Dice indexes are
    single digits, so an unseparated run like "135" is read as 1, 3 and 5;
    anything else that is not a plain 1..5 digit is rejected politely.
    """
    if not text:
        return [], None
    tokens = text.replace(",", " ").split()
    run = tokens[0] if len(tokens) == 1 else ""
    if len(run) > 1 and as_int(run) is not None:
        tokens = list(run)                # "135" -> 1, 3, 5
    indexes = set()
    for token in tokens:
        value = as_int(token)
        if value is None or len(token) != 1:
            return None, (f"  {token!r} is not a dice index — use the numbers "
                          f"1-{count}, separated by spaces.")
        if not 1 <= value <= count:
            return None, f"  Die {value} does not exist — pick 1-{count}."
        indexes.add(value)
    return sorted(indexes), None


def prompt_for_reroll(dice, rng, fast):
    """One re-roll per turn on the chosen subset; '' keeps the whole hand."""
    while True:
        raw = ask("Dice to re-roll (indexes 1-5, space-separated, "
                  "empty to keep): > ")
        indexes, error = parse_indexes(raw, len(dice))
        if error:
            print(paint(error, "bad"))
            continue
        if not indexes:
            print(paint("  Keeping this hand.", "info"))
            return list(dice)
        dice = list(dice)
        for index in indexes:
            dice[index - 1] = rng.randint(1, 6)
        animate_roll(dice, set(indexes), rng, fast,
                     paint("Rolling " + " ".join(str(i) for i in indexes) +
                           " again...", "info"))
        return dice


def category_spans(numbers):
    """Render allowed picks: '1-6' when contiguous, else '2, 3, 6'."""
    contiguous = numbers == list(range(numbers[0], numbers[-1] + 1))
    if len(numbers) > 1 and contiguous:
        return f"{numbers[0]}-{numbers[-1]}"
    return ", ".join(str(n) for n in numbers)


def prompt_for_category(card, filled, dice):
    """Show each open category with what this hand earns, then pick one."""
    open_items = [(number, name, scorer)
                  for number, (name, scorer, _) in enumerate(card, start=1)
                  if name not in filled]
    numbers = [n for n, _, _ in open_items]
    allowed = category_spans(numbers)

    print()
    print(paint("Open categories for this hand:", "head"))
    for number, name, scorer in open_items:
        points = scorer(dice)
        label = paint(f"{points:>3}", "good" if points else "bad")
        print(f"  {number}) {name:<16} -> {label}")

    while True:
        raw = ask(f"Score in category ({allowed}): > ")
        if not raw:
            print(paint("  A category is required each turn — even a 0 "
                        "(scratch) must be filed.", "bad"))
            continue
        choice = as_int(raw)
        if choice is None:
            print(paint(f"  Enter one of the numbers {allowed}, not {raw!r}.",
                        "bad"))
            continue
        hit = next((item for item in open_items if item[0] == choice), None)
        if hit:
            _, name, scorer = hit
            return name, scorer(dice)
        taken = next((nm for n, (nm, _, _) in enumerate(card, 1)
                      if n == choice), None)
        if taken:
            score = filled[taken]
            print(paint(f"  {taken} is already filled ({score} points) — "
                        "it cannot be overwritten.", "bad"))
        else:
            print(paint(f"  Category {choice} is off the card.", "bad"))
        print(paint(f"  Choose from: {allowed}.", "bad"))


# ---------------------------------------------------------------------------
# Banner, game loop, wrap-up.
# ---------------------------------------------------------------------------
def welcome_banner(use_chance):
    turns = 7 if use_chance else 6
    lines = [f"Five dice · one re-roll per turn · {turns} turns",
             "Fill every category once — scratching for 0 is a legal move."]
    if use_chance:
        lines += ["Card: Ones, Twos, Threes, Three of a Kind, Full House,",
                  "Small Straight and Chance (the sum of all dice)."]
    else:
        lines += ["Card: Ones, Twos, Threes, Three of a Kind,",
                  "Full House and Small Straight."]
    lines.append(SIGN_OFF)
    width = max(len(line) for line in lines)
    inner = width + 2
    print()
    print(paint("┌" + "─" * inner + "┐", "head"))
    print(paint("│", "head") + bold(f"{'FIVE-DICE FRENZY':^{inner}}") +
          paint("│", "head"))
    print(paint("├" + "─" * inner + "┤", "head"))
    for line in lines:
        key = "info" if line == SIGN_OFF else "hold"
        print(paint("│", "head") + paint(f" {line:<{width}} ", key) +
              paint("│", "head"))
    print(paint("└" + "─" * inner + "┘", "head"))


def rating(total, use_chance):
    """One-line verdict.  The 7-turn card scales the bands by about 7/6."""
    low, high = (40, 70) if not use_chance else (47, 82)
    if total < low:
        return "Better luck next roll!"
    if total < high:
        return "Solid game!"
    return "Dice master!"


def play(card, rng, fast):
    """Play every turn; returns {category: score}."""
    filled = {}
    for turn in range(1, len(card) + 1):
        print()
        print(paint(rule(f"Turn {turn}/{len(card)}"), "head"))
        dice = roll_five(rng)
        animate_roll(dice, None, rng, fast, paint("Rolling...", "info"))
        dice = prompt_for_reroll(dice, rng, fast)
        name, points = prompt_for_category(card, filled, dice)
        filled[name] = points
        note = " — scratched" if points == 0 else ""
        verdict = f"  Filed {name}: {points}{note}"
        print(paint(verdict, "good" if points else "bad"))
        render_card(card, filled, rule(f"Scorecard after turn {turn}"))
    return filled


def finish(card, filled, use_chance):
    total = sum(filled.values())
    best = sum(best_ for _, _, best_ in card)
    print()
    print(paint(rule("Final scorecard"), "head"))
    render_card(card, filled)
    print()
    print(f"Total score: {bold(str(total))} out of {best} possible")
    print(bold(f"Rating: {rating(total, use_chance)}"))
    print(paint(SIGN_OFF, "info"))


# ---------------------------------------------------------------------------
# Self-test — the hands named in the challenge's "Done When" checklist.
# ---------------------------------------------------------------------------
def self_test():
    by_name = {name: scorer for name, scorer, _ in build_card(False)}
    scoring_cases = [
        ([4, 5, 2, 3, 4], "Small Straight", 30),
        ([3, 3, 3, 5, 5], "Full House", 25),
        ([6, 6, 6, 2, 1], "Three of a Kind", 21),   # sum of all five dice
        ([1, 1, 1, 1, 1], "Full House", 0),         # five alike is not a house
        ([1, 1, 2, 2, 2], "Ones", 2),
        ([2, 2, 2, 2, 2], "Twos", 10),
        ([3, 3, 3, 3, 3], "Threes", 15),
        ([1, 2, 3, 4, 6], "Small Straight", 30),
        ([1, 2, 4, 5, 6], "Small Straight", 0),
        ([1, 2, 3, 4, 5], "Small Straight", 30),
        ([2, 3, 4, 5, 6], "Small Straight", 30),
        ([1, 1, 1, 1, 2], "Three of a Kind", 6),
        ([4, 4, 2, 6, 4], "Three of a Kind", 20),
        ([4, 4, 2, 6, 4], "Full House", 0),
        ([6, 6, 6, 6, 6], "Three of a Kind", 30),
        ([1, 1, 1, 1, 1], "Three of a Kind", 5),
        ([2, 2, 3, 3, 3], "Full House", 25),
        ([4, 5, 2, 3, 4], "Twos", 2),
        ([4, 5, 2, 3, 4], "Threes", 3),
    ]
    parse_cases = [
        ("1 3 5", [1, 3, 5]), ("1,3,5", [1, 3, 5]), ("135", [1, 3, 5]),
        ("", []), ("  2 ", [2]), ("2 2", [2]), ("1 2 3 4 5", [1, 2, 3, 4, 5]),
        ("7", None), ("0", None), ("a", None), ("1-3", None), ("1 42", None),
        ("one", None), ("1 2 x", None), ("²", None), ("٣", None),
        ("42", [2, 4]),            # unseparated shorthand, like "135"
    ]
    failures = []

    def check(ok, message):
        if not ok:
            failures.append(message)
        return ok

    print("Scoring rules:")
    for hand, category, expected in scoring_cases:
        got = by_name[category](hand)
        ok = check(got == expected, f"{category} on {hand}: got {got}, "
                                    f"want {expected}")
        print(f"  [{'ok' if ok else 'FAIL'}] {str(hand):<16} {category:<16}"
              f" -> {got:>3}")

    print("\nRe-roll input:")
    for raw, want in parse_cases:
        indexes, error = parse_indexes(raw, 5)
        ok = check((error is not None) if want is None
                   else (error is None and indexes == want),
                   f"parse_indexes({raw!r}): got {indexes}, want {want}")
        shown = "rejected (re-prompt)" if error else repr(indexes)
        print(f"  [{'ok' if ok else 'FAIL'}] {raw!r:<12} -> {shown}")

    print("\nRating bands:")
    for total, want in [(0, "Better luck next roll!"),
                        (39, "Better luck next roll!"),
                        (40, "Solid game!"), (69, "Solid game!"),
                        (70, "Dice master!"), (115, "Dice master!")]:
        got = rating(total, False)
        ok = check(got == want, f"rating({total}): got {got}, want {want}")
        print(f"  [{'ok' if ok else 'FAIL'}] {total:>3} -> {got}")

    print("\nTable layout (Ones=3, Three of a Kind=0, Small Straight=30):")
    demo = {"Ones": 3, "Three of a Kind": 0, "Small Straight": 30}
    for line in score_table(CATEGORIES, demo):
        print(line)

    if failures:
        print("\nSelf-test FAILED:")
        for line in failures:
            print("  " + line)
        return 1
    print("\nSelf-test passed.")
    print("Note: Requirement 4 makes Three of a Kind the sum of ALL dice, so")
    print("6 6 6 2 1 scores 21. The 'Done When' checklist says 18 — the three")
    print("sixes only. See README.md for why the written rule wins.")
    return 0


# ---------------------------------------------------------------------------
# Entry point.
# ---------------------------------------------------------------------------
def main(argv=None):
    global USE_COLOR, ANIMATING

    parser = argparse.ArgumentParser(
        prog="five_dice_frenzy.py",
        description="Five-Dice Frenzy — a Yahtzee-lite dice game for the "
                    "terminal.",
        epilog=SIGN_OFF + " — standard library only, no files written.",
    )
    parser.add_argument("--fast", action="store_true",
                        help="skip the roll animation")
    parser.add_argument("--chance", action="store_true",
                        help="stretch rule: add a 7th Chance category and "
                             "play 7 turns")
    parser.add_argument("--no-color", dest="no_color", action="store_true",
                        help="disable ANSI colours")
    parser.add_argument("--seed", type=int, default=None,
                        help="seed the dice RNG")
    parser.add_argument("--self-test", dest="self_test", action="store_true",
                        help="check the scoring rules and exit")
    args = parser.parse_args(argv)

    tty = sys.stdout.isatty()
    plain = args.no_color or bool(os.environ.get("NO_COLOR"))
    USE_COLOR = tty and not plain and not args.self_test
    ANIMATING = tty and not args.self_test

    if args.self_test:
        return self_test()

    rng = random.Random(args.seed)
    card = build_card(args.chance)
    try:
        welcome_banner(args.chance)
        filled = play(card, rng, args.fast)
        finish(card, filled, args.chance)
    except Abandoned:
        print()
        print(paint("Game abandoned — the napkin stays clean.", "bad"))
        return 130
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nGame abandoned — the napkin stays clean.")
        sys.exit(130)
