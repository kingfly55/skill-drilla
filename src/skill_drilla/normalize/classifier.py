"""Semantic classification helpers for normalized evidence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ClassificationDecision:
    semantic_class: str
    inclusion_status: str
    inclusion_rationale: str
    ambiguity_reason: str | None = None


def classify_raw_event(event) -> ClassificationDecision:
    if event.parse_status != "parsed":
        return ClassificationDecision(
            semantic_class="unknown_ambiguous",
            inclusion_status="ambiguous",
            inclusion_rationale="unknown_or_ambiguous_record",
            ambiguity_reason=f"parse_status:{event.parse_status}",
        )

    record = event.raw_record or {}
    record_type = event.record_type
    if record_type == "file-history-snapshot":
        return ClassificationDecision("snapshot_state", "excluded_default", "snapshot_or_state_record")
    if record_type == "progress":
        return ClassificationDecision("system_operational", "excluded_default", "system_or_operational_record")
    if record_type == "system":
        subtype = record.get("subtype")
        if subtype in {"compact_boundary", "bridge_status"}:
            return ClassificationDecision("protocol_meta", "excluded_default", "protocol_or_meta_chatter")
        return ClassificationDecision("system_operational", "excluded_default", "system_or_operational_record")
    if record_type == "summary":
        return ClassificationDecision("protocol_meta", "excluded_default", "protocol_or_meta_chatter")

    if event.message_role == "assistant":
        return ClassificationDecision("assistant_natural_language", "included_secondary", "assistant_secondary_natural_language")
    if event.message_role == "user":
        if _is_tool_result_record(record):
            return ClassificationDecision("tool_result", "excluded_default", "tooling_context_only")
        if _is_meta_user_record(record):
            return ClassificationDecision("protocol_meta", "excluded_default", "protocol_or_meta_chatter")
        return ClassificationDecision("user_natural_language", "included_primary", "user_primary_natural_language")

    return ClassificationDecision(
        semantic_class="unknown_ambiguous",
        inclusion_status="ambiguous",
        inclusion_rationale="unknown_or_ambiguous_record",
        ambiguity_reason="unrecognized_record_shape",
    )


def classify_content_block(block: dict[str, Any], *, producer_role: str | None, default_decision: ClassificationDecision) -> ClassificationDecision:
    block_type = block.get("type")
    if block_type == "text":
        if producer_role == "assistant":
            return ClassificationDecision("assistant_natural_language", "included_secondary", "assistant_secondary_natural_language")
        return ClassificationDecision("user_natural_language", "included_primary", "user_primary_natural_language")
    if block_type == "tool_use":
        return ClassificationDecision("tool_call", "excluded_default", "tooling_context_only")
    if block_type == "tool_result":
        return ClassificationDecision("tool_result", "excluded_default", "tooling_context_only")
    if block_type in {"thinking", "redacted_thinking"}:
        return ClassificationDecision("thinking", "excluded_default", "thinking_not_analysis_text")
    return ClassificationDecision(
        semantic_class="unknown_ambiguous",
        inclusion_status="ambiguous",
        inclusion_rationale="unknown_or_ambiguous_record",
        ambiguity_reason=f"unknown_block_type:{block_type}",
    ) if block_type else default_decision


def _is_tool_result_record(record: dict[str, Any]) -> bool:
    message = record.get("message")
    if not isinstance(message, dict):
        return False
    content = message.get("content")
    if not isinstance(content, list):
        return False
    return any(isinstance(item, dict) and item.get("type") == "tool_result" for item in content)


def _is_meta_user_record(record: dict[str, Any]) -> bool:
    if record.get("isMeta") is True or record.get("isCompactSummary") is True or record.get("isVisibleInTranscriptOnly") is True:
        return True
    message = record.get("message")
    if not isinstance(message, dict):
        return False
    content = message.get("content")
    if isinstance(content, str):
        lowered = content.lower()
        return any(token in lowered for token in ("<local-command", "<command-name>", "<summary>", "[request interrupted by user]"))
    return False
