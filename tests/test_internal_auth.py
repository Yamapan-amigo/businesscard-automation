"""Tests for optional internal auth."""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import config
import internal_auth


def test_auth_mode_detection() -> None:
    with (
        patch.object(config, "APP_SHARED_PASSWORD", ""),
        patch.object(config, "APP_USER_PASSWORDS", {}),
    ):
        assert internal_auth.auth_mode() == "disabled"
        assert not internal_auth.is_auth_enabled()

    with (
        patch.object(config, "APP_SHARED_PASSWORD", "shared"),
        patch.object(config, "APP_USER_PASSWORDS", {}),
    ):
        assert internal_auth.auth_mode() == "shared_password"
        assert internal_auth.is_auth_enabled()

    with (
        patch.object(config, "APP_SHARED_PASSWORD", ""),
        patch.object(config, "APP_USER_PASSWORDS", {"alice": "pw"}),
    ):
        assert internal_auth.auth_mode() == "per_user_password"
        assert internal_auth.is_auth_enabled()


def test_validate_credentials_shared_password() -> None:
    with (
        patch.object(config, "APP_SHARED_PASSWORD", "shared-secret"),
        patch.object(config, "APP_ALLOWED_USERS", ["alice", "bob"]),
        patch.object(config, "APP_USER_PASSWORDS", {}),
    ):
        ok, message = internal_auth.validate_credentials("alice", "shared-secret")
        assert ok
        assert message == ""

        ok, message = internal_auth.validate_credentials("charlie", "shared-secret")
        assert not ok
        assert message == internal_auth.INVALID_CREDENTIALS_MESSAGE

        ok, message = internal_auth.validate_credentials("alice", "wrong")
        assert not ok
        assert message == internal_auth.INVALID_CREDENTIALS_MESSAGE


def test_validate_credentials_per_user_password() -> None:
    with (
        patch.object(config, "APP_SHARED_PASSWORD", ""),
        patch.object(config, "APP_ALLOWED_USERS", []),
        patch.object(config, "APP_USER_PASSWORDS", {"alice": "pw1", "bob": "pw2"}),
    ):
        ok, message = internal_auth.validate_credentials("alice", "pw1")
        assert ok
        assert message == ""

        ok, message = internal_auth.validate_credentials("alice", "bad")
        assert not ok
        assert message == internal_auth.INVALID_CREDENTIALS_MESSAGE

        ok, message = internal_auth.validate_credentials("charlie", "pw3")
        assert not ok
        assert message == internal_auth.INVALID_CREDENTIALS_MESSAGE


def test_login_and_logout_update_session_state() -> None:
    fake_streamlit = SimpleNamespace(session_state={})

    with (
        patch.object(config, "APP_SHARED_PASSWORD", "shared-secret"),
        patch.object(config, "APP_ALLOWED_USERS", []),
        patch.object(config, "APP_USER_PASSWORDS", {}),
        patch.object(internal_auth, "st", fake_streamlit),
    ):
        ok, message = internal_auth.login("alice", "shared-secret")
        assert ok
        assert message == ""
        assert internal_auth.get_authenticated_user() == "alice"

        internal_auth.logout()
        assert internal_auth.get_authenticated_user() is None
