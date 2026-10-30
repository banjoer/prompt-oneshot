# File Listing — Local File Inventory Studio

**Difficulty:** Extreme  |  **Stack:** Python (Tkinter, stdlib only)  |  **Estimated time:** 8+ hours

## The Problem

Photographers, archivists, lawyers, and researchers all hit the same wall: a folder with thousands of files and no trustworthy manifest of what is actually there. OS file browsers show names and sizes but cannot filter by media type, annotate files with comments and tags, compute integrity hashes on demand, or export a clean CSV manifest that reflects exactly what was reviewed. Build that tool: a calm, utilitarian desktop app that scans a local folder into a sortable, filterable, editable table, computes hashes only when asked, and exports exactly what the user sees to CSV.

## Requirements

1. Deliver a single self-contained `filelist.py` using only the Python standard library (`tkinter`/`ttk`, `filedialog`, `os`, `threading`, `queue`, `hashlib`, `csv`, `datetime`, …). It must run with `python3 filelist.py` on Python 3.10+ with no install step and no third-party packages.
2. The first and only screen is the working application — no landing page. Layout, top to bottom: a top toolbar (folder-pick button, path entry with paste support, `Include subfolders` checkbutton, `Calculate hashes` button, `Export CSV` button), a filters row (type selector, custom-extension entry, name/path search entries), the results table, a column-visibility panel or dropdown, and a status bar (state, file count, errors, progress).
3. **Folder selection:** a `Choose folder…` button opens a native directory dialog (`filedialog.askdirectory`). A path entry beside it accepts a pasted or typed path plus an explicit `Scan`/`Load` action, so drag-and-drop equivalents (copy-paste of a path) work without any web view. An `Include subfolders` toggle controls recursive traversal (off = top level only, on = `os.walk`).
4. **Visible scan states:** the status bar always shows one of `idle`, `scanning`, `completed`, or `error`, plus a live count of records found and a short message for the last error or stage (e.g. `scanning… 412 files`, `completed: 1,204 records`, `error: folder not readable`). Starting with no folder selected shows the idle state, never a traceback.
5. **Non-blocking scan:** directory traversal runs on a worker thread feeding results back through a `queue.Queue` (or equivalent) with `after()` polling; the window, filters, and table stay responsive while scanning a large tree. Per-file access errors (permission denied, broken symlink, file vanishing mid-scan) are recorded in the error count and status message and never crash the scan or the app.
6. **Collected metadata:** each row stores `name`, `date modified`, `date created` (empty string when the platform does not provide it — state this in a header comment and in an About/help line), `kind`/extension (lowercased, `"<dir>"` or `"<no-ext>"` where applicable), `size` in bytes (blank for directories), full `path`, plus user-editable `comments`, `tags`, and `title` (all empty at scan time). No `md5`/`sha256` value is computed during the initial scan — those columns start empty by design.
7. **Hash calculation by button:** a `Calculate hashes` button computes `md5` and `sha256` with `hashlib` in streaming chunks (e.g. 64 KiB) only after an explicit click. If table rows are selected, hash exactly the selected files; if nothing is selected, hash the currently filtered file list. Folders keep empty hash values. A progress indication (status text and/or `ttk.Progressbar`) shows `hashing i/n`, per-file read errors appear in the status area, and one bad file never aborts the rest.
8. **Filters:** a type selector with `All`, `Images` (`.png .jpg .jpeg .gif .bmp .webp .tiff .svg`), `Video` (`.mp4 .mov .avi .mkv .webm`), `Audio` (`.mp3 .wav .flac .ogg .m4a`), `PDF` (`.pdf`), and `Custom` (with a text entry such as `.txt,.zip`); plus two search entries filtering by file name substring and by full-path substring (case-insensitive). Filters combine with AND logic and apply instantly to the table without rescanning.
9. **Preview table:** results render in a `ttk.Treeview` with column headings for `File name`, `Date modified`, `Date created`, `Kind`, `Size`, `Path`, `Comments`, `Tags`, `Title`, `md5`, `sha256`. The table supports clicking a heading to sort ascending/descending by at least name, size, and modification date; multi-row selection (`extended` mode) for hash calculation; a column show/hide panel that can toggle every column; a live `N records` count; a distinct empty state when no folder has been scanned yet (`No files scanned yet — choose a folder above`); and a distinct empty state when filters match nothing (`No files match the current filters`). Filenames are displayed safely (no markup interpretation) and directories are visually distinguishable (e.g. a `📁` prefix or a kind label), never by color alone.
10. **Inline editing:** the user-editable fields `file name` (rename affordance — renaming the display value; a full on-disk rename is acceptable if confirmed and error-handled, otherwise the edit applies to the in-memory record and the export), `comments`, `tags`, and `title` are editable in place (double-click a cell, or select a row and press a clearly labelled `Edit` control, with Save/Cancel). Saving writes the trimmed text back to the in-memory record; cancelling leaves it untouched. All other columns are read-only.
11. **CSV export:** an `Export CSV…` button opens a native save dialog (`filedialog.asksaveasfilename`, default extension `.csv`). The export writes exactly the currently visible columns, in their current display order, for exactly the currently filtered rows, including all user edits; `md5`/`sha256` cells are filled only where hashes were actually calculated, otherwise empty. The writer uses the `csv` module with proper quoting of commas, quotes, and line breaks, UTF-8 encoding, and a header row. Cancelling the dialog writes nothing and raises no error.
12. **Corrupt-input handling:** pasting a nonexistent path, picking an unreadable folder, or pointing the app at a file instead of a folder shows the `error` state with a plain-language message and leaves the previous table (if any) intact. The app never shows an unhandled exception dialog for these cases.
13. **Sign-off:** the finished solution must display, somewhere easy to spot, the date and time it was produced and the model/author that produced it — both as a header comment at the top of `filelist.py` and as a visible line in the app (e.g. a status-bar suffix or an About label).

## Constraints

- One file only: `filelist.py`. Python standard library only — `tkinter`/`ttk` for UI, `os`/`pathlib`, `threading`/`queue`, `hashlib`, `csv`, `datetime`. No pip packages, no web views, no subprocess tools.
- Local only: no network calls, no telemetry, no server backend. Reading file bytes is allowed solely for on-demand hash calculation.
- Chunked hashing (fixed-size block reads); never load a whole file into memory to hash it.
- Timestamps display in a consistent sortable format (e.g. `YYYY-MM-DD HH:MM:SS`); sizes display as exact bytes in the data model (human-readable formatting in the cell is allowed only if sorting still uses the byte value).
- Must remain responsive while scanning folders with 10,000+ entries; no full-tree pre-materialization on the UI thread.

## Sample Data / Inputs

Example folder tree the app must handle (create locally to test):

```
photos/
  beach.jpg        (images filter, ~2.1 MB)
  notes.txt        (custom `.txt` filter)
  archive.zip
  sub/
    clip.mp4       (video filter, only listed when Include subfolders is ON)
    paper.pdf      (PDF filter)
    song.mp3       (audio filter)
```

Expected CSV snippet after scanning `photos/` with `Include subfolders` ON, hiding every column except three, editing the title of `beach.jpg`, and hashing only that row:

```csv
File name,Title,sha256
beach.jpg,"Summer, ""golden"" trip",9f2c…(64 hex chars)
notes.txt,,
clip.mp4,,
paper.pdf,,
song.mp3,,
archive.zip,,
```

Note the quoting: the title contains both a comma and quotes, so it must be wrapped in double quotes with inner quotes doubled. Only `beach.jpg` carries a hash because only it was selected when `Calculate hashes` was pressed.

## Deliverable

- One file: `filelist.py`
- Run: `python3 filelist.py` (opens the desktop window; no install, no arguments required)

## Done When

- [ ] `python3 filelist.py` opens the working app as the first screen with toolbar, filters, table, column panel, and status bar, with no console errors.
- [ ] Choosing a folder via the system dialog scans it and lists its files; the status line moves through `scanning` to `completed` with a correct record count, and the UI never freezes during the scan.
- [ ] Toggling `Include subfolders` off/on and rescanning excludes/includes nested files (e.g. `sub/clip.mp4` appears only when ON).
- [ ] No `md5`/`sha256` value exists immediately after a scan; pressing `Calculate hashes` with rows selected hashes only those files (folders stay empty), and with nothing selected hashes the filtered list, with visible progress and per-file errors that do not abort the run.
- [ ] Each type filter (images/video/audio/PDF/custom `.txt`) narrows the table correctly, and name + path search combine with the type filter; an impossible filter shows the no-results empty state, distinct from the pre-scan empty state.
- [ ] Clicking the Name, Size, and Date-modified headings toggles ascending/descending sort correctly (sizes sort numerically, not alphabetically).
- [ ] Hiding a column removes it from both the table and the exported CSV; the record count label matches the filtered rows.
- [ ] Editing `comments`, `tags`, or `title` on a row and then exporting produces a CSV containing the edited text, with commas/quotes/newlines correctly quoted and the file readable as UTF- 8.
- [ ] Pasting a nonexistent path shows the `error` state with a plain message and no traceback, keeping prior results intact.
- [ ] The sign-off (date/time produced + model/author) appears both as a header comment and visibly in the app.

## Stretch Goals (optional)

- Cancel buttons for an in-flight scan and for an in-flight hash run, leaving partial results intact.
- Persist the user's column visibility/order to a local JSON file (e.g. `~/.filelist-columns.json`) and restore it on launch.
- Thumbnail strip or tooltip preview for selected image files (still stdlib-only, via `tkinter.PhotoImage` for supported formats).
