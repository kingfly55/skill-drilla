"""Detector for recurring output quality complaints or preferences."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping

from .base import BaseDetector, FindingCandidate, canonicalize_text

QUALITY_MARKERS = (
    "too verbose", "too long", "brief", "concise", "quality", "miss the mark", "format", "style", "wrong output", "bad pattern",
)


class OutputQualityDetector(BaseDetector):
    detector_name = "output_quality"
    category = "output_quality"
    version = "1.0"
    default_settings = {
        "min_raw_occurrences": 1,
        "min_distinct_sessions": 1,
    }

    def iter_candidates(self, rows: Iterable[dict[str, object]], settings: Mapping[str, object]):
        grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            text = canonicalize_text(row["evidence"].get("content_text"))
            matched = tuple(marker for marker in QUALITY_MARKERS if marker in text)
            if not matched:
                continue
            key = "output-quality:" + matched[0]
            grouped[key].append(row)

        for key, matched_rows in grouped.items():
            yield FindingCandidate(
                key=key,
                category=self.category,
                title=f"Output quality issue: {key.split(':', 1)[1]}",
                summary=f"User explicitly flags output-quality preferences or misses for this theme ({len(matched_rows)} examples).",
                rows=tuple(matched_rows),
                diagnostics={"heuristic": "quality-marker", "marker": key.split(':', 1)[1]},
            )
