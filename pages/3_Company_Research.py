"""Company-level historical market research from the available daily price database."""

import sqlite3

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from scripts.create_stock_database import DB_PATH, build_database
from scripts.dashboard_theme import apply_sidebar_theme, render_page_hero, render_sidebar_insights

st.set_page_config(page_title="Company Research | Stock Market Analysis", page_icon="🔎", layout="wide")
apply_sidebar_theme("Company research", "Review historical price performance, risk, and trading activity for one company.")
render_page_hero(
    "Equity research workspace / company",
    "Company research",
    "Explore a company's historical market performance, trading activity, and risk against NIFTY 50 and SENSEX.",
)

if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
    build_database()

with sqlite3.connect(DB_PATH) as connection:
    stocks = pd.read_sql_query("SELECT * FROM stock_prices", connection, parse_dates=["date"])
    try:
        benchmarks = pd.read_sql_query(
            "SELECT index_name, date, close_value FROM market_indices",
            connection,
            parse_dates=["date"],
        )
    except sqlite3.OperationalError:
        benchmarks = pd.DataFrame(columns=["index_name", "date", "close_value"])

if stocks.empty:
    st.warning("No stock records are available in the database.")
    st.stop()

stocks = stocks.dropna(subset=["company", "date", "close_price"]).sort_values(["company", "date"]).copy()
companies = sorted(stocks.company.unique())
min_date, max_date = stocks.date.min().date(), stocks.date.max().date()

with st.container(border=True):
    company_col, benchmark_col, dates_col = st.columns([1, 1, 2])
    company = company_col.selectbox("Company", companies, key="research_company")
    benchmark_names = sorted(benchmarks.index_name.dropna().unique()) if not benchmarks.empty else []
    selected_benchmark = benchmark_col.selectbox(
        "Benchmark for relative metrics",
        benchmark_names,
        index=benchmark_names.index("NIFTY 50") if "NIFTY 50" in benchmark_names else 0,
        key="research_benchmark",
    ) if benchmark_names else None
    date_range = dates_col.date_input(
        "Analysis period", value=(min_date, max_date), min_value=min_date, max_value=max_date,
        key="research_date_range",
    )

if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

company_history = stocks[stocks.company == company].copy()
company_history["daily_return_pct"] = company_history.close_price.pct_change() * 100
period_data = company_history[company_history.date.dt.date.between(start_date, end_date)].copy()
if period_data.empty:
    st.info("No observations match this company and date range.")
    st.stop()

period_data["drawdown_pct"] = (
    period_data.close_price / period_data.close_price.cummax() - 1
) * 100
period_return = (period_data.close_price.iloc[-1] / period_data.close_price.iloc[0] - 1) * 100 if len(period_data) > 1 else np.nan
period_returns = period_data.close_price.pct_change().dropna() * 100
period_volatility = period_returns.std() * np.sqrt(252) if len(period_returns) > 1 else np.nan
period_drawdown = period_data.drawdown_pct.min()
average_turnover = period_data.turnover.mean() if "turnover" in period_data else np.nan
latest = period_data.iloc[-1]

benchmark_return = np.nan
company_common_return = np.nan
benchmark_correlation = np.nan
benchmark_beta = np.nan
if selected_benchmark:
    benchmark_period = benchmarks[
        (benchmarks.index_name == selected_benchmark)
        & benchmarks.date.dt.date.between(start_date, end_date)
    ][["date", "close_value"]].dropna().sort_values("date")
    paired_closes = period_data[["date", "close_price"]].merge(benchmark_period, on="date", how="inner")
    if len(paired_closes) > 1 and paired_closes.close_value.iloc[0] > 0:
        company_common_return = (paired_closes.close_price.iloc[-1] / paired_closes.close_price.iloc[0] - 1) * 100
        benchmark_return = (paired_closes.close_value.iloc[-1] / paired_closes.close_value.iloc[0] - 1) * 100
        aligned_returns = paired_closes.set_index("date").pct_change().dropna()
        if len(aligned_returns) > 1:
            stock_returns = aligned_returns.close_price
            index_returns = aligned_returns.close_value
            benchmark_correlation = stock_returns.corr(index_returns)
            index_variance = index_returns.var()
            benchmark_beta = stock_returns.cov(index_returns) / index_variance if index_variance > 0 else np.nan
excess_return = company_common_return - benchmark_return if np.isfinite(benchmark_return) else np.nan

with st.container(border=True):
    st.subheader(f"{company} · historical snapshot")
    st.caption(f"{start_date:%d %b %Y} to {end_date:%d %b %Y} · {len(period_data):,} trading observations")
    first_kpis = st.columns(3)
    first_kpis[0].metric("Price return", f"{period_return:+.2f}%" if np.isfinite(period_return) else "n/a")
    first_kpis[1].metric(f"Excess vs {selected_benchmark or 'benchmark'}", f"{excess_return:+.2f} pp" if np.isfinite(excess_return) else "n/a")
    first_kpis[2].metric("Latest close", f"Rs. {latest.close_price:,.2f}")
    second_kpis = st.columns(3)
    second_kpis[0].metric("Annualized volatility", f"{period_volatility:.2f}%" if np.isfinite(period_volatility) else "n/a")
    second_kpis[1].metric("Maximum drawdown", f"{period_drawdown:.2f}%" if pd.notna(period_drawdown) else "n/a")
    second_kpis[2].metric("Average daily turnover", f"Rs. {average_turnover / 10_000_000:,.2f} cr" if pd.notna(average_turnover) else "n/a")
    st.caption("Price return uses the first and last available closes; it excludes dividends and corporate-action adjustments. Drawdown is measured from the running peak within this analysis period.")

with st.container(border=True):
    st.subheader("Relative price performance")
    indexed = period_data[["date", "close_price"]].copy()
    if indexed.close_price.iloc[0] == 0:
        st.info("Cannot index this price series because its first close is zero.")
    else:
        indexed["indexed_close"] = indexed.close_price / indexed.close_price.iloc[0] * 100
        indexed["series"] = company
        chart_rows = [indexed[["date", "series", "indexed_close"]]]
        if not benchmarks.empty:
            selected_benchmarks = benchmarks[
                benchmarks.date.dt.date.between(start_date, end_date)
            ].sort_values(["index_name", "date"]).copy()
            selected_benchmarks["indexed_close"] = (
                selected_benchmarks.close_value
                / selected_benchmarks.groupby("index_name").close_value.transform("first")
                * 100
            )
            selected_benchmarks = selected_benchmarks.rename(columns={"index_name": "series"})
            chart_rows.append(selected_benchmarks[["date", "series", "indexed_close"]])
        chart_data = pd.concat(chart_rows, ignore_index=True)
        fig = px.line(
            chart_data, x="date", y="indexed_close", color="series",
            labels={"date": "Date", "indexed_close": "Indexed close (first close = 100)", "series": "Company / benchmark"},
            color_discrete_map={"NIFTY 50": "#ffd166", "SENSEX": "#ff6b6b"},
        )
        fig.add_hline(y=100, line_color="#8296af", line_dash="dot", line_width=1)
        fig.update_layout(hovermode="x unified", legend_title_text="Company / benchmark", margin=dict(t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Each series starts at 100 using its first available close in the selected period. Returns are price-only and exclude dividends and corporate-action adjustments.")

left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("Drawdown")
        drawdown_chart = px.line(
            period_data, x="date", y="drawdown_pct",
            labels={"date": "Date", "drawdown_pct": "Drawdown from prior peak (%)"},
        )
        drawdown_chart.add_hline(y=0, line_color="#8296af", line_dash="dot", line_width=1)
        drawdown_chart.update_layout(showlegend=False, margin=dict(t=20, b=10))
        st.plotly_chart(drawdown_chart, use_container_width=True)
with right:
    with st.container(border=True):
        st.subheader("Monthly turnover")
        if "turnover" not in period_data:
            st.info("Turnover data is not available in the stock table.")
        else:
            monthly = period_data.assign(month=period_data.date.dt.to_period("M").dt.to_timestamp())
            monthly = monthly.groupby("month", as_index=False).turnover.sum(min_count=1)
            monthly["turnover_crore"] = monthly.turnover / 10_000_000
            fig = px.bar(
                monthly, x="month", y="turnover_crore",
                labels={"month": "Month", "turnover_crore": "Turnover (Rs. crore)"},
            )
            fig.update_traces(marker_color="#28d7a0")
            fig.update_layout(margin=dict(t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)

st.header("Financials")

st.markdown(
    """<style>
    .st-key-research_financial_balance button,
    .st-key-research_financial_pnl button,
    .st-key-research_financial_cashflow button { border-radius:8px; font-weight:700; }
    .st-key-research_financial_balance button[kind="primary"],
    .st-key-research_financial_pnl button[kind="primary"],
    .st-key-research_financial_cashflow button[kind="primary"] {
        background:#f04452; border:1px solid #ff626d; color:#fff;
    }
    .st-key-research_financial_balance button[kind="secondary"],
    .st-key-research_financial_pnl button[kind="secondary"],
    .st-key-research_financial_cashflow button[kind="secondary"] {
        background:#351c28; border:1px solid #a73749; color:#ffdce0;
    }
    .st-key-research_financial_balance button:hover,
    .st-key-research_financial_pnl button:hover,
    .st-key-research_financial_cashflow button:hover {
        background:#ff626d; border-color:#ff7c85; color:#fff;
    }
    </style>""",
    unsafe_allow_html=True,
)
if "research_financial_view" not in st.session_state:
    st.session_state.research_financial_view = "Balance Sheet"

financial_button_columns = st.columns(3)
financial_views = [
    ("Balance Sheet", "research_financial_balance"),
    ("P&L", "research_financial_pnl"),
    ("Cash Flow", "research_financial_cashflow"),
]
for column, (view_name, button_key) in zip(financial_button_columns, financial_views):
    if column.button(
        view_name,
        key=button_key,
        type="primary" if st.session_state.research_financial_view == view_name else "secondary",
        use_container_width=True,
    ):
        st.session_state.research_financial_view = view_name
        st.rerun()

financial_view = st.session_state.research_financial_view
balance_basis = st.radio(
    "Statement basis",
    ["Consolidated", "Standalone"],
    horizontal=True,
    key="research_balance_basis",
    help="Consolidated includes subsidiaries; standalone covers the parent company only.",
)

if financial_view == "Balance Sheet":
    with st.container(border=True):
        st.subheader("Balance sheet")
        balance_table = (
            "balance_sheet_consolidated" if balance_basis == "Consolidated"
            else "balance_sheet_standalone"
        )

        with sqlite3.connect(DB_PATH) as connection:
            table_exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (balance_table,),
            ).fetchone()
            if table_exists:
                balance_sheet = pd.read_sql_query(
                    f"""SELECT period_end_date, period_label, metric_name, value,
                               source_file, source_sheet
                        FROM {balance_table}
                        WHERE company = ?
                        ORDER BY period_end_date, source_row""",
                    connection,
                    params=(company,),
                    parse_dates=["period_end_date"],
                )
            else:
                balance_sheet = pd.DataFrame()

        if not table_exists:
            st.info(
                "Balance-sheet data is not in this database yet. Run "
                "`python scripts/import_balance_sheets.py` to import the workbooks."
            )
        elif balance_sheet.empty:
            st.info(f"No {balance_basis.lower()} balance-sheet data is available for {company}.")
        else:
            periods = (
                balance_sheet[["period_end_date", "period_label"]]
                .drop_duplicates("period_end_date")
                .sort_values("period_end_date")
            )
            latest_date = periods.iloc[-1]["period_end_date"]
            latest_label = periods.iloc[-1]["period_label"]
            latest = balance_sheet[balance_sheet.period_end_date == latest_date].copy()
            latest_values = {
                str(row.metric_name).strip().casefold(): row.value
                for row in latest.itertuples(index=False)
            }

            def statement_value(*names: str) -> float | None:
                for name in names:
                    value = latest_values.get(name.casefold())
                    if value is not None and pd.notna(value):
                        return float(value)
                return None

            total_assets = statement_value("Total Assets")
            equity = statement_value("Total Shareholders Funds", "Total Shareholders' Funds", "Total Equity")
            current_assets = statement_value("Total Current Assets")
            current_liabilities = statement_value("Total Current Liabilities")
            cash = statement_value("Cash And Cash Equivalents", "Cash and Cash Equivalents")
            long_debt = statement_value("Long Term Borrowings", "Long-term Borrowings")
            short_debt = statement_value("Short Term Borrowings", "Short-term Borrowings")

            st.caption(
                f"{company} · {balance_basis.lower()} · latest reported period: {latest_label}. "
                "Values are shown in the workbook's reported units; the workbooks do not state those units."
            )
            metric_cols = st.columns(5)
            metric_cols[0].metric("Total assets", f"{total_assets:,.2f}" if total_assets is not None else "n/a")
            metric_cols[1].metric("Shareholders' funds", f"{equity:,.2f}" if equity is not None else "n/a")
            metric_cols[2].metric("Cash & equivalents", f"{cash:,.2f}" if cash is not None else "n/a")
            debt = long_debt + short_debt if long_debt is not None and short_debt is not None else None
            metric_cols[3].metric("Borrowings", f"{debt:,.2f}" if debt is not None else "n/a")
            current_ratio = current_assets / current_liabilities if current_assets is not None and current_liabilities else None
            metric_cols[4].metric("Current ratio", f"{current_ratio:.2f}x" if current_ratio is not None else "n/a")

            if debt is not None and equity is not None and equity != 0:
                st.caption(f"Debt-to-equity: {debt / equity:.2f}x · calculated as reported borrowings ÷ shareholders' funds.")

            preferred_metrics = ["Total Assets", "Total Shareholders Funds", "Total Current Liabilities"]
            available_metrics = balance_sheet.metric_name.dropna().astype(str).unique().tolist()
            default_metrics = [name for name in preferred_metrics if name in available_metrics]
            selected_metrics = st.multiselect(
                "Balance-sheet trends",
                available_metrics,
                default=default_metrics,
                key=f"research_balance_metrics_{company}_{balance_basis.lower()}",
            )
            if selected_metrics:
                chart_data = balance_sheet[balance_sheet.metric_name.isin(selected_metrics)].copy()
                chart_data["period"] = chart_data.period_end_date.dt.strftime("%b %Y")
                chart = px.line(
                    chart_data,
                    x="period_end_date",
                    y="value",
                    color="metric_name",
                    markers=True,
                    labels={
                        "period_end_date": "Reported period",
                        "value": "Value (workbook-reported units)",
                        "metric_name": "Balance-sheet item",
                    },
                )
                chart.update_layout(hovermode="x unified", margin=dict(t=20, b=10))
                st.plotly_chart(chart, use_container_width=True)
            else:
                st.info("Select one or more balance-sheet items to draw a trend chart.")

            selected_periods = st.multiselect(
                "Periods in detailed table",
                periods.period_label.tolist()[::-1],
                default=periods.period_label.tolist()[::-1][:5],
                key=f"research_balance_periods_{company}_{balance_basis.lower()}",
            )
            details = balance_sheet[balance_sheet.period_label.isin(selected_periods)]
            if not details.empty:
                detail_table = details.pivot_table(
                    index="metric_name",
                    columns="period_label",
                    values="value",
                    aggfunc="first",
                )
                ordered_periods = [label for label in selected_periods if label in detail_table.columns]
                detail_table = detail_table.reindex(columns=ordered_periods)
                detail_table.columns.name = "Reported period"
                st.dataframe(detail_table, use_container_width=True)
            st.caption(
                "Source: imported balance-sheet workbook. Historical periods can reflect different reporting "
                "period lengths; compare year-on-year values with care."
            )


def render_annual_statement(table_name: str, title: str, preferred_metrics: list[str]) -> None:
    """Render an imported annual statement using the selected company and basis."""
    with sqlite3.connect(DB_PATH) as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
        ).fetchone()
        if exists:
            statement = pd.read_sql_query(
                f"""SELECT period_end_date, period_label, metric_name, value
                    FROM {table_name}
                    WHERE company = ?
                    ORDER BY period_end_date, source_row""",
                connection,
                params=(company,),
                parse_dates=["period_end_date"],
            )
        else:
            statement = pd.DataFrame()

    st.subheader(title)
    if not exists:
        st.info(
            "This statement has not been imported yet. Run "
            "`python scripts/import_profit_loss_and_cashflow.py` to load the P&L and cash-flow workbooks."
        )
        return
    if statement.empty:
        st.info(f"No {balance_basis.lower()} {title.lower()} data is available for {company}.")
        return

    periods = (
        statement[["period_end_date", "period_label"]]
        .drop_duplicates("period_end_date")
        .sort_values("period_end_date")
    )
    st.caption(
        f"{company} · {balance_basis.lower()} · values in workbook-reported units "
        "(unit not stated in the workbook)."
    )
    metric_options = statement.metric_name.dropna().astype(str).unique().tolist()
    default_metrics = [metric for metric in preferred_metrics if metric in metric_options]
    chart_metrics = st.multiselect(
        f"{title} trends",
        metric_options,
        default=default_metrics,
        key=f"research_{table_name}_{company}",
    )
    if chart_metrics:
        chart_data = statement[statement.metric_name.isin(chart_metrics)]
        chart = px.line(
            chart_data,
            x="period_end_date",
            y="value",
            color="metric_name",
            markers=True,
            labels={
                "period_end_date": "Reported period",
                "value": "Value (workbook-reported units)",
                "metric_name": "Line item",
            },
        )
        chart.update_layout(hovermode="x unified", margin=dict(t=20, b=10))
        st.plotly_chart(chart, use_container_width=True)

    selected_periods = st.multiselect(
        f"Periods in {title.lower()} table",
        periods.period_label.tolist()[::-1],
        default=periods.period_label.tolist()[::-1][:5],
        key=f"research_periods_{table_name}_{company}",
    )
    selected = statement[statement.period_label.isin(selected_periods)]
    if not selected.empty:
        detail_table = selected.pivot_table(
            index="metric_name", columns="period_label", values="value", aggfunc="first"
        )
        detail_table = detail_table.reindex(
            columns=[label for label in selected_periods if label in detail_table.columns]
        )
        detail_table.columns.name = "Reported period"
        st.dataframe(detail_table, use_container_width=True)


if financial_view == "P&L":
    with st.container(border=True):
        render_annual_statement(
            "profit_loss_consolidated" if balance_basis == "Consolidated" else "profit_loss_standalone",
            "Profit & loss",
            ["Revenue From Operations [Net]", "Operating Profit", "Net Profit"],
        )
elif financial_view == "Cash Flow":
    with st.container(border=True):
        render_annual_statement(
            "cash_flow_consolidated" if balance_basis == "Consolidated" else "cash_flow_standalone",
            "Cash flow",
            [
                "Net CashFlow From Operating Activities",
                "Net Cash Used In Investing Activities",
                "Net Cash Used From Financing Activities",
            ],
        )

def normalized_line_item(label: object) -> str:
    return "".join(character for character in str(label).casefold() if character.isalnum())


def load_line_item(table_name: str, aliases: list[str]) -> pd.DataFrame:
    """Return one line item over time, matching only known normalized labels."""
    with sqlite3.connect(DB_PATH) as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
        ).fetchone()
        if not exists:
            return pd.DataFrame(columns=["period_end_date", "period_label", "value"])
        values = pd.read_sql_query(
            f"""SELECT period_end_date, period_label, metric_name, value
                FROM {table_name} WHERE company = ? ORDER BY period_end_date, source_row""",
            connection,
            params=(company,),
            parse_dates=["period_end_date"],
        )
    if values.empty:
        return pd.DataFrame(columns=["period_end_date", "period_label", "value"])
    values["normalized_metric"] = values.metric_name.map(normalized_line_item)
    for alias in aliases:
        matched = values[values.normalized_metric == normalized_line_item(alias)]
        if not matched.empty:
            return (
                matched.sort_values("period_end_date")
                .drop_duplicates("period_end_date", keep="last")
                [["period_end_date", "period_label", "value"]]
            )
    return pd.DataFrame(columns=["period_end_date", "period_label", "value"])


if financial_view == "Balance Sheet":
    with st.container(border=True):
        st.subheader("Integrated historical analysis")
        st.caption(
            "Links the selected company's annual P&L, balance sheet, and cash flow by reported period. "
            "Growth and ratios are calculated from imported values; they are not forecasts."
        )

        selected_tables = {
            "Revenue": "profit_loss_consolidated" if balance_basis == "Consolidated" else "profit_loss_standalone",
            "Operating profit": "profit_loss_consolidated" if balance_basis == "Consolidated" else "profit_loss_standalone",
            "Net profit": "profit_loss_consolidated" if balance_basis == "Consolidated" else "profit_loss_standalone",
            "Total assets": "balance_sheet_consolidated" if balance_basis == "Consolidated" else "balance_sheet_standalone",
            "Equity": "balance_sheet_consolidated" if balance_basis == "Consolidated" else "balance_sheet_standalone",
            "Current assets": "balance_sheet_consolidated" if balance_basis == "Consolidated" else "balance_sheet_standalone",
            "Current liabilities": "balance_sheet_consolidated" if balance_basis == "Consolidated" else "balance_sheet_standalone",
            "Long-term borrowings": "balance_sheet_consolidated" if balance_basis == "Consolidated" else "balance_sheet_standalone",
            "Short-term borrowings": "balance_sheet_consolidated" if balance_basis == "Consolidated" else "balance_sheet_standalone",
            "Operating cash flow": "cash_flow_consolidated" if balance_basis == "Consolidated" else "cash_flow_standalone",
        }
        all_tables_exist = True
        with sqlite3.connect(DB_PATH) as connection:
            for table_name in set(selected_tables.values()):
                if not connection.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
                ).fetchone():
                    all_tables_exist = False
                    break

        if not all_tables_exist:
            st.info("Import the balance sheet, P&L, and cash-flow workbooks to build the integrated analysis.")
        else:
            metric_aliases = {
                "Revenue": ["Revenue From Operations [Net]", "Revenue From Operations", "Sales"],
                # These workbooks use Screener-style labels rather than the
                # short labels used by the original dashboard mapping.
                "Operating profit": ["Operating Profit"],
                "Net profit": [
                    "Net Profit",
                    "Profit After Tax",
                    "Profit for the Year",
                    "Profit/Loss For The Period",
                    "Profit/Loss From Continuing Operations",
                    "Profit/Loss After Tax And Before ExtraOrdinary Items",
                ],
                "Total assets": ["Total Assets"],
                "Equity": ["Total Shareholders Funds", "Total Shareholders' Funds", "Total Equity"],
                "Current assets": ["Total Current Assets"],
                "Current liabilities": ["Total Current Liabilities"],
                "Long-term borrowings": ["Long Term Borrowings", "Long-term Borrowings"],
                "Short-term borrowings": ["Short Term Borrowings", "Short-term Borrowings"],
                "Operating cash flow": [
                    "Net CashFlow From Operating Activities",
                    "Net Cash Flow From Operating Activities",
                    "Net Cash Generated From Operating Activities",
                ],
            }
            merged = None
            for metric_name, aliases in metric_aliases.items():
                series = load_line_item(selected_tables[metric_name], aliases)
                series = series.rename(columns={"value": metric_name})
                if merged is None:
                    merged = series
                else:
                    merged = merged.merge(
                        series[["period_end_date", metric_name]],
                        on="period_end_date",
                        how="outer",
                    )

            # The source P&L workbooks do not contain a row literally called
            # "Operating Profit". Calculate operating profit from reported
            # operating revenue less the reported operating expense lines;
            # keep it missing for a period if any required input is missing.
            operating_inputs = {
                "Operating revenue": ["Total Operating Revenues", "Revenue From Operations [Net]"],
                "Operating and direct expenses": ["Operating And Direct Expenses"],
                "Employee benefit expenses": ["Employee Benefit Expenses"],
                "Depreciation and amortisation": ["Depreciation And Amortisation Expenses"],
                "Other operating expenses": ["Other Expenses"],
            }
            operating_parts = None
            for input_name, aliases in operating_inputs.items():
                part = load_line_item(selected_tables["Operating profit"], aliases)
                part = part.rename(columns={"value": input_name})
                if operating_parts is None:
                    operating_parts = part
                else:
                    operating_parts = operating_parts.merge(
                        part[["period_end_date", input_name]],
                        on="period_end_date",
                        how="outer",
                    )
            if operating_parts is not None and not operating_parts.empty:
                expense_columns = list(operating_inputs)[1:]
                complete_inputs = operating_parts[
                    ["Operating revenue", *expense_columns]
                ].notna().all(axis=1)
                operating_parts["Operating profit"] = (
                    operating_parts["Operating revenue"]
                    - operating_parts[expense_columns].sum(axis=1)
                ).where(complete_inputs)
                operating_by_date = operating_parts.set_index("period_end_date")["Operating profit"]
                if merged is None:
                    merged = operating_parts[["period_end_date"]].copy()
                merged["Operating profit"] = merged.period_end_date.map(operating_by_date)

            if merged is None or merged.empty:
                st.info(f"No integrated statement rows are available for {company}.")
            else:
                labels = {}
                for metric_name, aliases in metric_aliases.items():
                    series = load_line_item(selected_tables[metric_name], aliases)
                    if not series.empty:
                        for date, label in zip(series.period_end_date, series.period_label):
                            labels.setdefault(date, label)
                merged["period_label"] = merged.period_end_date.map(labels)
                if company == "Eicher Motors":
                    transition_date = pd.Timestamp("2016-03-31")
                    merged.loc[
                        merged.period_end_date == transition_date, "period_label"
                    ] = "Mar 16 (15m)"
                merged = merged.sort_values("period_end_date").reset_index(drop=True)

                borrowings_available = merged[["Long-term borrowings", "Short-term borrowings"]].notna().all(axis=1)
                merged["Total borrowings"] = (
                    merged["Long-term borrowings"] + merged["Short-term borrowings"]
                ).where(borrowings_available)
                merged["Revenue growth (%)"] = np.nan
                revenue_denominator = merged["Revenue"].replace(0, np.nan)
                merged["Operating margin (%)"] = merged["Operating profit"] / revenue_denominator * 100
                merged["Net margin (%)"] = merged["Net profit"] / revenue_denominator * 100
                merged["Current ratio (x)"] = merged["Current assets"] / merged["Current liabilities"].replace(0, np.nan)
                merged["Debt-to-equity (x)"] = merged["Total borrowings"] / merged["Equity"].replace(0, np.nan)
                merged["Operating cash flow / net profit (x)"] = (
                    merged["Operating cash flow"] / merged["Net profit"].replace(0, np.nan)
                )
                merged["ROE on average equity (%)"] = np.nan

                for idx in range(1, len(merged)):
                    previous = merged.iloc[idx - 1]
                    current = merged.iloc[idx]
                    day_gap = (current.period_end_date - previous.period_end_date).days
                    same_fiscal_end_month = current.period_end_date.month == previous.period_end_date.month
                    normal_annual_interval = 330 <= day_gap <= 400 and same_fiscal_end_month
                    irregular_period = any(
                        "15m" in str(value).casefold()
                        for value in (current.period_label, previous.period_label)
                    )
                    if normal_annual_interval and not irregular_period:
                        if pd.notna(previous.Revenue) and previous.Revenue != 0 and pd.notna(current.Revenue):
                            merged.loc[idx, "Revenue growth (%)"] = (current.Revenue / previous.Revenue - 1) * 100
                        if pd.notna(previous.Equity) and pd.notna(current.Equity):
                            average_equity = (previous.Equity + current.Equity) / 2
                            if average_equity != 0 and pd.notna(current["Net profit"]):
                                merged.loc[idx, "ROE on average equity (%)"] = current["Net profit"] / average_equity * 100

                latest = merged.iloc[-1]
                summary_cols = st.columns(4)
                summary_cols[0].metric(
                    "Latest revenue", f"{latest.Revenue:,.2f}" if pd.notna(latest.Revenue) else "Unavailable"
                )
                summary_cols[1].metric(
                    "Latest net profit", f"{latest['Net profit']:,.2f}" if pd.notna(latest["Net profit"]) else "Unavailable"
                )
                summary_cols[2].metric(
                    "Current ratio", f"{latest['Current ratio (x)']:.2f}x" if pd.notna(latest["Current ratio (x)"]) else "Unavailable"
                )
                summary_cols[3].metric(
                    "Debt-to-equity", f"{latest['Debt-to-equity (x)']:.2f}x" if pd.notna(latest["Debt-to-equity (x)"]) else "Unavailable"
                )

                reported_value_metrics = [
                    "Revenue", "Operating profit", "Net profit", "Total assets", "Equity",
                    "Total borrowings", "Operating cash flow",
                ]
                ratio_metrics = [
                    "Revenue growth (%)", "Operating margin (%)", "Net margin (%)",
                    "ROE on average equity (%)", "Current ratio (x)", "Debt-to-equity (x)",
                    "Operating cash flow / net profit (x)",
                ]
                chart_group = st.radio(
                    "Trend type",
                    ["Reported values", "Calculated ratios"],
                    horizontal=True,
                    key=f"integrated_trend_group_{company}_{balance_basis.lower()}",
                )
                trend_options = reported_value_metrics if chart_group == "Reported values" else ratio_metrics
                trend_metric = st.selectbox(
                    "Metric to chart",
                    trend_options,
                    key=f"integrated_trend_metric_{company}_{balance_basis.lower()}_{chart_group}",
                )
                chart_data = merged.dropna(subset=[trend_metric])
                if not chart_data.empty:
                    trend_chart = px.line(
                        chart_data,
                        x="period_end_date",
                        y=trend_metric,
                        markers=True,
                        labels={
                            "period_end_date": "Reported period",
                            trend_metric: trend_metric + (" (workbook-reported units)" if chart_group == "Reported values" else ""),
                        },
                    )
                    trend_chart.update_layout(showlegend=False, margin=dict(t=20, b=10))
                    st.plotly_chart(trend_chart, use_container_width=True)
                else:
                    st.info(f"{trend_metric} could not be calculated from the available line items.")

                display_columns = [
                    "period_label", "Revenue", "Revenue growth (%)", "Operating profit",
                    "Operating margin (%)", "Net profit", "Net margin (%)", "Total assets",
                    "Equity", "Total borrowings", "Current ratio (x)",
                    "Debt-to-equity (x)", "Operating cash flow",
                    "Operating cash flow / net profit (x)", "ROE on average equity (%)",
                ]
                annual_summary = merged.sort_values("period_end_date", ascending=False)[display_columns]
                annual_summary = annual_summary.rename(columns={"period_label": "Reported period"})
                st.dataframe(annual_summary, use_container_width=True, hide_index=True)
                st.caption(
                    "Definitions: margins = profit ÷ revenue; current ratio = current assets ÷ current liabilities; "
                    "debt-to-equity = long- plus short-term borrowings ÷ shareholders' funds; cash conversion = "
                    "operating cash flow ÷ net profit; ROE = net profit ÷ average beginning/ending equity. "
                    "Annual growth and ROE are suppressed for periods with non-standard month ends or a 15-month label. "
                    "Reported amounts use the workbook's units, which are not explicitly stated in the files."
                )

sidebar_insights = [
    ("Period return", f"{period_return:+.2f}%" if np.isfinite(period_return) else "Insufficient history"),
    ("Annualized volatility", f"{period_volatility:.2f}%" if np.isfinite(period_volatility) else "Insufficient history"),
    ("Maximum drawdown", f"{period_drawdown:.2f}%" if pd.notna(period_drawdown) else "Unavailable"),
]
if selected_benchmark:
    sidebar_insights.extend([
        (f"Return vs {selected_benchmark}", f"{excess_return:+.2f} pp" if np.isfinite(excess_return) else "Insufficient overlap"),
        (f"Correlation vs {selected_benchmark}", f"{benchmark_correlation:.2f}" if np.isfinite(benchmark_correlation) else "Insufficient overlap"),
        (f"Beta vs {selected_benchmark}", f"{benchmark_beta:.2f}" if np.isfinite(benchmark_beta) else "Insufficient overlap"),
    ])
render_sidebar_insights(sidebar_insights, heading=f"{company} insights")
