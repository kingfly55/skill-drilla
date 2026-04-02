"""Detector for repeated change requests and refinement-through-change language."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping

from .base import BaseDetector, FindingCandidate, canonicalize_text, extract_keywords

CHANGE_TOKENS = {"change", "update", "modify", "revise", "redo", "adjust", "tweak", "refine"}


class ChangeRequestsDetector(BaseDetector):
    detector_name = "change_requests"
    category = "change_requests"
    version = "1.0"
    default_settings = {
        "min_raw_occurrences": 2,
        "min_distinct_sessions": 1,
    }

    def iter_candidates(self, rows: Iterable[dict[str, object]], settings: Mapping[str, object]):
        grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            text = row["evidence"].get("content_text")
            canonical = canonicalize_text(text)
            keywords = extract_keywords(text)
            if not any(token in keywords for token in CHANGE_TOKENS):
                continue
            focus = tuple(token for token in keywords if token not in CHANGE_TOKENS)[:4]
            key = "change-request:" + (" ".join(focus) if focus else canonical[:80])
            grouped[key].append(row)

        for key, matched_rows in grouped.items():
            yield FindingCandidate(
                key=key,
                category=self.category,
                title=f"Repeated change request cluster: {key.split(':', 1)[1][:64]}",
                summary=f"User asks for revisions or updates around the same focus area in {len(matched_rows)} messages.",
                rows=tuple(matched_rows),
                diagnostics={
                    "heuristic": "change-request-keyword-cluster",
                    "cluster_key": key,
                },
                caveats=("Keyword clustering may merge nearby but not identical revision intents.",),
            )
