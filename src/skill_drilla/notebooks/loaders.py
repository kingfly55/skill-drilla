"""Notebook-friendly loaders for canonical chat analysis artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Iterator


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))



def iter_jsonl(path: str | Path) -> Iterator[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)



def load_inventory(path: str | Path) -> list[dict[str, Any]]:
    return list(iter_jsonl(path))



def load_parse_diagnostics(path: str | Path) -> dict[str, Any]:
    return read_json(path)



def load_validation_summary(path: str | Path) -> dict[str, Any]:
    return read_json(path)



def load_normalization_diagnostics(path: str | Path) -> dict[str, Any]:
    return read_json(path)



def load_semantic_run(path: str | Path) -> dict[str, Any]:
    return read_json(path)



def load_evidence(path: str | Path, *, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in iter_jsonl(path):
        rows.append(row)
        if limit is not None and len(rows) >= limit:
            break
    return rows



def load_corpus_view(view_dir: str | Path, *, limit: int | None = None) -> dict[str, Any]:
    root = Path(view_dir)
    summary = read_json(root / "view_summary.json")
    rows = load_evidence(root / "corpus_view.jsonl", limit=limit)
    return {
        "view_name": summary["view_name"],
        "summary": summary,
        "rows": rows,
    }



def load_seed_run(path: str | Path) -> dict[str, Any]:
    return read_json(path)



def load_detector_run(path: str | Path) -> dict[str, Any]:
    return read_json(path)



def load_report_metadata(path: str | Path) -> dict[str, Any]:
    return read_json(path)



def collect_evidence_by_status(evidence_rows: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in evidence_rows:
        grouped.setdefault(row.get("inclusion_status", "unknown"), []).append(row)
    return dict(sorted(grouped.items(), key=lambda item: item[0]))



def recurrence_snapshot(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    evidence_ids: set[str] = set()
    project_ids: set[str] = set()
    session_ids: set[str] = set()
    raw_occurrences = 0
    for row in records:
        raw_occurrences += 1
        evidence_id = row.get("evidence_id")
        if evidence_id is not None:
            evidence_ids.add(str(evidence_id))
        project_id = row.get("project_id")
        if project_id is not None:
            project_ids.add(str(project_id))
        session_id = row.get("session_id")
        if session_id is not None:
            session_ids.add(str(session_id))
    return {
        "raw_occurrences": raw_occurrences,
        "distinct_evidence": len(evidence_ids),
        "distinct_projects": len(project_ids),
        "distinct_sessions": len(session_ids),
    }
