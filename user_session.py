"""Multi-user session management for cloud deployment."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote

import streamlit as st

import internal_auth
import user_storage


def get_current_user() -> str | None:
    """Get current username from session state."""
    if internal_auth.is_auth_enabled():
        return internal_auth.get_authenticated_user()
    return st.session_state.get("username")


def set_current_user(username: str) -> None:
    st.session_state["username"] = user_storage.normalize_username(username)


def get_eight_session_path(username: str) -> Path:
    """Get the Eight session file path for a user."""
    return user_storage.get_eight_session_path(username)


def save_eight_session(username: str, session_data: bytes) -> Path:
    """Save uploaded Eight session file for a user."""
    path = user_storage.get_user_dir(username) / "eight_session.json"
    path.write_bytes(session_data)
    return path


def has_eight_session(username: str) -> bool:
    return get_eight_session_path(username).exists()


def delete_eight_session(username: str) -> None:
    user_storage.get_eight_session_path(username).unlink(missing_ok=True)
    user_storage.get_legacy_eight_session_path(username).unlink(missing_ok=True)


def list_users() -> list[str]:
    """List all users who have uploaded sessions."""
    users = set()

    if user_storage.USER_DATA_DIR.exists():
        for user_dir in user_storage.USER_DATA_DIR.iterdir():
            if not user_dir.is_dir():
                continue
            session_path = user_dir / "eight_session.json"
            if session_path.exists():
                users.add(unquote(user_dir.name))

    if user_storage.LEGACY_SESSIONS_DIR.exists():
        for session_file in user_storage.LEGACY_SESSIONS_DIR.glob("*_eight_session.json"):
            users.add(session_file.name.replace("_eight_session.json", ""))

    return sorted(users)


def require_login() -> str:
    """Ensure user is logged in. Returns username or stops the page."""
    if internal_auth.is_auth_enabled():
        username = internal_auth.get_authenticated_user()
        if not username:
            st.error("⚠️ ログインしてください。サイドバーから認証してください。")
            st.stop()
        st.session_state["username"] = username
        return username

    username = get_current_user()
    if not username:
        st.error("⚠️ ユーザー名を入力してください。サイドバーからログインしてください。")
        st.stop()
    return user_storage.normalize_username(username)
