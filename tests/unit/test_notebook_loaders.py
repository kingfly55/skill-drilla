import json
from pathlib import Path

from skill_drilla.notebooks import (
    collect_evidence_by_status,
    load_corpus_view,
    load_detector_run,
    load_evidence,
    load_inventory,
    load_normalization_diagnostics,
    load_parse_diagnostics,
    load_report_metadata,
    load_seed_run,
    load_semantic_run,
    load_validation_summary,
    recurrence_snapshot,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = REPO_ROOT / "artifacts" / "chat-analysis"



def test_load_inventory_from_canonical_discovery_artifact():
    inventory_path = ARTIFACTS / "discovery" / "smoke-a" / "session_inventory.jsonl"
    rows = load_inventory(inventory_path)

    assert rows
    assert {"project_id", "project_slug", "session_id", "transcript_path"} <= set(rows[0])



def test_load_parse_diagnostics_from_canonical_artifact():
    diagnostics = load_parse_diagnostics(ARTIFACTS / "parse" / "smoke" / "parse_diagnostics.json")

    assert {"aggregate", "files"} <= set(diagnostics)
    assert diagnostics["aggregate"]["files"] >= 1



def test_load_validation_summary_from_validation_bundle():
    summary = load_validation_summary(ARTIFACTS / "validation" / "full-smoke" / "validation_summary.json")

    assert {"views", "detectors", "reports", "normalize", "parse", "discovery"} <= set(summary)
    assert summary["reports"]["section_count"] >= 1
    assert "user_nl_root_only" in summary["views"]["views"]



def test_load_normalization_diagnostics_from_validation_bundle():
    diagnostics = load_normalization_diagnostics(
        ARTIFACTS / "validation" / "full-smoke" / "normalize" / "normalization_diagnostics.json"
    )

    assert {"semantic_class_counts", "inclusion_status_counts", "transform_outcome_counts", "ambiguous_items"} <= set(diagnostics)
    assert diagnostics["ambiguous_items"]



def test_load_semantic_run_from_non_canonical_artifact():
    semantic_run = load_semantic_run(ARTIFACTS / "semantic" / "clustering-smoke" / "semantic_run.json")

    assert semantic_run["non_canonical"] is True
    assert {"canonical_input", "derived_output", "parameters"} <= set(semantic_run)
    assert semantic_run["derived_output"]["kind"] == "clusters"



def test_load_evidence_and_group_by_inclusion_status():
    evidence = load_evidence(ARTIFACTS / "normalize" / "smoke" / "evidence.jsonl", limit=50)
    grouped = collect_evidence_by_status(evidence)

    assert evidence
    assert "excluded_default" in grouped or "included_primary" in grouped
    assert {"evidence_id", "inclusion_status", "project_id", "session_id"} <= set(evidence[0])



def test_recurrence_snapshot_matches_view_summary_for_limited_rows():
    view = load_corpus_view(ARTIFACTS / "views" / "user_nl_root_only", limit=25)
    records = [row["evidence"] for row in view["rows"]]

    snapshot = recurrence_snapshot(records)
    assert snapshot["raw_occurrences"] == len(records)
    assert snapshot["distinct_evidence"] == len({row["evidence_id"] for row in records})



def test_load_corpus_view_preserves_canonical_summary_metadata():
    view = load_corpus_view(ARTIFACTS / "views" / "debug_included_and_excluded", limit=10)

    assert view["view_name"] == "debug_included_and_excluded"
    assert view["summary"]["include_excluded_records"] is True
    assert view["summary"]["recurrence_basis"]["distinct_sessions"] == "count unique session_id values"
    assert view["rows"]
    assert {"view_name", "view_row_id", "inspection", "evidence"} <= set(view["rows"][0])



def test_load_seed_run_detector_run_and_report_metadata_from_canonical_paths():
    seed_run = load_seed_run(ARTIFACTS / "seed" / "pipeline" / "seed_run.json")
    detector_run = load_detector_run(ARTIFACTS / "detectors" / "repeated_instructions" / "detector_run.json")
    report_metadata = load_report_metadata(ARTIFACTS / "reports" / "repeated_instructions" / "report_metadata.json")

    assert seed_run["view_name"] == "user_nl_root_only"
    assert detector_run["detector"] == "repeated_instructions"
    assert report_metadata["source_detector_runs"][0]["detector"] == "repeated_instructions"
    assert report_metadata["sections"]



def test_notebook_visible_recurrence_matches_detector_run_exactly():
    detector_run = load_detector_run(ARTIFACTS / "detectors" / "repeated_instructions" / "detector_run.json")
    first_finding = detector_run["findings"][0]

    assert set(first_finding["recurrence"]) == {
        "raw_occurrences",
        "distinct_sessions",
        "distinct_projects",
        "distinct_evidence",
    }
    assert first_finding["recurrence_basis"]["raw_occurrences"] == "count every included view row"



def test_debug_view_keeps_included_excluded_and_ambiguous_material_inspectable():
    evidence = load_evidence(ARTIFACTS / "normalize" / "smoke" / "evidence.jsonl", limit=5000)
    statuses = {row["inclusion_status"] for row in evidence}

    assert "excluded_default" in statuses
    assert "ambiguous" in statuses
    assert any(row["semantic_class"] == "unknown_ambiguous" for row in evidence)



def test_iterative_insight_notebook_references_canonical_validation_artifacts():
    notebook_path = REPO_ROOT / "notebooks" / "05_iterative_insight_analysis.ipynb"
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    cell_sources = ["".join(cell.get("source", [])) for cell in notebook["cells"]]
    notebook_text = "\n".join(cell_sources)

    assert notebook_path.exists()
    assert notebook["nbformat"] == 4
    assert "skill_drilla.notebooks" in notebook_text
    assert "artifacts/chat-analysis/validation/full-smoke" in notebook_text
    assert "non-canonical" in notebook_text
    assert "semantic_run.json" in notebook_text
