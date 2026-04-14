"""Scraping page — fetch contacts from Eight (requests-based, no Playwright)."""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

import db
import scraper_api
import sidebar_user
import user_session
import user_storage

st.set_page_config(page_title="スクレイピング", page_icon="📥")
sidebar_user.render_user_sidebar()

st.title("📥 名刺データ取得")
st.markdown("Eight から名刺データを取得します。")

username = user_session.require_login()
db.init_db(username=username)

st.divider()

# --- Pre-check ---
if not user_session.has_eight_session(username):
    st.error("⚠️ Eight のセッションがありません。「Eight ログイン」ページからアップロードしてください。")
    st.stop()

session_path = user_session.get_eight_session_path(username)
st.success(f"✅ Eight セッションあり（ユーザー: {username}）")

st.divider()

# --- Date filter ---
st.subheader("フィルタ設定")

filter_mode_key = user_storage.scoped_key(username, "filter_mode")
target_date_key = user_storage.scoped_key(username, "target_date")
since_date_key = user_storage.scoped_key(username, "since_date")
show_filter_key = user_storage.scoped_key(username, "show_filter")

filter_mode = st.radio(
    "日付フィルタ",
    ["指定日のみ", "指定日以降", "すべて取得"],
    horizontal=True,
    index=0,
    key=filter_mode_key,
)

target_date: date | None = None
since_date: date | None = None

if filter_mode == "指定日のみ":
    target_date = st.date_input("対象日", value=date.today(), key=target_date_key)
elif filter_mode == "指定日以降":
    since_date = st.date_input(
        "開始日",
        value=date.today() - timedelta(days=7),
        key=since_date_key,
    )
else:
    st.caption("Eight に登録されている全ての名刺を取得します。件数が多い場合は時間がかかります。")

st.divider()

# --- Execute ---
if st.button("📥 名刺データを取得", type="primary", use_container_width=True):
    with st.spinner("Eight からデータを取得中..."):
        try:
            contacts = scraper_api.fetch_contacts(
                session_path,
                target_date=target_date,
                since_date=since_date,
            )

            if not contacts:
                st.warning("連絡先が見つかりませんでした。日付フィルタを確認してください。")
                st.stop()

            # Save to SQLite
            inserted = db.save_contacts(contacts, username=username)

            st.success(f"✅ {len(contacts)} 件の連絡先を取得（新規DB保存: {inserted} 件）")

        except RuntimeError as e:
            error_msg = str(e)
            if "セッション期限切れ" in error_msg:
                st.error("⚠️ Eight のセッションが期限切れです。「Eight ログイン」ページから再アップロードしてください。")
            else:
                st.error(f"エラー: {error_msg}")
            st.stop()
        except Exception as e:
            st.error(f"スクレイピングに失敗しました:\n```\n{e}\n```")
            st.stop()

st.divider()

# --- Saved contacts ---
st.subheader("保存済み連絡先")

show_filter = st.selectbox(
    "表示フィルタ",
    ["すべて", "未処理のみ"],
    key=show_filter_key,
)

contacts_from_db = db.get_contacts(
    username=username,
    unprocessed_only=(show_filter == "未処理のみ"),
)

if contacts_from_db:
    display_data = [
        {
            "名前": c["name"],
            "会社": c["company"],
            "部署": c["department"],
            "役職": c["title"],
            "メール": c["email"],
            "追加日": c["added_date"][:10] if c["added_date"] else "",
        }
        for c in contacts_from_db
    ]
    st.dataframe(display_data, use_container_width=True, hide_index=True)
    st.caption(f"合計: {len(contacts_from_db)} 件")
else:
    st.info("連絡先データがありません。上のボタンでデータを取得してください。")
