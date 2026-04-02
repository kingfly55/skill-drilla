"""Detector for corrections, pushback, and frustration signals."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping

from .base import BaseDetector, FindingCandidate, canonicalize_text

FRUSTRATION_MARKERS = (
    "wrong", "not working", "didn't", "didnt", "why did", "debug why", "retry", "issue", "problem", "broken", "failed",
)


class CorrectionsFrustrationsDetector(BaseDetector):
    detector_name = "corrections_frustrations"
    category = "corrections_frustrations"
    version = "1.0"
    default_settings = {
        "min_raw_occurrences": 1,
        "min_distinct_sessions": 1,
    }

    def iter_candidates(self, rows: Iterable[dict[str, object]], settings: Mapping[str, object]):
        grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            text = canonicalize_text(row["evidence"].get("content_text"))
            matched = tuple(marker for marker in FRUSTRATION_MARKERS if marker in text)
            if not matched:
                continue
            key = "correction:" + matched[0]
            grouped[key].append(row)

        for key, matched_rows in grouped.items():
            yield FindingCandidate(
                key=key,
                category=self.category,
                title=f"Correction/frustration pattern: {key.split(':', 1)[1]}",
                summary=f"User language shows recurring correction or frustration cues for this issue family ({len(matched_rows)} messages).",
                rows=tuple(matched_rows),
                diagnostics={"heuristic": "frustration-marker", "marker": key.split(':', 1)[1]},
            )
