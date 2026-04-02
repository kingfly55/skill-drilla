"""Unit tests for episode evidence loader."""

import json
from pathlib import Path

from skill_drilla.episodes.loader import iter_evidence_rows


def test_iter_evidence_rows_yields_dicts(tmp_path: Path):
    f = tmp_path / "evidence.jsonl"
    f.write_text(
        json.dumps({"evidence_id": "aaa", "session_id": "sss"}) + "\n" +
        json.dumps({"evidence_id": "bbb", "session_id": "ttt"}) + "\n",
        encoding="utf-8",
    )
    rows = list(iter_evidence_rows(f))
    assert len(rows) == 2
    assert rows[0]["evidence_id"] == "aaa"
    assert rows[1]["evidence_id"] == "bbb"


def test_iter_evidence_rows_skips_blank_lines(tmp_path: Path):
    f = tmp_path / "evidence.jsonl"
    f.write_text(
        json.dumps({"evidence_id": "aaa"}) + "\n" +
        "\n" +
        json.dumps({"evidence_id": "bbb"}) + "\n",
        encoding="utf-8",
    )
    rows = list(iter_evidence_rows(f))
    assert len(rows) == 2


def test_iter_evidence_rows_empty_file(tmp_path: Path):
    f = tmp_path / "evidence.jsonl"
    f.write_text("", encoding="utf-8")
    rows = list(iter_evidence_rows(f))
    assert rows == []
