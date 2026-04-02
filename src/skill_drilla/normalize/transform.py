"""Transform raw events into canonical normalized evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Iterator

from skill_drilla.discovery.inventory import InventoryRecord
from skill_drilla.normalize.classifier import ClassificationDecision, classify_content_block, classify_raw_event
from skill_drilla.normalize.diagnostics import NormalizationDiagnosticsAccumulator, write_normalization_diagnostics
from skill_drilla.normalize.model import (
    NormalizationBundle,
    TransformOutcome,
    build_raw_event_id,
    make_evidence_record,
)
from skill_drilla.parse.raw_events import RawEvent


def normalize_event(inventory: InventoryRecord, event: RawEvent) -> NormalizationBundle:
    raw_event_id = build_raw_event_id(event)
    decision = classify_raw_event(event)
    record = event.raw_record or {}
    producer_role = event.message_role

    if event.parse_status != "parsed":
        evidence = (
            make_evidence_record(
                inventory=inventory,
                event=event,
                raw_event_id=raw_event_id,
                semantic_class=decision.semantic_class,
                inclusion_status=decision.inclusion_status,
                inclusion_rationale=decision.inclusion_rationale,
                producer_role=producer_role,
                content_text=None,
                content_format="none",
                content_block_index=None,
                content_block_type=None,
                ordinal=0,
                ambiguity_reason=decision.ambiguity_reason,
                metadata={"parse_error": event.parse_error},
            ),
        )
        return NormalizationBundle(evidence=evidence, outcome=TransformOutcome(raw_event_id, event.event_index, event.source_file, event.source_line, 1, "single_evidence", (decision.semantic_class,)))

    message = record.get("message")
    content = message.get("content") if isinstance(message, dict) else None

    if isinstance(content, list):
        evidence_records = []
        for block_index, block in enumerate(content):
            if not isinstance(block, dict):
                block_decision = ClassificationDecision("unknown_ambiguous", "ambiguous", "unknown_or_ambiguous_record", "non_object_block")
                text = str(block)
                block_type = None
            else:
                block_decision = classify_content_block(block, producer_role=producer_role, default_decision=decision)
                text = _extract_block_text(block)
                block_type = _maybe_string(block.get("type"))
            evidence_records.append(
                make_evidence_record(
                    inventory=inventory,
                    event=event,
                    raw_event_id=raw_event_id,
                    semantic_class=block_decision.semantic_class,
                    inclusion_status=block_decision.inclusion_status,
                    inclusion_rationale=block_decision.inclusion_rationale,
                    producer_role=producer_role,
                    content_text=text,
                    content_format="block",
                    content_block_index=block_index,
                    content_block_type=block_type,
                    ordinal=block_index,
                    tool_name=_maybe_string(block.get("name")) if isinstance(block, dict) else None,
                    tool_use_id=_maybe_string((block or {}).get("tool_use_id") if isinstance(block, dict) else None) or _maybe_string((block or {}).get("id") if isinstance(block, dict) else None),
                    is_error=_maybe_bool((block or {}).get("is_error") if isinstance(block, dict) else None),
                    ambiguity_reason=block_decision.ambiguity_reason,
                    metadata=_block_metadata(block) if isinstance(block, dict) else {},
                )
            )
        outcome_name = "multiple_evidence" if len(evidence_records) > 1 else "single_evidence"
        return NormalizationBundle(
            evidence=tuple(evidence_records),
            outcome=TransformOutcome(raw_event_id, event.event_index, event.source_file, event.source_line, len(evidence_records), outcome_name, tuple(r.semantic_class for r in evidence_records)),
        )

    if isinstance(content, str) or content is None:
        text = content if isinstance(content, str) else None
        evidence = (
            make_evidence_record(
                inventory=inventory,
                event=event,
                raw_event_id=raw_event_id,
                semantic_class=decision.semantic_class,
                inclusion_status=decision.inclusion_status,
                inclusion_rationale=decision.inclusion_rationale,
                producer_role=producer_role,
                content_text=text,
                content_format="string" if isinstance(content, str) else "none",
                content_block_index=None,
                content_block_type=None,
                ordinal=0,
                ambiguity_reason=decision.ambiguity_reason,
                metadata=_record_metadata(record),
            ),
        )
        return NormalizationBundle(evidence=evidence, outcome=TransformOutcome(raw_event_id, event.event_index, event.source_file, event.source_line, 1, "single_evidence", (decision.semantic_class,)))

    evidence = (
        make_evidence_record(
            inventory=inventory,
            event=event,
            raw_event_id=raw_event_id,
            semantic_class="unknown_ambiguous",
            inclusion_status="ambiguous",
            inclusion_rationale="unknown_or_ambiguous_record",
            producer_role=producer_role,
            content_text=str(content),
            content_format=type(content).__name__,
            content_block_index=None,
            content_block_type=None,
            ordinal=0,
            ambiguity_reason="unsupported_message_content_shape",
            metadata=_record_metadata(record),
        ),
    )
    return NormalizationBundle(evidence=evidence, outcome=TransformOutcome(raw_event_id, event.event_index, event.source_file, event.source_line, 1, "single_evidence", ("unknown_ambiguous",)))


def write_normalize_artifacts(
    output_dir: Path,
    inventory_records: Iterable[InventoryRecord],
    raw_events: Iterable[RawEvent],
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    evidence_path = output_dir / "evidence.jsonl"
    diagnostics_path = output_dir / "normalization_diagnostics.json"

    inventory_by_session = {record.session_id: record for record in inventory_records}
    diagnostics = NormalizationDiagnosticsAccumulator()
    with evidence_path.open("w", encoding="utf-8") as handle:
        for event in raw_events:
            inventory = inventory_by_session[event.session_id]
            bundle = normalize_event(inventory, event)
            diagnostics.add(bundle.outcome, bundle.evidence)
            for evidence in bundle.evidence:
                handle.write(json.dumps(evidence.to_dict(), sort_keys=True) + "\n")

    write_normalization_diagnostics(diagnostics_path, diagnostics)
    return {
        "output_dir": str(output_dir),
        "evidence": str(evidence_path),
        "normalization_diagnostics": str(diagnostics_path),
    }


def iter_normalized_evidence(inventory_records: Iterable[InventoryRecord], raw_events: Iterable[RawEvent]) -> Iterator[dict[str, Any]]:
    inventory_by_session = {record.session_id: record for record in inventory_records}
    for event in raw_events:
        bundle = normalize_event(inventory_by_session[event.session_id], event)
        for evidence in bundle.evidence:
            yield evidence.to_dict()


def _extract_block_text(block: dict[str, Any]) -> str | None:
    block_type = block.get("type")
    if block_type == "text":
        return _maybe_string(block.get("text"))
    if block_type in {"thinking", "redacted_thinking"}:
        return _maybe_string(block.get("thinking"))
    if block_type == "tool_use":
        return json.dumps(block.get("input", {}), sort_keys=True)
    if block_type == "tool_result":
        content = block.get("content")
        if isinstance(content, str):
            return content
        return json.dumps(content, sort_keys=True)
    return None


def _block_metadata(block: dict[str, Any]) -> dict[str, Any]:
    metadata = {}
    for key in ("id", "name", "signature"):
        value = block.get(key)
        if value is not None:
            metadata[key] = value
    if "input" in block:
        metadata["input"] = block["input"]
    return metadata


def _record_metadata(record: dict[str, Any]) -> dict[str, Any]:
    metadata = {}
    for key in (
        "subtype",
        "isMeta",
        "isCompactSummary",
        "isVisibleInTranscriptOnly",
        "sourceToolAssistantUUID",
        "toolUseResult",
    ):
        if key in record:
            metadata[key] = record[key]
    if isinstance(record.get("data"), dict):
        metadata["data"] = record["data"]
    if isinstance(record.get("snapshot"), dict):
        metadata["snapshot"] = record["snapshot"]
    return metadata


def _maybe_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _maybe_bool(value: Any) -> bool | None:
    return value if isinstance(value, bool) else None
