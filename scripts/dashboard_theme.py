"""Shared sidebar styling for all Streamlit pages."""

from html import escape

import streamlit as st
import plotly.io as pio

def apply_sidebar_theme(page_name: str, page_summary: str) -> None:
    pio.templates.default = "plotly_dark"
    st.markdown(
        """
        <style>
        :root { --market-ink:#e7eef8; --market-muted:#91a3bb; --market-panel:#111c2d; --market-line:#26384f; --market-teal:#28d7a0; }
        .stApp { background:radial-gradient(ellipse at 75% -8%,#142c43 0,#0b1220 48%,#080e18 100%); color:var(--market-ink); }
        header[data-testid="stHeader"] {
            background:linear-gradient(90deg,rgba(10,18,30,.98),rgba(15,27,43,.97));
            border-bottom:none;
            box-shadow:none;
        }
        header[data-testid="stHeader"] button,
        header[data-testid="stHeader"] a { color:#dce7f3; border-radius:8px; }
        header[data-testid="stHeader"] button:hover,
        header[data-testid="stHeader"] a:hover { background:rgba(40,215,160,.12); color:#f2fbf7; }
        header[data-testid="stHeader"] svg { fill:#a9bad0; }
        div[data-testid="stToolbar"] { background:transparent; }
        .stDeployButton button { border:1px solid rgba(40,215,160,.45); border-radius:8px; }
        .block-container { max-width:1440px; padding-top:2rem; padding-bottom:3rem; }
        .page-hero { position:relative; overflow:hidden; border:1px solid #263c55; border-radius:24px; padding:32px 38px; margin:20px 0 22px; background:linear-gradient(115deg,rgba(15,31,50,.97),rgba(13,27,43,.92) 58%,rgba(12,34,45,.9)); box-shadow:0 20px 65px rgba(0,0,0,.18); }
        .page-hero:after { content:''; position:absolute; width:42%; height:180%; right:-3%; top:-36%; opacity:.3; background:repeating-linear-gradient(135deg,transparent 0 28px,rgba(40,215,160,.13) 29px 30px); transform:skewX(-13deg); }
        .page-hero-kicker { color:#28d7a0; font:500 11px Consolas,monospace; letter-spacing:.17em; text-transform:uppercase; }
        .page-hero h1 { color:#f3f7fc; font-size:clamp(30px,3.6vw,45px); letter-spacing:-.045em; margin:.55rem 0; line-height:1.1; }
        .page-hero p { color:#adbbcd; max-width:760px; font-size:14px; line-height:1.7; margin:0; }
        h1,h2,h3,h4 { color:#f0f5fb; letter-spacing:-.025em; }
        p, label, [data-testid="stMarkdownContainer"] { color:#c0ccda; }
        [data-testid="stCaption"] { color:#8296af; }
        div[data-testid="stMetric"] { background:linear-gradient(145deg,rgba(19,34,53,.96),rgba(13,24,39,.96)); border:1px solid var(--market-line); border-radius:14px; padding:14px 17px; }
        div[data-testid="stMetricLabel"] p { color:#91a5bd; font-size:.78rem; }
        div[data-testid="stMetricValue"] { color:#f1f6fb; }
        div[data-testid="stMetricDelta"] { color:var(--market-teal); }
        button[kind="primary"] { background:linear-gradient(100deg,#20b887,#28d7a0); border:1px solid #28d7a0; color:#071710; font-weight:700; }
        button[kind="primary"]:hover { background:#54e2b5; border-color:#54e2b5; color:#071710; }
        button[kind="secondary"], [data-testid="stDownloadButton"] button { background:#14243a; color:#dce7f3; border:1px solid #2a415c; }
        button[kind="secondary"]:hover, [data-testid="stDownloadButton"] button:hover { border-color:#28d7a0; color:#f2fbf7; }
        input, textarea, [data-baseweb="select"] > div, [data-baseweb="input"] > div {
            background-color:#101b2c !important; color:#e7eef8 !important; border-color:#2a4059 !important;
        }
        [data-baseweb="select"] svg { fill:#a9bad0; }
        div[data-testid="stDataFrame"], div[data-testid="stTable"] { border:1px solid #26384f; border-radius:12px; overflow:hidden; }
        div[data-testid="stExpander"] { background:rgba(16,26,42,.82); border:1px solid #26384f; border-radius:13px; }
        div[data-testid="stForm"] { background:rgba(16,26,42,.7); border:1px solid #26384f; border-radius:13px; padding:16px; }
        div[data-testid="stVerticalBlockBorderWrapper"] { background:linear-gradient(155deg,rgba(17,30,48,.86),rgba(11,20,33,.88)); border-color:#26384f; border-radius:16px; }
        div[data-testid="stTabs"] button[role="tab"] { color:#9aacc1; }
        div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] { color:#28d7a0; border-bottom-color:#28d7a0; }
        hr { border-color:#26384f; }
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #101b2b 0%, #0b1320 100%);
            border-right: 1px solid #24374e;
        }
        section[data-testid="stSidebar"] > div { padding-top: 1.2rem; }
        div[data-testid="stSidebarNav"] { padding: 0.55rem 0.65rem 0.85rem; }
        div[data-testid="stSidebarNav"] ul { gap: 0.38rem; }
        div[data-testid="stSidebarNav"] a {
            border: 1px solid transparent;
            border-radius: 11px;
            margin: 2px 0;
            min-height: 42px;
            transition: background .16s ease, border-color .16s ease, transform .16s ease;
        }
        div[data-testid="stSidebarNav"] a p {
            color: #a9b9cc;
            font-size: 0.91rem;
            font-weight: 550;
        }
        div[data-testid="stSidebarNav"] a:hover {
            background: #17263a;
            border-color: #2a425b;
            transform: translateX(2px);
        }
        div[data-testid="stSidebarNav"] a[aria-current="page"] {
            background: linear-gradient(100deg, rgba(40,215,160,.16), rgba(40,215,160,.06));
            border-color: rgba(40,215,160,.33);
            box-shadow: inset 3px 0 #28d7a0;
        }
        div[data-testid="stSidebarNav"] a[aria-current="page"] p { color: #ecf8f4; font-weight: 700; }
        .sidebar-context {
            margin: 8px 8px 0; padding: 14px 14px 15px;
            border: 1px solid #24384f; border-radius: 12px;
            background: linear-gradient(145deg, rgba(22,39,59,.92), rgba(14,26,42,.92));
        }
        .sidebar-context .kicker { color:#28d7a0; font:10px Consolas,monospace; letter-spacing:.13em; text-transform:uppercase; }
        .sidebar-context strong { display:block; color:#eef4fb; font-size:13px; margin:7px 0 5px; }
        .sidebar-context p { color:#91a4bc; font-size:11px; line-height:1.55; margin:0; }
        .sidebar-filter-row { display:flex; flex-direction:column; gap:2px; padding:8px 0; border-top:1px solid rgba(145,163,187,.12); }
        .sidebar-filter-row span { color:#8296af; font-size:10px; text-transform:uppercase; letter-spacing:.06em; }
        .sidebar-filter-row strong { color:#e7eef8; font-size:11px; line-height:1.45; overflow-wrap:anywhere; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        f"""<div class="sidebar-context"><div class="kicker">Current workspace</div>
        <strong>{escape(page_name)}</strong><p>{escape(page_summary)}</p></div>""",
        unsafe_allow_html=True,
    )


def render_sidebar_insights(items: list[tuple[str, object]], heading: str = "Chart insights") -> None:
    """Render concise observations derived from the current page data."""
    rows = []
    for label, value in items:
        rows.append(
            '<div class="sidebar-filter-row">'
            f'<span>{escape(str(label))}</span><strong>{escape(str(value))}</strong></div>'
        )
    st.sidebar.markdown(
        f'<div class="sidebar-context"><div class="kicker">{escape(heading)}</div>'
        + "".join(rows)
        + "</div>",
        unsafe_allow_html=True,
    )


def render_page_hero(kicker: str, title: str, description: str) -> None:
    st.markdown(
        f"""<section class="page-hero">
        <div class="page-hero-kicker">{kicker}</div>
        <h1>{title}</h1>
        <p>{description}</p>
        </section>""",
        unsafe_allow_html=True,
    )

