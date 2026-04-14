"""Filesystem paths for user-scoped application data."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import config

USER_DATA_DIR = config.BASE_DIR / "user_data"
LEGACY_SESSIONS_DIR = config.BASE_DIR / "user_sessions"


def normalize_username(username: str) -> str:
    normalized = username.strip()
    if not normalized:
        raise ValueError("username must not be empty")
    return normalized


def user_key(username: str) -> str:
    return quote(normalize_username(username), safe="")


def scoped_key(username: str, name: str) -> str:
    return f"{user_key(username)}::{name}"


def get_user_dir(username: str, *, create: bool = True) -> Path:
    path = USER_DATA_DIR / user_key(username)
    if create:
        path.mkdir(parents=True, exist_ok=True)
    return path


def get_db_path(username: str) -> Path:
    return get_user_dir(username) / "app.db"


def get_token_cache_path(username: str) -> Path:
    return get_user_dir(username) / ".token_cache.json"


def get_legacy_eight_session_path(username: str) -> Path:
    return LEGACY_SESSIONS_DIR / f"{normalize_username(username)}_eight_session.json"


def get_eight_session_path(username: str) -> Path:
    new_path = get_user_dir(username) / "eight_session.json"
    if new_path.exists():
        return new_path

    legacy_path = get_legacy_eight_session_path(username)
    if legacy_path.exists():
        return legacy_path

    return new_path
