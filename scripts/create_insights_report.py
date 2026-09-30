"""Create PNG insight charts and a PDF summary from the generated SQLite database."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = ROOT / "database" / "stock_market.db"
REPORTS = ROOT / "reports"
CHARTS = REPORTS / "insights_charts"
PDF_PATH = REPORTS / "Stock_Market_Analysis_Insights.pdf"


def load_data() -> pd.DataFrame:
    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        raise FileNotFoundError(f"Database not found or empty: {DB_PATH}")
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query("SELECT * FROM stock_prices", conn, parse_dates=["date"])
    if df.empty:
        raise ValueError("The stock_prices table contains no data.")
    return df.sort_values(["company", "date"])


def calculate_metrics(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for company, group in df.groupby("company"):
        group = group.dropna(subset=["close_price"])
        if group.empty:
            continue
        start, end = group.iloc[0], group.iloc[-1]
        ret = (end.close_price / start.close_price - 1) * 100 if start.close_price else float("nan")
        rows.append({
            "Company": company,
            "Observations": len(group),
            "Start date": start.date.strftime("%d %b %Y"),
            "End date": end.date.strftime("%d %b %Y"),
            "First close": start.close_price,
            "Last close": end.close_price,
            "Return (%)": ret,
            "Avg turnover (Rs.)": group.turnover.mean(),
            "Avg delivery (%)": group.deliverable_pct.mean(),
        })
    return pd.DataFrame(rows).sort_values("Return (%)", ascending=False)


def save_charts(df: pd.DataFrame, metrics: pd.DataFrame) -> list[Path]:
    CHARTS.mkdir(parents=True, exist_ok=True)
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update({"font.size": 9, "axes.titlesize": 13, "axes.labelsize": 10, "legend.fontsize": 8})
    palette = ["#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7", "#56B4E9"]
    company_colors = dict(zip(sorted(df.company.dropna().unique()), palette))
    paths = []

    fig, ax = plt.subplots(figsize=(10, 5.2))
    for company, group in df.dropna(subset=["close_price"]).groupby("company"):
        group = group.sort_values("date")
        base = group.close_price.iloc[0]
        if base:
            ax.plot(group.date, group.close_price / base * 100, label=company,
                    color=company_colors.get(company), linewidth=1.8)
    ax.set(title="Indexed closing price (first observation = 100)", ylabel="Indexed close", xlabel="Date")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=3, frameon=False)
    fig.tight_layout()
    path = CHARTS / "indexed_closing_prices.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    fig, ax = plt.subplots(figsize=(9, 4.8))
    chart = metrics.sort_values("Return (%)")
    bars = ax.barh(chart.Company, chart["Return (%)"], color=["#d97757" if v < 0 else "#3977a8" for v in chart["Return (%)"]])
    ax.axvline(0, color="#333333", linewidth=0.8)
    ax.bar_label(bars, fmt="%.1f%%", padding=4, fontsize=9)
    ax.set(title="Price change over each company's available period", xlabel="Change from first to last close (%)")
    fig.tight_layout()
    path = CHARTS / "period_returns.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    fig, ax = plt.subplots(figsize=(9, 4.8))
    chart = metrics.sort_values("Avg turnover (Rs.)")
    bars = ax.barh(chart.Company, chart["Avg turnover (Rs.)"] / 1_000_000, color="#3977a8")
    ax.bar_label(bars, fmt="%.1f", padding=4, fontsize=9)
    ax.set(title="Average daily turnover", xlabel="Rs. millions")
    fig.tight_layout()
    path = CHARTS / "average_turnover.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    fig, ax = plt.subplots(figsize=(9, 4.8))
    chart = metrics.sort_values("Avg delivery (%)")
    bars = ax.barh(chart.Company, chart["Avg delivery (%)"], color="#5d9270")
    ax.bar_label(bars, fmt="%.1f%%", padding=4, fontsize=9)
    ax.set(title="Average deliverable quantity as a share of traded quantity", xlabel="Average delivery (%)")
    fig.tight_layout()
    path = CHARTS / "average_delivery.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    # U: distribution of daily returns by company.
    chart_data = df.sort_values(["company", "date"]).copy()
    chart_data["daily_return_pct"] = chart_data.groupby("company")["close_price"].pct_change() * 100
    return_groups = [
        group["daily_return_pct"].dropna().to_numpy()
        for _, group in chart_data.groupby("company")
    ]
    return_labels = list(chart_data.company.dropna().unique())
    fig, ax = plt.subplots(figsize=(9, 4.8))
    box = ax.boxplot(return_groups, tick_labels=return_labels, showfliers=False, patch_artist=True,
               boxprops={"facecolor": "#9fc4dc"}, medianprops={"color": "#16324f", "linewidth": 1.5})
    for patch, company in zip(box["boxes"], return_labels):
        patch.set_facecolor(company_colors.get(company, "#9fc4dc"))
    ax.axhline(0, color="#555555", linewidth=0.8)
    ax.set(title="Univariate: daily return distribution by company", ylabel="Daily return (%)")
    ax.tick_params(axis="x", rotation=20)
    fig.tight_layout()
    path = CHARTS / "daily_return_distribution.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    # B: traded share count and turnover.
    activity = df.dropna(subset=["shares_traded", "turnover"])
    fig, ax = plt.subplots(figsize=(9, 4.8))
    activity = activity[(activity.shares_traded > 0) & (activity.turnover > 0)].copy()
    x_log = np.log10(activity.shares_traded)
    y_log = np.log10(activity.turnover / 1_000_000)
    density = ax.hexbin(x_log, y_log, gridsize=36, mincnt=1, bins="log", cmap="Blues", linewidths=0)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda value, _: f"{10**value:,.0f}"))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda value, _: f"{10**value:g}"))
    ax.set(title="Shares traded and turnover", xlabel="Shares traded (log scale)", ylabel="Turnover (Rs. millions, log scale)")
    fig.colorbar(density, ax=ax, label="Days in bin (log color scale)")
    fig.tight_layout()
    path = CHARTS / "shares_vs_turnover.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    # B: daily price movement and delivery ratio.
    fig, ax = plt.subplots(figsize=(9, 4.8))
    relation = chart_data.dropna(subset=["deliverable_pct", "daily_return_pct"])
    lower, upper = relation.daily_return_pct.quantile([0.01, 0.99])
    relation = relation[relation.daily_return_pct.between(lower, upper)]
    density = ax.hexbin(relation.deliverable_pct, relation.daily_return_pct, gridsize=42,
                        mincnt=1, bins="log", cmap="viridis")
    ax.axhline(0, color="#555555", linewidth=0.8)
    ax.set(title="Bivariate: delivery ratio vs daily return", xlabel="Deliverable quantity (% of traded quantity)", ylabel="Daily return (%) | central 98%")
    fig.colorbar(density, ax=ax, label="Observations per bin (log scale)")
    fig.tight_layout()
    path = CHARTS / "delivery_vs_daily_return.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    # M: relationships among four numeric variables.
    corr_columns = ["daily_return_pct", "shares_traded", "turnover", "deliverable_pct"]
    corr = chart_data[corr_columns].corr(method="spearman")
    fig, ax = plt.subplots(figsize=(7.2, 6))
    cmap = plt.cm.RdBu_r.copy()
    cmap.set_bad("#f4f6f8")
    image = ax.imshow(corr, cmap=cmap, vmin=-1, vmax=1)
    ax.grid(False)
    labels = ["Daily return", "Shares traded", "Turnover", "Delivery %"]
    ax.set_xticks(range(len(labels)), labels, rotation=25, ha="right")
    ax.set_yticks(range(len(labels)), labels)
    for row in range(len(labels)):
        for col in range(len(labels)):
            value = corr.iloc[row, col]
            ax.text(col, row, f"{value:.2f}", ha="center", va="center",
                    fontsize=9, color="white" if abs(value) > 0.55 else "#222222")
    ax.set_title("How the measures move together (Spearman correlation)")
    fig.colorbar(image, ax=ax, label="Spearman correlation")
    fig.tight_layout()
    path = CHARTS / "spearman_correlation_matrix.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)

    # M: price movement, turnover, share volume, and delivery ratio in one view.
    bubble = chart_data.dropna(subset=["daily_return_pct", "turnover", "shares_traded", "deliverable_pct"])
    x_low, x_high = bubble.turnover.quantile([0.01, 0.99])
    y_low, y_high = bubble.daily_return_pct.quantile([0.01, 0.99])
    bubble = bubble[bubble.turnover.between(x_low, x_high) & bubble.daily_return_pct.between(y_low, y_high)]
    bubble = bubble.sample(n=min(1200, len(bubble)), random_state=42)
    log_size = np.log1p(bubble.shares_traded.clip(lower=0))
    size = 9 + 25 * (log_size / log_size.max()) if log_size.max() else 9
    fig, ax = plt.subplots(figsize=(9, 4.8))
    points = ax.scatter(bubble.turnover / 1_000_000, bubble.daily_return_pct,
                        s=size, c=bubble.deliverable_pct, cmap="viridis", alpha=0.22, edgecolors="none", rasterized=True)
    ax.set_xscale("log")
    ax.axhline(0, color="#555555", linewidth=0.8)
    ax.set(title="Turnover, daily return and delivery ratio", xlabel="Turnover (Rs. millions, log scale)", ylabel="Daily return (%)")
    fig.colorbar(points, ax=ax, label="Deliverable quantity (%)")
    fig.tight_layout()
    path = CHARTS / "multivariate_activity_returns.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    paths.append(path)
    return paths


def make_pdf(df: pd.DataFrame, metrics: pd.DataFrame, charts: list[Path]) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(PDF_PATH), pagesize=A4, rightMargin=0.55 * inch, leftMargin=0.55 * inch,
        topMargin=0.55 * inch, bottomMargin=0.55 * inch,
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="CenteredTitle", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor("#16324f")))
    story = [
        Paragraph("Stock Market Analysis", styles["CenteredTitle"]),
        Paragraph("SQL based insights from the supplied historical trading data", styles["Heading2"]),
        Spacer(1, 10),
    ]
    start_date, end_date = df.date.min().strftime("%d %b %Y"), df.date.max().strftime("%d %b %Y")
    summary = (
        f"The dataset contains <b>{len(df):,}</b> daily observations across <b>{df.company.nunique()}</b> companies, "
        f"covering <b>{start_date}</b> through <b>{end_date}</b>. Period returns compare each company's earliest "
        "and latest available closing prices; they do not represent annualized returns or risk adjusted performance."
    )
    story.extend([Paragraph(summary, styles["BodyText"]), Spacer(1, 12)])

    best = metrics.iloc[0]
    worst = metrics.iloc[-1]
    highest_turnover = metrics.loc[metrics["Avg turnover (Rs.)"].idxmax()]
    highest_delivery = metrics.loc[metrics["Avg delivery (%)"].idxmax()]
    story.append(Paragraph("Key observations", styles["Heading1"]))
    bullets = [
        f"Highest period price change: {best.Company} ({best['Return (%)']:.2f}%).",
        f"Lowest period price change: {worst.Company} ({worst['Return (%)']:.2f}%).",
        f"Highest average daily turnover: {highest_turnover.Company} (Rs. {highest_turnover['Avg turnover (Rs.)']:,.0f}).",
        f"Highest average delivery ratio: {highest_delivery.Company} ({highest_delivery['Avg delivery (%)']:.2f}%).",
    ]
    for item in bullets:
        story.append(Paragraph("&bull; " + item, styles["BodyText"]))
    story.extend([Spacer(1, 12), Paragraph("Company summary", styles["Heading1"])])
    table_data = [["Company", "Rows", "First close", "Last close", "Period return", "Avg delivery"]]
    for _, row in metrics.iterrows():
        table_data.append([
            row.Company, f"{int(row.Observations):,}", f"{row['First close']:,.2f}",
            f"{row['Last close']:,.2f}", f"{row['Return (%)']:.2f}%", f"{row['Avg delivery (%)']:.2f}%",
        ])
    table = Table(table_data, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#16324f")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eef3f7")]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#c8d2dc")),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.extend([table, PageBreak(), Paragraph("Insight charts", styles["Heading1"])])
    for i, chart in enumerate(charts):
        if i == 4:
            story.extend([PageBreak(), Paragraph("Univariate, bivariate and multivariate EDA", styles["Heading1"])])
        story.append(Image(str(chart), width=7.15 * inch, height=3.68 * inch))
        if i % 2 == 1 and i < len(charts) - 1:
            story.append(PageBreak())
    story.extend([
        Spacer(1, 8),
        Paragraph("Notes", styles["Heading2"]),
        Paragraph(
            "All figures are descriptive summaries of the provided CSV data. Period return is calculated as "
            "(last close / first close - 1) x 100 using chronologically sorted observations. Average turnover "
            "and delivery use available non-null values. This report is for project analysis and is not investment advice.",
            styles["BodyText"],
        ),
    ])
    doc.build(story)


def main() -> None:
    df = load_data()
    metrics = calculate_metrics(df)
    charts = save_charts(df, metrics)
    make_pdf(df, metrics, charts)
    print(f"Created {len(charts)} charts in {CHARTS}")
    print(f"Created report: {PDF_PATH}")


if __name__ == "__main__":
    main()
