"""Streaming reader for canonical evidence.jsonl artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterator


def iter_evidence_rows(evidence_path: Path) -> Iterator[dict[str, Any]]:
    """Yield one dict per non-blank line from an evidence.jsonl file."""
    with evidence_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)
