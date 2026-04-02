import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "normalize" / "sample_evidence.jsonl"
SMOKE_EVIDENCE = REPO_ROOT / "artifacts" / "chat-analysis" / "normalize" / "smoke" / "evidence.jsonl"


def test_build_view_cli_generates_user_root_only_artifacts(tmp_path: Path):
    output_dir = tmp_path / "user-view"
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_drilla.cli",
            "build-view",
            "--evidence",
            str(EVIDENCE_FIXTURE),
            "--view",
            "user_nl_root_only",
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    summary = json.loads((output_dir / "view_summary.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (output_dir / "corpus_view.jsonl").read_text(encoding="utf-8").splitlines()]

    assert summary["view_name"] == "user_nl_root_only"
    assert summary["subagent_policy"] == "exclude_subagent_sessions"
    assert summary["counts"]["raw_occurrences"] == len(rows) == 2
    assert all(row["evidence"]["session_role"] == "root" for row in rows)
    assert all(row["evidence"]["semantic_class"] == "user_natural_language" for row in rows)


def test_build_view_cli_debug_view_includes_excluded_and_ambiguous(tmp_path: Path):
    output_dir = tmp_path / "debug-view"
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_drilla.cli",
            "build-view",
            "--evidence",
            str(EVIDENCE_FIXTURE),
            "--view",
            "debug_included_and_excluded",
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    summary = json.loads((output_dir / "view_summary.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (output_dir / "corpus_view.jsonl").read_text(encoding="utf-8").splitlines()]

    assert summary["counts"]["raw_occurrences"] == 6
    assert {row["evidence"]["inclusion_status"] for row in rows} == {
        "included_primary",
        "included_secondary",
        "excluded_default",
        "ambiguous",
    }
    assert any(row["evidence"]["session_role"] == "subagent" for row in rows)


def test_build_view_smoke_artifacts_have_required_summary_fields(tmp_path: Path):
    output_dir = tmp_path / "smoke-view"
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_drilla.cli",
            "build-view",
            "--evidence",
            str(SMOKE_EVIDENCE),
            "--view",
            "root_plus_subagent_all_roles",
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    summary = json.loads((output_dir / "view_summary.json").read_text(encoding="utf-8"))
    first_row = json.loads((output_dir / "corpus_view.jsonl").read_text(encoding="utf-8").splitlines()[0])

    assert {"view_name", "filters", "recurrence_basis", "counts", "subagent_policy"} <= set(summary)
    assert {"raw_occurrences", "distinct_evidence", "distinct_sessions", "distinct_projects"} <= set(summary["counts"])
    assert {"inspection", "evidence", "filter_decision"} <= set(first_row)
