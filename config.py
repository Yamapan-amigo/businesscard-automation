from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

BASE_DIR = Path(__file__).parent


def _get_secret(key: str, default: str = "") -> str:
    """Read from environment, falling back to Streamlit secrets if available."""
    val = os.getenv(key)
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(key, default)
    except Exception:
        return default


# Eight
EIGHT_EMAIL: str = _get_secret("EIGHT_EMAIL")
EIGHT_PASSWORD: str = _get_secret("EIGHT_PASSWORD")
EIGHT_BASE_URL: str = "https://8card.net"
EIGHT_SESSION_FILE: Path = BASE_DIR / ".eight_session.json"

# Microsoft Graph
MS_CLIENT_ID: str = _get_secret("MS_CLIENT_ID")
MS_TENANT_ID: str = _get_secret("MS_TENANT_ID", "common")
MS_SCOPES: list[str] = ["Mail.ReadWrite"]
TOKEN_CACHE_FILE: Path = BASE_DIR / ".token_cache.json"

# Playwright
HEADLESS: bool = _get_secret("HEADLESS", "true").lower() == "true"

# Data
DATA_DIR: Path = BASE_DIR / "data"
PROCESSED_FILE: Path = BASE_DIR / ".processed_contacts.json"
TEMPLATE_DIR: Path = BASE_DIR / "templates"
