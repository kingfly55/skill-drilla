"""Normalization layer for canonical evidence generation."""

from skill_drilla.normalize.classifier import ClassificationDecision, classify_content_block, classify_raw_event
from skill_drilla.normalize.diagnostics import (
    NormalizationDiagnosticsAccumulator,
    write_normalization_diagnostics,
)
from skill_drilla.normalize.model import (
    EvidenceRecord,
    INCLUSION_RATIONALES,
    INCLUSION_STATUSES,
    NormalizationBundle,
    SEMANTIC_CLASSES,
    TransformOutcome,
    build_evidence_id,
    build_raw_event_id,
    make_evidence_record,
)
from skill_drilla.normalize.transform import iter_normalized_evidence, normalize_event, write_normalize_artifacts

__all__ = [
    "ClassificationDecision",
    "EvidenceRecord",
    "INCLUSION_RATIONALES",
    "INCLUSION_STATUSES",
    "NormalizationBundle",
    "NormalizationDiagnosticsAccumulator",
    "SEMANTIC_CLASSES",
    "TransformOutcome",
    "build_evidence_id",
    "build_raw_event_id",
    "classify_content_block",
    "classify_raw_event",
    "iter_normalized_evidence",
    "make_evidence_record",
    "normalize_event",
    "write_normalization_diagnostics",
    "write_normalize_artifacts",
]
