"""Hypothetical buy-and-hold portfolio performance using available close-price history."""

import hashlib
import sqlite3

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

from scripts.create_stock_database import DB_PATH, build_database
from scripts.dashboard_theme import apply_sidebar_theme, render_page_hero, render_sidebar_insights

st.set_page_config(page_title="Portfolio & Risk | Stock Market Analysis", page_icon="📈", layout="wide")
apply_sidebar_theme("Portfolio & risk", "Analyze hypothetical weighted holdings against historical market benchmarks.")
render_page_hero(
    "Equity research workspace / portfolio",
    "Portfolio & risk",
    "Explore how a hypothetical weighted portfolio performed against NIFTY 50 and SENSEX over a selected historical period.",
)
st.info(
    "This is a what-if calculator: choose stocks and allocations to see how that mix would have performed in the past. "
    "It does not tell you what to buy or predict what will happen next."
)
with st.expander("How to use this page", expanded=True):
    st.markdown(
        "1. Choose the stocks you want to include.\n"
        "2. Set each stock's percentage of the portfolio; all weights together must equal 100%.\n"
        "3. Enter a starting amount and date range, then click **Update portfolio analysis**.\n\n"
    "The page buys whole shares on the first common trading date, keeps leftover cash idle, and holds without rebalancing."
    )

if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
    build_database()

with sqlite3.connect(DB_PATH) as connection:
    stocks = pd.read_sql_query(
        "SELECT company, date, close_price FROM stock_prices ORDER BY date, company",
        connection,
        parse_dates=["date"],
    )
    try:
        benchmarks = pd.read_sql_query(
            "SELECT index_name, date, close_value FROM market_indices ORDER BY date, index_name",
            connection,
            parse_dates=["date"],
        )
    except sqlite3.OperationalError:
        benchmarks = pd.DataFrame(columns=["index_name", "date", "close_value"])

if stocks.empty:
    st.warning("No stock prices are available to analyze.")
    st.stop()

stocks = stocks.dropna(subset=["company", "date", "close_price"])
companies = sorted(stocks.company.unique())
min_date, max_date = stocks.date.min().date(), stocks.date.max().date()

with st.container(border=True):
    st.subheader("Hypothetical holdings")
    st.caption("Weights start equal. Change them to control how much of the starting amount goes into each company.")
    selected_holdings = st.multiselect(
        "Stocks in portfolio", companies, default=companies[:min(3, len(companies))],
        key="portfolio_selected_holdings",
    )
    if not selected_holdings:
        st.info("Select at least one stock to build a portfolio.")
        st.stop()

    selection_id = hashlib.sha1("|".join(selected_holdings).encode("utf-8")).hexdigest()[:12]
    base_weight = round(100 / len(selected_holdings), 2)
    initial_weights = [base_weight] * len(selected_holdings)
    initial_weights[-1] = round(100 - sum(initial_weights[:-1]), 2)
    default_positions = pd.DataFrame({"Company": selected_holdings, "Weight (%)": initial_weights})

    with st.form(f"portfolio_holdings_form_{selection_id}"):
        positions = st.data_editor(
            default_positions,
            column_config={
                "Company": st.column_config.TextColumn("Company", disabled=True),
                "Weight (%)": st.column_config.NumberColumn("Weight (%)", min_value=0.0, max_value=100.0, step=0.01, format="%.2f"),
            },
            hide_index=True,
            use_container_width=True,
            key=f"portfolio_positions_{selection_id}",
        )
        st.caption(f"Current allocation total: {positions['Weight (%)'].sum():.2f}% (must equal 100%).")
        controls = st.columns([1, 1.2])
        investment = controls[0].number_input("Starting value (Rs.)", min_value=1_000.0, value=100_000.0, step=10_000.0, key="portfolio_starting_value")
        date_range = controls[1].date_input(
            "Analysis period", value=(min_date, max_date), min_value=min_date, max_value=max_date,
            key="portfolio_date_range",
        )
        with st.expander("Advanced setting: risk-free rate for Sharpe and Sortino", expanded=False):
            risk_free_rate_pct = st.number_input(
                "Annual rate (%)", min_value=-5.0, max_value=30.0, value=0.0,
                step=0.25, key="portfolio_risk_free_rate",
                help="These two ratios compare returns with this assumed low-risk annual rate. Leave at 0% if you do not have a period-matched rate.",
            )
        st.form_submit_button("Update portfolio analysis", type="primary")
    st.caption("After changing weights, amount, dates, or the advanced rate, click **Update portfolio analysis** to recalculate.")

if len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date, max_date

positions = positions.dropna(subset=["Company", "Weight (%)"]).copy()
positions["Weight (%)"] = pd.to_numeric(positions["Weight (%)"], errors="coerce")
positions = positions.dropna(subset=["Weight (%)"])
if positions.empty:
    st.info("Add at least one holding to calculate portfolio performance.")
    st.stop()
if positions.Company.duplicated().any():
    st.error("Each company can appear only once. Remove duplicate holdings to continue.")
    st.stop()
weight_total = positions["Weight (%)"].sum()
if not np.isclose(weight_total, 100.0, atol=0.05):
    st.error(f"Portfolio weights currently total {weight_total:.1f}%. Adjust them to total 100%.")
    st.stop()

selected_companies = positions.Company.tolist()
weights = positions.set_index("Company")["Weight (%)"] / 100
prices = stocks.pivot_table(index="date", columns="company", values="close_price", aggfunc="last")
portfolio_prices = prices.loc[
    (prices.index.date >= start_date) & (prices.index.date <= end_date), selected_companies
].dropna(how="any")
if len(portfolio_prices) < 2:
    st.warning("At least two dates with prices for every holding are needed in this range. Expand the date range or change the holdings.")
    st.stop()
if (portfolio_prices.iloc[0] <= 0).any():
    st.error("A holding has a zero or negative starting close, so its return cannot be calculated.")
    st.stop()

starting_allocations = weights * investment
starting_prices = portfolio_prices.iloc[0]
shares_held = np.floor(starting_allocations / starting_prices).astype("int64")
amount_invested = shares_held * starting_prices
cash_held = float(investment - amount_invested.sum())
portfolio_value = portfolio_prices.mul(shares_held, axis="columns").sum(axis=1) + cash_held
portfolio_index = portfolio_value / investment * 100
portfolio_returns = portfolio_index.pct_change().dropna()
portfolio_drawdown = (portfolio_index / portfolio_index.cummax() - 1) * 100
total_return = (portfolio_index.iloc[-1] / portfolio_index.iloc[0] - 1) * 100
annualized_volatility = portfolio_returns.std() * np.sqrt(252) * 100 if len(portfolio_returns) > 1 else np.nan
annualized_return = (
    ((portfolio_index.iloc[-1] / portfolio_index.iloc[0]) ** (252 / len(portfolio_returns)) - 1) * 100
    if len(portfolio_returns) and portfolio_index.iloc[-1] > 0 else np.nan
)
sharpe = (
    (portfolio_returns.mean() - ((1 + risk_free_rate_pct / 100) ** (1 / 252) - 1))
    / portfolio_returns.std() * np.sqrt(252)
    if len(portfolio_returns) > 1 and portfolio_returns.std() > 0 else np.nan
)
daily_risk_free_rate = (1 + risk_free_rate_pct / 100) ** (1 / 252) - 1
daily_excess_returns = portfolio_returns - daily_risk_free_rate
downside_deviation = np.sqrt(np.square(np.minimum(daily_excess_returns, 0)).mean()) * np.sqrt(252)
sortino = (
    daily_excess_returns.mean() * 252 / downside_deviation
    if len(daily_excess_returns) > 1 and downside_deviation > 0 else np.nan
)
historical_var_95 = -portfolio_returns.quantile(0.05) * 100 if len(portfolio_returns) >= 100 else np.nan
tail_returns = portfolio_returns[portfolio_returns <= portfolio_returns.quantile(0.05)]
historical_es_95 = -tail_returns.mean() * 100 if len(portfolio_returns) >= 100 and not tail_returns.empty else np.nan
max_drawdown = portfolio_drawdown.min()
ending_value = float(portfolio_value.iloc[-1])
underwater = portfolio_drawdown < 0
underwater_runs = underwater.groupby((underwater != underwater.shift()).cumsum()).sum()
max_drawdown_duration = int(underwater_runs.max()) if not underwater_runs.empty else 0

benchmark_prices = pd.DataFrame()
benchmark_comparison = {}
if not benchmarks.empty:
    benchmark_prices = benchmarks.pivot_table(
        index="date", columns="index_name", values="close_value", aggfunc="last"
    ).sort_index()
    period_benchmarks = benchmark_prices.reindex(portfolio_prices.index)
    for index_name in period_benchmarks.columns:
        series = period_benchmarks[index_name].dropna()
        if len(series) >= 2 and series.iloc[0] > 0:
            common_start = series.index[0]
            common_end = series.index[-1]
            portfolio_common_return = (portfolio_index.loc[common_end] / portfolio_index.loc[common_start] - 1) * 100
            benchmark_return = (series.iloc[-1] / series.iloc[0] - 1) * 100
            benchmark_comparison[index_name] = {
                "return": benchmark_return,
                "excess": portfolio_common_return - benchmark_return,
                "start_date": common_start,
                "end_date": common_end,
            }

benchmark_risk_rows = []
benchmark_series_iter = benchmark_prices.items() if not benchmark_prices.empty else []
for index_name, series in benchmark_series_iter:
    benchmark_daily_returns = series.dropna().pct_change().reindex(portfolio_returns.index)
    paired_returns = pd.concat(
        [portfolio_returns.rename("portfolio"), benchmark_daily_returns.rename("benchmark")],
        axis=1,
    ).dropna()
    if len(paired_returns) < 2:
        continue
    benchmark_variance = paired_returns["benchmark"].var()
    active_returns = paired_returns["portfolio"] - paired_returns["benchmark"]
    tracking_error = active_returns.std() * np.sqrt(252) * 100
    benchmark_risk_rows.append({
        "Benchmark": index_name,
        "Observations": len(paired_returns),
        "Correlation with index": paired_returns["portfolio"].corr(paired_returns["benchmark"]),
        "Market sensitivity (beta)": paired_returns["portfolio"].cov(paired_returns["benchmark"]) / benchmark_variance if benchmark_variance > 0 else np.nan,
        "Variation vs index (%/year)": tracking_error,
        "Active return consistency": active_returns.mean() / active_returns.std() * np.sqrt(252) if active_returns.std() > 0 else np.nan,
    })

def format_rupees_compact(value: float) -> str:
    if abs(value) >= 10_000_000:
        return f"Rs. {value / 10_000_000:.2f} crore"
    if abs(value) >= 100_000:
        return f"Rs. {value / 100_000:.2f} lakh"
    return f"Rs. {value:,.0f}"

with st.container(border=True):
    st.subheader("Portfolio summary")
    st.caption(f"Buy-and-hold weights · common trading dates {portfolio_prices.index[0]:%d %b %Y} to {portfolio_prices.index[-1]:%d %b %Y}")
    first_metrics = st.columns(3)
    first_metrics[0].metric("Change over this period", f"{total_return:+.2f}%", help="Percentage change in the hypothetical portfolio value across the full selected period.")
    first_metrics[1].metric("Ending value", format_rupees_compact(ending_value), delta=f"Change: {format_rupees_compact(ending_value - investment)}", delta_color="normal")
    first_metrics[2].metric("Average annualized return", f"{annualized_return:+.2f}%" if np.isfinite(annualized_return) else "n/a", help="The compounded yearly rate that would produce this full-period change. It is not a forecast.")
    second_metrics = st.columns(2)
    second_metrics[0].metric("Typical yearly price fluctuation", f"{annualized_volatility:.2f}%" if np.isfinite(annualized_volatility) else "n/a", help="Annualized standard deviation of daily portfolio returns. Higher means returns varied more; it does not indicate direction.")
    second_metrics[1].metric("Largest fall from a previous high", f"{max_drawdown:.2f}%", help="The largest peak-to-trough decline in the selected period. Recovery may take longer than this period.")
    st.markdown(f"For this hypothetical mix, **{format_rupees_compact(investment)}** becomes **{format_rupees_compact(ending_value)}** over the selected dates, before dividends, corporate actions, fees, and taxes.")
    st.caption(f"Sharpe and Sortino assume a {risk_free_rate_pct:.2f}% annual risk-free rate. This assumption affects the ratios, not the portfolio value or return.")
    if benchmark_comparison:
        st.markdown("**Benchmark comparison** · returns use each benchmark's available closes on portfolio trading dates.")
        comparison_cols = st.columns(len(benchmark_comparison))
        for col, (index_name, values) in zip(comparison_cols, benchmark_comparison.items()):
            col.metric(
                f"{index_name} return",
                f"{values['return']:+.2f}%",
                delta=f"Portfolio {values['excess']:+.2f} pp",
            )
            col.caption(f"Common dates: {values['start_date']:%d %b %Y} to {values['end_date']:%d %b %Y}")

with st.container(border=True):
    st.subheader("How bad days and market moves looked")
    tail_cols = st.columns(3)
    tail_cols[0].metric(
        "Estimated loss threshold on a bad day",
        f"{historical_var_95:.2f}%" if np.isfinite(historical_var_95) else "Need 100+ sessions",
        delta=f"{format_rupees_compact(ending_value * historical_var_95 / 100)} at ending value" if np.isfinite(historical_var_95) else None,
        help="Historical 95% one-day Value at Risk: about 5% of observed daily returns were worse than this threshold. It is not a maximum possible loss.",
    )
    tail_cols[1].metric(
        "Average loss on the worst 5% of days",
        f"{historical_es_95:.2f}%" if np.isfinite(historical_es_95) else "Need 100+ sessions",
        delta=f"{format_rupees_compact(ending_value * historical_es_95 / 100)} at ending value" if np.isfinite(historical_es_95) else None,
        help="Historical expected shortfall: average loss on days in the worst 5% of observed daily returns.",
    )
    tail_cols[2].metric("Longest time below a previous high", f"{max_drawdown_duration:,} sessions", help="Longest uninterrupted run of trading sessions when the portfolio remained below its previous peak.")
    st.caption("These are estimates from past daily price moves, not guarantees or forecasts. The rupee amounts scale the historical percentages to the portfolio's ending value.")
    with st.expander("Advanced: risk-adjusted return scores", expanded=False):
        ratio_cols = st.columns(2)
        ratio_cols[0].metric("Sharpe ratio", f"{sharpe:.2f}" if np.isfinite(sharpe) else "n/a")
        ratio_cols[1].metric("Sortino ratio", f"{sortino:.2f}" if np.isfinite(sortino) else "n/a")
        st.caption("These compare excess return with risk. Sharpe counts all daily variation; Sortino focuses on downside variation. Higher values indicate better past return per unit of measured risk, not a forecast.")
    if benchmark_risk_rows:
        with st.expander("Advanced: how the portfolio moved relative to the indexes", expanded=False):
            benchmark_risk = pd.DataFrame(benchmark_risk_rows).set_index("Benchmark")
            st.dataframe(
                benchmark_risk.style.format({
                    "Correlation with index": "{:.2f}",
                    "Market sensitivity (beta)": "{:.2f}",
                    "Variation vs index (%/year)": "{:.2f}%",
                    "Active return consistency": "{:.2f}",
                    "Observations": "{:,.0f}",
                }, na_rep="n/a"),
                use_container_width=True,
            )
            st.markdown(
                "- **Moves together (correlation):** 1 means daily moves were closely aligned; 0 means little linear relationship.\n"
                "- **Market sensitivity (beta):** around 1 means similar sensitivity to that index; above 1 means larger historical responses.\n"
                "- **Difference from index (tracking error):** how much the portfolio's daily returns varied from the index.\n"
                "- **Active return per difference (information ratio):** whether return above the index was consistent relative to that variation."
            )
    else:
        st.info("Benchmark return history is unavailable for this period.")

portfolio_chart = pd.DataFrame({"date": portfolio_index.index, "Indexed value": portfolio_index.values, "Series": "Hypothetical portfolio"})
chart_rows = [portfolio_chart]
if not benchmark_prices.empty:
    for index_name in benchmark_prices.columns:
        aligned_close = benchmark_prices[index_name].reindex(portfolio_index.index).dropna()
        baseline = aligned_close.iloc[0] if not aligned_close.empty else np.nan
        if pd.notna(baseline) and baseline > 0:
            benchmark_chart = pd.DataFrame({
                "date": aligned_close.index,
                "Indexed value": aligned_close / baseline * 100,
                "Series": index_name,
            }).dropna(subset=["Indexed value"])
            chart_rows.append(benchmark_chart)
performance_chart = pd.concat(chart_rows, ignore_index=True)

with st.container(border=True):
    st.subheader("Portfolio performance vs benchmarks")
    fig = px.line(
        performance_chart, x="date", y="Indexed value", color="Series",
        labels={"date": "Date", "Indexed value": "Indexed value (start = 100)"},
        color_discrete_map={"NIFTY 50": "#ffd166", "SENSEX": "#ff6b6b"},
    )
    fig.add_hline(y=100, line_color="#8296af", line_dash="dot", line_width=1)
    fig.update_layout(hovermode="x unified", margin=dict(t=20, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.caption("The portfolio starts at 100 on its first complete holdings date. Each benchmark starts at 100 on its first available date within the selected period; a line at 120 represents a 20% gain from its own starting date.")

left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("Holding contributions")
        contributions = pd.DataFrame({
            "Company": selected_companies,
            "Weight (%)": positions.set_index("Company").loc[selected_companies, "Weight (%)"].values,
            "Contribution (pp)": [
                weights[company] * (portfolio_prices[company].iloc[-1] / portfolio_prices[company].iloc[0] - 1) * 100
                for company in selected_companies
            ],
        }).sort_values("Contribution (pp)")
        fig = px.bar(
            contributions, x="Contribution (pp)", y="Company", orientation="h", color="Contribution (pp)",
            color_continuous_scale=["#e16b6b", "#26384f", "#28d7a0"],
            labels={"Contribution (pp)": "Contribution to portfolio return (pp)"},
        )
        fig.add_vline(x=0, line_color="#aab7c7", line_width=1)
        fig.update_layout(coloraxis_showscale=False, margin=dict(t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Each bar shows how many percentage points that holding added to or subtracted from the portfolio's total return.")
with right:
    with st.container(border=True):
        st.subheader("Portfolio drawdown")
        drawdown_data = pd.DataFrame({"Date": portfolio_drawdown.index, "Drawdown (%)": portfolio_drawdown.values})
        fig = px.area(drawdown_data, x="Date", y="Drawdown (%)")
        fig.update_traces(line_color="#ff6b6b", fillcolor="rgba(255,107,107,.14)")
        fig.update_layout(showlegend=False, margin=dict(t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Drawdown shows the portfolio's percentage decline from its previous high; deeper negative values mean larger losses from a peak.")

left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("Holding return correlation")
        if len(selected_companies) < 2:
            st.info("Select at least two holdings to compare how their daily returns move together.")
        else:
            holding_returns = portfolio_prices.pct_change().dropna()
            if len(holding_returns) < 2:
                st.info("At least three common price dates are needed to estimate holding return correlations.")
            else:
                correlation = holding_returns.corr()
                fig = px.imshow(
                    correlation, zmin=-1, zmax=1, color_continuous_scale="RdYlGn",
                    text_auto=".2f", aspect="auto",
                    labels={"x": "Holding", "y": "Holding", "color": "Correlation"},
                )
                fig.update_layout(margin=dict(t=20, b=10), coloraxis_colorbar_title="Correlation")
                st.plotly_chart(fig, use_container_width=True)
                st.caption("Values near +1 indicate holdings that tended to move together; values near 0 indicate weaker linear co-movement. Correlation is not a measure of guaranteed diversification.")
with right:
    with st.container(border=True):
        st.subheader("30-session realized volatility")
        risk_returns = pd.DataFrame(
            {"Hypothetical portfolio": portfolio_index.pct_change() * 100}
        )
        if not benchmark_prices.empty:
            benchmark_daily_returns = benchmark_prices.apply(
                lambda values: values.dropna().pct_change()
            ) * 100
            benchmark_daily_returns = benchmark_daily_returns.reindex(portfolio_index.index)
            risk_returns = risk_returns.join(benchmark_daily_returns)
        rolling_risk = risk_returns.rolling(30, min_periods=30).std() * np.sqrt(252)
        rolling_risk = rolling_risk.dropna(how="all").reset_index(names="date")
        rolling_risk = rolling_risk.melt(id_vars="date", var_name="Series", value_name="Annualized volatility (%)")
        rolling_risk = rolling_risk.dropna(subset=["Annualized volatility (%)"])
        if rolling_risk.empty:
            st.info("At least 30 daily return observations are needed for rolling volatility.")
        else:
            fig = px.line(
                rolling_risk, x="date", y="Annualized volatility (%)", color="Series",
                labels={"date": "Date", "Annualized volatility (%)": "Annualized volatility (%)"},
                color_discrete_map={"NIFTY 50": "#ffd166", "SENSEX": "#ff6b6b"},
            )
            fig.update_layout(hovermode="x unified", margin=dict(t=20, b=10))
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Annualized standard deviation of daily returns over the previous 30 trading sessions. Volatility measures variation, not the direction of returns.")

st.caption("Hypothetical buy-and-hold results from close prices. The calculation uses dates with prices for every holding, assumes no rebalancing, and excludes dividends, corporate actions, fees, taxes, and slippage. It is a historical illustration, not a forecast.")

best_contributor = contributions.iloc[-1]
worst_contributor = contributions.iloc[0]
render_sidebar_insights([
    ("Portfolio return", f"{total_return:+.2f}%"),
    ("Ending value", f"Rs. {ending_value:,.0f}"),
    ("Annualized volatility", f"{annualized_volatility:.2f}%" if np.isfinite(annualized_volatility) else "n/a"),
    ("Maximum drawdown", f"{max_drawdown:.2f}%"),
    ("Largest contribution", f"{best_contributor.Company}: {best_contributor['Contribution (pp)']:+.2f} pp"),
    ("Smallest contribution", f"{worst_contributor.Company}: {worst_contributor['Contribution (pp)']:+.2f} pp"),
], heading="Portfolio insights")
