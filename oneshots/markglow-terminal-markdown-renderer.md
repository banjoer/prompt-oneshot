# MarkGlow

**Difficulty:** medium  |  **Stack:** Node.js (stdlib only)  |  **Estimated time:** 1–3 h

## The Problem

You live in the terminal, but half the project docs, changelogs, and READMEs you need are Markdown. `cat` dumps raw `#` and `**` noise; opening a browser for a 40-line note is overkill. What you want is a tiny renderer that turns a Markdown file into styled terminal output — colored headings, real bold and italic, tidy lists, shaded code blocks, quoted callouts — using nothing but ANSI escape codes. Build that renderer as a single self-contained Node.js script that works out of the box on an embedded sample document.

## Requirements

1. Produce a single file `markglow.js`. Running `node markglow.js` renders an embedded sample document (the Markdown from the Sample Data section, stored in the source as a template-literal constant `SAMPLE_MD`); running `node markglow.js somefile.md` reads that file as UTF-8 and renders it instead.
2. Always emit ANSI escape codes, even when output is piped (no TTY detection). End every styled run with a full reset `\x1b[0m` — never partial resets.
3. Headings: a line matching `^(#{1,6})\s+(.*)$` is a heading. Render H1 uppercased in SGR `1;36` (bold cyan), H2 in `1;33` (bold yellow), H3–H6 in `1;35` (bold magenta). A `#` with no following space (`#nope`) is ordinary paragraph text.
4. Paragraphs: consecutive non-blank, non-special lines join into one line with single spaces, then inline styling (requirement 5) is applied.
5. Inline styling, applied in this exact precedence order: (a) code spans `` `...` `` → content rendered literally in inverse video `\x1b[7m`, with no other markers processed inside; (b) bold `**text**` → `\x1b[1m` (bold *may* contain italic or code spans); (c) italic `*text*` → `\x1b[3m` (italic contains plain text only); (d) links `[text](url)` → `\x1b[4mtext\x1b[0m` + a space + `\x1b[90m(url)\x1b[0m`, with no styling inside the link text. A marker with no matching closer on the same line, or an empty marker pair, stays literal.
6. Lists: lines matching `^(\s*)([-*+]|\d+[.)])\s+(.*)$`. Every 2 leading spaces = 1 nesting level; render 2 spaces of indent per level. Unordered items render their marker as a cyan bullet `\x1b[36m•\x1b[0m`; ordered items render as `\x1b[36mN.\x1b[0m`, renumbered 1, 2, 3… within each contiguous ordered run at the same level (source numbers are ignored). Inline styling applies to item text.
7. Blockquotes: consecutive lines starting with `>` (optionally followed by one space) render as `\x1b[90m▌\x1b[0m ` + the inline-styled content, one output line per source line.
8. Fenced code blocks: a line starting with exactly three backticks (optional language letters after them) opens a block; every line until the closing fence is printed verbatim as two spaces + `\x1b[7m` + the line + `\x1b[0m` — no inline processing inside, and fence/language lines themselves print nothing. An unclosed fence consumes the rest of the file as code.
9. Horizontal rules: a line that is exactly `---`, `***`, or `___` renders as `\x1b[90m` + 40 `─` characters + reset.
10. Layout: blocks are separated by exactly one blank line, with no blank line before the first block.
11. Robustness: a missing/unreadable file argument prints one clear error line (including the file name) to **stderr** and exits with code 1 — never a stack trace. Empty input renders just the footer.
12. **Sign-off:** the final output block must be a dim footer line — `\x1b[2m` + `— Rendered by <model/author> on <YYYY-MM-DD HH:MM> —` + reset — showing the date and time the solution was produced and the model/author that produced it; also include the same information as a header comment in the source.

## Constraints

- Node.js 16+, standard library only (`fs` and `process` are enough). No npm packages, no `package.json`, no build step.
- No network access. Do not read or write any file other than the optional Markdown path given as a command-line argument.
- The embedded sample must live inside the source as a constant — the script must run with zero arguments and no external files present.
- Colors are always on (deterministic output), and all structure must come from actually parsing the input — never hardcode rendered lines of the sample.
- Handle the edge cases named in the requirements: `#` without a space, unmatched/empty inline markers, an unclosed code fence, and ordered lists whose source numbers are out of order.

## Sample Data / Inputs

Embedded sample — use exactly this as `SAMPLE_MD` (one page of coastal field notes):

````markdown
# Saltmarsh Field Notes

## Morning Survey

The tide gauge read **1.8 meters** at dawn — the *highest* this month.
Wind held steady from the northwest, and the `anemometer` logged gusts
near [the station log](station-2026-10.log).

### Species Spotted

- Saltmarsh sparrow, two adults
- Marsh periwinkle (*too many to count*)
  - dense cluster under the boardwalk
- One very calm heron

## Afternoon Tasks

5. Refill the freshwater trap
9. Replace battery in logger `TM-04`
1. Photograph the cordgrass plots

> The marsh keeps its own ledger.
> Every creek is an entry, every tide a signature.

---

## Appendix: Raw Readings

```json
{"station": "north-2", "temp_c": 14.2, "note": "**raw** *unstyled*"}
{"station": "south-1", "temp_c": 15.0, "note": "battery *low*"}
```

An unmatched marker stays literal: *oops.
````

Expected shape of the first blocks when piped through `cat -v` (so `^[` is the ESC byte; every value and structure must come from parsing, never hardcoding):

```text
^[[1;36mSALTMARSH FIELD NOTES^[[0m

^[[1;33mMorning Survey^[[0m

The tide gauge read ^[[1m1.8 meters^[[0m at dawn — the ^[[3mhighest^[[0m this month. Wind held steady from the northwest, and the ^[[7manemometer^[[0m logged gusts near ^[[4mthe station log^[[0m ^[[90m(station-2026-10.log)^[[0m.
```

## Deliverable

- One file: `markglow.js`
- Run commands:
  - `node markglow.js` — renders the embedded sample document
  - `node markglow.js notes.md` — renders any other Markdown file
  - `node markglow.js | cat -v` — reveals the raw escape sequences for verification

## Done When

- [ ] `node markglow.js` runs with no arguments and renders the full embedded sample without errors.
- [ ] The first output line is exactly `^[[1;36mSALTMARSH FIELD NOTES^[[0m` (via `cat -v`); `Morning Survey` is wrapped in `^[[1;33m…^[[0m` and `Species Spotted` in `^[[1;35m…^[[0m`.
- [ ] The three source lines of the first paragraph render as ONE line containing `^[[1m1.8 meters^[[0m`, `^[[3mhighest^[[0m`, `^[[7manemometer^[[0m`, and the link `^[[4mthe station log^[[0m ^[[90m(station-2026-10.log)^[[0m`.
- [ ] The unordered list shows cyan `•` bullets; the nested item `dense cluster under the boardwalk` is indented 2 spaces; the periwinkle line contains `^[[3mtoo many to count^[[0m`.
- [ ] The task list (source numbers 5, 9, 1) renders renumbered `1.` `2.` `3.` in cyan, and `TM-04` appears in inverse video.
- [ ] Both blockquote lines begin with `^[[90m▌^[[0m `, and the `---` renders as a gray line of 40 `─` characters.
- [ ] Both JSON lines render indented 2 spaces in inverse video with their `**raw**` and `*low*` markers left literal (no `^[[1m` or `^[[3m` inside the code block).
- [ ] The final line is the dim footer (`^[[2m— Rendered by …`) and the source carries the same sign-off as a header comment.
- [ ] `node markglow.js missing.md` prints one clean stderr line and exits with code 1 (no stack trace).

## Stretch Goals (optional)

- Add a `--no-color` flag that strips all SGR codes (plain structural output: `#` headings, `-` bullets, indented quotes).
- Wrap paragraphs, list items, and blockquotes to `process.stdout.columns` (default 80), keeping styles intact across wrapped lines.
- Render pipe tables (`| a | b |`) as aligned box-drawn tables with a header separator row.
