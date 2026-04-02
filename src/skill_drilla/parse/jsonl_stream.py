"""Streaming JSONL parsing helpers for transcript ingestion."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


@dataclass(frozen=True)
class JSONLStreamRecord:
    """A single streamed JSONL record with line provenance."""

    line_number: int
    raw_line: str
    record: dict[str, Any] | None
    status: str
    error: str | None = None


VALID_STREAM_STATUSES = frozenset({"parsed", "blank", "invalid_json", "non_object"})


def stream_jsonl_records(path: str | Path | Any) -> Iterator[JSONLStreamRecord]:
    """Yield JSONL records one line at a time without materializing the file."""

    source_path = path if hasattr(path, "open") else Path(path)
    with source_path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            payload = raw_line.rstrip("\n")
            if not payload.strip():
                yield JSONLStreamRecord(
                    line_number=line_number,
                    raw_line=payload,
                    record=None,
                    status="blank",
                    error="blank line",
                )
                continue

            try:
                decoded = json.loads(payload)
            except json.JSONDecodeError as exc:
                yield JSONLStreamRecord(
                    line_number=line_number,
                    raw_line=payload,
                    record=None,
                    status="invalid_json",
                    error=f"{exc.msg} at column {exc.colno}",
                )
                continue

            if not isinstance(decoded, dict):
                yield JSONLStreamRecord(
                    line_number=line_number,
                    raw_line=payload,
                    record=None,
                    status="non_object",
                    error=f"expected JSON object, got {type(decoded).__name__}",
                )
                continue

            yield JSONLStreamRecord(
                line_number=line_number,
                raw_line=payload,
                record=decoded,
                status="parsed",
                error=None,
            )
