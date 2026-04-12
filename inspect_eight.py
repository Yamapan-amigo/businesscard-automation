"""One-time inspection script: login to Eight manually, then dump contacts page DOM."""

import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright
from playwright_stealth import Stealth

import config

SESSION_FILE = config.EIGHT_SESSION_FILE


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=100)

        # Restore session if available
        if SESSION_FILE.exists():
            context = await browser.new_context(
                storage_state=str(SESSION_FILE)
            )
            print("セッション復元中...")
        else:
            context = await browser.new_context()

        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        # Navigate to login or home
        await page.goto(
            f"{config.EIGHT_BASE_URL}/login",
            wait_until="domcontentloaded",
            timeout=60_000,
        )
        await page.wait_for_timeout(3000)

        # Check if we need to login
        if "/login" in page.url:
            print("\n" + "=" * 60)
            print("ブラウザでEightにログインしてください（2FA含む）")
            print("ログイン完了後、自動的に続行します")
            print("=" * 60 + "\n")

            for _ in range(150):  # Wait up to 5 min
                if "/login" not in page.url and "/signup" not in page.url:
                    break
                await page.wait_for_timeout(2000)

            # Save session
            await page.context.storage_state(path=str(SESSION_FILE))
            print(f"セッション保存: {SESSION_FILE}")

        print(f"\n現在のURL: {page.url}")

        # Navigate to cards/contacts page
        # Try various possible URLs for the contacts list
        for url_path in ["/cards", "/contacts", "/home", "/feed"]:
            try:
                await page.goto(
                    f"{config.EIGHT_BASE_URL}{url_path}",
                    wait_until="domcontentloaded",
                    timeout=15_000,
                )
                await page.wait_for_timeout(3000)
                print(f"\n=== {url_path} ===")
                print(f"URL: {page.url}")
                print(f"Title: {await page.title()}")

                # Dump page structure
                body = await page.query_selector("body")
                if body:
                    # Get all classes used on the page
                    classes = await page.evaluate("""() => {
                        const els = document.querySelectorAll('[class]');
                        const classSet = new Set();
                        els.forEach(el => {
                            el.classList.forEach(c => classSet.add(c));
                        });
                        return Array.from(classSet).sort();
                    }""")
                    print(f"\nAll CSS classes ({len(classes)}):")
                    for c in classes:
                        if any(kw in c.lower() for kw in [
                            'card', 'contact', 'name', 'company', 'email',
                            'title', 'list', 'item', 'date', 'page', 'feed',
                            'profile', 'person', 'user', 'meishi',
                        ]):
                            print(f"  * {c}")

                    # Get main content area HTML
                    inner = await body.inner_html()
                    # Save full HTML for inspection
                    dump_path = config.DATA_DIR / f"eight_page_{url_path.strip('/')}.html"
                    dump_path.parent.mkdir(parents=True, exist_ok=True)
                    dump_path.write_text(inner, encoding="utf-8")
                    print(f"\nHTML保存: {dump_path}")

            except Exception as e:
                print(f"\n{url_path}: エラー - {e}")

        print("\n\n調査完了。ブラウザを閉じます...")
        await page.wait_for_timeout(3000)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
