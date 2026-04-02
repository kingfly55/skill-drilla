"""Detector for workflow refinement and system-management requests."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping

from .base import BaseDetector, FindingCandidate, extract_keywords

REFINEMENT_TERMS = {
    "hook", "hooks", "settings", "skill", "skills", "config", "configuration", "parameter", "detector",
    "view", "analysis", "pipeline", "framework", "system", "management", "subagent",
}


class RefinementRequestsDetector(BaseDetector):
    detector_name = "refinement_requests"
    category = "workflow_refinement_requests"
    version = "1.0"
    default_settings = {
        "min_raw_occurrences": 1,
        "min_distinct_sessions": 1,
    }

    def iter_candidates(self, rows: Iterable[dict[str, object]], settings: Mapping[str, object]):
        grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            keywords = extract_keywords(row["evidence"].get("content_text"))
            matched = tuple(token for token in keywords if token in REFINEMENT_TERMS)
            if len(matched) < 2:
                continue
            key = "refinement:" + " ".join(sorted(set(matched))[:5])
            grouped[key].append(row)

        for key, matched_rows in grouped.items():
            caveats = ()
            if any("analysis" in (row["evidence"].get("content_text") or "").lower() for row in matched_rows):
                caveats = ("Includes analysis-system-management friction or framework-tuning requests.",)
            yield FindingCandidate(
                key=key,
                category=self.category,
                title=f"Workflow refinement request: {key.split(':', 1)[1]}",
                summary=f"User requests configuration or workflow refinement around the same system surface in {len(matched_rows)} messages.",
                rows=tuple(matched_rows),
                diagnostics={"heuristic": "refinement-keyword-overlap", "cluster_key": key},
                caveats=caveats,
            )
