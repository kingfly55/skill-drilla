import json
from pathlib import Path

from skill_drilla.discovery.inventory import DiscoverySummary, discover_corpus, inventory_jsonl_lines
from skill_drilla.discovery.scoping import apply_scope


FIXTURE_ROOT = Path("tests/fixtures/discovery")


def test_discover_corpus_builds_inventory_from_fixture():
    result = discover_corpus(FIXTURE_ROOT)

    assert len(result.projects) == 1
    assert result.projects[0].project_slug == "basic-project"
    assert result.projects[0].metadata_paths == (
        "tests/fixtures/discovery/basic-project/bridge-pointer.json",
    )
    assert len(result.records) == 2

    root_record = next(record for record in result.records if record.session_role == "root")
    subagent_record = next(record for record in result.records if record.session_role == "subagent")

    assert root_record.project_id == result.projects[0].project_id
    assert root_record.root_session_id == root_record.session_id
    assert root_record.parent_session_id is None
    assert subagent_record.parent_session_id == root_record.session_id
    assert subagent_record.root_session_id == root_record.session_id
    assert subagent_record.metadata_path.endswith("agent-a1111111111111111.meta.json")


def test_apply_scope_excludes_subagents_by_default():
    result = discover_corpus(FIXTURE_ROOT)
    scoped = apply_scope(
        result.records,
        {
            "include_projects": [],
            "exclude_projects": [],
            "include_subagents": False,
        },
    )

    assert len(scoped.records) == 1
    assert scoped.records[0].session_role == "root"
    assert len(scoped.excluded_records) == 1
    assert scoped.exclusion_reasons == {"excluded_subagent": 1}


def test_inventory_summary_and_jsonl_are_deterministic():
    result = discover_corpus(FIXTURE_ROOT)
    scoped = apply_scope(
        result.records,
        {
            "include_projects": [],
            "exclude_projects": [],
            "include_subagents": True,
        },
    )
    summary = DiscoverySummary.from_records(result.records, scoped.excluded_records)

    lines = inventory_jsonl_lines(result.records)
    reparsed = [json.loads(line) for line in lines]

    assert lines == inventory_jsonl_lines(result.records)
    assert reparsed[0]["project_slug"] == "basic-project"
    assert summary.to_dict()["projects"] == 1
    assert summary.to_dict()["sessions"] == 2
