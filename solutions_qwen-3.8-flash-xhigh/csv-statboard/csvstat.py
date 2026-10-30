#!/usr/bin/env python3
# CSV StatBoard -- csvstat.py
# A tiny terminal dashboard that profiles numeric columns of any CSV
# and draws ASCII horizontal bar charts. Stdlib only, Python 3.8+.
#
# Generated 2026-10-30 00:09 by Qwen3.8 Flash (xhigh)

import argparse
import csv
import io
import math
import statistics
import sys
from datetime import datetime

# --- sign-off stamp (time this solution was produced, not runtime) ----------
GENERATED_AT = "2026-10-30 00:09"
GENERATED_BY = "Qwen3.8 Flash (xhigh)"

# --- embedded sample dataset (coffee-cart sales) -----------------------------
SAMPLE_CSV = """\
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
"""

SEP_WIDTH = 60
BAR_MAX = 30          # the largest value always gets 30 '#' chars
LINE_LIMIT = 78       # keep output inside any terminal width


def parse_num(text):
    """Parse one CSV cell as a number: int if it looks like one, else float.

    Returns None for empty cells and anything that does not parse as a
    finite float.
    """
    s = text.strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        v = float(s)
    except ValueError:
        return None
    if not math.isfinite(v):
        return None
    return v


def looks_like_dates(values):
    """True if every value parses as an ISO calendar date (YYYY-MM-DD)."""
    if not values:
        return False
    for s in values:
        try:
            datetime.strptime(s.strip(), "%Y-%m-%d")
        except ValueError:
            return False
    return True


def load_rows(text):
    """Split CSV text into (header, data_rows), skipping blank lines and
    rows whose field count differs from the header."""
    header = None
    rows = []
    for row in csv.reader(io.StringIO(text)):
        if not row or all(field.strip() == "" for field in row):
            continue                      # blank line
        if header is None:
            header = row
            continue
        if len(row) != len(header):
            continue                      # ragged row
        rows.append(row)
    return header, rows


def profile_columns(header, rows):
    """Return (numeric_cols, nonnumeric_cols) preserving header order.

    numeric_cols:      list of (index, name, [parsed values])
    nonnumeric_cols:   list of (index, name, [raw non-empty values])
    A column counts as numeric when every non-empty value parses as a float.
    """
    numeric, nonnumeric = [], []
    for i, name in enumerate(header):
        non_empty = [row[i] for row in rows if row[i].strip() != ""]
        values = []
        is_numeric = True
        for cell in non_empty:
            v = parse_num(cell)
            if v is None:
                is_numeric = False
                break
            values.append(v)
        if is_numeric:
            numeric.append((i, name, values))
        else:
            nonnumeric.append((i, name, non_empty))
    return numeric, nonnumeric


def pick_category_column(nonnumeric):
    """First non-numeric column, preferring a true category: date-stamp
    columns are skipped when another non-numeric column exists."""
    if not nonnumeric:
        return None
    plain = [col for col in nonnumeric
             if not looks_like_dates(col[2])]
    chosen = plain[0] if plain else nonnumeric[0]
    return chosen[0], chosen[1]


def fmt_value(v):
    """Render a computed value: ints stay bare, floats rounded to 2 dp."""
    if isinstance(v, int):
        return str(v)
    return str(round(float(v), 2))


def stats_section(numeric_cols):
    lines = ["COLUMN STATS"]
    if not numeric_cols:
        lines.append("(no numeric columns detected)")
        return lines
    stats = []
    for _, name, values in numeric_cols:
        if not values:
            stats.append((name, "n/a", "n/a", "n/a", "n/a"))
            continue
        mean = round(float(sum(values)) / len(values), 2)
        median = round(float(statistics.median(values)), 2)
        stats.append((name, fmt_value(min(values)), fmt_value(max(values)),
                      str(mean), str(median)))
    w_name = max(len(s[0]) for s in stats) + 3
    w_min = max(len(s[1]) for s in stats)
    w_max = max(len(s[2]) for s in stats)
    w_mean = max(len(s[3]) for s in stats)
    for name, vmin, vmax, mean, median in stats:
        lines.append(
            "{:<{wn}} min {:<{wmin}} max {:<{wmax}} mean {:<{wmean}} median {}"
            .format(name, vmin, vmax, mean, median,
                    wn=w_name, wmin=w_min, wmax=w_max, wmean=w_mean)
        )
    return lines


def aggregate(rows, cat_idx, val_idx, want_mean):
    """Aggregate the value column per category label.

    Empty labels and empty / non-numeric value cells are ignored.
    Categories with no valid values at all are dropped.
    """
    totals, counts = {}, {}
    for row in rows:
        label = row[cat_idx].strip()
        if not label:
            continue
        v = parse_num(row[val_idx])
        if v is None:
            continue
        totals[label] = totals.get(label, 0) + v
        counts[label] = counts.get(label, 0) + 1
    if want_mean:
        return {k: totals[k] / counts[k] for k in totals}
    return totals


def chart_section(title, data, top):
    lines = [title]
    if not data:
        lines.append("(no data)")
        return lines
    items = sorted(data.items(), key=lambda kv: (-kv[1], kv[0]))
    if top is not None:
        items = items[:top]
    scale = max(v for _, v in items)
    label_w = max(len(k) for k, _ in items)
    for label, value in items:
        disp = fmt_value(value)
        if value == 0:
            length = 0
        elif scale > 0:
            length = int(value / scale * BAR_MAX + 0.5)
            length = max(1, min(length, BAR_MAX))
        else:                       # no positive value to scale against
            length = 1
        # keep the whole line inside the terminal-width limit
        room = LINE_LIMIT - (label_w + 3 + len(disp) + 1)
        length = min(length, max(0, room))
        lines.append("{:<{w}} | {} {}".format(label, "#" * length, disp,
                                              w=label_w))
    return lines


def build_dashboard(source_label, header, rows, top):
    out = ["=" * SEP_WIDTH, "CSV STATBOARD"]
    src = "Source: {} | Rows: {} | Columns: {}".format(
        source_label, len(rows), len(header))
    if len(src) > LINE_LIMIT:       # truncate a very long file name
        keep = LINE_LIMIT - (len(src) - len(source_label))
        source_label = (source_label[:max(0, keep - 3)] + "...") if keep > 3 else "..."
        src = "Source: {} | Rows: {} | Columns: {}".format(
            source_label, len(rows), len(header))
    out.append(src)
    out.append("")

    numeric_cols, nonnumeric_cols = profile_columns(header, rows)
    out += stats_section(numeric_cols)

    cat = pick_category_column(nonnumeric_cols)
    if cat is not None and numeric_cols:
        cat_idx, cat_name = cat

        col1_idx, col1_name, _ = numeric_cols[0]
        out.append("")
        data1 = aggregate(rows, cat_idx, col1_idx, want_mean=False)
        out += chart_section("TOTAL {} BY {}".format(col1_name, cat_name),
                             data1, top)

        if len(numeric_cols) > 1:
            col2_idx, col2_name, _ = numeric_cols[1]
            out.append("")
            data2 = aggregate(rows, cat_idx, col2_idx, want_mean=True)
            out += chart_section("AVG {} BY {}".format(col2_name, cat_name),
                                 data2, top)

    out.append("")
    out.append("Generated {} by {}".format(GENERATED_AT, GENERATED_BY))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="csvstat.py",
        description="CSV StatBoard: profile numeric columns of a CSV and "
                    "draw ASCII bar charts. With no file argument the "
                    "embedded sample dataset is analyzed.")
    parser.add_argument("csv_file", nargs="?",
                        help="path to a CSV file (optional)")
    parser.add_argument("--top", type=int, default=None, metavar="N",
                        help="limit each chart to the top N categories")
    args = parser.parse_args(argv)
    if args.top is not None and args.top <= 0:
        parser.error("--top must be a positive integer")

    if args.csv_file:
        try:
            with open(args.csv_file, newline="", encoding="utf-8") as fh:
                text = fh.read()
        except OSError as exc:
            print("error: cannot read {}: {}".format(args.csv_file, exc),
                  file=sys.stderr)
            return 1
        source_label = args.csv_file
    else:
        text = SAMPLE_CSV
        source_label = "embedded sample"

    header, rows = load_rows(text)
    if not header:
        print("error: no CSV header found", file=sys.stderr)
        return 1

    for line in build_dashboard(source_label, header, rows, args.top):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
