"""Canonical normalized evidence models for the normalization layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from skill_drilla.contracts.ids import stable_id
from skill_drilla.discovery.inventory import InventoryRecord
from skill_drilla.parse.raw_events import RawEvent

SEMANTIC_CLASSES = (
    "user_natural_language",
    "assistant_natural_language",
    "tool_call",
    "tool_result",
    "thinking",
    "protocol_meta",
    "system_operational",
    "snapshot_state",
    "unknown_ambiguous",
)

INCLUSION_STATUSES = (
    "included_primary",
    "included_secondary",
    "excluded_default",
    "ambiguous",
)

INCLUSION_RATIONALES = (
    "user_primary_natural_language",
    "assistant_secondary_natural_language",
    "tooling_context_only",
    "thinking_not_analysis_text",
    "protocol_or_meta_chatter",
    "system_or_operational_record",
    "snapshot_or_state_record",
    "unknown_or_ambiguous_record",
)


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    project_id: str
    project_slug: str
    session_id: str
    session_key: str
    session_role: str
    root_session_id: str | None
    parent_session_id: str | None
    lineage_state: str
    subagent_id: str | None
    raw_event_id: str
    raw_event_index: int
    source_file: str
    source_line: int
    semantic_class: str
    inclusion_status: str
    inclusion_rationale: str
    producer_role: str | None
    content_text: str | None
    content_format: str
    content_block_index: int | None
    content_block_type: str | None
    tool_name: str | None = None
    tool_use_id: str | None = None
    is_error: bool | None = None
    parse_status: str = "parsed"
    record_type: str | None = None
    message_role: str | None = None
    is_sidechain: bool | None = None
    ambiguity_reason: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "project_id": self.project_id,
            "project_slug": self.project_slug,
            "session_id": self.session_id,
            "session_key": self.session_key,
            "session_role": self.session_role,
            "root_session_id": self.root_session_id,
            "parent_session_id": self.parent_session_id,
            "lineage_state": self.lineage_state,
            "subagent_id": self.subagent_id,
            "raw_event_id": self.raw_event_id,
            "raw_event_index": self.raw_event_index,
            "source_file": self.source_file,
            "source_line": self.source_line,
            "semantic_class": self.semantic_class,
            "inclusion_status": self.inclusion_status,
            "inclusion_rationale": self.inclusion_rationale,
            "producer_role": self.producer_role,
            "content_text": self.content_text,
            "content_format": self.content_format,
            "content_block_index": self.content_block_index,
            "content_block_type": self.content_block_type,
            "tool_name": self.tool_name,
            "tool_use_id": self.tool_use_id,
            "is_error": self.is_error,
            "parse_status": self.parse_status,
            "record_type": self.record_type,
            "message_role": self.message_role,
            "is_sidechain": self.is_sidechain,
            "ambiguity_reason": self.ambiguity_reason,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class TransformOutcome:
    raw_event_id: str
    raw_event_index: int
    source_file: str
    source_line: int
    evidence_count: int
    outcome: str
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_event_id": self.raw_event_id,
            "raw_event_index": self.raw_event_index,
            "source_file": self.source_file,
            "source_line": self.source_line,
            "evidence_count": self.evidence_count,
            "outcome": self.outcome,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class NormalizationBundle:
    evidence: tuple[EvidenceRecord, ...]
    outcome: TransformOutcome


def build_raw_event_id(event: RawEvent) -> str:
    return stable_id(
        "raw-event",
        event.project_id,
        event.session_id,
        str(event.event_index),
        str(event.source_line),
    )


def build_evidence_id(raw_event_id: str, semantic_class: str, block_index: int | None, ordinal: int) -> str:
    return stable_id(
        "evidence",
        raw_event_id,
        semantic_class,
        "none" if block_index is None else str(block_index),
        str(ordinal),
    )


def make_evidence_record(
    *,
    inventory: InventoryRecord,
    event: RawEvent,
    raw_event_id: str,
    semantic_class: str,
    inclusion_status: str,
    inclusion_rationale: str,
    producer_role: str | None,
    content_text: str | None,
    content_format: str,
    content_block_index: int | None,
    content_block_type: str | None,
    ordinal: int,
    tool_name: str | None = None,
    tool_use_id: str | None = None,
    is_error: bool | None = None,
    ambiguity_reason: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=build_evidence_id(raw_event_id, semantic_class, content_block_index, ordinal),
        project_id=inventory.project_id,
        project_slug=inventory.project_slug,
        session_id=inventory.session_id,
        session_key=inventory.session_key,
        session_role=inventory.session_role,
        root_session_id=inventory.root_session_id,
        parent_session_id=inventory.parent_session_id,
        lineage_state=inventory.lineage_state,
        subagent_id=inventory.subagent_id,
        raw_event_id=raw_event_id,
        raw_event_index=event.event_index,
        source_file=event.source_file,
        source_line=event.source_line,
        semantic_class=semantic_class,
        inclusion_status=inclusion_status,
        inclusion_rationale=inclusion_rationale,
        producer_role=producer_role,
        content_text=content_text,
        content_format=content_format,
        content_block_index=content_block_index,
        content_block_type=content_block_type,
        tool_name=tool_name,
        tool_use_id=tool_use_id,
        is_error=is_error,
        parse_status=event.parse_status,
        record_type=event.record_type,
        message_role=event.message_role,
        is_sidechain=event.is_sidechain,
        ambiguity_reason=ambiguity_reason,
        metadata=metadata or {},
    )
