# TwinFold — Visual Folder Sync with Conflict Resolution

**Difficulty:** hard  |  **Stack:** Java 11+ (JDK only, Swing)  |  **Estimated time:** 3–8 h

## The Problem

Everyone with a laptop and a desktop (or a USB drive and a project folder) eventually hits the same wall: two copies of a directory tree have drifted apart, and nobody remembers which side is right. Blindly copying newer files over older ones destroys work the day you edited a file on *both* sides; commercial sync tools phone home, want accounts, or cost money. What you actually need is a small local tool that scans both trees, shows you a precise plan of what it *would* do — copy this way, copy that way, delete this, leave those alone — lets you eyeball it in a dry run, and forces you to decide, file by file, when both sides changed. Build that tool: a Swing desktop app that diffs two folders by size, mtime, and content hash, previews the plan in a sortable table, executes it safely, and remembers the last sync so real conflicts are detected next time.

## Requirements

1. Produce a single file `TwinFold.java`. It must compile with `javac TwinFold.java` and run with `java TwinFold` on any JDK 11+ — no build tool, no dependencies. All UI is Swing.
2. The main window is titled `TwinFold` and contains: a top panel with two folder fields (Left, Right), each with a `Browse…` button opening a `JFileChooser` in `DIRECTORIES_ONLY` mode; a `Scan` button and an `Execute` button; a `Dry run` checkbox that starts **checked**; a results `JTable` in the middle; and a non-editable, auto-scrolling log pane (`JTextArea` in a `JScrollPane`) at the bottom.
3. Refuse bad input before scanning, with a `JOptionPane` error dialog: missing/non-directory paths, or two folders where one is nested inside the other.
4. Scanning runs off the EDT (use `SwingWorker`): the window stays responsive, an indeterminate progress bar shows while scanning, and a determinate progress bar advances during Execute. The log pane appends timestamped (`HH:mm:ss`) lines for each phase.
5. The scan walks **both trees recursively** and builds a map of relative path → (size in bytes, last-modified time). Use `/` as the path separator in all display and state output, regardless of platform. Skip symbolic links (log each skipped link). Always exclude the state manifest file itself (requirement 10) from scanning.
6. Classify every relative path found in either tree using exactly these rules, in this order:
   - Present only on the left → `COPY L→R`; only on the right → `COPY R→L`.
   - Present on both with equal size **and** mtimes within a 2-second tolerance → `UNCHANGED` (do **not** hash).
   - Otherwise hash both sides with SHA-256 (`java.security.MessageDigest`, streamed in ≥ 8 KB chunks, never loading whole files into memory). Equal hashes → `UNCHANGED (content match)`.
   - Hashes differ → consult the state manifest from the previous sync (requirement 10):
     - Entry exists and left hash equals the entry but right does not → `COPY L→R` (left changed since last sync).
     - Entry exists and right hash equals the entry but left does not → `COPY R→L`.
     - Anything else (both sides changed since the entry, or no entry exists) → `CONFLICT`.
   - Manifest entry exists but the file is now missing on exactly one side → `DELETE` the surviving side (`DELETE L` or `DELETE R`); missing on both → silently drop the entry.
7. Show the plan in a `JTable` with columns `Path | Status | Action | Left (size · modified) | Right (size · modified) | Resolution`. Sizes are human-readable (`812 B`, `12.4 KB`, `3.1 MB`), times are `yyyy-MM-dd HH:mm:ss`, missing sides show `—`. Rows are ordered: all `CONFLICT`s first, then copies, then deletes, then unchanged; alphabetical by path within each group.
8. Color-code rows with a custom cell renderer: conflicts red, `COPY L→R` green, `COPY R→L` blue, deletes orange, unchanged plain gray text. The colors must be visible without selecting the row.
9. The `Resolution` column is editable **only** on `CONFLICT` rows, via a `JComboBox` cell editor offering `Skip` (the default), `Keep Left`, and `Keep Right`. All other rows show `—` and are not editable.
10. Persist sync state in a file named `.twinfold.state` in the **left** folder root: one line per synced file — `<sha256-hex> <size> <mtimeMillis> <relative-path>`. It is (re)written only after a **non-dry** Execute, and must contain an entry for every file that exists with identical content on both sides after the sync (this is what makes requirement 6's conflict detection work on the next run).
11. Execute behavior:
    - **Dry run checked:** write *nothing at all* — no copies, no deletes, no state file. Log every planned action as `[DRY RUN] COPY L→R  notes/left-only.txt  (26 B)` (and `DELETE`, `SKIP` lines), then a totals line.
    - **Dry run unchecked:** perform each action with `java.nio.file.Files` — copies use `Files.copy(src, dst, REPLACE_EXISTING, COPY_ATTRIBUTES)` creating parent directories as needed; deletes use `Files.delete`. Conflicts still set to `Skip` are left untouched and logged as skipped. Afterwards, write the state manifest (requirement 10). Log each action with its outcome (`OK` / `FAILED: reason`) and end with a summary line.
12. After every scan, log a summary line with computed (never hardcoded) values, e.g. `scanned 5 left / 4 right files in 42 ms — 2 copies, 1 delete, 1 conflict, 2 unchanged`.
13. **Sign-off:** the finished solution must display, somewhere easy to spot, the date and time it was produced and the model/author that produced it — both as a header comment at the top of `TwinFold.java` **and** in an `About TwinFold` dialog reachable from the main window (menu or button).

## Constraints

- Java 11+, JDK standard library only (`javax.swing`, `java.awt`, `java.nio.file`, `java.security`, `java.util.concurrent`/`SwingWorker` are enough). Single `.java` file, no Maven/Gradle, no external libraries, no module system required.
- No network access, no external processes. The only file writes ever allowed are inside the two selected folders, plus the `.twinfold.state` manifest in the left folder.
- Never hash a file whose classification is already decided by size+mtime; never load a whole file into memory to hash it.
- All filesystem work (scan, hash, execute) must run off the EDT; the UI must never freeze.
- Paths in the table, log, and manifest always use `/` separators and are relative to the respective folder root.
- The 2-second mtime tolerance and the rule order in requirement 6 are part of the spec — implement them exactly.

## Sample Data / Inputs

Create a deterministic test fixture with this script (run it in an empty scratch directory; it is also the basis of the *Done When* checks):

```bash
#!/usr/bin/env bash
# TwinFold demo fixture — phase 1
rm -rf demo-left demo-right
mkdir -p demo-left/notes demo-left/pics demo-right/notes demo-right/pics

printf 'identical on both sides\n' > demo-left/notes/same.txt
cp demo-left/notes/same.txt demo-right/notes/same.txt

printf 'only exists on the left\n'  > demo-left/notes/left-only.txt
printf 'only exists on the right\n' > demo-right/notes/right-only.txt

printf 'left version\n'                    > demo-left/shared.txt
printf 'right version - different text\n'  > demo-right/shared.txt

# same content, different size is impossible — so here: same content, different mtime
printf 'content twins\n' > demo-left/pics/readme.txt
printf 'content twins\n' > demo-right/pics/readme.txt

touch -d '2026-01-01 10:00' demo-left/notes/same.txt demo-right/notes/same.txt
touch -d '2026-01-02 10:00' demo-left/shared.txt
touch -d '2026-01-03 10:00' demo-right/shared.txt
touch -d '2026-01-04 10:00' demo-left/pics/readme.txt
touch -d '2026-01-05 10:00' demo-right/pics/readme.txt
```

Expected first scan (no `.twinfold.state` exists yet):

| Path | Status | Action |
|---|---|---|
| `shared.txt` | CONFLICT | unresolved |
| `notes/left-only.txt` | COPY L→R | — |
| `notes/right-only.txt` | COPY R→L | — |
| `notes/same.txt` | UNCHANGED | — |
| `pics/readme.txt` | UNCHANGED (content match) | — |

After a real (non-dry) sync, run this phase-2 script to test manifest-based conflict detection:

```bash
#!/usr/bin/env bash
# TwinFold demo fixture — phase 2 (run AFTER a real sync)
printf 'edited on left after sync\n'  >> demo-left/shared.txt      # left-only change
printf 'left edit\n'  >> demo-left/notes/same.txt                  # both changed...
printf 'right edit\n' >> demo-right/notes/same.txt                 # ...on both sides
rm demo-left/notes/left-only.txt                                   # deleted on left
```

Expected rescan: `shared.txt` → `COPY L→R` (left changed vs manifest), `notes/same.txt` → `CONFLICT` (both changed), `notes/left-only.txt` → `DELETE R`, everything else unchanged.

## Deliverable

- One file: `TwinFold.java`
- Run commands:
  - `javac TwinFold.java` — compile
  - `java TwinFold` — launch the app
- Then: Browse… to `demo-left` and `demo-right`, press `Scan`, review the table, press `Execute` (dry run first!), resolve any conflicts, and Execute again for real.

## Done When

- [ ] `javac TwinFold.java && java TwinFold` compiles and opens the window with two folder pickers, Scan/Execute buttons, a checked Dry run checkbox, an empty table, and a log pane.
- [ ] Pressing Scan with a non-folder path, or with `demo-left` nested inside the right folder, shows an error dialog instead of scanning.
- [ ] Scanning the phase-1 fixture shows exactly the five rows from the expected table: the conflict on top in red, the two copies in green/blue, and the two unchanged rows in gray — including `pics/readme.txt` marked as a content match despite different mtimes.
- [ ] With Dry run checked, Execute logs `[DRY RUN]` lines for every planned action; afterwards `demo-right/shared.txt` still contains `right version`, no `left-only.txt` appears on the right, and no `.twinfold.state` exists.
- [ ] Resolving `shared.txt` to `Keep Left` and executing for real copies both one-sided files across, overwrites the right `shared.txt` with `left version`, preserves mtimes on copied files, and writes `.twinfold.state` inside `demo-left`.
- [ ] After running the phase-2 script, a rescan produces exactly: `COPY L→R` for `shared.txt`, a new red `CONFLICT` for `notes/same.txt`, and `DELETE R` for `notes/left-only.txt`; executing deletes `demo-right/notes/left-only.txt`.
- [ ] The window stays responsive while scanning a large tree (e.g. your JDK's `src.zip` extracted, or any folder with a few thousand files), and the progress bar advances during Execute.
- [ ] The About dialog shows the date and time the solution was produced and the model/author that produced it.

## Stretch Goals (optional)

- Add a `Keep newer on all conflicts` bulk-resolution button that sets every conflict's Resolution from its mtime comparison.
- Add an ignore-patterns field (comma-separated globs like `*.tmp,Thumbs.db,.git`) applied to both trees during scan, with ignored paths logged.
- Add a `One-way mirror` toggle: the left folder is the master — right-only files become `DELETE R` instead of `COPY R→L`, and conflicts disappear (left always wins).
