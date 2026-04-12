"""Eight (8card.net) contact scraper via requests — no Playwright needed.

Uses session cookies from a Playwright storage_state JSON file
to call Eight's internal API directly with the requests library.
Designed for cloud deployment where Playwright is unavailable.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from pathlib import Path

import requests

import config

logger = logging.getLogger(__name__)

ENTRY_STATUS_COMPLETE = 40


def _load_cookies_from_session(session_path: Path) -> dict[str, str]:
    """Extract cookies from Playwright storage_state JSON."""
    if not session_path.exists():
        raise FileNotFoundError(f"セッションファイルが見つかりません: {session_path}")

    data = json.loads(session_path.read_text(encoding="utf-8"))
    cookies: dict[str, str] = {}
    for cookie in data.get("cookies", []):
        cookies[cookie["name"]] = cookie["value"]
    return cookies


def _get_csrf_token(session: requests.Session) -> str:
    """Fetch CSRF token from Eight's myhome page."""
    resp = session.get(
        f"{config.EIGHT_BASE_URL}/myhome",
        timeout=30,
    )
    resp.raise_for_status()

    # Check if redirected to login
    if "/login" in resp.url or "/signup" in resp.url:
        raise RuntimeError(
            "セッション期限切れです。ローカルで再ログインしてセッションをアップロードしてください。"
        )

    match = re.search(r'<meta\s+name="csrf-token"\s+content="([^"]+)"', resp.text)
    if not match:
        raise RuntimeError("CSRFトークンが取得できませんでした。セッションが無効な可能性があります。")

    return match.group(1)


def _fetch_contacts_page(
    session: requests.Session,
    csrf_token: str,
    page_num: int,
    per_page: int = 100,
) -> list[dict]:
    """Call Eight's internal API to fetch a page of contacts."""
    resp = session.post(
        f"{config.EIGHT_BASE_URL}/search_contacts/search_personal_cards",
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf_token,
            "X-Requested-With": "XMLHttpRequest",
        },
        json={
            "keyword": "",
            "page": page_num,
            "sort": 5,
            "per_page": per_page,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json().get("personal_cards", [])


def _parse_card(raw: dict) -> dict | None:
    """Parse a single card from the API response."""
    person = raw.get("person", {})
    pc_list = person.get("personal_cards", [])
    if not pc_list:
        return None

    pc = pc_list[0]
    fc = pc.get("friend_card") or pc.get("my_card") or pc

    if fc.get("entry_status") != ENTRY_STATUS_COMPLETE:
        return None

    name = fc.get("front_full_name", "").strip()
    if not name:
        return None

    return {
        "card_id": str(person.get("id", "")),
        "name": name,
        "name_reading": fc.get("front_full_name_reading", "").strip(),
        "email": fc.get("front_email", "").strip(),
        "company": fc.get("front_company_name", "").strip(),
        "department": fc.get("front_department", "").strip(),
        "title": fc.get("front_title", "").strip(),
        "phone": fc.get("front_company_phone_number", "").strip(),
        "mobile": fc.get("front_mobile_phone_number", "").strip(),
        "added_date": fc.get("created_at", ""),
    }


def _parse_date_from_iso(iso_str: str) -> date | None:
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str).date()
    except ValueError:
        return None


def fetch_contacts(
    session_path: Path,
    *,
    target_date: date | None = None,
    since_date: date | None = None,
    max_pages: int = 50,
    per_page: int = 100,
) -> list[dict]:
    """Fetch contacts from Eight's API using session cookies.

    Args:
        session_path: Path to Playwright storage_state JSON.
        target_date: Only return contacts added on this exact date.
        since_date: Only return contacts added on or after this date.
        max_pages: Maximum API pages to fetch.
        per_page: Results per API page.
    """
    cookies = _load_cookies_from_session(session_path)

    session = requests.Session()
    session.cookies.update(cookies)
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    })

    logger.info("CSRFトークン取得中...")
    csrf_token = _get_csrf_token(session)
    logger.info("セッション有効。データ取得開始")

    contacts: list[dict] = []
    stop_early = False

    for pg in range(1, max_pages + 1):
        logger.info("APIページ %d を取得中...", pg)
        raw_cards = _fetch_contacts_page(session, csrf_token, pg, per_page)

        if not raw_cards:
            logger.info("ページ %d: データなし（最終ページ）", pg)
            break

        for raw in raw_cards:
            contact = _parse_card(raw)
            if contact is None:
                continue

            card_date = _parse_date_from_iso(contact["added_date"])

            if target_date and card_date:
                if card_date != target_date:
                    if card_date < target_date:
                        stop_early = True
                        break
                    continue

            if since_date and card_date:
                if card_date < since_date:
                    stop_early = True
                    break

            contacts.append(contact)

        if stop_early:
            logger.info("日付フィルタにより早期終了（ページ %d）", pg)
            break

    logger.info("合計 %d 件の連絡先を取得", len(contacts))
    return contacts


def check_session(session_path: Path) -> bool:
    """Check if the session file is valid without fetching contacts."""
    try:
        cookies = _load_cookies_from_session(session_path)
        session = requests.Session()
        session.cookies.update(cookies)
        session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })
        _get_csrf_token(session)
        return True
    except Exception:
        return False
