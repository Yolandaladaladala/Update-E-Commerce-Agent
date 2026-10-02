from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .supabase_client import get_client, remember_session, clear_client_session, supabase_configured


@dataclass
class AuthUser:
    id: str
    email: str = ""


def sign_in(email: str, password: str) -> AuthUser:
    client = get_client()
    if client is None:
        raise RuntimeError("Supabase is not configured.")
    response = client.auth.sign_in_with_password({"email": email.strip(), "password": password})
    if getattr(response, "session", None):
        remember_session(response.session)
    user = getattr(response, "user", None)
    if not user:
        raise RuntimeError("Sign in did not return a user.")
    return AuthUser(id=str(user.id), email=str(getattr(user, "email", "") or ""))


def sign_up(email: str, password: str) -> tuple[Optional[AuthUser], bool]:
    client = get_client()
    if client is None:
        raise RuntimeError("Supabase is not configured.")
    response = client.auth.sign_up({"email": email.strip(), "password": password})
    session = getattr(response, "session", None)
    user = getattr(response, "user", None)
    if session:
        remember_session(session)
    auth_user = None
    if user:
        auth_user = AuthUser(id=str(user.id), email=str(getattr(user, "email", "") or ""))
    return auth_user, bool(session)


def current_user() -> Optional[AuthUser]:
    if not supabase_configured():
        return None
    client = get_client()
    if client is None:
        return None
    try:
        response = client.auth.get_user()
        user = getattr(response, "user", None)
        if not user:
            return None
        return AuthUser(id=str(user.id), email=str(getattr(user, "email", "") or ""))
    except Exception:
        return None


def sign_out() -> None:
    client = get_client()
    if client is not None:
        try:
            client.auth.sign_out()
        except Exception:
            pass
    clear_client_session()
