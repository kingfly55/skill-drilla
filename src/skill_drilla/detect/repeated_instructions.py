"""Detector for recurring user instructions across sessions."""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Mapping

from .base import BaseDetector, FindingCandidate, canonicalize_text, is_instruction_like


class RepeatedInstructionsDetector(BaseDetector):
    detector_name = "repeated_instructions"
    category = "repeated_instructions"
    version = "1.0"
    default_settings = {
        "min_raw_occurrences": 2,
        "min_distinct_sessions": 2,
    }

    def iter_candidates(self, rows: Iterable[dict[str, object]], settings: Mapping[str, object]):
        grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
        for row in rows:
            text = row["evidence"].get("content_text")
            canonical = canonicalize_text(text)
            if not canonical or not is_instruction_like(text):
                continue
            grouped[canonical].append(row)

        for canonical, matched_rows in grouped.items():
            if len(matched_rows) < int(settings["min_raw_occurrences"]):
                continue
            yield FindingCandidate(
                key=canonical,
                category=self.category,
                title=f"Repeated instruction: {canonical[:72]}",
                summary=f"The same normalized instruction recurs {len(matched_rows)} times in the selected view.",
                rows=tuple(matched_rows),
                diagnostics={
                    "canonical_text": canonical,
                    "heuristic": "exact-normalized-instruction",
                },
                caveats=("Normalization is lexical and may miss paraphrases.",),
            )
