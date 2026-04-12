"""Eight login helper — run locally to generate session file for upload.

Usage:
    pip install playwright playwright-stealth
    playwright install chromium
    python login_helper.py

This opens a browser for manual Eight login (including 2FA).
After login, the session file is saved and can be uploaded to the cloud app.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

OUTPUT_FILE = Path("eight_session.json")
EIGHT_URL = "https://8card.net"


async def main() -> None:
    try:
        from playwright.async_api import async_playwright
        from playwright_stealth import Stealth
    except ImportError:
        print("必要なライブラリをインストールしてください:")
        print("  pip install playwright playwright-stealth")
        print("  playwright install chromium")
        sys.exit(1)

    print()
    print("=" * 50)
    print("  Eight ログインヘルパー")
    print("=" * 50)
    print()
    print("ブラウザが開きます。Eight にログインしてください。")
    print("2段階認証（2FA）も完了してください。")
    print("ホーム画面が表示されたら自動で保存されます。")
    print()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)
        context = await browser.new_context()
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        await page.goto(
            f"{EIGHT_URL}/login",
            wait_until="domcontentloaded",
            timeout=60_000,
        )

        # Wait for login completion (up to 5 minutes)
        for _ in range(150):
            url = page.url
            if "/login" not in url and "/signup" not in url:
                break
            await page.wait_for_timeout(2000)

        # Save session
        await context.storage_state(path=str(OUTPUT_FILE))
        await browser.close()

    print()
    print("=" * 50)
    print(f"  セッション保存完了: {OUTPUT_FILE}")
    print("=" * 50)
    print()
    print("このファイルをアプリの「Eight ログイン」ページから")
    print("アップロードしてください。")
    print()


if __name__ == "__main__":
    asyncio.run(main())
