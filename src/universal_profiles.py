from pathlib import Path
import json
import sqlite3

import pandas as pd
import streamlit as st

DATABASE = Path(__file__).resolve().parent.parent / "private" / "workspace.db"


def connection():
    DATABASE.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DATABASE)
    con.execute(
        "CREATE TABLE IF NOT EXISTS universal_profiles ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT,"
        "owner TEXT NOT NULL,"
        "name TEXT NOT NULL,"
        "schema_json TEXT NOT NULL,"
        "settings_json TEXT NOT NULL,"
        "created TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    con.commit()
    return con


def validate_profile(schema, columns):
    required = {
        "Column", "Type", "Role", "Date format",
        "Number format", "Aggregation"
    }
    if not required.issubset(schema.columns):
        raise ValueError("Saved schema is incomplete.")
    if schema["Column"].duplicated().any():
        raise ValueError("Saved schema has duplicate fields.")
    if set(schema["Column"]) != set(columns):
        raise ValueError("Profile fields do not match this dataset.")
    from .universal import TYPES, ROLES, FORMATS, AGGREGATIONS
    for field, choices in [
        ("Type", TYPES), ("Role", ROLES),
        ("Number format", FORMATS), ("Aggregation", AGGREGATIONS),
    ]:
        if not schema[field].isin(choices).all():
            raise ValueError("Unsupported saved " + field)
    return schema.set_index("Column").loc[list(columns)].reset_index()


def choose_profile(suggested, identity):
    owner = st.session_state.get("account_email")
    if not owner:
        return suggested

    override_key = "profile_schema_override_" + identity

    with st.expander("Reuse a saved schema / dashboard"):
        con = connection()
        try:
            rows = con.execute(
                "SELECT id, name, created FROM universal_profiles "
                "WHERE owner = ? ORDER BY id DESC",
                (owner,),
            ).fetchall()
        finally:
            con.close()

        if not rows:
            st.caption("No saved universal profiles yet.")
            return st.session_state.get(override_key, suggested)

        labels = {
            row[0]: f"{row[1]} | {row[2]} UTC | #{row[0]}"
            for row in rows
        }
        selected = st.selectbox(
            "Saved profile",
            list(labels),
            format_func=lambda value: labels[value],
            key="profile_choice_" + identity,
        )

        if st.button("Load profile", key="profile_load_" + identity):
            con = connection()
            try:
                row = con.execute(
                    "SELECT schema_json, settings_json FROM universal_profiles "
                    "WHERE id = ? AND owner = ?",
                    (selected, owner),
                ).fetchone()
            finally:
                con.close()

            try:
                if row is None:
                    raise ValueError("Profile no longer exists.")
                schema = validate_profile(
                    pd.DataFrame(json.loads(row[0])),
                    suggested["Column"].tolist(),
                )
                from datetime import date
                def decode(item):
                    if isinstance(item, dict) and set(item) == {"__date__"}:
                        return date.fromisoformat(item["__date__"][:10])
                    return item
                settings = json.loads(row[1], object_hook=decode)

                # Clear old widget state before loading this profile.
                prefix = "ud_" + identity
                for key in list(st.session_state):
                    if isinstance(key, str) and key.startswith(prefix + "_"):
                        del st.session_state[key]
                for suffix, value in settings.items():
                    if isinstance(suffix, str) and suffix.startswith("_"):
                        st.session_state[prefix + suffix] = value

                st.session_state[override_key] = schema
                st.session_state.pop("confirmed_schema_" + identity, None)
                editor_key = "schema_editor_" + identity
                st.session_state.pop(editor_key, None)
                st.rerun()
            except (ValueError, TypeError, KeyError) as error:
                st.error(str(error))

        if st.button(
            "Use automatic suggestions",
            key="profile_reset_" + identity,
        ):
            st.session_state.pop(override_key, None)
            st.session_state.pop("confirmed_schema_" + identity, None)
            st.session_state.pop("schema_editor_" + identity, None)
            st.rerun()

        delete = st.checkbox(
            "Delete selected profile",
            key="profile_delete_confirm_" + identity,
        )
        if st.button(
            "Delete profile",
            disabled=not delete,
            key="profile_delete_" + identity,
        ):
            con = connection()
            try:
                con.execute(
                    "DELETE FROM universal_profiles WHERE id = ? AND owner = ?",
                    (selected, owner),
                )
                con.commit()
            finally:
                con.close()
            st.rerun()

    return st.session_state.get(override_key, suggested)


def save_profile_panel(schema, identity):
    owner = st.session_state.get("account_email")
    if not owner:
        return

    with st.expander("Save schema and dashboard settings"):
        st.caption(
            "Saves field types, roles, numeric/date formats, "
            "chart choices and KPI settings. Dataset rows are not stored."
        )
        with st.form("profile_save_form_" + identity):
            name = st.text_input(
                "Profile name",
                placeholder="Football player statistics",
                max_chars=100,
            ).strip()
            save = st.form_submit_button("Save profile")

        if save:
            if not name:
                st.warning("Enter a profile name.")
                return

            prefix = "ud_" + identity
            settings = {}
            for key, value in st.session_state.items():
                if (
                    isinstance(key, str)
                    and key.startswith(prefix + "_")
                    and not key.endswith("_download")
                ):
                    try:
                        # Date objects in date filters need an explicit marker.
                        from datetime import date, datetime
                        def encode(item):
                            if isinstance(item, (date, datetime)):
                                return {"__date__": item.isoformat()}
                            raise TypeError()
                        settings[key[len(prefix):]] = json.loads(
                            json.dumps(value, default=encode)
                        )
                    except (TypeError, ValueError):
                        pass

            con = connection()
            try:
                con.execute(
                    "INSERT INTO universal_profiles "
                    "(owner, name, schema_json, settings_json) VALUES (?, ?, ?, ?)",
                    (
                        owner, name,
                        schema.to_json(orient="records"),
                        json.dumps(settings),
                    ),
                )
                con.commit()
            finally:
                con.close()
            st.success("Profile saved for your account.")
