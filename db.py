"""Database helper module for VK Auto Parts system.

Backed by PostgreSQL (Supabase, Render Postgres, Fly Postgres, Neon, etc.)
via psycopg2, instead of the local-file SQLite used in the first version of
this app. This lets the app run on hosts that don't offer persistent local
disk storage (e.g. Netlify Functions, Cloud Run) as long as they can reach an
external Postgres database over the network.

A thin wrapper class keeps the rest of the codebase (every blueprint) using
the same sqlite3-style calling convention it was written with:
    db.execute(sql, params).fetchone() / .fetchall()
    db.commit()
even though the underlying driver is psycopg2. It also transparently
translates the SQLite-style '?' placeholders used throughout the app into
psycopg2's '%s' placeholders, so the blueprint files did not need to change.
"""
import os
import psycopg2
import psycopg2.extras
from flask import g

DATABASE_URL = os.environ.get("DATABASE_URL")


class DBWrapper:
    """Minimal sqlite3-connection-like shim around a psycopg2 connection."""

    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=()):
        cur = self.conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql.replace("?", "%s"), tuple(params))
        return cur

    def commit(self):
        self.conn.commit()

    def close(self):
        self.conn.close()


def _connect():
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. Set it to your "
            "Postgres connection string (e.g. from Supabase: Project Settings "
            "-> Database -> Connection string -> URI)."
        )
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    return conn


def get_db():
    if "db" not in g:
        g.db = DBWrapper(_connect())
    return g.db


def close_db(e=None):
    wrapper = g.pop("db", None)
    if wrapper is not None:
        wrapper.close()


def init_db(app):
    """Create tables if they don't exist yet. Safe to call on every boot."""
    schema_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
    conn = _connect()
    cur = conn.cursor()
    with open(schema_path, "r") as f:
        cur.execute(f.read())
    conn.commit()
    cur.close()
    conn.close()
    app.teardown_appcontext(close_db)


def is_fresh_database():
    """True if this looks like a brand-new database (no users yet)."""
    conn = _connect()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    count = cur.fetchone()[0]
    cur.close()
    conn.close()
    return count == 0


def get_setting(db, key, default=None):
    row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(db, key, value):
    db.execute(
        "INSERT INTO settings (key, value) VALUES (?, ?) "
        "ON CONFLICT (key) DO UPDATE SET value = excluded.value",
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
