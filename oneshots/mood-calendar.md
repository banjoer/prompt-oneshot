# Mood Calendar

**Difficulty:** easy  |  **Stack:** JavaScript (browser, vanilla HTML/CSS/JS)  |  **Estimated time:** 30–60 min

## The Problem

Most mood-tracking apps are overkill: accounts, cloud sync, graphs you never
read. What actually works is the "year in pixels" idea — one glance at a
calendar tells you how the month is going. You need a tiny, fully local web
page where you tap a day, pick an emoji for your mood, and instantly see the
month fill up with color — plus a per-week average strip so you can spot
which weeks went well and which didn't. Everything must survive a page
reload with zero setup.

## Requirements

1. The app is a **single HTML file** (`mood-calendar.html`) using only
   vanilla HTML/CSS/JS — no libraries, no frameworks, no network requests.
2. It renders a **calendar grid for one month** at a time, with day-of-week
   headers (Mon–Sun or Sun–Sat, your choice) and each day cell correctly
   aligned under its weekday. The month and year are shown as a title
   (e.g. "October 2026").
3. **Previous / Next month buttons** let the user navigate between months;
   the grid re-renders correctly for any month (including February in leap
   years).
4. Clicking a day cell opens a small **emoji picker** offering exactly these
   five moods: `😄 😐 😢 😡 😴` (great, meh, bad, angry, tired). Picking one
   stamps that emoji into the day cell. Clicking the same emoji again (or a
   clearly visible "clear" option in the picker) removes the entry, leaving
   the cell blank.
5. **Future days cannot be logged**: days after today's real date show no
   picker (visually dimmed or simply non-interactive). Days in past or future
   *months* are loggable/clearable only according to the same rule relative
   to today's date.
6. Every entry is **persisted in `localStorage`** keyed by ISO date
   (`YYYY-MM-DD`), so reloading the page or navigating away and back shows
   all previously logged moods in their correct cells.
7. A **weekly average strip** is shown alongside (or under) the calendar:
   one row per calendar week of the displayed month. For each week, map the
   logged emojis to scores (`😄`=5, `😐`=3, `😢`=1, `😡`=2, `😴`=4 — i.e.
   rested beats neutral), compute the arithmetic mean of that week's logged
   days, and render a horizontal bar whose **width is proportional to the
   score (0–5)** and whose color shifts from red (low) through yellow to
   green (high). Weeks with no entries show an empty/grey bar and a "—".
8. Each weekly row also displays the week's date range (e.g. "Oct 5–11") and
   the numeric average rounded to one decimal (e.g. `3.7`).
9. The current displayed month updates the weekly strip immediately whenever
   a mood is added, changed, or cleared — no page reload needed.
10. **Sign-off:** the page must display, somewhere easy to spot (e.g. a
    footer), the date and time the solution was produced and the model/author
    that produced it (e.g. `Built 2026-10-29 14:32 by <model-name>`).

## Constraints

- One file only: `mood-calendar.html`. Everything (markup, styles, logic)
  lives inside it.
- Standard browser APIs only — no CDNs, no npm, no build step, no external
  fonts or images.
- Storage: `localStorage` exclusively. No servers, no fetch calls, no
  third-party APIs.
- Must work when opened directly from disk (`file://`) in a current Chrome,
  Edge, or Firefox.
- The date key format in `localStorage` must be `YYYY-MM-DD`; values are the
  emoji character.

## Sample Data / Inputs

Mood scale used for averaging:

| Emoji | Meaning | Score |
|-------|---------|-------|
| 😄    | great   | 5     |
| 😴    | rested  | 4     |
| 😐    | meh     | 3     |
| 😡    | angry   | 2     |
| 😢    | bad     | 1     |

Example week average: a week with `😄 😐 😢` logged on three days →
(5 + 3 + 1) / 3 = `3.0` → bar at 60% width, yellow-ish.

Example `localStorage` content after logging Oct 1 = great, Oct 2 = tired:

```json
{ "2026-10-01": "😄", "2026-10-02": "😴" }
```

## Deliverable

- `mood-calendar.html` — the complete app.
- Run: open `mood-calendar.html` in any modern browser (double-click it, or
  `File → Open`). No server, no install.

## Done When

- [ ] Opening the file shows the current month as a correctly aligned
      weekday grid with the month/year title.
- [ ] Clicking a past or today's cell shows the 5-emoji picker; choosing an
      emoji stamps it into the cell; future dates are not loggable.
- [ ] Reloading the page keeps all stamped emojis in place.
- [ ] Navigating to the previous and next month renders correct grids, and
      entries made there persist when navigating back.
- [ ] The weekly strip shows one row per calendar week of the visible month,
      with date range, colored proportional bar, and 1-decimal average;
      empty weeks show "—".
- [ ] Changing or clearing a mood updates that week's bar and number
      immediately without reload.
- [ ] A visible footer/sign-off shows the production date-time and the
      model/author name.

## Stretch Goals (optional)

- Show a "current streak" counter: consecutive days (ending today or
  yesterday) with any mood logged.
- Add a compact year overview: 12 mini-month grids colored by each month's
  average score.
- Add an "Export JSON" button that downloads the full `localStorage` mood
  map as a `.json` file.
