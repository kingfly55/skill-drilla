import json
from pathlib import Path

from skill_drilla.search import SearchFilters, inspect_evidence, parse_query, run_search, write_search_result


FIXTURE_VIEW_DIR = Path(__file__).resolve().parents[2] / "artifacts/chat-analysis/views/debug_included_and_excluded"


def test_run_search_returns_recurrence_and_representative_examples(tmp_path: Path):
    result = run_search(FIXTURE_VIEW_DIR, parse_query("pipeline AND report"), SearchFilters())

    assert result.view_name == "debug_included_and_excluded"
    assert result.recurrence["raw_occurrences"] >= 1
    assert result.summary["total_matches"] == len(result.matches)
    assert len(result.summary["representative_examples"]) <= 3
    assert all({"evidence_id", "session_id", "source_file", "source_anchor"} <= set(match.to_dict()) for match in result.matches[:3])

    artifacts = write_search_result(tmp_path / "search", result)
    payload = json.loads(Path(artifacts["query_result"]).read_text(encoding="utf-8"))
    assert payload["filters"] == {
        "project_slugs": [],
        "session_ids": [],
        "semantic_classes": [],
        "include_subagents": None,
        "limit": None,
    }
    assert payload["reproducibility"]["view_dir"] == str(FIXTURE_VIEW_DIR)


def test_run_search_honors_filters():
    result = run_search(
        FIXTURE_VIEW_DIR,
        parse_query("pipeline AND report"),
        SearchFilters(project_slugs=("-home-user",), include_subagents=False),
    )

    assert result.matches
    assert all(match.project_slug == "-home-user" for match in result.matches)
    assert all(match.session_role != "subagent" for match in result.matches)


def test_inspect_evidence_returns_surrounding_context():
    result = run_search(FIXTURE_VIEW_DIR, parse_query("pipeline AND report"), SearchFilters())
    inspection = inspect_evidence(FIXTURE_VIEW_DIR, result.matches[0].evidence_id, context=1)

    assert inspection.evidence_id == result.matches[0].evidence_id
    assert inspection.row["inspection"]["source_anchor"] == inspection.source_anchor
    assert len(inspection.context_before) <= 1
    assert len(inspection.context_after) <= 1
