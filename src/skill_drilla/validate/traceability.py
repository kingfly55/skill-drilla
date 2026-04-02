"""Traceability helpers for validation runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from skill_drilla.normalize.model import build_raw_event_id
from skill_drilla.parse.raw_events import RawEvent


def load_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def build_traceability_samples(
    *,
    report_metadata_path: str | Path,
    detector_run_paths: Iterable[str | Path],
    evidence_path: str | Path,
    raw_events_path: str | Path,
    limit: int = 10,
) -> list[dict[str, Any]]:
    metadata = load_json(report_metadata_path)
    detector_runs = {str(Path(path)): load_json(path) for path in detector_run_paths}
    evidence_by_id = {row["evidence_id"]: row for row in load_jsonl(evidence_path)}
    raw_events_by_id = {_build_raw_event_lookup_key(row): row for row in load_jsonl(raw_events_path)}

    samples: list[dict[str, Any]] = []
    for section in metadata.get("sections", []):
        detector_path = _find_detector_path(metadata, section.get("detector"), section.get("finding_id"))
        if detector_path is None:
            continue
        detector_run = detector_runs.get(detector_path)
        if detector_run is None:
            continue
        finding = next((item for item in detector_run.get("findings", []) if item.get("finding_id") == section.get("finding_id")), None)
        if finding is None:
            continue
        for evidence_ref in finding.get("evidence", []):
            evidence = evidence_by_id.get(evidence_ref.get("evidence_id"))
            if evidence is None:
                continue
            raw_event = raw_events_by_id.get(evidence.get("raw_event_id"))
            if raw_event is None:
                continue
            samples.append(
                {
                    "report_section": section.get("section_id"),
                    "report_heading": section.get("heading"),
                    "detector_run": detector_path,
                    "detector": section.get("detector"),
                    "finding_id": section.get("finding_id"),
                    "evidence_id": evidence.get("evidence_id"),
                    "raw_event_id": evidence.get("raw_event_id"),
                    "source_file": evidence.get("source_file"),
                    "source_line": evidence.get("source_line"),
                    "source_anchor": f"{evidence.get('source_file')}:{evidence.get('source_line')}",
                    "project_slug": evidence.get("project_slug"),
                    "session_id": evidence.get("session_id"),
                    "semantic_class": evidence.get("semantic_class"),
                    "record_type": raw_event.get("record_type"),
                    "parse_status": raw_event.get("parse_status"),
                    "excerpt": evidence_ref.get("excerpt") or evidence.get("content_text"),
                }
            )
            if len(samples) >= limit:
                return samples
    if samples:
        return samples
    fallback_evidence = next(iter(evidence_by_id.values()), None)
    if fallback_evidence is None:
        return []
    raw_event = raw_events_by_id.get(fallback_evidence.get("raw_event_id"))
    if raw_event is None:
        return []
    fallback_detector_run = next((run.get("path") for run in metadata.get("source_detector_runs", []) if run.get("path")), None)
    return [
        {
            "report_section": "unranked-fallback",
            "report_heading": "No ranked findings available",
            "detector_run": fallback_detector_run,
            "detector": None,
            "finding_id": "unavailable",
            "evidence_id": fallback_evidence.get("evidence_id"),
            "raw_event_id": fallback_evidence.get("raw_event_id"),
            "source_file": fallback_evidence.get("source_file"),
            "source_line": fallback_evidence.get("source_line"),
            "source_anchor": f"{fallback_evidence.get('source_file')}:{fallback_evidence.get('source_line')}",
            "project_slug": fallback_evidence.get("project_slug"),
            "session_id": fallback_evidence.get("session_id"),
            "semantic_class": fallback_evidence.get("semantic_class"),
            "record_type": raw_event.get("record_type"),
            "parse_status": raw_event.get("parse_status"),
            "excerpt": fallback_evidence.get("content_text"),
        }
    ]


def write_traceability_samples(output_path: str | Path, samples: list[dict[str, Any]]) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(samples, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _find_detector_path(metadata: dict[str, Any], detector: str | None, finding_id: str | None) -> str | None:
    for run in metadata.get("source_detector_runs", []):
        if run.get("detector") == detector and run.get("path"):
            return str(run["path"])
    if metadata.get("source_detector_runs"):
        return metadata["source_detector_runs"][0].get("path")
    return None


def _build_raw_event_lookup_key(row: dict[str, Any]) -> str:
    raw_event_id = row.get("raw_event_id")
    if raw_event_id is not None:
        return str(raw_event_id)
    event = RawEvent(**row)
    return build_raw_event_id(event)
