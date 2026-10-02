from __future__ import annotations

import json
import math
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, Any, List
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from config import SERPER_API_KEY
from llm import chat

BASE_DIR = Path(__file__).resolve().parents[1]
SKILL_PATH = BASE_DIR / "skills" / "MARKET_SKILL.md"

SOURCE_PRIORITY = {
    "Government / regulator": 0,
    "Industry association / official statistics": 1,
    "Company / platform disclosure": 2,
    "Professional research institution": 3,
    "Reliable industry / business media": 4,
    "Marketplace / search evidence": 5,
    "Other web evidence": 6,
}

COUNTRY_SEARCH_CONFIG = {
    "brazil": {"gl": "br", "hl": "pt-br", "local_language": "Portuguese (Brazil)"},
    "brasil": {"gl": "br", "hl": "pt-br", "local_language": "Portuguese (Brazil)"},
    "mexico": {"gl": "mx", "hl": "es", "local_language": "Spanish"},
    "méxico": {"gl": "mx", "hl": "es", "local_language": "Spanish"},
    "chile": {"gl": "cl", "hl": "es", "local_language": "Spanish"},
    "singapore": {"gl": "sg", "hl": "en", "local_language": "English; Chinese where useful"},
    "新加坡": {"gl": "sg", "hl": "en", "local_language": "English; Chinese where useful"},
    "巴西": {"gl": "br", "hl": "pt-br", "local_language": "Portuguese (Brazil)"},
    "china": {"gl": "cn", "hl": "zh-cn", "local_language": "Chinese"},
    "中国": {"gl": "cn", "hl": "zh-cn", "local_language": "Chinese"},
    "united kingdom": {"gl": "gb", "hl": "en", "local_language": "English"},
    "uk": {"gl": "gb", "hl": "en", "local_language": "English"},
    "united states": {"gl": "us", "hl": "en", "local_language": "English"},
    "usa": {"gl": "us", "hl": "en", "local_language": "English"},
    "germany": {"gl": "de", "hl": "de", "local_language": "German"},
    "france": {"gl": "fr", "hl": "fr", "local_language": "French"},
    "japan": {"gl": "jp", "hl": "ja", "local_language": "Japanese"},
    "india": {"gl": "in", "hl": "en", "local_language": "English; local languages where useful"},
}


def _skill_text() -> str:
    try:
        return SKILL_PATH.read_text(encoding="utf-8")
    except Exception:
        return ""


def _search_config(country: str) -> dict:
    key = country.strip().lower()
    return COUNTRY_SEARCH_CONFIG.get(key, {"gl": "", "hl": "en", "local_language": "local market language where useful"})


def _clean_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _classify_source(url: str, title: str = "") -> str:
    domain = _clean_domain(url)
    text = f"{domain} {title}".lower()

    if re.search(r"(?:^|\.)(?:gov|gob|go)\.[a-z]{2,3}$", domain) or domain.endswith(".gov"):
        return "Government / regulator"
    if any(x in text for x in ["associação", "association", "instituto", "federation", "federação", "abinpet", "ipb.org"]):
        return "Industry association / official statistics"
    if any(x in domain for x in ["amazon.", "mercadolivre.", "mercadolibre.", "shopee.", "magazineluiza", "americanas"]):
        return "Marketplace / search evidence"
    if any(x in domain for x in ["tiktok.com", "petz.com", "cobasi.com"]):
        return "Company / platform disclosure"
    if any(x in text for x in ["euromonitor", "statista", "grand view research", "mordor intelligence", "research and markets", "market research"]):
        return "Professional research institution"
    if any(x in domain for x in ["reuters.com", "bloomberg.com", "ft.com", "forbes.com", "valor.globo.com", "exame.com"]):
        return "Reliable industry / business media"
    if any(x in domain for x in ["mercadolivre", "amazon", "shopee", "magazineluiza", "americanas"]):
        return "Marketplace / search evidence"
    return "Other web evidence"


def _serper_search(query: str, num: int = 8, gl: str = "", hl: str = "en") -> List[dict]:
    if not SERPER_API_KEY:
        return []

    payload = {"q": query, "num": num}

