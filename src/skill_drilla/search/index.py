"""Search over materialized corpus view artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

from skill_drilla.views import compute_recurrence_counts

from .query import ParsedQuery, SearchFilters


@dataclass(frozen=True)
class SearchMatch:
    evidence_id: str
    session_id: str
    project_slug: str
    semantic_class: str | None
    session_role: str | None
    source_file: str
    source_line: int
    source_anchor: str
    content_text: str | None
    matched_terms: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "session_id": self.session_id,
            "project_slug": self.project_slug,
            "semantic_class": self.semantic_class,
            "session_role": self.session_role,
            "source_file": self.source_file,
            "source_line": self.source_line,
            "source_anchor": self.source_anchor,
            "content_text": self.content_text,
            "matched_terms": list(self.matched_terms),
        }


@dataclass(frozen=True)
class SearchResult:
    query: dict[str, Any]
    view_name: str
    view_metadata: dict[str, Any]
    filters: dict[str, Any]
    reproducibility: dict[str, Any]
    recurrence: dict[str, int]
    summary: dict[str, Any]
    matches: tuple[SearchMatch, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "view_name": self.view_name,
            "view_metadata": self.view_metadata,
            "filters": self.filters,
            "reproducibility": self.reproducibility,
            "recurrence": self.recurrence,
            "summary": self.summary,
            "matches": [match.to_dict() for match in self.matches],
        }


@dataclass(frozen=True)
class ViewArtifactSet:
    view_dir: Path
    corpus_view_path: Path
    summary_path: Path
    view_name: str
    view_summary: dict[str, Any]


@dataclass(frozen=True)
class InspectionResult:
    evidence_id: str
    view_name: str
    source_anchor: str
    row: dict[str, Any]
    context_before: tuple[dict[str, Any], ...]
    context_after: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "view_name": self.view_name,
            "source_anchor": self.source_anchor,
            "row": self.row,
            "context_before": list(self.context_before),
            "context_after": list(self.context_after),
        }


def load_view_artifacts(view_dir: Path) -> ViewArtifactSet:
    corpus_view_path = view_dir / "corpus_view.jsonl"
    summary_path = view_dir / "view_summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    return ViewArtifactSet(
        view_dir=view_dir,
        corpus_view_path=corpus_view_path,
        summary_path=summary_path,
        view_name=summary["view_name"],
        view_summary=summary,
    )


def iter_view_rows(corpus_view_path: Path) -> Iterator[dict[str, Any]]:
    with corpus_view_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def run_search(view_dir: Path, parsed_query: ParsedQuery, filters: SearchFilters) -> SearchResult:
    artifacts = load_view_artifacts(view_dir)
    matched_rows: list[dict[str, Any]] = []
    for row in iter_view_rows(artifacts.corpus_view_path):
        evidence = row["evidence"]
        if not filters.matches(evidence):
            continue
        if parsed_query.matches(evidence.get("content_text")):
            matched_rows.append(row)
            if filters.limit is not None and len(matched_rows) >= filters.limit:
                break

    matches = tuple(_build_match(row, parsed_query) for row in matched_rows)
    recurrence = compute_recurrence_counts(row["evidence"] for row in matched_rows)
    summary = {
        "total_matches": len(matches),
        "representative_examples": [match.to_dict() for match in matches[:3]],
        "distinct_projects": recurrence["distinct_projects"],
        "distinct_sessions": recurrence["distinct_sessions"],
    }
    reproducibility = {
        "view_dir": str(view_dir),
        "corpus_view_path": str(artifacts.corpus_view_path),
        "view_summary_path": str(artifacts.summary_path),
        "parsed_query": parsed_query.to_dict(),
        "filters": filters.to_dict(),
        "view_id": artifacts.view_summary.get("view_id"),
        "subagent_policy": artifacts.view_summary.get("subagent_policy"),
    }
    return SearchResult(
        query=parsed_query.to_dict(),
        view_name=artifacts.view_name,
        view_metadata={
            "view_id": artifacts.view_summary.get("view_id"),
            "source_evidence_path": artifacts.view_summary.get("source_evidence_path"),
            "subagent_policy": artifacts.view_summary.get("subagent_policy"),
            "filters": artifacts.view_summary.get("filters"),
            "recurrence_basis": artifacts.view_summary.get("recurrence_basis"),
        },
        filters=filters.to_dict(),
        reproducibility=reproducibility,
        recurrence=recurrence,
        summary=summary,
        matches=matches,
    )


def inspect_evidence(view_dir: Path, evidence_id: str, *, context: int = 2) -> InspectionResult:
    artifacts = load_view_artifacts(view_dir)
    rows = list(iter_view_rows(artifacts.corpus_view_path))
    for index, row in enumerate(rows):
        if row["evidence"]["evidence_id"] == evidence_id:
            start = max(0, index - context)
            end = min(len(rows), index + context + 1)
            return InspectionResult(
                evidence_id=evidence_id,
                view_name=artifacts.view_name,
                source_anchor=row["inspection"]["source_anchor"],
                row=row,
                context_before=tuple(rows[start:index]),
                context_after=tuple(rows[index + 1:end]),
            )
    raise ValueError(f"evidence_id not found in view: {evidence_id}")


def write_search_result(output_dir: Path, result: SearchResult) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    query_result_path = output_dir / "query_result.json"
    query_result_path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"output_dir": str(output_dir), "query_result": str(query_result_path)}


def _build_match(row: dict[str, Any], parsed_query: ParsedQuery) -> SearchMatch:
    evidence = row["evidence"]
    inspection = row["inspection"]
    text = evidence.get("content_text")
    matched_terms = tuple(
        term.value
        for term in parsed_query.terms
        if term.value.casefold() in (text or "").casefold()
    )
    return SearchMatch(
        evidence_id=evidence["evidence_id"],
        session_id=evidence["session_id"],
        project_slug=evidence["project_slug"],
        semantic_class=evidence.get("semantic_class"),
        session_role=evidence.get("session_role"),
        source_file=inspection["source_file"],
        source_line=inspection["source_line"],
        source_anchor=inspection["source_anchor"],
        content_text=text,
        matched_terms=matched_terms,
    )
