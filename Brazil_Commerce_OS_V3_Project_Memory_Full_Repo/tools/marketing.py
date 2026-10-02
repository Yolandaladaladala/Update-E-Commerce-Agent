from __future__ import annotations

import math
import re
import unicodedata
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

import pandas as pd
import requests

from config import SERPER_API_KEY
from llm import chat


# =============================================================================
# SECTION 3 — CREATOR DISCOVERY, MATCHING & CAMPAIGN INTELLIGENCE
# =============================================================================
# This version supports TWO workflows:
#
# A) DISCOVERY MODE
#    User gives product/category/market/platform/objective.
#    The agent plans multiple searches, retrieves real public creator candidates,
#    deduplicates them, checks relevance, expands search when the pool is too
#    small, scores candidates, and explains the shortlist.
#
# B) ANALYSE-MY-LIST MODE
#    User uploads CSV/XLS/XLSX.
#    The tool normalises multilingual columns, checks whether the creator pool
#    is relevant, ranks only supported candidates, and explains the result.
#
# Important governance:
# - Creator identities must come from a source, never from the LLM.
# - Public-search snippets are discovery evidence, not verified performance data.
# - Missing followers/fees/GMV/conversion remain missing.
# - Human approval remains required for outreach, contracts, publishing/payment.
# =============================================================================


# -----------------------------------------------------------------------------
# Schema normalisation
# -----------------------------------------------------------------------------
COLUMN_ALIASES = {
    "creator_id": [
        "creator_id", "creator id", "id creator", "id do creator", "id do criador",
    ],
    "display_name": [
        "display_name", "display name", "name", "creator", "creator_name", "creator name",
        "username", "user name", "handle", "nome", "nome do criador", "criador",
    ],
    "platform": [
        "platform", "platforms", "plataforma", "plataformas", "plataforma(s)",
    ],
    "category": [
        "category", "creator_category", "creator category", "categoria", "niche", "nicho",
    ],
    "followers": [
        "followers", "follower", "followers_count", "follower count", "seguidores",
        "numero de seguidores", "número de seguidores",
    ],
    "avg_views": [
        "avg_views", "average_views", "average views", "media de views", "média de views",
        "visualizacoes medias", "visualizações médias",
    ],
    "engagement_rate": [
        "engagement_rate", "engagement rate", "engagement", "taxa de engajamento",
        "engajamento",
    ],
    "gmv_30d": [
        "gmv_30d", "gmv 30d", "gmv", "gmv_30_days", "gmv 30 days", "gmv 30 dias",
    ],
    "fee_brl": [
        "fee_brl", "creator_fee", "creator fee", "fee", "price", "quote", "quotation",
        "preco", "preço", "valor", "cachê", "cache",
    ],
    "profile_url": [
        "profile_url", "profile url", "profile link", "link perfil tiktok",
        "link perfil instagram", "link do perfil", "perfil",
    ],
    "content_url": [
        "content_url", "content url", "video_url", "video url", "link video tiktok",
        "link vídeo tiktok", "link do video", "link do vídeo",
    ],
    "product_url": [
        "product_url", "product url", "website", "website_url", "site", "link site/produto",
        "link produto", "link do produto",
    ],
    "content_focus": [
        "content_focus", "content focus", "what they teach", "o que ensina", "conteudo",
        "conteúdo", "tema", "topic", "snippet", "description",
    ],
    "research_status": [
        "research_status", "research status", "status", "status da pesquisa",
    ],
    "source": [
        "source", "data_source", "data source", "fonte",
    ],
    "source_date": [
        "source_date", "source date", "date", "data", "data da fonte",
    ],
    "source_title": [
        "source_title", "search_title", "title",
    ],
    "source_snippet": [
        "source_snippet", "search_snippet", "snippet",
    ],
    "data_confidence": [
        "data_confidence", "confidence", "evidence_confidence",
    ],
}

NUMERIC_FIELDS = [
    "followers", "avg_views", "engagement_rate", "gmv_30d", "fee_brl",
    "data_confidence",
]

CATEGORY_GROUPS = {
    "pet": {
        "pet", "pets", "animal", "animals", "animais", "pet care", "petcare",
    },
    "cat": {
        "cat", "cats", "gato", "gatos", "felino", "felinos", "kitten", "kitty",
    },
    "dog": {
        "dog", "dogs", "cachorro", "cachorros", "cao", "caes", "puppy",
    },
    "home": {
        "home", "home living", "home & living", "living", "casa", "lar", "decor",
        "decoracao", "decoração", "furniture", "moveis", "móveis", "interior", "household",
    },
    "beauty": {
        "beauty", "beleza", "makeup", "maquiagem", "skincare", "skin care",
        "cosmetics", "cosmeticos", "cosméticos",
    },
    "fashion": {
        "fashion", "moda", "style", "estilo", "clothing", "apparel", "roupa", "roupas",
    },
    "food": {
        "food", "foods", "comida", "alimento", "alimentos", "culinaria",
        "culinária", "recipe", "receita", "receitas",
    },
    "fitness": {
        "fitness", "sport", "sports", "esporte", "esportes", "gym", "academia",
        "wellness", "bem estar", "bem-estar",
    },
    "tech": {
        "tech", "technology", "tecnologia", "gadget", "gadgets", "electronics",
        "eletronicos", "eletrônicos",
    },
    "automotive": {
        "auto", "automotive", "car", "cars", "vehicle", "vehicles", "automotivo",
        "carro", "carros", "veiculo", "veículo", "veiculos", "veículos",
    },
}

PLATFORM_DOMAINS = {
    "TikTok": ("tiktok.com",),
    "Instagram": ("instagram.com",),
    "YouTube": ("youtube.com", "youtu.be"),
    "Facebook": ("facebook.com",),
    "Kwai": ("kwai.com",),
}

COMMERCIAL_TERMS = {
    "review", "reviews", "unboxing", "affiliate", "afiliado", "afiliada",
    "tiktok shop", "shop", "produto", "product", "achadinhos", "comprinhas",
    "cupom", "discount", "desconto", "live", "livestream",
}


def _plain(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().strip()
    text = re.sub(r"[_\-/|]+", " ", text)
    text = re.sub(r"[^a-z0-9%+&.@ ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _alias_lookup() -> Dict[str, str]:
    out: Dict[str, str] = {}
    for canonical, aliases in COLUMN_ALIASES.items():
        out[_plain(canonical)] = canonical
        for alias in aliases:
            out[_plain(alias)] = canonical
    return out


_ALIAS_LOOKUP = _alias_lookup()


def _parse_numeric(value: Any) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)

    s = _plain(value)
    if not s or s in {"nan", "none", "missing", "n/a", "na", "-"}:
        return None

    multiplier = 1.0
    if re.search(r"\b(k|mil)\b", s):
        multiplier = 1_000.0
    elif re.search(r"\b(m|mi|milhao|milhoes|million)\b", s):
        multiplier = 1_000_000.0

    raw = re.sub(r"[^0-9,.-]", "", s)
    if not raw:
        return None

    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        parts = raw.split(",")
        if len(parts[-1]) in {1, 2}:
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")

    try:
        return float(raw) * multiplier
    except ValueError:
        return None


def normalize_creator_schema(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    rename_map: Dict[str, str] = {}
    occupied = set(str(c) for c in x.columns)

    for original in x.columns:
        canonical = _ALIAS_LOOKUP.get(_plain(original))
        if canonical and canonical not in occupied and canonical not in rename_map.values():
            rename_map[original] = canonical
        elif canonical and str(original) == canonical:
            rename_map[original] = canonical

    x = x.rename(columns=rename_map)

    for canonical in COLUMN_ALIASES:
        matching = [c for c in x.columns if _plain(c) == _plain(canonical)]
        if len(matching) > 1:
            merged = x[matching[0]].copy()
            for col in matching[1:]:
                merged = merged.where(
                    merged.notna() & (merged.astype(str).str.strip() != ""),
                    x[col],
                )
            x[canonical] = merged
            x = x.drop(columns=[c for c in matching if c != canonical], errors="ignore")

    if "creator_id" not in x.columns and "display_name" in x.columns:
        x["creator_id"] = x["display_name"].astype(str).map(
            lambda s: "CREATOR-" + re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-").upper()[:48]
            if s.strip() else ""
        )

    for col in NUMERIC_FIELDS:
        if col in x.columns:
            x[col] = x[col].map(_parse_numeric)

    return x


def load_creator_file(file) -> pd.DataFrame:
    name = getattr(file, "name", "")
    if name.lower().endswith(".csv"):
        raw = pd.read_csv(file)
    else:
        raw = pd.read_excel(file)
    return normalize_creator_schema(raw)


# -----------------------------------------------------------------------------
# Relevance logic
# -----------------------------------------------------------------------------
def _tokenise(text: str) -> set[str]:
    return {
        t for t in re.split(r"\s+", _plain(text))
        if len(t) >= 2 and t not in {"and", "the", "de", "da", "do", "para", "com"}
    }


def _detect_target_groups(category: str, product: str = "") -> set[str]:
    text = f"{_plain(category)} {_plain(product)}"
    groups: set[str] = set()

    for group, terms in CATEGORY_GROUPS.items():
        if any(_plain(term) in text for term in terms):
            groups.add(group)

    # Species-specific target should not collapse to generic "pet".
    if "cat" in groups:
        groups.discard("dog")
    if "dog" in groups:
        groups.discard("cat")

    return groups


def _row_relevance_text(row: pd.Series) -> str:
    fields = [
        "category", "content_focus", "display_name",
        "source_title", "source_snippet",
    ]
    return " | ".join(_plain(row.get(c, "")) for c in fields if c in row.index)


def _creator_relevance_score(row: pd.Series, category: str, product: str = "") -> float:
    text = _row_relevance_text(row)
    if not text:
        return 0.0

    target_groups = _detect_target_groups(category, product)
    product_tokens = _tokenise(product)
    category_tokens = _tokenise(category)

    score = 0.0

    # Direct product terms are strongest.
    direct_hits = sum(1 for t in product_tokens if t in text)
    if product_tokens:
        score += min(45.0, 45.0 * direct_hits / max(1, len(product_tokens)))

    # Category terms.
    category_hits = sum(1 for t in category_tokens if t in text)
    if category_tokens:
        score += min(25.0, 25.0 * category_hits / max(1, len(category_tokens)))

    # Broader semantic group match.
    row_groups = set()
    for group, terms in CATEGORY_GROUPS.items():
        if any(_plain(term) in text for term in terms):
            row_groups.add(group)

    # Cat vs dog is intentionally strict.
    if "cat" in target_groups and "dog" in row_groups and "cat" not in row_groups:
        score = min(score, 20.0)
    elif "dog" in target_groups and "cat" in row_groups and "dog" not in row_groups:
        score = min(score, 20.0)
    elif target_groups & row_groups:
        score += 20.0

    # Commerce/content signal.
    if any(term in text for term in COMMERCIAL_TERMS):
        score += 10.0

    return round(min(score, 100.0), 1)


def _top_counts(series: pd.Series, n: int = 5) -> List[Dict[str, Any]]:
    clean = series.dropna().astype(str).str.strip()
    clean = clean[clean.ne("") & clean.str.lower().ne("nan")]
    counts = clean.value_counts().head(n)
    return [{"value": str(idx), "count": int(val)} for idx, val in counts.items()]


def analyse_creator_dataset(
    df: pd.DataFrame,
    target_category: str = "",
    product: str = "",
) -> Dict[str, Any]:
    x = normalize_creator_schema(df)
    total = int(len(x))

    present_fields = [c for c in COLUMN_ALIASES if c in x.columns and x[c].notna().any()]
    useful_for_ranking = [
        c for c in [
            "display_name", "platform", "category", "followers", "avg_views",
            "engagement_rate", "gmv_30d", "fee_brl", "content_focus",
            "profile_url", "source_snippet",
        ]
        if c in present_fields
    ]

    category_counts = _top_counts(x["category"]) if "category" in x.columns else []
    platform_counts = _top_counts(x["platform"]) if "platform" in x.columns else []

    if target_category.strip() or product.strip():
        relevance = x.apply(
            lambda row: _creator_relevance_score(row, target_category, product),
            axis=1,
        )
        matched_mask = relevance >= 35.0
        matched_count = int(matched_mask.sum())
    else:
        relevance = pd.Series(0.0, index=x.index)
        matched_mask = pd.Series(False, index=x.index)
        matched_count = 0

    match_rate = matched_count / total if total else 0.0

    if not target_category.strip() and not product.strip():
        fit_level = "NOT_ASSESSED"
    elif matched_count == 0:
        fit_level = "LOW"
    elif matched_count >= 10 or match_rate >= 0.30:
        fit_level = "HIGH"
    elif matched_count >= 3 or match_rate >= 0.10:
        fit_level = "MEDIUM"
    else:
        fit_level = "LOW"

    return {
        "rows": total,
        "present_fields": present_fields,
        "ranking_fields": useful_for_ranking,
        "top_categories": category_counts,
        "top_platforms": platform_counts,
        "target_category": target_category,
        "product": product,
        "matched_count": matched_count,
        "match_rate": round(match_rate, 4),
        "fit_level": fit_level,
        "can_shortlist": (
            bool(target_category.strip() or product.strip())
            and fit_level in {"MEDIUM", "HIGH"}
            and matched_count > 0
        ),
        "matched_index": x.index[matched_mask].tolist(),
        "relevance_scores": relevance.round(1).to_dict(),
    }


# -----------------------------------------------------------------------------
# Deterministic scoring
# -----------------------------------------------------------------------------
def _percentile_score(s: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(s, errors="coerce")
    if numeric.notna().sum() <= 1:
        return pd.Series(0.5, index=s.index)
    return numeric.rank(pct=True, method="average").fillna(0.0)


def _row_data_confidence(row: pd.Series) -> float:
    weighted_fields = {
        "profile_url": 0.22,
        "display_name": 0.12,
        "platform": 0.10,
        "category": 0.08,
        "content_focus": 0.10,
        "followers": 0.10,
        "avg_views": 0.08,
        "engagement_rate": 0.08,
        "gmv_30d": 0.05,
        "fee_brl": 0.04,
        "source": 0.03,
    }

    score = 0.0
    for field, weight in weighted_fields.items():
        if field in row.index:
            value = row.get(field)
            if pd.notna(value) and str(value).strip() not in {"", "nan", "None", "missing"}:
                score += weight

    # Public-search-only records should not look fully verified.
    status = _plain(row.get("research_status", ""))
    if "public search candidate" in status:
        score = min(score, 0.55)

    return round(min(score, 1.0), 2)


def score_creators(
    df: pd.DataFrame,
    category: str,
    budget: float | None = None,
    product: str = "",
) -> pd.DataFrame:
    x = normalize_creator_schema(df)
    profile = analyse_creator_dataset(x, category, product)

    if not profile["can_shortlist"]:
        empty = x.iloc[0:0].copy()
        empty["fit_score"] = pd.Series(dtype=float)
        empty["data_confidence"] = pd.Series(dtype=float)
        empty.attrs["dataset_profile"] = profile
        return empty

    matched = x.loc[profile["matched_index"]].copy()

    # Fit and confidence are deliberately separate.
    matched["relevance_score"] = matched.apply(
        lambda row: _creator_relevance_score(row, category, product),
        axis=1,
    )

    fit = matched["relevance_score"] * 0.60

    if "followers" in matched.columns and matched["followers"].notna().any():
        fit += _percentile_score(matched["followers"]) * 10.0

    if "avg_views" in matched.columns and matched["avg_views"].notna().any():
        fit += _percentile_score(matched["avg_views"]) * 10.0

    if "engagement_rate" in matched.columns and matched["engagement_rate"].notna().any():
        er = pd.to_numeric(matched["engagement_rate"], errors="coerce")
        if er.dropna().max() <= 1:
            er = er * 100
        fit += er.clip(lower=0, upper=10).fillna(0) / 10 * 10.0

    if "gmv_30d" in matched.columns and matched["gmv_30d"].notna().any():
        fit += _percentile_score(matched["gmv_30d"]) * 5.0

    if budget and "fee_brl" in matched.columns and matched["fee_brl"].notna().any():
        fee = pd.to_numeric(matched["fee_brl"], errors="coerce")
        budget_fit = fee.le(float(budget)).where(fee.notna(), False).astype(float)
        fit += budget_fit * 5.0

    matched["fit_score"] = fit.clip(0, 100).round(1)
    matched["data_confidence"] = matched.apply(_row_data_confidence, axis=1)

    # Backward-compatible field used by the old UI.
    matched["score_data_coverage"] = matched["data_confidence"]

    matched.attrs["dataset_profile"] = profile
    return matched.sort_values(
        ["fit_score", "data_confidence", "followers" if "followers" in matched.columns else "fit_score"],
        ascending=False,
    )


# -----------------------------------------------------------------------------
# Agentic creator discovery
# -----------------------------------------------------------------------------
def _platform_from_url(url: str) -> str:
    host = urlparse(url).netloc.lower()
    for platform, domains in PLATFORM_DOMAINS.items():
        if any(domain in host for domain in domains):
            return platform
    return "Web"


def _profile_like_url(url: str, platform: str) -> bool:
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        path = parsed.path.strip("/")
    except Exception:
        return False

    if not url.startswith(("http://", "https://")):
        return False

    domains = PLATFORM_DOMAINS.get(platform, ())
    if domains and not any(domain in host for domain in domains):
        return False

    if platform == "TikTok":
        return "/@" in parsed.path
    if platform == "Instagram":
        blocked = {"p", "reel", "reels", "stories", "explore"}
        first = path.split("/")[0] if path else ""
        return bool(first) and first not in blocked
    if platform == "YouTube":
        return any(token in parsed.path for token in ["/@", "/channel/", "/c/", "/user/"])
    if platform == "Facebook":
        return bool(path)
    if platform == "Kwai":
        return bool(path)
    return False


def _display_name_from_result(title: str, url: str) -> str:
    title = (title or "").strip()
    title = re.sub(
        r"\s*[-|·]\s*(TikTok|Instagram|YouTube|Facebook|Kwai).*$",
        "",
        title,
        flags=re.I,
    ).strip()

    if title:
        return title[:120]

    path = urlparse(url).path.strip("/")
    if "/@" in url:
        handle = url.split("/@", 1)[1].split("/", 1)[0]
        return f"@{handle}"
    return path.split("/")[0] if path else url


def _serper_search(query: str, num: int = 10) -> List[Dict[str, Any]]:
    if not SERPER_API_KEY:
        raise RuntimeError(
            "Creator Discovery needs SERPER_API_KEY. "
            "Add the key to your Streamlit secrets/config, or use 'Analyse My Creator List'."
        )

    response = requests.post(
        "https://google.serper.dev/search",
        headers={
            "X-API-KEY": SERPER_API_KEY,
            "Content-Type": "application/json",
        },
        json={
            "q": query,
            "num": max(5, min(int(num), 20)),
            "gl": "br",
            "hl": "pt-br",
        },
        timeout=25,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("organic", []) or []


def build_creator_search_plan(
    product: str,
    category: str,
    objective: str,
    platforms: List[str],
    market: str = "Brazil",
    target_count: int = 20,
) -> Dict[str, Any]:
    """
    Deterministic planning layer.

    The LLM is not allowed to invent creators. Search planning can be generated
    in code because the important agent behaviour is the iterative tool loop:
    plan -> search -> observe -> expand -> stop.
    """
    product_clean = product.strip()
    category_clean = category.strip()
    market_clean = market.strip() or "Brazil"

    direct_terms = [
        product_clean,
        category_clean,
        f"{category_clean} creator",
        f"{category_clean} influencer",
    ]

    adjacent_terms: List[str] = []
    target_groups = _detect_target_groups(category_clean, product_clean)

    if "cat" in target_groups:
        adjacent_terms += ["gatos", "cat care", "cat lifestyle", "pet cats"]
    elif "dog" in target_groups:
        adjacent_terms += ["cachorros", "dog care", "dog lifestyle"]
    elif "pet" in target_groups:
        adjacent_terms += ["pet care", "pet lifestyle", "animais de estimação"]
    if "home" in target_groups:
        adjacent_terms += ["home decor", "casa decoração", "home living"]

    if not adjacent_terms:
        adjacent_terms += [category_clean, product_clean]

    commercial_terms = [
        "review produto",
        "affiliate",
        "achadinhos",
        "TikTok Shop",
        "unboxing",
    ]

    rounds: List[Dict[str, Any]] = []

    for round_no, terms in enumerate(
        [direct_terms, adjacent_terms, commercial_terms],
        start=1,
    ):
        queries: List[str] = []
        for platform in platforms:
            domain = PLATFORM_DOMAINS.get(platform, ("",))[0]
            for term in terms:
                term = term.strip()
                if not term:
                    continue
                query = f'site:{domain} "{market_clean}" {term}'
                queries.append(query)

        # Deduplicate while preserving order.
        queries = list(dict.fromkeys(queries))
        rounds.append({
            "round": round_no,
            "purpose": [
                "Direct product/category discovery",
                "Adjacent niche expansion",
                "Commercial-content expansion",
            ][round_no - 1],
            "queries": queries,
        })

    return {
        "product": product_clean,
        "category": category_clean,
        "objective": objective,
        "market": market_clean,
        "platforms": platforms,
        "target_count": int(target_count),
        "stop_rule": "Stop when enough unique profile candidates are collected or all planned rounds are exhausted.",
        "rounds": rounds,
    }


def discover_creators(
    product: str,
    category: str,
    objective: str,
    platforms: List[str],
    market: str = "Brazil",
    budget: float | None = None,
    target_count: int = 20,
    max_rounds: int = 3,
) -> Dict[str, Any]:
    """
    Agentic discovery loop:
    PLAN -> SEARCH -> OBSERVE -> EXPAND -> STOP.

    Search results create real sourced candidates only. They do NOT create
    followers, fees, GMV, conversion or audience demographics.
    """
    if not product.strip() or not category.strip():
        raise ValueError("Product and Category are required for creator discovery.")

    platforms = [p for p in platforms if p in PLATFORM_DOMAINS]
    if not platforms:
        raise ValueError("Choose at least one supported platform.")

    target_count = max(5, min(int(target_count), 50))
    plan = build_creator_search_plan(
        product, category, objective, platforms, market, target_count
    )

    seen: set[str] = set()
    records: List[Dict[str, Any]] = []
    search_log: List[Dict[str, Any]] = []

    rounds_used = 0

    for round_info in plan["rounds"][: max(1, min(max_rounds, 3))]:
        rounds_used += 1
        round_new = 0

        for query in round_info["queries"]:
            results = _serper_search(query, num=10)
            retained = 0

            for item in results:
                link = (item.get("link") or "").strip()
                title = (item.get("title") or "").strip()
                snippet = (item.get("snippet") or "").strip()
                platform = _platform_from_url(link)

                if platform not in platforms:
                    continue
                if not _profile_like_url(link, platform):
                    continue

                canonical = link.split("?", 1)[0].rstrip("/").lower()
                if canonical in seen:
                    continue

                seen.add(canonical)
                retained += 1
                round_new += 1

                temp_row = pd.Series({
                    "display_name": _display_name_from_result(title, link),
                    "platform": platform,
                    "content_focus": snippet,
                    "source_title": title,
                    "source_snippet": snippet,
                })
                relevance = _creator_relevance_score(temp_row, category, product)

                records.append({
                    "creator_id": "CREATOR-DISC-" + str(len(records) + 1).zfill(4),
                    "display_name": _display_name_from_result(title, link),
                    "platform": platform,
                    "category": None,
                    "followers": None,
                    "avg_views": None,
                    "engagement_rate": None,
                    "gmv_30d": None,
                    "fee_brl": None,
                    "profile_url": link,
                    "content_focus": snippet,
                    "source_title": title,
                    "source_snippet": snippet,
                    "source": "Google/Serper public search",
                    "source_date": None,
                    "research_status": "Public search candidate — requires profile/performance enrichment",
                    "discovery_relevance": relevance,
                })

            search_log.append({
                "round": round_info["round"],
                "query": query,
                "results_seen": len(results),
                "profiles_retained": retained,
            })

            if len(records) >= target_count:
                break

        if len(records) >= target_count:
            break

        # Agent observation: if the current round produced too few candidates,
        # continue automatically into the next broader search round.
        if round_new == 0 and round_info["round"] >= max_rounds:
            break

    candidates = pd.DataFrame(records)

    if candidates.empty:
        return {
            "status": "NO_CANDIDATES",
            "plan": plan,
            "search_log": search_log,
            "rounds_used": rounds_used,
            "candidates": candidates,
            "ranked": candidates,
            "profile": {
                "rows": 0,
                "matched_count": 0,
                "fit_level": "LOW",
                "can_shortlist": False,
            },
        }

    # Keep the search pool honest: remove very weak semantic matches before ranking.
    candidates = candidates.sort_values(
        "discovery_relevance", ascending=False
    ).reset_index(drop=True)

    candidate_pool = candidates[candidates["discovery_relevance"] >= 25].copy()
    if candidate_pool.empty:
        candidate_pool = candidates.head(min(10, len(candidates))).copy()

    ranked = score_creators(
        candidate_pool,
        category=category,
        budget=budget,
        product=product,
    )

    profile = ranked.attrs.get(
        "dataset_profile",
        analyse_creator_dataset(candidate_pool, category, product),
    )

    status = "TARGET_REACHED" if len(candidates) >= target_count else "PARTIAL_POOL"

    return {
        "status": status,
        "plan": plan,
        "search_log": search_log,
        "rounds_used": rounds_used,
        "candidates": candidates.head(target_count).reset_index(drop=True),
        "ranked": ranked,
        "profile": profile,
    }


# -----------------------------------------------------------------------------
# AI explanation
# -----------------------------------------------------------------------------
def _records_for_llm(df: pd.DataFrame, limit: int = 15) -> List[Dict[str, Any]]:
    preferred = [
        "creator_id", "display_name", "platform", "category", "followers",
        "avg_views", "engagement_rate", "gmv_30d", "fee_brl",
        "content_focus", "profile_url", "research_status", "source",
        "source_title", "source_snippet", "fit_score", "data_confidence",
    ]
    cols = [c for c in preferred if c in df.columns]
    if not cols:
        cols = list(df.columns[:12])
    return (
        df[cols]
        .head(limit)
        .where(pd.notna(df[cols].head(limit)), "missing")
        .to_dict("records")
    )


def explain_creator_fit(
    shortlisted: pd.DataFrame,
    campaign_id: str,
    product: str,
    objective: str,
    approved_brief: str,
    dataset_profile: Dict[str, Any] | None = None,
    full_dataset: pd.DataFrame | None = None,
    discovery_context: Dict[str, Any] | None = None,
) -> str:
    if dataset_profile is None:
        dataset_profile = (
            shortlisted.attrs.get("dataset_profile")
            if hasattr(shortlisted, "attrs")
            else None
        )

    source_df = full_dataset if full_dataset is not None else shortlisted

    if dataset_profile is None:
        dataset_profile = analyse_creator_dataset(source_df, "", product)

    if shortlisted.empty:
        sample_records = _records_for_llm(
            normalize_creator_schema(source_df)
            if source_df is not None
            else shortlisted
        )
    else:
        sample_records = _records_for_llm(shortlisted)

    discovery_text = discovery_context or {}

    prompt = f"""
You are the Creator Discovery & Campaign Intelligence agent for a professional commerce team.

Campaign reference: {campaign_id}
Product: {product}
Objective: {objective}
Approved brief / confirmed facts only:
{approved_brief or 'No additional approved product facts supplied.'}

DETERMINISTIC DATASET PROFILE:
{dataset_profile}

DISCOVERY / TOOL CONTEXT:
{discovery_text}

REAL CREATOR RECORDS FROM SEARCH OR USER DATA:
{sample_records}

Rules:
- Creator identities and URLs must come from the supplied records. Never invent a creator.
- Public-search snippets are discovery evidence only. Do not pretend they prove followers, GMV, conversion, audience demographics or fee.
- Missing performance data must remain missing.
- Distinguish FIT from DATA CONFIDENCE.
- A highly relevant but data-poor creator may be a strong research candidate, not yet a final commercial recommendation.
- If the pool is weak, say the search should be expanded or enriched instead of fabricating a Top 10.
- Human approval is required before outreach, contracting, publishing or payment.

Return:
1. Executive Decision Summary
2. Search / Dataset Quality
3. Recommended Creator Shortlist
   - only use creator names actually present in the records
   - explain WHY each fits the product/campaign
   - state what evidence is still missing
4. Creators / profiles that should be deprioritised and why
5. Next Agent Actions
   - what data should be enriched next (e.g. followers, recent views, engagement, public commerce signals, fee)
   - whether another search round is needed
6. Recommended campaign/content direction based only on confirmed product facts

Be concise, commercial and management-ready.
"""
    return chat(prompt)

