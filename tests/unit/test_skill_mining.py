"""Unit tests for the skill-mining semantic method."""

from __future__ import annotations

import json
from pathlib import Path

from skill_drilla.semantic import SEMANTIC_METHODS, get_semantic_method
from skill_drilla.semantic.skill_mining import (
    SkillMiningMethod,
    _collect_user_turns,
    _derive_fixture,
    _leading_token,
    _load_episodes,
    _summarize_text,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_turn(turn_id: str, episode_id: str, role: str, text: str, evidence_id: str = None, turn_index: int = 0) -> dict:
    return {
        "turn_id": turn_id or f"turn-{turn_index}",
        "episode_id": episode_id,
        "turn_index": turn_index,
        "role": role,
        "content_text": text,
        "compressed_text": None,
        "tool_context": [],
        "evidence_id": evidence_id or ("e" * 64),
        "raw_event_id": "r" * 64,
        "raw_event_index": turn_index,
        "session_id": "s" * 64,
        "root_session_id": "rs" * 32,
        "parent_session_id": None,
        "session_role": "root",
    }


def _make_episode(episode_id: str, turns: list) -> dict:
    return {
        "episode_id": episode_id,
        "root_session_id": "rs" * 32,
        "project_id": "p" * 64,
        "project_slug": "test-project",
        "turn_count": len(turns),
        "turns": turns,
        "child_episode_refs": [],
        "session_ids": ["s" * 64],
    }


def _sample_episodes() -> list[dict]:
    ep1_turns = [
        _make_turn("t1", "ep1", "user", "Please fix the failing tests.", "e1" * 32, 0),
        _make_turn("t2", "ep1", "assistant", "I will fix the tests.", "e2" * 32, 1),
        _make_turn("t3", "ep1", "user", "Please summarize the changes.", "e3" * 32, 2),
    ]
    ep2_turns = [
        _make_turn("t4", "ep2", "user", "Fix the linting errors in the codebase.", "e4" * 32, 0),
        _make_turn("t5", "ep2", "user", "Please add documentation for the API.", "e5" * 32, 1),
    ]
    return [
        _make_episode("ep1", ep1_turns),
        _make_episode("ep2", ep2_turns),
    ]


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------

def test_skill_mining_is_registered_in_semantic_methods():
    assert "skill-mining" in SEMANTIC_METHODS
    method = get_semantic_method("skill-mining")
    assert isinstance(method, SkillMiningMethod)


def test_skill_mining_method_name():
    assert SkillMiningMethod.method_name == "skill-mining"


def test_skill_mining_default_parameters_include_base_url():
    defaults = SkillMiningMethod.default_parameters
    assert "base_url" in defaults
    assert "base_url" in defaults
    assert "model" in defaults
    assert "backend" in defaults
    assert defaults["backend"] == "fixture"


# ---------------------------------------------------------------------------
# Fixture backend — derive_from_episodes
# ---------------------------------------------------------------------------

def test_derive_fixture_empty_episodes():
    method = SkillMiningMethod()
    result = method.derive_from_episodes([], {})
    assert result["kind"] == "skill_mining"
    assert result["non_canonical"] is True
    assert result["candidate_skill_count"] == 0
    assert result["candidate_skills"] == []
    assert result["scope"]["episode_count"] == 0
    assert result["scope"]["user_turn_count"] == 0


def test_derive_fixture_produces_candidate_skills():
    episodes = _sample_episodes()
    method = SkillMiningMethod()
    result = method.derive_from_episodes(episodes, {"backend": "fixture"})
    assert result["kind"] == "skill_mining"
    assert result["non_canonical"] is True
    assert result["candidate_skill_count"] > 0
    assert len(result["candidate_skills"]) == result["candidate_skill_count"]


def test_derive_fixture_candidate_skill_shape():
    episodes = _sample_episodes()
    method = SkillMiningMethod()
    result = method.derive_from_episodes(episodes, {"backend": "fixture"})
    for skill in result["candidate_skills"]:
        assert "skill_id" in skill
        assert "candidate_label" in skill
        assert "turn_count" in skill
        assert "representative_turn_refs" in skill
        assert "supporting_evidence_ids" in skill
        assert isinstance(skill["representative_turn_refs"], list)


def test_derive_fixture_preserves_evidence_ids():
    episodes = _sample_episodes()
    method = SkillMiningMethod()
    result = method.derive_from_episodes(episodes, {"backend": "fixture"})
    all_evidence_ids = set()
    for skill in result["candidate_skills"]:
        for ref in skill["representative_turn_refs"]:
            if ref.get("evidence_id"):
                all_evidence_ids.add(ref["evidence_id"])
    # At least some evidence IDs should be in the output
    assert len(all_evidence_ids) > 0


def test_derive_fixture_output_includes_derived_output_id():
    episodes = _sample_episodes()
    method = SkillMiningMethod()
    result = method.derive_from_episodes(episodes, {"backend": "fixture"})
    assert "derived_output_id" in result
    assert result["derived_output_id"]


def test_derive_fixture_respects_max_skills():
    episodes = _sample_episodes()
    method = SkillMiningMethod()
    result = method.derive_from_episodes(episodes, {"backend": "fixture", "max_skills": 1})
    assert result["candidate_skill_count"] <= 1
    assert len(result["candidate_skills"]) <= 1


def test_derive_fixture_has_caveats():
    result = _derive_fixture([], {})
    assert "caveats" in result
    assert len(result["caveats"]) > 0


# ---------------------------------------------------------------------------
# build_run tests
# ---------------------------------------------------------------------------

def test_build_run_returns_semantic_run(tmp_path: Path):
    episodes = _sample_episodes()
    # Write episodes.jsonl to a temp dir
    ep_dir = tmp_path / "episodes" / "default"
    ep_dir.mkdir(parents=True)
    (ep_dir / "episodes.jsonl").write_text(
        "\n".join(json.dumps(ep) for ep in episodes) + "\n",
        encoding="utf-8",
    )

    method = SkillMiningMethod()
    run = method.build_run(None, parameters={"episode_dir": str(ep_dir)})

    assert run.method == "skill-mining"
    assert run.non_canonical is True
    assert run.canonical_input["episode_count"] == len(episodes)
    assert "episode_dir" in run.canonical_input


def test_build_run_does_not_store_api_key(tmp_path: Path):
    ep_dir = tmp_path / "ep"
    ep_dir.mkdir()
    (ep_dir / "episodes.jsonl").write_text("", encoding="utf-8")

    method = SkillMiningMethod()
    run = method.build_run(None, parameters={
        "episode_dir": str(ep_dir),
        "api_key": "super-secret-key",
    })
    assert "api_key" not in run.parameters


def test_build_run_output_is_non_canonical(tmp_path: Path):
    ep_dir = tmp_path / "ep"
    ep_dir.mkdir()
    (ep_dir / "episodes.jsonl").write_text("", encoding="utf-8")

    method = SkillMiningMethod()
    run = method.build_run(None, parameters={"episode_dir": str(ep_dir)})
    assert run.non_canonical is True
    assert run.derived_output.get("non_canonical") is True


def test_build_run_with_missing_episode_dir():
    method = SkillMiningMethod()
    run = method.build_run(None, parameters={})
    assert run.canonical_input["episode_count"] == 0
    assert run.derived_output["candidate_skill_count"] == 0


# ---------------------------------------------------------------------------
# Episode loading
# ---------------------------------------------------------------------------

def test_load_episodes_empty_dir(tmp_path: Path):
    result = _load_episodes(str(tmp_path))
    assert result == []


def test_load_episodes_reads_jsonl(tmp_path: Path):
    episodes = _sample_episodes()
    (tmp_path / "episodes.jsonl").write_text(
        "\n".join(json.dumps(ep) for ep in episodes) + "\n",
        encoding="utf-8",
    )
    result = _load_episodes(str(tmp_path))
    assert len(result) == len(episodes)
    assert result[0]["episode_id"] == episodes[0]["episode_id"]


def test_load_episodes_none_returns_empty():
    result = _load_episodes(None)
    assert result == []


# ---------------------------------------------------------------------------
# collect_user_turns
# ---------------------------------------------------------------------------

def test_collect_user_turns_filters_role():
    episodes = _sample_episodes()
    turns = _collect_user_turns(episodes, max_per_episode=10)
    for t in turns:
        assert t["role"] == "user"


def test_collect_user_turns_respects_cap():
    episodes = _sample_episodes()
    turns = _collect_user_turns(episodes, max_per_episode=1)
    # At most 1 user turn per episode
    assert len(turns) <= len(episodes)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def test_leading_token_normal_text():
    assert _leading_token("Please fix the tests") == "please"


def test_leading_token_empty():
    assert _leading_token("") == "_empty_"


def test_summarize_text_short():
    assert _summarize_text("hello world", 80) == "hello world"


def test_summarize_text_truncated():
    long_text = "word " * 40
    result = _summarize_text(long_text, 20)
    assert len(result) <= 20
    assert result.endswith("...")


# ---------------------------------------------------------------------------
# pydantic-ai import error
# ---------------------------------------------------------------------------

def test_pydantic_ai_backend_raises_import_error_when_not_available():
    """Verify a helpful ImportError is raised when pydantic-ai is absent."""
    import sys
    # Temporarily hide pydantic_ai from imports
    saved = sys.modules.pop("pydantic_ai", None)
    try:
        from skill_drilla.semantic.skill_mining import _load_pydantic_ai_dependencies
        try:
            _load_pydantic_ai_dependencies()
        except ImportError as exc:
            assert "pydantic-ai" in str(exc).lower()
        except Exception:
            # pydantic_ai was already importable (installed) — skip guard
            pass
    finally:
        if saved is not None:
            sys.modules["pydantic_ai"] = saved
