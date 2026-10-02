from __future__ import annotations

import json
import re
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

    if any(x in domain for x in ["gov.br", ".gov.", "government", "anvisa.gov", "ibge.gov"]):
        return "Government / regulator"
    if any(x in text for x in ["associação", "association", "instituto", "federation", "federação", "abinpet", "ipb.org"]):
        return "Industry association / official statistics"
    if any(x in domain for x in ["tiktok.com", "amazon.", "mercadolivre.", "mercadolibre.", "shopee.", "petz.com", "cobasi.com"]):
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
    if gl:
        payload["gl"] = gl
    if hl:
        payload["hl"] = hl

    r = requests.post(
        "https://google.serper.dev/search",
        headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
        json=payload,
        timeout=45,
    )
    r.raise_for_status()
    data = r.json()
    results = []
    for x in data.get("organic", []):
        link = x.get("link") or ""
        title = x.get("title") or ""
        results.append(
            {
                "title": title,
                "link": link,
                "snippet": x.get("snippet") or "",
                "date": x.get("date") or "",
                "domain": _clean_domain(link),
                "source_type": _classify_source(link, title),
                "position": x.get("position"),
                "query": query,
            }
        )
    return results


def _extract_json_block(text: str) -> dict | list | None:
    if not text:
        return None
    candidates = []
    fence = re.findall(r"```(?:json)?\s*(.*?)```", text, flags=re.S | re.I)
    candidates.extend(fence)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        candidates.append(text[start : end + 1])
    for c in candidates:
        try:
            return json.loads(c)
        except Exception:
            continue
    return None


def _fallback_queries(country: str, product: str, platform: str, dimensions: List[str]) -> List[dict]:
    q: List[dict] = []
    base = [
        ("Market size & growth", f'{country} {product} market size growth industry'),
        ("Market size & growth", f'{country} {product} category growth demand'),
        ("Consumer need", f'{country} {product} consumer demand trends'),
        ("Competition", f'{country} {product} competitors brands sellers'),
        ("Pricing", f'{country} {product} price marketplace'),
        ("Channels", f'{country} {product} ecommerce channels marketplace'),
        ("Regulation", f'{country} {product} import regulation compliance'),
        ("Regulation", f'site:gov.br {product} importação regulamentação Brasil'),
        ("Competition", f'site:mercadolivre.com.br {product}'),
        ("Pricing", f'site:amazon.com.br {product} preço'),
        ("Consumer need", f'Brasil {product} consumidores tendências'),
        ("Market size & growth", f'mercado {product} Brasil crescimento'),
    ]
    for dim, query in base:
        if dim in dimensions or dim in {"Market size & growth", "Competition", "Pricing", "Regulation"}:
            q.append({"dimension": dim, "query": query, "language": "mixed"})
    if platform:
        q.append({"dimension": "Channels", "query": f'{country} {platform} {product}', "language": "mixed"})
    return q[:16]


def _plan_queries(country: str, product: str, objective: str, platform: str, dimensions: List[str]) -> List[dict]:
    cfg = _search_config(country)
    prompt = f"""
You are a search-query planner for a consulting-grade market research agent.

TARGET MARKET: {country}
PRODUCT/CATEGORY: {product}
USER OBJECTIVE: {objective}
PRIORITY PLATFORM: {platform or 'not specified'}
DIMENSIONS: {', '.join(dimensions)}
LOCAL SEARCH LANGUAGE: {cfg['local_language']}

Create 14-18 search queries. Requirements:
- Mix English and the local market language.
- Cover market context, category demand, consumers, competitors, pricing, channels, platform/e-commerce, regulation/import/logistics, and social commerce where relevant.
- Include several authoritative-domain searches such as government, regulator, industry association or official statistics.
- Include marketplace / competitor queries for observed pricing and positioning.
- Do not assume facts. This is only a retrieval plan.

Return ONLY JSON in this format:
{{
  "queries": [
    {{"dimension": "Competition", "query": "...", "language": "pt-BR"}}
  ]
}}
"""
    try:
        raw = chat(prompt, max_tokens=1200, temperature=0.1)
        obj = _extract_json_block(raw)
        items = obj.get("queries", []) if isinstance(obj, dict) else []
        cleaned = []
        seen = set()
        for item in items:
            query = str(item.get("query", "")).strip()
            if not query or query.lower() in seen:
                continue
            seen.add(query.lower())
            cleaned.append(
                {
                    "dimension": str(item.get("dimension", "General")).strip() or "General",
                    "query": query,
                    "language": str(item.get("language", "")).strip(),
                }
            )
        if len(cleaned) >= 8:
            return cleaned[:18]
    except Exception:
        pass
    return _fallback_queries(country, product, platform, dimensions)


def _dedupe_evidence(items: List[dict]) -> List[dict]:
    out = []
    seen = set()
    for item in items:
        link = (item.get("link") or "").strip()
        title = (item.get("title") or "").strip().lower()
        key = link.lower() if link else title
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _rank_evidence(items: List[dict]) -> List[dict]:
    def score(x: dict):
        priority = SOURCE_PRIORITY.get(x.get("source_type", "Other web evidence"), 9)
        position = x.get("position") if isinstance(x.get("position"), int) else 99
        date_penalty = 0 if x.get("date") else 1
        return (priority, date_penalty, position)

    return sorted(items, key=score)


def _fetch_page_text(url: str, max_chars: int = 7000) -> str:
    if not url or not url.startswith("http"):
        return ""
    try:
        r = requests.get(
            url,
            timeout=12,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; BrazilCommerceOS/0.2; research prototype)"
            },
        )
        if r.status_code >= 400 or "text/html" not in r.headers.get("content-type", ""):
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "form", "aside"]):
            tag.decompose()
        text = " ".join(soup.stripped_strings)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_chars]
    except Exception:
        return ""


def _enrich_top_sources(evidence: List[dict], limit: int = 10) -> List[dict]:
    enriched = []
    for i, item in enumerate(evidence):
        row = dict(item)
        if i < limit and row.get("link"):
            page_text = _fetch_page_text(row["link"])
            if page_text:
                row["page_excerpt"] = page_text
        enriched.append(row)
    return enriched


def _source_lines(evidence: List[dict], limit: int = 45) -> str:
    lines = []
    for i, x in enumerate(evidence[:limit], start=1):
        excerpt = x.get("page_excerpt") or x.get("snippet") or ""
        excerpt = excerpt[:2200]
        lines.append(
            f"[S{i}] TYPE={x.get('source_type','')} | DATE={x.get('date','')} | "
            f"TITLE={x.get('title','')} | URL={x.get('link','')} | "
            f"QUERY={x.get('query','')} | TEXT={excerpt}"
        )
    return "\n".join(lines)


def _parse_chart_block(text: str) -> tuple[str, list]:
    marker = re.search(r"<!--\s*CHART_DATA_JSON\s*(.*?)\s*CHART_DATA_JSON\s*-->", text, flags=re.S | re.I)
    if not marker:
        return text.strip(), []
    raw = marker.group(1).strip()
    clean_text = (text[: marker.start()] + text[marker.end() :]).strip()
    try:
        charts = json.loads(raw)
        if not isinstance(charts, list):
            charts = []
    except Exception:
        charts = []

    valid = []
    for c in charts[:3]:
        if not isinstance(c, dict):
            continue
        labels = c.get("labels") or []
        values = c.get("values") or []
        if len(labels) < 2 or len(labels) != len(values):
            continue
        try:
            nums = [float(v) for v in values]
        except Exception:
            continue
        valid.append(
            {
                "title": str(c.get("title", "Evidence-backed comparison")),
                "type": str(c.get("type", "bar")).lower(),
                "labels": [str(x) for x in labels],
                "values": nums,
                "unit": str(c.get("unit", "")),
                "source_ids": [str(x) for x in c.get("source_ids", [])],
                "note": str(c.get("note", "")),
            }
        )
    return clean_text, valid


def run_market_research(
    country: str,
    product: str,
    objective: str,
    platform: str = "",
    dimensions: List[str] | None = None,
) -> Dict[str, Any]:
    dimensions = dimensions or [
        "Market size & growth",
        "Competition",
        "Pricing",
        "Channels",
        "Consumer need",
        "Regulation",
    ]

    cfg = _search_config(country)
    queries = _plan_queries(country, product, objective, platform, dimensions)

    evidence: List[dict] = []
    search_errors: List[str] = []
    for plan in queries:
        try:
            rows = _serper_search(plan["query"], num=6, gl=cfg.get("gl", ""), hl=cfg.get("hl", "en"))
            for row in rows:
                row["dimension"] = plan.get("dimension", "General")
                row["query_language"] = plan.get("language", "")
            evidence.extend(rows)
        except Exception as e:
            search_errors.append(f"{plan['query']}: {e}")

    evidence = _rank_evidence(_dedupe_evidence(evidence))
    live = any(x.get("link") for x in evidence)

    if not live:
        return {
            "mode": "DEMO SEARCH",
            "country": country,
            "product": product,
            "objective": objective,
            "dimensions": dimensions,
            "queries": queries,
            "evidence": [],
            "analysis": (
                "## Research unavailable\n\n"
                "Live search returned no usable evidence. Check SERPER_API_KEY / connectivity and retry."
            ),
            "charts": [],
            "search_errors": search_errors,
        }

    evidence = _enrich_top_sources(evidence[:60], limit=10)
    source_text = _source_lines(evidence, limit=45)
    skill = _skill_text()

    report_prompt = f"""
You are the Market & Product Intelligence research engine for Brazil Commerce OS.
Follow the research standard below exactly.

=== RESEARCH STANDARD ===
{skill}
=== END STANDARD ===

TARGET MARKET: {country}
PRODUCT/CATEGORY: {product}
USER OBJECTIVE: {objective}
PRIORITY PLATFORM: {platform or 'not specified'}
PRIORITY DIMENSIONS: {', '.join(dimensions)}
LOCAL SEARCH LANGUAGE: {cfg['local_language']}

SEARCH PLAN USED:
{json.dumps(queries, ensure_ascii=False)}

RETRIEVED EVIDENCE:
{source_text}

Write the full report now.

Mandatory content rules:
- Start with an Executive Summary that directly answers the business question.
- Be objective: do not force a positive or negative conclusion.
- Use source tags like [S1], [S2] directly after factual or quantitative claims.
- If a figure is only a broader-industry proxy, say so explicitly.
- If evidence conflicts, show the conflict and explain the difference in scope/definition.
- Do not invent exact category market size, sales, seller rankings, prices, market shares or regulations.
- Include at least one competitor/pricing table if evidence supports it.
- Include a concise “What this means commercially” interpretation after data-heavy sections.
- Include a Data Gaps / Confidence section.
- End with a staged validation plan: what can be decided now, what must be tested next.
- Do not dump raw URLs in the main body; use [S#] tags. A source appendix is added separately by the application.

Length target:
- If output is Chinese: roughly 2,500–5,000 Chinese characters when evidence supports it.
- If English or Brazilian Portuguese: roughly 1,800–3,000 words when evidence supports it.
- Do not pad the report with generic filler.

After the report, include an HTML-comment block exactly in this format:
<!-- CHART_DATA_JSON
[
  {{
    "title": "...",
    "type": "bar",
    "labels": ["...", "..."],
    "values": [1, 2],
    "unit": "BRL",
    "source_ids": ["S1", "S2"],
    "note": "Only use evidence-backed comparable values."
  }}
]
CHART_DATA_JSON -->

Chart rules:
- 0 to 3 charts maximum.
- Use only comparable numeric observations explicitly supported by the evidence above.
- If there are not at least two comparable numeric observations, return [] for charts.
"""

    try:
        raw_report = chat(report_prompt, max_tokens=7000, temperature=0.15)
    except Exception as e:
        raw_report = f"## Research generation error\n\n{e}"

    analysis, charts = _parse_chart_block(raw_report)

    return {
        "mode": "LIVE SEARCH",
        "country": country,
        "product": product,
        "objective": objective,
        "dimensions": dimensions,
        "queries": queries,
        "evidence": evidence,
        "analysis": analysis,
        "charts": charts,
        "search_errors": search_errors,
        "research_stats": {
            "queries_run": len(queries),
            "evidence_items": len(evidence),
            "enriched_sources": len([x for x in evidence if x.get("page_excerpt")]),
        },
    }
