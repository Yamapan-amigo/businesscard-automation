"""SQLite database layer for contact and draft management."""

from __future__ import annotations

import json
import logging
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Generator

import config
import user_storage

logger = logging.getLogger(__name__)

DB_FILE: Path = config.BASE_DIR / "app.db"


def _db_path(username: str | None = None) -> Path:
    if username:
        return user_storage.get_db_path(username)
    return DB_FILE


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection(
    username: str | None = None,
) -> Generator[sqlite3.Connection, None, None]:
    db_path = _db_path(username)
    _ensure_parent_dir(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


_SCHEMA_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        card_id TEXT UNIQUE,
        name TEXT NOT NULL,
        name_reading TEXT DEFAULT '',
        email TEXT DEFAULT '',
        company TEXT DEFAULT '',
        department TEXT DEFAULT '',
        title TEXT DEFAULT '',
        phone TEXT DEFAULT '',
        mobile TEXT DEFAULT '',
        added_date TEXT DEFAULT '',
        scraped_at TEXT NOT NULL,
        raw_json TEXT DEFAULT ''
    )""",
    """CREATE TABLE IF NOT EXISTS processed (
        contact_id TEXT PRIMARY KEY,
        processed_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS templates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(email)",
    "CREATE INDEX IF NOT EXISTS idx_contacts_added_date ON contacts(added_date)",
]

_CONTACT_COLUMNS = [
    "card_id",
    "name",
    "name_reading",
    "email",
    "company",
    "department",
    "title",
    "phone",
    "mobile",
    "added_date",
    "scraped_at",
    "raw_json",
]
_TEMPLATE_COLUMNS = ["name", "body", "created_at", "updated_at"]
_SETTING_COLUMNS = ["key", "value"]


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def init_db(*, username: str | None = None) -> None:
    """Create tables if they don't exist."""
    with get_connection(username=username) as conn:
        for stmt in _SCHEMA_STATEMENTS:
            conn.execute(stmt)


# --- Contacts ---

def save_contacts(contacts: list[dict], *, username: str | None = None) -> int:
    """Insert contacts into DB. Returns number of newly inserted rows."""
    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    with get_connection(username=username) as conn:
        for c in contacts:
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO contacts
                       (card_id, name, name_reading, email, company,
                        department, title, phone, mobile, added_date,
                        scraped_at, raw_json)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        c.get("card_id", ""),
                        c.get("name", ""),
                        c.get("name_reading", ""),
                        c.get("email", ""),
                        c.get("company", ""),
                        c.get("department", ""),
                        c.get("title", ""),
                        c.get("phone", ""),
                        c.get("mobile", ""),
                        c.get("added_date", ""),
                        now,
                        json.dumps(c, ensure_ascii=False),
                    ),
                )
                if conn.execute("SELECT changes()").fetchone()[0] > 0:
                    inserted += 1
            except sqlite3.Error as e:
                logger.warning(
                    "連絡先の保存に失敗 (card_id=%s): %s",
                    c.get("card_id", "?"),
                    e,
                )
                continue
    return inserted


def get_contacts(
    *,
    username: str | None = None,
    since_date: str | None = None,
    target_date: str | None = None,
    unprocessed_only: bool = False,
) -> list[dict]:
    """Fetch contacts from DB with optional filters."""
    query = "SELECT * FROM contacts WHERE 1=1"
    params: list[str] = []

    if target_date:
        query += " AND added_date LIKE ?"
        params.append(f"{target_date}%")
    elif since_date:
        query += " AND added_date >= ?"
        params.append(since_date)

    if unprocessed_only:
        query += " AND card_id NOT IN (SELECT contact_id FROM processed)"

    query += " ORDER BY added_date DESC"

    with get_connection(username=username) as conn:
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]


# --- Processed tracking ---

def is_processed(contact_id: str, *, username: str | None = None) -> bool:
    with get_connection(username=username) as conn:
        row = conn.execute(
            "SELECT 1 FROM processed WHERE contact_id = ?", (contact_id,)
        ).fetchone()
        return row is not None


def mark_processed(
    contact_ids: list[str], *, username: str | None = None
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection(username=username) as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO processed (contact_id, processed_at) VALUES (?, ?)",
            [(cid, now) for cid in contact_ids],
        )


def get_processed_count(*, username: str | None = None) -> int:
    with get_connection(username=username) as conn:
        row = conn.execute("SELECT COUNT(*) FROM processed").fetchone()
        return row[0] if row else 0


def clear_processed(*, username: str | None = None) -> int:
    """Clear all processed records. Returns number of deleted rows."""
    with get_connection(username=username) as conn:
        conn.execute("DELETE FROM processed")
        row = conn.execute("SELECT changes()").fetchone()
        return row[0] if row else 0


# --- Templates ---

def save_template(
    name: str, body: str, *, username: str | None = None
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    with get_connection(username=username) as conn:
        conn.execute(
            """INSERT INTO templates (name, body, created_at, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(name) DO UPDATE SET body=?, updated_at=?""",
            (name, body, now, now, body, now),
        )


def delete_template(name: str, *, username: str | None = None) -> None:
    with get_connection(username=username) as conn:
        conn.execute("DELETE FROM templates WHERE name = ?", (name,))


def get_template(name: str, *, username: str | None = None) -> str | None:
    with get_connection(username=username) as conn:
        row = conn.execute(
            "SELECT body FROM templates WHERE name = ?", (name,)
        ).fetchone()
        return row["body"] if row else None


def list_templates(*, username: str | None = None) -> list[dict]:
    with get_connection(username=username) as conn:
        rows = conn.execute(
            "SELECT name, updated_at FROM templates ORDER BY name"
        ).fetchall()
        return [dict(row) for row in rows]


# --- Settings ---

def get_setting(
    key: str, default: str = "", *, username: str | None = None
) -> str:
    with get_connection(username=username) as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


def set_setting(
    key: str, value: str, *, username: str | None = None
) -> None:
    with get_connection(username=username) as conn:
        conn.execute(
            """INSERT INTO settings (key, value) VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE SET value=?""",
            (key, value, value),
        )


# --- Migration from JSON ---

def migrate_from_json(*, username: str | None = None) -> None:
    """Import existing processed contacts from JSON file into SQLite."""
    json_path = config.PROCESSED_FILE
    if not json_path.exists():
        return
    data = json.loads(json_path.read_text(encoding="utf-8"))
    ids = data.get("processed_ids", [])
    if ids:
        mark_processed(ids, username=username)


def import_shared_db(
    *,
    username: str,
    source_path: Path | None = None,
) -> dict[str, int]:
    """Copy data from the legacy shared DB into a user-scoped DB."""
    source = source_path or DB_FILE
    target = _db_path(username)
    if not source.exists():
        return {"contacts": 0, "processed": 0, "templates": 0, "settings": 0}
    if source.resolve() == target.resolve():
        return {"contacts": 0, "processed": 0, "templates": 0, "settings": 0}

    init_db(username=username)
    counts = {"contacts": 0, "processed": 0, "templates": 0, "settings": 0}

    source_conn = sqlite3.connect(str(source))
    source_conn.row_factory = sqlite3.Row
    try:
        with get_connection(username=username) as target_conn:
            if _table_exists(source_conn, "contacts"):
                rows = source_conn.execute(
                    f"SELECT {', '.join(_CONTACT_COLUMNS)} FROM contacts"
                ).fetchall()
                for row in rows:
                    values = tuple(row[col] for col in _CONTACT_COLUMNS)
                    target_conn.execute(
                        """INSERT OR IGNORE INTO contacts
                           (card_id, name, name_reading, email, company,
                            department, title, phone, mobile, added_date,
                            scraped_at, raw_json)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        values,
                    )
                    if target_conn.execute("SELECT changes()").fetchone()[0] > 0:
                        counts["contacts"] += 1

            if _table_exists(source_conn, "processed"):
                rows = source_conn.execute(
                    "SELECT contact_id, processed_at FROM processed"
                ).fetchall()
                for row in rows:
                    target_conn.execute(
                        "INSERT OR IGNORE INTO processed (contact_id, processed_at) VALUES (?, ?)",
                        (row["contact_id"], row["processed_at"]),
                    )
                    if target_conn.execute("SELECT changes()").fetchone()[0] > 0:
                        counts["processed"] += 1

            if _table_exists(source_conn, "templates"):
                rows = source_conn.execute(
                    f"SELECT {', '.join(_TEMPLATE_COLUMNS)} FROM templates"
                ).fetchall()
                for row in rows:
                    target_conn.execute(
                        """INSERT INTO templates (name, body, created_at, updated_at)
                           VALUES (?, ?, ?, ?)
                           ON CONFLICT(name) DO UPDATE SET body=?, updated_at=?""",
                        (
                            row["name"],
                            row["body"],
                            row["created_at"],
                            row["updated_at"],
                            row["body"],
                            row["updated_at"],
                        ),
                    )
                    counts["templates"] += 1

            if _table_exists(source_conn, "settings"):
                rows = source_conn.execute(
                    f"SELECT {', '.join(_SETTING_COLUMNS)} FROM settings"
                ).fetchall()
                for row in rows:
                    target_conn.execute(
                        """INSERT INTO settings (key, value) VALUES (?, ?)
                           ON CONFLICT(key) DO UPDATE SET value=?""",
                        (row["key"], row["value"], row["value"]),
                    )
                    counts["settings"] += 1
    finally:
        source_conn.close()

    return counts
