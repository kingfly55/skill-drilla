"""Unit tests for deterministic episode builder."""

from skill_drilla.episodes.builder import (
    _collapse_raw_event,
    _group_by_root_session,
    build_episodes,
)


def _user_nl_row(
    session_id: str = "s1",
    root_session_id: str | None = "s1",
    raw_event_id: str = "ev1",
    raw_event_index: int = 1,
    content_text: str = "fix the bug",
    evidence_id: str = "e1",
    session_role: str = "root",
    **extra,
) -> dict:
    return {
        "evidence_id": evidence_id,
        "session_id": session_id,
        "root_session_id": root_session_id,
        "parent_session_id": None,
        "raw_event_id": raw_event_id,
        "raw_event_index": raw_event_index,
        "semantic_class": "user_natural_language",
        "content_text": content_text,
        "session_role": session_role,
        "project_id": "proj1",
        "project_slug": "my-project",
        "tool_name": None,
        "tool_use_id": None,
        "is_error": None,
        **extra,
    }


def _assistant_nl_row(
    session_id: str = "s1",
    root_session_id: str | None = "s1",
    raw_event_id: str = "ev2",
    raw_event_index: int = 2,
    content_text: str = "I will fix it now",
    evidence_id: str = "e2",
    **extra,
) -> dict:
    return {
        "evidence_id": evidence_id,
        "session_id": session_id,
        "root_session_id": root_session_id,
        "parent_session_id": None,
        "raw_event_id": raw_event_id,
        "raw_event_index": raw_event_index,
        "semantic_class": "assistant_natural_language",
        "content_text": content_text,
        "session_role": "root",
        "project_id": "proj1",
        "project_slug": "my-project",
        "tool_name": None,
        "tool_use_id": None,
        "is_error": None,
        **extra,
    }


def _tool_call_row(
    session_id: str = "s1",
    root_session_id: str | None = "s1",
    raw_event_id: str = "ev2",
    raw_event_index: int = 2,
    tool_use_id: str = "toolu_1",
    tool_name: str = "Bash",
    content_text: str = "ls",
    evidence_id: str = "tc1",
    **extra,
) -> dict:
    return {
        "evidence_id": evidence_id,
        "session_id": session_id,
        "root_session_id": root_session_id,
        "raw_event_id": raw_event_id,
        "raw_event_index": raw_event_index,
        "semantic_class": "tool_call",
        "content_text": content_text,
        "session_role": "root",
        "project_id": "proj1",
        "project_slug": "my-project",
        "tool_name": tool_name,
        "tool_use_id": tool_use_id,
        "is_error": None,
        **extra,
    }


def _tool_result_row(
    session_id: str = "s1",
    root_session_id: str | None = "s1",
    raw_event_id: str = "ev2",
    raw_event_index: int = 2,
    tool_use_id: str = "toolu_1",
    content_text: str = "file1.py",
    evidence_id: str = "tr1",
    is_error: bool = False,
    **extra,
) -> dict:
    return {
        "evidence_id": evidence_id,
        "session_id": session_id,
        "root_session_id": root_session_id,
        "raw_event_id": raw_event_id,
        "raw_event_index": raw_event_index,
        "semantic_class": "tool_result",
        "content_text": content_text,
        "session_role": "root",
        "project_id": "proj1",
        "project_slug": "my-project",
        "tool_name": None,
        "tool_use_id": tool_use_id,
        "is_error": is_error,
        **extra,
    }


# --- grouping ---

def test_group_by_root_session_uses_root_session_id_when_present():
    rows = [
        _user_nl_row(session_id="s1", root_session_id="root1", raw_event_id="ev1"),
        _assistant_nl_row(session_id="s1", root_session_id="root1", raw_event_id="ev2"),
    ]
    groups = _group_by_root_session(rows)
    assert list(groups.keys()) == ["root1"]
    assert len(groups["root1"]) == 2


def test_group_by_root_session_falls_back_to_session_id():
    rows = [
        _user_nl_row(session_id="solo1", root_session_id=None, raw_event_id="ev1"),
        _user_nl_row(session_id="solo2", root_session_id=None, raw_event_id="ev2"),
    ]
    groups = _group_by_root_session(rows)
    assert "solo1" in groups
    assert "solo2" in groups
    assert len(groups) == 2


# --- tool collapsing ---

def test_tool_call_and_result_collapse_into_tool_context():
    raw_event_id = "ev_tool"
    rows = [
        _assistant_nl_row(raw_event_id=raw_event_id, raw_event_index=3, evidence_id="nl1"),
        _tool_call_row(raw_event_id=raw_event_id, raw_event_index=3, tool_use_id="t1", evidence_id="tc1"),
        _tool_result_row(raw_event_id=raw_event_id, raw_event_index=3, tool_use_id="t1", evidence_id="tr1"),
    ]
    nl_row, tool_contexts = _collapse_raw_event(raw_event_id, rows)
    assert nl_row is not None
    assert len(tool_contexts) == 1
    tc = tool_contexts[0]
    assert tc.tool_use_id == "t1"
    assert tc.call_text == "ls"
    assert tc.result_text == "file1.py"
    assert tc.call_evidence_id == "tc1"
    assert tc.result_evidence_id == "tr1"


def test_orphaned_tool_result_produces_context_without_call():
    raw_event_id = "ev_orphan"
    rows = [
        _tool_result_row(raw_event_id=raw_event_id, tool_use_id="t_orphan", evidence_id="tr_orphan"),
    ]
    nl_row, tool_contexts = _collapse_raw_event(raw_event_id, rows)
    assert nl_row is None
    assert len(tool_contexts) == 1
    tc = tool_contexts[0]
    assert tc.call_text is None
    assert tc.call_evidence_id is None
    assert tc.result_text == "file1.py"


# --- turn compression ---

def test_assistant_turn_has_compressed_text():
    rows = [_assistant_nl_row(content_text="I will fix the bug by editing the file and running tests")]
    episodes, _ = build_episodes(rows)
    assert len(episodes) == 1
    turn = episodes[0].turns[0]
    assert turn.role == "assistant"
    assert turn.compressed_text is not None


def test_user_turn_has_no_compressed_text():
    rows = [_user_nl_row(content_text="please fix the bug")]
    episodes, _ = build_episodes(rows)
    assert len(episodes) == 1
    turn = episodes[0].turns[0]
    assert turn.role == "user"
    assert turn.compressed_text is None


# --- subagent handling ---

def test_subagent_rows_appear_as_child_refs_not_turns():
    rows = [
        _user_nl_row(session_id="root1", root_session_id="root1", raw_event_id="ev1"),
        # subagent row linked to root1
        _assistant_nl_row(
            session_id="sub1",
            root_session_id="root1",
            raw_event_id="ev_sub",
            raw_event_index=10,
            session_role="subagent",
            evidence_id="sub_e1",
        ),
    ]
    episodes, _ = build_episodes(rows)
    # Only one episode (keyed by root1)
    assert len(episodes) == 1
    ep = episodes[0]
    # Subagent content not in turns
    assert ep.turn_count == 1
    assert ep.turns[0].session_role == "root"
    # Subagent session_id in child_episode_refs
    assert "sub1" in ep.child_episode_refs


# --- provenance invariant ---

def test_provenance_fields_never_stripped():
    rows = [
        _user_nl_row(),
        _assistant_nl_row(),
    ]
    episodes, _ = build_episodes(rows)
    for ep in episodes:
        for turn in ep.turns:
            assert turn.evidence_id
            assert turn.raw_event_id
            assert turn.raw_event_index is not None
            assert turn.session_id


# --- determinism ---

def test_build_episodes_is_deterministic():
    rows = [
        _user_nl_row(raw_event_id="ev1", evidence_id="e1"),
        _assistant_nl_row(raw_event_id="ev2", evidence_id="e2"),
    ]
    episodes_a, index_a = build_episodes(rows)
    episodes_b, index_b = build_episodes(rows)
    assert [e.to_dict() for e in episodes_a] == [e.to_dict() for e in episodes_b]
    assert index_a.to_dict() == index_b.to_dict()


# --- non-NL rows skipped ---

def test_non_nl_non_tool_rows_are_skipped():
    rows = [
        _user_nl_row(raw_event_id="ev1", evidence_id="e1"),
        {
            "evidence_id": "skip1",
            "session_id": "s1",
            "root_session_id": "s1",
            "raw_event_id": "ev_skip",
            "raw_event_index": 99,
            "semantic_class": "thinking",
            "content_text": "internal reasoning",
            "session_role": "root",
        },
    ]
    episodes, index = build_episodes(rows)
    assert index.turn_count == 1  # only the user NL row becomes a turn


# --- empty input ---

def test_build_episodes_empty_input():
    episodes, index = build_episodes([])
    assert episodes == ()
    assert index.episode_count == 0
    assert index.turn_count == 0
