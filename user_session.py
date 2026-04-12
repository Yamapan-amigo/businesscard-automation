"""Multi-user session management for cloud deployment."""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

import config

SESSIONS_DIR = config.BASE_DIR / "user_sessions"


def _ensure_sessions_dir() -> None:
    SESSIONS_DIR.mkdir(exist_ok=True)


def get_current_user() -> str | None:
    """Get current username from session state."""
    return st.session_state.get("username")


def set_current_user(username: str) -> None:
    st.session_state["username"] = username


def get_eight_session_path(username: str) -> Path:
    """Get the Eight session file path for a user."""
    _ensure_sessions_dir()
    return SESSIONS_DIR / f"{username}_eight_session.json"


def save_eight_session(username: str, session_data: bytes) -> Path:
    """Save uploaded Eight session file for a user."""
    path = get_eight_session_path(username)
    path.write_bytes(session_data)
    return path


def has_eight_session(username: str) -> bool:
    return get_eight_session_path(username).exists()


def delete_eight_session(username: str) -> None:
    path = get_eight_session_path(username)
    path.unlink(missing_ok=True)


def list_users() -> list[str]:
    """List all users who have uploaded sessions."""
    _ensure_sessions_dir()
    users = set()
    for f in SESSIONS_DIR.glob("*_eight_session.json"):
        name = f.name.replace("_eight_session.json", "")
        users.add(name)
    return sorted(users)


def require_login() -> str:
    """Ensure user is logged in. Returns username or stops the page."""
    username = get_current_user()
    if not username:
        st.error("⚠️ ユーザー名を入力してください。サイドバーからログインしてください。")
        st.stop()
    return username
