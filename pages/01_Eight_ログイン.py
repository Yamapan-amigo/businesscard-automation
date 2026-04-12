"""Eight login page — upload session file from local login_helper.py."""

from __future__ import annotations

from datetime import datetime

import streamlit as st

import scraper_api
import user_session

st.set_page_config(page_title="Eight ログイン", page_icon="🔑")

st.title("🔑 Eight ログイン")

username = user_session.require_login()

st.divider()

# --- Status ---
has_session = user_session.has_eight_session(username)
if has_session:
    path = user_session.get_eight_session_path(username)
    modified = datetime.fromtimestamp(path.stat().st_mtime)
    st.success(f"✅ セッションあり（最終更新: {modified.strftime('%Y-%m-%d %H:%M')}）")

    # Validate session
    if scraper_api.check_session(path):
        st.success("✅ セッション有効（Eight に接続可能）")
    else:
        st.warning("⚠️ セッションが期限切れの可能性があります。再アップロードしてください。")
else:
    st.warning("⚠️ セッションがありません。下の手順でアップロードしてください。")

st.divider()

# --- Upload session ---
st.subheader("セッションのアップロード")

st.markdown("""
**手順:**
1. 手元の PC で `login_helper.py` を実行:
   ```
   python login_helper.py
   ```
2. ブラウザが開くので Eight にログイン（2FA含む）
3. 生成された `eight_session.json` を下からアップロード
""")

uploaded = st.file_uploader(
    "セッションファイルをアップロード",
    type=["json"],
    key="session_upload",
)

if uploaded is not None:
    try:
        # Validate JSON
        import json
        data = json.loads(uploaded.read())
        uploaded.seek(0)

        if "cookies" not in data:
            st.error("⚠️ 正しいセッションファイルではありません。`login_helper.py` で生成されたファイルを使ってください。")
        else:
            path = user_session.save_eight_session(username, uploaded.read())
            uploaded.seek(0)

            # Validate
            if scraper_api.check_session(path):
                st.success(f"✅ セッションをアップロードしました（ユーザー: {username}）")
                st.rerun()
            else:
                st.error("⚠️ セッションが無効です。Eight に再ログインしてからアップロードしてください。")
                user_session.delete_eight_session(username)
    except json.JSONDecodeError:
        st.error("⚠️ JSON ファイルの解析に失敗しました。")

st.divider()

# --- Session management ---
if has_session:
    st.subheader("セッション管理")
    if st.button("🗑️ セッション削除", type="secondary"):
        user_session.delete_eight_session(username)
        st.success("セッションを削除しました。")
        st.rerun()

st.divider()

# --- Download login_helper.py ---
st.subheader("ログインヘルパーのダウンロード")
st.markdown("`login_helper.py` がない場合は下からダウンロードできます。")

from pathlib import Path
helper_path = Path(__file__).parent.parent / "login_helper.py"
if helper_path.exists():
    st.download_button(
        "📥 login_helper.py をダウンロード",
        data=helper_path.read_text(encoding="utf-8"),
        file_name="login_helper.py",
        mime="text/x-python",
    )
