"""CLI entry point for Eight business card → Outlook draft automation."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
from datetime import date, datetime
from pathlib import Path

import config
import graph_client
import processed_tracker
import scraper
import template_engine
import user_storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Eight名刺 → Outlook下書き自動化",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Eightに手動ログイン（2FA対応）してセッションを保存",
    )
    parser.add_argument(
        "--auth-outlook",
        action="store_true",
        help="Microsoft Graph API認証（デバイスコードフロー）",
    )
    parser.add_argument(
        "--scrape-only",
        action="store_true",
        help="スクレイピングのみ実行（下書き作成しない）",
    )
    parser.add_argument(
        "--drafts-only",
        type=str,
        metavar="FILE",
        help="既存のJSONファイルから下書きのみ作成",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="下書きを作成せず内容を表示のみ",
    )
    parser.add_argument(
        "--date",
        type=str,
        help="対象日（YYYY-MM-DD）。この日に追加された名刺のみ",
    )
    parser.add_argument(
        "--since",
        type=str,
        help="開始日（YYYY-MM-DD）。この日以降に追加された名刺",
    )
    parser.add_argument(
        "--headless",
        type=str,
        choices=["true", "false"],
        help="ヘッドレスモード（デフォルト: .envの設定）",
    )
    parser.add_argument(
        "--template",
        type=str,
        default="initial_outreach.txt",
        help="テンプレートファイル名（デフォルト: initial_outreach.txt）",
    )
    parser.add_argument(
        "--user",
        type=str,
        help="ユーザー名。指定するとユーザー別のデータ/認証を使用",
    )
    return parser.parse_args()


def _parse_date_arg(date_str: str) -> date:
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def run_login_eight() -> None:
    logger.info("Eightログインモード開始")
    asyncio.run(scraper.run_scraper(login_only=True))
    logger.info("セッション保存完了: %s", config.EIGHT_SESSION_FILE)


def run_auth_outlook(*, username: str | None = None) -> None:
    logger.info("Microsoft Graph API 認証開始")
    token_cache_path = (
        user_storage.get_token_cache_path(username) if username else None
    )
    graph_client.acquire_token(token_cache_path=token_cache_path)
    logger.info(
        "認証成功。トークンキャッシュ保存済み: %s",
        token_cache_path or config.TOKEN_CACHE_FILE,
    )


def run_scrape(
    *,
    headless: bool | None,
    target_date: date | None,
    since_date: date | None,
) -> list[dict]:
    contacts = asyncio.run(
        scraper.run_scraper(
            headless=headless,
            target_date=target_date,
            since_date=since_date,
        )
    )
    if contacts:
        path = scraper.save_contacts(contacts)
        logger.info("スクレイピング完了: %d件 → %s", len(contacts), path)
    else:
        logger.warning("連絡先が見つかりませんでした")
    return contacts


def load_contacts_from_file(filepath: str) -> list[dict]:
    path = Path(filepath)
    if not path.exists():
        logger.error("ファイルが見つかりません: %s", path)
        sys.exit(1)
    return json.loads(path.read_text(encoding="utf-8"))


def _deduplicate_contacts(contacts: list[dict]) -> list[dict]:
    """Remove duplicate contacts by email, keeping the one with the most data."""
    seen: dict[str, dict] = {}
    for c in contacts:
        email = c.get("email", "").strip().lower()
        if not email:
            continue
        existing = seen.get(email)
        if existing is None:
            seen[email] = c
        else:
            # Keep the one with more filled fields
            new_score = sum(1 for v in c.values() if v)
            old_score = sum(1 for v in existing.values() if v)
            if new_score > old_score:
                seen[email] = c
    # Also include contacts without email
    no_email = [c for c in contacts if not c.get("email", "").strip()]
    return list(seen.values()) + no_email


def prepare_drafts(
    contacts: list[dict], template_name: str
) -> list[dict]:
    tmpl = template_engine.load_template(template_name)
    drafts: list[dict] = []

    for contact in contacts:
        if not contact.get("email"):
            logger.warning(
                "メールアドレスなし（スキップ）: %s", contact.get("name", "不明")
            )
            continue

        subject, body = template_engine.render_template(tmpl, contact)
        drafts.append(
            {
                "to_email": contact["email"],
                "subject": subject,
                "body": body,
                "contact": contact,
            }
        )

    return drafts


def display_drafts(drafts: list[dict]) -> None:
    for i, d in enumerate(drafts, 1):
        print(f"\n{'='*60}")
        print(f"下書き {i}/{len(drafts)}")
        print(f"{'='*60}")
        print(f"宛先: {d['to_email']}")
        print(f"件名: {d['subject']}")
        print(f"---")
        print(d["body"])
    print(f"\n合計: {len(drafts)}件")


def create_outlook_drafts(drafts: list[dict]) -> list[dict]:
    token = graph_client.acquire_token()
    graph_drafts = [
        {"to_email": d["to_email"], "subject": d["subject"], "body": d["body"]}
        for d in drafts
    ]
    return graph_client.create_drafts_batch(token, graph_drafts)


def main() -> None:
    args = parse_args()

    # Login modes
    if args.login:
        run_login_eight()
        return

    if args.auth_outlook:
        run_auth_outlook(username=args.user)
        return

    # Parse date filters
    target_date = _parse_date_arg(args.date) if args.date else None
    since_date = _parse_date_arg(args.since) if args.since else None
    headless = None
    if args.headless:
        headless = args.headless == "true"

    # Get contacts
    if args.drafts_only:
        contacts = load_contacts_from_file(args.drafts_only)
        logger.info("ファイルから %d件の連絡先を読み込み", len(contacts))
    else:
        contacts = run_scrape(
            headless=headless,
            target_date=target_date,
            since_date=since_date,
        )
        if args.scrape_only:
            return

    if not contacts:
        logger.info("処理対象の連絡先がありません")
        return

    # Filter already-processed
    new_contacts = processed_tracker.filter_unprocessed(contacts)
    logger.info(
        "新規: %d件 / 全体: %d件（処理済み: %d件スキップ）",
        len(new_contacts),
        len(contacts),
        len(contacts) - len(new_contacts),
    )

    if not new_contacts:
        logger.info("すべて処理済みです")
        return

    # Deduplicate by email (keep the one with most data)
    new_contacts = _deduplicate_contacts(new_contacts)

    # Prepare drafts
    drafts = prepare_drafts(new_contacts, args.template)

    if not drafts:
        logger.info("メール送信可能な連絡先がありません（メールアドレスなし）")
        return

    # Dry run
    if args.dry_run:
        display_drafts(drafts)
        return

    # Create Outlook drafts via Graph API
    results = create_outlook_drafts(drafts)
    logger.info("Outlook下書き作成完了: %d件", len(results))

    # Mark as processed — results from Graph API are message objects, not our drafts
    drafted_contacts = [d["contact"] for d in drafts[:len(results)]]
    processed_tracker.mark_processed(drafted_contacts)
    logger.info("処理済みとしてマーク: %d件", len(drafted_contacts))


if __name__ == "__main__":
    main()
