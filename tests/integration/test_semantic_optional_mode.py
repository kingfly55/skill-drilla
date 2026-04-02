import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VIEW_DIR = REPO_ROOT / "artifacts" / "chat-analysis" / "views" / "user_nl_root_only"


def test_semantic_run_requires_explicit_enable_flag(tmp_path: Path):
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_drilla.cli",
            "semantic-run",
            "--view-dir",
            str(VIEW_DIR),
            "--method",
            "clustering",
            "--output-dir",
            str(tmp_path / "semantic"),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "disabled by default" in completed.stderr


def test_semantic_run_writes_non_canonical_artifact_and_report_still_works(tmp_path: Path):
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    semantic_dir = tmp_path / "semantic"
    report_dir = tmp_path / "report"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_drilla.cli",
            "semantic-run",
            "--view-dir",
            str(VIEW_DIR),
            "--method",
            "clustering",
            "--disabled-by-default-check",
            "--output-dir",
            str(semantic_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )
    semantic_payload = json.loads((semantic_dir / "semantic_run.json").read_text(encoding="utf-8"))
    assert semantic_payload["non_canonical"] is True
    assert semantic_payload["canonical_input"]["view_name"] == "user_nl_root_only"
    assert semantic_payload["parameters"]["implementation"] == "keyword-overlap-v1"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_drilla.cli",
            "report",
            "--detector-run",
            str(REPO_ROOT / "artifacts" / "chat-analysis" / "detectors" / "repeated_instructions" / "detector_run.json"),
            "--output-dir",
            str(report_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )
    assert (report_dir / "report.md").exists()
