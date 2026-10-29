# Reflex Light — Reaction Time Tester

**Difficulty:** easy  |  **Stack:** HTML/CSS/JS (vanilla, single file)  |  **Estimated time:** 30–60 min

## The Problem

Esports players, athletes, and the simply curious all want to know the same
thing: how fast are my reflexes, really? Human reaction time to a visual
stimulus is typically 150–300 ms, but you can't measure it with a stopwatch —
you need a stimulus that appears at an unpredictable moment and a timer that
starts the instant it shows. This challenge is a standalone web page that
runs the classic "wait for green" test: the screen turns red, switches to
green after a random delay, and the player clicks as fast as they can.
Clicking too early is a false start and must be called out. Attempt history
and a persistent best time turn a one-off gimmick into something worth
coming back to.

## Requirements

1. The page shows a single large click target (at least half the viewport)
  that cycles through four clearly labeled states: **Idle** ("Click to
  start"), **Waiting** (red background, "Wait for green…"), **Go** (green
  background, "CLICK!"), and **Result** (shows the measured time).
2. Clicking the target in the Idle state starts a round: the target turns
   red and, after a **random delay between 1.5 and 5 seconds**, turns green.
3. When the target turns green, start a timer; when the player clicks, stop
   it and display the reaction time in **whole milliseconds** (e.g. `243 ms`).
4. **False-start detection:** if the player clicks while the target is red
   (before it turns green), the round is aborted, the target shows a clear
   "Too soon! False start." message, and no time is recorded for that round.
5. After a valid click or a false start, clicking the target again returns
   it to the Waiting state and starts a new round (no page reload).
6. An **attempt history** lists every valid reaction time from the current
   and previous sessions, most recent first, numbered (e.g.
   `#7 — 243 ms`). False starts are not listed.
7. The **best time** (lowest valid ms) is shown prominently on the page and
   is persisted in `localStorage`, so it survives closing and reopening the
   browser. The attempt history is also persisted in `localStorage`.
8. A "Clear history" button wipes both the stored history and the best time
   from `localStorage` and resets the display.
9. Each valid result is labeled qualitatively: under 200 ms "Blazing!",
   200–250 ms "Fast", 251–300 ms "Average", over 300 ms "Keep practicing".
10. **Sign-off:** the finished page must display, somewhere easy to spot
    (e.g. a footer), the date and time it was produced and the model/author
    that produced it.

## Constraints

- Vanilla HTML/CSS/JS only — everything in **one file** (`index.html`), no
  frameworks, no build step, no external fonts, icons, or CDNs.
- No network calls of any kind; the page must work fully offline from
  `file://`.
- Storage is `localStorage` only — no cookies, no servers.
- Use `Date.now()` (or `performance.now()`) for timing; the random delay
  must be implemented with `setTimeout` and cancelled cleanly on a false
  start (no double-timing or zombie timers).
- All timing/state logic must be robust against rapid repeated clicks and
  clicking during state transitions.

## Sample Data / Inputs

No external data. Expected localStorage shape (keys are suggestions):

```json
{
  "reflexBestMs": 187,
  "reflexHistory": [243, 221, 310, 187, 265]
}
```

A typical session looks like: click to start → red 2.3 s → green → click →
`243 ms — Fast` → history gains `#1 — 243 ms`, best shows `243 ms`.

## Deliverable

- `index.html` — the complete game (markup, styles, and script inline).
- Run: open `index.html` in any modern browser (double-click it, or
  `python3 -m http.server` and visit `http://localhost:8000/index.html`).

## Done When

- [ ] Clicking the idle target turns it red; it turns green after a random
      delay between 1.5 and 5 s.
- [ ] Clicking while red aborts the round with a "Too soon!" false-start
      message and records nothing.
- [ ] Clicking while green displays the reaction time in whole ms plus its
      qualitative label (Blazing! / Fast / Average / Keep practicing).
- [ ] The attempt history updates after every valid round, newest first.
- [ ] The best time is shown and persists across a full browser restart
      (close the tab/browser, reopen the file — best and history are back).
- [ ] "Clear history" empties the history and resets the best time.
- [ ] The date/time produced and the model/author are visible on the page.

## Stretch Goals (optional)

- Show a live "average of all attempts" next to the best time.
- Add a subtle scale/flash animation on the green state using pure CSS.
- Support keyboard input (Spacebar) as an alternative to clicking.
