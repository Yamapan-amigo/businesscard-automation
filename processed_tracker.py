"""Track processed contacts to avoid duplicate draft creation."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

import config

_lock = threading.Lock()


def _state_path() -> Path:
    return config.PROCESSED_FILE


def load_processed() -> set[str]:
    path = _state_path()
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return set(data.get("processed_ids", []))


def save_processed(ids: set[str]) -> None:
    path = _state_path()
    data = {
        "processed_ids": sorted(ids),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "count": len(ids),
    }
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def filter_unprocessed(contacts: list[dict]) -> list[dict]:
    processed = load_processed()
    return [c for c in contacts if contact_id(c) not in processed]


def mark_processed(contacts: list[dict]) -> None:
    with _lock:
        ids = load_processed()
        for c in contacts:
            ids.add(contact_id(c))
        save_processed(ids)


def contact_id(contact: dict) -> str:
    """Generate a unique ID for a contact.

    Prefer Eight's internal card_id if available,
    otherwise use a composite key.
    """
    if contact.get("card_id"):
        return str(contact["card_id"])
    name = contact.get("name", "").strip()
    company = contact.get("company", "").strip()
    email = contact.get("email", "").strip()
    return f"{name}_{company}_{email}".lower()
