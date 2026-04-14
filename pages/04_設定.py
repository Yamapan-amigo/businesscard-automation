"""Settings page — Outlook auth, template collection, data management."""

from __future__ import annotations

import shutil
import time
from datetime import datetime

import streamlit as st

import config
import db
import graph_client
import sidebar_user
import template_engine
import user_session
import user_storage

st.set_page_config(page_title="設定", page_icon="⚙️")
sidebar_user.render_user_sidebar()

st.title("⚙️ 設定")

username = user_session.require_login()
db.init_db(username=username)
template_select_key = user_storage.scoped_key(username, "template_select")
template_edit_area_key = user_storage.scoped_key(username, "template_edit_area")
rename_input_key = user_storage.scoped_key(username, "rename_input")
new_template_name_key = user_storage.scoped_key(username, "new_template_name")
new_template_body_key = user_storage.scoped_key(username, "new_template_body")

st.divider()

# ============================================================
# Outlook 認証
# ============================================================
st.subheader("📧 Outlook 認証")

token_cache_path = user_storage.get_token_cache_path(username)
token_exists = token_cache_path.exists()
device_flow_key = f"outlook_device_flow::{user_storage.user_key(username)}"
device_flow = st.session_state.get(device_flow_key)

if device_flow and device_flow.get("expires_at", 0) <= time.time():
    st.session_state.pop(device_flow_key, None)
    device_flow = None

if token_exists:
    stat = token_cache_path.stat()
    modified = datetime.fromtimestamp(stat.st_mtime)
    st.success(f"✅ 認証済み（最終更新: {modified.strftime('%Y-%m-%d %H:%M')}）")
    st.session_state.pop(device_flow_key, None)
else:
    st.warning("⚠️ Outlook 未認証")

st.markdown("""
**認証手順（デバイスコードフロー）:**
1. 下の「認証コードを発行」をクリック
2. 表示されるURLをブラウザで開く
3. 表示されるコードを入力
4. Microsoft アカウントでログイン
""")

if not token_exists and st.button(
    "🔐 認証コードを発行",
    type="primary",
    use_container_width=True,
):
    try:
        st.session_state[device_flow_key] = graph_client.start_device_flow(
            token_cache_path=token_cache_path
        )
        st.rerun()
    except Exception as e:
        st.error(f"認証開始に失敗しました: {e}")

if not token_exists and device_flow:
    st.info("以下の URL を開き、コードを入力して Microsoft アカウントでログインしてください。")
    st.markdown(f"認証 URL: {device_flow['verification_uri']}")
    st.code(device_flow["user_code"])

    col_confirm, col_cancel = st.columns(2)

    with col_confirm:
        if st.button("✅ 認証完了を確認", use_container_width=True):
            with st.spinner("認証状態を確認中..."):
                result = graph_client.poll_device_flow(
                    device_flow,
                    token_cache_path=token_cache_path,
                )
                st.session_state[device_flow_key] = device_flow

            if "access_token" in result:
                st.session_state.pop(device_flow_key, None)
                st.success("✅ Outlook 認証完了！")
                st.rerun()

            error = result.get("error", "")
            if error == "authorization_pending":
                st.info("まだ認証待ちです。ブラウザでログイン完了後に、もう一度確認してください。")
            elif error == "slow_down":
                st.info("少し待ってから、もう一度確認してください。")
            else:
                if error in {"expired_token", "authorization_declined", "bad_verification_code"}:
                    st.session_state.pop(device_flow_key, None)
                message = result.get("error_description", error or "不明なエラー")
                st.error(f"認証に失敗しました: {message}")

    with col_cancel:
        if st.button("✖️ 認証をキャンセル", use_container_width=True):
            st.session_state.pop(device_flow_key, None)
            st.rerun()

if token_exists:
    if st.button("🗑️ Outlook 認証をリセット"):
        token_cache_path.unlink(missing_ok=True)
        st.success("トークンを削除しました。再認証が必要です。")
        st.rerun()

st.divider()

# ============================================================
# テンプレート集
# ============================================================
st.subheader("📝 テンプレート集")

st.markdown("""
**使用可能な変数:** `{name}`, `{company}`, `{email}`, `{department}`, `{title}`, `{phone}`, `{mobile}`

**フォーマット:** 1行目 = 件名 → 空行 → 本文
""")

# Load all templates
all_templates = db.list_templates(username=username)
template_names = [t["name"] for t in all_templates]

# --- Template tabs: 一覧 / 新規作成 ---
tab_list, tab_new = st.tabs(["📋 一覧・編集", "➕ 新規作成"])

# --- Tab: 一覧・編集 ---
with tab_list:
    if not template_names:
        st.info("テンプレートがありません。「新規作成」タブから作成してください。")
    else:
        selected_name = st.selectbox(
            "テンプレートを選択",
            template_names,
            key=template_select_key,
        )

        current_body = db.get_template(selected_name, username=username) or ""

        edited_body = st.text_area(
            "テンプレート内容",
            value=current_body,
            height=400,
            key=template_edit_area_key,
        )

        col_save, col_rename, col_delete = st.columns([2, 2, 1])

        with col_save:
            if st.button("💾 保存", use_container_width=True):
                db.save_template(selected_name, edited_body, username=username)
                st.success(f"✅ 「{selected_name}」を保存しました。")

        with col_rename:
            new_name = st.text_input(
                "名前変更",
                value="",
                placeholder="新しい名前を入力",
                label_visibility="collapsed",
                key=rename_input_key,
            )
            if new_name and new_name != selected_name:
                if st.button("✏️ 名前変更", use_container_width=True):
                    db.save_template(new_name, edited_body, username=username)
                    db.delete_template(selected_name, username=username)
                    st.success(f"✅ 「{selected_name}」→「{new_name}」に変更しました。")
                    st.rerun()

        with col_delete:
            if st.button("🗑️ 削除", use_container_width=True, type="secondary"):
                db.delete_template(selected_name, username=username)
                st.success(f"「{selected_name}」を削除しました。")
                st.rerun()

        # Preview with sample data
        with st.expander("📄 プレビュー（サンプルデータ）"):
            sample = {
                "name": "山田太郎",
                "company": "サンプル株式会社",
                "email": "yamada@sample.co.jp",
                "department": "営業部",
                "title": "部長",
                "phone": "03-1234-5678",
                "mobile": "090-1234-5678",
            }
            subj, body = template_engine.render_template(edited_body, sample)
            st.markdown(f"**件名:** {subj}")
            st.divider()
            st.text(body)

# --- Tab: 新規作成 ---
with tab_new:
    new_template_name = st.text_input(
        "テンプレート名",
        placeholder="例: 展示会フォロー、セミナー後フォロー",
        key=new_template_name_key,
    )

    new_template_body = st.text_area(
        "テンプレート内容",
        value="件名テスト　{company} {name}様\n\n{company}\n{name}様\n\nお世話になっております。\nDelight株式会社　山中です。\n\n（本文をここに入力）\n\n何卒よろしくお願いいたします。\n\n•••••••••••••••••••••••••••••••••••••••••••••••\nDelight株式会社\n営業部　山中　翔太\n〒170-0012 東京都豊島区東池袋1-34-5 いちご東池袋ビル6F\nTEL：080-8068-8323\nURL：https://delight-x.co.jp/\n共通：ses@delight-x.co.jp\n•••••••••••••••••••••••••••••••••••••••••••••••",
        height=400,
        key=new_template_body_key,
    )

    if st.button("➕ テンプレートを作成", type="primary", use_container_width=True):
        if not new_template_name.strip():
            st.error("テンプレート名を入力してください。")
        elif new_template_name in template_names:
            st.error(f"「{new_template_name}」は既に存在します。別の名前を使ってください。")
        else:
            db.save_template(
                new_template_name.strip(),
                new_template_body,
                username=username,
            )
            st.success(f"✅ 「{new_template_name}」を作成しました。")
            st.rerun()

st.divider()

# ============================================================
# 処理済みデータ管理
# ============================================================
st.subheader("📊 データ管理")

col1, col2 = st.columns(2)

with col1:
    processed_count = db.get_processed_count(username=username)
    st.metric("処理済み連絡先", f"{processed_count} 件")

with col2:
    contacts = db.get_contacts(username=username)
    st.metric("保存済み連絡先", f"{len(contacts)} 件")

if processed_count > 0:
    st.caption("処理済みデータをリセットすると、すべての連絡先が「未処理」に戻ります。")
    if st.button("🗑️ 処理済みをリセット", type="secondary"):
        cleared = db.clear_processed(username=username)
        st.success(f"{cleared} 件の処理済みデータをリセットしました。")
        st.rerun()

st.divider()

# ============================================================
# JSON → SQLite 移行
# ============================================================
st.subheader("🔄 データ移行")
st.markdown("既存の JSON ファイル（`.processed_contacts.json`）から SQLite にデータを移行します。初回のみ実行してください。")

json_exists = config.PROCESSED_FILE.exists()
if json_exists:
    if st.button("📦 JSON → SQLite 移行を実行"):
        db.migrate_from_json(username=username)
        st.success("✅ 移行完了！")
        st.rerun()
else:
    st.caption("移行対象のJSONファイルがありません。")

st.divider()

# ============================================================
# Legacy shared data import
# ============================================================
st.subheader("📦 旧共有データの引き継ぎ")
st.markdown("旧単一ユーザー構成の共有DB / Outlook認証を、現在のユーザー領域へコピーします。")

shared_db_exists = db.DB_FILE.exists()
shared_token_exists = config.TOKEN_CACHE_FILE.exists()

if shared_db_exists:
    if st.button("🗃️ 共有DBを現在ユーザーへ取り込む"):
        counts = db.import_shared_db(username=username)
        st.success(
            "共有DBを取り込みました。"
            f" contacts={counts['contacts']} /"
            f" processed={counts['processed']} /"
            f" templates={counts['templates']} /"
            f" settings={counts['settings']}"
        )
        st.rerun()

if shared_token_exists and config.TOKEN_CACHE_FILE.resolve() != token_cache_path.resolve():
    if st.button("🔑 共有Outlook認証を現在ユーザーへコピー"):
        token_cache_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(config.TOKEN_CACHE_FILE, token_cache_path)
        st.success("共有Outlook認証を現在ユーザーへコピーしました。")
        st.rerun()

if not shared_db_exists and not shared_token_exists:
    st.caption("引き継ぎ対象の共有データはありません。")
