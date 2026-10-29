# Swing Pong Spin Duel

**Difficulty:** medium  |  **Stack:** Java (Swing, JDK only)  |  **Estimated time:** 1.5–3 hours

## The Problem

Arcade classics survive because their physics feel fair but exploitable: a good Pong
clone lives or dies on how the ball reacts when it clips the edge of a paddle. You're
building a single-player Pong duel in a Swing window against a simple AI opponent —
with human paddle control on the keyboard, ball spin that depends on where the ball
strikes the paddle, a first-to-N score race, and proper pause/restart flow so a match
can be interrupted and replayed without restarting the JVM.

## Requirements

1. **Window & rendering:** a resizable-free `JFrame` (fixed size, e.g. 800×600) showing
   a centered dashed net line, both paddles, the ball, and the current score as drawn
   text (no images or external assets — draw everything with `Graphics2D`).
2. **Game loop:** a fixed-timestep loop driven by `javax.swing.Timer` (or an equivalent
   `Thread` loop) running at ~60 updates per second; rendering and update logic are
   separate methods.
3. **Player paddle:** the left paddle is human-controlled. `W`/`S` **and** the
   `↑`/`↓` arrow keys must both move it; movement is smooth (key held = continuous
   motion), clamped so the paddle can never leave the play area.
4. **AI opponent:** the right paddle is computer-controlled. It must track the ball's
   vertical position with a capped maximum speed **lower than the ball's maximum
   vertical speed**, so it is beatable; add a small reaction dead-zone (e.g. it only
   moves when the ball is more than ~6 px from its center) so it doesn't jitter.
5. **Ball physics & spin:** the ball bounces off the top and bottom walls. On paddle
   contact, the outgoing angle depends on **where** the ball hits the paddle: dead
   center sends it nearly horizontal, the extreme edges send it at up to ~60° from
   horizontal. The ball's total speed must increase slightly (e.g. ×1.05, capped) on
   each paddle hit so rallies escalate.
6. **Scoring & win condition:** a point is scored when the ball passes the opponent's
   paddle and exits the left/right edge; the ball then re-serves toward the player who
   just conceded, after a short ~1 s countdown. First player to reach **7 points**
   wins the match; the window then shows a clear "YOU WIN" / "AI WINS" banner.
7. **Pause & restart:** pressing `P` (or `Space`) toggles pause — while paused the
   ball and paddles freeze and a "PAUSED" overlay is shown; pressing `R` at any time
   (mid-rally, paused, or after a win) resets scores, ball, and paddle positions to a
   fresh match state.
8. **Sign-off:** the finished solution must display, somewhere easy to spot, the date
   and time it was produced and the model/author that produced it — e.g. a header
   comment at the top of the source file **and** a small line drawn at the bottom of
   the game window or printed to stdout on startup.

## Constraints

- **JDK only:** plain `javac` + `java`. No build tools (no Maven/Gradle), no external
  libraries, no assets, no resource files — everything drawn in code.
- Single self-contained source file is preferred; if you split classes, keep it to
  one directory with no packages beyond the default.
- No network access, no file I/O (no high-score persistence — keep everything in
  memory).
- Use Swing timers/events on the Event Dispatch Thread correctly; no `Thread.sleep`
  inside the paint method.
- Key input must use Key Bindings or a `KeyListener` with held-key state tracking —
  no reliance on OS key-repeat for paddle motion.

## Sample Data / Inputs

All tuning constants are up to you, but these reference values produce a playable
match and are a good starting point:

| Constant                    | Suggested value |
|-----------------------------|-----------------|
| Window size                 | 800 × 600 px    |
| Paddle size                 | 12 × 90 px      |
| Player paddle speed         | 420 px/s        |
| AI paddle max speed         | 300 px/s        |
| Ball size                   | 14 × 14 px      |
| Ball initial speed          | 320 px/s        |
| Ball speed multiplier/hit   | ×1.05           |
| Ball max speed              | 700 px/s        |
| Max bounce angle off paddle | 60°             |
| Points to win               | 7               |

Manual test inputs: hold `W`/`↑` then `S`/`↓` to verify smooth clamped motion; let
the ball pass you to confirm the AI scores and the re-serve goes toward you; hit the
ball with the paddle's top edge to confirm a steep upward angle; press `P` mid-rally,
then `R`.

## Deliverable

- `PongSpinDuel.java` (single file, or a small set of `.java` files in one folder)
- Compile and run:
  ```
  javac PongSpinDuel.java
  java PongSpinDuel
  ```

## Done When

- [ ] `javac` compiles with zero warnings/errors on a stock JDK 11+, and the window opens.
- [ ] The left paddle moves smoothly with `W`/`S` and arrow keys, and cannot leave the screen.
- [ ] The AI right paddle tracks the ball, jitters not at all, and visibly loses some rallies.
- [ ] Ball angle clearly varies with paddle contact point: center ≈ flat, edge ≈ steep (~60°).
- [ ] Ball speed visibly increases during long rallies, then resets on a new serve.
- [ ] Score displays for both players; reaching 7 shows the win banner and stops play.
- [ ] `P`/`Space` freezes everything with a PAUSED overlay; `R` restarts instantly from any state.
- [ ] The sign-off line (date/time + model/author) is visible in the window or on stdout.

## Stretch Goals (optional)

- **Spin drift:** paddle velocity at the moment of impact adds a small curve (english)
  to the ball's trajectory for the next second.
- **Adaptive AI:** the AI's max speed scales up slightly each time it loses a point,
  making comebacks harder.
- **Rally stats:** show current rally length and longest rally of the match in a
  corner of the window.
