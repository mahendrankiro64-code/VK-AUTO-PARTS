"""Database helper module for VK Auto Parts system.

Uses plain sqlite3 (no ORM) so the app has zero external dependencies
beyond Flask + pandas/openpyxl (for Excel import/export). This keeps
deployment on free hosts (PythonAnywhere, etc.) simple.
"""
import os
import sqlite3
from flask import g, current_app

DB_PATH = os.environ.get(
    "VKAP_DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "instance", "vkap.db"),
)


def get_db():
    if "db" not in g:
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(app):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    conn = sqlite3.connect(DB_PATH)
    with open(schema_path, "r") as f:
        conn.executescript(f.read())
    conn.commit()
    conn.close()
    app.teardown_appcontext(close_db)


def get_setting(db, key, default=None):
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(db, key, value):
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    db.commit()


def next_sequence_code(db, seq_key, prefix, pad=4):
    """Generate the next auto-incrementing code like VKAP-0001.

    seq_key is the settings key used to persist the counter, e.g. 'item_seq'.
    """
    current = int(get_setting(db, seq_key, "0"))
    nxt = current + 1
    set_setting(db, seq_key, nxt)
    return f"{prefix}-{str(nxt).zfill(pad)}"
