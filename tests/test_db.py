"""Tests for db module — SQLite database layer."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import sqlite3
from unittest.mock import patch

import db
import user_storage


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


def test_user_scoped_data_is_isolated(tmp_path: Path) -> None:
    user_data_dir = tmp_path / "user_data"

    alice_contacts = [
        {"card_id": "shared-card", "name": "Alice", "email": "alice@test.jp"},
    ]
    bob_contacts = [
        {"card_id": "shared-card", "name": "Bob", "email": "bob@test.jp"},
    ]

    with patch.object(user_storage, "USER_DATA_DIR", user_data_dir):
        db.init_db(username="alice")
        db.init_db(username="bob")

        assert db.save_contacts(alice_contacts, username="alice") == 1
        assert db.save_contacts(bob_contacts, username="bob") == 1

        db.mark_processed(["shared-card"], username="alice")
        db.save_template("welcome", "Hello Alice", username="alice")
        db.save_template("welcome", "Hello Bob", username="bob")
        db.set_setting("signature", "alice-signature", username="alice")
        db.set_setting("signature", "bob-signature", username="bob")

        assert db.get_contacts(username="alice")[0]["name"] == "Alice"
        assert db.get_contacts(username="bob")[0]["name"] == "Bob"
        assert db.get_processed_count(username="alice") == 1
        assert db.get_processed_count(username="bob") == 0
        assert db.get_template("welcome", username="alice") == "Hello Alice"
        assert db.get_template("welcome", username="bob") == "Hello Bob"
        assert db.get_setting("signature", username="alice") == "alice-signature"
        assert db.get_setting("signature", username="bob") == "bob-signature"


def test_import_shared_db_into_user_scope(tmp_path: Path) -> None:
    shared_db = tmp_path / "shared.db"
    user_data_dir = tmp_path / "user_data"

    with (
        patch.object(db, "DB_FILE", shared_db),
        patch.object(user_storage, "USER_DATA_DIR", user_data_dir),
    ):
        db.init_db()
        db.save_contacts(
            [{"card_id": "c1", "name": "共有ユーザー", "email": "shared@test.jp"}]
        )
        db.mark_processed(["c1"])
        db.save_template("shared-template", "Hello shared")
        db.set_setting("signature", "shared-signature")

        counts = db.import_shared_db(username="alice")

        assert counts["contacts"] == 1
        assert counts["processed"] == 1
        assert counts["templates"] == 1
        assert counts["settings"] == 1
        assert db.get_contacts(username="alice")[0]["name"] == "共有ユーザー"
        assert db.is_processed("c1", username="alice")
        assert db.get_template("shared-template", username="alice") == "Hello shared"
        assert db.get_setting("signature", username="alice") == "shared-signature"
