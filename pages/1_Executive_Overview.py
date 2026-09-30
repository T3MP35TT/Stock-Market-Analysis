"""Executive overview dashboard for the stock market analysis project."""

import sqlite3
from datetime import timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from scripts.create_stock_database import DB_PATH, build_database
from scripts.dashboard_theme import apply_sidebar_theme, render_sidebar_insights

st.set_page_config(page_title="Executive Overview | Stock Market Analysis", page_icon="📈", layout="wide")
apply_sidebar_theme("Executive overview", "Track selected companies, price performance, and market activity over a chosen date range.")


@st.cache_data
def load_data(db_mtime: float) -> pd.DataFrame:
    del db_mtime
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("SELECT * FROM stock_prices", conn, parse_dates=["date"])


@st.cache_data
def load_benchmark_data(db_mtime: float) -> pd.DataFrame:
    del db_mtime
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query("SELECT index_name, date, close_value FROM market_indices", conn, parse_dates=["date"])
    except sqlite3.OperationalError:
        return pd.DataFrame(columns=["index_name", "date", "close_value"])


if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
    with st.spinner("Preparing the stock database from CSV files..."):
        build_database()

data = load_data(DB_PATH.stat().st_mtime)
benchmark_data = load_benchmark_data(DB_PATH.stat().st_mtime)
if data.empty:
    st.error("No stock data found. Check the database or import the source CSV files.")
    st.stop()

st.markdown("""
<style>
.exec-hero { position:relative; overflow:hidden; border:1px solid #263c55; border-radius:24px; padding:32px 38px; margin:20px 0 22px;
 background:linear-gradient(115deg,rgba(15,31,50,.97),rgba(13,27,43,.92) 58%,rgba(12,34,45,.9)); box-shadow:0 20px 65px rgba(0,0,0,.18); }
.exec-hero:after { content:''; position:absolute; width:42%; height:180%; right:-3%; top:-36%; opacity:.3;
 background:repeating-linear-gradient(135deg,transparent 0 28px,rgba(40,215,160,.13) 29px 30px); transform:skewX(-13deg); }
.exec-kicker { color:#28d7a0; font:500 11px Consolas,monospace; letter-spacing:.17em; text-transform:uppercase; }
.exec-hero h1 { color:#f3f7fc; font-size:clamp(30px,3.6vw,45px); letter-spacing:-.045em; margin:.55rem 0; line-height:1.1; }
.exec-hero p { color:#adbbcd; max-width:760px; font-size:14px; line-height:1.7; margin:0; }
.filter-heading { color:#28d7a0; font:500 11px Consolas,monospace; letter-spacing:.14em; text-transform:uppercase; }
</style>
<section class="exec-hero">
 <div class="exec-kicker">Equity research workspace / executive overview</div>
 <h1>Executive Market Overview</h1>
 <p>Track historical company performance and trading activity across the selected market universe and date range.</p>
</section>
""", unsafe_allow_html=True)

companies = sorted(data.company.dropna().unique())
min_date, max_date = data.date.min().date(), data.date.max().date()
period_days = {"All history": None, "Last 3 years": 1095, "Last 1 year": 365, "Last 6 months": 183, "Last 3 months": 92}
if "executive_date_range" not in st.session_state:
    st.session_state.executive_date_range = (min_date, max_date)

def apply_period_preset() -> None:
    days = period_days[st.session_state.executive_period]
    end = max_date
    start = min_date if days is None else max(min_date, end - timedelta(days=days))
    st.session_state.executive_date_range = (start, end)

with st.container(border=True):
    st.markdown('<div class="filter-heading">Dashboard filters</div>', unsafe_allow_html=True)
    filter_companies, filter_period, filter_dates = st.columns([1.5, 0.8, 1.1])
    selected = filter_companies.multiselect("Companies", companies, default=companies, key="executive_companies")
    filter_period.selectbox("Quick period", list(period_days), key="executive_period", on_change=apply_period_preset)
    date_range = filter_dates.date_input("Custom date range", min_value=min_date, max_value=max_date, key="executive_date_range")

if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date
view = data[data.company.isin(selected) & data.date.dt.date.between(start_date, end_date)].copy()
if view.empty:
    st.info("No observations match these filters. Expand the date range or select a company.")
    st.stop()

view = view.dropna(subset=["close_price"]).sort_values(["company", "date"])
if view.empty:
    st.info("The selected range contains no valid closing prices.")
    st.stop()

company_perf = view.groupby("company", as_index=False).agg(
    first_close=("close_price", "first"), last_close=("close_price", "last"),
    avg_turnover=("turnover", "mean"), avg_delivery=("deliverable_pct", "mean"),
    trading_days=("date", "nunique"),
)
company_perf["period_return_pct"] = (company_perf.last_close / company_perf.first_close - 1) * 100
view["daily_return"] = view.groupby("company").close_price.pct_change()
portfolio_daily = view.groupby("date", as_index=False).daily_return.mean().dropna(subset=["daily_return"])
portfolio_nav = (1 + portfolio_daily.daily_return).cumprod()
annualized_volatility = portfolio_daily.daily_return.std() * (252 ** 0.5) * 100 if len(portfolio_daily) > 1 else 0.0
max_drawdown = ((portfolio_nav / portfolio_nav.cummax()) - 1).min() * 100 if len(portfolio_nav) else 0.0
avg_period_return = company_perf.period_return_pct.mean()
benchmark_returns = {}
if not benchmark_data.empty:
    benchmark_view = benchmark_data[
        benchmark_data.date.dt.date.between(start_date, end_date)
    ].sort_values(["index_name", "date"]).copy()
    for index_name, group in benchmark_view.groupby("index_name"):
        if len(group) >= 2 and group.close_value.iloc[0] != 0:
            benchmark_returns[index_name] = (group.close_value.iloc[-1] / group.close_value.iloc[0] - 1) * 100
daily_turnover = view.groupby("date", as_index=False).turnover.sum(min_count=1)
k1, k2, k3, k4 = st.columns(4)
benchmark_delta = None
if "NIFTY 50" in benchmark_returns:
    benchmark_delta = f"{avg_period_return - benchmark_returns['NIFTY 50']:+.2f} pp vs NIFTY 50"
k1.metric("Equal-weight period return", f"{avg_period_return:+.2f}%", delta=benchmark_delta, delta_color="normal")
k2.metric("Annualized volatility", f"{annualized_volatility:.2f}%")
k3.metric("Maximum drawdown", f"{max_drawdown:.2f}%")
k4.metric("Average daily turnover", f"Rs. {daily_turnover.turnover.mean() / 10_000_000:,.2f} crore")
st.caption(f"{view.company.nunique()} companies | {len(view):,} observations | {start_date:%d %b %Y} to {end_date:%d %b %Y}")

left, right = st.columns([1.6, 1])
with left:
    with st.container(border=True):
        st.subheader("Relative performance vs NIFTY 50 and SENSEX")
        indexed = view.copy()
        indexed["indexed_close"] = indexed.close_price / indexed.groupby("company").close_price.transform("first") * 100
        fig = go.Figure()
        stock_colors = px.colors.qualitative.Plotly
        for index, (company, group) in enumerate(indexed.groupby("company", sort=False)):
            fig.add_trace(go.Scatter(
                x=group.date,
                y=group.indexed_close,
                mode="lines",
                name=company,
                line={"color": stock_colors[index % len(stock_colors)], "width": 1.4},
                opacity=0.38,
                hovertemplate=f"{company}<br>%{{x|%d %b %Y}}<br>Indexed close: %{{y:.1f}}<extra></extra>",
            ))

        selected_benchmarks = benchmark_data[
            benchmark_data.date.dt.date.between(start_date, end_date)
        ].sort_values(["index_name", "date"]).copy()
        benchmark_colors = {"NIFTY 50": "#ffd166", "SENSEX": "#ff6b6b"}
        if not selected_benchmarks.empty:
            selected_benchmarks["indexed_close"] = (
                selected_benchmarks.close_value
                / selected_benchmarks.groupby("index_name").close_value.transform("first")
                * 100
            )
            for index_name, group in selected_benchmarks.groupby("index_name", sort=False):
                color = benchmark_colors.get(index_name, "#ffffff")
                fig.add_trace(go.Scatter(
                    x=group.date,
                    y=group.indexed_close,
                    mode="lines",
                    name=f"{index_name} benchmark",
                    line={"color": color, "width": 4, "dash": "dash"},
                    hovertemplate=f"{index_name} benchmark<br>%{{x|%d %b %Y}}<br>Indexed close: %{{y:.1f}}<extra></extra>",
                ))
                period_return = (group.close_value.iloc[-1] / group.close_value.iloc[0] - 1) * 100
                fig.add_annotation(
                    x=group.date.iloc[-1], y=group.indexed_close.iloc[-1],
                    text=f"{index_name} {period_return:+.1f}%", showarrow=False,
                    xshift=65, font={"color": color, "size": 12},
                    bgcolor="rgba(8,14,24,0.88)", bordercolor=color, borderwidth=1,
                )
        fig.add_hline(y=100, line_color="#8296af", line_dash="dot", line_width=1)
        fig.update_layout(
            xaxis_title="Date",
            yaxis_title="Indexed close (first available close = 100)",
            legend_title_text="Company / benchmark",
            hovermode="x unified",
            margin=dict(t=20, b=10, r=120),
        )
        st.plotly_chart(fig, use_container_width=True)
        if selected_benchmarks.empty:
            st.info("No benchmark observations match this date range. Check the market_indices table and selected dates.")
        else:
            st.caption("Companies are thin solid lines; NIFTY 50 and SENSEX are thick dashed lines with period-return labels. All are rebased to 100. Returns are price-only and exclude dividends.")
with right:
    with st.container(border=True):
        st.subheader("Return by company")
        perf = company_perf.sort_values("period_return_pct")
        fig = px.bar(perf, x="period_return_pct", y="company", orientation="h", color="period_return_pct",
                     color_continuous_scale=["#e16b6b", "#26384f", "#28d7a0"],
                     labels={"period_return_pct": "Period return (%)", "company": "Company"})
        fig.add_vline(x=0, line_color="#aab7c7", line_width=1)
        fig.update_layout(coloraxis_showscale=False, margin=dict(t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

with st.container(border=True):
    st.subheader("Monthly turnover across selected companies")
    turnover_companies = st.multiselect(
        "Companies included in turnover chart", companies,
        default=selected or companies,
        key="executive_turnover_companies",
    )
    turnover_view = data[
        data.company.isin(turnover_companies)
        & data.date.dt.date.between(start_date, end_date)
    ]
    monthly_turnover = (
        turnover_view.assign(month=turnover_view.date.dt.to_period("M").dt.to_timestamp())
        .groupby("month", as_index=False).turnover.sum(min_count=1)
    )
    monthly_turnover["turnover_crore"] = monthly_turnover.turnover / 10_000_000
    if monthly_turnover.empty:
        st.info("Select at least one company to show monthly turnover.")
    else:
        fig = px.area(
            monthly_turnover, x="month", y="turnover_crore",
            labels={"month": "Month", "turnover_crore": "Turnover (Rs. crore)"},
        )
        fig.update_traces(line_color="#28d7a0", fillcolor="rgba(40,215,160,0.16)")
        fig.update_layout(hovermode="x unified", margin=dict(t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)
    sidebar_insights = []
    best_company = company_perf.loc[company_perf.period_return_pct.idxmax()]
    weakest_company = company_perf.loc[company_perf.period_return_pct.idxmin()]
    sidebar_insights.extend([
        ("Top period return", f"{best_company.company}: {best_company.period_return_pct:+.1f}%"),
        ("Lowest period return", f"{weakest_company.company}: {weakest_company.period_return_pct:+.1f}%"),
    ])
    for index_name in ("NIFTY 50", "SENSEX"):
        if index_name in benchmark_returns:
            sidebar_insights.append((f"{index_name} return", f"{benchmark_returns[index_name]:+.1f}%"))
    if not monthly_turnover.empty:
        latest_turnover = monthly_turnover.iloc[-1]
        peak_turnover = monthly_turnover.loc[monthly_turnover.turnover_crore.idxmax()]
        sidebar_insights.extend([
            ("Latest chart month", f"{latest_turnover.month:%b %Y}: Rs. {latest_turnover.turnover_crore:,.0f} crore"),
            ("Peak turnover month", f"{peak_turnover.month:%b %Y}: Rs. {peak_turnover.turnover_crore:,.0f} crore"),
        ])
    render_sidebar_insights(sidebar_insights)

with st.container(border=True):
    st.subheader("Company summary")
    snapshot = company_perf[["company", "period_return_pct", "avg_turnover", "avg_delivery", "trading_days"]].rename(columns={
        "company": "Company", "period_return_pct": "Period return (%)", "avg_turnover": "Avg daily turnover (Rs.)",
        "avg_delivery": "Avg delivery (%)", "trading_days": "Trading days",
    })
    st.dataframe(snapshot.style.format({"Period return (%)": "{:+.2f}", "Avg daily turnover (Rs.)": "{:,.0f}", "Avg delivery (%)": "{:.1f}"}),
                 use_container_width=True, hide_index=True)

with st.expander("Metric definitions"):
    st.write("Period return is the equal-weight average of each selected company's first-to-last close return within the selected window. Annualized volatility and maximum drawdown are calculated from the daily equal-weight average return series, using 252 trading days per year. Monthly turnover sums daily turnover across the selected companies. These are descriptive historical metrics, not forecasts.")
