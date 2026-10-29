# Stepforge — 16-Step Drum Machine

**Difficulty:** hard  |  **Stack:** HTML/CSS/JS (Web Audio API, vanilla)  |  **Estimated time:** 4–7 hours

## The Problem

Browser-based drum machines are the classic stress test for real-time audio
engineering: `setTimeout` and `setInterval` jitter by tens of milliseconds,
which is more than enough to make a rhythm sound drunk. Real grooveboxes
schedule sounds against a sample-accurate audio clock, synthesize their own
voices instead of playing back samples, and let musicians change tempo and
swing mid-performance without the beat ever stuttering. Most web tutorials
get one of these right at best. Build the real thing: a self-contained
16-step sequencer with four Web Audio–synthesized voices (kick, snare,
hi-hat, clap), a clickable step grid, BPM and swing controls, a playhead
locked to the audio clock, and patterns that persist in localStorage.

## Requirements

1. The solution is a single `index.html` file (embedded `<style>` and
   `<script>`) that runs by opening it directly in a modern browser — no
   server, no build step, no dependencies.
2. **Four fully synthesized voices — no audio files.** All sound is produced
   at trigger time with the Web Audio API (oscillators, generated noise
   buffers, filters, gain envelopes). No `<audio>` elements, no sample
   files, no data-URI audio, no network requests. Target sound designs
   (tune to taste, but each voice must be clearly distinguishable):
   - **Kick** — a sine oscillator pitched from ~150 Hz down to ~50 Hz over
     ~0.1 s with a fast-decaying amplitude envelope (~0.4 s).
   - **Snare** — a short white-noise burst through a bandpass or highpass
     filter (~1.5–2 kHz) layered with a tonal "body" oscillator (~180 Hz),
     decaying over ~0.2 s.
   - **Hi-hat** — white noise through a highpass filter (~7 kHz+) with a
     very short decay (~0.05 s).
   - **Clap** — 3–4 short noise bursts spaced ~10 ms apart through a
     bandpass filter (~1–1.5 kHz), with a slightly longer decay tail.
3. **16-step grid.** Four labeled rows (kick, snare, hi-hat, clap) × 16
   clickable step cells. Clicking a cell toggles it on/off with an immediate
   visual change; active steps are visually distinct per instrument (e.g.
   per-row colors). Steps must be toggleable while playing, and the change
   must be audible on the next pass of that step.
4. **Sample-accurate scheduler.** Implement the lookahead-scheduling
   pattern: a short JS timer (e.g. every 25 ms) schedules upcoming notes
   against `AudioContext.currentTime` using a lookahead window (e.g. 0.1 s).
   Audible timing must NOT be driven directly by `setInterval` callbacks.
   The timer interval and lookahead must be named constants at the top of
   the script.
5. **Autoplay-policy compliance.** The `AudioContext` is created/resumed on
   the first user gesture (pressing Play), so no console warnings or silent
   starts occur.
6. **BPM control.** Adjustable from 60 to 200 BPM (slider and/or number
   input, showing the current value). Changing BPM while playing takes
   effect within one 16th note — no stopping, no audible glitch, no skipped
   or double-triggered steps.
7. **Swing control.** Adjustable from 0% (straight) to at least 60%,
   displayed as a number. Swing delays every off-beat 16th (even-numbered
   steps: 2, 4, 6, …) by the given fraction of a 16th-note duration while
   on-beats stay exactly on the grid. Must be adjustable live during
   playback.
8. **Playhead animation.** A clearly visible playhead (highlighted column)
   advances step-by-step in sync with the audio. It must be driven by the
   audio clock — e.g. the scheduler pushes each scheduled step's time into a
   queue and a `requestAnimationFrame` loop draws the current step — NOT by
   the scheduling timer, so the visual never drifts from what is heard.
9. **Transport controls.** Play and Stop buttons with obvious active state.
   Stop halts scheduling, silences any ringing voices, and resets the
   playhead to step 1.
10. **Pattern persistence via localStorage.** The user can save the current
    pattern (full grid + BPM + swing) under a chosen name, see the list of
    saved patterns, and Load or Delete any of them. Loading restores grid,
    BPM, and swing exactly. On first visit (empty storage), the built-in
    Default Groove from Sample Data is loaded.
11. The layout must be fully usable at a ~1280×800 viewport: transport,
    tempo/swing controls, and the save/load panel visible without horizontal
    scrolling.
12. **Sign-off:** the finished solution must display, somewhere easy to
    spot, the date and time it was produced and the model/author that
    produced it (e.g. a footer on the page and/or a header comment in the
    source).

## Constraints

- Vanilla HTML/CSS/JS only — no frameworks, no libraries, no CDNs, no
  external assets, everything inline in one file.
- Audio exclusively via the Web Audio API, synthesized at runtime; no audio
  files, no `speechSynthesis`, no network calls of any kind.
- Persistence limited to `localStorage` (JSON-serialized patterns). No
  servers, no third-party APIs.
- Must work from the `file://` protocol (double-click the file) in a current
  Chrome, Edge, or Firefox.
- Scheduler constants (timer interval, lookahead seconds) must be named
  constants, and the audio code must be organized so each voice is a
  self-contained trigger function (e.g. `playKick(time)`, `playSnare(time)`).

## Sample Data / Inputs

Built-in **Default Groove**, loaded on first visit and shown pre-selected in
the grid (rows are 16 steps, `1` = active, `0` = off). This is also the
suggested internal/persisted shape:

```json
{
  "name": "Default Groove",
  "bpm": 120,
  "swing": 0,
  "tracks": {
    "kick":  [1,0,0,0, 1,0,0,0, 1,0,0,0, 1,0,0,0],
    "snare": [0,0,0,0, 1,0,0,0, 0,0,0,0, 1,0,0,0],
    "hihat": [1,0,1,0, 1,0,1,0, 1,0,1,0, 1,0,1,0],
    "clap":  [0,0,0,0, 0,0,0,0, 0,0,0,0, 0,0,1,0]
  }
}
```

That is: four-on-the-floor kick, snare on beats 2 and 4 (steps 5 and 13),
hi-hat on every on-beat 8th, and a single clap pickup on step 15.

## Deliverable

- One file: `index.html` (embedded `<style>` and `<script>`; no other files).
- Run: double-click `index.html` or open it via a `file://` URL in a modern
  browser. No server or tooling required.

## Done When

- [ ] Opening the page shows the 4×16 grid preloaded with the Default
      Groove, plus Play/Stop, BPM, and swing controls.
- [ ] Pressing Play starts a clean groove at 120 BPM where kick, snare,
      hi-hat, and clap are four clearly distinguishable synthesized voices
      (no samples anywhere).
- [ ] The playhead column highlight advances in lockstep with the audible
      steps and is still perfectly aligned after 60 seconds of playback (no
      drift, no double-fires).
- [ ] Raising BPM from 120 to 180 mid-playback speeds the groove up within
      one step, with no skipped or repeated hits.
- [ ] Setting swing to 60% audibly delays the off-beat 16ths (the hi-hat
      "ands") while the kick and snare on-beats stay exactly on the grid.
- [ ] Clicking steps while playing adds/removes hits on the next loop pass.
- [ ] Saving a pattern as "Test A", reloading the page, and loading
      "Test A" restores grid, BPM, and swing exactly; deleting it removes it
      from the saved list.
- [ ] Stop silences everything and resets the playhead to step 1.
- [ ] A visible sign-off on the page shows the production date/time and the
      model/author.

## Stretch Goals (optional)

- Per-track volume sliders and mute buttons, also persisted with the
  pattern.
- Step velocity: right-click (or long-press) a cell to cycle through 2–3
  accent levels, visually distinguished (e.g. brighter/larger) and applied
  to the trigger gain.
- Export/import patterns as JSON via the clipboard (still fully offline).
