"""Detector for recurring workflow-oriented requests."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping

from .base import BaseDetector, FindingCandidate, extract_keywords

WORKFLOW_TERMS = {
    "workflow", "pipeline", "milestone", "plan", "verify", "verification", "test", "tests", "commit", "branch",
    "cli", "integration", "report", "artifact", "build", "deploy",
}


class WorkflowPatternsDetector(BaseDetector):
    detector_name = "workflow_patterns"
    category = "workflow_patterns"
    version = "1.0"
    default_settings = {
        "min_raw_occurrences": 2,
        "min_distinct_sessions": 1,
    }

    def iter_candidates(self, rows: Iterable[dict[str, object]], settings: Mapping[str, object]):
        grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            keywords = extract_keywords(row["evidence"].get("content_text"))
            workflow_hits = tuple(token for token in keywords if token in WORKFLOW_TERMS)
            if len(workflow_hits) < 2:
                continue
            key = "workflow:" + " ".join(sorted(set(workflow_hits))[:5])
            grouped[key].append(row)

        for key, matched_rows in grouped.items():
            yield FindingCandidate(
                key=key,
                category=self.category,
                title=f"Workflow pattern: {key.split(':', 1)[1]}",
                summary=f"Messages repeatedly describe the same workflow mechanics or execution shape ({len(matched_rows)} supporting messages).",
                rows=tuple(matched_rows),
                diagnostics={"heuristic": "workflow-keyword-overlap", "cluster_key": key},
            )
