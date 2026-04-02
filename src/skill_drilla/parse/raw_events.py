"""Raw event models and deterministic parse artifact generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

from skill_drilla.discovery.inventory import InventoryRecord
from skill_drilla.parse.jsonl_stream import JSONLStreamRecord, stream_jsonl_records


KNOWN_RECORD_TYPES = frozenset(
    {
        "assistant",
        "file-history-snapshot",
        "progress",
        "summary",
        "system",
        "user",
    }
)

PARSE_STATUS_ORDER = {
    "parsed": 0,
    "unknown_record_shape": 1,
    "invalid_json": 2,
    "non_object": 3,
    "blank": 4,
}


@dataclass(frozen=True)
class RawEvent:
    project_id: str
    project_slug: str
    session_id: str
    session_key: str
    session_role: str
    source_file: str
    source_line: int
    event_index: int
    parse_status: str
    record_type: str | None
    message_role: str | None
    is_sidechain: bool | None
    raw_record: dict[str, Any] | None
    parse_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "project_id": self.project_id,
            "project_slug": self.project_slug,
            "session_id": self.session_id,
            "session_key": self.session_key,
            "session_role": self.session_role,
            "source_file": self.source_file,
            "source_line": self.source_line,
            "event_index": self.event_index,
            "parse_status": self.parse_status,
            "record_type": self.record_type,
            "message_role": self.message_role,
            "is_sidechain": self.is_sidechain,
            "raw_record": self.raw_record,
            "parse_error": self.parse_error,
        }
        return payload


def iter_raw_events(record: InventoryRecord) -> Iterator[RawEvent]:
    for event_index, streamed in enumerate(stream_jsonl_records(record.transcript_path)):
        yield raw_event_from_stream_record(record, streamed, event_index)


def raw_event_from_stream_record(
    inventory_record: InventoryRecord,
    streamed: JSONLStreamRecord,
    event_index: int,
) -> RawEvent:
    parsed_record = streamed.record
    record_type = None
    message_role = None
    is_sidechain = None
    parse_status = streamed.status

    if parsed_record is not None:
        record_type = _optional_string(parsed_record.get("type"))
        message = parsed_record.get("message")
        if isinstance(message, dict):
            message_role = _optional_string(message.get("role"))
        sidechain_value = parsed_record.get("isSidechain")
        if isinstance(sidechain_value, bool):
            is_sidechain = sidechain_value
        if parse_status == "parsed" and not _is_known_shape(parsed_record):
            parse_status = "unknown_record_shape"

    return RawEvent(
        project_id=inventory_record.project_id,
        project_slug=inventory_record.project_slug,
        session_id=inventory_record.session_id,
        session_key=inventory_record.session_key,
        session_role=inventory_record.session_role,
        source_file=inventory_record.transcript_path,
        source_line=streamed.line_number,
        event_index=event_index,
        parse_status=parse_status,
        record_type=record_type,
        message_role=message_role,
        is_sidechain=is_sidechain,
        raw_record=parsed_record,
        parse_error=streamed.error,
    )


def write_raw_events(output_path: Path, events: Iterable[RawEvent]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")
    return output_path


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _is_known_shape(record: dict[str, Any]) -> bool:
    record_type = record.get("type")
    if record_type in KNOWN_RECORD_TYPES:
        return True
    if isinstance(record.get("message"), dict):
        return True
    if isinstance(record.get("data"), dict):
        return True
    if isinstance(record.get("snapshot"), dict):
        return True
    return False
