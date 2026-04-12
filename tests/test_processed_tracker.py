"""Tests for processed_tracker module."""

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import processed_tracker


def test_contact_id_with_card_id():
    contact = {"card_id": "abc123", "name": "田中", "company": "テスト"}
    assert processed_tracker.contact_id(contact) == "abc123"


def test_contact_id_composite():
    contact = {"card_id": "", "name": "田中太郎", "company": "テスト社", "email": "tanaka@test.jp"}
    assert processed_tracker.contact_id(contact) == "田中太郎_テスト社_tanaka@test.jp"


def test_load_processed_empty(tmp_path):
    fake_path = tmp_path / "processed.json"
    with patch.object(processed_tracker, "_state_path", return_value=fake_path):
        result = processed_tracker.load_processed()
    assert result == set()


def test_save_and_load(tmp_path):
    fake_path = tmp_path / "processed.json"
    with patch.object(processed_tracker, "_state_path", return_value=fake_path):
        processed_tracker.save_processed({"id1", "id2"})
        result = processed_tracker.load_processed()
    assert result == {"id1", "id2"}


def test_filter_unprocessed(tmp_path):
    fake_path = tmp_path / "processed.json"
    fake_path.write_text(json.dumps({"processed_ids": ["abc123"]}))

    contacts = [
        {"card_id": "abc123", "name": "既存"},
        {"card_id": "def456", "name": "新規"},
    ]
    with patch.object(processed_tracker, "_state_path", return_value=fake_path):
        result = processed_tracker.filter_unprocessed(contacts)
    assert len(result) == 1
    assert result[0]["name"] == "新規"


def test_mark_processed(tmp_path):
    fake_path = tmp_path / "processed.json"
    with patch.object(processed_tracker, "_state_path", return_value=fake_path):
        processed_tracker.mark_processed([{"card_id": "new1", "name": "テスト"}])
        result = processed_tracker.load_processed()
    assert "new1" in result
