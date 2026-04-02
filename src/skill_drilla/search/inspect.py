"""Inspection helpers for non-interactive evidence drill-down."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .index import InspectionResult, inspect_evidence


def inspect_evidence_record(view_dir: str | Path, evidence_id: str, *, context: int = 2) -> dict[str, Any]:
    result: InspectionResult = inspect_evidence(Path(view_dir), evidence_id, context=context)
    return result.to_dict()
