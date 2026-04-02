import json
from pathlib import Path

from skill_drilla.discovery.inventory import InventoryRecord
from skill_drilla.normalize.transform import normalize_event
from skill_drilla.parse.jsonl_stream import stream_jsonl_records
from skill_drilla.parse.raw_events import raw_event_from_stream_record


FIXTURE_INVENTORY = InventoryRecord(
    project_id="p1",
    project_slug="fixture-project",
    session_id="s1",
    session_key="fixture-session",
    transcript_path="/tmp/fixture.jsonl",
    transcript_relpath="fixture.jsonl",
    session_role="root",
    lineage_state="confirmed",
    parent_session_id=None,
    root_session_id="s1",
    observed_parent_session_key=None,
    observed_root_session_key="fixture-session",
    lineage_source="fixture",
    subagent_id=None,
    metadata_path=None,
    transcript_format="jsonl",
    transcript_size_bytes=1,
    transcript_mtime_ns=1,
)


def _event_from_payload(tmp_path: Path, payload: str, *, event_index: int = 0):
    transcript = tmp_path / "variant.jsonl"
    transcript.write_text(payload, encoding="utf-8")
    streamed = next(stream_jsonl_records(transcript))
    inventory = FIXTURE_INVENTORY.__class__(**{**FIXTURE_INVENTORY.to_dict(), "transcript_path": str(transcript)})
    return inventory, raw_event_from_stream_record(inventory, streamed, event_index)


def test_invalid_json_line_surfaces_ambiguous_evidence(tmp_path: Path):
    inventory, event = _event_from_payload(tmp_path, '{"type":"user"\n')

    bundle = normalize_event(inventory, event)

    assert event.parse_status == "invalid_json"
    assert bundle.evidence[0].inclusion_status == "ambiguous"
    assert bundle.evidence[0].metadata["parse_error"]


def test_non_object_json_line_is_recorded_as_ambiguous(tmp_path: Path):
    inventory, event = _event_from_payload(tmp_path, '[1, 2, 3]\n')

    bundle = normalize_event(inventory, event)

    assert event.parse_status == "non_object"
    assert bundle.evidence[0].semantic_class == "unknown_ambiguous"


def test_user_tool_result_block_does_not_count_as_primary_user_language(tmp_path: Path):
    payload = json.dumps(
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tool-1", "content": "failure output", "is_error": True}
                ],
            },
        }
    ) + "\n"
    inventory, event = _event_from_payload(tmp_path, payload)

    bundle = normalize_event(inventory, event)

    assert bundle.evidence[0].semantic_class == "tool_result"
    assert bundle.evidence[0].inclusion_status == "excluded_default"
    assert bundle.evidence[0].producer_role == "user"


def test_assistant_text_block_is_secondary_language(tmp_path: Path):
    payload = json.dumps(
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Here is the report summary."}],
            },
        }
    ) + "\n"
    inventory, event = _event_from_payload(tmp_path, payload)

    bundle = normalize_event(inventory, event)

    assert bundle.evidence[0].semantic_class == "assistant_natural_language"
    assert bundle.evidence[0].inclusion_status == "included_secondary"


def test_unknown_message_content_shape_is_ambiguous(tmp_path: Path):
    payload = json.dumps(
        {
            "type": "user",
            "message": {"role": "user", "content": {"unexpected": True}},
        }
    ) + "\n"
    inventory, event = _event_from_payload(tmp_path, payload)

    bundle = normalize_event(inventory, event)

    assert bundle.evidence[0].semantic_class == "unknown_ambiguous"
    assert bundle.evidence[0].ambiguity_reason == "unsupported_message_content_shape"
