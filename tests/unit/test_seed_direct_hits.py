from pathlib import Path

from skill_drilla.seed import collect_direct_hits


FIXTURE_VIEW_DIR = Path(__file__).resolve().parents[2] / "artifacts/chat-analysis/views/debug_included_and_excluded"


def test_collect_direct_hits_returns_traceable_matches_and_recurrence():
    run = collect_direct_hits(FIXTURE_VIEW_DIR, "pipeline")

    assert run.seed_term == "pipeline"
    assert run.hits
    assert run.recurrence["raw_occurrences"] == len(run.hits)
    first = run.hits[0].to_dict()
    assert {"evidence_id", "session_id", "source_file", "source_line", "source_anchor", "matched_terms"} <= set(first)
    assert any(session["hit_count"] >= 1 for session in run.related_sessions)


def test_collect_direct_hits_supports_phrase_queries():
    run = collect_direct_hits(FIXTURE_VIEW_DIR, "pipeline report")

    assert run.parsed_query["terms"][0]["is_phrase"] is True
    assert all("pipeline report" in (hit.content_text or "").casefold() for hit in run.hits)
