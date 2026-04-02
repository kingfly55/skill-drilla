from skill_drilla.views import STANDARD_VIEW_DEFINITIONS, ViewFilterPolicy, apply_view_policy, build_inspection_record


def make_record(**overrides):
    record = {
        "evidence_id": "e" * 64,
        "project_id": "p" * 64,
        "session_id": "s" * 64,
        "session_role": "root",
        "source_file": "/tmp/source.jsonl",
        "source_line": 42,
        "semantic_class": "user_natural_language",
        "inclusion_status": "included_primary",
    }
    record.update(overrides)
    return record


def test_root_only_user_view_excludes_subagent_records():
    definition = STANDARD_VIEW_DEFINITIONS["user_nl_root_only"]
    decision = apply_view_policy(make_record(session_role="subagent"), definition.filter_policy)
    assert decision.include is False
    assert decision.reason == "session_role_excluded:subagent"


def test_debug_view_includes_excluded_and_ambiguous_records():
    definition = STANDARD_VIEW_DEFINITIONS["debug_included_and_excluded"]
    excluded = apply_view_policy(
        make_record(semantic_class="tool_call", inclusion_status="excluded_default"),
        definition.filter_policy,
    )
    ambiguous = apply_view_policy(
        make_record(semantic_class="unknown_ambiguous", inclusion_status="ambiguous", session_role="unknown"),
        definition.filter_policy,
    )
    assert excluded.include is True
    assert ambiguous.include is True


def test_assistant_view_rejects_user_evidence():
    definition = STANDARD_VIEW_DEFINITIONS["assistant_nl_root_only"]
    decision = apply_view_policy(make_record(), definition.filter_policy)
    assert decision.include is False
    assert decision.reason == "inclusion_status_excluded:included_primary"


def test_inspection_record_preserves_anchor_fields():
    inspection = build_inspection_record(make_record())
    assert inspection == {
        "evidence_id": "e" * 64,
        "session_id": "s" * 64,
        "source_file": "/tmp/source.jsonl",
        "source_line": 42,
        "source_anchor": "/tmp/source.jsonl:42",
    }


def test_default_policy_excludes_ambiguous_when_not_allowed():
    policy = ViewFilterPolicy(allow_ambiguous=False)
    decision = apply_view_policy(make_record(inclusion_status="ambiguous"), policy)
    assert decision.include is False
    assert decision.reason == "ambiguous_excluded"
