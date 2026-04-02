from skill_drilla.notebooks.loaders import recurrence_snapshot
from skill_drilla.views import compute_recurrence_counts


def test_multi_evidence_same_raw_event_does_not_inflate_distinct_evidence():
    records = [
        {"evidence_id": "e1", "session_id": "s1", "project_id": "p1", "raw_event_id": "r1"},
        {"evidence_id": "e2", "session_id": "s1", "project_id": "p1", "raw_event_id": "r1"},
        {"evidence_id": "e3", "session_id": "s2", "project_id": "p1", "raw_event_id": "r2"},
    ]

    counts = compute_recurrence_counts(records)

    assert counts["raw_occurrences"] == 3
    assert counts["distinct_evidence"] == 3
    assert counts["distinct_sessions"] == 2
    assert counts["distinct_projects"] == 1


def test_recurrence_snapshot_matches_core_recurrence_metrics():
    records = [
        {"evidence_id": "e1", "session_id": "s1", "project_id": "p1"},
        {"evidence_id": "e1", "session_id": "s1", "project_id": "p1"},
        {"evidence_id": "e2", "session_id": "s2", "project_id": "p2"},
    ]

    assert recurrence_snapshot(records) == compute_recurrence_counts(records)


def test_session_repetition_counts_once_per_distinct_session():
    records = [
        {"evidence_id": f"e{i}", "session_id": "s1", "project_id": "p1"}
        for i in range(5)
    ] + [
        {"evidence_id": "e5", "session_id": "s2", "project_id": "p1"}
    ]

    counts = compute_recurrence_counts(records)

    assert counts["raw_occurrences"] == 6
    assert counts["distinct_sessions"] == 2
    assert counts["distinct_projects"] == 1
