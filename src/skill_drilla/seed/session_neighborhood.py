"""Session-neighborhood helpers for seed-term expansion workflows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SessionNeighborhoodRecord:
    evidence_id: str
    session_id: str
    project_id: str
    project_slug: str
    session_role: str | None
    source_file: str
    source_line: int
    source_anchor: str
    content_text: str | None
    distance: int
    relationship: str

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
            "distance": self.distance,
            "relationship": self.relationship,
        }


def collect_session_neighborhood(view_dir: Path, *, direct_hit_ids: set[str], direct_session_ids: set[str], window: int) -> dict[str, list[SessionNeighborhoodRecord]]:
    rows: list[dict[str, Any]] = []
    with (view_dir / "corpus_view.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))

    by_session: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        session_id = row["evidence"]["session_id"]
        by_session.setdefault(session_id, []).append(row)

    session_neighbors: dict[str, list[SessionNeighborhoodRecord]] = {}
    for session_id in direct_session_ids:
        ordered = by_session.get(session_id, [])
        direct_indexes = [i for i, row in enumerate(ordered) if row["evidence"]["evidence_id"] in direct_hit_ids]
        neighbors: list[SessionNeighborhoodRecord] = []
        seen: set[str] = set()
        for index in direct_indexes:
            start = max(0, index - window)
            end = min(len(ordered), index + window + 1)
            for neighbor_index in range(start, end):
                if neighbor_index == index:
                    continue
                row = ordered[neighbor_index]
                evidence = row["evidence"]
                evidence_id = evidence["evidence_id"]
                if evidence_id in direct_hit_ids or evidence_id in seen:
                    continue
                seen.add(evidence_id)
                inspection = row["inspection"]
                distance = abs(neighbor_index - index)
                neighbors.append(
                    SessionNeighborhoodRecord(
                        evidence_id=evidence_id,
                        session_id=session_id,
                        project_id=evidence["project_id"],
                        project_slug=evidence["project_slug"],
                        session_role=evidence.get("session_role"),
                        source_file=inspection["source_file"],
                        source_line=inspection["source_line"],
                        source_anchor=inspection["source_anchor"],
                        content_text=evidence.get("content_text"),
                        distance=distance,
                        relationship="session_neighbor",
                    )
                )
        session_neighbors[session_id] = sorted(neighbors, key=lambda item: (item.distance, item.source_line, item.evidence_id))
    return session_neighbors
