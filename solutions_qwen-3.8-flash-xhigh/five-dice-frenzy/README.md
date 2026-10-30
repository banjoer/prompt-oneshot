# Five-Dice Frenzy

A Yahtzee-lite dice game for the terminal in **one Python file**, standard
library only. Five dice, one optional re-roll per turn, six scorecard
categories, six turns.

```bash
python3 five_dice_frenzy.py          # normal play, animated dice
python3 five_dice_frenzy.py --fast   # skip the roll animation
python3 five_dice_frenzy.py --chance # stretch rule: 7th category, 7 turns
python3 five_dice_frenzy.py --help   # all options
```

Built **2026-10-30 00:06 CET** (2026-10-29 23:06 UTC) by **Qwen3.8 Flash**,
thinking effort *xhigh*, via OpenCode — the sign-off also appears in the file
header, in the welcome banner, in the final line of a game and in `--help`
(Requirement 9).

## What you get

| Requirement | Where it lives |
|---|---|
| Single file, `python3`, stdlib only | `five_dice_frenzy.py` (`argparse`, `os`, `random`, `sys`, `time`) |
| ASCII-art dice + ~1s roll animation | `PIP_ROWS`, `hand_lines`, `animate_roll` (14 frames × 0.07 s, carriage-return + cursor-up rewrites) |
| One optional re-roll of a chosen subset | `prompt_for_reroll` — `1 3 5`, `1,3,5` or `135`; empty Enter keeps the hand |
| Six categories, scored by the rules | `score_*` functions and `CATEGORIES` |
| Open categories shown with this hand's value | `prompt_for_category` |
| Bordered score table after every turn | `score_table` — reproduces the challenge's sample layout exactly |
| Exactly 6 turns, final table + total + rating | `play`, `finish`, `rating` |
| Validated input, friendly re-prompts, never crashes | `ask`, `parse_indexes`, `prompt_for_category`; Ctrl-C / EOF exit with a message, not a traceback |
| Sign-off: date/time + model | header comment, banner, end of game, `--help` epilog |

## Controls

| Prompt | What to type |
|--------|--------------|
| `Dice to re-roll (indexes 1-5, ...)` | `1 3 5` (also `1,3,5` or `135`), or just Enter to keep the hand |
| `Score in category (1-6)` | the number of any **open** category; 0-point "scratch" picks are legal |

Die indexes are printed inside each die's top border (`┌──3──┐`), and dice you
keep are dimmed while the rest flash.

## Scoring

| Category | Points |
|----------|--------|
| Ones / Twos / Threes | sum of the dice showing that value |
| Three of a Kind | **sum of all five dice** if some value appears 3+ times, else 0 |
| Full House | 25 if the hand is exactly three-of-a-kind **plus** a pair, else 0 |
| Small Straight | 30 if the hand contains four consecutive values, else 0 |
| Chance (`--chance` only) | sum of all five dice |

Ratings for the standard card: `< 40` → *Better luck next roll!*,
`40–69` → *Solid game!*, `≥ 70` → *Dice master!* (out of 115 possible).

### One deliberate call: Three of a Kind on `6 6 6 2 1`

Requirement 4 defines the category as *"sum of all dice if any value appears
≥3 times"*, which for `6 6 6 2 1` is **21**. The "Done When" checklist states
that same hand scores **18** — that is the sum of the three sixes only, and it
contradicts the rule the same document specifies. Where a spec disagrees with
itself, the explicit normative rule wins, so this implementation scores 21 and
documents the discrepancy instead of silently picking one. (Every other
checklist example — `4 5 2 3 4` → Small Straight 30, `3 3 3 5 5` → Full House
25 — agrees under both readings and is verified as-is.)

`python3 five_dice_frenzy.py --self-test` prints the whole rule table, the
input-parsing cases, the rating bands and a sample card, and exits non-zero if
anything drifts.

## Robustness details

* **Terminal, not file, friendly.** The animation only runs when `stdout` is a
  terminal; when output is redirected the settled hand is printed once, so logs
  and tests stay readable. With a piped `stdin` the typed answer is echoed, so
  a scripted game reads like the transcript in the challenge.
* **80×24 assumed.** The widest thing on screen is the dice block at 45 columns;
  the card and banner are narrower. Nothing depends on the terminal size.
* **Colours are cosmetic and optional.** ANSI is used for dice, scores and
  rules, auto-disabled off a terminal, and switchable with `--no-color` or the
  `NO_COLOR` environment variable. Cells are padded *before* colourising, so
  escape codes can never shift a column.
* **Nothing escapes to disk.** No files, no network, no subprocesses.

## Stretch goals — all three implemented

1. **Chance category** — `--chance` adds a 7th "Chance" category (sum of all
   dice) and plays 7 turns. Off by default, so the required 6-category /
   6-turn game is untouched; the rating bands scale to 47/82 for the longer
   card.
2. **ANSI colour** — green for points, yellow for zeroes, cyan dice, dimmed
   held dice, magenta chrome.
3. **`--fast`** — skips the animation for impatient players. `--seed N` was
   added as a bonus so games are reproducible (and testable).

## Tests

`test_five_dice_frenzy.py` covers the checklist end to end — 28 tests,
standard library only:

```bash
python3 test_five_dice_frenzy.py -v
```

* scoring for every category, including the boundary cases (five alike is not
  a house; `1 1 2 3 4` is a small straight);
* re-roll parsing accepted/rejected forms, and that each turn shows exactly
  one re-roll prompt;
* the rendered table compared line-for-line with the challenge's sample;
* animation wall-clock between 0.7 s and 2.0 s, frame count, and `--fast`
  skipping the redraws;
* a full 6-turn game, a 7-turn `--chance` game, repeated-category refusal,
  malformed input, `EOF`/Ctrl-C exiting 130 with a message and no traceback;
* no ANSI codes when redirected, and no output line wider than 80 columns.

## Sample turn

```
── Turn 3/6 ────────────────────────────────
Rolling...
  ┌──1──┐  ┌──2──┐  ┌──3──┐  ┌──4──┐  ┌──5──┐
  │ ● ● │  │ ● ● │  │ ● ● │  │     │  │ ● ● │
  │  ●  │  │  ●  │  │     │  │  ●  │  │     │
  │ ● ● │  │ ● ● │  │ ● ● │  │     │  │ ● ● │
  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘
  [ 5  5  6  2  4 ]
Dice to re-roll (indexes 1-5, space-separated, empty to keep): > 4
Rolling 4 again...
  ...
Open categories for this hand:
  2) Twos             ->   0
  3) Threes           ->   0
  4) Three of a Kind  ->   0
  5) Full House       ->   0
  6) Small Straight   ->   0
Score in category (2, 3, 4, 5, 6): > 4
  Filed Three of a Kind: 0 — scratched
```
