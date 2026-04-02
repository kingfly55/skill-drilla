"""Render human-readable Markdown reports from detector run artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from skill_drilla.report.metadata import build_report_metadata, write_report_metadata
from skill_drilla.report.ranking import RankedFinding, rank_findings


@dataclass(frozen=True)
class LoadedDetectorRun:
    path: Path
    payload: dict[str, Any]


@dataclass(frozen=True)
class ReportArtifacts:
    output_dir: Path
    report_path: Path
    metadata_path: Path
    report_title: str
    section_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "output_dir": str(self.output_dir),
            "report": str(self.report_path),
            "report_metadata": str(self.metadata_path),
            "report_title": self.report_title,
            "section_count": self.section_count,
        }



def load_detector_run(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["_source_path"] = str(path)
    return payload



def generate_report(
    detector_run_paths: Sequence[Path],
    *,
    output_dir: Path,
    view_names: Sequence[str] | None = None,
    detectors: Sequence[str] | None = None,
    title: str | None = None,
) -> ReportArtifacts:
    loaded_runs = [load_detector_run(path) for path in detector_run_paths]
    filtered_runs = _filter_runs(loaded_runs, view_names=view_names, detectors=detectors)
    findings = [finding for run in filtered_runs for finding in run.get("findings", [])]
    ranked = rank_findings(findings)

    report_title = title or _default_report_title(filtered_runs, ranked)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.md"
    metadata_path = output_dir / "report_metadata.json"

    report_scope = {
        "detectors": sorted({run["detector"] for run in filtered_runs}),
        "view_names": sorted({run["view_name"] for run in filtered_runs}),
        "detector_run_count": len(filtered_runs),
        "finding_count": len(ranked),
        "scoped": bool(view_names or detectors),
        "requested_views": list(view_names or []),
        "requested_detectors": list(detectors or []),
    }
    metadata = build_report_metadata(
        report_title=report_title,
        detector_runs=filtered_runs,
        ranked_findings=ranked,
        report_scope=report_scope,
        report_paths={
            "output_dir": str(output_dir),
            "report": str(report_path),
            "report_metadata": str(metadata_path),
        },
    )
    report_text = render_markdown_report(
        report_title=report_title,
        detector_runs=filtered_runs,
        ranked_findings=ranked,
        metadata=metadata,
    )
    report_path.write_text(report_text, encoding="utf-8")
    write_report_metadata(metadata_path, metadata)
    return ReportArtifacts(
        output_dir=output_dir,
        report_path=report_path,
        metadata_path=metadata_path,
        report_title=report_title,
        section_count=len(metadata["sections"]),
    )



def render_markdown_report(
    *,
    report_title: str,
    detector_runs: Sequence[Mapping[str, Any]],
    ranked_findings: Sequence[RankedFinding],
    metadata: Mapping[str, Any],
) -> str:
    lines: list[str] = [f"# {report_title}", ""]
    lines.extend(_render_scope_section(metadata))
    lines.extend(_render_findings_section(ranked_findings))
    lines.extend(_render_caveats_section(ranked_findings))
    lines.extend(_render_sources_section(detector_runs))
    return "\n".join(lines).rstrip() + "\n"



def _render_scope_section(metadata: Mapping[str, Any]) -> list[str]:
    scope = metadata["report_scope"]
    ranking = metadata["ranking_method"]
    return [
        "## Scope",
        "",
        f"- Detector runs included: {scope['detector_run_count']}",
        f"- Detectors: {', '.join(scope['detectors']) if scope['detectors'] else 'none'}",
        f"- Views: {', '.join(scope['view_names']) if scope['view_names'] else 'none'}",
        f"- Findings ranked: {scope['finding_count']}",
        f"- Scoped selection: {'yes' if scope['scoped'] else 'no'}",
        "- Ranking method: distinct session spread first, then raw recurrence, then project spread, then evidence volume.",
        f"- Ranking weights: {json.dumps(ranking['weights'], sort_keys=True)}",
        "",
    ]



def _render_findings_section(ranked_findings: Sequence[RankedFinding]) -> list[str]:
    lines = ["## Findings", ""]
    if not ranked_findings:
        return lines + ["No findings matched the selected report scope.", ""]
    for item in ranked_findings:
        finding = item.finding
        evidence = list(finding.get("evidence", []))
        direct_user = [entry for entry in evidence if _is_direct_user_evidence(entry)]
        supporting = [entry for entry in evidence if not _is_direct_user_evidence(entry)]
        lines.extend(
            [
                f"### {item.rank}. {finding['title']}",
                "",
                f"- Detector: {finding['detector']}",
                f"- Category: {finding['category']}",
                f"- Rank score: {item.score:.1f}",
                f"- Frequency: {finding['recurrence'].get('raw_occurrences', 0)} raw occurrences across {finding['recurrence'].get('distinct_sessions', 0)} sessions and {finding['recurrence'].get('distinct_projects', 0)} projects.",
                f"- Recurrence basis: raw_occurrences={finding['recurrence_basis'].get('raw_occurrences', 'n/a')}; distinct_sessions={finding['recurrence_basis'].get('distinct_sessions', 'n/a')}; distinct_projects={finding['recurrence_basis'].get('distinct_projects', 'n/a')}; distinct_evidence={finding['recurrence_basis'].get('distinct_evidence', 'n/a')}",
                f"- Description: {finding['summary']}",
                "",
                "#### Direct user-centered evidence",
                "",
            ]
        )
        if direct_user:
            for entry in direct_user[:3]:
                lines.append(_format_evidence_bullet(entry))
        else:
            lines.append("- No direct user-centered examples were identified in detector evidence; see supporting context.")
        lines.extend(["", "#### Supporting context", ""])
        if supporting:
            for entry in supporting[:3]:
                lines.append(_format_evidence_bullet(entry))
        else:
            lines.append("- No additional supporting context was attached to this finding.")
        lines.extend(["", "#### Source references", ""])
        for entry in evidence[:5]:
            lines.append(
                f"- `{entry['evidence_id']}` → `{entry.get('source_anchor')}` ({entry.get('project_slug')}, session {entry.get('session_id')})"
            )
        lines.extend(["", "#### Caveats", ""])
        caveats = finding.get("caveats", [])
        if caveats:
            for caveat in caveats:
                lines.append(f"- {caveat}")
        else:
            lines.append("- No detector-specific caveats recorded.")
        lines.append("")
    return lines



def _render_caveats_section(ranked_findings: Sequence[RankedFinding]) -> list[str]:
    caveats = sorted({caveat for item in ranked_findings for caveat in item.finding.get("caveats", [])})
    lines = ["## Caveats", ""]
    if caveats:
        lines.extend(f"- {caveat}" for caveat in caveats)
    else:
        lines.append("- No report-level caveats were emitted.")
    lines.append("")
    return lines



def _render_sources_section(detector_runs: Sequence[Mapping[str, Any]]) -> list[str]:
    lines = ["## Sources", ""]
    for run in detector_runs:
        lines.append(
            f"- Detector `{run['detector']}` on view `{run['view_name']}` from `{run.get('_source_path')}`"
        )
    lines.append("")
    return lines



def _format_evidence_bullet(entry: Mapping[str, Any]) -> str:
    excerpt = entry.get("excerpt") or "(no excerpt)"
    return (
        f"- `{entry['evidence_id']}` [{entry.get('project_slug')} / {entry.get('session_role') or 'unknown'}] "
        f"{excerpt} — source `{entry.get('source_anchor')}`"
    )



def _filter_runs(
    runs: Iterable[Mapping[str, Any]],
    *,
    view_names: Sequence[str] | None,
    detectors: Sequence[str] | None,
) -> list[dict[str, Any]]:
    allowed_views = set(view_names or [])
    allowed_detectors = set(detectors or [])
    filtered: list[dict[str, Any]] = []
    for run in runs:
        if allowed_views and run["view_name"] not in allowed_views:
            continue
        if allowed_detectors and run["detector"] not in allowed_detectors:
            continue
        filtered.append(dict(run))
    return filtered



def _default_report_title(runs: Sequence[Mapping[str, Any]], ranked_findings: Sequence[RankedFinding]) -> str:
    if len(runs) == 1:
        run = runs[0]
        return f"{run['detector'].replace('_', ' ').title()} report"
    if ranked_findings:
        return "Scoped detector findings report"
    return "Detector findings report"



def _is_direct_user_evidence(entry: Mapping[str, Any]) -> bool:
    return (entry.get("session_role") in {"root", None}) and str(entry.get("qualification", "")).startswith("Matched")
