# Centsible

**Difficulty:** Hard  |  **Stack:** Python 3 (stdlib only, `sqlite3`)  |  **Estimated time:** 3–6 hours

## The Problem

Bank apps show you transactions but never a budget; spreadsheets rot the moment you forget a row. What actually works for personal finance is a tiny local-first ledger you control: record income and expenses from the terminal, file them under categories, set monthly budgets, get warned *the instant* a purchase pushes you over, and read a rendered monthly report — bar charts and all — without leaving the shell. Build **Centsible**: a single-file, SQLite-backed personal finance CLI that is durable (data survives restarts), scriptable (every command is composable), and honest about money (integer cents, never floats).

## Requirements

1. **Single-file CLI.** Deliver `centsible.py`, a Python command-line app built on `argparse` subcommands, persisting everything to a local SQLite database via the stdlib `sqlite3` module. The database file defaults to `centsible.db` in the current directory and is overridable with a global `--db PATH` flag. The schema is created automatically on first use — no manual setup step — and running any command twice never fails because tables already exist.
2. **Add transactions:** `centsible.py add income|expense AMOUNT CATEGORY [--date YYYY-MM-DD] [--note TEXT]`. `AMOUNT` must be positive with at most two decimal places (`12`, `12.5`, `12.55` accepted; `0`, `-3`, `12.345`, `abc` rejected). `--date` must be a real calendar date in ISO format, defaulting to today (`2026-02-30` rejected). `CATEGORY` is trimmed and matched case-insensitively — `groceries`, `Groceries`, and ` GROCERIES ` are the same category, with one consistent stored/display form. On success, print a one-line confirmation including the new transaction's id.
3. **Integer-cent money.** Store all amounts as integer cents in SQLite — never floats. Every displayed amount uses a currency symbol, thousands separators, and exactly two decimals (e.g. `$1,674.73`); in listings, income is signed `+` and expenses `-`.
4. **List transactions:** `centsible.py list [--month YYYY-MM] [--category NAME] [--type income|expense]` prints an aligned table (id, date, type, category, amount, note) ordered by date then id, defaulting to the current month, followed by a totals footer (total income, total expenses, net) computed over the filtered rows. Filters must compose when combined.
5. **Delete:** `centsible.py delete ID` removes one transaction and confirms it. Deleting a non-existent id is a clean error, not a traceback.
6. **Budgets:** `centsible.py budget set CATEGORY AMOUNT [--month YYYY-MM]` (default: current month) upserts a budget for that category; `centsible.py budget list [--month YYYY-MM]` shows each effective budget with the month's actual spend, the remaining/over amount, and a status tag (`OK` / `OVER`). Budgets are **sticky**: the effective budget for a category in month M is the most recent `budget set` for that category in any month ≤ M — setting Groceries to $450 in `2026-02` applies to `2026-03` unless overridden.
7. **Overspend warning on add:** when `add expense ...` pushes the category's total for that month past its effective budget, the transaction is still recorded, but a warning prints immediately, e.g. `! OVER BUDGET: Groceries is now $527.16 of $450.00 for 2026-03 (over by $77.16)`. No warning when the category has no effective budget.
8. **Monthly report:** `centsible.py report [YYYY-MM]` (default: current month) renders a full report to stdout containing, in order: (a) a header with the month's name and year; (b) a summary block — total income, total expenses, net, and savings rate (net ÷ income, printed as `n/a` when income is 0); (c) an income-vs-expenses comparison drawn as two horizontal bars sharing one scale; (d) a **category breakdown** — one line per expense category, sorted by total descending, each with right-aligned amount, a horizontal bar, and its percentage of total expenses; (e) a **budget status** section — for every category with an effective budget that month, a bar of spend vs budget with the percentage used and an explicit `OVER by $X` marker when exceeded; (f) a **daily spending** section listing every day of the month that has expenses, one line per day (`DD |bar $amount`), scaled like the other charts.
9. **Chart rules.** All charts are plain ASCII (`#`, `-`, `|`, `+`, `>`, `=`, `[`, `]`) — no Unicode block or box-drawing characters. In each section, the largest value's bar fills a fixed maximum width of 30 characters, smaller values scale proportionally (minimum 1 character for any non-zero value), amounts are right-aligned, and the entire report fits an 80-column terminal. A month with no transactions prints a friendly "no data" message and exits 0 — never a crash, empty chart, or division-by-zero.
10. **CSV import:** `centsible.py import FILE` imports a CSV with header `date,type,category,amount,note` (see Sample Data). Every row is validated exactly like `add`; invalid rows are skipped and reported with their line numbers while valid rows still import in the same run. Import is **idempotent**: re-importing the same file imports 0 rows and reports every previously imported row as a skipped duplicate (enforce with a uniqueness constraint over `(date, type, category, amount, note)`). The command ends with a one-line summary, e.g. `imported 47, skipped 0 duplicates, 0 invalid`.
11. **Robust errors.** Any invalid input — bad amount, impossible date, malformed month, missing CSV file, corrupt CSV row — produces a single clear error line on stderr and a non-zero exit code: never a Python traceback, and never a partial database write for a failed command.
12. **Sign-off:** the finished solution must display the date and time it was produced and the model/author that produced it, both in a header comment at the top of `centsible.py` and in the output of `centsible.py about` (e.g. `Centsible — built 2026-10-29 14:32 by <model-name>`).

## Constraints

- Python 3.8+ **standard library only** — `sqlite3`, `argparse`, `csv`, `datetime`, `calendar`, `sys`, `os`, `textwrap`. No third-party packages, no `pip install`, no virtualenv, no build step.
- Exactly one source file, `centsible.py`, plus the `sample.csv` data file created verbatim from this prompt. No other modules, config files, or resources.
- Storage is exactly one local SQLite file. No network access, no environment variables, no background daemons.
- Multi-row writes (import) run inside a transaction: a failed command leaves previously committed data untouched.
- All terminal output is plain ASCII text, charts included; assume ≥ 80 columns and a monospace font.
- The sample data below is the only dataset — embed it; do not fetch anything from anywhere else.

## Sample Data / Inputs

Save the following verbatim as `sample.csv` (47 data rows, Jan–Mar 2026):

```csv
date,type,category,amount,note
2026-01-01,income,Salary,3450.00,Monthly paycheck
2026-01-02,expense,Rent,1150.00,January rent
2026-01-03,expense,Groceries,84.12,Weekly supermarket run
2026-01-05,expense,Transport,42.00,Metro pass top-up
2026-01-07,expense,Utilities,96.44,Electricity bill
2026-01-10,expense,Groceries,77.85,Weekly supermarket run
2026-01-11,expense,Dining,23.50,Ramen with Sam
2026-01-14,expense,Entertainment,15.99,Streaming subscription
2026-01-17,expense,Groceries,91.03,Weekly supermarket run
2026-01-18,income,Freelance,320.00,Logo design invoice
2026-01-19,expense,Health,28.75,Pharmacy
2026-01-21,expense,Dining,41.20,Birthday dinner
2026-01-24,expense,Groceries,68.49,Weekly supermarket run
2026-01-27,expense,Transport,18.60,Rideshare home
2026-01-31,expense,Groceries,75.55,Monthly pantry restock
2026-02-01,income,Salary,3450.00,Monthly paycheck
2026-02-02,expense,Rent,1150.00,February rent
2026-02-04,expense,Groceries,88.20,Weekly supermarket run
2026-02-06,expense,Utilities,102.37,Electricity bill
2026-02-08,expense,Dining,30.25,Pizza night
2026-02-11,expense,Groceries,72.94,Weekly supermarket run
2026-02-13,expense,Transport,42.00,Metro pass top-up
2026-02-14,expense,Dining,64.80,Valentines dinner
2026-02-15,expense,Entertainment,15.99,Streaming subscription
2026-02-18,expense,Groceries,95.61,Weekly supermarket run
2026-02-20,expense,Health,45.00,Dentist copay
2026-02-22,income,Freelance,410.50,Website fixes invoice
2026-02-22,expense,Groceries,80.32,Weekly supermarket run
2026-02-25,expense,Transport,21.35,Rideshare to airport
2026-02-27,expense,Groceries,69.08,Monthly pantry restock
2026-03-01,income,Salary,3450.00,Monthly paycheck
2026-03-02,expense,Rent,1150.00,March rent
2026-03-03,expense,Groceries,102.45,Bulk staples haul
2026-03-05,expense,Utilities,89.12,Electricity bill
2026-03-06,expense,Dining,27.90,Burger lunch
2026-03-08,expense,Groceries,118.37,Weekly supermarket run
2026-03-10,expense,Transport,42.00,Metro pass top-up
2026-03-12,expense,Groceries,96.20,Weekly supermarket run
2026-03-14,income,Freelance,275.00,Consulting call
2026-03-14,expense,Entertainment,15.99,Streaming subscription
2026-03-15,expense,Dining,38.45,Sushi takeout
2026-03-17,expense,Health,62.30,New glasses
2026-03-19,expense,Groceries,121.64,Weekly supermarket run
2026-03-21,expense,Transport,19.75,Rideshare home
2026-03-24,expense,Groceries,88.50,Weekly supermarket run
2026-03-26,expense,Dining,45.60,Team lunch
2026-03-28,expense,Entertainment,32.00,Concert ticket
```

**Reference figures for verifying your implementation** (after importing the file above):

- **March 2026:** income $3,725.00 · expenses $2,050.27 · net $1,674.73 · savings rate ≈ 45.0%
- March category leaders: Rent $1,150.00 (56.1% of expenses) → Groceries $527.16 (25.7%) → Dining $111.95 (5.5%)
- With a $450.00 Groceries budget, March Groceries sits at 117% used — **OVER by $77.16**

## Deliverable

- `centsible.py` — the complete application (single file)
- `sample.csv` — the sample data from this prompt, copied verbatim
- Run it:

```sh
python3 centsible.py import sample.csv
python3 centsible.py budget set groceries 450 --month 2026-03
python3 centsible.py report 2026-03
python3 centsible.py list --month 2026-02 --category dining
python3 centsible.py add expense 9.99 groceries --date 2026-03-30 --note "Late snack run"
```

## Done When

- [ ] `python3 centsible.py import sample.csv` prints `imported 47, skipped 0 duplicates, 0 invalid`; running the exact same command again prints `imported 0, skipped 47 duplicates, 0 invalid`.
- [ ] `python3 centsible.py report 2026-03` shows income $3,725.00, expenses $2,050.27, net $1,674.73, savings rate ≈ 45%, and the category breakdown begins Rent $1,150.00 (56.1%) then Groceries $527.16 (25.7%), with ASCII bars scaled to the largest value.
- [ ] After `budget set groceries 450 --month 2026-03`, the March report's budget section shows Groceries at 117% used with an `OVER by $77.16` marker.
- [ ] `budget set dining 100 --month 2026-02` followed by `report 2026-03` still applies the $100 dining budget in March (sticky budget) and flags March dining ($111.95) as over.
- [ ] `add expense 9.99 groceries --date 2026-03-30` prints an over-budget warning immediately, and the transaction still appears in `list --month 2026-03`.
- [ ] `list --month 2026-02 --category dining` shows exactly the 2 February dining rows plus a totals footer with correct income/expense/net figures.
- [ ] `delete <id>` removes a listed transaction; deleting the same id again fails with a clean error and non-zero exit.
- [ ] `add expense 12.345 food`, `add expense -5 food`, and `add expense 5 food --date 2026-02-30` each fail with a clear one-line error, a non-zero exit code, and no traceback; nothing is written to the database.
- [ ] `report 2025-12` (no data) prints a friendly message and exits 0; every chart in every report is ASCII-only and fits 80 columns.
- [ ] `python3 centsible.py about` prints the sign-off (date/time produced + model/author), matching the header comment at the top of `centsible.py`.

## Stretch Goals (optional)

- `export FILE` — dump all transactions to CSV in the same format as the importer, such that exporting and re-importing into a fresh database reproduces the data losslessly.
- `trend` — render the last 6 months of net savings as an ASCII bar chart, drawing negative months to the left of a visible zero axis.
- `recurring add income Salary 3450.00 --day 1` — store recurring rules in SQLite and auto-materialize that month's instances (idempotently, at most once each) whenever any command runs.
