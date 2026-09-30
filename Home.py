"""Project landing page for the stock market analysis dashboard."""

import sqlite3

import pandas as pd
import streamlit as st

from scripts.create_stock_database import DB_PATH
from scripts.dashboard_theme import apply_sidebar_theme, render_sidebar_insights


st.set_page_config(
    page_title="Stock Market Analysis | Home",
    page_icon="📈",
    layout="wide",
)

apply_sidebar_theme(
    "Project home",
    "Start here for project context, database coverage, and the application structure.",
)


st.markdown(
    """
<style>

:root {
    --ink: #e7eef8;
    --muted: #91a3bb;
    --panel: #101a2b;
    --line: #213149;
    --teal: #28d7a0;
    --blue: #75a7ff;
}

.stApp {
    background:
        radial-gradient(
            ellipse at 78% 0%,
            #142c43 0,
            #0b1220 48%,
            #080e18 100%
        );
    color: var(--ink);
}

html,
body,
[class*="css"] {
    font-family: Inter, "Segoe UI", sans-serif;
}

.block-container {
    max-width: 1320px;
    padding-top: 2rem;
    padding-bottom: 3rem;
}


/* Hero */

.hero {
    position: relative;
    overflow: hidden;
    border: 1px solid #263c55;
    border-radius: 24px;
    padding: 30px 34px;
    background:
        linear-gradient(
            115deg,
            rgba(15, 31, 50, 0.97),
            rgba(13, 27, 43, 0.90) 54%,
            rgba(12, 34, 45, 0.90)
        );
    box-shadow: 0 24px 80px rgba(0, 0, 0, 0.22);
}

.hero::after {
    content: "";
    position: absolute;
    width: 55%;
    height: 150%;
    right: -4%;
    top: -30%;
    opacity: 0.35;
    background:
        repeating-linear-gradient(
            135deg,
            transparent 0 28px,
            rgba(40, 215, 160, 0.13) 29px 30px
        );
    transform: skewX(-13deg);
}

.hero-content {
    position: relative;
    z-index: 2;
}

.eyebrow {
    color: var(--teal);
    font: 500 12px Consolas, monospace;
    letter-spacing: 0.18em;
    text-transform: uppercase;
}

.hero-title {
    color: #f3f7fc;
    font-size: clamp(34px, 4vw, 50px);
    font-weight: 800;
    letter-spacing: -0.045em;
    line-height: 1.08;
    margin: 12px 0 12px;
}

.hero-title-accent {
    color: var(--teal);
}

.hero-description {
    color: #adbbcd;
    max-width: 760px;
    font-size: 15px;
    line-height: 1.65;
    margin: 0;
}

.hero-ticker {
    position: absolute;
    right: 38px;
    bottom: 28px;
    z-index: 3;
    text-align: right;
    color: #9cb0c7;
    font: 12px Consolas, monospace;
}

.hero-ticker strong {
    display: block;
    color: var(--teal);
    font-size: 20px;
    margin-top: 5px;
}


/* Section headings */

.section-label {
    color: #8ca2bc;
    font: 500 11px Consolas, monospace;
    letter-spacing: 0.14em;
    text-transform: uppercase;
    margin: 28px 0 12px;
}


/* Research cards */

div.block-container a {
    display: block;
    box-sizing: border-box;
    min-height: 166px;
    padding: 20px 21px;
    overflow: hidden;
    white-space: normal;
    border: 1px solid var(--line);
    border-radius: 17px;
    background:
        linear-gradient(
            160deg,
            rgba(20, 33, 52, 0.96),
            rgba(13, 23, 38, 0.96)
        );
    text-decoration: none;
    transition:
        transform 0.18s ease,
        border-color 0.18s ease,
        box-shadow 0.18s ease;
}

div.block-container a:hover {
    transform: translateY(-3px);
    border-color: #3e6886;
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.18);
}

div.block-container a:focus-visible {
    outline: 2px solid var(--teal);
    outline-offset: 2px;
}

div.block-container a p {
    margin: 0;
    white-space: normal;
    overflow-wrap: anywhere;
}

div.block-container a p:first-child {
    color: var(--teal);
    font: 500 11px Consolas, monospace;
    letter-spacing: 0.12em;
}

div.block-container a p:nth-child(2) {
    color: #eff5fc;
    font-size: 17px;
    font-weight: 700;
    margin: 13px 0 7px;
}

div.block-container a p:nth-child(3) {
    color: #9aabc0;
    font-size: 13px;
    line-height: 1.6;
}


/* Dataset cards */

.data-card {
    background: #111c2d;
    border: 1px solid var(--line);
    border-radius: 14px;
    padding: 18px 20px;
}

.data-card-label {
    color: #93a7c0;
    font: 11px Consolas, monospace;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.data-card-value {
    display: block;
    color: #f1f6fc;
    font-size: 23px;
    font-weight: 700;
    margin-top: 8px;
}

.data-card-small {
    color: #657d99;
    font-size: 12px;
}


/* Streamlit elements */

.stCaption,
[data-testid="stCaption"] {
    color: #8194ac;
}

div[data-testid="stExpander"] {
    background: #101a2a;
    border: 1px solid var(--line);
    border-radius: 14px;
}


/* Responsive */

@media (max-width: 700px) {

    .hero {
        padding: 24px;
    }

    .hero-ticker {
        display: none;
    }

}

</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------
# Hero
# ---------------------------------------------------------

st.markdown(
    """
<section class="hero">
<div class="hero-content">
<div class="eyebrow">
Equity Research Workspace
&nbsp; / &nbsp;
India Markets
</div>

<h1 class="hero-title">
<span class="hero-title-accent">Stock</span>
Market Analysis
</h1>

<p class="hero-description">
Analyze historical stock performance, risk, trading activity,
financial fundamentals, and benchmark behavior across selected
Indian listed companies.
</p>
</div>

<div class="hero-ticker">
MARKET DATA LAB
<strong>ANALYZE ↗</strong>
</div>
</section>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# Research toolkit
# ---------------------------------------------------------

st.markdown(
    '<div class="section-label">Your research toolkit</div>',
    unsafe_allow_html=True,
)


cards = [
    (
        "01 / OVERVIEW",
        "Executive overview",
        "Compare company performance with NIFTY 50 and SENSEX benchmarks.",
        "pages/1_Executive_Overview.py",
    ),
    (
        "02 / STATISTICS",
        "Statistical analysis",
        "Explore return distributions, volatility, calendar returns, and benchmark context.",
        "pages/2_Statistical_Analysis.py",
    ),
    (
        "03 / RESEARCH",
        "Company research",
        "Review price performance, risk, trading activity, and company-level information.",
        "pages/3_Company_Research.py",
    ),
    (
        "04 / PORTFOLIO",
        "Portfolio & risk",
        "Analyze a hypothetical weighted portfolio against market benchmarks.",
        "pages/4_Portfolio_Risk.py",
    ),
    (
        "05 / QUERY",
        "SQL playground",
        "Run read-only SQL queries against the SQLite market database.",
        "pages/5_SQL_Playground.py",
    ),
    (
        "06 / OPERATIONS",
        "CRUD",
        "Create, read, update, and delete company market records in the database.",
        "pages/6_CRUD.py",
    ),
]


for offset in range(0, len(cards), 3):

    feature_columns = st.columns(3)

    for col, (
        number,
        title,
        description,
        page_path,
    ) in zip(
        feature_columns,
        cards[offset : offset + 3],
    ):

        with col:

            st.page_link(
                page_path,
                label=(
                    f"**{number}**\n\n"
                    f"**{title}**\n\n"
                    f"{description}"
                ),
            )


# ---------------------------------------------------------
# Dataset snapshot
# ---------------------------------------------------------

st.markdown(
    '<div class="section-label">Dataset at a glance</div>',
    unsafe_allow_html=True,
)


if DB_PATH.exists() and DB_PATH.stat().st_size:

    try:

        with sqlite3.connect(DB_PATH) as conn:

            coverage = pd.read_sql_query(
                """
                SELECT
                    COUNT(*) AS observations,
                    COUNT(DISTINCT company) AS companies,
                    MIN(date) AS first_date,
                    MAX(date) AS last_date
                FROM stock_prices
                """,
                conn,
            ).iloc[0]

            try:

                benchmark_coverage = pd.read_sql_query(
                    """
                    SELECT
                        COUNT(DISTINCT index_name) AS indices,
                        COUNT(*) AS observations
                    FROM market_indices
                    """,
                    conn,
                ).iloc[0]

            except sqlite3.Error:

                benchmark_coverage = pd.Series(
                    {
                        "indices": 0,
                        "observations": 0,
                    }
                )


        c1, c2, c3, c4 = st.columns(4)


        c1.markdown(
            f"""
            <div class="data-card">
                <div class="data-card-label">Companies covered</div>
                <span class="data-card-value">
                    {int(coverage.companies):,}
                </span>
                <small class="data-card-small">
                    Listed companies
                </small>
            </div>
            """,
            unsafe_allow_html=True,
        )


        c2.markdown(
            f"""
            <div class="data-card">
                <div class="data-card-label">Daily observations</div>
                <span class="data-card-value">
                    {int(coverage.observations):,}
                </span>
                <small class="data-card-small">
                    Company trading records
                </small>
            </div>
            """,
            unsafe_allow_html=True,
        )


        c3.markdown(
            f"""
            <div class="data-card">
                <div class="data-card-label">Historical window</div>
                <span
                    class="data-card-value"
                    style="font-size:18px;"
                >
                    {coverage.first_date} — {coverage.last_date}
                </span>
                <small class="data-card-small">
                    Available date range
                </small>
            </div>
            """,
            unsafe_allow_html=True,
        )


        c4.markdown(
            f"""
            <div class="data-card">
                <div class="data-card-label">Market benchmarks</div>
                <span class="data-card-value">
                    {int(benchmark_coverage["indices"]):,}
                </span>
                <small class="data-card-small">
                    {int(benchmark_coverage["observations"]):,}
                    index observations
                </small>
            </div>
            """,
            unsafe_allow_html=True,
        )


        render_sidebar_insights(
            [
                (
                    "Companies",
                    f"{int(coverage.companies):,}",
                ),
                (
                    "Stock observations",
                    f"{int(coverage.observations):,}",
                ),
                (
                    "Available dates",
                    f"{coverage.first_date} – {coverage.last_date}",
                ),
                (
                    "Benchmarks",
                    f"{int(benchmark_coverage['indices']):,} indices",
                ),
            ],
            heading="Dataset snapshot",
        )


    except sqlite3.Error:

        st.info(
            "The database exists but does not yet have a readable "
            "`stock_prices` table. Build it with "
            "`python scripts/create_stock_database.py`."
        )

else:

    st.info(
        "The database has not been built yet. Run "
        "`python scripts/create_stock_database.py` "
        "to initialize the SQLite database."
    )


# ---------------------------------------------------------
# Project structure
# ---------------------------------------------------------

st.markdown(
    '<div class="section-label">Project structure</div>',
    unsafe_allow_html=True,
)


st.code(
    """SQL - Stock Market Analysis Project/
├── app.py                         Home page / project overview
├── pages/
│   ├── 1_Executive_Overview.py   Executive dashboard
│   ├── 2_Statistical_Analysis.py Statistical analysis
│   ├── 3_Company_Research.py     Company research
│   ├── 4_Portfolio_Risk.py       Portfolio & risk analysis
│   ├── 5_SQL_Playground.py       SQL playground
│   └── 6_CRUD.py                 Data management
├── data/                          Source company CSV files
│   ├── balance sheets/
│   ├── benchmark/
│   ├── cashflow/
│   ├── gap data/
│   └── PL statement/
├── database/
│   └── stock_market.db           SQLite database
├── reports/
│   ├── insights_charts/
│   └── Stock_Market_Analysis_Insights.pdf
├── notebook/
│   └── Stock_Market_Analysis.ipynb
├── scripts/
│   ├── create_stock_database.py  CSV import / database builder
│   ├── dashboard_theme.py        Dashboard styling
│   ├── analysis/report scripts
│   ├── import_balance_sheets.py
│   └── import_profit_loss_and_cashflow.py
├── sql/
│   └── stock_market_analysis.sql Reusable SQL queries
├── README.md
└── requirements.txt""",
    language="text",
)


# ---------------------------------------------------------
# Footer
# ---------------------------------------------------------

st.caption(
    "Historical market data is descriptive and intended for analytical "
    "and educational purposes. It is not a forecast or investment recommendation."
)