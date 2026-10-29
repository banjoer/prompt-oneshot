# Echo Pads — Simon-Style Tone Memory

**Difficulty:** easy  |  **Stack:** HTML/CSS/JS (vanilla, single file)  |  **Estimated time:** 30–60 min

## The Problem

The classic Simon toy (1978) is still the purest test of working memory ever
put in a plastic case: four colored pads, each with its own tone, play a
growing sequence that the player must echo back perfectly. One wrong pad and
the run is over. Recreate it as a self-contained browser game — four glowing
pads, real synthesized tones (no audio files), a sequence that grows by one
step every round, and two difficulty modes: forgiving **Normal** (mistakes
replay the sequence) and brutal **Strict** (one mistake ends the run). A
persistent best streak in localStorage gives players a record to chase every
time they reopen the page.

## Requirements

1. One single self-contained `.html` file (inline CSS + JS) that runs by
   double-clicking it — no server, no build step, no external files.
2. Four large pads in a 2×2 grid (green, red, yellow, blue), each at least
   ~120 px, clearly clickable, with an obvious visual difference between
   idle and **lit** states (e.g. brighter color + glow/scale).
3. Each pad maps to a **distinct tone synthesized at runtime with the Web
   Audio API** (oscillator + gain envelope — no audio files, no external
   assets). "Playing" a pad always means lighting it AND sounding its tone
   together.
4. A **Start** button begins a new game at round 1; the game never
   auto-starts. A status line always shows one of: `Press Start`,
   `Watch…`, `Your turn`, or `Game over`.
5. The sequence starts with one random pad. Each round, the game replays the
   **full** sequence (each step lit ~420 ms with a ~180 ms gap), then the
   player must repeat it. After a correct round the sequence is extended by
   one new random pad and the next round begins after a ~700 ms pause. The
   current round number is displayed at all times.
6. **Input lock:** pad clicks are ignored while the sequence is playing back
   (`Watch…` state) and before the game starts.
7. During the player's turn, each pad press lights the pad and plays its tone
   (for the duration of the press, with a sensible minimum), and is checked
   immediately against the sequence. Completing the round shows a brief
   positive cue (e.g. "Nice!" or a flash) before the next playback.
8. A visible **Normal / Strict** mode toggle is settable before a game
   starts (changing it mid-game restarts the game or is disabled — pick one
   and make the behavior clear). On a wrong pad:
   - **Normal mode:** play a low error buzz, show "Wrong — watch again",
     then replay the *same* sequence and let the player retry the same round.
   - **Strict mode:** play the error buzz and end the game immediately,
     showing rounds completed and a "Play Again" button.
9. A **best streak** (highest round number reached in a single game) is
   displayed from page load, persisted in `localStorage` under the key
   `echoPadsBest`, updated the moment it is beaten (with a visible
   "New best!" indicator), and survives closing and reopening the browser.
10. **Sign-off:** the finished solution must display, somewhere easy to spot,
    the date and time it was produced and the model/author that produced it —
    a visible page footer (e.g. `Built 2026-10-29 14:32 · <model name>`) AND
    a matching header comment at the top of the HTML file.

## Constraints

- One single `.html` file; all markup, styles, and script inline. Must work
  from `file://` (double-click) in any modern browser.
- **Third-party libraries are permitted for this batch** (CDN script tag or
  inlined source) — but none are needed; a vanilla solution using only the
  Web Audio API, DOM, and CSS is expected. State any library used in a
  header comment.
- No network calls, no external assets, fonts, images, or audio files —
  every sound is synthesized with `AudioContext` oscillators.
- The `AudioContext` must be created/resumed inside a user-gesture handler
  (e.g. the Start click) to satisfy browser autoplay policies.
- Storage is `localStorage` only.
- Aim for under ~300 lines.

## Sample Data / Inputs

Suggested pad → tone mapping (descending, close to the original toy):

| Pad | Color  | Frequency          |
|-----|--------|--------------------|
| 0   | Green  | 329.63 Hz (E4)     |
| 1   | Red    | 261.63 Hz (C4)     |
| 2   | Yellow | 220.00 Hz (A3)     |
| 3   | Blue   | 164.81 Hz (E3)     |

- Error buzz: ~110 Hz sawtooth for ~400 ms (clearly uglier than any pad).
- Timing: step lit 420 ms · gap between steps 180 ms · pause between rounds
  ~700 ms.
- Persistence: `localStorage["echoPadsBest"]` = integer, default 0.

## Deliverable

- One file: `echo-pads.html` — the complete game.
- Run: double-click `echo-pads.html` (or open it via your browser's
  File → Open). No install, no server.

## Done When

- [ ] Opening the file shows four colored pads, a Start button, a mode
      toggle, round 0, status `Press Start`, and the best streak (0 on first
      run).
- [ ] Clicking Start plays a one-step sequence; the status changes
      `Watch…` → `Your turn`; clicks are ignored during `Watch…`.
- [ ] Pressing pads in the shown order advances rounds; each round replays
      the whole sequence plus one new step.
- [ ] Every pad lights up and sounds its own distinct pitch, both during
      playback and when pressed — the four pitches are clearly different.
- [ ] In Normal mode a wrong pad buzzes and replays the same sequence for a
      retry at the same round.
- [ ] In Strict mode a wrong pad buzzes and ends the game, showing rounds
      completed and a working Play Again button.
- [ ] Exceeding the best streak shows "New best!", and the new best is still
      displayed after closing and reopening the browser.
- [ ] The footer sign-off with date/time and model/author is visible on the
      page, with a matching header comment in the source.

## Stretch Goals (optional)

- Speed ramp: step duration shrinks ~20 ms every 4 rounds, to a floor of
  ~250 ms, so long runs feel increasingly frantic.
- Ear candy: a short ascending arpeggio every 5 rounds, and a descending
  two-tone "game over" phrase in Strict mode.
- Keyboard play: keys 1–4 (or arrow keys) trigger pads, with the key hint
  shown on each pad.
