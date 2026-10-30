#!/usr/bin/env python3
# Five-Dice Frenzy - a Yahtzee-lite terminal dice game.
# Generated 2026-10-29 22:44 CET by DeepSeek V4.1 Flash (opencode).
"""Five-Dice Frenzy - a pocket Yahtzee-lite game for the terminal.

Usage:
    python3 five_dice_frenzy.py [--fast]

Five dice, one re-roll per turn, six scorecard categories.  Fill every
category exactly once; highest total wins (there is only you, but still).

Options:
    --fast   skip the dice-roll animation (for impatient players)
    -h, --help
             show this help

Standard library only.  No files, no network, no setup.
"""

import random
import sys
import time

# ---------------------------------------------------------------------------
# Sign-off (also shown in the welcome banner)
# ---------------------------------------------------------------------------
BUILT_AT = "2026-10-29 22:44 CET"
AUTHOR = "DeepSeek V4.1 Flash (opencode)"
SIGN_OFF = "Built {} by {}".format(BUILT_AT, AUTHOR)

# ---------------------------------------------------------------------------
# Game data
# ---------------------------------------------------------------------------
CATEGORIES = (
    "Ones",
    "Twos",
    "Threes",
    "Three of a Kind",
    "Full House",
    "Small Straight",
)
CATEGORY_WIDTH = 17
SCORE_WIDTH = 7
DICE_COUNT = 5
SIDES = 6
ANIMATION_SECONDS = 1.0
FRAME_SECONDS = 0.07

# A 3x3 dot grid per face, one string per row, five columns wide.
DIE_FACES = {
    1: ("     ", "  \u25cf  ", "     "),
    2: ("\u25cf    ", "     ", "    \u25cf"),
    3: ("\u25cf    ", "  \u25cf  ", "    \u25cf"),
    4: ("\u25cf   \u25cf", "     ", "\u25cf   \u25cf"),
    5: ("\u25cf   \u25cf", "  \u25cf  ", "\u25cf   \u25cf"),
    6: ("\u25cf   \u25cf", "\u25cf   \u25cf", "\u25cf   \u25cf"),
}

RULE_LINES = (
    "Five dice, one re-roll, six categories.  Fill every slot once.",
    "  Ones / Twos / Threes  - sum of dice showing that value",
    "  Three of a Kind       - sum of all dice (needs 3+ alike), else 0",
    "  Full House            - 25 (exactly 3 of one value + 2 of another)",
    "  Small Straight        - 30 (contains four consecutive values)",
)


class QuitGame(Exception):
    """Raised when the player runs out of input or interrupts the game."""


# ---------------------------------------------------------------------------
# Dice rendering and animation
# ---------------------------------------------------------------------------
def render_hand(dice):
    """Return the six display lines for a hand: five art rows + index labels."""
    faces = [DIE_FACES[value] for value in dice]
    lines = ["  ".join("\u250c\u2500\u2500\u2500\u2500\u2500\u2510" for _ in dice)]
    for row in range(3):
        lines.append("  ".join("\u2502" + face[row] + "\u2502" for face in faces))
    lines.append("  ".join("\u2514\u2500\u2500\u2500\u2500\u2500\u2518" for _ in dice))
    lines.append("  ".join("[{}]".format(i).center(7) for i in range(1, DICE_COUNT + 1)))
    return lines


def _emit(lines):
    sys.stdout.write("\n".join(lines) + "\n")
    sys.stdout.flush()


def animate_roll(dice, fast=False, changing=None):
    """Flash the dice faces for about a second, then settle on *dice*.

    *changing* limits the flicker to those zero-based die positions; the
    other dice appear frozen, which makes the re-roll easy to read.
    """
    final = list(dice)
    if changing is None:
        changing = list(range(DICE_COUNT))

    # Redirected output has nowhere to animate, so just print the result.
    if fast or not sys.stdout.isatty():
        _emit(render_hand(final))
        return

    height = len(render_hand(final))
    deadline = time.monotonic() + ANIMATION_SECONDS
    first_frame = True
    while time.monotonic() < deadline:
        frame = list(final)
        for position in changing:
            frame[position] = random.randint(1, SIDES)
        if not first_frame:
            # Move back up over the previous frame before drawing again.
            sys.stdout.write("\033[{}A".format(height))
        _emit(render_hand(frame))
        first_frame = False
        time.sleep(FRAME_SECONDS)

    sys.stdout.write("\033[{}A".format(height))
    _emit(render_hand(final))


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def score_for(category, dice):
    """Return the points *dice* would earn in *category*."""
    counts = [dice.count(value) for value in range(1, SIDES + 1)]

    if category == "Ones":
        return counts[0] * 1
    if category == "Twos":
        return counts[1] * 2
    if category == "Threes":
        return counts[2] * 3
    if category == "Three of a Kind":
        # All five dice count, not just the matching three.
        return sum(dice) if max(counts) >= 3 else 0
    if category == "Full House":
        shape = sorted(count for count in counts if count)
        return 25 if shape == [2, 3] else 0
    if category == "Small Straight":
        present = set(dice)
        runs = ((1, 2, 3, 4), (2, 3, 4, 5), (3, 4, 5, 6))
        return 30 if any(set(run) <= present for run in runs) else 0

    raise ValueError("unknown category: {!r}".format(category))


# ---------------------------------------------------------------------------
# Input helpers
# ---------------------------------------------------------------------------
def ask(prompt):
    """input() wrapper that turns EOF / Ctrl-C into a friendly exit."""
    try:
        return input(prompt)
    except (EOFError, KeyboardInterrupt):
        print()
        raise QuitGame


def parse_dice_indexes(raw):
    """Parse '1 3 5' into [1, 3, 5].  Empty means keep.  None means invalid."""
    cleaned = raw.replace(",", " ").strip()
    if not cleaned:
        return []

    indexes = []
    for token in cleaned.split():
        try:
            number = int(token)
        except ValueError:
            return None
        if not 1 <= number <= DICE_COUNT:
            return None
        if number not in indexes:
            indexes.append(number)
    return sorted(indexes)


def parse_category_choice(raw):
    """Parse a 1-based category number into a zero-based index, or None."""
    token = raw.strip()
    if not token.isdigit():
        return None
    number = int(token)
    if 1 <= number <= len(CATEGORIES):
        return number - 1
    return None


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------
def print_banner():
    line = "=" * 60
    print(line)
    print("   FIVE-DICE FRENZY  \u00b7  a pocket Yahtzee-lite dice game")
    print(line)
    for rule in RULE_LINES:
        print("  " + rule)
    print(line)
    print("  " + SIGN_OFF)
    print(line)


def print_score_table(scores):
    """Print the bordered scorecard; unfilled categories show as 'open'."""
    horizontal = "\u2500"
    top = "\u250c" + horizontal * CATEGORY_WIDTH + "\u252c" + horizontal * SCORE_WIDTH + "\u2510"
    middle = "\u251c" + horizontal * CATEGORY_WIDTH + "\u253c" + horizontal * SCORE_WIDTH + "\u2524"
    bottom = "\u2514" + horizontal * CATEGORY_WIDTH + "\u2534" + horizontal * SCORE_WIDTH + "\u2518"

    def row(left, right):
        return "\u2502 " + left.ljust(CATEGORY_WIDTH - 1) + "\u2502" + right.center(SCORE_WIDTH) + "\u2502"

    print(top)
    print(row("Category", "Score"))
    print(middle)
    for name in CATEGORIES:
        value = scores[name]
        print(row(name, "open" if value is None else str(value)))
    print(middle)
    print(row("TOTAL", str(total_score(scores))))
    print(bottom)


def total_score(scores):
    return sum(value for value in scores.values() if value is not None)


def rating_for(total):
    if total < 40:
        return "Better luck next roll!"
    if total < 70:
        return "Solid game!"
    return "Dice master!"


# ---------------------------------------------------------------------------
# Turn flow
# ---------------------------------------------------------------------------
def choose_category(dice, scores):
    """Show the open categories, then return the chosen category name."""
    print("\nOpen categories for this hand:")
    for index, name in enumerate(CATEGORIES, start=1):
        if scores[name] is None:
            print("  {}) {:<{width}} -> {:>2}".format(
                index, name, score_for(name, dice), width=CATEGORY_WIDTH
            ))

    while True:
        raw = ask("Score in category (1-6): > ")
        index = parse_category_choice(raw)
        if index is None:
            print("  Please enter a category number from 1 to 6.")
            continue
        name = CATEGORIES[index]
        if scores[name] is not None:
            print("  {} is already filled - pick an open category.".format(name))
            continue
        return name


def play_turn(turn_number, scores, fast):
    print("\nTurn {}/{}".format(turn_number, len(CATEGORIES)))

    dice = [random.randint(1, SIDES) for _ in range(DICE_COUNT)]
    print("Rolling...")
    animate_roll(dice, fast=fast)
    print("Dice: " + " ".join(str(value) for value in dice))

    while True:
        raw = ask(
            "Dice to re-roll (indexes 1-5, space-separated, empty to keep): > "
        )
        indexes = parse_dice_indexes(raw)
        if indexes is None:
            print("  Hmm, use indexes from 1 to 5 (e.g. 1 3 5), or Enter to keep.")
            continue
        break

    if indexes:
        for index in indexes:
            dice[index - 1] = random.randint(1, SIDES)
        print("Rolling...")
        animate_roll(dice, fast=fast, changing=[index - 1 for index in indexes])
        print("Dice: " + " ".join(str(value) for value in dice))
    else:
        print("  Keeping all five dice.")

    category = choose_category(dice, scores)
    scores[category] = score_for(category, dice)
    points = scores[category]
    print("  {} scores {} point{}.".format(
        category, points, "" if points == 1 else "s"
    ))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main(argv):
    fast = False
    for arg in argv:
        if arg == "--fast":
            fast = True
        elif arg in ("-h", "--help"):
            print(__doc__.strip())
            return 0
        else:
            print("Unknown option: {}".format(arg))
            print("Try: python3 five_dice_frenzy.py --help")
            return 2

    print_banner()

    scores = {name: None for name in CATEGORIES}
    for turn_number in range(1, len(CATEGORIES) + 1):
        play_turn(turn_number, scores, fast)
        print()
        print_score_table(scores)

    total = total_score(scores)
    print("\n" + "=" * 60)
    print("  FINAL SCORECARD")
    print("=" * 60)
    print_score_table(scores)
    print("\n  FINAL SCORE: {}".format(total))
    print("  RATING: {}".format(rating_for(total)))
    print("=" * 60)
    print("  " + SIGN_OFF)
    print("  Thanks for playing - now go argue about the real rules!")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except QuitGame:
        print("Thanks for playing - see you next game night!")
        sys.exit(0)
