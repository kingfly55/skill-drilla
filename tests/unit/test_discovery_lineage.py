from pathlib import Path

from skill_drilla.discovery.lineage import derive_lineage


def test_derive_lineage_for_root_session():
    project_root = Path("/tmp/project")
    transcript_path = project_root / "12345678-1234-1234-1234-123456789abc.jsonl"

    lineage = derive_lineage(project_root, transcript_path)

    assert lineage.session_role == "root"
    assert lineage.lineage_state == "confirmed"
    assert lineage.parent_session_key is None
    assert lineage.root_session_key == "12345678-1234-1234-1234-123456789abc"


def test_derive_lineage_for_subagent_session():
    project_root = Path("/tmp/project")
    transcript_path = project_root / "12345678-1234-1234-1234-123456789abc" / "subagents" / "agent-a1111111111111111.jsonl"

    lineage = derive_lineage(project_root, transcript_path)

    assert lineage.session_role == "subagent"
    assert lineage.lineage_state == "confirmed"
    assert lineage.parent_session_key == "12345678-1234-1234-1234-123456789abc"
    assert lineage.root_session_key == "12345678-1234-1234-1234-123456789abc"
    assert lineage.subagent_id == "agent-a1111111111111111"


def test_derive_lineage_for_top_level_subagent_without_parent():
    project_root = Path("/tmp/project")
    transcript_path = project_root / "agent-a1111111111111111.jsonl"

    lineage = derive_lineage(project_root, transcript_path)

    assert lineage.session_role == "subagent"
    assert lineage.lineage_state == "unknown"
    assert lineage.parent_session_key is None
    assert lineage.root_session_key is None
