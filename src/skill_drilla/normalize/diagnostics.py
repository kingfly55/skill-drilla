"""Diagnostics aggregation for normalization outputs."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from skill_drilla.normalize.model import EvidenceRecord, TransformOutcome


@dataclass
class NormalizationDiagnosticsAccumulator:
    semantic_class_counts: Counter[str] = field(default_factory=Counter)
    inclusion_status_counts: Counter[str] = field(default_factory=Counter)
    inclusion_rationale_counts: Counter[str] = field(default_factory=Counter)
    transform_outcome_counts: Counter[str] = field(default_factory=Counter)
    ambiguous_items: list[dict[str, Any]] = field(default_factory=list)
    zero_evidence_events: int = 0
    multi_evidence_events: int = 0
    total_events: int = 0
    total_evidence: int = 0
    transform_outcomes: list[dict[str, Any]] = field(default_factory=list)

    def add(self, outcome: TransformOutcome, evidence_records: Iterable[EvidenceRecord]) -> None:
        records = tuple(evidence_records)
        self.total_events += 1
        self.total_evidence += len(records)
        self.transform_outcome_counts[outcome.outcome] += 1
        if len(records) == 0:
            self.zero_evidence_events += 1
        if len(records) > 1:
            self.multi_evidence_events += 1
        self.transform_outcomes.append(outcome.to_dict())
        for record in records:
            self.semantic_class_counts[record.semantic_class] += 1
            self.inclusion_status_counts[record.inclusion_status] += 1
            self.inclusion_rationale_counts[record.inclusion_rationale] += 1
            if record.inclusion_status == "ambiguous" or record.semantic_class == "unknown_ambiguous":
                self.ambiguous_items.append(
                    {
                        "evidence_id": record.evidence_id,
                        "raw_event_id": record.raw_event_id,
                        "semantic_class": record.semantic_class,
                        "ambiguity_reason": record.ambiguity_reason,
                        "source_file": record.source_file,
                        "source_line": record.source_line,
                    }
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_events": self.total_events,
            "total_evidence": self.total_evidence,
            "zero_evidence_events": self.zero_evidence_events,
            "multi_evidence_events": self.multi_evidence_events,
            "semantic_class_counts": dict(sorted(self.semantic_class_counts.items())),
            "inclusion_status_counts": dict(sorted(self.inclusion_status_counts.items())),
            "inclusion_rationale_counts": dict(sorted(self.inclusion_rationale_counts.items())),
            "transform_outcome_counts": dict(sorted(self.transform_outcome_counts.items())),
            "ambiguous_items": self.ambiguous_items,
            "transform_outcomes": self.transform_outcomes,
        }


def write_normalization_diagnostics(output_path: Path, diagnostics: NormalizationDiagnosticsAccumulator) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(diagnostics.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path
