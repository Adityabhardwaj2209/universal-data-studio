from io import StringIO
from pathlib import Path
import hashlib
import json
import sqlite3
from datetime import date

import pandas as pd
import streamlit as st

DATABASE = Path(__file__).resolve().parent.parent / "private" / "workspace.db"


def connect():
    DATABASE.parent.mkdir(exist_ok=True)
    connection = sqlite3.connect(DATABASE)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS snapshots ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "owner TEXT NOT NULL,"
        "name TEXT NOT NULL,"
        "created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,"
        "sales TEXT NOT NULL,"
        "issues TEXT NOT NULL,"
        "preferences TEXT NOT NULL)"
    )
    connection.execute(
        "CREATE INDEX IF NOT EXISTS snapshot_owner "
        "ON snapshots(owner)"
    )
    connection.commit()
    return connection


def workspace_prefix(data):
    identity = hashlib.sha256(
        pd.util.hash_pandas_object(data, index=True)
        .values.tobytes()
    ).hexdigest()[:12]
    return "workspace_" + identity


def read_frame(payload):
    return pd.read_json(StringIO(payload), orient="table")


def history_panel(clean, issues):
    owner = st.session_state.get("account_email")
    if not owner:
        st.error("Sign in to use saved reports.")
        st.stop()

    active_key = "saved_active_" + owner
    active = st.session_state.get(active_key)
    if active is not None:
        clean, issues = active["clean"], active["issues"]

    prefix = workspace_prefix(clean)

    with st.expander("Saved reports and preferences"):
        st.caption(
            "Snapshots include the complete validated dataset, remaining "
            "issues, applied filters, chart settings and session target. "
            "Only this signed-in account can access them through the app."
        )

        if active is not None:
            st.info("Viewing saved report: " + active["name"])
            if st.button("Return to uploaded data", key="history_return"):
                st.session_state.pop(active_key, None)
                st.rerun()

        with st.form("save_snapshot_form"):
            name = st.text_input(
                "Report name",
                placeholder="October sales review",
                max_chars=100,
            ).strip()
            save = st.form_submit_button("Save report and preferences")

        if save:
            if not name:
                st.warning("Enter a report name.")
            else:
                preferences = {}
                if prefix in st.session_state:
                    filters = st.session_state[prefix]
                    preferences["filters"] = {
                        "dates": [str(d) for d in filters["dates"]],
                        "categories": list(filters["categories"]),
                        "products": list(filters["products"]),
                    }

                suffixes = [
                    "_kind", "_group", "_metric", "_colour",
                    "_limit", "_sort", "_descending", "_target",
                ]
                for suffix in suffixes:
                    key = prefix + suffix
                    if key in st.session_state:
                        preferences[suffix] = st.session_state[key]

                with connect() as connection:
                    connection.execute(
                        "INSERT INTO snapshots "
                        "(owner, name, sales, issues, preferences) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            owner,
                            name,
                            clean.to_json(
                                orient="table", date_format="iso", index=False
                            ),
                            issues.to_json(
                                orient="table", date_format="iso", index=False
                            ),
                            json.dumps(preferences),
                        ),
                    )
                st.success("Report and preferences saved.")

        with connect() as connection:
            rows = connection.execute(
                "SELECT id, name, created FROM snapshots "
                "WHERE owner = ? ORDER BY id DESC",
                (owner,),
            ).fetchall()

        if not rows:
            st.caption("No saved reports yet.")
            return clean, issues

        labels = {
            row[0]: f"{row[1]} | {row[2]} UTC | #{row[0]}"
            for row in rows
        }
        selected = st.selectbox(
            "Your saved reports",
            list(labels),
            format_func=lambda value: labels[value],
            key="history_selected",
        )

        with connect() as connection:
            record = connection.execute(
                "SELECT name, sales, issues, preferences FROM snapshots "
                "WHERE id = ? AND owner = ?",
                (selected, owner),
            ).fetchone()

        if record is None:
            st.warning("Report is no longer available.")
            return clean, issues

        load_column, download_column = st.columns(2)

        if load_column.button("Open saved report", key="history_open"):
            restored_clean = read_frame(record[1])
            restored_issues = read_frame(record[2])
            restored_prefix = workspace_prefix(restored_clean)
            preferences = json.loads(record[3])

            if "filters" in preferences:
                filters = preferences["filters"]
                st.session_state[restored_prefix] = {
                    "dates": tuple(
                        date.fromisoformat(d) for d in filters["dates"]
                    ),
                    "categories": filters["categories"],
                    "products": filters["products"],
                }

            for suffix, value in preferences.items():
                if suffix != "filters":
                    st.session_state[restored_prefix + suffix] = value

            st.session_state[active_key] = {
                "name": record[0],
                "clean": restored_clean,
                "issues": restored_issues,
            }
            st.rerun()

        from .report import excel_safe
        snapshot_sales = read_frame(record[1])
        download_column.download_button(
            "Download saved sales CSV",
            excel_safe(snapshot_sales).to_csv(
                index=False
            ).encode("utf-8-sig"),
            file_name=f"saved_sales_{selected}.csv",
            mime="text/csv",
            key="history_csv",
        )

        st.caption(
            "Saved CSV contains the full snapshot. Use the dashboard "
            "Downloads tab to export its applied filters."
        )
        confirmed = st.checkbox(
            "Delete the selected saved report",
            key=f"history_confirm_{selected}",
        )
        if st.button(
            "Delete report",
            disabled=not confirmed,
            key=f"history_delete_{selected}",
        ):
            with connect() as connection:
                connection.execute(
                    "DELETE FROM snapshots WHERE id = ? AND owner = ?",
                    (selected, owner),
                )
            st.rerun()

    return clean, issues
