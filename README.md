# Stock Market Analysis with SQL

A Streamlit dashboard for the six historical stock datasets in `data/`, with executive overview, statistical analysis, company research, hypothetical portfolio risk, read-only SQL exploration, and database record management.

## Run locally

```bash
python -m pip install -r requirements.txt
python scripts/create_stock_database.py
streamlit run app.py
```

The database builder reads the CSVs and creates `database/stock_market.db`. It can be rerun whenever the source data changes. The dashboard also builds the database automatically if it is missing or empty.

Benchmark index files belong under `data/benchmark/`, separate from the company CSVs. To import NIFTY 50 and SENSEX history into the `market_indices` table without rebuilding `stock_prices`, run:

```bash
python scripts/create_stock_database.py --benchmarks-only
```

## Analysis notebook and PDF report

Open `reports/Stock_Market_Analysis.ipynb` in Jupyter or VS Code and run the cells from top to bottom. It loads the raw CSVs, cleans and validates them, merges the company datasets, saves the cleaned merged data to `database/stock_market.db`, and performs EDA. The database save cell replaces the existing `stock_prices` table. It includes nine charts: core comparisons plus Univariate, Bivariate, and Multivariate analysis. Each chart has its own code cell. The final cell rebuilds `reports/Stock_Market_Analysis_Insights.pdf` with the charts and written findings.

To refresh the standalone report charts and PDF from the command line, run:

```bash
python scripts/create_insights_report.py
```

To refresh the notebook file and its embedded chart previews after regenerating the report, run:

```bash
python scripts/create_analysis_notebook.py
```

## Project layout

- `app.py` - project landing page with overview, data coverage, and structure.
- `pages/1_Executive_Overview.py` - executive dashboard and company-level performance.
- `pages/2_Statistical_Analysis.py` - return distributions, volatility, and correlations.
- `pages/3_SQL_Playground.py` - interactive, read-only SQL editor.
- `pages/4_CRUD.py` - create, inspect, update, and delete daily records.
- `pages/5_Company_Research.py` - company-level historical price, risk, and trading activity; financial statements and filings are not in the current database.
- `pages/6_Portfolio_Risk.py` - hypothetical buy-and-hold allocations compared with available benchmarks; excludes dividends, corporate actions, fees, taxes, and slippage.
- `scripts/create_stock_database.py` - CSV import and schema creation.
- `sql/stock_market_analysis.sql` - reusable analysis queries.
- `reports/Stock_Market_Analysis.ipynb` - annotated, chart by chart analysis notebook.
- `reports/Stock_Market_Analysis_UBM.ipynb` - notebook copy with the expanded UBM chart sections.
- `scripts/create_insights_report.py` - chart and PDF report generation.
- `data/` - source company CSV files, one per company; benchmark CSVs belong under `data/benchmark/`.
- `database/` - generated SQLite database.
- `reports/` - space for exported charts and the written insights report.

`stock_prices` contains company observations, while `market_indices` contains benchmark OHLC values keyed by index and date. Company prices and turnover are numeric; dates use ISO `YYYY-MM-DD` format.
