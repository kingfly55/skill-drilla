"""Unit tests for episode data models."""

from skill_drilla.episodes.model import Episode, EpisodeIndex, EpisodeTurn, ToolContext


def _make_tool_context(**overrides) -> ToolContext:
    defaults = dict(
        tool_use_id="toolu_abc",
        tool_name="Bash",
        call_text="ls -la",
        result_text="total 0",
        is_error=False,
        call_evidence_id="a" * 64,
        result_evidence_id="b" * 64,
        raw_event_id="c" * 64,
        raw_event_index=1,
        session_id="d" * 64,
    )
    defaults.update(overrides)
    return ToolContext(**defaults)


def _make_turn(episode_id: str = "e" * 64, **overrides) -> EpisodeTurn:
    defaults = dict(
        turn_id="f" * 64,
        episode_id=episode_id,
        turn_index=0,
        role="user",
        content_text="please fix the bug",
        compressed_text=None,
        tool_context=(),
        evidence_id="1" * 64,
        raw_event_id="2" * 64,
        raw_event_index=1,
        session_id="3" * 64,
        root_session_id="4" * 64,
        parent_session_id=None,
        session_role="root",
    )
    defaults.update(overrides)
    return EpisodeTurn(**defaults)


def test_episode_turn_to_dict_preserves_provenance_fields():
    turn = _make_turn()
    d = turn.to_dict()
    for field in ("evidence_id", "raw_event_id", "raw_event_index", "session_id"):
        assert field in d
        assert d[field] is not None


def test_tool_context_to_dict_captures_call_and_result():
    tc = _make_tool_context()
    d = tc.to_dict()
    assert d["call_text"] == "ls -la"
    assert d["result_text"] == "total 0"
    assert d["tool_name"] == "Bash"
    assert d["tool_use_id"] == "toolu_abc"
    assert d["is_error"] is False
    assert d["call_evidence_id"] is not None
    assert d["result_evidence_id"] is not None


def test_episode_to_dict_serializes_lists_not_tuples():
    turn = _make_turn()
    ep = Episode(
        episode_id="e" * 64,
        root_session_id="r" * 64,
        project_id="p" * 64,
        project_slug="my-project",
        turn_count=1,
        turns=(turn,),
        child_episode_refs=("child-session-id",),
        session_ids=("root-session-id",),
    )
    d = ep.to_dict()
    assert isinstance(d["turns"], list)
    assert isinstance(d["child_episode_refs"], list)
    assert isinstance(d["session_ids"], list)
    assert d["turn_count"] == 1


def test_episode_index_to_dict_structure():
    index = EpisodeIndex(
        run_id="test-run",
        episode_count=2,
        turn_count=5,
        root_session_ids=("r1", "r2"),
        episode_ids=("e1", "e2"),
        child_ref_count=1,
    )
    d = index.to_dict()
    assert d["run_id"] == "test-run"
    assert d["episode_count"] == 2
    assert d["turn_count"] == 5
    assert isinstance(d["root_session_ids"], list)
    assert isinstance(d["episode_ids"], list)
    assert d["child_ref_count"] == 1
