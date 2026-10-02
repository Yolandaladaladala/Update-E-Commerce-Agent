from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
import mimetypes
import re
import uuid
from typing import Any, Optional

import streamlit as st

from .auth import current_user
from .project_store import persistence_mode
from .supabase_client import get_client, storage_bucket

LOCAL_FILES = "_bcos_local_files"


def _safe_name(name: str) -> str:
    name = PurePosixPath(name or "file.bin").name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name or "file.bin"


def _local_init() -> None:
    st.session_state.setdefault(LOCAL_FILES, {})


def upload_project_file(
    project_id: str,
    module: str,
    file_name: str,
    data: bytes,
    *,
    mime_type: Optional[str] = None,
    source_kind: str = "upload",
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data must be bytes")
    clean_name = _safe_name(file_name)
    mime_type = mime_type or mimetypes.guess_type(clean_name)[0] or "application/octet-stream"
    metadata = metadata or {}

    if persistence_mode() == "supabase":
        user = current_user()
        client = get_client()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        storage_path = f"{user.id}/{project_id}/{module}/{stamp}_{uuid.uuid4().hex[:8]}_{clean_name}"
        client.storage.from_(storage_bucket()).upload(
            path=storage_path,
            file=bytes(data),
            file_options={"content-type": mime_type, "upsert": "false"},
        )
        row = client.table("project_files").insert({
            "user_id": user.id,
            "project_id": project_id,
            "module": module,
            "file_name": clean_name,
            "storage_path": storage_path,
            "mime_type": mime_type,
            "size_bytes": len(data),
            "source_kind": source_kind,
            "metadata": metadata,
        }).execute().data[0]
        return row

    _local_init()
    file_id = str(uuid.uuid4())
    row = {
        "id": file_id,
        "project_id": project_id,
        "module": module,
        "file_name": clean_name,
        "storage_path": f"session://{file_id}",
        "mime_type": mime_type,
        "size_bytes": len(data),
        "source_kind": source_kind,
        "metadata": metadata,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "_bytes": bytes(data),
    }
    st.session_state[LOCAL_FILES][file_id] = row
    return row


def save_generated_report(
    project_id: str,
    module: str,
    report_type: str,
    file_name: str,
    data: bytes,
    *,
    mime_type: str,
    version: int = 1,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    file_row = upload_project_file(
        project_id,
        module,
        file_name,
        data,
        mime_type=mime_type,
        source_kind="generated_report",
        metadata=metadata,
    )
    if persistence_mode() == "supabase":
        user = current_user()
        report = get_client().table("reports").insert({
            "user_id": user.id,
            "project_id": project_id,
            "module": module,
            "report_type": report_type,
            "version": int(version),
            "file_id": file_row["id"],
            "storage_path": file_row["storage_path"],
            "metadata": metadata or {},
        }).execute().data[0]
        return report
    return {**file_row, "report_type": report_type, "version": int(version)}


def list_project_files(project_id: str, module: Optional[str] = None) -> list[dict[str, Any]]:
    if persistence_mode() == "supabase":
        user = current_user()
        query = (
            get_client().table("project_files")
            .select("*")
            .eq("project_id", project_id)
            .eq("user_id", user.id)
        )
        if module:
            query = query.eq("module", module)
        return query.order("created_at", desc=True).execute().data or []

    _local_init()
    rows = [r for r in st.session_state[LOCAL_FILES].values() if r["project_id"] == project_id]
    if module:
        rows = [r for r in rows if r["module"] == module]
    return sorted(rows, key=lambda x: x.get("created_at", ""), reverse=True)


def download_project_file(file_row: dict[str, Any]) -> bytes:
    path = file_row.get("storage_path", "")
    if persistence_mode() == "supabase":
        return bytes(get_client().storage.from_(storage_bucket()).download(path))
    _local_init()
    file_id = str(file_row.get("id", ""))
    row = st.session_state[LOCAL_FILES].get(file_id)
    if not row:
        raise FileNotFoundError("Session-only file is no longer available.")
    return row["_bytes"]
