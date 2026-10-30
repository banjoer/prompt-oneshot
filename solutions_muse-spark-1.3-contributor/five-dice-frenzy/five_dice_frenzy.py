#!/usr/bin/env python3
"""Five-Dice Frenzy — a Yahtzee-lite terminal game.

Produced: 2026-10-29 (UTC) by Muse Spark 1.3 Contributor.

Single-file, standard-library-only dice game. Five dice, one optional
single re-roll per turn, 6-category scorecard, 6 turns total.

Run with: python3 five_dice_frenzy.py [--fast]
  --fast : skip the ~1s roll animation (impatient players / piped input).
"""

import random
import sys
import time

# Sign-off: produced 2026-10-29 (UTC) by Muse Spark 1.3 Contributor.
PRODUCED_STAMP = "2026-10-29 (UTC) by Muse Spark 1.3 Contributor"

CATEGORIES = [
    "Ones",
    "Twos",
    "Threes",
    "Three of a Kind",
    "Full House",
    "Small Straight",
]

FAST_MODE = "--fast" in sys.argv[1:]

# ASCII-art dice faces. Each face is 5 rows of 7 chars wide.
# Pip layout uses U+25CF BLACK CIRCLE to match the spec example.
DICE_ART = {
    1: [
        "┌─────┐",
        "│     │",
        "│  ●  │",
        "│     │",
        "└─────┘",
    ],
    2: [
        "┌─────┐",
        "│ ●   │",
        "│     │",
        "│   ● │",
        "└─────┘",
    ],
    3: [
        "┌─────┐",
        "│ ●   │",
        "│  ●  │",
        "│   ● │",
        "└─────┘",
    ],
    4: [
        "┌─────┐",
        "│ ● ● │",
        "│     │",
        "│ ● ● │",
        "└─────┘",
    ],
    5: [
        "┌─────┐",
        "│ ● ● │",
        "│  ●  │",
        "│ ● ● │",
        "└─────┘",
    ],
    6: [
        "┌─────┐",
        "│ ● ● │",
        "│ ● ● │",
        "│ ● ● │",
        "└─────┘",
    ],
}


def score_for_category(dice, cat_index):
    """Return the score `dice` (list of 5 ints) would earn in category cat_index."""
    counts = [dice.count(v) for v in range(1, 7)]
    if cat_index == 0:  # Ones
        return sum(d for d in dice if d == 1)
    if cat_index == 1:  # Twos
        return sum(d for d in dice if d == 2)
    if cat_index == 2:  # Threes
        return sum(d for d in dice if d == 3)
    if cat_index == 3:  # Three of a Kind: sum of ALL dice if any value >= 3
        if max(counts) >= 3:
            return sum(dice)
        return 0
    if cat_index == 4:  # Full House: exactly 3 of one + 2 of another
        if sorted(counts) == [0, 0, 0, 0, 2, 3]:
            return 25
        return 0
    if cat_index == 5:  # Small Straight: any 4 consecutive values present
        uniq = set(dice)
        for run in ({1, 2, 3, 4}, {2, 3, 4, 5}, {3, 4, 5, 6}):
            if run.issubset(uniq):
                return 30
        return 0
    raise ValueError("bad category index")


def scores_for_hand(dice):
    """Return list of 6 potential scores for this hand."""
    return [score_for_category(dice, i) for i in range(len(CATEGORIES))]


def render_dice_block(dice):
    """Build the 5 text rows showing all dice side by side."""
    rows = [""] * 5
    for j, d in enumerate(dice):
        art = DICE_ART[d]
        for r in range(5):
            if j > 0:
                rows[r] += " "
            rows[r] += art[r]
    return rows


def animated_roll(final_dice, fixed_mask=None, duration=1.0, frames=10):
    """Show a ~1s animation cycling dice faces, then settle on final_dice.

    fixed_mask: optional list of bools; True means that die stays fixed
    (used for re-rolls so only chosen dice flash). None means all animate.
    """
    if FAST_MODE or not sys.stdout.isatty():
        # Still honour "roughly 1 second" only on interactive terminals;
        # when piped (tests) or --fast, skip the sleep but still show dice.
        # If stdout is not a tty, ANSI cursor-up rewrites would pollute
        # piped output, so just print the final block once.
        # For --fast on a tty we still print once with no sleep.
        for line in render_dice_block(final_dice):
            print(line)
        return

    if fixed_mask is None:
        fixed_mask = [False] * len(final_dice)

    n_rows = 5
    for f in range(frames):
        if f == frames - 1:
            shown = list(final_dice)
        else:
            shown = [
                final_dice[i] if fixed_mask[i] else random.randint(1, 6)
                for i in range(len(final_dice))
            ]
        rows = render_dice_block(shown)
        for line in rows:
            # \r + clear-line keeps rewrites clean even if widths differed.
            sys.stdout.write("\r\033[K" + line + "\n")
        sys.stdout.flush()
        if f < frames - 1:
            time.sleep(duration / (frames - 1))
            # Move cursor back up over the 5 dice rows to overwrite them.
            sys.stdout.write("\033[%dA\r" % n_rows)
            sys.stdout.flush()
    # Cursor now sits on the line after the final dice block.


def display_dice_with_labels(dice):
    """Print final dice block plus index/value helper lines (after animation)."""
    # animated_roll already printed the final block; add helper lines.
    labels = "  ".join("  %d  " % (i + 1) for i in range(len(dice)))
    values = "  ".join("[ %d ]" % d for d in dice)
    print("Indexes:" + " " + labels)
    print("Values: " + " " + values + "   (hand: %s)" % " ".join(map(str, dice)))


def roll_dice(n=5):
    return [random.randint(1, 6) for _ in range(n)]


def prompt_reroll():
    """Ask which dice to re-roll. Returns sorted list of 0-based indexes."""
    while True:
        try:
            raw = input(
                "Dice to re-roll (indexes 1-5, space-separated, empty to keep): "
            )
        except EOFError:
            print()
            return []
        raw = raw.strip()
        if raw == "":
            return []
        parts = raw.split()
        idxs = []
        ok = True
        for p in parts:
            if not p.lstrip("+-").isdigit():
                print("  '%s' is not a number. Use indexes 1-5 separated by spaces." % p)
                ok = False
                break
            v = int(p)
            if v < 1 or v > 5:
                print("  Index %d is out of range. Use indexes 1-5." % v)
                ok = False
                break
            if (v - 1) not in idxs:
                idxs.append(v - 1)
        if not ok:
            continue
        return sorted(idxs)


def prompt_category(scores):
    """Ask which open category to fill. Returns 0-based category index."""
    open_idx = [i for i, s in enumerate(scores) if s is None]
    while True:
        try:
            raw = input("Score in category (1-6): ").strip()
        except EOFError:
            # On EOF, pick the first open category rather than crashing.
            print()
            print("No input — scoring first open category.")
            return open_idx[0]
        if not raw.lstrip("+-").isdigit():
            print("  Please enter a number 1-6 for an open category.")
            continue
        v = int(raw)
        if v < 1 or v > 6:
            print("  %d is out of range. Choose 1-6." % v)
            continue
        if scores[v - 1] is not None:
            print("  %s is already filled — pick an open category." % CATEGORIES[v - 1])
            continue
        return v - 1


def show_open_categories(dice, scores):
    potentials = scores_for_hand(dice)
    print("\nOpen categories for this hand:")
    for i, name in enumerate(CATEGORIES):
        if scores[i] is None:
            print("  %d) %-15s -> %d" % (i + 1, name, potentials[i]))


def running_total(scores):
    return sum(s for s in scores if s is not None)


def print_score_table(scores):
    total = running_total(scores)
    print("┌─────────────────┬───────┐")
    print("│ Category        │ Score │")
    print("├─────────────────┼───────┤")
    for i, name in enumerate(CATEGORIES):
        if scores[i] is None:
            cell = "open"
        else:
            cell = str(scores[i])
        cell = cell.center(5) if len(cell) < 5 else cell
        print("│ %-15s │ %5s │" % (name, cell))
    print("├─────────────────┼───────┤")
    print("│ %-15s │ %5s │" % ("TOTAL", str(total).center(5) if len(str(total)) < 5 else str(total)))
    print("└─────────────────┴───────┘")


def rating_for_total(total):
    if total < 40:
        return "Better luck next roll!"
    if total < 70:
        return "Solid game!"
    return "Dice master!"


def print_banner():
    print("==============================================")
    print("  FIVE-DICE FRENZY — a Yahtzee-lite dice game")
    print("  Produced: %s" % PRODUCED_STAMP)
    print("==============================================")
    print("Five dice, one re-roll per turn, 6 categories.")
    print("Fill each category once over 6 turns. Good luck!")
    print()


def main():
    print_banner()
    scores = [None] * len(CATEGORIES)
    try:
        for turn in range(1, 7):
            print("Turn %d/6" % turn)
            print("Rolling...")
            dice = roll_dice(5)
            animated_roll(dice)
            # When animation already printed the block (tty), don't duplicate;
            # when piped/--fast it printed once — either way add labels now.
            display_dice_with_labels(dice)

            reroll = prompt_reroll()
            if reroll:
                print("Re-rolling dice %s..." % ", ".join(str(i + 1) for i in reroll))
                print("Rolling...")
                fixed = [(i not in reroll) for i in range(5)]
                new_vals = roll_dice(len(reroll))
                for k, di in enumerate(reroll):
                    dice[di] = new_vals[k]
                animated_roll(dice, fixed_mask=fixed)
                display_dice_with_labels(dice)
            else:
                print("Keeping all dice.")

            print("Final hand: %s" % " ".join(map(str, dice)))
            show_open_categories(dice, scores)
            choice = prompt_category(scores)
            earned = score_for_category(dice, choice)
            scores[choice] = earned
            print("Scored %d in %s." % (earned, CATEGORIES[choice]))
            print()
            print_score_table(scores)
            print()

        print("Game over! Final results:")
        print_score_table(scores)
        total = running_total(scores)
        print("Total score: %d" % total)
        print(rating_for_total(total))
    except KeyboardInterrupt:
        print("\nGame interrupted. Thanks for playing!")
        print_score_table(scores)


if __name__ == "__main__":
    main()
