"""Tests for db module — SQLite database layer."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from unittest.mock import patch

import db


def test_init_db(tmp_path: Path) -> None:
    """init_db creates all tables without error."""
    test_db = tmp_path / "test.db"
    with patch.object(db, "DB_FILE", test_db):
        db.init_db()

    conn = sqlite3.connect(str(test_db))
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    conn.close()
    assert "contacts" in tables
    assert "processed" in tables
    assert "templates" in tables
    assert "settings" in tables


def test_save_and_get_contacts(tmp_path: Path) -> None:
    test_db = tmp_path / "test.db"
    with patch.object(db, "DB_FILE", test_db):
        db.init_db()

        contacts = [
            {"card_id": "c1", "name": "田中太郎", "email": "tanaka@test.jp", "company": "テスト社"},
            {"card_id": "c2", "name": "山田花子", "email": "yamada@test.jp", "company": "サンプル社"},
        ]
        inserted = db.save_contacts(contacts)
        assert inserted == 2

        # Duplicate insert should return 0
        inserted2 = db.save_contacts(contacts)
        assert inserted2 == 0

        all_contacts = db.get_contacts()
        assert len(all_contacts) == 2


def test_processed_tracking(tmp_path: Path) -> None:
    test_db = tmp_path / "test.db"
    with patch.object(db, "DB_FILE", test_db):
        db.init_db()

        assert db.get_processed_count() == 0
        assert not db.is_processed("c1")

        db.mark_processed(["c1", "c2"])
        assert db.get_processed_count() == 2
        assert db.is_processed("c1")
        assert db.is_processed("c2")

        cleared = db.clear_processed()
        assert cleared == 2
        assert db.get_processed_count() == 0


def test_unprocessed_filter(tmp_path: Path) -> None:
    test_db = tmp_path / "test.db"
    with patch.object(db, "DB_FILE", test_db):
        db.init_db()

        contacts = [
            {"card_id": "c1", "name": "田中", "email": "t@test.jp"},
            {"card_id": "c2", "name": "山田", "email": "y@test.jp"},
            {"card_id": "c3", "name": "鈴木", "email": "s@test.jp"},
        ]
        db.save_contacts(contacts)
        db.mark_processed(["c1"])

        unprocessed = db.get_contacts(unprocessed_only=True)
        assert len(unprocessed) == 2
        names = {c["name"] for c in unprocessed}
        assert "田中" not in names
        assert "山田" in names
        assert "鈴木" in names


def test_templates(tmp_path: Path) -> None:
    test_db = tmp_path / "test.db"
    with patch.object(db, "DB_FILE", test_db):
        db.init_db()

        assert db.get_template("test") is None

        db.save_template("test", "Hello {name}")
        assert db.get_template("test") == "Hello {name}"

        # Update
        db.save_template("test", "Updated {name}")
        assert db.get_template("test") == "Updated {name}"

        templates = db.list_templates()
        assert len(templates) == 1
        assert templates[0]["name"] == "test"


def test_settings(tmp_path: Path) -> None:
    test_db = tmp_path / "test.db"
    with patch.object(db, "DB_FILE", test_db):
        db.init_db()

        assert db.get_setting("key1", "default") == "default"

        db.set_setting("key1", "value1")
        assert db.get_setting("key1") == "value1"

        # Update
        db.set_setting("key1", "value2")
        assert db.get_setting("key1") == "value2"


def test_migrate_from_json(tmp_path: Path) -> None:
    import json
    import config

    test_db = tmp_path / "test.db"
    json_path = tmp_path / "processed.json"
    json_path.write_text(json.dumps({"processed_ids": ["id1", "id2", "id3"]}))

    with patch.object(db, "DB_FILE", test_db), patch.object(config, "PROCESSED_FILE", json_path):
        db.init_db()
        db.migrate_from_json()

    with patch.object(db, "DB_FILE", test_db):
        assert db.get_processed_count() == 3
        assert db.is_processed("id1")
