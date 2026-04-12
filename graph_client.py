"""Microsoft Graph API client for creating Outlook draft emails."""

from __future__ import annotations

import json
import logging
import time

import msal
import requests

import config

logger = logging.getLogger(__name__)

GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0"


def _load_token_cache() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    if config.TOKEN_CACHE_FILE.exists():
        cache.deserialize(config.TOKEN_CACHE_FILE.read_text(encoding="utf-8"))
    return cache


def _save_token_cache(cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        config.TOKEN_CACHE_FILE.write_text(
            cache.serialize(), encoding="utf-8"
        )


def acquire_token() -> str:
    """Acquire an access token via MSAL device code flow.

    Returns the access token string.
    Raises RuntimeError if authentication fails.
    """
    cache = _load_token_cache()
    app = msal.PublicClientApplication(
        client_id=config.MS_CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{config.MS_TENANT_ID}",
        token_cache=cache,
    )

    # Try silent token acquisition first
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(
            config.MS_SCOPES, account=accounts[0]
        )
        if result and "access_token" in result:
            _save_token_cache(cache)
            logger.info("トークンをキャッシュから取得しました")
            return result["access_token"]

    # Fall back to device code flow
    flow = app.initiate_device_flow(scopes=config.MS_SCOPES)
    if "user_code" not in flow:
        raise RuntimeError(f"デバイスコードフローの開始に失敗: {flow}")

    print("\n" + "=" * 60)
    print("  Microsoft 認証が必要です")
    print("=" * 60)
    print()
    print(f"  1. ブラウザで開く: {flow['verification_uri']}")
    print(f"  2. コードを入力:  {flow['user_code']}")
    print()
    print("=" * 60)
    print("  認証完了を待機中... (最大5分)")
    print("=" * 60 + "\n")
    import sys
    sys.stdout.flush()

    result = app.acquire_token_by_device_flow(flow)
    _save_token_cache(cache)

    if "access_token" not in result:
        error = result.get("error_description", result.get("error", "不明"))
        raise RuntimeError(f"認証失敗: {error}")

    logger.info("認証成功")
    return result["access_token"]


def create_draft(
    token: str,
    to_email: str,
    subject: str,
    body: str,
    *,
    content_type: str = "Text",
) -> dict:
    """Create a draft email in Outlook.

    Args:
        token: Microsoft Graph access token.
        to_email: Recipient email address.
        subject: Email subject line.
        body: Email body text.
        content_type: "Text" or "HTML".

    Returns:
        The created message dict from Graph API.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "subject": subject,
        "body": {
            "contentType": content_type,
            "content": body,
        },
        "toRecipients": [
            {
                "emailAddress": {
                    "address": to_email,
                }
            }
        ],
        "isDraft": True,
    }

    resp = requests.post(
        f"{GRAPH_ENDPOINT}/me/messages",
        headers=headers,
        json=payload,
        timeout=30,
    )

    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", "5"))
        logger.warning("レート制限。%d秒後にリトライ", retry_after)
        time.sleep(retry_after)
        resp = requests.post(
            f"{GRAPH_ENDPOINT}/me/messages",
            headers=headers,
            json=payload,
            timeout=30,
        )

    resp.raise_for_status()
    logger.info("下書き作成: %s 宛", to_email)
    return resp.json()


def create_drafts_batch(
    token: str,
    drafts: list[dict],
) -> list[dict]:
    """Create multiple draft emails.

    Args:
        token: Microsoft Graph access token.
        drafts: List of dicts with keys: to_email, subject, body.

    Returns:
        List of created message dicts.
    """
    results: list[dict] = []
    for i, draft in enumerate(drafts, 1):
        try:
            result = create_draft(
                token=token,
                to_email=draft["to_email"],
                subject=draft["subject"],
                body=draft["body"],
            )
            results.append(result)
            logger.info("下書き %d/%d 作成完了", i, len(drafts))
        except requests.HTTPError as e:
            logger.error("下書き作成失敗 (%s): %s", draft["to_email"], e)
            continue

        # Throttle between requests
        if i < len(drafts):
            time.sleep(0.5)

    return results
