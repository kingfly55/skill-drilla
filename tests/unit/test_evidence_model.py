import json
from pathlib import Path

from skill_drilla.cli import load_inventory_records, load_raw_events
from skill_drilla.normalize import normalize_event, write_normalize_artifacts
from skill_drilla.normalize.model import build_raw_event_id


FIXTURE_DIR = Path("tests/fixtures/normalize")


def test_evidence_records_preserve_canonical_fields():
    inventory = load_inventory_records(FIXTURE_DIR / "sample_inventory.jsonl")
    events = load_raw_events(FIXTURE_DIR / "sample_raw_events.jsonl")

    bundle = normalize_event(inventory[0], events[0])
    evidence = bundle.evidence[0].to_dict()

    assert {
        "evidence_id",
        "project_id",
        "session_id",
        "raw_event_id",
        "semantic_class",
        "inclusion_status",
        "inclusion_rationale",
        "session_role",
        "root_session_id",
    } <= set(evidence)
    assert evidence["semantic_class"] == "user_natural_language"
    assert evidence["inclusion_status"] == "included_primary"
    assert evidence["root_session_id"] == inventory[0].root_session_id


def test_normalization_can_emit_multiple_evidence_units(tmp_path: Path):
    inventory = load_inventory_records(FIXTURE_DIR / "sample_inventory.jsonl")
    events = load_raw_events(FIXTURE_DIR / "sample_raw_events.jsonl")

    bundle = normalize_event(inventory[0], events[1])
    assert len(bundle.evidence) == 2
    assert bundle.outcome.outcome == "multiple_evidence"
    assert {item.semantic_class for item in bundle.evidence} == {
        "assistant_natural_language",
        "tool_call",
    }

    artifacts = write_normalize_artifacts(tmp_path, inventory, events)
    evidence_lines = (tmp_path / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
    diagnostics = json.loads((tmp_path / "normalization_diagnostics.json").read_text(encoding="utf-8"))

    assert artifacts["evidence"].endswith("evidence.jsonl")
    assert len(evidence_lines) == 7
    assert diagnostics["multi_evidence_events"] == 1
    assert diagnostics["transform_outcome_counts"]["multiple_evidence"] == 1
    assert diagnostics["semantic_class_counts"]["unknown_ambiguous"] == 1


def test_raw_event_id_is_stable_for_provenance():
    events = load_raw_events(FIXTURE_DIR / "sample_raw_events.jsonl")
    raw_event_id = build_raw_event_id(events[0])
    assert len(raw_event_id) == 64
    assert raw_event_id == build_raw_event_id(events[0])
