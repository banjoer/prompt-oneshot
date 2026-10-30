# Sortlines — Real-Time Sorting Visualizer

**Difficulty:** Medium  |  **Stack:** HTML/CSS/JS (vanilla, single file)  |  **Estimated time:** 1–3 h

## The Problem

Sorting algorithms are usually taught as static pseudocode, but intuition only clicks when you can watch one run: bubble sort's slow percolation, quicksort's partition dance, heap sort's mound collapse. Students cramming for exams, interview candidates drilling fundamentals, and curious developers all reach for a bar-array visualizer — and building one is a classic exercise in pairing instrumented algorithm logic with a live, non-blocking animation. Build a polished single-file visualizer covering six algorithms with smooth animation, speed and size controls, and honest live statistics.

## Requirements

1. Deliver a single self-contained `sortlines.html` file using only vanilla HTML/CSS/JS — all markup, styles, and logic inside it. It must work when opened directly from disk (`file://`) in a modern browser; no server needed.
2. Render the array as vertical **bars** (divs or canvas) on a **dark background** with vibrant colors and three distinct states: a default color for unsorted bars, a highlight color for bars being compared, and a distinct color for bars confirmed sorted. Bar heights are proportional to values and rescale to fit when the window is resized.
3. Implement all six algorithms: **Bubble Sort, Insertion Sort, Selection Sort, Merge Sort, Quick Sort, and Heap Sort**. Provide one button per algorithm to select it; switching algorithms while idle resets the sorted highlighting and stats but keeps the current array.
4. Provide a **speed slider** (from very slow to very fast, e.g. 1–200 ms delay per step, default mid-range with the current value labelled) and an **array-size slider** from **10 to 200** elements (default ~60, current value labelled). Changing array size generates a fresh random array and resets stats; changing speed mid-run takes effect within a step without restarting the sort.
5. Provide a **Shuffle & Reset** button that generates a new random permutation, clears sorted highlighting, zeroes the counters, and stops any running sort cleanly. Provide a **Start / Pause** toggle button that begins the selected algorithm, pauses mid-run preserving counters, and resumes the same run.
6. Animate **smoothly**: the sort must run asynchronously (e.g. `async`/`await` with `setTimeout`, or `requestAnimationFrame`) so the UI never freezes — sliders, buttons, and window controls stay responsive at all times. Starting a second run while one is active is impossible (Start is disabled or re-arms safely); pausing then shuffling leaves no orphaned animation still painting.
7. Show a live **stats panel** updating during the run: **algorithm name**, **comparisons**, **swaps/writes**, and **elapsed time**. Counters are incremented by the algorithm code itself on each real compare/swap/write — never estimated or hardcoded. When a run finishes, sweep all bars to the sorted color and leave the final stats on display.
8. Handle edge cases: an already-sorted array still animates to the sorted state with truthful counters; array size 10 and 200 both render and sort correctly; pause/resume preserves exact counters; corrupt or missing state never blanks the page (fall back to a fresh random array).
9. **Sign-off:** the page must display, somewhere easy to spot (e.g. a footer), the date and time the solution was produced and the model/author that produced it (e.g. `Built 2026-10-30 10:15 by <model-name>`), plus a matching header comment at the top of the file.

## Constraints

- One file only: `sortlines.html`. No external CSS/JS files, no CDNs, no frameworks, no web fonts or images, no build step.
- Vanilla HTML/CSS/JS and standard browser APIs only. No network calls of any kind (`fetch`, XHR, beacons); everything runs locally.
- No persistence required; if any state is stored, use `localStorage` only. No cookies, no backend.
- Must run by double-clicking the file (`file://` protocol) in a current Chrome/Firefox/Edge/Safari. No dev server, no install.
- Sorting must not block the main thread: use async stepping so controls stay live even at the fastest speed.

## Sample Data / Inputs

No input files. The array is generated in code: a random permutation of values `1..N` where `N` is the array-size slider value. Example seed array at size 12 (illustrative only):

```
[7, 2, 11, 4, 9, 1, 12, 5, 3, 10, 6, 8]
```

Sanity-check statistics for a full run on a random shuffle of 100 elements (typical ranges, not exact — values depend on the shuffle):

```
algorithm    comparisons (typical)   swaps/writes (typical)
Bubble       4,400 – 5,050           1,900 – 3,100
Insertion    2,300 – 2,800           2,300 – 2,800
Selection      4,950 (fixed)           90 – 110
Merge          550 – 750             650 – 800
Quick          600 – 1,200             250 – 600
Heap         1,000 – 1,400             550 – 750
```

Deterministic smoke test: Bubble Sort on the ascending array `1..N` (Start pressed before ever pressing Shuffle at size 100) must report `N-1` comparisons and `0` swaps.

## Deliverable

- One file: `sortlines.html`
- Run: open `sortlines.html` in any modern browser (double-click it, or `File → Open`). No install, no server.

## Done When

- [ ] The page opens from `file://` and shows a bar array with six algorithm buttons, both sliders labelled, Shuffle & Reset, Start/Pause, and a stats panel.
- [ ] Each of the six algorithms visibly sorts a shuffled array into a monotonically increasing skyline ending in the sorted color.
- [ ] Compared bars flash the compare color and all bars end in the sorted color with final stats still displayed.
- [ ] Speed slider takes effect mid-run without restart; array-size slider (10–200) regenerates the array and resets stats.
- [ ] Shuffle & Reset produces a fresh order, zeroes stats, and leaves no orphaned animation; Start/Pause toggles with counters intact.
- [ ] Stats are truthful: Bubble Sort on an unshuffled ascending array of 100 reports exactly 99 comparisons / 0 swaps.
- [ ] The UI stays responsive at the fastest speed and resizing the window rescales the bars without breaking the run.
- [ ] The sign-off (date/time produced + model/author) is visible on the page and in a source header comment.

## Stretch Goals (optional)

- Add a **Step** button that advances exactly one compare/swap while paused.
- Add a comparison-count race mode: run two algorithms on identical shuffles and show both stat lines side by side.
- Add sound: map bar value to pitch with a mute checkbox (WebAudio only, no files).
