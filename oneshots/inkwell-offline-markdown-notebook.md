# Inkwell — Offline Markdown Notebook

**Difficulty:** hard  |  **Stack:** Vanilla JavaScript (browser, IndexedDB) — single HTML file  |  **Estimated time:** 3–8 h

## The Problem

Every developer ends up with a graveyard of `notes.txt`, `scratch.md`, and "New Text Document (4)" files scattered across the disk, because opening a full notes service means accounts, sync spinners, and someone else's server holding your half-formed ideas. What you actually want is a page on your own machine: type Markdown on the left, see it rendered on the right, find any note instantly, close the tab, and have everything still there tomorrow. No install, no login, no network. Build that notebook: a single HTML file with a hand-rolled Markdown renderer, a live split-pane preview, full note management, instant search, and IndexedDB persistence that survives reloads.

## Requirements

1. Produce **one** self-contained file, `inkwell.html`, containing all markup, CSS, and JavaScript inline. No external files, no CDN scripts or stylesheets, no build step. It must work when opened directly via `file://` as well as when served from a local static server.
2. **Layout.** Three visible regions: a left sidebar (app title "Inkwell", a `+ New note` button, a search input, and the note list below), a center editor pane (a plain `<textarea>`), and a right preview pane showing rendered HTML. A draggable vertical divider between editor and preview lets the user resize the two panes by dragging (pointer events; clamp both panes to a sane minimum width). The sidebar never collapses.
3. **Markdown renderer.** Implement your own renderer as a pure `renderMarkdown(src) → htmlString` function (no libraries) supporting exactly this subset:
   - Headings `# `, `## `, `### ` → `<h1>`, `<h2>`, `<h3>` (space required; four or more `#` is a paragraph).
   - Paragraphs separated by blank lines; single newlines inside a paragraph join with a space.
   - Bold `**text**` → `<strong>`, italic `*text*` → `<em>`, with the *hugging rule*: a delimiter only counts when it directly touches a non-space character on the inside (so `2 * 3` and `a * b` stay literal). Process bold before italic.
   - Inline code `` `text` `` → `<code>`, content verbatim and escaped.
   - Fenced code blocks: lines of three backticks (optionally followed by a language word) open/close a `<pre><code>` block; content is verbatim with no inline formatting; an unclosed fence closes at end of input.
   - Lists: consecutive lines starting with `- ` group into one `<ul>`; consecutive lines matching `N. ` group into one `<ol>`. A blank line or any other line ends the list. No nesting.
   - Blockquotes: consecutive lines starting with `> ` group into one `<blockquote>`.
   - Horizontal rules: a line of exactly three or more `-` characters → `<hr>`.
   - Links `[text](url)` → `<a href="url" target="_blank" rel="noopener">text</a>`; inline formatting applies to link text. URLs must start with `http://`, `https://`, `#`, or `/` — anything else (e.g. a `javascript:` URL) renders as plain unlinked text.
   - Escape **all** literal text: `&`, `<`, `>` in ordinary text and code must come out as entities. There is no raw-HTML passthrough — `<script>alert(1)</script>` typed into a note must display as readable text, never execute.
4. **Live preview.** Re-render the preview as the user types, debounced so rendering happens at most ~150 ms after the last keystroke. The preview always reflects the current editor content.
5. **Note model & storage.** Each note is `{ id, title, body, createdAt, updatedAt }` with `id` from `crypto.randomUUID()` and timestamps as epoch milliseconds. Persist everything in IndexedDB: database `inkwell-db`, object store `notes` with keyPath `id` and an index on `updatedAt`. Wrap the IndexedDB API in promises; all reads/writes go through this layer — nothing is stored in localStorage.
6. **Autosave.** Typing marks the active note dirty and shows a `Saving…` status; after 400 ms of idle time the note is written to IndexedDB, `updatedAt` is bumped, and the status shows `Saved HH:MM:SS`. `Ctrl/Cmd+S` saves immediately (and calls `preventDefault`). Closing or reloading the page after edits loses at most the last 400 ms of typing.
7. **Note list.** Shows every note sorted by `updatedAt` descending, each row displaying its title and its last-saved time (e.g. `14:03`). The active note is visually highlighted. Saving the active note re-sorts the list if its timestamp changed the order.
8. **Create.** `+ New note` creates a note titled `Untitled` (auto-suffix `Untitled 2`, `Untitled 3`, … if that title exists) with a short starter body, makes it active, and focuses the editor.
9. **Rename.** Double-clicking a note's title in the list turns it into an inline text input prefilled with the current title. `Enter` commits, `Escape` cancels, clicking away commits. A trimmed empty title is rejected; a title that case-insensitively duplicates another note's title is rejected with a brief visible error (e.g. red flash or message). A successful rename persists immediately.
10. **Delete.** Each list row shows a delete button (on hover is fine). Deleting asks `confirm()` naming the note's title, removes it from IndexedDB, and activates the nearest remaining note; deleting the last note shows the empty state.
11. **Empty state.** With zero notes, the editor and preview are replaced by a centered panel saying there are no notes yet, with a `Create your first note` button that behaves like `+ New note`.
12. **Search.** The search input filters the note list live on every keystroke, case-insensitively matching a substring against both title and body. Each matching row shows the title plus a one-line snippet: if the query occurs in the body, the snippet is ~40 characters of context on each side of the first body match (ellipses when truncated) with the matched text wrapped in `<mark>`; if only the title matches, the snippet is the first ~80 characters of the body. A counter in the sidebar shows `N notes` normally and `N of M notes` while filtering. A `×` button inside the search field clears the query and restores the full list. The active note stays visible and highlighted if it matches.
13. **Status bar.** A thin bar at the bottom of the editor pane shows the live word count of the active note's body (split on whitespace) and the save status from requirement 6.
14. **First-run seeding.** When the database is empty on first launch, seed it with exactly the three sample notes from the Sample Data section (stored in the source as a constant), so a brand-new user sees a populated app. Never re-seed once the store has been touched.
15. **Graceful degradation.** If IndexedDB is unavailable or throws (e.g. some private-browsing modes), the app must still run fully in-memory and show a persistent visible banner: `Persistence unavailable — notes will not survive a reload`.
16. **Sign-off:** the finished solution must display, somewhere easy to spot, the date and time it was produced and the model/author that produced it — both as a header comment at the top of `inkwell.html` and as a small footer line in the sidebar (e.g. `Built 2026-10-29 14:30 · <model/author>`).

## Constraints

- One file: `inkwell.html`. All CSS and JS inline. No frameworks, no libraries, no imports, no CDN, no webfonts, no build tooling.
- No network access of any kind: no fetch, no external images, no service workers.
- Storage is IndexedDB only (with the in-memory fallback from requirement 15). Do not use localStorage.
- Plain `<textarea>` for editing — no contenteditable, no embedded editor components.
- Everything must work in a current Chrome/Firefox from `file://` and from `http://localhost`.
- All timestamps, counters, snippets, and list ordering must be computed from live data — nothing hardcoded.

## Sample Data / Inputs

Seed notes — use exactly these titles and bodies (timestamps generated at seed time, `updatedAt` staggered so *Welcome to Inkwell* sorts first):

Title: `Welcome to Inkwell`

````markdown
# Welcome to Inkwell

Inkwell is a **local-first** Markdown notebook. Everything you type is saved to your browser's IndexedDB — *no account, no server, no network*.

## Get going

- Press **+ New note** to start a note
- Double-click a title in the sidebar to rename it
- Type in the search box to filter by title or content

Your work autosaves after a moment of idle typing, and `Ctrl/Cmd+S` saves right away.

> Write it down before it evaporates.
````

Title: `Markdown Cheatsheet`

````markdown
# Markdown Cheatsheet

## Inline

**bold** and *italic* and `inline code`. Multiplication like 2 * 3 stays literal, and tags like <div> are shown as text, never rendered.

## Lists

- unordered item
- another one

1. first
2. second

## Code

```js
const fish = "Fish & chips";
console.log(`<div>${fish}</div>`);
```

## Links

A safe link: [MDN web docs](https://developer.mozilla.org). A sketchy one: [click me](javascript:alert(1)) — rendered as plain text.

---

That's the whole subset. Go write something.
````

Title: `Standup Notes 2026-10-29`

````markdown
# Standup 2026-10-29

## Yesterday

- Finished the CSV import retry logic
- Paired with Ana on the search ranking bug

## Today

1. Ship the import fix behind the feature flag
2. Draft the migration runbook
3. Book a review slot for the API proposal

## Blockers

> Still waiting on staging credentials from infra — pinged twice.

Reminder: retro moved to **Friday 15:00**.
````

Suggested manual test flow: reload the page after editing a note (content must survive); search `import` (two notes match, body snippets highlighted); search `fish` (cheatsheet matches); search `zzz` (empty list, counter `0 of 3 notes`); rename a note to an existing title (rejected); delete all notes (empty state appears).

## Deliverable

- One file: `inkwell.html`
- Run either way:
  - Double-click it / `open inkwell.html` (works from `file://`), **or**
  - `python3 -m http.server 8000` in its folder, then visit `http://localhost:8000/inkwell.html`

## Done When

- [ ] Opening `inkwell.html` shows the three seeded notes, *Welcome to Inkwell* selected, its Markdown rendered in the preview (styled HTML, not raw markup).
- [ ] Typing in the editor updates the preview within ~150 ms; the status shows `Saving…` then `Saved HH:MM:SS`, and after a full page reload the edits are still there.
- [ ] In the cheatsheet note: `2 * 3` shows literal asterisks, `<div>` is readable text, the `js` code block renders verbatim and escaped, the `javascript:` link is plain text, and the `---` renders as a horizontal rule.
- [ ] The editor/preview divider drags smoothly and both panes respect a minimum width.
- [ ] `+ New note` creates `Untitled`, then `Untitled 2` after deleting nothing; the new note becomes active with the editor focused.
- [ ] Double-clicking a title renames it inline; empty input and duplicating an existing title are both visibly rejected; `Escape` cancels.
- [ ] Searching `import` narrows the list to two notes with `<mark>`-highlighted body snippets and counter `2 of 3 notes`; clicking `×` restores all three.
- [ ] Deleting a note shows a confirmation naming it, removes it permanently (gone after reload), and deleting the last note shows the empty state panel.
- [ ] The word count in the status bar updates live as you type.
- [ ] With DevTools IndexedDB disabled/unavailable (or in a mode that blocks it), the banner appears and the app still works in-memory.
- [ ] The sidebar footer and the top-of-file comment both show when the solution was produced and by which model/author.

## Stretch Goals (optional)

- Scroll sync: scrolling the editor scrolls the preview proportionally (and vice versa) using scroll-percentage mapping, with no feedback loop.
- Export: an `Export all` button that downloads one JSON file of every note, plus per-note `Copy as Markdown` to the clipboard.
- Multi-term search: treat space-separated terms as AND, highlight every term occurrence in the snippet, and rank title matches above body-only matches.
