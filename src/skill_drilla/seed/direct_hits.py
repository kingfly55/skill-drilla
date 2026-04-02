"""Direct seed-term hit collection over materialized corpus views."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from skill_drilla.search import ParsedQuery, parse_query
from skill_drilla.views import compute_recurrence_counts


@dataclass(frozen=True)
class DirectHit:
    evidence_id: str
    session_id: str
    project_id: str
    project_slug: str
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
            "project_id": self.project_id,
            "project_slug": self.project_slug,
            "session_role": self.session_role,
            "source_file": self.source_file,
            "source_line": self.source_line,
            "source_anchor": self.source_anchor,
            "content_text": self.content_text,
            "matched_terms": list(self.matched_terms),
        }


@dataclass(frozen=True)
class DirectHitRun:
    seed_term: str
    parsed_query: dict[str, Any]
    recurrence: dict[str, int]
    related_sessions: list[dict[str, Any]]
    hits: tuple[DirectHit, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed_term": self.seed_term,
            "parsed_query": self.parsed_query,
            "recurrence": self.recurrence,
            "related_sessions": self.related_sessions,
            "hits": [hit.to_dict() for hit in self.hits],
        }


def iter_view_rows(view_dir: Path) -> Iterator[dict[str, Any]]:
    with (view_dir / "corpus_view.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def collect_direct_hits(view_dir: Path, seed_term: str) -> DirectHitRun:
    parsed = parse_query(f'"{seed_term}"' if " " in seed_term.strip() else seed_term)
    matched_rows: list[dict[str, Any]] = []
    for row in iter_view_rows(view_dir):
        evidence = row["evidence"]
        if parsed.matches(evidence.get("content_text")):
            matched_rows.append(row)

    hits = tuple(_build_direct_hit(row, parsed) for row in matched_rows)
    recurrence = compute_recurrence_counts(row["evidence"] for row in matched_rows)
    return DirectHitRun(
        seed_term=seed_term,
        parsed_query=parsed.to_dict(),
        recurrence=recurrence,
        related_sessions=_build_related_sessions(matched_rows),
        hits=hits,
    )


def _build_direct_hit(row: dict[str, Any], parsed: ParsedQuery) -> DirectHit:
    evidence = row["evidence"]
    inspection = row["inspection"]
    text = evidence.get("content_text")
    matched_terms = tuple(term.value for term in parsed.terms if term.value.casefold() in (text or "").casefold())
    return DirectHit(
        evidence_id=evidence["evidence_id"],
        session_id=evidence["session_id"],
        project_id=evidence["project_id"],
        project_slug=evidence["project_slug"],
        session_role=evidence.get("session_role"),
        source_file=inspection["source_file"],
        source_line=inspection["source_line"],
        source_anchor=inspection["source_anchor"],
        content_text=text,
        matched_terms=matched_terms,
    )


def _build_related_sessions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        evidence = row["evidence"]
        session_id = evidence["session_id"]
        payload = grouped.setdefault(
            session_id,
            {
                "session_id": session_id,
                "project_id": evidence["project_id"],
                "project_slug": evidence["project_slug"],
                "session_role": evidence.get("session_role"),
                "hit_count": 0,
                "evidence_ids": [],
                "source_anchors": [],
            },
        )
        payload["hit_count"] += 1
        payload["evidence_ids"].append(evidence["evidence_id"])
        payload["source_anchors"].append(row["inspection"]["source_anchor"])
    return sorted(grouped.values(), key=lambda item: (-item["hit_count"], item["session_id"]))
