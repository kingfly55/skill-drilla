"""Integration tests for the skill-mining CLI workflow."""

from __future__ import annotations

import json
from pathlib import Path

from skill_drilla.cli import main


# ---------------------------------------------------------------------------
# Fixture episode data helpers
# ---------------------------------------------------------------------------

def _write_fixture_episodes(ep_dir: Path) -> None:
    """Write a minimal episodes.jsonl + episode_index.json for testing."""
    ep_dir.mkdir(parents=True, exist_ok=True)

    def _turn(turn_id, ep_id, role, text, ev_id, idx):
        return {
            "turn_id": turn_id,
            "episode_id": ep_id,
            "turn_index": idx,
            "role": role,
            "content_text": text,
            "compressed_text": None,
            "tool_context": [],
            "evidence_id": ev_id,
            "raw_event_id": "r" * 64,
            "raw_event_index": idx,
            "session_id": "s" * 64,
            "root_session_id": "rs" * 32,
            "parent_session_id": None,
            "session_role": "root",
        }

    episodes = [
        {
            "episode_id": "ep-aaa",
            "root_session_id": "rs" * 32,
            "project_id": "p" * 64,
            "project_slug": "fixture-project",
            "turn_count": 3,
            "turns": [
                _turn("t1", "ep-aaa", "user", "Please fix the failing tests.", "e1" * 32, 0),
                _turn("t2", "ep-aaa", "assistant", "I will fix the tests.", "e2" * 32, 1),
                _turn("t3", "ep-aaa", "user", "Please summarize the output.", "e3" * 32, 2),
            ],
            "child_episode_refs": [],
            "session_ids": ["s" * 64],
        },
        {
            "episode_id": "ep-bbb",
            "root_session_id": "rb" * 32,
            "project_id": "p" * 64,
            "project_slug": "fixture-project",
            "turn_count": 2,
            "turns": [
                _turn("t4", "ep-bbb", "user", "Fix the linting errors.", "e4" * 32, 0),
                _turn("t5", "ep-bbb", "user", "Please add docs for the new module.", "e5" * 32, 1),
            ],
            "child_episode_refs": [],
            "session_ids": ["s" * 64],
        },
    ]

    with (ep_dir / "episodes.jsonl").open("w", encoding="utf-8") as fh:
        for ep in episodes:
            fh.write(json.dumps(ep) + "\n")

    index = {
        "run_id": "fixture-run",
        "episode_count": len(episodes),
        "turn_count": 5,
        "root_session_ids": [ep["root_session_id"] for ep in episodes],
        "episode_ids": [ep["episode_id"] for ep in episodes],
        "child_ref_count": 0,
    }
    (ep_dir / "episode_index.json").write_text(
        json.dumps(index, indent=2) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# CLI contract tests
# ---------------------------------------------------------------------------

def test_skill_mining_requires_explicit_opt_in(tmp_path: Path):
    ep_dir = tmp_path / "episodes" / "default"
    _write_fixture_episodes(ep_dir)

    try:
        main([
            "semantic-run",
            "--method", "skill-mining",
            "--episode-dir", str(ep_dir),
            "--output-dir", str(tmp_path / "out"),
        ])
    except ValueError as exc:
        assert "disabled by default" in str(exc)
    else:
        raise AssertionError("semantic-run should require --disabled-by-default-check")


def test_skill_mining_requires_episode_dir(tmp_path: Path):
    try:
        main([
            "semantic-run",
            "--method", "skill-mining",
            "--disabled-by-default-check",
            "--output-dir", str(tmp_path / "out"),
        ])
    except ValueError as exc:
        assert "episode-dir" in str(exc).lower()
    else:
        raise AssertionError("skill-mining should require --episode-dir")


def test_skill_mining_fixture_backend_writes_artifact(tmp_path: Path, capsys):
    ep_dir = tmp_path / "episodes" / "default"
    _write_fixture_episodes(ep_dir)

    code = main([
        "semantic-run",
        "--method", "skill-mining",
        "--episode-dir", str(ep_dir),
        "--disabled-by-default-check",
        "--output-dir", str(tmp_path / "out"),
    ])

    out = capsys.readouterr().out
    assert code == 0
    assert '"command": "semantic-run"' in out
    assert '"method": "skill-mining"' in out
    assert '"non_canonical": true' in out
    assert (tmp_path / "out" / "semantic_run.json").exists()


def test_skill_mining_artifact_shape(tmp_path: Path):
    ep_dir = tmp_path / "episodes" / "default"
    _write_fixture_episodes(ep_dir)

    main([
        "semantic-run",
        "--method", "skill-mining",
        "--episode-dir", str(ep_dir),
        "--disabled-by-default-check",
        "--output-dir", str(tmp_path / "out"),
    ])

    payload = json.loads((tmp_path / "out" / "semantic_run.json").read_text(encoding="utf-8"))
    assert payload["non_canonical"] is True
    assert payload["method"] == "skill-mining"
    assert "canonical_input" in payload
    assert "derived_output" in payload
    assert "parameters" in payload

    derived = payload["derived_output"]
    assert derived["kind"] == "skill_mining"
    assert derived["non_canonical"] is True
    assert "candidate_skills" in derived
    assert "candidate_skill_count" in derived
    assert "scope" in derived
    assert "caveats" in derived


def test_skill_mining_artifact_is_non_canonical(tmp_path: Path):
    ep_dir = tmp_path / "episodes" / "default"
    _write_fixture_episodes(ep_dir)

    main([
        "semantic-run",
        "--method", "skill-mining",
        "--episode-dir", str(ep_dir),
        "--disabled-by-default-check",
        "--output-dir", str(tmp_path / "out"),
    ])

    payload = json.loads((tmp_path / "out" / "semantic_run.json").read_text(encoding="utf-8"))
    assert payload["non_canonical"] is True


def test_skill_mining_candidate_skills_have_evidence_ids(tmp_path: Path):
    ep_dir = tmp_path / "episodes" / "default"
    _write_fixture_episodes(ep_dir)

    main([
        "semantic-run",
        "--method", "skill-mining",
        "--episode-dir", str(ep_dir),
        "--disabled-by-default-check",
        "--output-dir", str(tmp_path / "out"),
    ])

    payload = json.loads((tmp_path / "out" / "semantic_run.json").read_text(encoding="utf-8"))
    skills = payload["derived_output"]["candidate_skills"]
    for skill in skills:
        assert "skill_id" in skill
        assert "supporting_evidence_ids" in skill
        for ref in skill.get("representative_turn_refs", []):
            assert "evidence_id" in ref


def test_skill_mining_canonical_input_records_episode_dir(tmp_path: Path):
    ep_dir = tmp_path / "episodes" / "default"
    _write_fixture_episodes(ep_dir)

    main([
        "semantic-run",
        "--method", "skill-mining",
        "--episode-dir", str(ep_dir),
        "--disabled-by-default-check",
        "--output-dir", str(tmp_path / "out"),
    ])

    payload = json.loads((tmp_path / "out" / "semantic_run.json").read_text(encoding="utf-8"))
    ci = payload["canonical_input"]
    assert ci["episode_dir"] == str(ep_dir)
    assert ci["episode_count"] == 2


def test_skill_mining_api_key_not_in_stored_parameters(tmp_path: Path):
    ep_dir = tmp_path / "episodes" / "default"
    _write_fixture_episodes(ep_dir)

    main([
        "semantic-run",
        "--method", "skill-mining",
        "--episode-dir", str(ep_dir),
        "--api-key", "super-secret",
        "--disabled-by-default-check",
        "--output-dir", str(tmp_path / "out"),
    ])

    payload = json.loads((tmp_path / "out" / "semantic_run.json").read_text(encoding="utf-8"))
    assert "api_key" not in payload["parameters"]
    assert "super-secret" not in json.dumps(payload)


def test_skill_mining_with_backend_fixture_param(tmp_path: Path, capsys):
    ep_dir = tmp_path / "episodes" / "default"
    _write_fixture_episodes(ep_dir)

    code = main([
        "semantic-run",
        "--method", "skill-mining",
        "--episode-dir", str(ep_dir),
        "--backend", "fixture",
        "--disabled-by-default-check",
        "--output-dir", str(tmp_path / "out"),
    ])

    out = capsys.readouterr().out
    assert code == 0
    assert '"backend": "fixture"' in out


def test_existing_methods_still_work_after_skill_mining_added(tmp_path: Path, capsys):
    """Existing semantic methods must remain unaffected."""
    code = main([
        "semantic-run",
        "--view-dir", "artifacts/chat-analysis/views/user_nl_root_only",
        "--method", "clustering",
        "--disabled-by-default-check",
        "--output-dir", str(tmp_path / "out"),
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert '"method": "clustering"' in out
    assert (tmp_path / "out" / "semantic_run.json").exists()
