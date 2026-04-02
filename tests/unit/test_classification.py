from pathlib import Path

from skill_drilla.cli import load_inventory_records, load_raw_events
from skill_drilla.normalize import normalize_event
from skill_drilla.normalize.classifier import classify_raw_event


FIXTURE_DIR = Path("tests/fixtures/normalize")


def _load():
    return load_inventory_records(FIXTURE_DIR / "sample_inventory.jsonl"), load_raw_events(FIXTURE_DIR / "sample_raw_events.jsonl")


def test_classifier_distinguishes_minimum_semantic_classes():
    inventory, events = _load()
    assert classify_raw_event(events[0]).semantic_class == "user_natural_language"
    assert classify_raw_event(events[2]).semantic_class == "tool_result"
    assert classify_raw_event(events[4]).semantic_class == "snapshot_state"
    assert classify_raw_event(events[5]).semantic_class == "unknown_ambiguous"

    assistant_bundle = normalize_event(inventory[0], events[1])
    assert [item.semantic_class for item in assistant_bundle.evidence] == [
        "assistant_natural_language",
        "tool_call",
    ]

    thinking_bundle = normalize_event(inventory[1], events[3])
    assert thinking_bundle.evidence[0].semantic_class == "thinking"
    assert thinking_bundle.evidence[0].session_role == "subagent"
    assert thinking_bundle.evidence[0].root_session_id == inventory[1].root_session_id


def test_unknown_and_ambiguous_items_remain_inspectable():
    inventory, events = _load()
    ambiguous = normalize_event(inventory[0], events[5]).evidence[0]
    assert ambiguous.semantic_class == "unknown_ambiguous"
    assert ambiguous.inclusion_status == "ambiguous"
    assert ambiguous.ambiguity_reason == "parse_status:unknown_record_shape"
