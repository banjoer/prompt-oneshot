# Elevator Panel Simulator

**Difficulty:** easy  |  **Stack:** Java (JDK only, single file)  |  **Estimated time:** 30–60 min

## The Problem

Building engineers and UX designers prototyping elevator logic don't start with hardware — they start with a little simulation they can *watch*. A floor panel that animates the car moving between floors, doors opening and closing, and requests queueing up makes scheduling problems obvious at a glance. Your job: build a self-contained terminal elevator simulator in Java that plays out a fixed, scripted set of passenger requests as a smooth in-place terminal animation, then reports how the run went.

## Requirements

1. Produce a single file `ElevatorSim.java`. It must compile with `javac ElevatorSim.java` and run with `java ElevatorSim` on any JDK 11+ — no build tool, no dependencies.
2. Embed the scripted schedule from the Sample Data section in the source as a constant (an array or list of small request objects/records). The simulation runs in **ticks** starting at tick `0`; each tick lasts **300 ms** (`Thread.sleep`). One tick = one animation frame.
3. **Animate in place:** every tick, clear the terminal (print ANSI `"\033[H\033[2J"` and flush) and redraw the entire panel. Frames must not scroll down the screen.
4. The panel must always show: the current tick; a direction indicator (`▲` moving up, `▼` moving down, `·` idle — ASCII `UP`/`DOWN`/`IDLE` is an acceptable fallback); the door state (`open`/`closed`); the building drawn vertically with all **8 floors** (floor 8 at the top, floor 1 at the bottom) and the elevator car drawn on its current floor, visually distinct when doors are open vs. closed (e.g. `[  ]` vs. `[##]`); the waiting request **queue in FIFO order**; and who is **on board** with their destination.
5. Implement exactly this state machine, in this order, once per tick:
   - (a) Any scripted requests scheduled for this tick join the **back** of the queue and are logged.
   - (b) If the elevator is idle and the queue is non-empty, it takes the **front** request and sets its target to that request's **origin** floor.
   - (c) The elevator performs **one** action: if a door cycle is in progress, advance it; otherwise, if it is not at its target floor, move **one** floor toward it; otherwise (already at the target floor) begin a door cycle.
   - Doors stay open for **exactly 2 ticks**, counting the tick the cycle begins as the first open tick (so beginning the cycle and advancing it are the same action). At the end of a **pickup** cycle the passenger boards and the target switches to their destination; at the end of a **dropoff** cycle the passenger leaves and the elevator becomes idle.
   - The elevator starts at floor 1, idle, doors closed.
6. Print a one-line event log under the panel (the latest event, or a rolling log of up to 4 lines): one line per request arrival, pickup, and dropoff, each prefixed with its tick number.
7. When every scripted request has been served, stop the animation and print a summary block: passengers served, total floors traveled, and total ticks elapsed. These must be **computed by the simulation, never hardcoded**. (For the embedded script the correct results are: 5 passengers, 28 floors traveled, 48 ticks — the final tick counter reads 47.)
8. **Sign-off:** the solution must show the date and time it was produced and the model/author that produced it — both as a header comment at the top of `ElevatorSim.java` and as a line in the final summary block.

## Constraints

- Java 11+, JDK standard library only. Single `.java` file, no Maven/Gradle, no external libraries.
- No network access, no file I/O, no user input — the run is fully scripted and must be deterministic: same timeline on every run, no randomness.
- Output must fit in 80 columns; use plain ASCII/UTF-8 text. ANSI escape codes may be used only for clearing the screen (colors optional as a stretch goal).
- The schedule must live in the source as data; all displayed numbers (tick, floors traveled, totals) must come from the simulation logic.

## Sample Data / Inputs

The embedded schedule — use exactly this:

```
tick  passenger  from  to
0     P1         2     6
4     P2         5     1
9     P3         3     8
14    P4         7     2
20    P5         1     5
```

Expected door-open events when the state machine in Requirement 5 is followed exactly:

```
ticks  event
1–2    doors open at floor 2 — P1 boards
7–8    doors open at floor 6 — P1 dropped off
10–11  doors open at floor 5 — P2 boards
16–17  doors open at floor 1 — P2 dropped off
20–21  doors open at floor 3 — P3 boards
27–28  doors open at floor 8 — P3 dropped off
30–31  doors open at floor 7 — P4 boards
37–38  doors open at floor 2 — P4 dropped off
40–41  doors open at floor 1 — P5 boards
46–47  doors open at floor 5 — P5 dropped off
47     simulation complete → summary (last frame shown is tick 47)
```

Example frame (exact layout is up to you, but all elements from Requirement 4 must be present and computed):

```
==================================================
 ELEVATOR PANEL                     tick 15
 direction: DOWN   doors: closed   floor: 1
--------------------------------------------------
  8 |      |
  7 |      |
  6 |      |
  5 |      |
  4 |      |
  3 |      |
  2 |      |
  1 |[##]__|
 Queue   : P3 (3>8)  <-  P4 (7>2)
 On board: P2 (to 1)
--------------------------------------------------
 log: tick 14 - P4 requested 7>2
==================================================
```

## Deliverable

- One file: `ElevatorSim.java`
- Run commands:
  - `javac ElevatorSim.java` — compile
  - `java ElevatorSim` — run the animation (about 15 seconds, ends by itself)

## Done When

- [ ] `javac ElevatorSim.java && java ElevatorSim` compiles and runs with no arguments and no errors.
- [ ] The panel is redrawn **in place** every 300 ms — the terminal does not scroll.
- [ ] Every frame shows the tick counter, direction indicator, door state, all 8 floors with the car on its floor, the FIFO queue, and any on-board passenger.
- [ ] P1 is picked up at floor 2 first; P2 visibly waits in the queue until P1 has been dropped at floor 6.
- [ ] The ten door-open events happen at the floors and ticks listed in the expected table, and the run finishes at tick 47.
- [ ] The final summary reports 5 passengers served, 28 floors traveled, and 48 ticks — all computed by the simulation.
- [ ] A sign-off with production date/time and model/author appears in the source header comment and in the final summary.

## Stretch Goals (optional)

- Accept an optional `--delay <ms>` argument (e.g. `java ElevatorSim --delay 50`) to change the tick speed for quick verification.
- Animate the doors through intermediate half-open frames (e.g. `[||]` → `[| |]` → `[|  |]`) while keeping the 2-tick cycle.
- Add ANSI color: green car when doors are open, red queue entries, but only when stdout is a terminal.
