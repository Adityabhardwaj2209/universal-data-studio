import hashlib
import hmac
import json
import secrets
import smtplib
import sqlite3
import time
from email.message import EmailMessage
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
DATABASE = ROOT / "private" / "accounts.db"


def database():
    DATABASE.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DATABASE)
    con.execute(
        "CREATE TABLE IF NOT EXISTS users "
        "(email TEXT PRIMARY KEY, salt TEXT NOT NULL, digest TEXT NOT NULL)"
    )
    columns = {r[1] for r in con.execute("PRAGMA table_info(users)")}
    if "verified" not in columns:
        con.execute(
            "ALTER TABLE users ADD COLUMN verified INTEGER NOT NULL DEFAULT 0"
        )
    con.execute(
        "CREATE TABLE IF NOT EXISTS verification "
        "(email TEXT PRIMARY KEY, token_hash TEXT NOT NULL, expires REAL NOT NULL)"
    )
    con.commit()
    return con


def hash_password(password, salt):
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), 600000
    ).hex()


def send_verification(email):
    config = json.loads(
        (ROOT / "private" / "mail.json").read_text(encoding="utf-8")
    )
    token = secrets.token_urlsafe(32)
    digest = hashlib.sha256(token.encode()).hexdigest()
    link = config["base_url"].rstrip("/") + "/?verify=" + token

    message = EmailMessage()
    message["Subject"] = "Verify your Sales Studio account"
    message["From"] = config["username"]
    message["To"] = email
    message.set_content(
        "Welcome to Sales Studio!\n\n"
        "Open this link and click Confirm verification:\n"
        + link + "\n\nThis link expires in 30 minutes.\n"
        "If you did not request this, ignore this message."
    )

    con = database()
    try:
        con.execute(
            "INSERT OR REPLACE INTO verification VALUES (?, ?, ?)",
            (email, digest, time.time() + 1800),
        )
        with smtplib.SMTP_SSL(
            config["host"], config["port"], timeout=20
        ) as smtp:
            smtp.login(config["username"], config["password"])
            smtp.send_message(message)
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def require_login():
    token = st.query_params.get("verify")
    if token:
        st.title("Verify your email")
        st.write("Confirm to activate your Sales Studio account.")
        if st.button("Confirm verification"):
            digest = hashlib.sha256(token.encode()).hexdigest()
            con = database()
            try:
                con.execute("BEGIN IMMEDIATE")
                row = con.execute(
                    "SELECT email FROM verification "
                    "WHERE token_hash = ? AND expires > ?",
                    (digest, time.time()),
                ).fetchone()
                if row:
                    con.execute(
                        "UPDATE users SET verified = 1 WHERE email = ?",
                        (row[0],),
                    )
                    con.execute(
                        "DELETE FROM verification WHERE email = ?", (row[0],)
                    )
                    con.commit()
                    st.success("Email verified. Return to Sign in.")
                else:
                    con.rollback()
                    st.error("Link expired or already used. Request a new one.")
            finally:
                con.close()
        if st.button("Return to Sign in"):
            st.query_params.clear()
            st.rerun()
        st.stop()

    if st.session_state.get("account_email"):
        with st.sidebar:
            st.caption("SIGNED IN")
            st.write(st.session_state["account_email"])
            if st.button("Sign out", key="email_signout"):
                st.session_state.clear()
                st.rerun()
        return

    st.title("Welcome to Sales Studio")
    mode = st.radio(
        "Account",
        ["Sign in", "Create account", "Resend verification"],
        horizontal=True,
    )
    st.caption("Existing accounts also need to verify their email.")

    with st.form("email_account"):
        email = st.text_input("Email").strip().lower()
        password = ""
        confirmation = ""
        if mode != "Resend verification":
            password = st.text_input("Password", type="password")
        if mode == "Create account":
            confirmation = st.text_input("Confirm password", type="password")
            st.caption("Use 12 or more characters.")
        submitted = st.form_submit_button(mode)

    if submitted:
        import re
        now = time.time()
        if now < st.session_state.get("auth_retry_after", 0):
            st.warning("Please wait before trying again.")
            st.stop()
        st.session_state["auth_retry_after"] = now + 5

        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            st.error("Enter a valid email.")
            st.stop()

        con = database()
        row = con.execute(
            "SELECT salt, digest, verified FROM users WHERE email = ?",
            (email,),
        ).fetchone()

        try:
            if mode == "Create account":
                if not 12 <= len(password) <= 256:
                    st.error("Use a password with 12 to 256 characters.")
                elif password != confirmation:
                    st.error("Passwords do not match.")
                elif row:
                    st.info("Use Sign in or Resend verification.")
                else:
                    salt = secrets.token_hex(16)
                    con.execute(
                        "INSERT INTO users (email, salt, digest, verified) "
                        "VALUES (?, ?, ?, 0)",
                        (email, salt, hash_password(password, salt)),
                    )
                    con.commit()
                    send_verification(email)
                    st.success(
                        "Account created. Check Inbox and Spam for verification."
                    )

            elif mode == "Resend verification":
                if row and not row[2]:
                    send_verification(email)
                st.success(
                    "If an unverified account exists, a verification email was sent."
                )

            else:
                if len(password) > 256:
                    st.error("Invalid email or password.")
                else:
                    salt = row[0] if row else "00" * 16
                    calculated = hash_password(password, salt)
                    valid = hmac.compare_digest(
                        calculated, row[1] if row else "0" * 64
                    )
                    if not row or not valid:
                        st.error("Invalid email or password.")
                    elif not row[2]:
                        st.warning("Verify your email first. Use Resend verification.")
                    else:
                        st.session_state["account_email"] = email
                        st.rerun()
        except (OSError, ValueError, smtplib.SMTPException):
            st.error(
                "Email could not be sent. Check your SMTP configuration, "
                "then use Resend verification."
            )
        finally:
            con.close()

    st.stop()
