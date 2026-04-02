from skill_drilla.report import rank_findings, score_finding


def _finding(*, finding_id: str, title: str, raw: int, sessions: int, projects: int, evidence: int):
    return {
        "finding_id": finding_id,
        "title": title,
        "detector": "repeated_instructions",
        "category": "repeated_instructions",
        "summary": "summary",
        "recurrence": {
            "raw_occurrences": raw,
            "distinct_sessions": sessions,
            "distinct_projects": projects,
            "distinct_evidence": evidence,
        },
        "recurrence_basis": {
            "raw_occurrences": "count every included view row",
            "distinct_sessions": "count unique session_id values",
            "distinct_projects": "count unique project_id values",
            "distinct_evidence": "count unique evidence_id values",
        },
        "evidence": [],
        "detector_metadata": {"version": "1.0", "ruleset": "repeated_instructions"},
        "diagnostics": {"candidate_key": title, "qualified_evidence_count": evidence},
        "caveats": [],
    }



def test_score_finding_uses_explicit_weighted_metrics():
    finding = _finding(
        finding_id="a" * 64,
        title="A",
        raw=4,
        sessions=3,
        projects=2,
        evidence=4,
    )

    ranked = score_finding(finding)

    assert ranked["score"] == 35.0
    assert ranked["weighted_metrics"] == {
        "distinct_sessions": 15.0,
        "raw_occurrences": 12.0,
        "distinct_projects": 4.0,
        "distinct_evidence": 4.0,
    }
    assert ranked["criteria_summary"]["primary"] == "distinct_sessions"



def test_rank_findings_prioritizes_session_spread_then_frequency():
    findings = [
        _finding(finding_id="a" * 64, title="Lower spread higher raw", raw=9, sessions=2, projects=2, evidence=9),
        _finding(finding_id="b" * 64, title="Higher spread", raw=4, sessions=3, projects=1, evidence=4),
        _finding(finding_id="c" * 64, title="Tie breaker title", raw=4, sessions=3, projects=1, evidence=4),
    ]

    ranked = rank_findings(findings)

    assert [item.finding["finding_id"] for item in ranked] == ["b" * 64, "c" * 64, "a" * 64]
    assert [item.rank for item in ranked] == [1, 2, 3]
    assert ranked[0].ranking_factors["sort_tuple"][0] == 3
