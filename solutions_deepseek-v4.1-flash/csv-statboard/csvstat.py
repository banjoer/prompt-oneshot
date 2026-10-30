#!/usr/bin/env python3
# Generated 2026-10-29 22:40 by DeepSeek V4.1 Flash (opencode)
"""CSV StatBoard - profile numeric CSV columns and draw ASCII bar charts.

Usage:
    python3 csvstat.py [--top N] [file.csv]

With no file argument the embedded SAMPLE_CSV is analysed.  Standard library
only; output is plain ASCII and fits in 78 columns.
"""

import csv
import io
import math
import os
import re
import statistics
import sys

SIGN_OFF = "Generated 2026-10-29 22:40 by DeepSeek V4.1 Flash (opencode)"
SEPARATOR = "=" * 60
BAR_MAX = 30
MAX_WIDTH = 78

SAMPLE_CSV = """date,drink,units_sold,revenue,avg_prep_seconds
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

# Values that look like calendar timestamps are treated as an axis rather
# than a category.  Without this, the sample's ``date`` column would win the
# "first non-numeric column" contest and the charts would group by day.
_DATE_VALUE_RE = re.compile(
    r"^(?:"
    r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?"
    r"|\d{4}/\d{2}/\d{2}"
    r"|\d{1,2}/\d{1,2}/\d{4}"
    r"|\d{1,2}:\d{2}(?::\d{2})?"
    r")$"
)
_DATE_NAMES = {"date", "datetime", "time", "timestamp", "ts", "day", "month", "year"}


def parse_float(text):
    """Return a float for *text*, or None when it is not numeric."""
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def load_rows(reader):
    """Normalise a csv.reader into (header, data).

    Blank lines and rows whose field count differs from the header are
    silently dropped.
    """
    rows = []
    for row in reader:
        if not row or not any(cell.strip() for cell in row):
            continue
        rows.append(row)

    if not rows:
        return [], []

    header = [cell.strip() for cell in rows[0]]
    width = len(header)
    data = [row for row in rows[1:] if len(row) == width]
    return header, data


def load_file(path):
    with open(path, "r", newline="", encoding="utf-8-sig", errors="replace") as handle:
        return load_rows(csv.reader(handle))


def column_is_numeric(column):
    """True when every non-empty cell in the column parses as a float."""
    return all(parse_float(cell.strip()) is not None for cell in column if cell.strip())


def numeric_column_style(column):
    """Return True when the column's literals look like decimal numbers.

    This only affects display (44.0 rather than 44); the arithmetic is the
    same either way.
    """
    return any(
        ("." in cell or "e" in cell.lower())
        for cell in column
        if cell.strip()
    )


def column_values(data, index):
    values = []
    for row in data:
        cell = row[index].strip()
        if not cell:
            continue
        number = parse_float(cell)
        if number is not None and math.isfinite(number):
            values.append(number)
    return values


def is_temporal_column(name, column):
    non_empty = [cell.strip() for cell in column if cell.strip()]
    if not non_empty:
        return False
    date_like = sum(1 for cell in non_empty if _DATE_VALUE_RE.match(cell))
    ratio = date_like / len(non_empty)
    lowered = name.strip().lower()
    name_hint = lowered in _DATE_NAMES or lowered.endswith(
        ("_date", "_time", "_at", "_timestamp")
    )
    return ratio >= 0.8 or (name_hint and ratio >= 0.5)


def choose_category(header, data, numeric_flags):
    """Pick the grouping column, avoiding timestamp axes when possible."""
    candidates = [i for i, flag in enumerate(numeric_flags) if not flag]
    if not candidates:
        return None
    non_temporal = [
        i
        for i in candidates
        if not is_temporal_column(header[i], [row[i] for row in data])
    ]
    return non_temporal[0] if non_temporal else candidates[0]


def fmt_number(value, force_decimal=False):
    """Compact display for mins, maxes and totals."""
    if value is None:
        return "n/a"
    if not math.isfinite(value):
        return str(value)
    if value == int(value) and abs(value) < 1e15:
        text = str(int(value))
        return text + ".0" if force_decimal else text
    if abs(value) >= 1e9:
        return f"{value:.6g}"
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def fmt_metric(value):
    """Mean/median style: rounded to 2 places, at least one decimal kept."""
    if value is None:
        return "n/a"
    if not math.isfinite(value):
        return str(value)
    rounded = round(value, 2)
    if rounded == 0:
        rounded = 0.0
    if abs(rounded) >= 1e9:
        return f"{rounded:.6g}"
    text = f"{rounded:.2f}".rstrip("0")
    if text.endswith("."):
        text += "0"
    return text


def truncate(text, limit):
    if limit <= 0:
        return ""
    if len(text) <= limit:
        return text
    if limit <= 3:
        return text[:limit]
    return text[: limit - 3] + "..."


def aggregate(data, category_index, value_index, mode):
    """Aggregate a numeric column per category, ignoring bad cells."""
    totals = {}
    counts = {}
    for row in data:
        cell = row[value_index].strip()
        if not cell:
            continue
        value = parse_float(cell)
        if value is None or not math.isfinite(value):
            continue
        label = row[category_index].strip() or "(blank)"
        totals[label] = totals.get(label, 0.0) + value
        counts[label] = counts.get(label, 0) + 1

    if mode == "sum":
        items = [(label, total) for label, total in totals.items()]
    else:
        items = [(label, totals[label] / counts[label]) for label in totals]

    # Python's sort is stable, so equal values keep first-seen order.
    items.sort(key=lambda item: item[1], reverse=True)
    return items


def chart_bar_length(value, largest, bar_limit):
    if not math.isfinite(value) or value == 0:
        return 0
    if not math.isfinite(largest) or largest <= 0:
        return 1
    scaled = int(value / largest * bar_limit + 0.5)
    return max(1, min(bar_limit, scaled)) if value > 0 else 1


def render_chart(title, items, force_decimal, limit):
    print(title)
    if limit is not None:
        items = items[:limit]
    if not items:
        print("  (no data)")
        print()
        return

    value_texts = [
        fmt_metric(value) if title.startswith("AVG ") else fmt_number(value, force_decimal)
        for _, value in items
    ]
    max_value_width = max(len(text) for text in value_texts)

    # Reserve room for the full 30-character bar.  Only a pathologically long
    # value string can force a shorter bar; labels are truncated instead.
    overhead = 3 + 1 + max_value_width  # " | " + " " + value
    label_limit = max(1, MAX_WIDTH - BAR_MAX - overhead)
    labels = [truncate(label, label_limit) for label, _ in items]
    label_width = max(len(label) for label in labels)
    bar_limit = min(BAR_MAX, max(1, MAX_WIDTH - label_width - overhead))

    largest = max(value for _, value in items)
    for label, value, value_text in zip(labels, (v for _, v in items), value_texts):
        bar = "#" * chart_bar_length(value, largest, bar_limit)
        print(f"{label:<{label_width}} | {bar} {value_text}")
    print()


def print_header(source, row_count, column_count):
    print(SEPARATOR)
    print("CSV STATBOARD")
    line = f"Source: {source} | Rows: {row_count} | Columns: {column_count}"
    if len(line) > MAX_WIDTH:
        room = MAX_WIDTH - len(line) + len(source)
        line = f"Source: {truncate(source, room)} | Rows: {row_count} | Columns: {column_count}"
    print(line)
    print()


def print_stats(header, data, numeric_indices):
    print("COLUMN STATS")
    rows = []
    for index in numeric_indices:
        values = column_values(data, index)
        if values:
            min_text = fmt_number(min(values), numeric_column_style([row[index] for row in data]))
            max_text = fmt_number(max(values), numeric_column_style([row[index] for row in data]))
            mean_text = fmt_metric(statistics.fmean(values))
            median_text = fmt_metric(statistics.median(values))
        else:
            min_text = max_text = mean_text = median_text = "n/a"
        rows.append((header[index] or f"column_{index + 1}", min_text, max_text, mean_text, median_text))

    min_width = max(len(row[1]) for row in rows)
    max_width = max(len(row[2]) for row in rows)
    mean_width = max(len(row[3]) for row in rows)
    median_width = max(len(row[4]) for row in rows)
    name_width = max(len(row[0]) for row in rows)

    fixed = 6 + min_width + 6 + max_width + 7 + mean_width + 8 + median_width
    if name_width + fixed > MAX_WIDTH:
        name_width = max(3, MAX_WIDTH - fixed)

    for name, min_text, max_text, mean_text, median_text in rows:
        name = truncate(name, name_width)
        print(
            f"{name:<{name_width}}  min {min_text:<{min_width}}"
            f"  max {max_text:<{max_width}}"
            f"  mean {mean_text:<{mean_width}}"
            f"  median {median_text}"
        )
    print()


def build_dashboard(header, data, source, top=None):
    print_header(source, len(data), len(header))
    if not header:
        print("No data found.")
        print()
        print(SIGN_OFF)
        return

    numeric_indices = [
        index
        for index in range(len(header))
        if column_is_numeric([row[index] for row in data])
    ]
    if not numeric_indices:
        print("COLUMN STATS")
        print("  (no numeric columns found)")
        print()
        print(SIGN_OFF)
        return

    print_stats(header, data, numeric_indices)

    category_index = choose_category(header, data, [i in numeric_indices for i in range(len(header))])
    first_numeric = numeric_indices[0]
    second_numeric = numeric_indices[1] if len(numeric_indices) > 1 else None

    if category_index is not None:
        category_name = header[category_index] or f"column_{category_index + 1}"
        first_name = header[first_numeric] or f"column_{first_numeric + 1}"
        totals = aggregate(data, category_index, first_numeric, "sum")
        render_chart(
            f"TOTAL {first_name} BY {category_name}",
            totals,
            numeric_column_style([row[first_numeric] for row in data]),
            top,
        )

        if second_numeric is not None:
            second_name = header[second_numeric] or f"column_{second_numeric + 1}"
            averages = aggregate(data, category_index, second_numeric, "avg")
            render_chart(f"AVG {second_name} BY {category_name}", averages, False, top)
        else:
            print(f"AVG chart skipped: only one numeric column ({first_name}).")
            print()
    else:
        print("Charts skipped: no category column found.")
        print()

    print(SIGN_OFF)


def usage(stream=sys.stdout):
    print("Usage: python3 csvstat.py [--top N] [file.csv]", file=stream)
    print("  file.csv   CSV to analyse (omit to use the embedded sample)", file=stream)
    print("  --top N    show only the N largest categories per chart", file=stream)


def main(argv):
    path = None
    top = None
    index = 1
    while index < len(argv):
        arg = argv[index]
        if arg in ("-h", "--help"):
            usage()
            return 0
        if arg == "--top":
            index += 1
            if index >= len(argv):
                print("error: --top requires a positive integer", file=sys.stderr)
                return 2
            raw = argv[index]
            try:
                top = int(raw)
            except ValueError:
                print(f"error: invalid --top value: {raw}", file=sys.stderr)
                return 2
            if top <= 0:
                print("error: --top must be a positive integer", file=sys.stderr)
                return 2
        elif arg.startswith("--top="):
            raw = arg.split("=", 1)[1]
            try:
                top = int(raw)
            except ValueError:
                print(f"error: invalid --top value: {raw}", file=sys.stderr)
                return 2
            if top <= 0:
                print("error: --top must be a positive integer", file=sys.stderr)
                return 2
        elif arg.startswith("-") and arg != "-":
            print(f"error: unknown option: {arg}", file=sys.stderr)
            usage(sys.stderr)
            return 2
        elif path is None:
            path = arg
        else:
            print(f"error: unexpected argument: {arg}", file=sys.stderr)
            usage(sys.stderr)
            return 2
        index += 1

    if path is None:
        header, data = load_rows(csv.reader(io.StringIO(SAMPLE_CSV)))
        source = "embedded sample"
    else:
        try:
            header, data = load_file(path)
        except OSError as exc:
            print(f"error: cannot read {path}: {exc}", file=sys.stderr)
            return 1
        except csv.Error as exc:
            print(f"error: invalid CSV in {path}: {exc}", file=sys.stderr)
            return 1
        source = os.path.basename(path) or path

    build_dashboard(header, data, source, top)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
