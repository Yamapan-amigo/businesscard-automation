from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

BASE_DIR = Path(__file__).parent

# Eight
EIGHT_EMAIL: str = os.getenv("EIGHT_EMAIL", "")
EIGHT_PASSWORD: str = os.getenv("EIGHT_PASSWORD", "")
EIGHT_BASE_URL: str = "https://8card.net"
EIGHT_SESSION_FILE: Path = BASE_DIR / ".eight_session.json"

# Microsoft Graph
MS_CLIENT_ID: str = os.getenv("MS_CLIENT_ID", "")
MS_TENANT_ID: str = os.getenv("MS_TENANT_ID", "common")
MS_SCOPES: list[str] = ["Mail.ReadWrite"]
TOKEN_CACHE_FILE: Path = BASE_DIR / ".token_cache.json"

# Playwright
HEADLESS: bool = os.getenv("HEADLESS", "true").lower() == "true"

# Data
DATA_DIR: Path = BASE_DIR / "data"
PROCESSED_FILE: Path = BASE_DIR / ".processed_contacts.json"
TEMPLATE_DIR: Path = BASE_DIR / "templates"
