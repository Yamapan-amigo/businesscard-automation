"""Optional internal authentication for Streamlit sessions."""

from __future__ import annotations

import hmac

import streamlit as st

import config
import user_storage

AUTH_USER_KEY = "authenticated_user"
INVALID_CREDENTIALS_MESSAGE = "ユーザー名またはパスワードが正しくありません。"


def is_auth_enabled() -> bool:
    return bool(config.APP_SHARED_PASSWORD or config.APP_USER_PASSWORDS)


def auth_mode() -> str:
    if config.APP_USER_PASSWORDS:
        return "per_user_password"
    if config.APP_SHARED_PASSWORD:
        return "shared_password"
    return "disabled"


def get_authenticated_user() -> str | None:
    username = st.session_state.get(AUTH_USER_KEY)
    if not username:
        return None
    return user_storage.normalize_username(username)


def validate_credentials(username: str, password: str) -> tuple[bool, str]:
    try:
        normalized_username = user_storage.normalize_username(username)
    except ValueError:
        return False, "ユーザー名を入力してください。"

    if not password:
        return False, "パスワードを入力してください。"

    if config.APP_USER_PASSWORDS:
        expected_password = config.APP_USER_PASSWORDS.get(normalized_username)
        if not expected_password:
            return False, INVALID_CREDENTIALS_MESSAGE
        if not hmac.compare_digest(password, expected_password):
            return False, INVALID_CREDENTIALS_MESSAGE
        return True, ""

    if config.APP_ALLOWED_USERS and normalized_username not in config.APP_ALLOWED_USERS:
        return False, INVALID_CREDENTIALS_MESSAGE

    if config.APP_SHARED_PASSWORD:
        if not hmac.compare_digest(password, config.APP_SHARED_PASSWORD):
            return False, INVALID_CREDENTIALS_MESSAGE
        return True, ""

    return True, ""


def login(username: str, password: str) -> tuple[bool, str]:
    ok, message = validate_credentials(username, password)
    if ok:
        st.session_state[AUTH_USER_KEY] = user_storage.normalize_username(username)
    return ok, message


def logout() -> None:
    st.session_state.pop(AUTH_USER_KEY, None)
    st.session_state.pop("username", None)
