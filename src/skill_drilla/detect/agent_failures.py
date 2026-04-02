"""Detector for agent-level failure or reliability issues."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping

from .base import BaseDetector, FindingCandidate, canonicalize_text

FAILURE_MARKERS = (
    "failed", "error", "quota", "429", "interrupted", "network unreachable", "retry", "not load", "doesn't work", "doesnt work",
)


class AgentFailuresDetector(BaseDetector):
    detector_name = "agent_failures"
    category = "agent_failures"
    version = "1.0"
    default_settings = {
        "min_raw_occurrences": 1,
        "min_distinct_sessions": 1,
    }

    def iter_candidates(self, rows: Iterable[dict[str, object]], settings: Mapping[str, object]):
        grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            text = canonicalize_text(row["evidence"].get("content_text"))
            matched = tuple(marker for marker in FAILURE_MARKERS if marker in text)
            if not matched:
                continue
            key = "failure:" + matched[0]
            grouped[key].append(row)

        for key, matched_rows in grouped.items():
            yield FindingCandidate(
                key=key,
                category=self.category,
                title=f"Agent failure signal: {key.split(':', 1)[1]}",
                summary=f"Messages capture recurring failure or reliability symptoms linked to agent execution ({len(matched_rows)} mentions).",
                rows=tuple(matched_rows),
                diagnostics={"heuristic": "failure-marker", "marker": key.split(':', 1)[1]},
            )
