"""Parse diagnostics aggregation and artifact writing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from skill_drilla.discovery.inventory import InventoryRecord
from skill_drilla.parse.raw_events import RawEvent


@dataclass(frozen=True)
class FileParseDiagnostics:
    project_id: str
    session_id: str
    source_file: str
    session_role: str
    total_lines: int
    parsed_events: int
    invalid_lines: int
    blank_lines: int
    non_object_lines: int
    unknown_record_shapes: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "session_id": self.session_id,
            "source_file": self.source_file,
            "session_role": self.session_role,
            "total_lines": self.total_lines,
            "parsed_events": self.parsed_events,
            "invalid_lines": self.invalid_lines,
            "blank_lines": self.blank_lines,
            "non_object_lines": self.non_object_lines,
            "unknown_record_shapes": self.unknown_record_shapes,
        }


class DiagnosticsAccumulator:
    def __init__(self) -> None:
        self._files: list[FileParseDiagnostics] = []

    def add_file_counts(self, file_diagnostics: FileParseDiagnostics) -> None:
        self._files.append(file_diagnostics)

    def to_dict(self) -> dict[str, Any]:
        files = [item.to_dict() for item in sorted(self._files, key=lambda item: (item.source_file, item.session_id))]
        aggregate = {
            "files": len(files),
            "total_lines": sum(item["total_lines"] for item in files),
            "parsed_events": sum(item["parsed_events"] for item in files),
            "invalid_lines": sum(item["invalid_lines"] for item in files),
            "blank_lines": sum(item["blank_lines"] for item in files),
            "non_object_lines": sum(item["non_object_lines"] for item in files),
            "unknown_record_shapes": sum(item["unknown_record_shapes"] for item in files),
        }
        return {"aggregate": aggregate, "files": files}


def summarize_file_parse(
    inventory_record: InventoryRecord,
    events: Iterable[RawEvent],
) -> tuple[tuple[RawEvent, ...], FileParseDiagnostics]:
    event_list = tuple(events)
    file_diagnostics = FileParseDiagnostics(
        project_id=inventory_record.project_id,
        session_id=inventory_record.session_id,
        source_file=inventory_record.transcript_path,
        session_role=inventory_record.session_role,
        total_lines=len(event_list),
        parsed_events=sum(1 for event in event_list if event.parse_status in {"parsed", "unknown_record_shape"}),
        invalid_lines=sum(1 for event in event_list if event.parse_status == "invalid_json"),
        blank_lines=sum(1 for event in event_list if event.parse_status == "blank"),
        non_object_lines=sum(1 for event in event_list if event.parse_status == "non_object"),
        unknown_record_shapes=sum(1 for event in event_list if event.parse_status == "unknown_record_shape"),
    )
    return event_list, file_diagnostics


def write_parse_artifacts(
    output_dir: Path,
    inventory_records: Iterable[InventoryRecord],
    event_iter_factory,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "raw_events.jsonl"
    diagnostics_path = output_dir / "parse_diagnostics.json"

    accumulator = DiagnosticsAccumulator()
    with raw_path.open("w", encoding="utf-8") as handle:
        for inventory_record in inventory_records:
            events, file_diagnostics = summarize_file_parse(inventory_record, event_iter_factory(inventory_record))
            accumulator.add_file_counts(file_diagnostics)
            for event in events:
                handle.write(json.dumps(event.to_dict(), sort_keys=True) + "\n")

    write_parse_diagnostics(diagnostics_path, accumulator)
    return {
        "output_dir": str(output_dir),
        "raw_events": str(raw_path),
        "parse_diagnostics": str(diagnostics_path),
    }


def write_parse_diagnostics(output_path: Path, diagnostics: DiagnosticsAccumulator) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(diagnostics.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path
