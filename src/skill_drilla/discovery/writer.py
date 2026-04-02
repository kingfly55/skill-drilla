"""Artifact writing helpers for discovery outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skill_drilla.discovery.inventory import DiscoverySummary, InventoryRecord, inventory_jsonl_lines
from skill_drilla.discovery.scoping import ScopedInventory


def write_discovery_artifacts(
    output_dir: Path,
    *,
    records: tuple[InventoryRecord, ...],
    scoped: ScopedInventory,
    summary: DiscoverySummary,
    project_count: int,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    inventory_path = output_dir / "session_inventory.jsonl"
    scoped_path = output_dir / "scoped_session_inventory.jsonl"
    summary_path = output_dir / "inventory_summary.json"

    inventory_path.write_text("\n".join(inventory_jsonl_lines(records)) + "\n", encoding="utf-8")
    scoped_path.write_text("\n".join(inventory_jsonl_lines(scoped.records)) + "\n", encoding="utf-8")

    payload: dict[str, Any] = summary.to_dict()
    payload["projects"] = project_count
    payload["scoped_sessions"] = len(scoped.records)
    payload["excluded_sessions"] = len(scoped.excluded_records)
    payload["exclusion_reasons"] = scoped.exclusion_reasons
    summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return {
        "output_dir": str(output_dir),
        "session_inventory": str(inventory_path),
        "scoped_session_inventory": str(scoped_path),
        "inventory_summary": str(summary_path),
    }
