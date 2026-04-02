"""Machine-readable metadata builders for generated reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from skill_drilla.report.ranking import DEFAULT_RANKING_WEIGHTS, RankedFinding


def build_report_metadata(
    *,
    report_title: str,
    detector_runs: Iterable[Mapping[str, Any]],
    ranked_findings: Iterable[RankedFinding],
    report_scope: Mapping[str, Any],
    report_paths: Mapping[str, str],
    ranking_weights: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    ranked = list(ranked_findings)
    runs = [dict(run) for run in detector_runs]
    weights = {**DEFAULT_RANKING_WEIGHTS, **(ranking_weights or {})}
    source_detector_runs = [
        {
            "detector": run["detector"],
            "view_name": run["view_name"],
            "path": run.get("_source_path"),
            "finding_count": len(run.get("findings", [])),
            "diagnostics": run.get("diagnostics", {}),
            "settings": run.get("settings", {}),
        }
        for run in runs
    ]
    sections = [build_section_metadata(item) for item in ranked]
    return {
        "report_title": report_title,
        "report_scope": dict(report_scope),
        "source_detector_runs": source_detector_runs,
        "ranking_method": {
            "weights": weights,
            "primary_sort": [
                "distinct_sessions",
                "raw_occurrences",
                "distinct_projects",
                "distinct_evidence",
                "title",
            ],
            "description": "Rank findings by session spread first, then recurrence volume, then project spread and evidence volume.",
        },
        "sections": sections,
        "artifact_paths": dict(report_paths),
    }



def build_section_metadata(item: RankedFinding) -> dict[str, Any]:
    finding = item.finding
    evidence = list(finding.get("evidence", []))
    direct_user_evidence = [entry for entry in evidence if _is_direct_user_evidence(entry)]
    supporting_context = [entry for entry in evidence if not _is_direct_user_evidence(entry)]
    return {
        "section_id": f"finding-{item.rank}",
        "heading": finding["title"],
        "rank": item.rank,
        "finding_id": finding["finding_id"],
        "detector": finding["detector"],
        "category": finding["category"],
        "score": item.score,
        "recurrence": finding.get("recurrence", {}),
        "recurrence_basis": finding.get("recurrence_basis", {}),
        "evidence_ids": [entry["evidence_id"] for entry in evidence],
        "direct_user_evidence_ids": [entry["evidence_id"] for entry in direct_user_evidence],
        "supporting_context_ids": [entry["evidence_id"] for entry in supporting_context],
        "source_references": [
            {
                "evidence_id": entry["evidence_id"],
                "source_anchor": entry.get("source_anchor"),
                "source_file": entry.get("source_file"),
                "source_line": entry.get("source_line"),
                "project_slug": entry.get("project_slug"),
                "session_id": entry.get("session_id"),
            }
            for entry in evidence
        ],
        "detector_metadata": finding.get("detector_metadata", {}),
        "diagnostics": finding.get("diagnostics", {}),
        "caveats": finding.get("caveats", []),
        "ranking_factors": item.ranking_factors,
    }



def write_report_metadata(output_path: Path, metadata: Mapping[str, Any]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(dict(metadata), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path



def _is_direct_user_evidence(entry: Mapping[str, Any]) -> bool:
    return (entry.get("session_role") in {"root", None}) and str(entry.get("qualification", "")).startswith("Matched")
