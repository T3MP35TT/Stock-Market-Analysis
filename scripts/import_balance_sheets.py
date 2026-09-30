"""Import annual balance-sheet data from the project's Excel workbooks into SQLite.

Only the raw Standalone and Consolidated sheets are imported. Growth % tabs are
intentionally omitted so growth can be calculated from the imported values.
"""

from __future__ import annotations

import argparse
import calendar
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "data" / "balance sheets"
DB_PATH = ROOT / "database" / "stock_market.db"

WORKBOOKS = {
    "bajaj-auto-balance-sheet.xlsx": "Bajaj Auto",
    "eicher-motors-balance-sheet.xlsx": "Eicher Motors",
    "hero-motocorp-balance-sheet.xlsx": "Hero Motocorp",
    "infosys-balance-sheet.xlsx": "Infosys",
    "tcs-balance-sheet.xlsx": "TCS",
    "tvs-motor-balance-sheet.xlsx": "TVS Motors",
}

TABLES = {
    "Standalone": "balance_sheet_standalone",
    "Consolidated": "balance_sheet_consolidated",
}


@dataclass(frozen=True)
class StatementRow:
    company: str
    period_end_date: str
    period_label: str
    metric_name: str
    value: float
    source_file: str
    source_sheet: str
    source_row: int


def period_end_date(label: object) -> str:
    """Convert workbook headers such as 'Mar 26' into an ISO period-end date."""
    match = re.fullmatch(r"\s*([A-Za-z]{3})\s+(\d{2}|\d{4})\s*", str(label))
    if not match:
        raise ValueError(f"Unrecognized financial period header: {label!r}")
    month, year = match.groups()
    parsed = pd.to_datetime(f"{month} {year}", format="%b %y" if len(year) == 2 else "%b %Y")
    last_day = calendar.monthrange(parsed.year, parsed.month)[1]
    return f"{parsed.year:04d}-{parsed.month:02d}-{last_day:02d}"


def numeric_value(value: object) -> float | None:
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip().replace(",", "").replace("%", "")
        if not value or value in {"-", "—", "–", "N/A", "NA"}:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def read_workbooks(cutoff_year: int) -> dict[str, list[StatementRow]]:
    """Read and validate all expected files before making any database changes."""
    missing = [filename for filename in WORKBOOKS if not (SOURCE_DIR / filename).is_file()]
    if missing:
        raise FileNotFoundError(
            "Missing balance-sheet workbook(s): " + ", ".join(missing)
            + f" in {SOURCE_DIR}"
        )

    result: dict[str, list[StatementRow]] = {table: [] for table in TABLES.values()}
    for filename, company in WORKBOOKS.items():
        path = SOURCE_DIR / filename
        workbook = pd.ExcelFile(path, engine="openpyxl")
        for sheet_name, table_name in TABLES.items():
            if sheet_name not in workbook.sheet_names:
                raise ValueError(f"{filename} is missing the required '{sheet_name}' sheet")
            frame = pd.read_excel(workbook, sheet_name=sheet_name, header=0)
            if frame.empty or frame.columns[0] != "Indicator":
                raise ValueError(f"{filename} / {sheet_name} has an unexpected layout")

            periods: list[tuple[object, str]] = []
            for label in frame.columns[1:]:
                iso_date = period_end_date(label)
                if int(iso_date[:4]) >= cutoff_year:
                    periods.append((label, iso_date))
            if not periods:
                raise ValueError(f"{filename} / {sheet_name} has no periods from {cutoff_year} onward")

            imported_before = len(result[table_name])
            for row_number, row in frame.iterrows():
                metric_name = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                if not metric_name:
                    continue
                for label, iso_date in periods:
                    value = numeric_value(row[label])
                    if value is None:
                        continue
                    result[table_name].append(
                        StatementRow(
                            company=company,
                            period_end_date=iso_date,
                            period_label=str(label).strip(),
                            metric_name=metric_name,
                            value=value,
                            source_file=filename,
                            source_sheet=sheet_name,
                            source_row=int(row_number) + 2,
                        )
                    )
            if len(result[table_name]) == imported_before:
                raise ValueError(f"No numeric data found in {filename} / {sheet_name}")
        workbook.close()
    return result


def create_table(connection: sqlite3.Connection, table_name: str) -> None:
    connection.execute(
        f"""CREATE TABLE IF NOT EXISTS {table_name} (
            company TEXT NOT NULL,
            period_end_date TEXT NOT NULL,
            period_label TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            value REAL NOT NULL,
            source_file TEXT NOT NULL,
            source_sheet TEXT NOT NULL,
            source_row INTEGER NOT NULL,
            PRIMARY KEY (company, period_end_date, source_row)
        )"""
    )
    connection.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{table_name}_company_period "
        f"ON {table_name}(company, period_end_date)"
    )


def import_balance_sheets(cutoff_year: int = 2015, dry_run: bool = False) -> dict[str, int]:
    if cutoff_year < 1900 or cutoff_year > 9998:
        raise ValueError("Cutoff year must be a valid four-digit year")
    rows_by_table = read_workbooks(cutoff_year)
    counts = {table: len(rows) for table, rows in rows_by_table.items()}
    if dry_run:
        return counts
    if not DB_PATH.is_file():
        raise FileNotFoundError(f"Database not found at {DB_PATH}; build the stock database first.")

    companies = tuple(WORKBOOKS.values())
    placeholders = ",".join("?" for _ in companies)
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("BEGIN")
        for table_name, rows in rows_by_table.items():
            create_table(connection, table_name)
            # Replace these six companies' statement history so reruns are safe and
            # old rows outside the requested cutoff cannot linger in the tables.
            connection.execute(
                f"DELETE FROM {table_name} WHERE company IN ({placeholders})", companies
            )
            connection.executemany(
                f"""INSERT INTO {table_name} (
                    company, period_end_date, period_label, metric_name, value,
                    source_file, source_sheet, source_row
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    (
                        row.company, row.period_end_date, row.period_label,
                        row.metric_name, row.value, row.source_file,
                        row.source_sheet, row.source_row,
                    )
                    for row in rows
                ],
            )
        connection.commit()
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import standalone and consolidated balance sheets into SQLite."
    )
    parser.add_argument(
        "--cutoff-year", type=int, default=2015,
        help="Keep periods whose calendar year is this year or later (default: 2015).",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Read and validate workbooks and report row counts without changing the database.",
    )
    args = parser.parse_args()
    imported = import_balance_sheets(args.cutoff_year, args.dry_run)
    action = "Validated" if args.dry_run else "Imported"
    for table_name, count in imported.items():
        print(f"{action} {count:,} rows into {table_name}.")
    if not args.dry_run:
        print(f"Database: {DB_PATH}")
