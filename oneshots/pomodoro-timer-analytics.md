# Pomodoro Timer with Analytics

**Difficulty:** Medium  |  **Stack:** HTML/CSS/JS (single file)  |  **Estimated time:** 1–3 h

## The Problem

Knowledge workers lose hours to unstructured time: they sit down to focus but drift, take breaks too late or too early, and have no record of how many real deep-work sessions they actually completed this week. A wall clock doesn't help — it can't auto-cycle focus and break phases, nudge you when a phase ends even with the tab in the background, or show whether you're on track for today's goal. Build a polished single-file Pomodoro timer with per-phase themes, timestamp-accurate countdowns, audio plus desktop-notification alerts, and a local analytics dashboard with a hand-rolled chart — so anyone can focus, recover, and prove it.

## Requirements

1. Deliver a single self-contained `pomodoro.html` file using only vanilla HTML/CSS/JS. It must run when opened directly from disk (`file://`) in a modern browser with no server and no network access.
2. Implement three phases — **Focus** (default 25 min), **Short Break** (default 5 min), **Long Break** (default 15 min) — with auto-cycling: every completed Focus session advances the completed-focus counter; after every 4th completed Focus session the next phase is Long Break, otherwise Short Break. Skipped or reset phases never advance the counter or change the cycle position.
3. Provide **Start**, **Pause**, **Skip**, and **Reset** controls with correct enabled/disabled states (e.g. Start disabled while running, Pause disabled while idle or paused, Skip/Reset disabled while idle at full duration). Prevent duplicate ticking intervals: at most one active timer at any time; pausing, skipping, resetting, or completing a phase cleans up the previous interval.
4. Keep time accurately when the tab is inactive: compute remaining time from `Date.now()` timestamps (stored deadline), not from tick counts, with a tick (e.g. `setInterval` ~250–500 ms) that re-renders from the deadline. Pausing stores the remaining milliseconds; resuming sets a fresh deadline from them.
5. Support an **auto-start next phase** toggle: when ON, completing a phase immediately starts the next phase after the alert; when OFF, the timer goes idle and waits for the user to press Start. The toggle state persists across reloads.
6. On natural phase completion: play an audible alert synthesized with the Web Audio API (e.g. `AudioContext` oscillator beeps — no external audio files, no network); fire a desktop `Notification` if permission was granted via an explicit user action (a dedicated "Enable notifications" button), otherwise continue silently with no errors; update `document.title` continuously during countdown in the form `MM:SS — <Phase>` (e.g. `14:20 — Focus`) and set a completion message on finish.
7. Provide a settings panel to change Focus / Short Break / Long Break durations (positive whole minutes only — reject zero, negative, fractional, or non-numeric input with an inline message and keep the old values) and the daily goal (positive whole number of Focus sessions). Changing durations while idle applies to the displayed time; mid-phase edits take effect on the next phase of that type and never corrupt the running countdown.
8. Apply a distinct visual theme per phase (e.g. red Focus, green Short Break, blue Long Break) via body class or CSS variables, with smooth transitions; the active phase label and a running/paused/idle indicator are always visible. Render remaining time prominently inside a circular progress indicator (SVG ring or conic-gradient) that depletes smoothly as the phase elapses.
9. Record session history: every naturally completed phase appends an entry `{ type, date, time }` (type is `focus`, `short`, or `long`; date is local `YYYY-MM-DD`; time is local `HH:MM`). Skipped or reset phases are never recorded. Show a history list (newest first) with type, date, and time, plus today's Focus count against the daily goal (e.g. `3 / 8 sessions`) with a progress bar.
10. Render a **7-day chart** of completed Focus sessions per day (today plus previous 6 days, labelled) drawn with hand-rolled code only — pure `<canvas>` 2D drawing or CSS bars built by your own code. Show a readable empty state ("No sessions yet — complete a Focus session to start your streak.") when there is no history.
11. Persist settings, daily goal, auto-start preference, cycle position (completed-focus count toward the next long break), and full session history to `localStorage` under namespaced keys (e.g. `pomodoro.*`), restoring everything on reload. Corrupt or unparseable stored values fall back to defaults without crashing and are overwritten on the next save.
12. **Sign-off:** the page must display, somewhere easy to spot (e.g. a footer), the date and time the solution was produced and the model/author that produced it (e.g. `Built 2026-10-30 09:15 by <model-name>`), plus a matching header comment at the top of the file.

## Constraints

- One file only: `pomodoro.html`. No external CSS/JS files, no CDNs, no frameworks, no web fonts, no images, no build step — Chart.js and any other library are forbidden.
- Standard browser APIs only: DOM, `Date`, `setInterval`, Web Audio API (`AudioContext`), `Notification`, `localStorage`, `<canvas>` 2D context. No network calls of any kind (`fetch`, XHR, beacons, dynamic script/link injection).
- Storage is `localStorage` exclusively — no IndexedDB, no cookies, no backend.
- Durations are positive whole minutes; goal is a positive whole number. Timer must stay correct when the tab is hidden or the window minimized.
- Must run by double-clicking the file (`file://` protocol) in a current Chrome/Firefox/Edge/Safari, fully offline. No install, no server.

## Sample Data / Inputs

Default settings (used when no saved state exists):

```json
{
  "focusMinutes": 25,
  "shortMinutes": 5,
  "longMinutes": 15,
  "dailyGoal": 8,
  "autoStart": false,
  "focusCompleted": 0
}
```

Example session history (solver may use for manual testing — paste into `localStorage` or complete sessions naturally):

```json
[
  { "type": "focus", "date": "2026-10-24", "time": "09:05" },
  { "type": "short", "date": "2026-10-24", "time": "09:35" },
  { "type": "focus", "date": "2026-10-25", "time": "10:12" },
  { "type": "focus", "date": "2026-10-29", "time": "14:02" },
  { "type": "focus", "date": "2026-10-30", "time": "08:50" },
  { "type": "focus", "date": "2026-10-30", "time": "09:20" }
]
```

Expected reading of the example: today (2026-10-30) shows `2 / 8 sessions`; the 7-day chart shows 2 bars of height 2 on 10-30, 1 on 10-29, 1 on 10-25, 1 on 10-24, and 0 elsewhere.

## Deliverable

- One file: `pomodoro.html`
- Run: open `pomodoro.html` in any modern browser (double-click it, or `File → Open`). No install, no server. Disconnect from the network to verify self-containment.

## Done When

- [ ] The page opens from `file://` with zero network requests, showing the timer at 25:00, phase label Focus, Start enabled and Pause disabled, plus settings and analytics panels.
- [ ] Start begins a visibly depleting circular countdown; minimizing/hiding the tab for 60 seconds still shows the correct remaining time on return (timestamp-based, no drift beyond 2 s).
- [ ] Pause freezes the countdown and Resume continues from the same second; only one interval ever runs (rapid Start/Pause clicking never accelerates the clock).
- [ ] Completing a Focus naturally records exactly one history entry, advances toward the goal counter, plays a Web Audio beep, and moves to Short Break (or Long Break after every 4th Focus); Skip and Reset record nothing.
- [ ] Auto-start ON begins the next phase immediately after completion; auto-start OFF waits idle for Start; the toggle survives a reload.
- [ ] Blocking notifications (or denying permission) leaves the timer fully functional; the tab title reads `MM:SS — <Phase>` throughout the countdown.
- [ ] Settings reject 0, negative, fractional, and non-numeric durations with an inline message and keep old values; valid edits persist across reload.
- [ ] Today's progress (e.g. `2 / 8` with progress bar) and the hand-drawn 7-day canvas/CSS chart match the stored history; with empty history a readable empty state appears instead of a blank chart.
- [ ] Reloading restores settings, goal, auto-start, cycle position, and history exactly; hand-corrupting a `pomodoro.*` key (e.g. setting it to `garbage`) and reloading falls back to defaults without a blank page.
- [ ] The sign-off (date/time produced + model/author) is visible on the page and in a source header comment.

## Stretch Goals (optional)

- Add a pause-on-tab-hide grace note plus a "sessions this week" total and longest-streak readout computed from history.
- Add per-day goal-met checkmarks on the 7-day chart and a Clear History button with native `confirm()`.
- Add keyboard shortcuts (`Space` Start/Pause, `S` Skip, `R` Reset) that ignore keystrokes typed inside inputs.
