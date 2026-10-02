from __future__ import annotations

from typing import Any
import streamlit as st

from config import SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_BUCKET

try:
    from supabase import create_client
except Exception:  # app can still run in session-only mode
    create_client = None


SESSION_CLIENT_KEY = "_bcos_supabase_client"
SESSION_TOKENS_KEY = "_bcos_auth_tokens"


def supabase_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_ANON_KEY and create_client is not None)


def get_client():
    """Return a Supabase client scoped to the current Streamlit session.

    Do not cache this globally: the client carries the authenticated user's JWT.
    """
    if not supabase_configured():
        return None

    if SESSION_CLIENT_KEY not in st.session_state:
        st.session_state[SESSION_CLIENT_KEY] = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

    client = st.session_state[SESSION_CLIENT_KEY]
    tokens = st.session_state.get(SESSION_TOKENS_KEY)
    if tokens and not st.session_state.get("_bcos_auth_restored"):
        try:
            response = client.auth.set_session(tokens["access_token"], tokens["refresh_token"])
            session = getattr(response, "session", None)
            if session:
                remember_session(session)
            st.session_state["_bcos_auth_restored"] = True
        except Exception:
            st.session_state.pop(SESSION_TOKENS_KEY, None)
            st.session_state.pop("_bcos_auth_restored", None)
    return client


def remember_session(session: Any) -> None:
    if not session:
        return
    access = getattr(session, "access_token", None)
    refresh = getattr(session, "refresh_token", None)
    if access and refresh:
        st.session_state[SESSION_TOKENS_KEY] = {
            "access_token": access,
            "refresh_token": refresh,
        }
        st.session_state["_bcos_auth_restored"] = True


def clear_client_session() -> None:
    st.session_state.pop(SESSION_TOKENS_KEY, None)
    st.session_state.pop("_bcos_auth_restored", None)
    st.session_state.pop(SESSION_CLIENT_KEY, None)


def storage_bucket() -> str:
    return SUPABASE_BUCKET or "bcos-project-files"
