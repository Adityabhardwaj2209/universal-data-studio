from pathlib import Path
import hashlib
import hmac
import re
import secrets
import sqlite3

import altair as alt
import streamlit as st

DATABASE = Path(__file__).resolve().parent.parent / "private" / "accounts.db"


def connect_db():
    DATABASE.parent.mkdir(exist_ok=True)
    connection = sqlite3.connect(DATABASE)
    connection.execute(
        "CREATE TABLE IF NOT EXISTS users "
        "(email TEXT PRIMARY KEY, salt TEXT NOT NULL, digest TEXT NOT NULL)"
    )
    connection.commit()
    return connection


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"),
        bytes.fromhex(salt), 600000
    ).hex()


def require_login():
    st.markdown(
        """
        <style>
        h1, h2, h3 { font-weight: 800 !important; }
        [data-testid="stMetricValue"] { font-weight: 800 !important; }
        [data-testid="stWidgetLabel"] p,
        [data-baseweb="tab"] p {
            font-weight: 700 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.get("account_email"):
        with st.sidebar:
            st.caption("SIGNED IN")
            st.write(st.session_state["account_email"])
            if st.button("Sign out", key="account_signout"):
                st.session_state.clear()
                st.rerun()
        return

    left, center, right = st.columns([1, 2, 1])
    with center:
        st.title("Welcome to Sales Studio")
        st.write("Sign in to open your sales workspace.")
        mode = st.radio(
            "Account",
            ["Sign in", "Create account"],
            horizontal=True,
            label_visibility="collapsed",
        )

        with st.form("account_form"):
            email = st.text_input("Email").strip().lower()
            password = st.text_input("Password", type="password")
            confirmation = None
            if mode == "Create account":
                confirmation = st.text_input(
                    "Confirm password", type="password"
                )
                st.caption("Use 12 or more characters.")
            submitted = st.form_submit_button(
                mode, use_container_width=True
            )

        if submitted:
            if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                st.error("Enter a valid email address.")
            elif len(password) > 256:
                st.error("Password must be at most 256 characters.")
            elif mode == "Create account":
                if len(password) < 12:
                    st.error("Use at least 12 characters.")
                elif password != confirmation:
                    st.error("Passwords do not match.")
                else:
                    salt = secrets.token_hex(16)
                    digest = password_hash(password, salt)
                    connection = connect_db()
                    try:
                        connection.execute(
                            "INSERT INTO users VALUES (?, ?, ?)",
                            (email, salt, digest),
                        )
                        connection.commit()
                        st.success("Account created. Choose Sign in above.")
                    except sqlite3.IntegrityError:
                        st.error("Unable to create account with this email.")
                    finally:
                        connection.close()
            else:
                import time
                now = time.time()
                if now < st.session_state.get("login_retry_after", 0):
                    st.error("Please wait a moment before trying again.")
                else:
                    connection = connect_db()
                    row = connection.execute(
                        "SELECT salt, digest FROM users WHERE email = ?",
                        (email,),
                    ).fetchone()
                    connection.close()
                    salt = row[0] if row else "00" * 16
                    digest = password_hash(password, salt)
                    valid = hmac.compare_digest(
                        digest, row[1] if row else "0" * 64
                    )
                    if row and valid:
                        st.session_state["account_email"] = email
                        st.session_state.pop("login_retry_after", None)
                        st.rerun()
                    else:
                        st.session_state["login_retry_after"] = now + 3
                        st.error("Invalid email or password.")

    st.stop()


def draw_chart(data, kind, color):
    frame = data.copy()
    frame.index.name = "Label"
    frame = frame.reset_index()
    frame["Label"] = frame["Label"].astype(str)
    metric = frame.columns[1]
    chart = alt.Chart(frame)

    if kind == "line":
        chart = chart.mark_line(
            color=color, strokeWidth=4, point=True
        )
    else:
        chart = chart.mark_bar(
            color=color, cornerRadiusTopLeft=6,
            cornerRadiusTopRight=6
        )

    chart = chart.encode(
        x=alt.X("Label:N", title=None, sort=None),
        y=alt.Y(
            field=metric, type="quantitative", title=str(metric)
        ),
        tooltip=[
            alt.Tooltip("Label:N", title="Label"),
            alt.Tooltip(
                field=metric, type="quantitative", format=",.2f"
            ),
        ],
    ).properties(height=350).configure_axis(
        labelFontSize=14,
        labelFontWeight="bold",
        titleFontSize=16,
        titleFontWeight="bold",
        labelColor="#43205F",
        titleColor="#43205F",
        gridColor="#DCCDE5",
    ).configure_view(strokeWidth=0)

    st.altair_chart(chart, use_container_width=True)


def bold_line_chart(data, color="#8756AC", **kwargs):
    draw_chart(data, "line", color)


def bold_bar_chart(data, color="#B05D96", **kwargs):
    draw_chart(data, "bar", color)
