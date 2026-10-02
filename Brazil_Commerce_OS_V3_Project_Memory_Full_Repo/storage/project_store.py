from __future__ import annotations

from datetime import datetime, timezone
import json
import uuid
from typing import Any, Optional

import streamlit as st

from .auth import current_user
from .schemas import MODULES, NEXT_MODULE
from .supabase_client import get_client, supabase_configured


LOCAL_PROJECTS = "_bcos_local_projects"
LOCAL_RUNS = "_bcos_local_module_runs"
LOCAL_MODULES = "_bcos_local_project_modules"
LOCAL_ACTIVITY = "_bcos_local_activity"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def persistence_mode() -> str:
    return "supabase" if supabase_configured() and current_user() else "session"


def _local_init() -> None:
    st.session_state.setdefault(LOCAL_PROJECTS, {})
    st.session_state.setdefault(LOCAL_RUNS, [])
    st.session_state.setdefault(LOCAL_MODULES, {})
    st.session_state.setdefault(LOCAL_ACTIVITY, [])


def create_project(
    project_name: str,
    product_name: str = "",
    target_market: str = "Brazil",
    category: str = "",
    selected_platform: str = "",
    notes: str = "",
) -> dict[str, Any]:
    name = project_name.strip()
    if not name:
        raise ValueError("Project name is required.")

    user = current_user()
    if persistence_mode() == "supabase":
        client = get_client()
        payload = {
            "user_id": user.id,
            "project_name": name,
            "product_name": product_name.strip(),
            "category": category.strip(),
            "target_market": target_market.strip() or "Brazil",
            "selected_platform": selected_platform.strip(),
            "current_stage": "market",
            "status": "active",
            "notes": notes.strip(),
        }
        row = client.table("projects").insert(payload).execute().data[0]
        _ensure_module_rows(row["id"], user.id)
        log_activity(row["id"], "project", "project_created", {"project_name": name})
        return row

    _local_init()
    project_id = str(uuid.uuid4())
    row = {
        "id": project_id,
        "user_id": "local",
        "project_name": name,
        "product_name": product_name.strip(),
        "category": category.strip(),
        "target_market": target_market.strip() or "Brazil",
        "selected_platform": selected_platform.strip(),
        "current_stage": "market",
        "status": "active",
        "notes": notes.strip(),
        "created_at": _now(),
        "updated_at": _now(),
    }
    st.session_state[LOCAL_PROJECTS][project_id] = row
    for module in MODULES:
        st.session_state[LOCAL_MODULES][f"{project_id}:{module}"] = {
            "project_id": project_id,
            "module": module,
            "status": "not_started",
            "progress_percent": 0,
            "blocking_count": 0,
            "missing_count": 0,
            "latest_run_id": None,
            "updated_at": _now(),
        }
    log_activity(project_id, "project", "project_created", {"project_name": name})
    return row


def _ensure_module_rows(project_id: str, user_id: str) -> None:
    client = get_client()
    rows = [
        {
            "user_id": user_id,
            "project_id": project_id,
            "module": module,
            "status": "not_started",
            "progress_percent": 0,
        }
        for module in MODULES
    ]
    client.table("project_modules").upsert(rows, on_conflict="project_id,module").execute()


def list_projects(include_archived: bool = False) -> list[dict[str, Any]]:
    if persistence_mode() == "supabase":
        user = current_user()
        query = get_client().table("projects").select("*").eq("user_id", user.id)
        if not include_archived:
            query = query.neq("status", "archived")
        return query.order("updated_at", desc=True).execute().data or []

    _local_init()
    rows = list(st.session_state[LOCAL_PROJECTS].values())
    if not include_archived:
        rows = [r for r in rows if r.get("status") != "archived"]
    return sorted(rows, key=lambda x: x.get("updated_at", ""), reverse=True)


def get_project(project_id: str) -> Optional[dict[str, Any]]:
    if not project_id:
        return None
    if persistence_mode() == "supabase":
        user = current_user()
        rows = (
            get_client().table("projects")
            .select("*")
            .eq("id", project_id)
            .eq("user_id", user.id)
            .limit(1)
            .execute().data
            or []
        )
        return rows[0] if rows else None
    _local_init()
    return st.session_state[LOCAL_PROJECTS].get(project_id)


def update_project(project_id: str, **fields: Any) -> Optional[dict[str, Any]]:
    allowed = {
        "project_name", "product_name", "category", "target_market",
        "selected_platform", "current_stage", "status", "notes",
    }
    payload = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not payload:
        return get_project(project_id)

    if persistence_mode() == "supabase":
        user = current_user()
        rows = (
            get_client().table("projects")
            .update(payload)
            .eq("id", project_id)
            .eq("user_id", user.id)
            .execute().data
            or []
        )
        return rows[0] if rows else get_project(project_id)

    _local_init()
    row = st.session_state[LOCAL_PROJECTS].get(project_id)
    if row:
        row.update(payload)
        row["updated_at"] = _now()
    return row


def get_module_statuses(project_id: str) -> list[dict[str, Any]]:
    if persistence_mode() == "supabase":
        user = current_user()
        return (
            get_client().table("project_modules")
            .select("*")
            .eq("project_id", project_id)
            .eq("user_id", user.id)
            .execute().data
            or []
        )
    _local_init()
    return [
        row for key, row in st.session_state[LOCAL_MODULES].items()
        if key.startswith(project_id + ":")
    ]


def save_module_result(
    project_id: str,
    module: str,
    result: Any,
    *,
    input_snapshot: Optional[dict[str, Any]] = None,
    status: str = "completed",
    progress_percent: int = 100,
    blocking_count: int = 0,
    missing_count: int = 0,
) -> dict[str, Any]:
    if module not in MODULES:
        raise ValueError(f"Unknown module: {module}")

    input_snapshot = _jsonable(input_snapshot or {})
    result_json = _jsonable(result)
    progress_percent = max(0, min(100, int(progress_percent)))

    if persistence_mode() == "supabase":
        user = current_user()
        client = get_client()
        previous = (
            client.table("module_runs")
            .select("version")
            .eq("project_id", project_id)
            .eq("module", module)
            .eq("user_id", user.id)
            .order("version", desc=True)
            .limit(1)
            .execute().data
            or []
        )
        version = int(previous[0]["version"]) + 1 if previous else 1
        run = client.table("module_runs").insert({
            "user_id": user.id,
            "project_id": project_id,
            "module": module,
            "version": version,
            "status": status,
            "input_snapshot": input_snapshot,
            "result": result_json,
        }).execute().data[0]
        client.table("project_modules").upsert({
            "user_id": user.id,
            "project_id": project_id,
            "module": module,
            "status": status,
            "progress_percent": progress_percent,
            "blocking_count": max(0, int(blocking_count)),
            "missing_count": max(0, int(missing_count)),
            "latest_run_id": run["id"],
            "updated_at": _now(),
        }, on_conflict="project_id,module").execute()
        update_project(project_id, current_stage=NEXT_MODULE.get(module, module))
        log_activity(project_id, module, "module_run_saved", {"version": version, "status": status})
        return run

    _local_init()
    previous = [r for r in st.session_state[LOCAL_RUNS] if r["project_id"] == project_id and r["module"] == module]
    version = max([int(r.get("version", 0)) for r in previous] + [0]) + 1
    run = {
        "id": str(uuid.uuid4()),
        "project_id": project_id,
        "module": module,
        "version": version,
        "status": status,
        "input_snapshot": input_snapshot,
        "result": result_json,
        "created_at": _now(),
    }
    st.session_state[LOCAL_RUNS].append(run)
    st.session_state[LOCAL_MODULES][f"{project_id}:{module}"] = {
        "project_id": project_id,
        "module": module,
        "status": status,
        "progress_percent": progress_percent,
        "blocking_count": max(0, int(blocking_count)),
        "missing_count": max(0, int(missing_count)),
        "latest_run_id": run["id"],
        "updated_at": _now(),
    }
    update_project(project_id, current_stage=NEXT_MODULE.get(module, module))
    log_activity(project_id, module, "module_run_saved", {"version": version, "status": status})
    return run


def get_latest_module_result(project_id: str, module: str) -> Optional[dict[str, Any]]:
    if persistence_mode() == "supabase":
        user = current_user()
        rows = (
            get_client().table("module_runs")
            .select("*")
            .eq("project_id", project_id)
            .eq("module", module)
            .eq("user_id", user.id)
            .order("version", desc=True)
            .limit(1)
            .execute().data
            or []
        )
        return rows[0] if rows else None
    _local_init()
    rows = [r for r in st.session_state[LOCAL_RUNS] if r["project_id"] == project_id and r["module"] == module]
    rows.sort(key=lambda x: int(x.get("version", 0)), reverse=True)
    return rows[0] if rows else None


def list_module_runs(project_id: str, module: Optional[str] = None) -> list[dict[str, Any]]:
    if persistence_mode() == "supabase":
        user = current_user()
        query = (
            get_client().table("module_runs")
            .select("*")
            .eq("project_id", project_id)
            .eq("user_id", user.id)
        )
        if module:
            query = query.eq("module", module)
        return query.order("created_at", desc=True).execute().data or []
    _local_init()
    rows = [r for r in st.session_state[LOCAL_RUNS] if r["project_id"] == project_id]
    if module:
        rows = [r for r in rows if r["module"] == module]
    return sorted(rows, key=lambda x: x.get("created_at", ""), reverse=True)


def log_activity(project_id: str, module: str, action: str, detail: Optional[dict[str, Any]] = None) -> None:
    detail = _jsonable(detail or {})
    if persistence_mode() == "supabase":
        user = current_user()
        get_client().table("activity_log").insert({
            "user_id": user.id,
            "project_id": project_id,
            "module": module,
            "action": action,
            "detail": detail,
        }).execute()
        return
    _local_init()
    st.session_state[LOCAL_ACTIVITY].append({
        "id": str(uuid.uuid4()),
        "project_id": project_id,
        "module": module,
        "action": action,
        "detail": detail,
        "created_at": _now(),
    })


def list_activity(project_id: str, limit: int = 100) -> list[dict[str, Any]]:
    if persistence_mode() == "supabase":
        user = current_user()
        return (
            get_client().table("activity_log")
            .select("*")
            .eq("project_id", project_id)
            .eq("user_id", user.id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute().data
            or []
        )
    _local_init()
    rows = [r for r in st.session_state[LOCAL_ACTIVITY] if r["project_id"] == project_id]
    return sorted(rows, key=lambda x: x.get("created_at", ""), reverse=True)[:limit]


def archive_project(project_id: str) -> None:
    update_project(project_id, status="archived")
    log_activity(project_id, "project", "project_archived", {})


def save_market_evidence(project_id: str, run_id: str, evidence: list[dict[str, Any]]) -> int:
    """Persist the evidence register for queryable auditability."""
    if not evidence:
        return 0
    if persistence_mode() != "supabase":
        return 0
    user = current_user()
    rows = []
    for idx, item in enumerate(evidence, start=1):
        rows.append({
            "user_id": user.id,
            "project_id": project_id,
            "run_id": run_id,
            "source_id": str(item.get("source_id") or item.get("id") or f"S{idx}"),
            "title": str(item.get("title") or ""),
            "url": str(item.get("link") or item.get("url") or ""),
            "source_type": str(item.get("source_type") or ""),
            "geography": str(item.get("geography") or ""),
            "published_date": str(item.get("date") or item.get("published_date") or ""),
            "snippet": str(item.get("snippet") or item.get("content_excerpt") or ""),
            "metadata": _jsonable(item),
        })
    get_client().table("market_evidence").insert(rows).execute()
    return len(rows)


def save_creator_records(project_id: str, records: list[dict[str, Any]], source_file_id: str | None = None) -> int:
    """Upsert creator rows so later campaigns can reuse/enrich the same pool."""
    if not records or persistence_mode() != "supabase":
        return 0
    user = current_user()
    rows = []
    for idx, item in enumerate(records, start=1):
        creator_key = str(
            item.get("creator_id") or item.get("handle") or item.get("display_name")
            or item.get("username") or f"creator-{idx}"
        ).strip()
        rows.append({
            "user_id": user.id,
            "project_id": project_id,
            "source_file_id": source_file_id,
            "creator_key": creator_key,
            "display_name": str(item.get("display_name") or item.get("username") or ""),
            "handle": str(item.get("handle") or item.get("username") or ""),
            "platform": str(item.get("platform") or ""),
            "category": str(item.get("category") or ""),
            "followers": item.get("followers"),
            "avg_views": item.get("avg_views"),
            "engagement_rate": item.get("engagement_rate"),
            "fee_brl": item.get("fee_brl"),
            "contact": str(item.get("contact") or item.get("email") or ""),
            "profile_url": str(item.get("profile_url") or ""),
            "source_url": str(item.get("source_url") or item.get("content_url") or ""),
            "fit_score": item.get("fit_score"),
            "raw_data": _jsonable(item),
        })
    get_client().table("creator_records").upsert(rows, on_conflict="project_id,creator_key").execute()
    return len(rows)


def save_finance_metrics(project_id: str, run_id: str, calc: dict[str, Any]) -> int:
    """Persist numeric finance metrics in queryable form in addition to the full JSON run."""
    if not calc or persistence_mode() != "supabase":
        return 0
    user = current_user()
    rows = []
    units = {
        "net_sales": "BRL", "aov": "BRL", "contribution_profit": "BRL",
        "contribution_margin": "ratio", "roas": "ratio",
    }
    for name, value in calc.items():
        if name in {"mapping", "missing_for_profitability"}:
            continue
        metric_value = value if isinstance(value, (int, float)) and not isinstance(value, bool) else None
        metric_text = None if metric_value is not None else (str(value) if value is not None else None)
        rows.append({
            "user_id": user.id,
            "project_id": project_id,
            "run_id": run_id,
            "metric_name": name,
            "metric_value": metric_value,
            "metric_text": metric_text,
            "unit": units.get(name, ""),
        })
    if rows:
        get_client().table("finance_metrics").insert(rows).execute()
    return len(rows)
