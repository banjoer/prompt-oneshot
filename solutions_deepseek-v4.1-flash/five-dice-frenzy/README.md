# Five-Dice Frenzy

A Yahtzee-lite dice game in one Python file, standard library only.

```bash
python3 five_dice_frenzy.py          # normal play, animated dice
python3 five_dice_frenzy.py --fast   # skip the roll animation
```

## What you get

- Five dice rendered as ASCII art boxes, flashing for about a second each roll.
- One optional re-roll per turn, limited to the dice indexes you name.
- Six categories: Ones, Twos, Threes, Three of a Kind, Full House,
  Small Straight. Each is filled once; scratching for 0 is allowed.
- A bordered scorecard after every turn, a final card, total, and rating.
- Friendly re-prompts for bad dice indexes, bad category numbers, and
  already-filled categories. EOF / Ctrl-C exits without a traceback.
- Sign-off in the file header and in the welcome banner:
  `Built 2026-10-29 22:44 CET by DeepSeek V4.1 Flash (opencode)`.

## Controls

| Prompt | Input |
|--------|-------|
| Re-roll | `1 3 5` (also `1,3,5`), or just Enter to keep the hand |
| Score | category number `1`–`6`; only open categories are listed |

The animation is drawn with ANSI cursor-up rewrites, so it needs a real
terminal (80×24 or larger). When stdout is redirected, or with `--fast`, the
final dice are printed without the flicker; gameplay is identical.

## Scoring

| Category | Points |
|----------|--------|
| Ones / Twos / Threes | sum of the dice showing that value |
| Three of a Kind | sum of all five dice if some value appears 3+ times, else 0 |
| Full House | 25 if the hand is exactly 3 of one value + 2 of another |
| Small Straight | 30 if the hand contains four consecutive values |

Ratings: `< 40` → "Better luck next roll!", `40–69` → "Solid game!",
`≥ 70` → "Dice master!".

## Note on the prompt's checklist

The challenge's Done When list says `6 6 6 2 1` should score 18 in Three of a
Kind. That conflicts with the prompt's own rule — "sum of all dice if any
value appears ≥3 times" — and with standard Yahtzee. Such a hand sums to
**21**, which is what this implementation awards (and the rule is what the
rest of the game follows). The 18 appears to be an arithmetic slip in the
checklist; the remaining checklist examples (`4 5 2 3 4` → 30 Small Straight,
`3 3 3 5 5` → 25 Full House) match exactly.

## Quick sanity checks

```bash
python3 - <<'EOF'
import five_dice_frenzy as g
assert g.score_for("Small Straight", [4, 5, 2, 3, 4]) == 30
assert g.score_for("Full House", [3, 3, 3, 5, 5]) == 25
assert g.score_for("Three of a Kind", [6, 6, 6, 2, 1]) == 21
assert g.score_for("Three of a Kind", [6, 6, 2, 1, 5]) == 0
assert g.parse_dice_indexes("1 3 5") == [1, 3, 5]
assert g.parse_dice_indexes("6") is None
print("all checks passed")
EOF

printf '\n1\n\n2\n\n3\n\n4\n\n5\n\n6\n' | python3 five_dice_frenzy.py
```

The piped run above plays a full six-turn game (keeping every initial hand and
filling categories in order) and ends with the final scorecard and rating.
