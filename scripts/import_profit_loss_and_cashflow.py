"""Import annual P&L and cash-flow workbooks into the project SQLite database.

Only the raw Standalone and Consolidated sheets are imported. Growth % sheets
are omitted; growth should be calculated from the underlying reported values.
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
DB_PATH = ROOT / "database" / "stock_market.db"
CUTOFF_YEAR = 2015

COMPANIES = {
    "bajaj-auto": "Bajaj Auto",
    "eicher-motors": "Eicher Motors",
    "hero-motocorp": "Hero Motocorp",
    "infosys": "Infosys",
    "tcs": "TCS",
    "tvs-motor": "TVS Motors",
}

SOURCES = {
    "profit_loss": {
        "directory": ROOT / "data" / "PL statement",
        "suffix": "profit-loss.xlsx",
        "tables": {
            "Standalone": "profit_loss_standalone",
            "Consolidated": "profit_loss_consolidated",
        },
    },
    "cash_flow": {
        "directory": ROOT / "data" / "cashflow",
        "suffix": "cash-flow.xlsx",
        "tables": {
            "Standalone": "cash_flow_standalone",
            "Consolidated": "cash_flow_consolidated",
        },
    },
}


@dataclass(frozen=True)
class FinancialRow:
    company: str
    period_end_date: str
    period_label: str
    metric_name: str
    value: float
    source_file: str
    source_sheet: str
    source_row: int


def parse_period(label: object) -> tuple[str, int] | None:
    """Parse headers such as 'Mar 26', 'Dec 15', or 'Mar 2016 15m'."""
    value = str(label).strip()
    if value.casefold() in {"ttm", "trailing twelve months"}:
        return None
    match = re.fullmatch(
        r"([A-Za-z]{3})\s+(\d{2}|\d{4})(?:\s+\d{1,2}m)?", value
    )
    if not match:
        raise ValueError(f"Unrecognized annual period header: {label!r}")
    month, year = match.groups()
    parsed = pd.to_datetime(
        f"{month} {year}", format="%b %y" if len(year) == 2 else "%b %Y"
    )
    last_day = calendar.monthrange(parsed.year, parsed.month)[1]
    return f"{parsed.year:04d}-{parsed.month:02d}-{last_day:02d}", parsed.year


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


def source_file(source_key: str, company_key: str) -> Path:
    source = SOURCES[source_key]
    return source["directory"] / f"{company_key}-{source['suffix']}"


def read_source(source_key: str) -> dict[str, list[FinancialRow]]:
    source = SOURCES[source_key]
    missing = [
        str(source_file(source_key, company_key))
        for company_key in COMPANIES
        if not source_file(source_key, company_key).is_file()
    ]
    if missing:
        raise FileNotFoundError("Missing workbook(s):\n" + "\n".join(missing))

    rows_by_table = {table: [] for table in source["tables"].values()}
    for company_key, company in COMPANIES.items():
        path = source_file(source_key, company_key)
        workbook = pd.ExcelFile(path, engine="openpyxl")
        for sheet_name, table_name in source["tables"].items():
            if sheet_name not in workbook.sheet_names:
                raise ValueError(f"{path.name} is missing the '{sheet_name}' sheet")
            frame = pd.read_excel(workbook, sheet_name=sheet_name, header=0)
            if frame.empty or str(frame.columns[0]).strip() != "Indicator":
                raise ValueError(f"{path.name} / {sheet_name} has an unexpected layout")

            periods: list[tuple[object, str, str]] = []
            for label in frame.columns[1:]:
                parsed = parse_period(label)
                if parsed is None:
                    continue
                iso_date, year = parsed
                if year >= CUTOFF_YEAR:
                    periods.append((label, iso_date, str(label).strip()))
            if not periods:
                raise ValueError(
                    f"{path.name} / {sheet_name} has no annual periods from {CUTOFF_YEAR} onward"
                )

            before = len(rows_by_table[table_name])
            for row_number, row in frame.iterrows():
                metric = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else ""
                if not metric:
                    continue
                for column, iso_date, period_label in periods:
                    value = numeric_value(row[column])
                    if value is None:
                        continue
                    rows_by_table[table_name].append(
                        FinancialRow(
                            company=company,
                            period_end_date=iso_date,
                            period_label=period_label,
                            metric_name=metric,
                            value=value,
                            source_file=path.name,
                            source_sheet=sheet_name,
                            source_row=int(row_number) + 2,
                        )
                    )
            if len(rows_by_table[table_name]) == before:
                raise ValueError(f"No numeric values found in {path.name} / {sheet_name}")
        workbook.close()
    return rows_by_table


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


def import_statements(dry_run: bool = False) -> dict[str, int]:
    combined: dict[str, list[FinancialRow]] = {}
    for source_key in SOURCES:
        combined.update(read_source(source_key))
    counts = {table: len(rows) for table, rows in combined.items()}
    if dry_run:
        return counts
    if not DB_PATH.is_file():
        raise FileNotFoundError(f"Database not found at {DB_PATH}; build it before importing statements.")

    companies = tuple(COMPANIES.values())
    placeholders = ",".join("?" for _ in companies)
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("BEGIN")
        for table_name, rows in combined.items():
            create_table(connection, table_name)
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
        description="Import annual P&L and cash-flow statements into SQLite."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate all six pairs of workbooks and report row counts without changing the database.",
    )
    args = parser.parse_args()
    imported = import_statements(dry_run=args.dry_run)
    action = "Validated" if args.dry_run else "Imported"
    for table_name, count in imported.items():
        print(f"{action} {count:,} rows into {table_name}.")
    if not args.dry_run:
        print(f"Database: {DB_PATH}")
