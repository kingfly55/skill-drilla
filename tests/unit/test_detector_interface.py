import json
from pathlib import Path

from skill_drilla.detect import DETECTOR_REGISTRY, get_detector


VIEW_DIR = Path(__file__).resolve().parents[2] / "artifacts/chat-analysis/views/user_nl_root_only"


def test_detector_registry_exposes_required_categories():
    assert set(DETECTOR_REGISTRY) == {
        "repeated_instructions",
        "workflow_patterns",
        "corrections_frustrations",
        "refinement_requests",
        "agent_failures",
        "output_quality",
        "change_requests",
    }


def test_detector_run_emits_structured_findings_and_diagnostics(tmp_path: Path):
    detector = get_detector("repeated_instructions")
    run = detector.build_run(VIEW_DIR)

    assert run.detector == "repeated_instructions"
    assert run.view_name == "user_nl_root_only"
    assert {"min_raw_occurrences", "min_distinct_sessions", "max_evidence"} <= set(run.settings)
    assert {"view_id", "rows_scanned", "qualified_findings", "recurrence_basis"} <= set(run.diagnostics)
    assert isinstance(run.findings, tuple)
    if run.findings:
        finding = run.findings[0].to_dict()
        assert {
            "finding_id",
            "detector",
            "category",
            "title",
            "summary",
            "recurrence",
            "recurrence_basis",
            "evidence",
            "detector_metadata",
            "diagnostics",
            "caveats",
        } <= set(finding)
        assert finding["detector_metadata"]["version"] == detector.version
        assert finding["recurrence"]["distinct_sessions"] >= 1
        assert finding["evidence"]
        assert {"source_anchor", "qualification", "excerpt"} <= set(finding["evidence"][0])

    out = tmp_path / "detector_run.json"
    out.write_text(json.dumps(run.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["detector"] == "repeated_instructions"
