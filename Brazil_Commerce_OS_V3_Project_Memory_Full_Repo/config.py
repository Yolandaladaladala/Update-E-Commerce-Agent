from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

try:
    import streamlit as st
except Exception:
    st = None

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def get_setting(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value not in (None, ""):
        return str(value).strip()
    if st is not None:
        try:
            value = st.secrets[name]
            if value not in (None, ""):
                return str(value).strip()
        except Exception:
            pass
    return default


def get_bool_setting(name: str, default: bool = False) -> bool:
    raw = get_setting(name, "true" if default else "false").lower()
    return raw in {"1", "true", "yes", "on"}


LLM_API_URL = get_setting("LLM_API_URL", "https://api.openai.com/v1/chat/completions")
LLM_API_KEY = get_setting("LLM_API_KEY")
LLM_MODEL = get_setting("LLM_MODEL")
SERPER_API_KEY = get_setting("SERPER_API_KEY")

SUPABASE_URL = get_setting("SUPABASE_URL")
SUPABASE_ANON_KEY = get_setting("SUPABASE_ANON_KEY")
SUPABASE_BUCKET = get_setting("SUPABASE_BUCKET", "bcos-project-files")
AUTH_REQUIRED = get_bool_setting("AUTH_REQUIRED", True)

DEMO_MODE = not (LLM_API_KEY and LLM_MODEL)
PERSISTENCE_CONFIGURED = bool(SUPABASE_URL and SUPABASE_ANON_KEY)
