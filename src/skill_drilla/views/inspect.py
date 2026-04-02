"""Inspection helpers for moving from view hits back to evidence provenance."""

from __future__ import annotations

from typing import Any


def build_inspection_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": record["evidence_id"],
        "session_id": record["session_id"],
        "source_file": record["source_file"],
        "source_line": record["source_line"],
        "source_anchor": f"{record['source_file']}:{record['source_line']}",
    }
