"""Integration tests for the extract-episodes CLI command."""

import json
from pathlib import Path

from skill_drilla.cli import STABLE_PIPELINE_COMMANDS, main

FIXTURE_EVIDENCE = Path("tests/fixtures/normalize/sample_evidence.jsonl")


def test_extract_episodes_command_registered_in_stable_pipeline_commands():
    assert "extract-episodes" in STABLE_PIPELINE_COMMANDS


def test_extract_episodes_command_produces_artifacts(tmp_path: Path, capsys):
    code = main([
        "extract-episodes",
        "--evidence", str(FIXTURE_EVIDENCE),
        "--run-label", "test-run",
        "--output-dir", str(tmp_path / "episodes"),
    ])
    assert code == 0
    assert (tmp_path / "episodes" / "test-run" / "episodes.jsonl").exists()
    assert (tmp_path / "episodes" / "test-run" / "episode_index.json").exists()


def test_extract_episodes_cli_output_is_json(tmp_path: Path, capsys):
    main([
        "extract-episodes",
        "--evidence", str(FIXTURE_EVIDENCE),
        "--run-label", "test-run",
        "--output-dir", str(tmp_path / "episodes"),
    ])
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["command"] == "extract-episodes"
    assert "episode_count" in payload
    assert "turn_count" in payload
    assert "artifacts" in payload


def test_extract_episodes_output_episodes_valid_structure(tmp_path: Path):
    main([
        "extract-episodes",
        "--evidence", str(FIXTURE_EVIDENCE),
        "--run-label", "run1",
        "--output-dir", str(tmp_path),
    ])
    episodes_path = tmp_path / "run1" / "episodes.jsonl"
    episodes = [json.loads(line) for line in episodes_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    required_fields = {"episode_id", "root_session_id", "project_id", "project_slug", "turn_count", "turns", "child_episode_refs", "session_ids"}
    for ep in episodes:
        assert required_fields <= ep.keys(), f"Missing fields in episode: {required_fields - ep.keys()}"


def test_extract_episodes_preserves_provenance_fields_in_turns(tmp_path: Path):
    main([
        "extract-episodes",
        "--evidence", str(FIXTURE_EVIDENCE),
        "--run-label", "run1",
        "--output-dir", str(tmp_path),
    ])
    episodes_path = tmp_path / "run1" / "episodes.jsonl"
    for line in episodes_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        ep = json.loads(line)
        for turn in ep["turns"]:
            assert turn["evidence_id"], f"evidence_id missing in turn {turn}"
            assert turn["raw_event_id"], f"raw_event_id missing in turn {turn}"
            assert turn["raw_event_index"] is not None
            assert turn["session_id"], f"session_id missing in turn {turn}"


def test_extract_episodes_index_valid_structure(tmp_path: Path):
    main([
        "extract-episodes",
        "--evidence", str(FIXTURE_EVIDENCE),
        "--run-label", "run1",
        "--output-dir", str(tmp_path),
    ])
    index = json.loads((tmp_path / "run1" / "episode_index.json").read_text(encoding="utf-8"))
    assert "episode_count" in index
    assert "turn_count" in index
    assert "episode_ids" in index
    assert "root_session_ids" in index
    assert index["episode_count"] >= 1
    assert index["turn_count"] >= 1


def test_extract_episodes_subagent_linked_not_inlined(tmp_path: Path):
    """The fixture contains a subagent row; it should appear in child_episode_refs, not as a turn."""
    main([
        "extract-episodes",
        "--evidence", str(FIXTURE_EVIDENCE),
        "--run-label", "run1",
        "--output-dir", str(tmp_path),
    ])
    episodes_path = tmp_path / "run1" / "episodes.jsonl"
    episodes = [json.loads(l) for l in episodes_path.read_text(encoding="utf-8").splitlines() if l.strip()]

    # Find the episode that has the root session cccc... (contains the subagent in fixture)
    root_ep = next((e for e in episodes if e["root_session_id"].startswith("cccc")), None)
    assert root_ep is not None, "Expected an episode for root session cccc..."

    # The subagent session_id from the fixture is 6767...
    subagent_sid = "6767676767676767676767676767676767676767676767676767676767676767"
    assert subagent_sid in root_ep["child_episode_refs"], (
        f"Subagent session_id should be in child_episode_refs; got {root_ep['child_episode_refs']}"
    )

    # The subagent's content should not appear as a turn with session_role=subagent
    for turn in root_ep["turns"]:
        assert turn["session_role"] != "subagent", "Subagent turns should not be inlined"


def test_extract_episodes_requires_evidence_and_output_dir(tmp_path: Path):
    try:
        main([
            "extract-episodes",
            "--output-dir", str(tmp_path),
        ])
    except ValueError as exc:
        assert "requires" in str(exc)
    else:
        raise AssertionError("expected ValueError when --evidence is missing")
