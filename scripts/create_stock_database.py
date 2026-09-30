"""Build the SQLite database from all CSV files in the project's data folder."""

from __future__ import annotations

import csv
import argparse
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
BENCHMARK_DIR = DATA_DIR / "benchmark"
DB_PATH = ROOT / "database" / "stock_market.db"


def safe_company_name(filename: str) -> str:
    return re.sub(r"\s+", " ", Path(filename).stem).strip()


def parse_number(value: str | None):
    if value is None or not value.strip():
        return None
    cleaned = value.strip().replace(",", "").replace("%", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def parse_date(value: str | None):
    if not value:
        return None
    from datetime import datetime

    for fmt in ("%d-%B-%Y", "%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), fmt).date().isoformat()
        except ValueError:
            continue
    return value.strip()


def benchmark_name(filename: str) -> str:
    name = Path(filename).stem.lower()
    if "nifty" in name:
        return "NIFTY 50"
    if "sensex" in name:
        return "SENSEX"
    return re.sub(r"\s+", " ", Path(filename).stem).strip()


def _load_benchmark_csvs(conn: sqlite3.Connection) -> int:
    files = sorted(BENCHMARK_DIR.glob("*.csv"))
    if not files:
        return 0

    conn.execute(
        """CREATE TABLE IF NOT EXISTS market_indices (
            index_name TEXT NOT NULL,
            date TEXT NOT NULL,
            open_value REAL,
            high_value REAL,
            low_value REAL,
            close_value REAL NOT NULL,
            change_pct REAL,
            PRIMARY KEY (index_name, date)
        )"""
    )
    count = 0
    for path in files:
        index_name = benchmark_name(path.name)
        conn.execute("DELETE FROM market_indices WHERE index_name = ?", (index_name,))
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                normalized = {str(key).strip().lower(): value for key, value in row.items() if key}
                date = parse_date(normalized.get("date"))
                close = parse_number(normalized.get("price") or normalized.get("close") or normalized.get("close price"))
                if not date or close is None:
                    continue
                conn.execute(
                    """INSERT OR REPLACE INTO market_indices
                    (index_name, date, open_value, high_value, low_value, close_value, change_pct)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        index_name,
                        date,
                        parse_number(normalized.get("open")),
                        parse_number(normalized.get("high")),
                        parse_number(normalized.get("low")),
                        close,
                        parse_number(normalized.get("change %") or normalized.get("change_pct")),
                    ),
                )
                count += 1
    conn.execute("CREATE INDEX IF NOT EXISTS idx_market_indices_date ON market_indices(date, index_name)")
    return count


def import_benchmarks() -> int:
    """Import benchmark CSVs without rebuilding or modifying stock_prices."""
    if not BENCHMARK_DIR.exists() or not list(BENCHMARK_DIR.glob("*.csv")):
        raise FileNotFoundError(f"No benchmark CSV files found in {BENCHMARK_DIR}")
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Stock database not found at {DB_PATH}; build it before importing benchmarks.")
    with sqlite3.connect(DB_PATH) as conn:
        count = _load_benchmark_csvs(conn)
        conn.commit()
    return count


def build_database() -> int:
    files = sorted(DATA_DIR.glob("*.csv"))
    if not files:
        raise FileNotFoundError(f"No CSV files found in {DATA_DIR}")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DROP TABLE IF EXISTS stock_prices")
        conn.execute(
            """CREATE TABLE stock_prices (
                id INTEGER PRIMARY KEY,
                company TEXT NOT NULL,
                date TEXT NOT NULL,
                open_price REAL, high_price REAL, low_price REAL, close_price REAL,
                wap REAL, shares_traded REAL, trades REAL, turnover REAL,
                deliverable_quantity REAL, deliverable_pct REAL,
                spread_high_low REAL, spread_close_open REAL
            )"""
        )
        count = 0
        for path in files:
            company = safe_company_name(path.name)
            with path.open("r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    conn.execute(
                        """INSERT INTO stock_prices (
                            company,date,open_price,high_price,low_price,close_price,wap,
                            shares_traded,trades,turnover,deliverable_quantity,deliverable_pct,
                            spread_high_low,spread_close_open
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            company,
                            parse_date(row.get("Date")),
                            parse_number(row.get("Open Price")),
                            parse_number(row.get("High Price")),
                            parse_number(row.get("Low Price")),
                            parse_number(row.get("Close Price")),
                            parse_number(row.get("WAP")),
                            parse_number(row.get("No.of Shares")),
                            parse_number(row.get("No. of Trades")),
                            parse_number(row.get("Total Turnover (Rs.)")),
                            parse_number(row.get("Deliverable Quantity")),
                            parse_number(row.get("% Deli. Qty to Traded Qty")),
                            parse_number(row.get("Spread High-Low")),
                            parse_number(row.get("Spread Close-Open")),
                        ),
                    )
                    count += 1
        conn.execute("CREATE INDEX idx_stock_company_date ON stock_prices(company, date)")
        _load_benchmark_csvs(conn)
        conn.commit()
    return count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build the stock database or import benchmark index CSVs.")
    parser.add_argument(
        "--benchmarks-only",
        action="store_true",
        help="Import data/benchmark/*.csv into market_indices without rebuilding stock_prices.",
    )
    args = parser.parse_args()
    if args.benchmarks_only:
        rows = import_benchmarks()
        print(f"Imported {rows:,} benchmark rows into {DB_PATH}.")
    else:
        rows = build_database()
        print(f"Created {DB_PATH} with {rows:,} rows from {len(list(DATA_DIR.glob('*.csv')))} CSV files.")
