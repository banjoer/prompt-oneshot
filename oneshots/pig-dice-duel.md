# Pig Dice Duel — Push-Your-Luck vs. the Computer

**Difficulty:** easy  |  **Stack:** Java (JDK only)  |  **Estimated time:** 30–60 min

## The Problem

Pig is the classic push-your-luck dice game: roll a die as many times as you
dare, bank your points before a 1 wipes them out, and race your opponent to
100. It's a perfect party game, but playing it fairly against a friend needs a
die, a scoresheet, and someone who doesn't "forget" their turn total. A
terminal version solves all three: it rolls the die, draws the face, tracks
every point, and even provides a built-in opponent — a computer player with a
simple, visible strategy — so you can play a full match solo in one file with
nothing but a JDK.

## Requirements

1. The program is a single Java source file, `PigDiceDuel.java`, that compiles
   with `javac` and runs with `java`, using only the standard JDK (no build
   tools, no external libraries).
2. The game implements the classic rules of Pig: two players (human vs.
   computer) take turns rolling one six-sided die. On a turn, the active
   player may roll repeatedly; each roll of 2–6 adds to a **turn total**;
   rolling a **1** ("pig!") loses the entire turn total and ends the turn;
   choosing to **hold** banks the turn total into the player's score and ends
   the turn. First player to reach **100 or more** banked points wins.
3. Every roll is drawn as an ASCII-art die face showing the rolled value with
   pips, e.g. for a 5:
   ```
   ┌─────────┐
   │ ●     ● │
   │    ●    │
   │ ●     ● │
   └─────────┘
   ```
   All six faces (1–6) must render correctly.
4. Before every decision, the program prints the full **turn state**: whose
   turn it is, both players' banked scores, the current turn total, and what
   the banked score would become if the active player holds now.
5. After each completed turn, the program prints a **score progression line
   for the round**, e.g.:
   `Round 3 — You: 24 (+9 banked) | CPU: 31 (+0, rolled a pig!)`
   so the whole match can be followed top to bottom.
6. The human is prompted each roll with `(r)oll or (h)old`. Input is
   validated: anything that isn't `r`/`roll` or `h`/`hold` (case-insensitive)
   is re-prompted without crashing or ending the turn.
7. The computer opponent uses a fixed, visible strategy: it keeps rolling
   until its turn total is **20 or more**, then holds (unless banking would
   win the game immediately, in which case it holds as soon as the turn total
   reaches the needed amount). Every computer decision is printed, e.g.
   `CPU rolls... 4 (turn total 13) — rolls again` /
   `CPU rolls... 6 (turn total 19) — holds? No, one more!` /
   `CPU holds at 22, banking 22 points.`
8. Rolling a 1 is clearly announced for both players (e.g. `*** PIG! Rolled a
   1 — turn total lost! ***`), the turn passes, and the turn total resets.
9. When either player banks enough to reach 100+, the program announces the
   winner with a final scoreboard showing both totals and the number of rounds
   played, then exits cleanly.
10. **Sign-off:** the finished solution must display, somewhere easy to spot,
    the date and time it was produced and the model/author that produced it —
    e.g. a header comment at the top of `PigDiceDuel.java` AND a line in the
    game's welcome banner.

## Constraints

- Java 11+ (any modern JDK), standard library only (`java.util.Random`,
  `java.util.Scanner`, etc.).
- No build tools (no Maven/Gradle), no external dependencies, no network
  access, no files written to disk.
- Exactly one source file; everything must compile with a single `javac`
  command.
- Interactive terminal play only; no GUI, no arguments required to start.
- Use `Random` (or `ThreadLocalRandom`) for real randomness — do not hard-code
  dice sequences.

## Sample Data / Inputs

Example opening of a game (user input shown after `>`):

```
==========================================
   PIG DICE DUEL — first to 100 wins!
   (built 2026-10-29 14:32 by <model>)
==========================================

Round 1 — YOUR TURN   [You: 0 | CPU: 0]
Turn total: 0   (hold now -> 0 banked)
(r)oll or (h)old? > r
You roll:
┌─────────┐
│ ●     ● │
│    ●    │
│ ●     ● │
└─────────┘
Rolled a 5! Turn total: 5   (hold now -> 5 banked)
(r)oll or (h)old? > h
You bank 5 points.
Round 1 — You: 5 (+5 banked) | CPU: 0 (not yet played)

Round 1 — CPU TURN   [You: 5 | CPU: 0]
CPU rolls... 3 (turn total 3) — rolls again
CPU rolls... 1
*** PIG! Rolled a 1 — turn total lost! ***
Round 1 — You: 5 | CPU: 0 (+0, rolled a pig!)
```

Example endgame line:

```
*** CPU banks 21 points and reaches 104! ***
FINAL — You: 87 | CPU: 104 after 9 rounds. CPU wins — better luck next time!
```

## Deliverable

- `PigDiceDuel.java` — the complete game.
- Compile and run with:
  ```
  javac PigDiceDuel.java
  java PigDiceDuel
  ```

## Done When

- [ ] `javac PigDiceDuel.java && java PigDiceDuel` compiles cleanly and shows a welcome banner containing the sign-off line.
- [ ] Every roll displays the correct ASCII die face for values 1 through 6.
- [ ] Before each human decision the full turn state is visible: both banked scores, turn total, and the hold-preview value.
- [ ] Typing garbage (`x`, empty input, `ROLLL`) is re-prompted; the game never crashes or skips a turn.
- [ ] Rolling a 1 announces "pig", zeroes the turn total, and passes the turn — for both players.
- [ ] The CPU visibly follows its hold-at-20 strategy and announces each roll/hold decision.
- [ ] A score-progression line is printed after every turn, each round.
- [ ] The game ends the moment someone banks their way to 100+, prints a final scoreboard with the round count, and exits.

## Stretch Goals (optional)

- Add a `--fast` flag (read from `args`) that skips pauses/prompts and simulates an entire CPU-vs-CPU match instantly, printing the full log.
- Color the output with ANSI escape codes (e.g. red for a pig, green for banked points).
- Let the human choose first to 50 ("short game") or 100 ("full game") at startup.
