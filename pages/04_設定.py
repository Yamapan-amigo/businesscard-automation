"""Settings page — Outlook auth, template collection, data management."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime

import streamlit as st

import config
import db
import template_engine
import user_session

st.set_page_config(page_title="設定", page_icon="⚙️")

st.title("⚙️ 設定")

username = user_session.require_login()

st.divider()

# ============================================================
# Outlook 認証
# ============================================================
st.subheader("📧 Outlook 認証")

token_exists = config.TOKEN_CACHE_FILE.exists()
if token_exists:
    stat = config.TOKEN_CACHE_FILE.stat()
    modified = datetime.fromtimestamp(stat.st_mtime)
    st.success(f"✅ 認証済み（最終更新: {modified.strftime('%Y-%m-%d %H:%M')}）")
else:
    st.warning("⚠️ Outlook 未認証")

st.markdown("""
**認証手順（デバイスコードフロー）:**
1. 下の「Outlook 認証」ボタンをクリック
2. 表示されるURLをブラウザで開く
3. 表示されるコードを入力
4. Microsoft アカウントでログイン
""")

if st.button("🔐 Outlook 認証を実行", type="primary", use_container_width=True):
    st.info("⏳ ターミナルに認証コードが表示されます。ターミナルを確認してください。")
    with st.spinner("認証完了を待機中...（最大5分）"):
        try:
            result = subprocess.run(
                [sys.executable, "main.py", "--auth-outlook"],
                capture_output=True,
                text=True,
                cwd=str(config.BASE_DIR),
                timeout=300,
            )
            if result.returncode == 0:
                st.success("✅ Outlook 認証完了！")
                st.rerun()
            else:
                output = result.stdout + "\n" + result.stderr
                st.error(f"認証に問題がありました:\n```\n{output.strip()}\n```")
        except subprocess.TimeoutExpired:
            st.error("⏱️ タイムアウト（5分）しました。もう一度お試しください。")
        except Exception as e:
            st.error(f"エラー: {e}")

if token_exists:
    if st.button("🗑️ Outlook 認証をリセット"):
        config.TOKEN_CACHE_FILE.unlink(missing_ok=True)
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
all_templates = db.list_templates()
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
            key="template_select",
        )

        current_body = db.get_template(selected_name) or ""

        edited_body = st.text_area(
            "テンプレート内容",
            value=current_body,
            height=400,
            key="template_edit_area",
        )

        col_save, col_rename, col_delete = st.columns([2, 2, 1])

        with col_save:
            if st.button("💾 保存", use_container_width=True):
                db.save_template(selected_name, edited_body)
                st.success(f"✅ 「{selected_name}」を保存しました。")

        with col_rename:
            new_name = st.text_input(
                "名前変更",
                value="",
                placeholder="新しい名前を入力",
                label_visibility="collapsed",
                key="rename_input",
            )
            if new_name and new_name != selected_name:
                if st.button("✏️ 名前変更", use_container_width=True):
                    db.save_template(new_name, edited_body)
                    db.delete_template(selected_name)
                    st.success(f"✅ 「{selected_name}」→「{new_name}」に変更しました。")
                    st.rerun()

        with col_delete:
            if st.button("🗑️ 削除", use_container_width=True, type="secondary"):
                db.delete_template(selected_name)
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
        key="new_template_name",
    )

    new_template_body = st.text_area(
        "テンプレート内容",
        value="件名テスト　{company} {name}様\n\n{company}\n{name}様\n\nお世話になっております。\nDelight株式会社　山中です。\n\n（本文をここに入力）\n\n何卒よろしくお願いいたします。\n\n•••••••••••••••••••••••••••••••••••••••••••••••\nDelight株式会社\n営業部　山中　翔太\n〒170-0012 東京都豊島区東池袋1-34-5 いちご東池袋ビル6F\nTEL：080-8068-8323\nURL：https://delight-x.co.jp/\n共通：ses@delight-x.co.jp\n•••••••••••••••••••••••••••••••••••••••••••••••",
        height=400,
        key="new_template_body",
    )

    if st.button("➕ テンプレートを作成", type="primary", use_container_width=True):
        if not new_template_name.strip():
            st.error("テンプレート名を入力してください。")
        elif new_template_name in template_names:
            st.error(f"「{new_template_name}」は既に存在します。別の名前を使ってください。")
        else:
            db.save_template(new_template_name.strip(), new_template_body)
            st.success(f"✅ 「{new_template_name}」を作成しました。")
            st.rerun()

st.divider()

# ============================================================
# 処理済みデータ管理
# ============================================================
st.subheader("📊 データ管理")

col1, col2 = st.columns(2)

with col1:
    processed_count = db.get_processed_count()
    st.metric("処理済み連絡先", f"{processed_count} 件")

with col2:
    contacts = db.get_contacts()
    st.metric("保存済み連絡先", f"{len(contacts)} 件")

if processed_count > 0:
    st.caption("処理済みデータをリセットすると、すべての連絡先が「未処理」に戻ります。")
    if st.button("🗑️ 処理済みをリセット", type="secondary"):
        cleared = db.clear_processed()
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
        db.migrate_from_json()
        st.success("✅ 移行完了！")
        st.rerun()
else:
    st.caption("移行対象のJSONファイルがありません。")
