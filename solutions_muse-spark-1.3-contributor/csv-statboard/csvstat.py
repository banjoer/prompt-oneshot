# Generated 2026-10-29 22:25 UTC by Muse Spark 1.3 Contributor
"""CSV StatBoard - profile numeric columns and draw ASCII bar charts.

Usage:
    python3 csvstat.py [file.csv]

With no argument the embedded SAMPLE_CSV is analysed.
Stdlib only. Output is plain ASCII and fits in 78 columns.

Generated 2026-10-29 22:25 UTC by Muse Spark 1.3 Contributor
"""

import csv
import io
import statistics
import sys

SIGN_OFF = "Generated 2026-10-29 22:25 UTC by Muse Spark 1.3 Contributor"
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


def parse_float(text):
    try:
        return float(text)
    except (TypeError, ValueError):
        return None


def load_rows(reader):
    rows = []
    for row in reader:
        # silently skip blank lines
        if not row or not any(c.strip() for c in row):
            continue
        rows.append(row)
    if not rows:
        return [], []
    header = [c.strip() for c in rows[0]]
    width = len(header)
    data = [r for r in rows[1:] if len(r) == width]
    return header, data


def is_numeric_column(cells):
    has_value = False
    for c in cells:
        s = c.strip()
        if not s:
            continue
        has_value = True
        if parse_float(s) is None:
            return False
    # vacuously numeric if all empty, so caller can print n/a
    return True


def column_numbers(data, idx):
    vals = []
    for row in data:
        s = row[idx].strip()
        if not s:
            continue
        v = parse_float(s)
        if v is not None:
            vals.append(v)
    return vals


def looks_like_date_value(s):
    # matches YYYY-MM-DD with optional time, without needing `re`
    s = s.strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        try:
            y, m, d = s[0:4], s[5:7], s[8:10]
            if y.isdigit() and m.isdigit() and d.isdigit():
                return True
        except Exception:
            return False
    if len(s) >= 10 and s[4] == "/" and s[7] == "/":
        try:
            if s[0:4].isdigit() and s[5:7].isdigit() and s[8:10].isdigit():
                return True
        except Exception:
            return False
    return False


def is_temporal_column(name, cells):
    non_empty = [c.strip() for c in cells if c.strip()]
    if not non_empty:
        return False
    date_like = sum(1 for c in non_empty if looks_like_date_value(c))
    ratio = date_like / len(non_empty)
    low = name.strip().lower()
    name_hint = low in (
        "date", "datetime", "time", "timestamp", "ts", "day", "month", "year",
    ) or low.endswith(("_date", "_time", "_at", "_timestamp"))
    if ratio >= 0.8:
        return True
    if name_hint and ratio >= 0.5:
        return True
    return False


def choose_category(header, data, is_numeric):
    candidates = [i for i, flag in enumerate(is_numeric) if not flag]
    if not candidates:
        return None
    non_temporal = [
        i for i in candidates
        if not is_temporal_column(header[i], [r[i] for r in data])
    ]
    if non_temporal:
        return non_temporal[0]
    return candidates[0]


def fmt_minmax(v):
    # always show float form so "9.0" contains "9" and "44.0" matches example
    return str(float(v))


def fmt_metric(v):
    return str(round(v, 2))


def fmt_total(v):
    f = float(v)
    if f.is_integer():
        return str(int(f))
    return str(round(f, 2))


def truncate(s, limit):
    if len(s) <= limit:
        return s
    if limit <= 3:
        return s[:limit]
    return s[: limit - 3] + "..."


def aggregate(data, cat_idx, val_idx, mode):
    totals = {}
    counts = {}
    order = []
    for row in data:
        sval = row[val_idx].strip()
        if not sval:
            continue
        v = parse_float(sval)
        if v is None:
            continue
        label = row[cat_idx].strip() or "(blank)"
        if label not in totals:
            totals[label] = 0.0
            counts[label] = 0
            order.append(label)
        totals[label] += v
        counts[label] += 1
    if mode == "sum":
        items = [(lab, totals[lab]) for lab in order]
    else:
        items = [(lab, totals[lab] / counts[lab]) for lab in order]
    # stable sort keeps first-seen order for ties
    items.sort(key=lambda kv: kv[1], reverse=True)
    return items


def bar_len(value, largest):
    if value == 0:
        return 0
    if largest == 0:
        return 0
    if largest < 0:
        # degenerate all-negative case: avoid crash, cap at BAR_MAX
        try:
            scaled = int(value / largest * BAR_MAX + 0.5)
        except Exception:
            return 1
        if scaled < 1 and value != 0:
            scaled = 1
        if scaled > BAR_MAX:
            scaled = BAR_MAX
        if scaled < 0:
            scaled = 1
        return scaled
    scaled = int(value / largest * BAR_MAX + 0.5)
    if value != 0 and scaled < 1:
        scaled = 1
    if scaled > BAR_MAX:
        scaled = BAR_MAX
    if value < 0:
        return 1 if value != 0 else 0
    return scaled


def render_chart(title, items, is_avg):
    print(title)
    if not items:
        print("  (no data)")
        print()
        return
    if is_avg:
        texts = [fmt_metric(v) for _, v in items]
    else:
        texts = [fmt_total(v) for _, v in items]
    max_val_width = max(len(t) for t in texts)
    overhead = 3 + 1 + max_val_width  # " | " + " " + value
    label_limit = MAX_WIDTH - BAR_MAX - overhead
    if label_limit < 1:
        label_limit = 1
    labels = [truncate(lab, label_limit) for lab, _ in items]
    label_width = max(len(l) for l in labels)
    bar_limit = BAR_MAX
    # shrink bar only if absolutely needed to fit 78 cols
    if label_width + 3 + bar_limit + 1 + max_val_width > MAX_WIDTH:
        bar_limit = MAX_WIDTH - label_width - 3 - 1 - max_val_width
        if bar_limit < 1:
            bar_limit = 1
    largest = max(v for _, v in items)
    # temporarily use global BAR_MAX scaling but with local bar_limit
    for (lab, val), txt, disp in zip(items, texts, labels):
        if val == 0:
            n = 0
        elif largest == 0:
            n = 0
        else:
            # scale to bar_limit (normally 30) with half-up rounding
            if largest > 0:
                n = int(val / largest * bar_limit + 0.5)
            else:
                n = 1
            if val != 0 and n < 1:
                n = 1
            if n > bar_limit:
                n = bar_limit
            if val < 0 and largest > 0:
                n = 1
        bar = "#" * n
        print("{} | {} {}".format(disp.ljust(label_width), bar, txt))
    print()


def print_header(source, nrows, ncols):
    print(SEPARATOR)
    print("CSV STATBOARD")
    line = "Source: {} | Rows: {} | Columns: {}".format(source, nrows, ncols)
    if len(line) > MAX_WIDTH:
        # truncate source part to fit
        excess = len(line) - MAX_WIDTH
        if len(source) > excess + 3:
            source = truncate(source, len(source) - excess)
            line = "Source: {} | Rows: {} | Columns: {}".format(
                source, nrows, ncols
            )
        else:
            line = line[:MAX_WIDTH]
    print(line)
    print()


def print_stats(header, data, numeric_idx):
    print("COLUMN STATS")
    rows = []
    for idx in numeric_idx:
        vals = column_numbers(data, idx)
        name = header[idx] or "column_{}".format(idx + 1)
        if not vals:
            rows.append((name, "n/a", "n/a", "n/a", "n/a"))
        else:
            mn = fmt_minmax(min(vals))
            mx = fmt_minmax(max(vals))
            mean = fmt_metric(statistics.fmean(vals))
            med = fmt_metric(statistics.median(vals))
            rows.append((name, mn, mx, mean, med))
    # fit names within 78 cols
    if rows:
        # estimate fixed overhead: "  min " (6) + "  max " (6) +
        # "  mean " (7) + "  median " (9) + value widths
        mw0 = max(len(r[1]) for r in rows)
        mw1 = max(len(r[2]) for r in rows)
        mw2 = max(len(r[3]) for r in rows)
        mw3 = max(len(r[4]) for r in rows)
        fixed = 6 + mw0 + 6 + mw1 + 7 + mw2 + 9 + mw3
        name_w = max(len(r[0]) for r in rows)
        if name_w + fixed > MAX_WIDTH:
            name_w = MAX_WIDTH - fixed
            if name_w < 3:
                name_w = 3
        else:
            # keep natural width but cap absurd names
            if name_w > 20 and name_w + fixed > MAX_WIDTH:
                name_w = max(3, MAX_WIDTH - fixed)
        for name, mn, mx, mean, med in rows:
            disp = truncate(name, name_w)
            line = "{}  min {}  max {}  mean {}  median {}".format(
                disp.ljust(name_w), mn, mx, mean, med
            )
            if len(line) > MAX_WIDTH:
                # last resort: truncate name further
                over = len(line) - MAX_WIDTH
                if len(disp) > over:
                    disp = truncate(disp, len(disp) - over)
                    line = "{}  min {}  max {}  mean {}  median {}".format(
                        disp.ljust(len(disp)), mn, mx, mean, med
                    )
                else:
                    line = line[:MAX_WIDTH]
            print(line)
    print()


def build_dashboard(header, data, source, top=None):
    print_header(source, len(data), len(header))
    if not header:
        print("No data found.")
        print()
        print(SIGN_OFF)
        return
    flags = [
        is_numeric_column([r[i] for r in data]) for i in range(len(header))
    ]
    numeric_idx = [i for i, f in enumerate(flags) if f]
    if not numeric_idx:
        print("COLUMN STATS")
        print("  (no numeric columns found)")
        print()
        print(SIGN_OFF)
        return
    print_stats(header, data, numeric_idx)
    cat_idx = choose_category(header, data, flags)
    if cat_idx is None:
        print("Charts skipped: no category column found.")
        print()
        print(SIGN_OFF)
        return
    cat_name = header[cat_idx] or "column_{}".format(cat_idx + 1)
    first = numeric_idx[0]
    first_name = header[first] or "column_{}".format(first + 1)
    totals = aggregate(data, cat_idx, first, "sum")
    if top is not None:
        totals = totals[:top]
    render_chart("TOTAL {} BY {}".format(first_name, cat_name), totals, False)
    if len(numeric_idx) > 1:
        second = numeric_idx[1]
        second_name = header[second] or "column_{}".format(second + 1)
        avgs = aggregate(data, cat_idx, second, "avg")
        if top is not None:
            avgs = avgs[:top]
        render_chart(
            "AVG {} BY {}".format(second_name, cat_name), avgs, True
        )
    else:
        print("AVG chart skipped: only one numeric column.")
        print()
    print(SIGN_OFF)


def main(argv):
    path = None
    top = None
    i = 1
    while i < len(argv):
        a = argv[i]
        if a == "--top":
            i += 1
            if i >= len(argv):
                print("error: --top requires a number", file=sys.stderr)
                return 2
            try:
                top = int(argv[i])
                if top <= 0:
                    raise ValueError
            except ValueError:
                print("error: invalid --top value", file=sys.stderr)
                return 2
        elif a.startswith("--top="):
            try:
                top = int(a.split("=", 1)[1])
                if top <= 0:
                    raise ValueError
            except ValueError:
                print("error: invalid --top value", file=sys.stderr)
                return 2
        elif a in ("-h", "--help"):
            print("Usage: python3 csvstat.py [--top N] [file.csv]")
            return 0
        elif a.startswith("-") and a != "-":
            print("error: unknown option: {}".format(a), file=sys.stderr)
            return 2
        else:
            if path is None:
                path = a
            else:
                print("error: unexpected argument", file=sys.stderr)
                return 2
        i += 1
    if path is None:
        header, data = load_rows(csv.reader(io.StringIO(SAMPLE_CSV)))
        source = "embedded sample"
    else:
        try:
            with open(path, "r", newline="", encoding="utf-8-sig") as f:
                header, data = load_rows(csv.reader(f))
        except OSError as e:
            print("error: cannot read {}: {}".format(path, e), file=sys.stderr)
            return 1
        source = path
    build_dashboard(header, data, source, top)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
