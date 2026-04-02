import json
from pathlib import Path

from skill_drilla.validate import run_validation


CONFIG = Path(__file__).resolve().parents[2] / "configs/chat-analysis.default.yaml"
PROJECTS = Path(__file__).resolve().parents[2] / "tests/fixtures/discovery"


def test_run_validation_writes_required_artifacts(tmp_path: Path):
    summary = run_validation(config_path=CONFIG, projects_root=PROJECTS, output_dir=tmp_path)

    assert {"discovery", "parse", "normalize", "views", "search", "seed", "detectors", "reports", "notebooks", "traceability"} <= set(summary)
    assert (tmp_path / "validation_summary.json").exists()
    assert (tmp_path / "traceability_samples.json").exists()
    assert (tmp_path / "performance_summary.json").exists()

    traceability = json.loads((tmp_path / "traceability_samples.json").read_text(encoding="utf-8"))
    performance = json.loads((tmp_path / "performance_summary.json").read_text(encoding="utf-8"))

    assert traceability
    assert {"report_section", "detector_run", "finding_id", "evidence_id", "raw_event_id", "source_file", "source_line"} <= set(traceability[0])
    assert {"streaming_memory_peak_mb", "validate_runtime_seconds"} <= set(performance)


def test_validation_summary_records_machine_readable_edge_case_outputs(tmp_path: Path):
    summary = run_validation(config_path=CONFIG, projects_root=PROJECTS, output_dir=tmp_path)

    assert "parse_failures" in summary["parse"]
    assert "classification_ambiguities" in summary["normalize"]
    assert "lineage_coverage" in summary["discovery"]
    assert "recurrence_edge_cases" in summary["views"]
    assert summary["traceability"]["sample_count"] >= 1
