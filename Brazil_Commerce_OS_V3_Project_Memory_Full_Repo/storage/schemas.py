from __future__ import annotations

from dataclasses import dataclass
from typing import Any

MODULES = ("market", "operations", "marketing", "finance")
MODULE_LABELS = {
    "market": "Market Intelligence",
    "operations": "Business Operations & Localization",
    "marketing": "Creator & Campaign",
    "finance": "Finance & Performance",
}

MODULE_ORDER = {name: i for i, name in enumerate(MODULES, start=1)}
NEXT_MODULE = {
    "market": "operations",
    "operations": "marketing",
    "marketing": "finance",
    "finance": "finance",
}

VALID_PROJECT_STATUS = {"active", "paused", "completed", "archived"}
VALID_MODULE_STATUS = {"not_started", "in_progress", "completed", "blocked", "waiting_for_data"}


@dataclass
class ProjectContext:
    id: str
    project_name: str
    product_name: str = ""
    category: str = ""
    target_market: str = "Brazil"
    selected_platform: str = ""
    current_stage: str = "market"
    status: str = "active"
    notes: str = ""

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "ProjectContext":
        return cls(
            id=str(row.get("id", "")),
            project_name=str(row.get("project_name", "")),
            product_name=str(row.get("product_name") or ""),
            category=str(row.get("category") or ""),
            target_market=str(row.get("target_market") or "Brazil"),
            selected_platform=str(row.get("selected_platform") or ""),
            current_stage=str(row.get("current_stage") or "market"),
            status=str(row.get("status") or "active"),
            notes=str(row.get("notes") or ""),
        )
