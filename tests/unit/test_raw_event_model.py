import json
from pathlib import Path

from skill_drilla.cli import load_inventory_records
from skill_drilla.parse import iter_raw_events, summarize_file_parse


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = REPO_ROOT / "tests" / "fixtures" / "parse" / "sample_session.jsonl"


def make_inventory_record(tmp_path: Path):
    inventory_path = tmp_path / "inventory.jsonl"
    inventory_path.write_text(
        json.dumps(
            {
                "project_id": "a" * 64,
                "project_slug": "fixture-project",
                "session_id": "b" * 64,
                "session_key": "fixture-session",
                "transcript_path": str(FIXTURE),
                "transcript_relpath": "sample_session.jsonl",
                "session_role": "root",
                "lineage_state": "confirmed",
                "parent_session_id": None,
                "root_session_id": "b" * 64,
                "observed_parent_session_key": None,
                "observed_root_session_key": "fixture-session",
                "lineage_source": "fixture",
                "subagent_id": None,
                "metadata_path": None,
                "transcript_format": "jsonl",
                "transcript_size_bytes": FIXTURE.stat().st_size,
                "transcript_mtime_ns": FIXTURE.stat().st_mtime_ns,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    return load_inventory_records(inventory_path)[0]


def test_raw_events_preserve_required_provenance_fields(tmp_path: Path):
    inventory_record = make_inventory_record(tmp_path)
    events = list(iter_raw_events(inventory_record))

    first = events[0].to_dict()
    assert {
        "project_id",
        "session_id",
        "source_file",
        "source_line",
        "event_index",
        "parse_status",
    } <= set(first)
    assert first["source_file"] == str(FIXTURE)
    assert first["source_line"] == 1
    assert first["event_index"] == 0
    assert events[2].parse_status == "unknown_record_shape"
    assert events[3].parse_status == "invalid_json"
    assert events[4].parse_status == "non_object"


def test_summarize_file_parse_counts_explicit_outcomes(tmp_path: Path):
    inventory_record = make_inventory_record(tmp_path)
    events, diagnostics = summarize_file_parse(inventory_record, iter_raw_events(inventory_record))

    assert len(events) == 6
    assert diagnostics.total_lines == 6
    assert diagnostics.parsed_events == 3
    assert diagnostics.invalid_lines == 1
    assert diagnostics.non_object_lines == 1
    assert diagnostics.blank_lines == 1
    assert diagnostics.unknown_record_shapes == 1
