from pathlib import Path

from skill_drilla.cli import STABLE_PIPELINE_COMMANDS, build_parser, main
from skill_drilla.validate import run_validation


EXPECTED_COMMANDS = [
    "discover",
    "parse",
    "normalize",
    "build-view",
    "search",
    "seed-expand",
    "detect",
    "report",
    "notebook-export",
    "semantic-run",
    "validate",
    "extract-episodes",
]


def test_stable_pipeline_commands_match_contract():
    assert STABLE_PIPELINE_COMMANDS == EXPECTED_COMMANDS


def test_parser_exposes_contract_commands():
    parser = build_parser()
    subparsers_action = next(action for action in parser._actions if action.dest == "command")
    for command in ["config", "manifest-smoke", "inspect-evidence", *EXPECTED_COMMANDS]:
        assert command in subparsers_action.choices


def test_search_command_runs_with_fixture_inputs(tmp_path: Path, capsys):
    view_dir = Path("artifacts/chat-analysis/views/debug_included_and_excluded")

    code = main([
        "search",
        "--view-dir",
        str(view_dir),
        "--query",
        "pipeline AND report",
        "--output-dir",
        str(tmp_path / "out"),
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert '"command": "search"' in out
    assert (tmp_path / "out" / "query_result.json").exists()


def test_inspect_evidence_command_prints_payload(capsys):
    view_dir = Path("artifacts/chat-analysis/views/debug_included_and_excluded")
    evidence_id = "6e5e7d94ed669f4fd2109594fbc39f9e8f9bf6c0d2fa42dbe869f9cdeb445a91"

    code = main([
        "inspect-evidence",
        "--view-dir",
        str(view_dir),
        "--evidence-id",
        evidence_id,
        "--context",
        "1",
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert evidence_id in out


def test_discover_command_runs_with_fixture(tmp_path: Path, capsys):
    code = main([
        "discover",
        "--config",
        "configs/chat-analysis.default.yaml",
        "--projects-root",
        "tests/fixtures/discovery",
        "--output-dir",
        str(tmp_path),
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert '"command": "discover"' in out
    assert (tmp_path / "session_inventory.jsonl").exists()


def test_parse_command_runs_with_fixture_inventory(tmp_path: Path, capsys):
    inventory = tmp_path / "inventory.jsonl"
    fixture = Path("tests/fixtures/parse/sample_session.jsonl")
    inventory.write_text(
        '{"project_id":"' + 'a' * 64 + '","project_slug":"fixture-project","session_id":"' + 'b' * 64 + '","session_key":"fixture-session","transcript_path":"' + str(fixture.resolve()) + '","transcript_relpath":"sample_session.jsonl","session_role":"root","lineage_state":"confirmed","parent_session_id":null,"root_session_id":"' + 'b' * 64 + '","observed_parent_session_key":null,"observed_root_session_key":"fixture-session","lineage_source":"fixture","subagent_id":null,"metadata_path":null,"transcript_format":"jsonl","transcript_size_bytes":1,"transcript_mtime_ns":1}\n',
        encoding="utf-8",
    )

    code = main([
        "parse",
        "--inventory",
        str(inventory),
        "--output-dir",
        str(tmp_path / "out"),
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert '"command": "parse"' in out
    assert (tmp_path / "out" / "raw_events.jsonl").exists()
    assert (tmp_path / "out" / "parse_diagnostics.json").exists()


def test_normalize_command_runs_with_fixture_inputs(tmp_path: Path, capsys):
    inventory = Path("tests/fixtures/normalize/sample_inventory.jsonl")
    raw_events = Path("tests/fixtures/normalize/sample_raw_events.jsonl")

    code = main([
        "normalize",
        "--inventory",
        str(inventory),
        "--raw-events",
        str(raw_events),
        "--output-dir",
        str(tmp_path / "out"),
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert '"command": "normalize"' in out
    assert (tmp_path / "out" / "evidence.jsonl").exists()
    assert (tmp_path / "out" / "normalization_diagnostics.json").exists()


def test_build_view_command_runs_with_fixture_inputs(tmp_path: Path, capsys):
    evidence = Path("tests/fixtures/normalize/sample_evidence.jsonl")

    code = main([
        "build-view",
        "--evidence",
        str(evidence),
        "--view",
        "user_nl_root_only",
        "--output-dir",
        str(tmp_path / "out"),
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert '"command": "build-view"' in out
    assert (tmp_path / "out" / "corpus_view.jsonl").exists()
    assert (tmp_path / "out" / "view_summary.json").exists()


def test_detect_command_runs_with_fixture_inputs(tmp_path: Path, capsys):
    view_dir = Path("artifacts/chat-analysis/views/user_nl_root_only")

    code = main([
        "detect",
        "--view-dir",
        str(view_dir),
        "--detector",
        "repeated_instructions",
        "--output-dir",
        str(tmp_path / "out"),
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert '"command": "detect"' in out
    assert (tmp_path / "out" / "detector_run.json").exists()


def test_report_command_runs_with_detector_run_input(tmp_path: Path, capsys):
    detector_run = Path("artifacts/chat-analysis/detectors/repeated_instructions/detector_run.json")

    code = main([
        "report",
        "--detector-run",
        str(detector_run),
        "--output-dir",
        str(tmp_path / "out"),
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert '"command": "report"' in out
    assert (tmp_path / "out" / "report.md").exists()
    assert (tmp_path / "out" / "report_metadata.json").exists()


def test_notebook_export_command_writes_manifest(tmp_path: Path, capsys):
    evidence = Path("artifacts/chat-analysis/normalize/smoke/evidence.jsonl")
    detector_run = Path("artifacts/chat-analysis/detectors/repeated_instructions/detector_run.json")

    code = main([
        "notebook-export",
        "--evidence",
        str(evidence),
        "--detector-run",
        str(detector_run),
        "--output-dir",
        str(tmp_path / "out"),
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert '"command": "notebook-export"' in out
    assert (tmp_path / "out" / "export_manifest.json").exists()


def test_semantic_run_requires_explicit_opt_in(tmp_path: Path):
    try:
        main([
            "semantic-run",
            "--view-dir",
            "artifacts/chat-analysis/views/user_nl_root_only",
            "--method",
            "clustering",
            "--output-dir",
            str(tmp_path / "out"),
        ])
    except ValueError as exc:
        assert "disabled by default" in str(exc)
    else:
        raise AssertionError("semantic-run should require explicit opt-in flag")


def test_semantic_run_writes_non_canonical_artifact(tmp_path: Path, capsys):
    code = main([
        "semantic-run",
        "--view-dir",
        "artifacts/chat-analysis/views/user_nl_root_only",
        "--method",
        "clustering",
        "--disabled-by-default-check",
        "--output-dir",
        str(tmp_path / "out"),
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert '"command": "semantic-run"' in out
    assert (tmp_path / "out" / "semantic_run.json").exists()


def test_semantic_run_embeddings_accepts_backend_parameters(tmp_path: Path, capsys):
    code = main([
        "semantic-run",
        "--view-dir",
        "artifacts/chat-analysis/views/user_nl_root_only",
        "--method",
        "embeddings",
        "--backend",
        "fixture",
        "--disabled-by-default-check",
        "--output-dir",
        str(tmp_path / "out"),
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert '"command": "semantic-run"' in out
    assert '"backend": "fixture"' in out
    assert (tmp_path / "out" / "semantic_run.json").exists()


def test_semantic_run_clustering_accepts_backend_parameters(tmp_path: Path, capsys):
    code = main([
        "semantic-run",
        "--view-dir",
        "artifacts/chat-analysis/views/user_nl_root_only",
        "--method",
        "clustering",
        "--backend",
        "fixture",
        "--distance-threshold",
        "0.25",
        "--min-cluster-size",
        "1",
        "--disabled-by-default-check",
        "--output-dir",
        str(tmp_path / "out"),
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert '"command": "semantic-run"' in out
    assert '"backend": "fixture"' in out
    assert '"distance_threshold": 0.25' in out
    assert (tmp_path / "out" / "semantic_run.json").exists()


def test_validate_command_runs_with_fixture_projects(tmp_path: Path, capsys):
    code = main([
        "validate",
        "--config",
        "configs/chat-analysis.default.yaml",
        "--projects-root",
        "tests/fixtures/discovery",
        "--output-dir",
        str(tmp_path / "out"),
    ])
    out = capsys.readouterr().out
    assert code == 0
    assert '"command": "validate"' in out
    assert (tmp_path / "out" / "validation_summary.json").exists()
    assert (tmp_path / "out" / "traceability_samples.json").exists()
