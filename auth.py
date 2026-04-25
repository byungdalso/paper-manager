"""
auth.py
=======
Two-tier password gate for the Paper Manager.

Usage in your main app file:

    from auth import gate
    role = gate()                 # blocks rendering until login succeeds
    is_admin = (role == "admin")  # gate edit widgets with this flag
"""

import streamlit as st


def gate():
    """Show a login screen.  Returns 'admin' or 'view' once authenticated."""
    if st.session_state.get("role"):
        return st.session_state.role

    st.title("📚 Paper Manager")
    st.caption("연구실 학생용 / 비밀번호로 입장하세요")

    pw = st.text_input("비밀번호", type="password",
                       label_visibility="collapsed",
                       placeholder="비밀번호")
    col1, col2 = st.columns([1, 5])
    with col1:
        clicked = st.button("입장", type="primary", use_container_width=True)

    if clicked:
        if pw == st.secrets.get("admin_password"):
            st.session_state.role = "admin"
            st.rerun()
        elif pw == st.secrets.get("view_password"):
            st.session_state.role = "view"
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다.")

    st.stop()      # halt rendering of the rest of the app


def logout_button():
    """Sidebar logout button.  Call inside `with st.sidebar:` block."""
    role = st.session_state.get("role", "")
    badge = "관리자" if role == "admin" else "보기 전용"
    st.markdown(f"**모드:** {badge}")
    if st.button("로그아웃", use_container_width=True):
        st.session_state.pop("role", None)
        st.rerun()
