"""Recurrence accounting utilities for corpus views."""

from __future__ import annotations

from typing import Iterable

RECURRENCE_BASIS_DEFAULT = {
    "raw_occurrences": "count every included view row",
    "distinct_evidence": "count unique evidence_id values",
    "distinct_sessions": "count unique session_id values",
    "distinct_projects": "count unique project_id values",
}


def compute_recurrence_counts(records: Iterable[dict[str, object]]) -> dict[str, int]:
    rows = list(records)
    return {
        "raw_occurrences": len(rows),
        "distinct_evidence": len({record["evidence_id"] for record in rows}),
        "distinct_sessions": len({record["session_id"] for record in rows}),
        "distinct_projects": len({record["project_id"] for record in rows}),
    }
