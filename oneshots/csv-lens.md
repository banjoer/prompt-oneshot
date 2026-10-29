# CSV Lens

**Difficulty:** medium  |  **Stack:** HTML/CSS/JS (vanilla, single file)  |  **Estimated time:** 1.5–3 h

## The Problem

A CSV export lands in your inbox — survey results, a sensor dump, a book-catalog backup — and you just want to *look* at it. Opening a spreadsheet is heavy, pasting it into an online viewer means uploading your data to a stranger, and `cat` gives you an unreadable wall of commas. What you need is a single HTML file you keep forever: double-click it, feed it any CSV, and get a sortable, paginated table plus an instant visual profile of every numeric column. No server, no install, no upload — the file is the app. Build that viewer.

## Requirements

1. Produce a single file `csv-lens.html` with all CSS in one inline `<style>` element and all JavaScript in one inline `<script>` element. Opening the file directly from disk (double-click, `file://`) in a modern browser must work — no server, no build step, no external requests of any kind.
2. Page structure: a header with the app title `CSV Lens`, a file input (`<input type="file" accept=".csv,text/csv">`), and a `Load sample data` button. Store the CSV from the Sample Data section in the source as a template-literal constant `SAMPLE_CSV`. On startup, automatically load and display the embedded sample; the button reloads it at any time.
3. Write your own CSV parser (no library): the first non-blank line is the header row giving the column names; both LF and CRLF line endings are accepted; blank lines are skipped. Fields may be wrapped in double quotes, in which case they may contain commas, and a doubled quote `""` inside a quoted field decodes to a single `"` character. (Quoted fields will not contain newlines.)
4. Ragged rows: a data row with fewer fields than the header is padded with empty strings; extra fields beyond the header width are dropped. Parsing never throws — malformed input still yields a table.
5. Show a summary line above the table: the source (`embedded sample` or the file name), the data-row count, the column count, and how many columns were detected as numeric. For the embedded sample this must report 30 rows, 5 columns, 3 numeric columns.
6. Render the data as an HTML table with a header row and a leading `#` column showing each row's 1-based position in original file order; the `#` value travels with its row when sorting.
7. Column type detection: a column is numeric if every non-empty cell in it parses as a finite number via `Number()`. Empty cells do not disqualify a column.
8. Sorting: clicking a column header sorts the whole dataset by that column ascending; clicking it again sorts descending; a third click restores original file order. Show `▲` on the ascending column and `▼` on the descending one (no marker in original order). Numeric columns compare as numbers; text columns compare with `localeCompare`. Sorting always jumps back to page 1.
9. Pagination: a page-size `<select>` with options 10, 25, 50 (default 10); `‹ Prev` and `Next ›` buttons; and a status line of the form `Rows A–B of N · Page X of Y`. Buttons are disabled at the first/last page. Changing the page size resets to page 1. With the embedded sample at page size 10 there are exactly 3 pages (rows 1–10, 11–20, 21–30).
10. Column profiles: below the table, render a section titled `Column profiles` containing one horizontal bar chart per numeric column, in column order. Each chart shows the column name, the dataset-wide min and max, and one bar for each row on the *current table page* (the bars re-render whenever the page changes). Each bar is labeled with the row's `#` and its raw value. Fill width = `(value − min) / (max − min) × 100%`, computed against the dataset-wide min and max and rounded to 1 decimal place; if `max === min`, every fill is 100%. Rows whose cell in that column is empty are omitted from that chart.
11. The charts must be pure CSS: ordinary `<div>` elements (a track plus a fill whose width is set as a percentage) styled with CSS. No `<canvas>`, no `<svg>`, no images, and no charting libraries anywhere in the file.
12. Loading a CSV through the file input (FileReader API) replaces the current dataset entirely — summary, table, sort state, pagination, and charts all reset and re-render. If the chosen file cannot be read or yields no usable header, show a clearly visible error banner naming the file and keep the previous dataset on screen.
13. **Sign-off:** the finished page must display, in a visible footer, the date and time the solution was produced and the model/author that produced it; include the same information as a comment at the top of the HTML source.

## Constraints

- Vanilla HTML/CSS/JS only — no frameworks, no libraries, no CDN links, no web fonts, no build tools. Everything lives in the one `.html` file.
- No network access (no `fetch`/XHR). The only file ever read is the user-chosen CSV via the file input. No storage is required; if you persist anything (stretch goals), use `localStorage` only.
- The parser may assume quoted fields contain commas and doubled quotes but never embedded newlines.
- All displayed numbers (counts, min/max, bar widths) must be computed from the parsed data at runtime, never hardcoded.
- Must work when opened straight from disk (`file://`) in a current Firefox or Chrome — do not use anything that requires a server.

## Sample Data / Inputs

Embedded sample — use exactly this as `SAMPLE_CSV` (a 30-book reading-catalog export; note the quoted titles containing commas, and the negative year):

```csv
title,author,year,pages,rating
"Guns, Germs, and Steel",Jared Diamond,1997,480,4.4
The Pragmatic Programmer,David Thomas,1999,352,4.6
"Surely You're Joking, Mr. Feynman!",Richard Feynman,1985,350,4.5
Dune,Frank Herbert,1965,412,4.7
The Left Hand of Darkness,Ursula K. Le Guin,1969,304,4.5
Structure and Interpretation of Computer Programs,Harold Abelson,1984,657,4.8
Neuromancer,William Gibson,1984,271,4.1
The Design of Everyday Things,Don Norman,1988,368,4.4
Snow Crash,Neal Stephenson,1992,440,4.3
A Brief History of Time,Stephen Hawking,1988,256,4.5
The Name of the Rose,Umberto Eco,1980,536,4.3
Gödel Escher Bach,Douglas Hofstadter,1979,777,4.6
The Time Machine,H. G. Wells,1895,118,4.2
Foundation,Isaac Asimov,1951,255,4.5
The Hobbit,J. R. R. Tolkien,1937,310,4.7
Brave New World,Aldous Huxley,1932,268,4.4
1984,George Orwell,1949,328,4.6
The Odyssey,Homer,-800,541,4.3
The Brothers Karamazov,Fyodor Dostoevsky,1880,824,4.6
One Hundred Years of Solitude,Gabriel García Márquez,1967,417,4.5
The Master and Margarita,Mikhail Bulgakov,1967,384,4.6
Crime and Punishment,Fyodor Dostoevsky,1866,671,4.6
The Little Prince,Antoine de Saint-Exupéry,1943,96,4.6
Moby-Dick,Herman Melville,1851,635,4.1
The Catcher in the Rye,J. D. Salinger,1951,234,4.0
To Kill a Mockingbird,Harper Lee,1960,281,4.6
The Great Gatsby,F. Scott Fitzgerald,1925,180,4.4
Jane Eyre,Charlotte Brontë,1847,507,4.5
Wuthering Heights,Emily Brontë,1847,342,4.2
Pride and Prejudice,Jane Austen,1813,432,4.6
```

Key reference values for this dataset (all must be computed by your code, never hardcoded): `year` ranges −800 to 1999, `pages` ranges 96 to 824, `rating` ranges 4.0 to 4.8; `title` and `author` are the only non-numeric columns.

## Deliverable

- One file: `csv-lens.html`
- Run command: none — double-click `csv-lens.html` (or drag it into a browser tab). It must work from `file://` with no server and no installation.

## Done When

- [ ] Opening `csv-lens.html` from disk immediately shows the embedded sample, with a summary reporting 30 rows, 5 columns, and 3 numeric columns (`year`, `pages`, `rating`).
- [ ] `Guns, Germs, and Steel` and `Surely You're Joking, Mr. Feynman!` each render as one single title cell — quoted commas never split a field.
- [ ] Page 1 shows rows 1–10; `Next ›` moves to rows 11–20; page 3 shows rows 21–30 with `Next ›` disabled and a status line reading `Rows 21–30 of 30 · Page 3 of 3`.
- [ ] Clicking the `pages` header sorts the whole dataset ascending (`The Little Prince`, 96 pages, first) and shows `▲`; a second click sorts descending (`The Brothers Karamazov`, 824 pages, first) and shows `▼`; a third click restores original file order. Every sort returns to page 1.
- [ ] The `#` column preserves original file positions after sorting — sorting `year` ascending puts `The Odyssey` (`#` 18, year −800) first.
- [ ] The `Column profiles` section shows exactly three charts (`year`, `pages`, `rating`), each labeled with its dataset-wide min/max, and its bars change when the table page changes.
- [ ] On page 1, the rating chart's bar for `Structure and Interpretation of Computer Programs` (rating 4.8) is completely full; on page 3, `The Catcher in the Rye` (rating 4.0) shows an empty (0%-width) bar.
- [ ] Inspecting any bar in the browser dev tools shows plain `<div>` elements with a percentage width — no `<canvas>` or `<svg>` exists in the page.
- [ ] Loading a different CSV through the file input (try one with CRLF line endings and a ragged row) replaces everything — summary, table, sort state, page 1, and charts — with short rows padded by empty cells and no errors.
- [ ] A visible page footer states the date/time the solution was produced and the model/author, matching the comment at the top of the source.

## Stretch Goals (optional)

- Add a live filter box that narrows rows by matching text across all columns, composing correctly with sorting and pagination (and resetting to page 1).
- Render a subtle in-cell micro-bar behind every numeric cell (same scaling as the column profiles) so values are visible directly in the table.
- Accept a `.csv` file dropped anywhere on the page via drag-and-drop.
