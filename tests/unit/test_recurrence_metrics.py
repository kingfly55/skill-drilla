from skill_drilla.views import RECURRENCE_BASIS_DEFAULT, compute_recurrence_counts


def test_recurrence_counts_use_explicit_metric_names():
    counts = compute_recurrence_counts(
        [
            {"evidence_id": "e1", "session_id": "s1", "project_id": "p1"},
            {"evidence_id": "e1", "session_id": "s1", "project_id": "p1"},
            {"evidence_id": "e2", "session_id": "s2", "project_id": "p1"},
            {"evidence_id": "e3", "session_id": "s3", "project_id": "p2"},
        ]
    )
    assert counts == {
        "raw_occurrences": 4,
        "distinct_evidence": 3,
        "distinct_sessions": 3,
        "distinct_projects": 2,
    }


def test_recurrence_basis_documents_each_metric():
    assert set(RECURRENCE_BASIS_DEFAULT) == {
        "raw_occurrences",
        "distinct_evidence",
        "distinct_sessions",
        "distinct_projects",
    }
    assert "count every included view row" in RECURRENCE_BASIS_DEFAULT["raw_occurrences"]
