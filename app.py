"""Streamlit dashboard — business card automation app (cloud-ready)."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

import db
import internal_auth
import sidebar_user
import user_session
import user_storage

st.set_page_config(
    page_title="名刺自動化ツール",
    page_icon="📇",
    layout="wide",
)

username = sidebar_user.render_user_sidebar()

st.title("📇 名刺自動化ツール")
st.markdown("Eight の名刺データを取得し、Outlook メール下書きを自動作成します。")

st.divider()

if not username:
    if internal_auth.is_auth_enabled():
        st.info("👈 サイドバーからログインしてください。")
    else:
        st.info("👈 サイドバーでユーザー名を入力してください。")
    st.stop()

db.init_db(username=username)

# --- Status cards ---
col1, col2, col3 = st.columns(3)

with col1:
    has_session = user_session.has_eight_session(username)
    if has_session:
        path = user_session.get_eight_session_path(username)
        modified = datetime.fromtimestamp(path.stat().st_mtime)
        st.success("Eight 接続済み")
        st.caption(f"最終更新: {modified.strftime('%Y-%m-%d %H:%M')}")
    else:
        st.error("Eight 未接続")
        st.caption("「Eight ログイン」ページからセッションをアップロード")

with col2:
    token_exists = user_storage.get_token_cache_path(username).exists()
    if token_exists:
        st.success("Outlook 認証済み")
    else:
        st.error("Outlook 未認証")
        st.caption("「設定」ページから認証")

with col3:
    processed_count = db.get_processed_count(username=username)
    st.metric("処理済み連絡先", f"{processed_count} 件")

st.divider()

# --- Quick guide ---
st.subheader("使い方")
st.markdown("""
| ステップ | ページ | やること |
|---------|--------|---------|
| 1 | **Eight ログイン** | ローカルでセッション取得 → アップロード |
| 2 | **スクレイピング** | 名刺データを取得 |
| 3 | **下書き作成** | Outlook にメール下書きを自動作成 |
| 4 | **設定** | テンプレート編集・Outlook 認証 |
""")

st.divider()

# --- Recent contacts ---
recent = db.get_contacts(username=username)
if recent:
    st.subheader(f"保存済み連絡先（{len(recent)} 件）")
    display_data = [
        {
            "名前": c["name"],
            "会社": c["company"],
            "メール": c["email"],
            "追加日": c["added_date"][:10] if c["added_date"] else "",
        }
        for c in recent[:20]
    ]
    st.dataframe(display_data, use_container_width=True, hide_index=True)
else:
    st.info("まだ連絡先データがありません。「スクレイピング」ページからデータを取得してください。")
