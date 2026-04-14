"""Draft creation page — preview and create Outlook email drafts."""

from __future__ import annotations

import logging

import streamlit as st

import db
import graph_client
import processed_tracker
import sidebar_user
import template_engine
import user_session
import user_storage

logger = logging.getLogger(__name__)

st.set_page_config(page_title="下書き作成", page_icon="📧")
sidebar_user.render_user_sidebar()

st.title("📧 メール下書き作成")
st.markdown("取得した連絡先に対して Outlook にメール下書きを自動作成します。")

username = user_session.require_login()
db.init_db(username=username)

st.divider()

# --- Pre-check: Outlook auth ---
token_cache_path = user_storage.get_token_cache_path(username)
if not token_cache_path.exists():
    st.error("⚠️ Outlook が未認証です。「設定」ページから先に認証してください。")
    st.stop()

# --- Load unprocessed contacts ---
contacts = db.get_contacts(username=username, unprocessed_only=True)

if not contacts:
    st.warning("未処理の連絡先がありません。先に「スクレイピング」ページでデータを取得してください。")
    st.stop()

# Separate by email availability
contacts_with_email = [c for c in contacts if c.get("email")]
contacts_no_email = [c for c in contacts if not c.get("email")]

st.info(
    f"📋 未処理の連絡先: **{len(contacts)}** 件"
    f"（メールあり: {len(contacts_with_email)} / メールなし: {len(contacts_no_email)}）"
)

if not contacts_with_email:
    st.warning("メールアドレスのある連絡先がありません。")
    st.stop()

st.divider()

# --- Contact selection ---
st.subheader("連絡先を選択")

select_all_key = user_storage.scoped_key(username, "select_all")
contact_key_prefix = user_storage.scoped_key(username, "contact")
template_select_key = user_storage.scoped_key(username, "draft_template_select")


def _contact_key(index: int) -> str:
    return f"{contact_key_prefix}_{index}"


def _toggle_all() -> None:
    """Sync individual checkboxes when 'select all' is toggled."""
    val = st.session_state[select_all_key]
    for idx in range(len(contacts_with_email)):
        st.session_state[_contact_key(idx)] = val


# Initialize session state for all checkboxes on first load
if select_all_key not in st.session_state:
    st.session_state[select_all_key] = True
for idx in range(len(contacts_with_email)):
    st.session_state.setdefault(_contact_key(idx), st.session_state[select_all_key])

st.checkbox("✅ すべて選択", key=select_all_key, on_change=_toggle_all)

selected: list[dict] = []
for i, c in enumerate(contacts_with_email):
    label = f"**{c['name']}** — {c['company']}　`{c['email']}`"
    if st.checkbox(label, key=_contact_key(i)):
        selected.append(c)

if not selected:
    st.info("下書きを作成する連絡先を選択してください。")
    st.stop()

st.divider()

# --- Template preview ---
st.subheader("テンプレート選択")

# Load available templates
all_templates = db.list_templates(username=username)
template_names = [t["name"] for t in all_templates]

if not template_names:
    # Fallback: load from file if no DB templates exist
    try:
        file_tmpl = template_engine.load_template("initial_outreach.txt")
        db.save_template("initial_outreach", file_tmpl, username=username)
        template_names = ["initial_outreach"]
    except FileNotFoundError:
        st.error("テンプレートがありません。「設定」ページで作成してください。")
        st.stop()

selected_template = st.selectbox(
    "使用するテンプレート",
    template_names,
    key=template_select_key,
)

template_str = db.get_template(selected_template, username=username) or ""

sample = selected[0]
subject_preview, body_preview = template_engine.render_template(template_str, sample)

with st.expander(f"📄 プレビュー: {sample['name']} 宛（{selected_template}）", expanded=True):
    st.markdown(f"**件名:** {subject_preview}")
    st.divider()
    st.text(body_preview)

st.divider()

# --- Actions ---
col1, col2 = st.columns(2)

with col1:
    preview_all = st.button("👁️ 全件プレビュー", use_container_width=True)

with col2:
    create_drafts = st.button(
        f"📧 下書き作成（{len(selected)} 件）",
        type="primary",
        use_container_width=True,
    )

# --- Preview all ---
if preview_all:
    st.subheader("全件プレビュー")
    for i, contact in enumerate(selected, 1):
        subject, body = template_engine.render_template(template_str, contact)
        with st.expander(f"{i}. {contact['name']}（{contact['email']}）"):
            st.markdown(f"**件名:** {subject}")
            st.divider()
            st.text(body)

# --- Create drafts ---
if create_drafts:
    drafts = []
    for contact in selected:
        subject, body = template_engine.render_template(template_str, contact)
        drafts.append({
            "to_email": contact["email"],
            "subject": subject,
            "body": body,
            "contact": contact,
        })

    st.subheader("下書き作成中...")
    progress = st.progress(0, text="Outlook に接続中...")
    status_area = st.empty()

    try:
        progress.progress(0, text="Outlook 認証中...")
        token = graph_client.acquire_token(token_cache_path=token_cache_path)

        results: list[dict] = []
        failed: list[str] = []

        for i, draft in enumerate(drafts):
            progress.progress(
                (i + 1) / len(drafts),
                text=f"下書き作成中... {i + 1}/{len(drafts)}（{draft['contact']['name']}）",
            )
            try:
                result = graph_client.create_draft(
                    token=token,
                    to_email=draft["to_email"],
                    subject=draft["subject"],
                    body=draft["body"],
                )
                results.append(result)

                # Mark this contact as processed immediately
                cid = processed_tracker.contact_id(draft["contact"])
                db.mark_processed([cid], username=username)

            except Exception as e:
                logger.error("下書き作成失敗 (%s): %s", draft["to_email"], e)
                failed.append(f"{draft['contact']['name']} ({draft['to_email']})")
                continue

        progress.progress(1.0, text="完了！")

        if results:
            st.success(f"✅ 下書き作成完了: {len(results)} 件")
            st.balloons()
            st.markdown("Outlook の下書きフォルダを確認してください。")

        if failed:
            st.warning(f"⚠️ {len(failed)} 件失敗:\n" + "\n".join(f"- {f}" for f in failed))

    except RuntimeError as e:
        error_msg = str(e)
        if "認証" in error_msg or "デバイスコード" in error_msg:
            st.error(
                "⚠️ Outlook 認証が必要です。\n\n"
                "「設定」ページの手順に従って認証してください。"
            )
        else:
            st.error(f"下書き作成に失敗しました:\n```\n{error_msg}\n```")
    except Exception as e:
        st.error(f"エラーが発生しました:\n```\n{e}\n```")
