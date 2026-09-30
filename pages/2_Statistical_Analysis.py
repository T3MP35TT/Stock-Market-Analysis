"""Time-series statistics for historical stock returns and market risk."""

import sqlite3
from datetime import timedelta
from statistics import NormalDist

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from scripts.create_stock_database import DB_PATH, build_database
from scripts.dashboard_theme import apply_sidebar_theme, render_page_hero, render_sidebar_insights

st.set_page_config(page_title="Statistical Analysis", page_icon="📊", layout="wide")
apply_sidebar_theme("Statistical analysis", "Study returns, risk, seasonality, and annual performance against market benchmarks.")
render_page_hero(
    "Equity research workspace / statistics",
    "Statistical analysis",
    "Use the full trading history to compare company returns with NIFTY 50 and SENSEX, spot seasonal patterns, and track risk.",
)
if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
    build_database()
with sqlite3.connect(DB_PATH) as conn:
    data = pd.read_sql_query("SELECT * FROM stock_prices", conn, parse_dates=["date"])
    try:
        benchmark_data = pd.read_sql_query(
            "SELECT index_name, date, close_value FROM market_indices",
            conn,
            parse_dates=["date"],
        )
    except sqlite3.OperationalError:
        benchmark_data = pd.DataFrame(columns=["index_name", "date", "close_value"])
if data.empty:
    st.warning("There is no data to analyze.")
    st.stop()

data = data.dropna(subset=["company", "date", "close_price"]).sort_values(["company", "date"]).copy()
data["daily_return_pct"] = data.groupby("company").close_price.pct_change() * 100
rolling_windows = (20, 30, 60, 90)
for window in rolling_windows:
    min_obs = max(10, int(window * 2 / 3))
    rolling_group = data.groupby("company").daily_return_pct
    rolling_std = rolling_group.rolling(window=window, min_periods=min_obs).std().reset_index(level=0, drop=True)
    rolling_mean = rolling_group.rolling(window=window, min_periods=min_obs).mean().reset_index(level=0, drop=True)
    data[f"rolling_vol_{window}"] = rolling_std * np.sqrt(252)
    data[f"rolling_sharpe_{window}"] = (rolling_mean / rolling_std * np.sqrt(252)).replace([np.inf, -np.inf], np.nan)
data["drawdown_pct"] = (
    (data.close_price / data.groupby("company").close_price.cummax() - 1) * 100
)
data["year"] = data.date.dt.year
data["month"] = data.date.dt.month

month_end = data.groupby(["company", "year", "month"], as_index=False).agg(
    month_end_close=("close_price", "last"), month_end_date=("date", "max")
)
month_end = month_end.sort_values(["company", "month_end_date"])
month_end["monthly_return_pct"] = month_end.groupby("company").month_end_close.pct_change() * 100
annual_close = data.groupby(["company", "year"], as_index=False).agg(year_end_close=("close_price", "last"))
annual_close = annual_close.sort_values(["company", "year"])
annual_close["annual_return_pct"] = annual_close.groupby("company").year_end_close.pct_change() * 100
benchmark_annual = pd.DataFrame(columns=["company", "year", "annual_return_pct"])
if not benchmark_data.empty:
    benchmark_data = benchmark_data.sort_values(["index_name", "date"]).copy()
    benchmark_data["daily_return_pct"] = benchmark_data.groupby("index_name").close_value.pct_change() * 100
    benchmark_data["drawdown_pct"] = (
        (benchmark_data.close_value / benchmark_data.groupby("index_name").close_value.cummax() - 1) * 100
    )
    for window in rolling_windows:
        min_obs = max(10, int(window * 2 / 3))
        grouped_returns = benchmark_data.groupby("index_name").daily_return_pct
        rolling_std = grouped_returns.rolling(window=window, min_periods=min_obs).std().reset_index(level=0, drop=True)
        rolling_mean = grouped_returns.rolling(window=window, min_periods=min_obs).mean().reset_index(level=0, drop=True)
        benchmark_data[f"rolling_vol_{window}"] = rolling_std * np.sqrt(252)
        benchmark_data[f"rolling_sharpe_{window}"] = (rolling_mean / rolling_std * np.sqrt(252)).replace([np.inf, -np.inf], np.nan)
    benchmark_data["year"] = benchmark_data.date.dt.year
    benchmark_data["month"] = benchmark_data.date.dt.month
    benchmark_data["week"] = benchmark_data.date.dt.to_period("W").dt.end_time.dt.normalize()
    benchmark_data["series"] = benchmark_data.index_name + " benchmark"
    benchmark_data["company"] = benchmark_data["series"]
    benchmark_data["month_end_date"] = benchmark_data.date
    benchmark_month_end = benchmark_data.groupby(["index_name", "year", "month"], as_index=False).agg(
        month_end_close=("close_value", "last"), month_end_date=("date", "max")
    ).sort_values(["index_name", "month_end_date"])
    benchmark_month_end["monthly_return_pct"] = benchmark_month_end.groupby("index_name").month_end_close.pct_change() * 100
    benchmark_month_end["company"] = benchmark_month_end.index_name + " benchmark"
else:
    benchmark_month_end = pd.DataFrame(columns=["company", "year", "month", "month_end_date", "monthly_return_pct"])
if not benchmark_data.empty:
    benchmark_annual = benchmark_data.groupby(["index_name", "year"], as_index=False).agg(
        year_end_close=("close_value", "last")
    )
    benchmark_annual = benchmark_annual.sort_values(["index_name", "year"])
    benchmark_annual["annual_return_pct"] = benchmark_annual.groupby("index_name").year_end_close.pct_change() * 100
    benchmark_annual = benchmark_annual.rename(columns={"index_name": "company"})

companies = sorted(data.company.unique())
min_date, max_date = data.date.min().date(), data.date.max().date()
period_days = {"All history": None, "Last 5 years": 1826, "Last 3 years": 1095, "Last 1 year": 365, "Last 6 months": 183}
if "stats_date_range" not in st.session_state:
    st.session_state.stats_date_range = (min_date, max_date)

def apply_stats_period() -> None:
    days = period_days[st.session_state.stats_period]
    end = max_date
    start = min_date if days is None else max(min_date, end - timedelta(days=days))
    st.session_state.stats_date_range = (start, end)

with st.container(border=True):
    st.markdown('<div class="filter-heading">Analysis filters</div>', unsafe_allow_html=True)
    company_col, period_col, date_col = st.columns([1.35, 0.8, 1.1])
    selected = company_col.multiselect("Company universe", companies, default=companies, key="stats_companies")
    period_col.selectbox("Quick window", list(period_days), key="stats_period", on_change=apply_stats_period)
    date_range = date_col.date_input("Custom date range", min_value=min_date, max_value=max_date, key="stats_date_range")
    window_col, confidence_col, focus_col = st.columns([0.8, 1, 1.2])
    rolling_window = window_col.selectbox("Rolling window (sessions)", rolling_windows, index=1, key="stats_rolling_window")
    confidence_level = confidence_col.selectbox("VaR / CVaR confidence", [90, 95, 99], index=1, format_func=lambda value: f"{value}%", key="stats_confidence")
    focus_options = selected or companies
    chart_stock_options = ["All selected companies", *focus_options]
    if st.session_state.get("stats_focus_company") not in focus_options:
        st.session_state.stats_focus_company = focus_options[0]
    focus_company = focus_col.selectbox("Company detail view", focus_options, key="stats_focus_company")

if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date
selected_data = data[
    data.company.isin(selected)
    & data.date.dt.date.between(start_date, end_date)
].copy()
if selected_data.empty:
    st.info("No observations match these filters. Select a company or expand the date range.")
    st.stop()

valid_returns = selected_data.dropna(subset=["daily_return_pct"])
annualized_vol = valid_returns.groupby("company").daily_return_pct.std() * np.sqrt(252)
mean_drawdown = selected_data.groupby("company").drawdown_pct.min()
yearly = annual_close[
    annual_close.company.isin(selected)
    & annual_close.year.between(start_date.year, end_date.year)
].dropna(subset=["annual_return_pct"])

daily_return_matrix = valid_returns.pivot(index="date", columns="company", values="daily_return_pct") / 100
tail_probability = 1 - confidence_level / 100
var_column = f"1-day VaR {confidence_level}% (%)"
cvar_column = f"1-day CVaR {confidence_level}% (%)"
stat_rows = []
for company, group in valid_returns.groupby("company"):
    returns = group.daily_return_pct.to_numpy(dtype=float) / 100
    count = len(returns)
    average = float(np.mean(returns)) if count else np.nan
    stdev = float(np.std(returns, ddof=1)) if count > 1 else np.nan
    downside_deviation = float(np.sqrt(np.mean(np.minimum(returns, 0) ** 2))) if count else np.nan
    var_cutoff = float(np.quantile(returns, tail_probability)) if count else np.nan
    tail = returns[returns <= var_cutoff] if count else np.array([])
    skewness = float(pd.Series(returns).skew()) if count > 2 else np.nan
    excess_kurtosis = float(pd.Series(returns).kurt()) if count > 3 else np.nan
    jb_stat = (count / 6) * (skewness**2 + excess_kurtosis**2 / 4) if np.isfinite(skewness) and np.isfinite(excess_kurtosis) else np.nan
    peer_columns = [name for name in daily_return_matrix.columns if name != company]
    if peer_columns:
        peer_return = daily_return_matrix[peer_columns].mean(axis=1).rename("peer_return")
        asset_return = group.set_index("date").daily_return_pct.div(100).rename("asset_return")
        aligned = pd.concat([asset_return, peer_return], axis=1).dropna()
        peer_variance = aligned.peer_return.var(ddof=1)
        beta = aligned.asset_return.cov(aligned.peer_return) / peer_variance if len(aligned) > 1 and peer_variance else np.nan
    else:
        beta = np.nan
    stat_rows.append({
        "Company": company,
        "Observations": count,
        "Mean daily return (%)": average * 100,
        "Annualized volatility (%)": stdev * np.sqrt(252) * 100 if np.isfinite(stdev) else np.nan,
        "Sharpe (Rf=0)": average / stdev * np.sqrt(252) if np.isfinite(stdev) and stdev else np.nan,
        "Sortino (Rf=0)": average / downside_deviation * np.sqrt(252) if downside_deviation else np.nan,
        var_column: -var_cutoff * 100 if np.isfinite(var_cutoff) else np.nan,
        cvar_column: -float(np.mean(tail)) * 100 if len(tail) else np.nan,
        "Skewness": skewness,
        "Excess kurtosis": excess_kurtosis,
        "JB p-value": float(np.exp(-jb_stat / 2)) if np.isfinite(jb_stat) else np.nan,
        "Peer beta": beta,
    })
technical_stats = pd.DataFrame(stat_rows)
pooled_returns = valid_returns.daily_return_pct.to_numpy(dtype=float) / 100
pooled_mean = float(np.mean(pooled_returns)) if len(pooled_returns) else np.nan
pooled_std = float(np.std(pooled_returns, ddof=1)) if len(pooled_returns) > 1 else np.nan
pooled_var = float(np.quantile(pooled_returns, tail_probability)) if len(pooled_returns) else np.nan

with st.container(border=True):
    st.subheader("Statistical snapshot")
    st.caption("Pooled return KPIs use all selected company-day observations. Volatility and Sharpe ratios are annualized using 252 sessions.")
    kpi_cols = st.columns(6)
    kpi_cols[0].metric("Return observations", f"{len(valid_returns):,}")
    kpi_cols[1].metric("Mean daily return", f"{pooled_mean * 100:+.3f}%" if np.isfinite(pooled_mean) else "n/a")
    kpi_cols[2].metric("Median annualized volatility", f"{annualized_vol.median():.2f}%" if annualized_vol.notna().any() else "n/a")
    kpi_cols[3].metric("Pooled Sharpe (Rf=0)", f"{pooled_mean / pooled_std * np.sqrt(252):.2f}" if np.isfinite(pooled_std) and pooled_std else "n/a")
    kpi_cols[4].metric(f"1-day VaR ({confidence_level}%)", f"{-pooled_var * 100:.2f}%" if np.isfinite(pooled_var) else "n/a")
    kpi_cols[5].metric("Worst drawdown", f"{mean_drawdown.min():.2f}%" if mean_drawdown.notna().any() else "n/a")
    st.caption(f"Showing {selected_data.company.nunique()} selected companies from {start_date:%d %b %Y} to {end_date:%d %b %Y}.")

with st.container(border=True):
    st.subheader("Key insights")
    insight_cols = st.columns(3)
    if yearly.empty:
        with insight_cols[0]:
            st.caption("CALENDAR-YEAR LEADER")
            st.write("Not enough year-end data in this selection.")
    else:
        best_year = yearly.loc[yearly.annual_return_pct.idxmax()]
        with insight_cols[0]:
            st.caption("CALENDAR-YEAR LEADER")
            st.metric("Best return", f"{best_year.annual_return_pct:+.1f}%")
            st.caption(f"{best_year.company} / {int(best_year.year)}")

    if annualized_vol.notna().any():
        most_volatile = annualized_vol.idxmax()
        with insight_cols[1]:
            st.caption("HIGHEST REALIZED RISK")
            st.metric(str(most_volatile), f"{annualized_vol.loc[most_volatile]:.1f}%")
            st.caption("Annualized volatility in selected window")
    else:
        with insight_cols[1]:
            st.caption("HIGHEST REALIZED RISK")
            st.write("Not enough return observations.")

    if mean_drawdown.notna().any():
        deepest = mean_drawdown.idxmin()
        with insight_cols[2]:
            st.caption("DEEPEST DRAWDOWN")
            st.metric(str(deepest), f"{mean_drawdown.loc[deepest]:.1f}%")
            st.caption("Largest decline from a prior closing-price peak")
    else:
        with insight_cols[2]:
            st.caption("DEEPEST DRAWDOWN")
            st.write("No drawdown observations.")

st.markdown("### Return history")
# Calendar-year return heatmap compares selected companies with the two market indices.
with st.container(border=True):
    st.subheader("Annual returns by company and benchmark")
    st.caption("Each cell compares that calendar year's last close with the previous year's last close. NIFTY 50 and SENSEX rows provide market context; the latest year may be year-to-date.")
    annual_heatmap_data = yearly[["company", "year", "annual_return_pct"]].copy()
    if not benchmark_annual.empty:
        benchmark_heatmap_rows = benchmark_annual[
            benchmark_annual.year.between(start_date.year, end_date.year)
        ][["company", "year", "annual_return_pct"]].dropna(subset=["annual_return_pct"])
        annual_heatmap_data = pd.concat([annual_heatmap_data, benchmark_heatmap_rows], ignore_index=True)
    if annual_heatmap_data.empty:
        st.info("At least two calendar-year closing prices are needed to calculate annual returns.")
    else:
        annual_matrix = annual_heatmap_data.pivot(index="company", columns="year", values="annual_return_pct")
        annual_color_limit = max(10, float(np.nanpercentile(np.abs(annual_matrix.to_numpy()), 95)))
        fig = px.imshow(
            annual_matrix, aspect="auto", color_continuous_scale="RdYlGn", zmin=-annual_color_limit, zmax=annual_color_limit,
            text_auto=".1f", labels={"x": "Calendar year", "y": "Company / index", "color": "Return (%)"},
        )
        fig.update_layout(margin=dict(t=15, b=10), coloraxis_colorbar_title="Return (%)", xaxis_side="top")
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Color intensity is capped at +/-{annual_color_limit:.0f}% to keep typical years readable; cell labels show actual returns.")

left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("Monthly return seasonality")
        monthly_stock = st.selectbox(
            "Stocks", chart_stock_options, index=0,
            key="stats_monthly_stock_with_all",
        )
        monthly_stock_names = focus_options if monthly_stock == "All selected companies" else [monthly_stock]
        monthly = month_end[
            (month_end.company.isin(monthly_stock_names))
            & month_end.month_end_date.dt.date.between(start_date, end_date)
        ].dropna(subset=["monthly_return_pct"])
        if not benchmark_month_end.empty:
            benchmark_monthly = benchmark_month_end[
                benchmark_month_end.month_end_date.dt.date.between(start_date, end_date)
            ].dropna(subset=["monthly_return_pct"])
            monthly = pd.concat([monthly, benchmark_monthly], ignore_index=True)
        monthly = monthly.drop_duplicates(subset=["company", "year", "month"], keep="last")
        month_labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        if monthly.empty:
            st.info("Not enough month-end prices in this range to calculate monthly returns.")
        else:
            matrix = monthly.pivot_table(
                index="company", columns="month", values="monthly_return_pct", aggfunc="mean"
            ).reindex(columns=range(1, 13))
            matrix.columns = month_labels
            monthly_color_limit = max(5, float(np.nanpercentile(np.abs(matrix.to_numpy()), 95)))
            fig = px.imshow(
                matrix, aspect="auto", color_continuous_scale="RdYlGn", zmin=-monthly_color_limit, zmax=monthly_color_limit,
                text_auto=".1f", labels={"x": "Month", "y": "Stock / benchmark", "color": "Average return (%)"},
            )
            fig.update_layout(margin=dict(t=15, b=10), coloraxis_colorbar_title="Average return (%)", xaxis_side="top")
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Each cell is the average return for that calendar month across the selected date range. Choose one stock or all stocks in the company universe; NIFTY 50 and SENSEX remain for comparison.")
            st.caption(f"Color intensity is capped at +/-{monthly_color_limit:.0f}%; labels show the actual monthly return.")

with right:
    with st.container(border=True):
        st.subheader(f"Rolling {rolling_window}-session volatility")
        volatility_stock = st.selectbox(
            "Stocks", chart_stock_options, index=0,
            key="stats_volatility_stock_with_all",
        )
        volatility_stock_names = focus_options if volatility_stock == "All selected companies" else [volatility_stock]
        st.caption(f"Annualized standard deviation over the previous {rolling_window} trading sessions; plotted weekly. Choose one stock or all stocks in the company universe; benchmarks remain visible.")
        volatility_column = f"rolling_vol_{rolling_window}"
        rolling = selected_data[
            selected_data.company.isin(volatility_stock_names)
        ].dropna(subset=[volatility_column]).copy()
        rolling = rolling.assign(week=rolling.date.dt.to_period("W").dt.end_time.dt.normalize())
        rolling = rolling.groupby(["company", "week"], as_index=False)[volatility_column].last()
        if not benchmark_data.empty:
            benchmark_rolling = benchmark_data[
                benchmark_data.date.dt.date.between(start_date, end_date)
            ].dropna(subset=[volatility_column]).groupby(["series", "week"], as_index=False)[volatility_column].last()
            benchmark_rolling = benchmark_rolling.rename(columns={"series": "company"})
            rolling = pd.concat([rolling, benchmark_rolling], ignore_index=True)
        fig = px.line(
            rolling, x="week", y=volatility_column, color="company",
            labels={"week": "Week", volatility_column: "Annualized volatility (%)", "company": "Company"},
        )
        fig.update_layout(hovermode="x unified", legend_title_text="Company", margin=dict(t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

with st.container(border=True):
    st.subheader(f"Rolling {rolling_window}-session Sharpe ratio")
    sharpe_stock = st.selectbox(
        "Stocks", chart_stock_options, index=0,
        key="stats_sharpe_stock_with_all",
    )
    sharpe_stock_names = focus_options if sharpe_stock == "All selected companies" else [sharpe_stock]
    st.caption("Annualized rolling mean return divided by rolling standard deviation; assumes a zero risk-free rate. Choose one stock or all stocks in the company universe; benchmarks remain visible.")
    sharpe_column = f"rolling_sharpe_{rolling_window}"
    rolling_sharpe = selected_data[
        selected_data.company.isin(sharpe_stock_names)
    ].dropna(subset=[sharpe_column]).copy()
    rolling_sharpe["week"] = rolling_sharpe.date.dt.to_period("W").dt.end_time.dt.normalize()
    rolling_sharpe = rolling_sharpe.groupby(["company", "week"], as_index=False)[sharpe_column].last()
    if not benchmark_data.empty:
        benchmark_sharpe = benchmark_data[
            benchmark_data.date.dt.date.between(start_date, end_date)
        ].dropna(subset=[sharpe_column]).groupby(["series", "week"], as_index=False)[sharpe_column].last()
        rolling_sharpe = pd.concat(
            [rolling_sharpe, benchmark_sharpe.rename(columns={"series": "company"})], ignore_index=True
        )
    fig = px.line(
        rolling_sharpe, x="week", y=sharpe_column, color="company",
        labels={"week": "Week", sharpe_column: "Annualized Sharpe (Rf=0)", "company": "Company"},
    )
    fig.add_hline(y=0, line_color="#8296af", line_dash="dot", line_width=1)
    fig.update_layout(hovermode="x unified", legend_title_text="Company", margin=dict(t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)

st.markdown("### Risk profile")
with st.container(border=True):
    st.subheader("Drawdown from prior peak")
    drawdown_stock = st.selectbox(
        "Stocks", chart_stock_options, index=0,
        key="stats_drawdown_stock_with_all",
    )
    drawdown_stock_names = focus_options if drawdown_stock == "All selected companies" else [drawdown_stock]
    st.caption("Shows each selected stock's close relative to its highest prior close. History before the selected start date establishes each peak.")
    fig = px.line(
        selected_data[selected_data.company.isin(drawdown_stock_names)], x="date", y="drawdown_pct", color="company",
        labels={"date": "Date", "drawdown_pct": "Drawdown (%)", "company": "Company"},
    )
    if not benchmark_data.empty:
        for index_name, group in benchmark_data[
            benchmark_data.date.dt.date.between(start_date, end_date)
        ].groupby("series", sort=False):
            fig.add_scatter(x=group.date, y=group.drawdown_pct, mode="lines", name=index_name, legendgroup=index_name)
    fig.add_hline(y=0, line_color="#8296af", line_dash="dot", line_width=1)
    fig.update_layout(hovermode="x unified", legend_title_text="Company", margin=dict(t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)

st.markdown("### Return distribution")
left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("Return distribution")
        clipped = valid_returns.copy()
        lower, upper = clipped.daily_return_pct.quantile([0.01, 0.99])
        clipped = clipped[clipped.daily_return_pct.between(lower, upper)]
        if not benchmark_data.empty:
            benchmark_returns = benchmark_data[
                benchmark_data.date.dt.date.between(start_date, end_date)
            ].dropna(subset=["daily_return_pct"])[["series", "daily_return_pct"]]
            clipped = pd.concat([
                clipped[["company", "daily_return_pct"]],
                benchmark_returns.rename(columns={"series": "company"}),
            ], ignore_index=True)
        fig = px.box(
            clipped, x="company", y="daily_return_pct", color="company", points=False,
            labels={"company": "Company", "daily_return_pct": "Daily return (%)"},
        )
        fig.add_hline(y=0, line_color="#8296af", line_dash="dot", line_width=1)
        fig.update_layout(showlegend=False, margin=dict(t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Company distributions trim the outer 1% of daily returns for display. Benchmark distributions are included for comparison; summary metrics use company observations only.")

with right:
    with st.container(border=True):
        st.subheader("Normal Q-Q diagnostic")
        diagnostic_returns = valid_returns.loc[valid_returns.company == focus_company, "daily_return_pct"].to_numpy(dtype=float) / 100
        if len(diagnostic_returns) < 8:
            st.info("At least eight daily returns are recommended for this diagnostic.")
        else:
            standardized = np.sort((diagnostic_returns - diagnostic_returns.mean()) / diagnostic_returns.std(ddof=1))
            quantiles = (np.arange(len(standardized)) + 0.5) / len(standardized)
            theoretical = np.array([NormalDist().inv_cdf(float(q)) for q in quantiles])
            sampled = np.linspace(0, len(standardized) - 1, min(1000, len(standardized)), dtype=int)
            qq = pd.DataFrame({"Normal quantile": theoretical[sampled], "Observed return quantile": standardized[sampled]})
            fig = px.scatter(qq, x="Normal quantile", y="Observed return quantile", opacity=0.55,
                             labels={"Normal quantile": "Theoretical normal quantile", "Observed return quantile": "Observed standardized return"})
            edge = max(abs(theoretical[sampled].min()), abs(theoretical[sampled].max()))
            fig.add_shape(type="line", x0=-edge, y0=-edge, x1=edge, y1=edge, line={"color": "#28d7a0", "dash": "dash"})
            fig.update_layout(showlegend=False, margin=dict(t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Points following the diagonal are closer to normal; tail departures indicate heavier tails or skew.")

with st.container(border=True):
    st.subheader("Per-company risk and distribution diagnostics")
    st.caption(f"Historical one-day VaR/CVaR use the empirical {100 - confidence_level}th percentile. Jarque-Bera p-values are asymptotic diagnostics for normality.")
    format_map = {
        "Mean daily return (%)": "{:+.3f}", "Annualized volatility (%)": "{:.2f}",
        "Sharpe (Rf=0)": "{:.2f}", "Sortino (Rf=0)": "{:.2f}",
        var_column: "{:.2f}", cvar_column: "{:.2f}",
        "Skewness": "{:.2f}", "Excess kurtosis": "{:.2f}", "JB p-value": "{:.3g}", "Peer beta": "{:.2f}",
    }
    st.dataframe(technical_stats.style.format(format_map), use_container_width=True, hide_index=True)

sidebar_insights = []
if not monthly.empty:
    stock_monthly = monthly[monthly.company.isin(monthly_stock_names)]
    seasonal_profile = stock_monthly.groupby("month").monthly_return_pct.mean()
    if seasonal_profile.empty:
        stock_monthly = monthly[monthly.company == focus_company]
        seasonal_profile = stock_monthly.groupby("month").monthly_return_pct.mean()
    if not seasonal_profile.empty:
        strongest_month = int(seasonal_profile.idxmax())
        weakest_month = int(seasonal_profile.idxmin())
        seasonality_scope = "selected stocks" if monthly_stock == "All selected companies" else monthly_stock
        sidebar_insights.extend([
            (f"Best month · {seasonality_scope}", f"{month_labels[strongest_month - 1]}: {seasonal_profile.loc[strongest_month]:+.1f}% average"),
            (f"Weakest month · {seasonality_scope}", f"{month_labels[weakest_month - 1]}: {seasonal_profile.loc[weakest_month]:+.1f}% average"),
        ])
volatility_series = rolling[rolling.company.isin(volatility_stock_names)].sort_values("week")
if not volatility_series.empty:
    latest_volatility = volatility_series.groupby("company", as_index=False).tail(1)
    if volatility_stock == "All selected companies":
        sidebar_insights.append((
            "Median latest rolling volatility",
            f"{latest_volatility[volatility_column].median():.1f}% annualized across {latest_volatility.company.nunique()} stocks",
        ))
    else:
        sidebar_insights.append((
            "Latest rolling volatility",
            f"{volatility_stock}: {latest_volatility.iloc[-1][volatility_column]:.1f}% annualized",
        ))
sharpe_series = rolling_sharpe[rolling_sharpe.company.isin(sharpe_stock_names)].sort_values("week")
if not sharpe_series.empty:
    latest_sharpe = sharpe_series.groupby("company", as_index=False).tail(1)
    if sharpe_stock == "All selected companies":
        sidebar_insights.append((
            "Median latest rolling Sharpe",
            f"{latest_sharpe[sharpe_column].median():+.2f} across {latest_sharpe.company.nunique()} stocks",
        ))
    else:
        sidebar_insights.append((
            "Latest rolling Sharpe",
            f"{sharpe_stock}: {latest_sharpe.iloc[-1][sharpe_column]:+.2f}",
        ))
drawdown_values = selected_data.loc[selected_data.company.isin(drawdown_stock_names), ["company", "drawdown_pct"]]
if not drawdown_values.empty:
    deepest_drawdown = drawdown_values.loc[drawdown_values.drawdown_pct.idxmin()]
    drawdown_label = "Deepest selected stock drawdown" if drawdown_stock == "All selected companies" else "Deepest stock drawdown"
    sidebar_insights.append((drawdown_label, f"{deepest_drawdown.company}: {deepest_drawdown.drawdown_pct:.1f}%"))
if not benchmark_data.empty:
    for index_name in ("NIFTY 50 benchmark", "SENSEX benchmark"):
        benchmark_drawdowns = benchmark_data.loc[
            (benchmark_data.series == index_name)
            & benchmark_data.date.dt.date.between(start_date, end_date),
            "drawdown_pct",
        ]
        if not benchmark_drawdowns.empty:
            sidebar_insights.append((f"Deepest {index_name.removesuffix(' benchmark')} drawdown", f"{benchmark_drawdowns.min():.1f}%"))
if sidebar_insights:
    render_sidebar_insights(sidebar_insights)

with st.expander("Methodology and assumptions"):
    st.markdown(
        "- Daily returns are close-to-close simple returns.\n"
        "- Annualized volatility and Sharpe/Sortino ratios use 252 trading sessions; Sharpe and Sortino assume a zero risk-free rate.\n"
        f"- Historical VaR is the {100 - confidence_level}th percentile of daily returns; CVaR is the mean return at or below that threshold. Values are shown as loss magnitudes.\n"
        "- Peer beta compares each stock with the equal-weighted daily return of the other selected stocks. It is a sample-universe proxy, not a market-index beta.\n"
        "- Jarque-Bera uses sample skewness and excess kurtosis with the large-sample chi-square approximation (2 degrees of freedom)."
    )
