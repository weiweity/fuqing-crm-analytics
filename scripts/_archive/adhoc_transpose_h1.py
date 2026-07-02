#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""将 adhoc_daily_segments_2026h1.py 生成的日指标 CSV 转置为：
行=指标，列=日期。"""
import csv
import sys
from pathlib import Path

IN_DIR = Path("/Users/hutou/Desktop/fuqin date/取数/2026年/2026年7月2日/2026年-2026年7月2日-H1日指标")
OUT_DIR = IN_DIR

PERIODS = [
    ("2026-01-01_2026-06-30", "Y26 H1日指标"),
    ("2025-01-01_2025-06-30", "Y25 H1日指标"),
]

METRIC_LABELS = [
    "小样GMV",
    "小样GSV",
    "会员GMV",
    "会员GSV",
    "新客人数",
    "新客GSV",
    "老客人数",
    "老客GSV",
]


def transpose_period(in_csv: Path, out_csv: Path) -> None:
    dates: list[str] = []
    rows_by_metric: dict[str, list[str]] = {label: [label] for label in METRIC_LABELS}

    with in_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            dates.append(row["日期"])
            for label in METRIC_LABELS:
                rows_by_metric[label].append(row[label])

    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        header = ["指标"] + dates
        writer.writerow(header)
        for label in METRIC_LABELS:
            writer.writerow(rows_by_metric[label])


def main() -> None:
    for period_file, period_label in PERIODS:
        in_csv = IN_DIR / f"daily_segment_{period_file}.csv"
        out_csv = OUT_DIR / f"transposed_daily_segment_{period_file}.csv"
        if not in_csv.exists():
            print(f"[WARN] {in_csv} not found, skip", file=sys.stderr)
            continue
        transpose_period(in_csv, out_csv)
        print(f"Transposed: {out_csv}")


if __name__ == "__main__":
    main()
