# Pocket Plotter

**Difficulty:** medium  |  **Stack:** Python 3 (Tkinter, stdlib only)  |  **Estimated time:** 1–3 hours

## The Problem

Engineers and hobbyists constantly receive small CSV exports — sensor logs, fermentation readings, battery discharge curves — and just want to *see* the shape of the numbers without firing up a spreadsheet or installing a plotting library. Double-clicking the file gets you a grid of cells, not insight. What’s missing is a tiny desktop tool that opens any CSV, lets you pick an X column and one or two Y series, and draws a proper line or scatter chart — axes, ticks, gridlines, legend and all — on a plain Tkinter canvas. Build that tool as a single dependency-free Python script that works out of the box on an embedded sample dataset.

## Requirements

1. Produce a single file `plotter.py`. Running `python3 plotter.py` opens the window and immediately plots the embedded sample dataset (stored in the source as a triple-quoted string constant `SAMPLE_CSV`); running `python3 plotter.py somefile.csv` preloads that file instead. The window must be at least 800×600 px at startup.
2. Window layout: a control bar across the top containing a **Load CSV…** button, an **X column** dropdown, a **Series 1** dropdown, a **Series 2** dropdown that includes a `— none —` option (default), and **Line / Scatter** radio buttons (Line selected by default); a `tk.Canvas` filling the rest of the window; and a status-bar label at the very bottom. Changing any dropdown or the mode re-renders the chart immediately.
3. The **Load CSV…** button opens `tkinter.filedialog.askopenfilename`; parse the chosen file with the `csv` module. The first row is the header. Silently skip blank lines and rows whose field count differs from the header. On fatal load errors (file unreadable, empty file, zero columns), show `tkinter.messagebox.showerror` and keep the previously displayed data.
4. A column is *plottable* if at least one of its values parses as a float. Only plottable columns appear in the Series dropdowns. The X dropdown lists `row index` as its first entry (meaning X = 1, 2, …, N) followed by the plottable columns, and defaults to the first plottable column. Series 1 defaults to the second plottable column if one exists, else the first.
5. Point extraction: convert X and Y values to floats; a point whose X or Y is missing or non-numeric is omitted from that series only (the other series keeps its valid points). The status bar must report the total number of skipped points. If the selected series end up with zero valid points, draw the axes anyway and display a centered “no plottable data” message on the canvas instead of crashing.
6. Rendering: compute a plot area inside the canvas with margins large enough for Y tick labels on the left and X tick labels plus axis titles below/right. Map data to pixels with about 5% headroom above and below the data range; if min == max on an axis, pad that axis by ±1. Negative values must render correctly (the zero line may fall inside the plot area — do not force axes through the origin).
7. Ticks and grid: each axis gets at least 5 and at most 8 tick marks placed at “nice” round steps (a 1 / 2 / 2.5 / 5 × 10^k progression). Format tick labels without useless trailing zeros. Draw light-gray gridlines across the plot area, black axis lines with tick marks, numeric tick labels, and axis titles taken from the column names (use `row index` when that X mode is selected).
8. Series rendering: in **Line** mode, connect each series’ valid points (sorted by X) with a polyline of width 2 and draw a filled circle marker (radius ~4 px) at every data point; in **Scatter** mode, draw markers only. Series 1 is drawn in `#1f77b4`, Series 2 in `#d62728`. Both series share the chosen X column and one common Y scale covering all visible data.
9. Legend: when at least one series is plotted, draw a legend inside the top-right corner of the plot area — one row per active series with a filled color swatch followed by the series’ column name. When Series 2 is set to `— none —`, only Series 1 appears in the legend.
10. Status bar: always shows the data source (`embedded sample` or the loaded file’s name), the number of data rows, the total skipped-point count, and the current X / Series 1 / Series 2 selections.
11. Handle window resizing: re-render the whole chart on the canvas `<Configure>` event so the plot, ticks, and legend always fit the current window size.
12. **Sign-off:** the window title bar or a clearly visible about line must display the date and time the solution was produced and the model/author that produced it; include the same information as a header comment in the source.

## Constraints

- Python 3.8+, standard library only (`tkinter`, `csv`, `io`, `math`, `os`/`sys` are enough). No third-party packages — in particular no matplotlib, numpy, or pandas — no pip, no build step.
- One self-contained file. No network access. Read no files other than the optional command-line CSV path or the file chosen in the load dialog.
- The embedded sample data must live in the source as a string constant so the program runs and shows a meaningful chart with zero arguments and no external files present.
- All drawing goes through `tk.Canvas` primitives (lines, ovals, rectangles, text) — no image assets.

## Sample Data / Inputs

Embedded sample — use exactly this as `SAMPLE_CSV` (14 days of homebrew fermentation: fermenter temperature vs. unheated garage temperature, one sensor dropout):

```csv
day,fermenter_c,garage_c
1,18.4,2.1
2,18.2,1.4
3,18.1,-0.6
4,18.3,-1.8
5,18.0,-2.4
6,17.8,-0.9
7,17.6,1.2
8,17.9,n/a
9,18.2,2.6
10,18.5,3.1
11,18.3,1.8
12,18.1,0.4
13,17.8,-1.1
14,17.7,-0.3
```

A second file for manual testing of the load dialog and error handling — save as `broken.csv`:

```csv
time,reading,notes
0,10.5,ok
1,11.2
2,,blank value
3,12.4,ok,extra field
4,13.0,ok
```

## Deliverable

- One file: `plotter.py`
- Run commands:
  - `python3 plotter.py` — opens the app showing the embedded sample chart
  - `python3 plotter.py yourdata.csv` — opens the app with that CSV preloaded

## Done When

- [ ] `python3 plotter.py` opens a window and immediately shows the sample data as two blue/red lines with markers — no file loading required.
- [ ] Both axes show 5–8 ticks with clean rounded values (e.g. steps of 0.5, 1, 2 or 5), gridlines, and axis titles `day`, `fermenter_c` / `garage_c`.
- [ ] The negative `garage_c` values plot below zero, the `n/a` dropout on day 8 is skipped (status bar reports 1 skipped point), and the red line simply bridges the gap.
- [ ] Switching to Scatter hides the polylines and leaves only markers; setting Series 2 to `— none —` removes the red series and its legend row.
- [ ] The legend sits inside the top-right of the plot area with correct swatches and names.
- [ ] Loading `broken.csv` via the dialog plots its valid points, and the status bar shows the file name plus the correct skipped-point count (2: the blank `reading` and the ragged row’s missing/extra fields per the skip rules).
- [ ] Loading an empty or header-less file pops an error dialog and the previous chart stays on screen.
- [ ] Dragging the window corner larger/smaller re-renders the chart to fit, with no clipped labels or misplaced legend.
- [ ] Selecting `row index` as X plots the series against 1..N with `row index` as the X axis title.
- [ ] The window title or an about line shows the date/time the solution was produced and the model/author, and the same sign-off appears as a source header comment.

## Stretch Goals (optional)

- Hover crosshair: moving the mouse over the plot shows the nearest data point’s exact (x, y) values in the status bar.
- Add a “Save as PostScript…” button that exports the current canvas via `canvas.postscript()`.
- Auto-detect the delimiter (comma, semicolon, or tab) using `csv.Sniffer`, falling back to comma.
