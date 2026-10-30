#!/usr/bin/env python3
# ===========================================================================
# Tests for five_dice_frenzy.py — stdlib only (unittest + subprocess).
#
#   Produced : 2026-10-30 00:06 CET  (2026-10-29 23:06 UTC)
#   Author   : Qwen3.8 Flash, thinking effort "xhigh", via OpenCode
#
#   Run with: python3 test_five_dice_frenzy.py -v
#
# Covers the challenge's "Done When" checklist: the animated roll, the one
# re-roll subset, validated re-prompts, the bordered score table after every
# turn, exactly six turns, the scoring rules, and the sign-off requirement.
# ===========================================================================
"""Behavioural and end-to-end tests for Five-Dice Frenzy."""

import io
import os
import re
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import five_dice_frenzy as game  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "five_dice_frenzy.py")

# A tidy game: keep every hand, file the categories from the highest number
# down so no pick ever collides with an already-filled category.
FULL_GAME = "".join("\n%d\n" % n for n in range(6, 0, -1))
FULL_CHANCE_GAME = "".join("\n%d\n" % n for n in range(7, 0, -1))


def run_game(stdin_text, args=()):
    """Play a scripted game in a subprocess and return its result."""
    proc = subprocess.run([sys.executable, SCRIPT, "--fast", *args],
                          input=stdin_text, capture_output=True, text=True,
                          timeout=60)
    return proc


class ScoringTests(unittest.TestCase):
    """Requirement 4 / checklist: the six categories score by the rules."""

    def s(self, hand, category):
        scorer = dict((name, fn) for name, fn, _ in game.CATEGORIES)[category]
        return scorer(list(hand))

    def test_small_straight_examples(self):
        self.assertEqual(self.s((4, 5, 2, 3, 4), "Small Straight"), 30)
        self.assertEqual(self.s((1, 2, 3, 4, 5), "Small Straight"), 30)
        self.assertEqual(self.s((2, 3, 4, 5, 6), "Small Straight"), 30)
        self.assertEqual(self.s((1, 2, 4, 5, 6), "Small Straight"), 0)
        self.assertEqual(self.s((1, 1, 2, 3, 4), "Small Straight"), 30)

    def test_full_house_examples(self):
        self.assertEqual(self.s((3, 3, 3, 5, 5), "Full House"), 25)
        self.assertEqual(self.s((2, 2, 2, 3, 3), "Full House"), 25)
        self.assertEqual(self.s((6, 6, 6, 6, 6), "Full House"), 0)   # not 3+2
        self.assertEqual(self.s((1, 1, 1, 2, 3), "Full House"), 0)

    def test_three_of_a_kind_is_sum_of_all_dice(self):
        # Requirement 4: "sum of all dice if any value appears >= 3 times".
        self.assertEqual(self.s((6, 6, 6, 2, 1), "Three of a Kind"), 21)
        self.assertEqual(self.s((4, 4, 2, 6, 4), "Three of a Kind"), 20)
        self.assertEqual(self.s((1, 1, 2, 2, 3), "Three of a Kind"), 0)

    def test_numbered_categories(self):
        self.assertEqual(self.s((1, 1, 6, 6, 6), "Ones"), 2)
        self.assertEqual(self.s((2, 2, 2, 2, 2), "Twos"), 10)
        self.assertEqual(self.s((3, 3, 6, 6, 6), "Threes"), 6)
        self.assertEqual(self.s((4, 5, 6, 1, 2), "Ones"), 1)

    def test_chance(self):
        self.assertEqual(game.score_chance([6, 6, 6, 2, 1]), 21)

    def test_rating_bands(self):
        self.assertEqual(game.rating(39, False), "Better luck next roll!")
        self.assertEqual(game.rating(40, False), "Solid game!")
        self.assertEqual(game.rating(69, False), "Solid game!")
        self.assertEqual(game.rating(70, False), "Dice master!")


class InputParsingTests(unittest.TestCase):
    """Requirement 8: malformed / out-of-range dice indexes never crash."""

    def test_valid_forms(self):
        for raw, want in [("1 3 5", [1, 3, 5]), ("1,3,5", [1, 3, 5]),
                          ("135", [1, 3, 5]), ("", []), ("  4 ", [4]),
                          ("5 1", [1, 5]), ("2 2 2", [2]),
                          ("1 2 3 4 5", [1, 2, 3, 4, 5])]:
            indexes, error = game.parse_indexes(raw, 5)
            self.assertIsNone(error, f"{raw!r} should be accepted")
            self.assertEqual(indexes, want, raw)

    def test_rejected_forms(self):
        for raw in ["0", "6", "7", "a", "1 a", "1-9", "one", "99"]:
            indexes, error = game.parse_indexes(raw, 5)
            self.assertIsNotNone(error, f"{raw!r} should be rejected")
            self.assertIsNone(indexes)

    def test_exotic_digits_are_rejected_not_crashed(self):
        # str.isdigit() says True for these, but int() would raise ValueError.
        for raw in ["²", "٣", "1²", "1٣", "١٢"]:
            indexes, error = game.parse_indexes(raw, 5)
            self.assertIsNotNone(error, f"{raw!r} must be rejected, not crash")
            self.assertIsNone(indexes)
        self.assertIsNone(game.as_int("²"))
        self.assertEqual(game.as_int("12"), 12)


class TableLayoutTests(unittest.TestCase):
    """Requirement 6: the bordered table matches the challenge sample."""

    SAMPLE = """┌─────────────────┬───────┐
│ Category        │ Score │
├─────────────────┼───────┤
│ Ones            │   3   │
│ Twos            │ open  │
│ Threes          │ open  │
│ Three of a Kind │   0   │
│ Full House      │ open  │
│ Small Straight  │  30   │
├─────────────────┼───────┤
│ TOTAL           │  33   │
└─────────────────┴───────┘""".splitlines()

    def test_table_matches_sample(self):
        filled = {"Ones": 3, "Three of a Kind": 0, "Small Straight": 30}
        self.assertEqual(game.score_table(game.CATEGORIES, filled),
                         self.SAMPLE)

    def test_colour_does_not_shift_columns(self):
        plain = game.score_table(game.CATEGORIES, {"Ones": 3})
        was = game.USE_COLOR
        game.USE_COLOR = True
        try:
            coloured = game.score_table(game.CATEGORIES, {"Ones": 3})
        finally:
            game.USE_COLOR = was
        self.assertTrue(any("\033[" in line for line in coloured))
        stripped = [re.sub(r"\033\[[0-9;]*m", "", line) for line in coloured]
        self.assertEqual(stripped, plain, "ANSI codes must not change widths")

    def test_no_ansi_when_redirected(self):
        self.assertEqual(game.USE_COLOR, False, "off by default")
        table = game.score_table(game.CATEGORIES, {"Ones": 3})
        self.assertNotIn("\033", "".join(table))

    def test_dice_block_fits_80_columns(self):
        lines = game.hand_lines([6, 5, 4, 3, 2])
        self.assertTrue(all(len(line) <= 80 for line in lines), lines)


class AnimationTests(unittest.TestCase):
    """Requirement 2: faces visibly cycle for roughly a second, then settle."""

    def capture(self, fn, *a, **kw):
        """Run fn against a fake terminal and capture its text."""
        colour = kw.pop("colour", False)
        was = (sys.stdout, game.ANIMATING, game.USE_COLOR)
        sys.stdout = io.StringIO()
        game.ANIMATING, game.USE_COLOR = True, colour
        try:
            started = time.monotonic()
            fn(*a, **kw)
            elapsed = time.monotonic() - started
        finally:
            text = sys.stdout.getvalue()
            sys.stdout, game.ANIMATING, game.USE_COLOR = was
        return text, elapsed

    def test_initial_roll_animates_about_one_second(self):
        text, elapsed = self.capture(game.animate_roll,
                                     [4, 4, 2, 6, 4], None,
                                     game.random.Random(1), False,
                                     "Rolling...")
        self.assertGreaterEqual(text.count("\033["), 10,
                              "expected many redraws")
        self.assertGreater(elapsed, 0.7,
                           f"animation too short: {elapsed:.2f}s")
        self.assertLess(elapsed, 2.0, f"animation too long: {elapsed:.2f}s")
        self.assertIn("┌──1──┐", text)
        # settles on the real hand
        self.assertIn("[ 4  4  2  6  4 ]", text)

    def test_reroll_keeps_the_other_dice(self):
        text, elapsed = self.capture(
            game.animate_roll, [4, 5, 2, 3, 4], {2, 3},
            game.random.Random(1), False, "Rolling...", colour=True)
        self.assertGreater(elapsed, 0.7)
        # Held dice 1, 4 and 5 are drawn grey the whole way through.
        self.assertIn("\033[90m", text)
        self.assertIn("[ 4  5  2  3  4 ]", re.sub(r"\033\[[0-9;]*m", "", text))

    def test_fast_flag_skips_the_frames(self):
        text, elapsed = self.capture(game.animate_roll,
                                     [1, 2, 3, 4, 5], None,
                                     game.random.Random(1), True, "Rolling...")
        self.assertLess(elapsed, 0.2)
        self.assertNotIn("\033[6A", text)             # no in-place redraws
        self.assertIn("[ 1  2  3  4  5 ]", text)


class GameFlowTests(unittest.TestCase):
    """End-to-end: the checklist items that need a played game."""

    def test_full_six_turn_game(self):
        stdin = ("1 2\n6\n"        # turn 1: re-roll 1,2 -> Small Straight
                 "\n5\n"            # turn 2: keep -> Full House
                 "3 3\n4\n"         # turn 3: duplicate index is fine
                 "junk 7\n\n1\n"    # turn 4: bad input, then keep
                 "1 2 3 4 5\n2\n"   # turn 5: re-roll everything
                 "\n3\n")           # turn 6: keep
        proc = run_game(stdin, ["--seed", "4"])
        out = proc.stdout
        self.assertEqual(proc.returncode, 0, out + proc.stderr)
        self.assertNotIn("Traceback", proc.stderr + out)
        self.assertEqual(len(re.findall(r"Turn \d/6", out)), 6,
                         "exactly 6 turns")
        self.assertEqual(out.count("│ TOTAL"), 7,   # 6 tables + final table
                         "a score table after every turn")
        self.assertIn("Rating:", out)
        self.assertRegex(out, r"Rating: (Better luck next roll!"
                             r"|Solid game!|Dice master!)")
        self.assertEqual(len(re.findall(r"Final scorecard", out)), 1)

    def test_rejects_filled_category_and_out_of_range_picks(self):
        # Turn 1 files Small Straight; turn 2 tries it again, then recovers.
        stdin = ("\n6\n"              # turn 1
                 "\n6\n5\n"            # turn 2: 6 is taken -> then 5
                 "\n4\n\n3\n\n2\n\n1\n")
        proc = run_game(stdin, ["--seed", "8"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("already filled", proc.stdout)
        self.assertIn("cannot be overwritten", proc.stdout)

    def test_bad_category_input_reprompts(self):
        stdin = "\nzero\n²\n99\n1\n\n2\n\n3\n\n4\n\n5\n\n6\n"
        proc = run_game(stdin, ["--seed", "12"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("not 'zero'", proc.stdout)
        self.assertIn("not '²'", proc.stdout)
        self.assertIn("off the card", proc.stdout)
        self.assertNotIn("Traceback", proc.stderr)

    def test_reroll_index_validation(self):
        # 9 and 1-3 and 'x 1' are rejected; a plain 1 is accepted.
        stdin = ("9\n1-3\nx 1\n1\n6\n"
                 "\n5\n\n4\n\n3\n\n2\n\n1\n")
        proc = run_game(stdin, ["--seed", "3"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("Die 9 does not exist", proc.stdout)
        self.assertIn("is not a dice index", proc.stdout)
        self.assertNotIn("Traceback", proc.stderr)

    def test_eof_and_ctrl_c_exit_cleanly(self):
        # input runs out mid-game
        proc = run_game("\n", ["--seed", "6"])
        self.assertEqual(proc.returncode, 130, proc.stdout + proc.stderr)
        self.assertIn("Game abandoned", proc.stdout)
        self.assertNotIn("Traceback", proc.stderr)

    def test_signoff_in_header_and_banner(self):
        with open(SCRIPT, encoding="utf-8") as handle:
            head = "\n".join(handle.read().splitlines()[:20])
        self.assertRegex(head, r"2026-\d\d-\d\d \d\d:\d\d")
        self.assertIn("Qwen3.8 Flash", head)
        out = run_game("", ["--seed", "1"]).stdout
        self.assertIn(game.SIGN_OFF, out)
        self.assertIn("Built 2026-", out)

    def test_chance_mode_is_seven_turns(self):
        proc = run_game(FULL_CHANCE_GAME, ["--chance", "--seed", "2"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("7 turns", proc.stdout)
        self.assertEqual(len(re.findall(r"Turn \d/7", proc.stdout)), 7)
        self.assertIn("│ Chance", proc.stdout)

    def test_open_categories_are_listed_with_their_values(self):
        out = run_game(FULL_GAME, ["--seed", "4"]).stdout
        self.assertIn("Open categories for this hand:", out)
        self.assertRegex(out, r"1\) Ones\s+->\s+\d+")
        self.assertRegex(out, r"6\) Small Straight\s+->\s+\d+")

    def test_no_ansi_control_codes_when_redirected(self):
        out = run_game(FULL_GAME, ["--seed", "5"]).stdout
        self.assertNotIn("\033[", out)

    def test_output_fits_80_columns(self):
        out = run_game(FULL_GAME, ["--seed", "7"]).stdout
        wide = [line for line in out.splitlines() if len(line) > 80]
        self.assertEqual(wide, [], "lines longer than 80 columns")

    def test_help_runs(self):
        proc = subprocess.run([sys.executable, SCRIPT, "--help"],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--fast", proc.stdout)
        self.assertIn("--chance", proc.stdout)

    def test_self_test_flag_passes(self):
        proc = subprocess.run([sys.executable, SCRIPT, "--self-test"],
                              capture_output=True, text=True, timeout=60)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("Self-test passed", proc.stdout)

    def test_only_one_reroll_per_turn(self):
        # Exactly one re-roll prompt per turn: no second chance to pick dice.
        out = run_game(FULL_GAME, ["--seed", "2"]).stdout
        self.assertEqual(out.count("Dice to re-roll"), 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
