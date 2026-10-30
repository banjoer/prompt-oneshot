# Clock, Stopwatch & Countdown

**Difficulty:** Easy  |  **Stack:** HTML/CSS/JS (vanilla, single file)  |  **Estimated time:** 15–60 min

## The Problem

Timing a workout, tracking a study sprint, or just glancing at the date shouldn't require installing an app or opening a bloated web service full of ads. What you need is one offline page with three honest tools: a big readable clock, a stopwatch with laps, and a countdown that tells you loudly when time is up. Build that utility as a single file that runs from disk, remembers your preferences, and never leaves a stray timer running in the background.

## Requirements

1. Deliver a single self-contained `clock.html` file using only vanilla HTML/CSS/JS — all markup, styles, and logic inside it. It must work when opened directly from disk (`file://`) in a modern browser; no server needed.
2. **Digital clock:** display the current time in `HH:MM:SS` format, updated every second via `setInterval`. Below it show the current date in long format (e.g. `Friday, October 30, 2026`).
3. Provide a **12/24-hour toggle button** that switches the clock between 24-hour time (e.g. `21:05:09`) and 12-hour time with an AM/PM indicator (e.g. `09:05:09 PM`). The selected format is saved to `localStorage` (e.g. `clock.prefs.v1`) and restored on reload.
4. **Stopwatch:** display elapsed time as `MM:SS:MS` where MS is centiseconds or milliseconds zero-padded (e.g. `02:47:35`). Provide **Start**, **Stop**, **Reset**, and **Lap** buttons. Start resumes from the current elapsed time, Stop pauses without resetting, Reset returns to zero and clears the running state.
5. Pressing Start repeatedly must never create duplicate intervals — only one stopwatch interval may run at a time. All intervals are cleared when they stop or finish; stopping, resetting, or reloading never leaves a hidden ticking timer.
6. **Laps:** pressing Lap records the current stopwatch value without stopping it and appends it to a numbered list (e.g. `Lap 1: 00:12:45`). The lap list is persisted to `localStorage` and restored on reload; Reset clears the displayed list and the stored laps.
7. **Countdown:** provide a number input for a duration in seconds plus a **Start Countdown** button. Accept only positive whole numbers (reject zero, negatives, decimals, and non-numeric input with an inline message and no timer started). Show the remaining time ticking down to zero.
8. While a countdown is running, its start button is **disabled** so overlapping countdowns cannot be created; it re-enables when the countdown finishes or is cancelled. When the countdown reaches zero, show a visible **"Time is up!"** message and flash the page background red for a few seconds (a native `alert()` may supplement this but must not replace the visible message).
9. Style the page as a **dark theme** with a large, highly readable clock. Clock, stopwatch, and countdown live in three clearly labelled sections; all buttons show visible hover, focus, and disabled states; the layout is usable on desktop and narrow mobile screens.
10. **Sign-off:** the page must display, somewhere easy to spot (e.g. a footer), the date and time the solution was produced and the model/author that produced it (e.g. `Built 2026-10-30 10:15 by <model-name>`), plus a matching header comment at the top of the file.

## Constraints

- One file only: `clock.html`. No external CSS/JS files, no CDNs, no frameworks, no web fonts or images, no build step.
- Vanilla JS only: `setInterval`/`clearInterval`, `Date`, DOM, `localStorage`. No network calls of any kind (`fetch`, XHR, beacons).
- Storage is `localStorage` exclusively — one or two keys for prefs and laps. No cookies, no backend.
- Must run by double-clicking the file (`file://` protocol) in a current Chrome/Firefox/Edge/Safari. No dev server, no install.

## Sample Data / Inputs

No input files. Example lap list after a short session (format only — exact values depend on timing):

```
Lap 1: 00:12:45
Lap 2: 00:25:10
Lap 3: 00:31:02
```

Example countdown inputs and expected outcomes:

```
Input "10"  → counts 10 … 0, then "Time is up!" + red flash
Input "0"   → rejected, inline message, no timer starts
Input "-5"  → rejected, inline message, no timer starts
Input "abc" → rejected, inline message, no timer starts
```

## Deliverable

- One file: `clock.html`
- Run: open `clock.html` in any modern browser (double-click it, or `File → Open`). No install, no server.

## Done When

- [ ] The page opens from `file://` and the clock ticks every second in `HH:MM:SS` with the long date below it.
- [ ] The 12/24-hour toggle switches formats (with AM/PM in 12-hour mode) and the choice survives a reload.
- [ ] The stopwatch counts in `MM:SS:MS`; Start resumes, Stop pauses, Reset zeroes; mashing Start creates only one running timer.
- [ ] Laps append numbered entries without stopping the stopwatch, survive a reload, and are cleared by Reset.
- [ ] Countdown accepts only positive whole seconds; invalid input shows an inline message and starts nothing.
- [ ] Countdown start is disabled while running, and reaching zero shows "Time is up!" plus a red background flash.
- [ ] Dark theme, three labelled sections, visible button states, and a usable mobile layout.
- [ ] The sign-off (date/time produced + model/author) is visible on the page and in a source header comment.

## Stretch Goals (optional)

- Countdown pause/cancel button that stops the timer and re-enables Start.
- Audible beep on countdown finish using `AudioContext` (no external files).
- Stopwatch millisecond precision toggle or a "best lap" highlight.
