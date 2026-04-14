"""Shared sidebar user/auth controls for all Streamlit pages."""

from __future__ import annotations

import streamlit as st

import internal_auth
import user_session


def render_user_sidebar() -> str:
    with st.sidebar:
        st.subheader("👤 ユーザー")

        if internal_auth.is_auth_enabled():
            current_user = internal_auth.get_authenticated_user()
            if current_user:
                username = current_user
                user_session.set_current_user(username)
                st.success(f"ログイン中: **{username}**")
                if internal_auth.auth_mode() == "per_user_password":
                    st.caption("認証方式: ユーザー別パスワード")
                else:
                    st.caption("認証方式: 共通パスワード")
                if st.button("ログアウト", use_container_width=True):
                    internal_auth.logout()
                    st.rerun()
                return username

            login_username = st.text_input(
                "ユーザー名",
                placeholder="例: yamanaka",
                key="sidebar_login_username",
            )
            login_password = st.text_input(
                "パスワード",
                type="password",
                key="sidebar_login_password",
            )
            if st.button("ログイン", type="primary", use_container_width=True):
                ok, message = internal_auth.login(login_username, login_password)
                if ok:
                    st.rerun()
                st.error(message)
            st.caption("社内利用のため認証が必要です。")
            return ""

        username_input = st.text_input(
            "ユーザー名",
            value=user_session.get_current_user() or "",
            placeholder="例: yamanaka",
            key="sidebar_username",
        )
        username = username_input.strip()
        if username:
            user_session.set_current_user(username)
            st.success(f"ログイン中: **{username}**")
        else:
            st.warning("ユーザー名を入力してください")
        return username
