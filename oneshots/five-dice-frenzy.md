# Five-Dice Frenzy — A Yahtzee-Lite Terminal Game

**Difficulty:** easy  |  **Stack:** Python (stdlib only)  |  **Estimated time:** 30–60 min

## The Problem

Game night is great until someone has to keep score on a napkin and argue about
whether that last roll was really a full house. A pocket-sized dice-poker game
for the terminal solves this: five dice, one roll per turn with an optional
single re-roll, and a fixed scorecard that fills up category by category. No
install, no setup — just run one Python file and play a full 6-category game
against the score sheet, with a little dice-roll animation to make it feel
alive.

## Requirements

1. The program is a single Python file that runs with `python3` and uses only
   the standard library (no pip installs).
2. Each turn, the program "rolls" five six-sided dice with a short terminal
   animation: the displayed dice faces visibly cycle/flash for roughly 1
   second (e.g. using `random`, `time.sleep` and carriage-return rewrites)
   before settling on the final values. Dice are rendered as ASCII art boxes,
   e.g.:
   ```
   ┌─────┐
   │ ● ● │
   │  ●  │
   │ ● ● │
   └─────┘
   ```
3. After the initial roll, the player may either keep all dice or re-roll a
   chosen subset **once** (e.g. typing `1 3 5` re-rolls dice 1, 3 and 5 with
   the same animation). Typing nothing keeps the hand.
4. The game has a scorecard with exactly 6 categories: **Ones**, **Twos**,
   **Threes**, **Three of a Kind** (sum of all dice if any value appears ≥3
   times, else 0), **Full House** (25 points if the hand is exactly three of
   one value and two of another, else 0), **Small Straight** (30 points if the
   hand contains four consecutive values, else 0).
5. After each final hand, the program shows the still-open categories and the
   score the current hand would earn in each. The player picks one open
   category, which is then filled permanently. A category can never be
   overwritten; choosing to "scratch" (score 0) is a legal move.
6. A full game is exactly 6 turns (one per category). After each turn the
   program prints a visible score table showing every category, its status
   (score or "open"), and the running total.
7. At the end of the game the program prints the final table, the total
   score, and a one-line rating: `< 40` → "Better luck next roll!",
   `40–69` → "Solid game!", `≥ 70` → "Dice master!".
8. All user input is validated with friendly re-prompts: out-of-range dice
   indexes, malformed input, or picking an already-filled category must never
   crash the game.
9. **Sign-off:** the finished solution must display, somewhere easy to spot,
   the date and time it was produced and the model/author that produced it —
   e.g. a header comment at the top of the `.py` file AND a line in the
   game's welcome banner.

## Constraints

- Python 3.8+, standard library only (`random`, `time`, `sys`, etc.).
- No network access, no files written to disk, no external assets.
- Single-player only; no AI opponent needed.
- The animation must not depend on terminal size — assume at least 80×24.
- Keep everything in one file; a reader should be able to skim it top to
  bottom.

## Sample Data / Inputs

Example turn flow (user input shown after `>`):

```
Turn 3/6
Rolling...
 [final dice shown: 4 4 2 6 4]
Dice to re-roll (indexes 1-5, space-separated, empty to keep): > 2 3
Rolling...
 [final dice shown: 4 5 2 3 4]

Open categories for this hand:
  1) Ones          ->  0
  2) Twos          ->  2
  3) Threes        ->  3
  4) Three of a Kind -> 0
  5) Full House    ->  0
  6) Small Straight-> 30
Score in category (1-6): > 6
```

Sample score table printed after each turn:

```
┌─────────────────┬───────┐
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
└─────────────────┴───────┘
```

## Deliverable

- `five_dice_frenzy.py` — the complete game.
- Run with: `python3 five_dice_frenzy.py`

## Done When

- [ ] Running `python3 five_dice_frenzy.py` shows a welcome banner including the sign-off line, then starts turn 1.
- [ ] Each roll visibly animates the dice faces for about a second before settling.
- [ ] Re-rolling only the chosen dice indexes works, and invalid input is re-prompted without crashing.
- [ ] After every turn a bordered score table shows filled scores, open categories, and the running total.
- [ ] The game ends after exactly 6 turns and prints the final table plus the rating line.
- [ ] Scoring matches the rules: try a hand of `4 5 2 3 4` → Small Straight scores 30; `3 3 3 5 5` → Full House scores 25; `6 6 6 2 1` → Three of a Kind scores 18.

## Stretch Goals (optional)

- Add a "chance" 7th category that scores the sum of all dice, extending the game to 7 turns.
- Color the dice and table using ANSI escape codes (e.g. green for good rolls).
- Offer a `--fast` command-line flag that skips the animation for impatient players.
