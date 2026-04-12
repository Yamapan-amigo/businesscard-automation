"""Eight (8card.net) contact scraper via internal API."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path

from playwright.async_api import Page, async_playwright
from playwright_stealth import Stealth

import config

logger = logging.getLogger(__name__)

# Entry status codes observed in Eight's API
ENTRY_STATUS_COMPLETE = 40  # Data entry finished
ENTRY_STATUS_PENDING = 31   # Image uploaded, awaiting data entry


async def login_interactive(page: Page) -> None:
    """Open Eight login page and wait for manual login (including 2FA)."""
    logger.info("ログインページを開きます。手動でログインしてください（2FA含む）")
    await page.goto(
        f"{config.EIGHT_BASE_URL}/login",
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    for _ in range(150):
        url = page.url
        if "/login" not in url and "/signup" not in url:
            break
        await page.wait_for_timeout(2000)
    logger.info("ログイン完了。セッションを保存します")
    await page.context.storage_state(path=str(config.EIGHT_SESSION_FILE))


async def _ensure_session(page: Page) -> bool:
    """Navigate to myhome and verify session is valid."""
    await page.goto(
        f"{config.EIGHT_BASE_URL}/myhome",
        wait_until="domcontentloaded",
        timeout=60_000,
    )
    await page.wait_for_timeout(5000)
    url = page.url
    if "/login" in url or "/signup" in url:
        logger.warning("セッション期限切れ。`--login` で再ログインしてください")
        return False
    logger.info("セッション有効")
    return True


async def _fetch_contacts_page(
    page: Page, page_num: int, per_page: int = 100
) -> list[dict]:
    """Call Eight's internal API to fetch a page of contacts.

    API: POST /search_contacts/search_personal_cards
    Body: {"keyword":"","page":<n>,"sort":5,"per_page":<n>}
    sort=5 appears to be newest-first.
    """
    result = await page.evaluate(
        """async ([pageNum, perPage]) => {
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
            const resp = await fetch('/search_contacts/search_personal_cards', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRF-Token': csrfToken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: JSON.stringify({keyword: '', page: pageNum, sort: 5, per_page: perPage})
            });
            return await resp.json();
        }""",
        [page_num, per_page],
    )
    return result.get("personal_cards", [])


def _parse_card(raw: dict) -> dict | None:
    """Parse a single card from the API response into our contact format."""
    person = raw.get("person", {})
    pc_list = person.get("personal_cards", [])
    if not pc_list:
        return None

    pc = pc_list[0]
    fc = pc.get("friend_card") or pc.get("my_card") or pc

    entry_status = fc.get("entry_status")
    if entry_status != ENTRY_STATUS_COMPLETE:
        return None  # Data not yet entered

    name = fc.get("front_full_name", "").strip()
    email = fc.get("front_email", "").strip()
    company = fc.get("front_company_name", "").strip()
    title = fc.get("front_title", "").strip()
    department = fc.get("front_department", "").strip()
    created_at = fc.get("created_at", "")

    if not name:
        return None

    return {
        "card_id": str(person.get("id", "")),
        "name": name,
        "name_reading": fc.get("front_full_name_reading", "").strip(),
        "email": email,
        "company": company,
        "department": department,
        "title": title,
        "phone": fc.get("front_company_phone_number", "").strip(),
        "mobile": fc.get("front_mobile_phone_number", "").strip(),
        "added_date": created_at,
    }


def _parse_date_from_iso(iso_str: str) -> date | None:
    """Parse ISO datetime string to date."""
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str).date()
    except ValueError:
        return None


async def fetch_contacts(
    page: Page,
    *,
    target_date: date | None = None,
    since_date: date | None = None,
    max_pages: int = 50,
    per_page: int = 100,
) -> list[dict]:
    """Fetch contacts from Eight's API with date filtering.

    Args:
        page: Playwright page with active session on /myhome.
        target_date: Only return contacts added on this exact date.
        since_date: Only return contacts added on or after this date.
        max_pages: Maximum API pages to fetch.
        per_page: Results per API page.
    """
    contacts: list[dict] = []
    stop_early = False

    for pg in range(1, max_pages + 1):
        logger.info("APIページ %d を取得中...", pg)
        raw_cards = await _fetch_contacts_page(page, pg, per_page)

        if not raw_cards:
            logger.info("ページ %d: データなし（最終ページ）", pg)
            break

        for raw in raw_cards:
            contact = _parse_card(raw)
            if contact is None:
                continue

            card_date = _parse_date_from_iso(contact["added_date"])

            # Date filters
            if target_date and card_date:
                if card_date != target_date:
                    # API is sorted newest-first; if card is older than target,
                    # all remaining cards will also be older
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


def save_contacts(contacts: list[dict], filename: str | None = None) -> Path:
    """Save contacts to a JSON file in data/."""
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not filename:
        filename = f"contacts_{date.today().isoformat()}.json"
    path = config.DATA_DIR / filename
    path.write_text(
        json.dumps(contacts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.info("連絡先を保存: %s", path)
    return path


async def run_scraper(
    *,
    login_only: bool = False,
    headless: bool | None = None,
    target_date: date | None = None,
    since_date: date | None = None,
) -> list[dict]:
    """Top-level entry point.

    Args:
        login_only: Only perform login and save session.
        headless: Override config.HEADLESS.
        target_date: Only fetch contacts added on this date.
        since_date: Only fetch contacts added on or after this date.
    """
    use_headless = headless if headless is not None else config.HEADLESS
    if login_only:
        use_headless = False

    async with async_playwright() as p:
        launch_args = {"headless": use_headless, "slow_mo": 100}
        session_path = config.EIGHT_SESSION_FILE

        if session_path.exists() and not login_only:
            browser = await p.chromium.launch(**launch_args)
            context = await browser.new_context(
                storage_state=str(session_path)
            )
        else:
            browser = await p.chromium.launch(**launch_args)
            context = await browser.new_context()

        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        if login_only:
            await login_interactive(page)
            await browser.close()
            return []

        if not await _ensure_session(page):
            await browser.close()
            return []

        contacts = await fetch_contacts(
            page,
            target_date=target_date,
            since_date=since_date,
        )

        await browser.close()
        return contacts
