from pathlib import Path

from skill_drilla.detect import get_detector


VIEW_DIR = Path(__file__).resolve().parents[2] / "artifacts/chat-analysis/views/user_nl_root_only"


def test_all_required_detectors_run_on_canonical_view():
    detector_names = [
        "repeated_instructions",
        "workflow_patterns",
        "corrections_frustrations",
        "refinement_requests",
        "agent_failures",
        "output_quality",
        "change_requests",
    ]
    runs = {name: get_detector(name).build_run(VIEW_DIR) for name in detector_names}

    assert set(runs) == set(detector_names)
    assert all(run.view_name == "user_nl_root_only" for run in runs.values())
    assert runs["change_requests"].diagnostics["rows_scanned"] >= 1
    assert any(
        "analysis-system-management friction" in caveat
        for finding in runs["refinement_requests"].findings
        for caveat in finding.caveats
    )
    assert any(finding.recurrence["raw_occurrences"] >= 2 for finding in runs["change_requests"].findings)


def test_change_requests_and_repeated_instructions_surface_explicit_clusters():
    change_run = get_detector("change_requests").build_run(VIEW_DIR)
    repeated_run = get_detector("repeated_instructions").build_run(VIEW_DIR)

    assert change_run.findings
    assert repeated_run.findings
    assert all(finding.detector == "change_requests" for finding in change_run.findings)
    assert all(finding.detector == "repeated_instructions" for finding in repeated_run.findings)
    assert any("change request" in finding.title.lower() for finding in change_run.findings)
    assert any("repeated instruction" in finding.title.lower() for finding in repeated_run.findings)
