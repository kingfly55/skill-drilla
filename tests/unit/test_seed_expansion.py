from pathlib import Path

from skill_drilla.seed import build_seed_run


FIXTURE_VIEW_DIR = Path(__file__).resolve().parents[2] / "artifacts/chat-analysis/views/debug_included_and_excluded"


def test_build_seed_run_separates_direct_and_expansion_hits():
    run = build_seed_run(FIXTURE_VIEW_DIR, seed_term="pipeline", window=2, strategy="cooccurrence", expansion_limit=10)

    assert run.view_name == "debug_included_and_excluded"
    assert isinstance(run.direct_hits, list)
    assert isinstance(run.expansion_hits, list)
    assert run.direct_hits is not run.expansion_hits
    assert run.parameters["strategy"] == "cooccurrence"
    assert run.parameters["window"] == 2
    assert {"direct", "expansion"} <= set(run.related_sessions)


def test_build_seed_run_supports_adjacency_strategy():
    run = build_seed_run(FIXTURE_VIEW_DIR, seed_term="pipeline", window=2, strategy="adjacency", expansion_limit=10)

    assert run.expansion_hits
    assert all(hit["expansion_strategy"] == "adjacency" for hit in run.expansion_hits)
    assert all(hit["relationship"] == "adjacent_to_direct_hit" for hit in run.expansion_hits)


def test_build_seed_run_supports_session_neighborhood_strategy():
    run = build_seed_run(FIXTURE_VIEW_DIR, seed_term="pipeline", window=2, strategy="session_neighborhood", expansion_limit=10)

    assert run.expansion_hits
    assert all(hit["expansion_strategy"] == "session_neighborhood" for hit in run.expansion_hits)
    assert run.expansion_recurrence["raw_occurrences"] == len(run.expansion_hits)
