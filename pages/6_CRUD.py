"""Create, inspect, update, and delete daily stock records."""

import sqlite3

import pandas as pd
import streamlit as st

from scripts.create_stock_database import DB_PATH, build_database
from scripts.dashboard_theme import apply_sidebar_theme, render_page_hero, render_sidebar_insights

st.set_page_config(page_title="CRUD | Stock Market Analysis", page_icon="🗃️", layout="wide")
apply_sidebar_theme("CRUD operations", "Read stock and benchmark records, and maintain company-day observations in the SQLite database.")
render_page_hero("Equity research workspace / data operations", "CRUD data management", "Read market benchmark history and maintain daily company observations in the SQLite database.")
if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
    build_database()

def read_records() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as connection:
        return pd.read_sql_query("SELECT * FROM stock_prices ORDER BY date DESC, company", connection, parse_dates=["date"])

data = read_records()
if data.empty:
    st.warning("There are no records in the database.")
    st.stop()

tab_create, tab_browse, tab_edit, tab_delete = st.tabs(
    ["Create record", "Read records", "Update records", "Delete record"]
)
companies = sorted(data.company.dropna().unique())
editable = ["open_price", "high_price", "low_price", "close_price", "wap", "shares_traded", "trades", "turnover", "deliverable_quantity", "deliverable_pct", "spread_high_low", "spread_close_open"]
labels = {"open_price": "Open price (Rs.)", "high_price": "High price (Rs.)", "low_price": "Low price (Rs.)",
          "close_price": "Close price (Rs.)", "wap": "Weighted average price (Rs.)", "shares_traded": "Shares traded",
          "trades": "Number of trades", "turnover": "Turnover (Rs.)", "deliverable_quantity": "Deliverable quantity",
          "deliverable_pct": "Delivery (%)", "spread_high_low": "High-low spread", "spread_close_open": "Close-open spread"}

def numeric_inputs(prefix: str, initial: dict | None = None) -> dict:
    initial = initial or {}
    result = {}
    col_a, col_b, col_c = st.columns(3)
    columns = [col_a, col_b, col_c]
    for i, name in enumerate(editable):
        current = initial.get(name)
        value = float(current) if pd.notna(current) else 0.0
        options = {"min_value": 0.0} if name in {
            "open_price", "high_price", "low_price", "close_price", "wap", "shares_traded",
            "trades", "turnover", "deliverable_quantity", "deliverable_pct",
        } else {}
        result[name] = columns[i % 3].number_input(labels[name], value=value, format="%.4f", key=f"{prefix}_{name}", **options)
    return result

def validate_values(values: dict) -> str | None:
    if values["deliverable_pct"] > 100:
        return "Delivery percentage must be between 0 and 100."
    if values["high_price"] < values["low_price"]:
        return "High price must be greater than or equal to low price."
    if not values["low_price"] <= values["close_price"] <= values["high_price"]:
        return "Close price must fall between the low and high prices."
    return None

with tab_create:
    st.write("Add a daily observation for a company. A company/date pair must be unique.")
    with st.form("create_record"):
        col1, col2 = st.columns(2)
        company = col1.selectbox("Company", companies, key="create_company")
        date = col2.date_input("Trading date", key="create_date")
        values = numeric_inputs("create")
        submitted = st.form_submit_button("Create record", type="primary")
    if submitted:
        date_text = date.isoformat()
        validation_error = validate_values(values)
        if validation_error:
            st.error(validation_error)
        else:
            try:
                with sqlite3.connect(DB_PATH) as connection:
                    exists = connection.execute("SELECT 1 FROM stock_prices WHERE company=? AND date=?", (company, date_text)).fetchone()
                    if exists:
                        st.error("A record already exists for that company and date.")
                    else:
                        fields = ["company", "date", *editable]
                        connection.execute(
                            f"INSERT INTO stock_prices ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                            [company, date_text, *[values[field] for field in editable]],
                        )
                        st.success("Record created.")
                        st.rerun()
            except sqlite3.Error as exc:
                st.error(f"Could not create record: {exc}")

with tab_browse:
    with st.container(border=True):
        st.subheader("Read records")
        st.caption("Records are identified by company and date. Saves update the database immediately.")
        company_filter = st.selectbox("Company filter", ["All companies", *sorted(data.company.dropna().unique())])
        shown = data if company_filter == "All companies" else data[data.company == company_filter]
        record_insights = [("Records shown", f"{len(shown):,}")]
        if not shown.empty:
            latest_record = shown.loc[shown.date.idxmax()]
            record_insights.extend([
                ("Companies represented", f"{shown.company.nunique():,}"),
                ("Latest observation", f"{latest_record.company}, {latest_record.date:%d %b %Y}"),
            ])
            if shown.close_price.notna().any():
                record_insights.append(("Average close", f"Rs. {shown.close_price.mean():,.2f}"))
        render_sidebar_insights(record_insights, heading="Record insights")
        st.dataframe(shown.head(500), use_container_width=True, hide_index=True)
        st.caption(f"Showing up to 500 of {len(shown):,} matching rows.")

        st.divider()
        st.subheader("Market benchmark records")
        try:
            with sqlite3.connect(DB_PATH) as connection:
                benchmark_records = pd.read_sql_query(
                    "SELECT index_name, date, open_value, high_value, low_value, close_value, change_pct "
                    "FROM market_indices ORDER BY date DESC, index_name",
                    connection,
                )
        except sqlite3.OperationalError:
            benchmark_records = pd.DataFrame()

        if benchmark_records.empty:
            st.info("No benchmark index records are available in the database yet.")
        else:
            selected_index = st.selectbox(
                "Benchmark index",
                ["All indices", *sorted(benchmark_records.index_name.dropna().unique())],
                key="read_benchmark_index",
            )
            visible_benchmarks = benchmark_records if selected_index == "All indices" else benchmark_records[benchmark_records.index_name == selected_index]
            st.dataframe(
                visible_benchmarks.head(500).rename(columns={
                    "index_name": "Index", "date": "Date", "open_value": "Open",
                    "high_value": "High", "low_value": "Low", "close_value": "Close",
                    "change_pct": "Change (%)",
                }).style.format({"Open": "{:,.2f}", "High": "{:,.2f}", "Low": "{:,.2f}", "Close": "{:,.2f}", "Change (%)": "{:+.2f}"}),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(f"Showing up to 500 of {len(visible_benchmarks):,} matching index observations.")

with tab_edit:
    if len(data):
        keys = data[["company", "date"]].drop_duplicates().copy()
        keys["key"] = keys.company + " · " + keys.date.dt.strftime("%Y-%m-%d")
        selected_key = st.selectbox("Select record", keys.key.tolist(), key="edit_record_key")
        row_key = keys.loc[keys.key == selected_key].iloc[0]
        current = data[(data.company == row_key.company) & (data.date == row_key.date)].iloc[0]
        with st.form("edit_record"):
            values = numeric_inputs("edit", current.to_dict())
            submitted = st.form_submit_button("Save changes", type="primary")
        if submitted:
            validation_error = validate_values(values)
            if validation_error:
                st.error(validation_error)
            else:
                try:
                    assignments = ", ".join(f"{field}=?" for field in editable)
                    with sqlite3.connect(DB_PATH) as connection:
                        connection.execute(f"UPDATE stock_prices SET {assignments} WHERE company=? AND date=?",
                                           [*[values[field] for field in editable], row_key.company, row_key.date.strftime("%Y-%m-%d")])
                    st.success("Record updated.")
                    st.rerun()
                except sqlite3.Error as exc:
                    st.error(f"Could not update record: {exc}")

with tab_delete, st.container(border=True):
    keys = data[["company", "date"]].drop_duplicates().copy()
    keys["key"] = keys.company + " · " + keys.date.dt.strftime("%Y-%m-%d")
    selected_key = st.selectbox("Select record to delete", keys.key.tolist(), key="delete_record_key")
    row_key = keys.loc[keys.key == selected_key].iloc[0]
    st.warning(f"This will permanently delete {row_key.company} on {row_key.date:%Y-%m-%d}.")
    confirmed = st.checkbox("I confirm this deletion", key="confirm_delete")
    if st.button("Delete selected record", type="primary", disabled=not confirmed):
        try:
            with sqlite3.connect(DB_PATH) as connection:
                connection.execute("DELETE FROM stock_prices WHERE company=? AND date=?",
                                   (row_key.company, row_key.date.strftime("%Y-%m-%d")))
            st.success("Record deleted.")
            st.rerun()
        except sqlite3.Error as exc:
            st.error(f"Could not delete record: {exc}")
