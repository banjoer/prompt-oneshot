# FlowBoard Kanban

**Difficulty:** Medium  |  **Stack:** HTML/CSS/JS (vanilla, single file)  |  **Estimated time:** 1–3 hours

## The Problem

Personal task trackers fail in two directions: sticky notes scatter and get lost, while hosted boards demand accounts, internet, and a subscription nudge. What many people actually need is a tiny, private kanban that lives in one file on their own machine — three lanes, cards you can grab and move with the mouse, and state that survives a browser restart with zero setup. Build that board: a fully local, single-file kanban with native HTML5 drag-and-drop, full card management, and `localStorage` persistence.

## Requirements

1. Deliver a single self-contained `flowboard.html` file using only vanilla HTML/CSS/JS — all markup, styles, and logic inside it. It must work when opened directly from disk (`file://`) in a modern browser; no server needed.
2. Render a three-column board with fixed lanes, left to right: **To Do**, **In Progress**, **Done**. Each column header shows the lane name plus a live count badge of the cards it currently holds. All three columns are visible side by side at desktop widths.
3. **Add a card:** each column has an "add" control (input + button or an inline composer). Submitting a non-empty title creates a card at the end of that column. Empty or whitespace-only titles are rejected — no card created, no error thrown. Cards have at least a title; an optional short note field is allowed.
4. **HTML5 drag-and-drop:** cards are draggable using the native Drag and Drop API (`draggable`, `dragstart`, `dragover`, `drop`, …). Dragging a card from one column and dropping it into another moves it there. The dragged card is visually distinct while dragging (e.g. reduced opacity or slight rotation), and the column currently under the pointer is highlighted as a drop target.
5. **Reorder within a column:** dropping a card at a specific position inside a column inserts it there — before or after the card under the pointer, based on the pointer's position within that card's box — not just appended at the end. A visible insertion indicator (gap line or placeholder) shows where the card will land during the drag.
6. **Edit a card:** each card exposes an edit affordance (double-click or an edit button) that turns the title (and note, if present) into editable fields with save and cancel. Saving applies the trimmed text; cancelling restores the previous text untouched. Saving an empty title never stores an empty title — keep the old one.
7. **Delete a card:** each card has a delete control that removes it after a lightweight confirmation (native `confirm()` is acceptable).
8. **Persistence:** every change (add, move, reorder, edit, delete) is saved immediately to `localStorage` as one JSON document under a single key (e.g. `flowboard.v1`), preserving card order within each column. Reloading the page restores the exact board: same columns, same cards, same order.
9. **First-run seed:** only when no saved state exists, the board pre-loads the sample cards from Sample Data below so the app is demonstrably alive on first open. Once any board state has been saved, the seed never reappears — even after the user deletes every card.
10. **Robust rendering:** card text is inserted via `textContent`/DOM nodes or properly escaped — a card titled `<script>alert(1)</script>` must render as literal text, never execute. Empty columns show a subtle "drop cards here" placeholder. If the stored JSON is corrupt or unparseable, the app falls back to the seed board instead of crashing, and overwrites the bad value on the next save.
11. **Sign-off:** the page must display, somewhere easy to spot (e.g. a footer), the date and time the solution was produced and the model/author that produced it (e.g. `Built 2026-10-29 14:32 by <model-name>`), plus a matching header comment at the top of the file.

## Constraints

- One file only: `flowboard.html`. No external CSS/JS files, no CDNs, no frameworks, no web fonts or images, no build step.
- Standard browser APIs only: Drag and Drop API, DOM, `localStorage`, `JSON`. No network calls of any kind (`fetch`, XHR, beacons).
- Storage is `localStorage` exclusively — no IndexedDB, no cookies, no backend.
- Must run by double-clicking the file (`file://` protocol) in a current Chrome/Firefox/Edge/Safari. No dev server, no install.
- Stay responsive with ~100 cards total on the board; no pagination or virtualization is required.

## Sample Data / Inputs

First-run seed board (titles only; notes optional):

- **To Do:** "Sketch onboarding wireframes", "Renew library books", "Plan weekly grocery run"
- **In Progress:** "Write project status update", "Fix leaky kitchen tap"
- **Done:** "Book dentist appointment"

Suggested storage shape (implementation may vary, but card order must round-trip):

```json
{
  "columns": {
    "todo": [
      { "id": "c1", "title": "Sketch onboarding wireframes", "note": "" }
    ],
    "inprogress": [],
    "done": []
  }
}
```

## Deliverable

- One file: `flowboard.html`
- Run: open `flowboard.html` in any modern browser (double-click it, or `File → Open`). No install, no server.

## Done When

- [ ] The page opens from `file://` and shows three labelled columns with count badges and the seed cards on first run.
- [ ] Adding a card to any column appends it there, updates the count, and survives a reload; blank titles create nothing.
- [ ] A card can be dragged with the mouse from one column into another and lands there; source and target count badges update immediately.
- [ ] Dropping a card between two cards in the same column inserts it exactly there (with visible insertion feedback during the drag), and the new order survives a reload.
- [ ] Editing a card and saving changes its text after reload; cancelling leaves it unchanged; a title of `<script>alert(1)</script>` displays as plain text.
- [ ] Deleting a card removes it (after confirmation) and it stays gone after reload.
- [ ] Deleting every card, then reloading, shows an empty board — the seed does not return.
- [ ] Corrupting the `localStorage` value by hand (e.g. setting it to `garbage`) and reloading restores a working board instead of a blank or broken page.
- [ ] The sign-off (date/time produced + model/author) is visible on the page and in a source header comment.

## Stretch Goals (optional)

- WIP limit on **In Progress**: a configurable cap (e.g. 3); drops beyond the cap are refused with a brief visual shake or message.
- Export/Import buttons that download the board as a JSON file and restore it from one.
- Keyboard power-move: with a card focused, `Ctrl+←` / `Ctrl+→` moves it between columns.
- Optional due-date field on cards; overdue cards get a red tint in any column except **Done**.
