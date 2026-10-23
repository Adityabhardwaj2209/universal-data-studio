from pathlib import Path
import sqlite3

DATABASE = Path(__file__).resolve().parent.parent / "private" / "workspace.db"


def connection():
    DATABASE.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DATABASE)
    con.execute(
        "CREATE TABLE IF NOT EXISTS brand_profiles ("
        "owner TEXT PRIMARY KEY,"
        "company TEXT NOT NULL,"
        "title TEXT NOT NULL,"
        "logo BLOB)"
    )
    con.commit()
    return con


def load_brand(owner):
    con = connection()
    try:
        row = con.execute(
            "SELECT company, title, logo FROM brand_profiles WHERE owner = ?",
            (owner,),
        ).fetchone()
    finally:
        con.close()

    if row is None:
        return {
            "company": "My Business",
            "title": "Sales Performance Report",
            "logo": None,
        }
    return {"company": row[0], "title": row[1], "logo": row[2]}


def save_brand(owner, company, title, logo):
    if not owner:
        raise ValueError("Sign in before saving branding.")
    if not company.strip() or not title.strip():
        raise ValueError("Business name and title are required.")
    if len(company) > 100 or len(title) > 150:
        raise ValueError("Business name or title is too long.")
    if logo is not None and len(logo) > 5 * 1024 * 1024:
        raise ValueError("Logo is too large to save.")

    con = connection()
    try:
        con.execute(
            "INSERT INTO brand_profiles(owner, company, title, logo) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(owner) DO UPDATE SET "
            "company=excluded.company, title=excluded.title, logo=excluded.logo",
            (owner, company.strip(), title.strip(), logo),
        )
        con.commit()
    finally:
        con.close()
