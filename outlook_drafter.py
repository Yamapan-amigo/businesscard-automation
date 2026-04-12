"""Create Outlook draft emails via Playwright automation of Outlook Web."""

from __future__ import annotations

import logging

from playwright.async_api import Page, async_playwright
from playwright_stealth import Stealth

import config

logger = logging.getLogger(__name__)

OUTLOOK_URL = "https://outlook.office365.com/mail"
# Persistent browser profile directory — keeps Microsoft login state
PROFILE_DIR = str(config.BASE_DIR / ".outlook_profile")


async def _wait_for_outlook_ready(page: Page, timeout_sec: int = 300) -> bool:
    """Wait until Outlook Web inbox is loaded.

    If login is required, the user logs in manually in the visible browser.
    Microsoft's "Stay signed in?" option keeps the session for next time.
    """
    for _ in range(timeout_sec // 2):
        url = page.url
        title = await page.title()

        # Check if we're on a logged-in Outlook page
        if "outlook.office" in url and ("mail" in url or "owa" in url):
            # Look for the "New mail" button as proof of loaded inbox
            new_mail = await page.query_selector(
                'button[aria-label="New mail"], '
                'button[aria-label="新しいメール"], '
                'button[aria-label="新規メール"]'
            )
            if new_mail:
                return True

        await page.wait_for_timeout(2000)

    return False


async def _create_single_draft(
    page: Page, to_email: str, subject: str, body: str
) -> bool:
    """Create a single draft email in Outlook Web."""
    try:
        # Click "New mail"
        new_mail_btn = page.locator(
            'button[aria-label="New mail"], '
            'button[aria-label="新しいメール"], '
            'button[aria-label="新規メール"]'
        )
        await new_mail_btn.first.click()
        await page.wait_for_timeout(2000)

        # Fill "To" field
        to_field = page.locator(
            '[aria-label="To"], '
            '[aria-label="宛先"]'
        ).locator('input')
        await to_field.first.click()
        await to_field.first.fill(to_email)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(1000)

        # Fill subject
        subject_field = page.locator(
            'input[aria-label="Add a subject"], '
            'input[aria-label="件名を追加"]'
        )
        await subject_field.first.click()
        await subject_field.first.fill(subject)
        await page.wait_for_timeout(500)

        # Fill body — click into the body area and type
        body_area = page.locator(
            'div[aria-label="Message body, press Alt+F10 to exit"], '
            'div[aria-label="メッセージ本文、終了するには Alt+F10 を押してください"], '
            'div[role="textbox"][contenteditable="true"]'
        )
        await body_area.first.click()
        # Type body line by line for contenteditable compatibility
        for line in body.split("\n"):
            await page.keyboard.type(line, delay=3)
            await page.keyboard.press("Enter")
        await page.wait_for_timeout(1000)

        # Close the compose window — Outlook auto-saves as draft
        # Use Escape key or the Discard button
        discard_btn = page.locator(
            'button[aria-label="Discard"], '
            'button[aria-label="破棄"]'
        )
        await discard_btn.first.click(timeout=5000)
        await page.wait_for_timeout(1500)

        # If save confirmation dialog appears, click "Save"
        try:
            save_btn = page.locator(
                'button:has-text("Save"), '
                'button:has-text("保存")'
            ).first
            await save_btn.click(timeout=3000)
        except Exception:
            pass

        await page.wait_for_timeout(1500)
        logger.info("下書き作成: %s 宛 - %s", to_email, subject[:40])
        return True

    except Exception as e:
        logger.error("下書き作成失敗 (%s): %s", to_email, e)
        return False


async def create_drafts_batch(
    drafts: list[dict],
    *,
    headless: bool | None = None,
    login_only: bool = False,
) -> list[dict]:
    """Create multiple draft emails in Outlook Web.

    Uses a persistent browser profile so Microsoft "Stay signed in"
    keeps the session across runs.
    """
    # For Outlook, always use headed mode (needs visible browser for login)
    use_headless = False if login_only else (
        headless if headless is not None else config.HEADLESS
    )

    async with async_playwright() as p:
        # Use persistent context — preserves cookies/localStorage across runs
        context = await p.chromium.launch_persistent_context(
            user_data_dir=PROFILE_DIR,
            headless=use_headless,
            slow_mo=200,
        )

        page = context.pages[0] if context.pages else await context.new_page()
        await Stealth().apply_stealth_async(page)

        # Navigate to Outlook
        await page.goto(OUTLOOK_URL, wait_until="domcontentloaded", timeout=60_000)

        logger.info("Outlookの読み込みを待機中...")
        if "login" in page.url or "signin" in page.url:
            logger.info("ブラウザでOutlookにログインしてください")

        ready = await _wait_for_outlook_ready(page)
        if not ready:
            logger.error("Outlookの読み込みに失敗しました")
            await context.close()
            return []

        logger.info("Outlook準備完了")

        if login_only:
            logger.info("ログインモード完了")
            await context.close()
            return []

        # Create drafts
        successful: list[dict] = []
        for i, draft in enumerate(drafts, 1):
            ok = await _create_single_draft(
                page,
                to_email=draft["to_email"],
                subject=draft["subject"],
                body=draft["body"],
            )
            if ok:
                successful.append(draft)
            logger.info("進捗: %d/%d", i, len(drafts))

        await context.close()
        return successful
