import sqlite3

import pandas as pd
import plotly.express as px
import streamlit as st

from scripts.create_stock_database import DB_PATH, build_database
from scripts.dashboard_theme import apply_sidebar_theme, render_page_hero, render_sidebar_insights

st.set_page_config(page_title="SQL Playground", page_icon="🧮", layout="wide")
apply_sidebar_theme("SQL playground", "Explore company and benchmark tables with read-only queries and exportable results.")
render_page_hero("Equity research workspace / query", "SQL playground", "Explore company stock and NIFTY 50 / SENSEX benchmark history with read-only queries.")
def pretty_label(column: str) -> str:
    labels = {
        "company": "Company", "index_name": "Index", "date": "Date", "month": "Month", "year": "Year",
        "first_date": "First date", "last_date": "Last date", "latest_date": "Latest date",
        "close_price": "Close price (Rs.)", "first_close": "First close (Rs.)", "last_close": "Last close (Rs.)",
        "total_turnover": "Total turnover (Rs.)", "avg_daily_turnover": "Average daily turnover (Rs.)",
        "total_shares": "Total shares traded", "avg_shares_traded": "Average shares traded",
        "deliverable_pct": "Delivery (%)", "avg_delivery_pct": "Average delivery (%)",
        "return_pct": "Return (%)", "move_pct": "Price move (%)", "drawdown_pct": "Drawdown (%)",
        "avg_absolute_daily_return_pct": "Average absolute daily return (%)",
        "close_value": "Index close", "first_index_level": "First index level", "last_index_level": "Last index level",
        "period_return_pct": "Period return (%)",
        "observations": "Observations", "row_count": "Row count", "duplicate_count": "Duplicate count",
        "up_days": "Up days", "down_days": "Down days", "unchanged_days": "Unchanged days",
    }
    name = column.lower()
    if name.startswith("missing_"):
        return f"Missing {name.removeprefix('missing_').replace('_', ' ').title()}"
    return labels.get(name, column.replace("_", " ").title())


def format_query_result(result: pd.DataFrame) -> pd.DataFrame:
    display_data = result.rename(columns={column: pretty_label(column) for column in result.columns})
    formatters = {}
    for source_column in result.columns:
        column = pretty_label(source_column)
        name = source_column.lower()
        if any(token in name for token in ("pct", "percent", "return", "drawdown", "move", "delivery", "volatility")):
            signed_metric = name in {"return_pct", "period_return_pct", "move_pct", "drawdown_pct"}
            formatters[column] = "{:+.2f}%" if signed_metric else "{:.2f}%"
        elif name in {"close_value", "first_index_level", "last_index_level"}:
            formatters[column] = "{:,.2f}"
        elif any(token in name for token in ("turnover", "price", "close", "wap")):
            formatters[column] = "Rs. {:,.2f}"
        elif any(token in name for token in ("count", "observations", "shares", "quantity", "volume", "trades", "days")):
            formatters[column] = "{:,.0f}"
        elif pd.api.types.is_numeric_dtype(result[source_column]):
            formatters[column] = "{:,.3f}"

    styled = display_data.style.format(formatters, na_rep="n/a")
    gradient_columns = [
        pretty_label(column) for column in result.columns
        if any(token in column.lower() for token in ("return_pct", "drawdown_pct", "move_pct"))
        and pd.api.types.is_numeric_dtype(result[column])
    ]
    if gradient_columns:
        values = result[[column for column in result.columns if pretty_label(column) in gradient_columns]].to_numpy(dtype=float)
        limit = max(float(pd.Series(values.ravel()).abs().quantile(0.95)), 1.0)
        styled = styled.background_gradient(subset=gradient_columns, cmap="RdYlGn", axis=None, vmin=-limit, vmax=limit)
    return styled


def result_chart(result: pd.DataFrame):
    numeric_columns = [column for column in result.select_dtypes(include="number").columns if column.lower() not in {"id"}]
    if not numeric_columns:
        return None

    company_column = next((column for column in result.columns if column.lower() == "company"), None)
    index_column = next((column for column in result.columns if column.lower() == "index_name"), None)
    series_column = company_column or index_column
    time_column = next((column for column in result.columns if column.lower() in {"date", "month", "year"}), None)
    priorities = ("return", "drawdown", "move", "close", "price", "turnover", "shares", "delivery", "up_days", "observations", "count")
    value_column = next(
        (column for token in priorities for column in numeric_columns if token in column.lower()),
        next((column for column in numeric_columns if column.lower() != "year"), None),
    )
    if value_column is None:
        return None

    chart_data = result.copy()
    one_row_per_series = (
        series_column is not None
        and chart_data[series_column].notna().all()
        and chart_data[series_column].nunique() == len(chart_data)
    )

    # Compare paired measures side by side for business questions such as up/down
    # days and missing-field counts instead of silently charting only one column.
    paired_columns = [
        column for column in numeric_columns
        if column.lower() in {"up_days", "down_days", "unchanged_days"}
        or column.lower().startswith("missing_")
    ]
    if one_row_per_series and company_column and len(paired_columns) > 1:
        long_data = chart_data[[company_column, *paired_columns]].melt(
            id_vars=company_column, var_name="Measure", value_name="Value",
        )
        long_data["Measure"] = long_data["Measure"].map(pretty_label)
        fig = px.bar(
            long_data, x=company_column, y="Value", color="Measure", barmode="group",
            labels={company_column: "Company", "Value": "Observations", "Measure": "Measure"},
        )
        fig.update_layout(title="Comparison by company", margin=dict(t=55, b=10), legend_title_text="")
        return fig

    # A cross-section with one observation per company (for example, latest
    # closing prices) is categorical, even if every row also contains a date.
    if one_row_per_series:
        if value_column is None:
            return None
        fig = px.bar(
            chart_data.sort_values(value_column, ascending=False),
            x=series_column, y=value_column, color=value_column,
            color_continuous_scale="Tealgrn",
            labels={series_column: "Company or index", value_column: pretty_label(value_column)},
        )
        fig.update_layout(
            title=f"{pretty_label(value_column)} by company or index", showlegend=False,
            coloraxis_showscale=False, margin=dict(t=55, b=10),
        )
        return fig

    if time_column:
        is_year = time_column.lower() == "year"
        if not is_year:
            chart_data[time_column] = pd.to_datetime(chart_data[time_column], errors="coerce")
            chart_data = chart_data.dropna(subset=[time_column]).sort_values(time_column)
        if chart_data.empty:
            return None
        color = series_column if series_column and chart_data[series_column].nunique() <= 10 else None
        if time_column.lower() == "date" and len(chart_data) <= 40 and any(token in value_column.lower() for token in ("return", "move", "drawdown")):
            fig = px.scatter(chart_data, x=time_column, y=value_column, color=color,
                             labels={time_column: pretty_label(time_column), value_column: pretty_label(value_column)})
        elif is_year:
            fig = px.bar(chart_data, x=time_column, y=value_column, color=color, barmode="group",
                         labels={time_column: pretty_label(time_column), value_column: pretty_label(value_column)})
        else:
            fig = px.line(chart_data, x=time_column, y=value_column, color=color,
                          labels={time_column: pretty_label(time_column), value_column: pretty_label(value_column)})
        fig.update_layout(
            title=f"{pretty_label(value_column)} by {pretty_label(time_column).lower()}",
            hovermode="x unified", margin=dict(t=55, b=10), legend_title_text="Company or index",
        )
        return fig

    if series_column and result[series_column].nunique() <= 30:
        fig = px.bar(chart_data, x=series_column, y=value_column, color=series_column,
                     labels={series_column: "Company or index", value_column: pretty_label(value_column)})
        fig.update_layout(
            title=f"{pretty_label(value_column)} by company",
            showlegend=False, margin=dict(t=55, b=10),
        )
        return fig
    return None


def metric_value(value: float, column: str) -> str:
    name = column.lower()
    if any(token in name for token in ("pct", "percent", "return", "drawdown", "move", "delivery", "volatility")):
        sign = "+" if name in {"return_pct", "period_return_pct", "move_pct"} and value > 0 else ""
        return f"{sign}{value:,.2f}%"
    if name in {"close_value", "first_index_level", "last_index_level"}:
        return f"{value:,.2f}"
    if any(token in name for token in ("turnover", "price", "close", "wap")):
        return f"Rs. {value:,.2f}"
    return f"{value:,.0f}" if any(token in name for token in ("count", "observations", "shares", "quantity", "volume", "trades", "days", "missing")) else f"{value:,.2f}"


def result_summary(result: pd.DataFrame) -> list[tuple[str, str, str | None]]:
    if result.empty:
        return [("Result", "No matching records.", None)]

    company_column = next((column for column in result.columns if column.lower() == "company"), None)
    index_column = next((column for column in result.columns if column.lower() == "index_name"), None)
    entity_column = company_column or index_column
    lower_name_columns = {column.lower(): column for column in result.columns}
    numeric_columns = [column for column in result.select_dtypes(include="number").columns if column.lower() not in {"id", "year"}]
    insights: list[tuple[str, str, str | None]] = []

    # Coverage results have an observation count and date boundaries per company.
    if "observations" in lower_name_columns:
        count_column = lower_name_columns["observations"]
        insights.append(("Total trading observations", f"{result[count_column].sum():,.0f}", None))
        first_column, last_column = lower_name_columns.get("first_date"), lower_name_columns.get("last_date")
        if first_column:
            first = pd.to_datetime(result[first_column], errors="coerce").min()
            if pd.notna(first):
                insights.append(("Coverage begins", f"{first:%d %b %Y}", None))
        if last_column:
            last = pd.to_datetime(result[last_column], errors="coerce").max()
            if pd.notna(last):
                insights.append(("Coverage ends", f"{last:%d %b %Y}", None))
        insights.append(("Median observations per company", f"{result[count_column].median():,.0f}", None))

    # Data-quality queries get totals and the field/company with the largest issue.
    missing_columns = [column for column in numeric_columns if column.lower().startswith("missing_")]
    duplicate_column = lower_name_columns.get("duplicate_count")
    if missing_columns:
        totals = result[missing_columns].sum().sort_values(ascending=False)
        insights = [
            ("Missing values", f"{totals.sum():,.0f}", None),
            ("Most affected field", pretty_label(totals.index[0]), f"{totals.iloc[0]:,.0f} missing"),
            ("Fields with missing data", f"{int((totals > 0).sum())}", None),
        ]
        if company_column:
            impacted = result[missing_columns].fillna(0).gt(0).any(axis=1).sum()
            insights.append(("Companies with gaps", f"{impacted:,.0f}", None))
    elif duplicate_column:
        extras = (result[duplicate_column].fillna(0) - 1).clip(lower=0)
        worst_index = result[duplicate_column].idxmax()
        company = result.loc[worst_index, company_column] if company_column else None
        date_column = lower_name_columns.get("date")
        detail = str(company) if company is not None else None
        if date_column:
            detail = f"{detail or ''} · {result.loc[worst_index, date_column]}".strip(" ·")
        insights = [
            ("Extra duplicate records", f"{extras.sum():,.0f}", None),
            ("Duplicate company-date groups", f"{len(result):,.0f}", None),
            ("Largest duplicate group", f"{result[duplicate_column].max():,.0f}", detail),
        ]
        if company_column:
            insights.append(("Companies affected", f"{result[company_column].nunique():,.0f}", None))

    # Paired directional counts are more useful as up/down insight cards than row totals.
    elif {"up_days", "down_days"}.issubset(lower_name_columns):
        up, down = lower_name_columns["up_days"], lower_name_columns["down_days"]
        top_up, top_down = result[up].idxmax(), result[down].idxmax()
        up_company = str(result.loc[top_up, company_column]) if company_column else None
        down_company = str(result.loc[top_down, company_column]) if company_column else None
        insights = [
            ("Most up days", f"{result.loc[top_up, up]:,.0f}", up_company),
            ("Most down days", f"{result.loc[top_down, down]:,.0f}", down_company),
            ("Total up days", f"{result[up].sum():,.0f}", None),
            ("Total down days", f"{result[down].sum():,.0f}", None),
        ]

    elif not insights:
        # Select the query's main business measure by its column name, not by
        # whichever numeric field happened to appear first in SELECT.
        priorities = ("return", "drawdown", "move", "close", "price", "turnover", "shares", "delivery", "up_days", "observations", "count")
        primary = next((column for token in priorities for column in numeric_columns if token in column.lower()), None)

        if primary is not None:
            values = pd.to_numeric(result[primary], errors="coerce")
            valid = values.dropna()
            if not valid.empty:
                high_index, low_index = valid.idxmax(), valid.idxmin()
                name = pretty_label(primary)
                if entity_column:
                    high_company = str(result.loc[high_index, entity_column])
                    low_company = str(result.loc[low_index, entity_column])
                    low_label = "Deepest drawdown" if "drawdown" in primary.lower() else f"Lowest {name.lower()}"
                    high_label = "Best return" if "return_pct" == primary.lower() else f"Highest {name.lower()}"
                    insights.extend([
                        (high_label, metric_value(float(valid.loc[high_index]), primary), high_company),
                        (f"Median {name.lower()}", metric_value(float(valid.median()), primary), None),
                        (low_label, metric_value(float(valid.loc[low_index]), primary), low_company),
                        (f"Average {name.lower()}", metric_value(float(valid.mean()), primary), None),
                    ])
                else:
                    time_column = next((column for column in result.columns if column.lower() in {"date", "month", "year"}), None)
                    if time_column:
                        peak_time = result.loc[high_index, time_column]
                        latest_time = result[time_column].iloc[-1]
                        insights.extend([
                            (f"Total {name.lower()}", metric_value(float(valid.sum()), primary), None),
                            (f"Peak {name.lower()}", metric_value(float(valid.loc[high_index]), primary), str(peak_time)),
                            (f"Latest {name.lower()}", metric_value(float(valid.iloc[-1]), primary), str(latest_time)),
                            (f"Average {name.lower()}", metric_value(float(valid.mean()), primary), None),
                        ])
                    else:
                        insights.extend([
                            (f"Highest {name.lower()}", metric_value(float(valid.max()), primary), None),
                            (f"Median {name.lower()}", metric_value(float(valid.median()), primary), None),
                            (f"Lowest {name.lower()}", metric_value(float(valid.min()), primary), None),
                            (f"Average {name.lower()}", metric_value(float(valid.mean()), primary), None),
                        ])

    return insights[:4] or [("Summary", "No numeric business measure to summarize.", None)]


def render_result_summary(result: pd.DataFrame) -> list[tuple[str, str, str | None]]:
    if result.empty:
        st.info("The query completed but returned no matching records.")
        return result_summary(result)
    insights = result_summary(result)
    columns = st.columns(min(4, len(insights)))
    for index, (label, value, detail) in enumerate(insights):
        columns[index].metric(label, value, delta=detail, delta_color="off" if detail else "normal")
    return insights

if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
    with st.spinner("Preparing database..."):
        build_database()

default_query = "SELECT company, date, close_price\nFROM stock_prices\nORDER BY date DESC\nLIMIT 100;"
examples = {
    "Coverage | How many records and years do we have per company?": """SELECT company, COUNT(*) AS observations,
       MIN(date) AS first_date, MAX(date) AS last_date
FROM stock_prices
GROUP BY company
ORDER BY company;""",
    "Latest | What is each company's latest closing price?": """WITH latest AS (
    SELECT company, MAX(date) AS latest_date
    FROM stock_prices
    GROUP BY company
)
SELECT p.company, p.date, p.close_price, p.turnover
FROM stock_prices AS p
JOIN latest AS l ON p.company = l.company AND p.date = l.latest_date
ORDER BY p.company;""",
    "Performance | How does full-period price return rank?": """SELECT company,
       (SELECT close_price FROM stock_prices p2 WHERE p2.company = p.company ORDER BY date ASC LIMIT 1) AS first_close,
       (SELECT close_price FROM stock_prices p3 WHERE p3.company = p.company ORDER BY date DESC LIMIT 1) AS last_close,
       ROUND(100.0 * ((SELECT close_price FROM stock_prices p4 WHERE p4.company = p.company ORDER BY date DESC LIMIT 1)
       / NULLIF((SELECT close_price FROM stock_prices p5 WHERE p5.company = p.company ORDER BY date ASC LIMIT 1), 0) - 1), 2) AS return_pct
FROM stock_prices AS p
GROUP BY company
ORDER BY return_pct DESC;""",
    "Activity | Which companies have the highest average daily turnover?": """SELECT company, ROUND(AVG(turnover), 0) AS avg_daily_turnover,
       ROUND(AVG(shares_traded), 0) AS avg_shares_traded
FROM stock_prices
GROUP BY company
ORDER BY avg_daily_turnover DESC;""",
    "Activity | How has monthly turnover changed over time?": """SELECT substr(date, 1, 7) AS month,
       ROUND(SUM(turnover), 0) AS total_turnover,
       ROUND(SUM(shares_traded), 0) AS total_shares
FROM stock_prices
GROUP BY substr(date, 1, 7)
ORDER BY month;""",
    "Activity | What was annual share volume by company?": """SELECT company, substr(date, 1, 4) AS year,
       SUM(shares_traded) AS shares_traded
FROM stock_prices
GROUP BY company, substr(date, 1, 4)
ORDER BY year, company;""",
    "Delivery | Which companies have the highest average delivery ratio?": """SELECT company,
       ROUND(AVG(deliverable_pct), 2) AS avg_delivery_pct,
       ROUND(AVG(deliverable_quantity), 0) AS avg_deliverable_quantity
FROM stock_prices
GROUP BY company
ORDER BY avg_delivery_pct DESC;""",
    "Returns | What were the largest open-to-close moves?": """SELECT company, date,
       ROUND(100.0 * (close_price - open_price) / NULLIF(open_price, 0), 2) AS move_pct
FROM stock_prices
WHERE open_price IS NOT NULL AND close_price IS NOT NULL
ORDER BY ABS(move_pct) DESC
LIMIT 25;""",
    "Returns | Which companies had the most up and down days?": """WITH daily_moves AS (
    SELECT company, close_price - LAG(close_price) OVER (PARTITION BY company ORDER BY date) AS price_change
    FROM stock_prices
)
SELECT company,
       SUM(CASE WHEN price_change > 0 THEN 1 ELSE 0 END) AS up_days,
       SUM(CASE WHEN price_change < 0 THEN 1 ELSE 0 END) AS down_days,
       SUM(CASE WHEN price_change = 0 THEN 1 ELSE 0 END) AS unchanged_days
FROM daily_moves
GROUP BY company
ORDER BY up_days DESC;""",
    "Returns | Which dates had the largest close-to-close moves?": """WITH daily_returns AS (
    SELECT company, date, close_price,
           LAG(close_price) OVER (PARTITION BY company ORDER BY date) AS prior_close
    FROM stock_prices
)
SELECT company, date,
       ROUND(100.0 * (close_price - prior_close) / NULLIF(prior_close, 0), 2) AS return_pct
FROM daily_returns
WHERE prior_close IS NOT NULL
ORDER BY ABS(return_pct) DESC
LIMIT 25;""",
    "Risk | Which companies had the highest average absolute daily return?": """WITH daily_returns AS (
    SELECT company, 100.0 * (close_price - LAG(close_price) OVER (PARTITION BY company ORDER BY date))
           / NULLIF(LAG(close_price) OVER (PARTITION BY company ORDER BY date), 0) AS return_pct
    FROM stock_prices
)
SELECT company, ROUND(AVG(ABS(return_pct)), 3) AS avg_absolute_daily_return_pct
FROM daily_returns
WHERE return_pct IS NOT NULL
GROUP BY company
ORDER BY avg_absolute_daily_return_pct DESC;""",
    "Risk | What are the largest historical drawdowns?": """WITH peaks AS (
    SELECT company, date, close_price,
           MAX(close_price) OVER (PARTITION BY company ORDER BY date ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_peak
    FROM stock_prices
)
SELECT company, date,
       ROUND(100.0 * (close_price / NULLIF(running_peak, 0) - 1), 2) AS drawdown_pct
FROM peaks
ORDER BY drawdown_pct ASC
LIMIT 25;""",
    "Benchmarks | How did NIFTY 50 and SENSEX perform?": """WITH ordered AS (
    SELECT index_name, date, close_value,
           ROW_NUMBER() OVER (PARTITION BY index_name ORDER BY date) AS first_rank,
           ROW_NUMBER() OVER (PARTITION BY index_name ORDER BY date DESC) AS last_rank
    FROM market_indices
)
SELECT index_name,
       MAX(CASE WHEN first_rank = 1 THEN date END) AS first_date,
       MAX(CASE WHEN last_rank = 1 THEN date END) AS last_date,
       MAX(CASE WHEN first_rank = 1 THEN close_value END) AS first_index_level,
       MAX(CASE WHEN last_rank = 1 THEN close_value END) AS last_index_level,
       ROUND(100.0 * (
           MAX(CASE WHEN last_rank = 1 THEN close_value END)
           / NULLIF(MAX(CASE WHEN first_rank = 1 THEN close_value END), 0) - 1
       ), 2) AS period_return_pct
FROM ordered
GROUP BY index_name
ORDER BY period_return_pct DESC;""",
    "Data quality | Are there duplicate company-date records?": """SELECT company, date, COUNT(*) AS duplicate_count
FROM stock_prices
GROUP BY company, date
HAVING COUNT(*) > 1
ORDER BY duplicate_count DESC, company, date;""",
    "Data quality | How many missing values are in key fields?": """SELECT company,
       SUM(CASE WHEN close_price IS NULL THEN 1 ELSE 0 END) AS missing_close,
       SUM(CASE WHEN turnover IS NULL THEN 1 ELSE 0 END) AS missing_turnover,
       SUM(CASE WHEN shares_traded IS NULL THEN 1 ELSE 0 END) AS missing_volume,
       SUM(CASE WHEN deliverable_pct IS NULL THEN 1 ELSE 0 END) AS missing_delivery_pct
FROM stock_prices
GROUP BY company
ORDER BY company;""",
}

if "sql_query" not in st.session_state:
    st.session_state.sql_query = default_query

def load_example_query() -> None:
    selected_example = st.session_state.sql_example
    st.session_state.sql_query = examples.get(selected_example, default_query)

with st.container(border=True):
    st.subheader("Build a query")
    st.caption("The connection is read-only. Data-changing SQL statements are not permitted.")
    st.caption("Choose a business question to load a sample query, then edit it or write your own.")
    st.selectbox("Choose a question", ["Custom query", *examples.keys()], key="sql_example", on_change=load_example_query)
    query = st.text_area("SQL query", height=260, key="sql_query")
    run_query = st.button("Run query", type="primary")

if run_query:
    try:
        uri = f"file:{DB_PATH.as_posix()}?mode=ro"
        with sqlite3.connect(uri, uri=True) as conn:
            result = pd.read_sql_query(query, conn)
        st.session_state.sql_result = result
        st.session_state.sql_result_query = query
        st.session_state.sql_result_question = st.session_state.get("sql_example", "Custom query")
    except Exception as exc:
        st.session_state.pop("sql_result", None)
        st.error(f"Query error: {exc}")

if "sql_result" in st.session_state:
    result = st.session_state.sql_result
    with st.container(border=True):
        st.subheader("Query results")
        selected_question = st.session_state.get("sql_result_question", "Custom query")
        if selected_question != "Custom query":
            st.caption(f"Business question: {selected_question.split(' | ', 1)[-1]}")
        st.caption("Showing the last executed result. Run the query again after changing the question or SQL.")
        query_insights = render_result_summary(result)

        chart = result_chart(result) if not result.empty else None
        if chart is not None:
            chart_tab, data_tab = st.tabs(["Visualization", f"Data table ({len(result):,})"])
            with chart_tab:
                st.plotly_chart(chart, use_container_width=True, config={"displaylogo": False})
            with data_tab:
                st.dataframe(format_query_result(result), use_container_width=True, hide_index=True)
        elif not result.empty:
            st.info("This result is best read as a table because it has no suitable category or time axis.")
            st.dataframe(format_query_result(result), use_container_width=True, hide_index=True)

        st.download_button(
            "Download full result as CSV",
            result.to_csv(index=False).encode("utf-8"),
            "query_result.csv",
            "text/csv",
            help="Downloads the original query output with its original column names and values.",
        )

if "sql_result" not in st.session_state:
    render_sidebar_insights([("Query KPI", "Run a query to see its business metrics.")], heading="Query KPIs")
else:
    render_sidebar_insights([
        (label, f"{value} · {detail}" if detail else value)
        for label, value, detail in query_insights
    ], heading="Query KPIs")

with st.container(border=True):
    st.subheader("Database schema")
    st.code("""stock_prices(company, date, open_price, high_price, low_price,
close_price, wap, shares_traded, trades, turnover, deliverable_quantity,
deliverable_pct, spread_high_low, spread_close_open)

market_indices(index_name, date, open_value, high_value, low_value,
close_value, change_pct)""", language="sql")
