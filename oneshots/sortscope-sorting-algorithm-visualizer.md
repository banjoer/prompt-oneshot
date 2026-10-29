# SortScope — Sorting Algorithm Visualizer

**Difficulty:** medium  |  **Stack:** Java (Swing, JDK only)  |  **Estimated time:** 1–3 h

## The Problem

Sorting algorithms are usually taught as static pseudocode, but intuition only really clicks when you can *watch* one run: bubble sort's slow percolation, insertion sort's shifting sweep, quicksort's partition dance. Educators demoing in a classroom, students cramming for exams, and interview candidates drilling fundamentals all reach for a bar-array visualizer — and building one is a classic exercise in marrying instrumented algorithm logic with a live GUI that never freezes. Your job: build a self-contained Swing desktop app that renders an array of bars, animates three sorting algorithms with compare/swap highlighting and live statistics, and lets the user shuffle, pause, and change speed mid-run until everything sweeps green.

## Requirements

1. Produce a single file `SortScope.java`. It must compile with `javac SortScope.java` and run with `java SortScope` on any JDK 11+ — no build tool, no dependencies, no extra files.
2. The window (`JFrame`, suggested initial size ~900×600) shows a bar chart of **100 bars**, one per array element. On startup the array holds the values **1..100 in ascending order**; bar heights are proportional to the values and must rescale to fit the panel when the window is resized.
3. A control bar offers: an algorithm selector (combo box or radio buttons) with exactly **Bubble Sort**, **Insertion Sort**, and **Quick Sort**; a **Shuffle** button; a **Start/Pause** toggle button; and a speed slider labeled with its current delay, ranging **0–100 ms** per step, defaulting to 20 ms.
4. **Shuffle** randomizes the array (Fisher–Yates with `java.util.Random`, or `Collections.shuffle`) and repaints. Shuffle is only enabled while no sort is running; the algorithm selector is disabled while a sort is running or paused and re-enabled when idle.
5. Sorting runs **off the Event Dispatch Thread** (a worker thread or `SwingWorker`) so the UI never freezes: the slider, Pause button, and window controls stay responsive at all times. Every comparison and every write/swap the algorithm performs counts as a **step**; after each step the worker sleeps for the *current* slider delay — changing the slider mid-run must take effect within one step, without restarting the sort.
6. Highlighting on every frame: the one or two bars involved in the current comparison are drawn in a distinct "compare" color (e.g. yellow), the bar(s) being written/swapped in a "swap" color (e.g. red), and all other bars in a neutral color. All drawing happens in `paintComponent` on a custom `JPanel` — no flicker, no painting outside the paint callback.
7. A status bar shows live, computed values: **comparisons**, **swaps/writes**, **elapsed time**, and current **state** (`ready`, `sorting`, `paused`, `sorted`). Counters must be incremented by the algorithm code itself, never estimated or hardcoded.
8. **Pause** freezes the animation at the current step (the button label switches to "Resume"); resuming continues the same run with its counters intact. Pressing Shuffle while paused first aborts the paused run cleanly — no orphaned worker may keep painting afterwards.
9. When a sort finishes, run a short **verification sweep**: a green wave passes once over the bars from left to right; after the sweep all bars stay green, the state reads `sorted`, and the final counters and elapsed time remain on display.
10. The three algorithms must be genuinely different implementations operating on the same instrumented array (comparisons and swaps/writes route through shared helper methods so the stats and animation stay honest): Bubble Sort with an early-exit flag, Insertion Sort, and in-place Quick Sort (Lomuto or Hoare partition — your choice, but state the pivot scheme in a comment).
11. **Sign-off:** the finished solution must display, somewhere easy to spot, the date and time it was produced and the model/author that produced it — both as a header comment at the top of `SortScope.java` and as a visible label inside the window (e.g. at the right end of the status bar or in an About dialog).

## Constraints

- Java 11+, JDK standard library only (`javax.swing`, `java.awt`, `java.util`). Single `.java` file; no Maven/Gradle, no external libraries.
- No network access, no file I/O, no sound (unless attempting a stretch goal).
- All displayed numbers (comparisons, swaps/writes, elapsed time, bar heights) must be computed by the program — nothing hardcoded.
- The array size (100) and delay range (0–100 ms) are compile-time constants.
- At delay 0 the worker must still give the EDT a chance to paint (e.g. `Thread.yield()`, or batch a few steps per repaint) — the window must never freeze even at full speed.

## Sample Data / Inputs

No input files. The array is generated in code: values `1..100`, initially ascending, randomized by the Shuffle button. Sanity-check statistics for a full run on any shuffle (typical ranges, not exact numbers — counters depend on the shuffle):

```
algorithm    comparisons (typical)   swaps/writes (typical)
Bubble       4,400 – 5,050           1,900 – 3,100
Insertion    2,300 – 2,800           2,300 – 2,800
Quick          600 – 1,200             250 – 600
```

Deterministic smoke test: Bubble Sort (with early exit) on the untouched ascending array — i.e. Start pressed *before* ever pressing Shuffle — must report exactly **99 comparisons** and **0 swaps** and finish almost instantly.

## Deliverable

- One file: `SortScope.java`
- Run commands:
  - `javac SortScope.java` — compile
  - `java SortScope` — launch the visualizer window

## Done When

- [ ] `javac SortScope.java && java SortScope` compiles and opens a window showing 100 ascending bars, with no console errors.
- [ ] All three algorithms are selectable, and each visibly sorts a shuffled array into a monotonically increasing skyline.
- [ ] During a run the compared bars flash the compare color and the written/swapped bars flash the swap color; at the end a green sweep confirms the sort and all bars remain green.
- [ ] Shuffle produces a fresh random order and is disabled while sorting; the algorithm selector is disabled during a run and re-enabled when `ready` or `sorted`.
- [ ] The speed slider takes effect mid-run: dragging from 100 ms to 0 ms visibly accelerates the animation without a restart, and the UI stays responsive at 0 ms.
- [ ] Pause halts the animation mid-step and Resume continues with counters intact; pressing Shuffle while paused leaves no orphaned worker animating.
- [ ] Counters match the algorithm: Bubble Sort on a fresh unshuffled array reports exactly 99 comparisons / 0 swaps, and typical-run stats fall inside the sanity ranges above.
- [ ] Resizing the window rescales the bars without breaking or restarting the animation.
- [ ] A sign-off with production date/time and model/author appears in the source header comment and visibly inside the window.

## Stretch Goals (optional)

- Add a **Step** button that advances exactly one compare/swap while paused.
- Add a fourth algorithm (Merge Sort or Heap Sort) reusing the same instrumented array — observe how its write pattern differs from the in-place trio.
- Map bar value to pitch and play a short `javax.sound.sampled` blip on each swap (still JDK-only), with a mute checkbox.
- Offer array-size presets (e.g. 25 / 100 / 250 bars) via a second combo box; changing it re-shuffles and resets the counters.
