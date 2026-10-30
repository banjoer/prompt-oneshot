# Kanban Board with Drag & Drop

**Difficulty:** Hard  |  **Stack:** HTML/CSS/JS (single file)  |  **Estimated time:** 3–8 h

## The Problem

Personal task management lives in an awkward gap: sticky notes and text files have no structure, while hosted boards demand accounts, connectivity, and per-seat pricing for what is fundamentally a private list of cards in columns. What a solo user or small team often needs is a private board that opens instantly from disk — custom columns, prioritized cards with due dates, full mouse drag-and-drop, instant search and filtering, and state that survives restarts with zero backend. Build that board as a single dark, glassy HTML file: flexible columns, rich cards, native HTML5 drag-and-drop, live search/filter, a stats bar, and whole-board `localStorage` persistence.

## Requirements

1. Deliver a single self-contained `kanban.html` file using only vanilla HTML/CSS/JS. It must work when opened directly from disk (`file://`) in a modern browser; no server, no network, no external fonts or assets — use a system font stack only.
2. Render **four default columns** left to right — **Backlog**, **To Do**, **In Progress**, **Done** — each showing its name plus a live card-count badge. Provide an "＋ Add Column" control at the end of the board that appends a custom column with a user-supplied non-blank name; blank names are rejected silently.
3. Support column **rename** by double-clicking the header, which swaps the title for an inline input (Enter/blur saves the trimmed non-empty name, Escape cancels); and column **delete** via a trash affordance visible on hover/focus, which succeeds only when the column is empty — attempting to delete a non-empty column is refused with a brief inline message or shake, never data loss.
4. Each card has a required non-blank **title** and optional **description** shown as a collapsible detail below the title (collapsed by default, expandable per card); a **priority badge** (Low = green, Medium = amber, High = red pill); an optional **due date** (`<input type="date">`) that renders red with a ⚠️ icon when overdue (due date before today); and a **delete button** revealed on card hover/focus that removes the card with a short fade-out animation.
5. Add cards via an inline mini-form at the bottom of each column ("＋ Add card" reveals title input + priority selector + due-date picker + optional description textarea + Save/Cancel). Never use `prompt()`, `alert()` for input, or any modal. Saving with a blank title creates nothing; Save persists the card, Cancel discards the form untouched.
6. Implement card movement with the **native HTML5 Drag and Drop API** (`draggable`, `dragstart`, `dragover`, `drop`, etc. — no libraries): any card can be dragged into any column at any position, with a visible drop-zone highlight on the column under the pointer (e.g. glowing outline or pulse) and an insertion indicator (gap line/placeholder) showing the exact landing position from the pointer's offset within the card under it. The dragged card renders distinctly (reduced opacity/ghost).
7. Cards landing in (or rendered in) the **Done** column automatically get a completed style: muted colors plus strikethrough title; moving a card out of Done removes that style immediately.
8. Provide a top **search bar** that filters cards in real time, case-insensitively, against card titles (and descriptions if present); and a **priority filter** dropdown (`All`, `Low`, `Medium`, `High`) that hides non-matching cards while leaving a placeholder gap so column heights don't jump. Search and filter combine (AND) and apply across all columns; clearing both restores every card.
9. Persist the **entire board** (columns in order, cards in order with all fields) to `localStorage` as one JSON document under a single key (e.g. `kanban.v1`) after every mutation (add/move/reorder/edit/rename/delete/filter-independent changes). Reloading restores the exact board. Only when no saved state exists, seed the board with the sample cards below; once any state has been saved the seed never returns, even if the user deletes every card and column down to nothing.
10. Render a **fixed bottom stats bar** with four live values recomputed on every change: total cards, overdue cards (due date < today, counting cards in any column including Done or excluding Done — state the choice in a comment), cards in Done, and completion rate `Done / Total × 100%` (show `—` or `0%` when Total is 0, never `NaN`).
11. Apply the dark theme: page background near `#0f1117`, columns as semi-transparent frosted-glass panels (CSS `backdrop-filter`/translucency, subtle border + shadow — CSS only), pill priority badges, hover-lift on cards, and horizontal board scrolling on narrow screens with no broken overlap. Card/user text is inserted via `textContent`/DOM nodes or escaped — a title of `<img src=x onerror=alert(1)>` renders as literal text and never executes. Corrupt stored JSON falls back to the seed board instead of crashing and is overwritten on the next save.
12. **Sign-off:** the page must display, somewhere easy to spot (e.g. a footer), the date and time the solution was produced and the model/author that produced it (e.g. `Built 2026-10-30 09:15 by <model-name>`), plus a matching header comment at the top of the file.

## Constraints

- One file only: `kanban.html`. No external CSS/JS files, no CDNs, no frameworks, no web fonts (system stack like `-apple-system, "Segoe UI", Roboto, sans-serif`), no images, no build step.
- Standard browser APIs only: Drag and Drop API, DOM, `localStorage`, `JSON`, `Date`. No network calls of any kind (`fetch`, XHR, beacons, web fonts).
- Storage is `localStorage` exclusively — no IndexedDB, no cookies, no backend.
- Must run by double-clicking the file (`file://` protocol) in a current Chrome/Firefox/Edge/Safari, fully offline. No dev server, no install.
- Must stay usable with ~200 cards total; no pagination or virtualization required. This board differs from fixed-3-lane boards: columns are user-extensible (add/rename/delete) and cards carry priority + due-date + filters + a stats bar.

## Sample Data / Inputs

First-run seed (only when no saved state exists):

```json
{
  "columns": [
    { "id": "col-backlog", "title": "Backlog",
      "cards": [
        { "id": "c1", "title": "Research offline-first sync", "description": "Compare CRDT vs last-write-wins.", "priority": "Medium", "due": "2026-11-07" },
        { "id": "c2", "title": "Renew gym membership", "description": "", "priority": "Low", "due": "" }
      ] },
    { "id": "col-todo", "title": "To Do",
      "cards": [
        { "id": "c3", "title": "Pay electricity bill", "description": "Overdue test card.", "priority": "High", "due": "2026-10-20" }
      ] },
    { "id": "col-progress", "title": "In Progress",
      "cards": [
        { "id": "c4", "title": "Draft launch announcement", "description": "Keep under 200 words.", "priority": "Medium", "due": "2026-11-01" }
      ] },
    { "id": "col-done", "title": "Done",
      "cards": [
        { "id": "c5", "title": "Book dentist appointment", "description": "", "priority": "Low", "due": "2026-10-28" }
      ] }
  ]
}
```

Expected stats-bar reading on fresh seed: Total 5 · Overdue ≥ 1 (card c3) · Done 1 · Completion 20%.

## Deliverable

- One file: `kanban.html`
- Run: open `kanban.html` in any modern browser (double-click it, or `File → Open`). No install, no server. Disconnect from the network to verify self-containment.

## Done When

- [ ] The page opens from `file://` fully offline with the four default columns, count badges, and the seed cards; no console errors and no network requests.
- [ ] "＋ Add Column" appends a custom column with a typed name (blank rejected); double-click rename saves on Enter and cancels on Escape; deleting a non-empty column is refused while deleting an emptied column succeeds.
- [ ] Adding a card via the inline mini-form (no `prompt()`) with priority + due date + description appears in the right column; blank titles create nothing; Cancel discards cleanly.
- [ ] Any card drags via native HTML5 DnD into any column with a visible drop-zone highlight and insertion indicator, lands at the indicated position, and the new order survives a reload.
- [ ] Cards in Done show muted + strikethrough styling that clears when dragged out; overdue cards show a red date with ⚠️; deleting a card fades it out and it stays gone after reload.
- [ ] Search filters titles live and case-insensitively, the priority dropdown hides non-matches leaving placeholder gaps, both combine, and clearing both restores all cards.
- [ ] Every mutation persists: reload restores columns, cards, order, and edits exactly; deleting everything then reloading shows an empty board (seed does not return).
- [ ] The bottom stats bar shows correct live Total / Overdue / Done / Completion % (20% on the fresh seed) and never shows `NaN`.
- [ ] A card titled `<img src=x onerror=alert(1)>` renders as inert text; hand-corrupting the `localStorage` key to `garbage` and reloading restores a working board.
- [ ] Narrowing the window to ~360 px keeps columns usable via horizontal scroll with no overlap; the sign-off (date/time + model/author) is visible on the page and in a source header comment.

## Stretch Goals (optional)

- Inline card editing (title/description/priority/due via the same mini-form in edit mode) with Save/Cancel.
- Export/Import buttons that download the board as JSON and restore it from a file input.
- WIP limit on In Progress (configurable cap; drops beyond it refused with a shake) plus per-column collapse toggles.
