"""Combine each stock's gap-period CSV chunks into one CSV; never touches SQLite."""

from __future__ import annotations

import csv
from collections import Counter
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "gap data"
OUTPUT_DIR = INPUT_DIR / "combined_by_stock"
COMPANIES = ("Bajaj Auto", "Eicher Motors", "Hero Motocorp", "Infosys", "TCS", "TVS Motors")
HEADERS = (
    "Date", "Open Price", "High Price", "Low Price", "Close Price", "WAP",
    "No.of Shares", "No. of Trades", "Total Turnover (Rs.)", "Deliverable Quantity",
    "% Deli. Qty to Traded Qty", "Spread High-Low", "Spread Close-Open",
)


def parse_date(raw: str) -> date:
    for fmt in ("%d-%B-%Y", "%d-%b-%Y", "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            pass
    raise ValueError(f"Unrecognized date: {raw!r}")


def company_for(path: Path) -> str | None:
    stem = path.stem
    name = stem.split("(", 1)[0].strip()
    return name if name in COMPANIES else None


def numeric_value(raw: str) -> Decimal | None:
    cleaned = raw.strip().replace(",", "").replace("%", "")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def rows_equal_or_complement(old: dict[str, str], new: dict[str, str], label: str, day: str) -> dict[str, str]:
    merged = dict(old)
    for field in HEADERS[1:]:
        left, right = old[field].strip(), new[field].strip()
        if left and right:
            a, b = numeric_value(left), numeric_value(right)
            if a is not None and b is not None:
                equal = a == b
            else:
                equal = left == right
            if not equal:
                raise ValueError(f"Conflicting duplicate {label} record on {day}, field {field!r}")
        elif right:
            merged[field] = right
    return merged


def main() -> None:
    paths = sorted(INPUT_DIR.glob("*.csv"))
    if not paths:
        raise FileNotFoundError(f"No source CSVs found in {INPUT_DIR}")

    records: dict[str, dict[str, dict[str, str]]] = {name: {} for name in COMPANIES}
    files_seen: Counter[str] = Counter()
    source_rows: Counter[str] = Counter()
    duplicates: Counter[str] = Counter()

    for path in paths:
        company = company_for(path)
        if company is None:
            raise ValueError(f"Cannot identify stock from filename: {path.name}")
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != HEADERS:
                raise ValueError(f"Headers do not match the stock schema in {path.name}: {reader.fieldnames}")
            row_count = 0
            for raw in reader:
                parsed_day = parse_date(raw.get("Date") or "")
                day = parsed_day.isoformat()
                row = {field: (raw.get(field) or "").strip() for field in HEADERS}
                row["Date"] = f"{parsed_day.day}-{parsed_day.strftime('%B-%Y')}"
                if day in records[company]:
                    duplicates[company] += 1
                    records[company][day] = rows_equal_or_complement(records[company][day], row, company, day)
                else:
                    records[company][day] = row
                source_rows[company] += 1
                row_count += 1
            if row_count == 0:
                raise ValueError(f"No records in {path.name}")
            files_seen[company] += 1

    missing_companies = [name for name in COMPANIES if not records[name]]
    if missing_companies:
        raise ValueError(f"No gap data found for: {', '.join(missing_companies)}")

    date_sets = {name: set(records[name]) for name in COMPANIES}
    date_union = set.union(*date_sets.values())
    date_intersection = set.intersection(*date_sets.values())

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    report = [
        "# Combined gap-period CSV validation",
        "",
        "Combined from `data/gap data/*.csv`; original input chunks are preserved.",
        "This process does not use or modify the SQLite database.",
        "All outputs keep the existing 13 stock-data headers.",
        "",
        "| Stock | Files | Input rows | Unique output rows | First date | Last date | Duplicate rows merged | Rows missing values |",
        "|---|---:|---:|---:|---|---|---:|---:|",
    ]
    for company in COMPANIES:
        sorted_days = sorted(records[company])
        rows = [records[company][day] for day in sorted_days]
        first_label = datetime.strptime(sorted_days[0], "%Y-%m-%d").strftime("%d-%m-%Y")
        last_label = datetime.strptime(sorted_days[-1], "%Y-%m-%d").strftime("%d-%m-%Y")
        output_path = OUTPUT_DIR / f"{company}({first_label} - {last_label}).csv"
        with output_path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=HEADERS)
            writer.writeheader()
            writer.writerows(rows)
        rows_with_missing = sum(any(not row[field] for field in HEADERS[1:]) for row in rows)
        report.append(
            f"| {company} | {files_seen[company]} | {source_rows[company]:,} | {len(rows):,} | "
            f"{sorted_days[0]} | {sorted_days[-1]} | {duplicates[company]} | {rows_with_missing} |"
        )

    report.extend([
        "",
        f"Distinct dates present for all six stocks: {len(date_intersection):,}.",
        f"Dates present for some but not all stocks: {len(date_union - date_intersection):,}.",
        "",
        "## Blank cells by stock and field",
        "",
    ])
    any_blanks = False
    for company in COMPANIES:
        field_counts = Counter(
            field
            for row in records[company].values()
            for field in HEADERS[1:]
            if not row[field]
        )
        nonzero = [f"{field}: {count}" for field, count in field_counts.items() if count]
        if nonzero:
            any_blanks = True
            report.append(f"- {company}: " + "; ".join(nonzero))
    if not any_blanks:
        report.append("None.")
    report.append("")

    (OUTPUT_DIR / "VALIDATION.md").write_text("\n".join(report), encoding="utf-8")
    print(f"Created one CSV per stock in {OUTPUT_DIR}")
    print(f"Dates shared across all six: {len(date_intersection):,}; dates missing for at least one stock: {len(date_union - date_intersection):,}.")
    print("SQLite was not modified.")


if __name__ == "__main__":
    main()
