# CSV StatBoard

**Difficulty:** easy  |  **Stack:** Python 3 (stdlib only)  |  **Estimated time:** 30–60 min

## The Problem

Someone hands you a CSV export — coffee-cart sales, a sensor log, a survey dump — and you just want a quick feel for the numbers without opening a spreadsheet. Scrolling raw rows tells you nothing; what you need is a tiny terminal tool that reads any CSV, profiles its numeric columns, and draws horizontal ASCII bar charts so the shape of the data is visible at a glance. Build that dashboard as a single self-contained Python script that works out of the box on an embedded sample dataset.

## Requirements

1. Produce a single file `csvstat.py`. Running `python3 csvstat.py` analyzes an embedded sample dataset (the CSV from the Sample Data section, stored in the source as a triple-quoted string constant `SAMPLE_CSV`); running `python3 csvstat.py somefile.csv` analyzes that file instead.
2. Print a dashboard header first: a separator line of 60 `=` characters, then a title line `CSV STATBOARD`, then the data source (`embedded sample` or the file name) and the number of data rows and columns detected.
3. Detect numeric columns automatically: a column counts as numeric if every non-empty value in it parses as a float. For each numeric column, print one stats line showing the column name plus its **min**, **max**, **mean**, and **median**, with mean and median rounded to 2 decimal places.
4. Render a first horizontal bar chart titled `TOTAL <col> BY <category>`, where `<col>` is the first numeric column and `<category>` is the first non-numeric column: sum the values per category and sort the categories by total descending. For the embedded sample this must be total `units_sold` by `drink`.
5. Render a second horizontal bar chart titled `AVG <col2> BY <category>`, where `<col2>` is the second numeric column (if one exists): show the per-category mean rounded to 2 decimals, sorted descending by that mean. For the embedded sample this must be average `revenue` by `drink`.
6. Bar formatting rules (apply to both charts): draw bars as runs of `#` characters; category labels left-justified and padded with spaces to the width of the longest label, followed by ` | `, then the bar, then a space and the numeric value. The largest value gets a bar of exactly 30 `#` characters; every other bar's length is its value scaled proportionally and rounded to the nearest integer (any non-zero value gets at least 1 `#`). Ignore empty or non-numeric cells in the aggregated column.
7. Robustness: silently skip blank lines and rows whose field count differs from the header; if a numeric column ends up with no valid values, print `n/a` for its stats instead of crashing.
8. **Sign-off:** the dashboard must end with a footer line showing the date and time the solution was produced and the model/author that produced it; also include the same information as a header comment in the source.

## Constraints

- Python 3.8+, standard library only (`csv`, `io`, `statistics`, `sys` are enough). No third-party packages, no pip, no build step.
- No network access. Do not read or write any file other than the optional CSV path given as a command-line argument.
- Output must be plain ASCII text (use `#` for bars) and stay within 78 columns wide so it fits any terminal.
- The embedded sample data must live inside the source as a string constant — the script must run with zero arguments and no external files present.

## Sample Data / Inputs

Embedded sample — use exactly this as `SAMPLE_CSV` (two-plus days of coffee-cart sales):

```csv
date,drink,units_sold,revenue,avg_prep_seconds
2025-01-06,Espresso,42,126.00,38
2025-01-06,Latte,35,157.50,52
2025-01-06,Cold Brew,18,81.00,15
2025-01-06,Mocha,12,66.00,64
2025-01-07,Espresso,51,153.00,36
2025-01-07,Latte,28,126.00,55
2025-01-07,Cold Brew,24,108.00,14
2025-01-07,Mocha,9,49.50,61
2025-01-08,Espresso,47,141.00,39
2025-01-08,Latte,31,139.50,50
2025-01-08,Cold Brew,29,130.50,16
2025-01-08,Mocha,15,82.50,58
2025-01-08,Chai,11,44.00,45
2025-01-09,Chai,14,56.00,42
```

Expected shape of the dashboard for the embedded sample (exact layout is up to you, but all values must be computed, never hardcoded):

```
============================================================
CSV STATBOARD
Source: embedded sample | Rows: 14 | Columns: 5

COLUMN STATS
units_sold         min 9    max 51     mean 26.14  median 26.0
revenue            min 44.0 max 157.5  mean 104.32 median 117.0
avg_prep_seconds   min 14.0 max 64.0   mean 41.79  median 43.5

TOTAL units_sold BY drink
Espresso  | ############################## 140
Latte     | #################### 94
Cold Brew | ############### 71
Mocha     | ######## 36
Chai      | ##### 25

AVG revenue BY drink
Latte     | ############################## 141.0
Espresso  | ############################## 140.0
Cold Brew | ####################### 106.5
Mocha     | ############## 66.0
Chai      | ########### 50.0

Generated 2026-10-29 12:00 by <model/author>
```

## Deliverable

- One file: `csvstat.py`
- Run commands:
  - `python3 csvstat.py` — renders the dashboard for the embedded sample data
  - `python3 csvstat.py yourdata.csv` — renders the dashboard for any other CSV file

## Done When

- [ ] `python3 csvstat.py` runs with no arguments and prints the full dashboard for the embedded sample without errors.
- [ ] The header reports source `embedded sample`, 14 rows and 5 columns.
- [ ] Stats lines appear for `units_sold`, `revenue`, and `avg_prep_seconds` (but not `date` or `drink`) with min/max/mean/median.
- [ ] Chart 1 shows Espresso (140) on top and Chai (25) at the bottom; the Espresso bar is exactly 30 `#` characters.
- [ ] Chart 2 shows average revenue per drink, sorted descending (Latte 141.0 first), and all bar lines are aligned via padded labels and a ` | ` separator.
- [ ] The script also works on a different CSV file passed as a command-line argument.
- [ ] A footer line shows the date/time the solution was produced and the model/author.

## Stretch Goals (optional)

- Add a `--top N` flag that limits each chart to the top N categories.
- Add a third chart: a sparkline (`▁▂▃▄▅▆▇█`) of the first numeric column in original file order.
- Color the bars with ANSI escape codes, but only when `sys.stdout.isatty()` is true.
