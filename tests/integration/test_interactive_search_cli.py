import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VIEW_DIR = REPO_ROOT / "artifacts" / "chat-analysis" / "views" / "debug_included_and_excluded"


def test_search_cli_writes_reproducible_query_result(tmp_path: Path):
    output_dir = tmp_path / "search"
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_drilla.cli",
            "search",
            "--view-dir",
            str(VIEW_DIR),
            "--query",
            "pipeline AND report",
            "--project=-home-user",
            "--root-only",
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = json.loads((output_dir / "query_result.json").read_text(encoding="utf-8"))
    assert payload["query"]["operator"] == "AND"
    assert payload["view_name"] == "debug_included_and_excluded"
    assert payload["filters"]["project_slugs"] == ["-home-user"]
    assert payload["filters"]["include_subagents"] is False
    assert payload["filters"]["limit"] is None
    assert payload["reproducibility"]["parsed_query"]["terms"][0]["value"] == "pipeline"
    assert isinstance(payload["matches"], list)


def test_inspect_evidence_cli_prints_context(tmp_path: Path):
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    search_dir = tmp_path / "search"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_drilla.cli",
            "search",
            "--view-dir",
            str(VIEW_DIR),
            "--query",
            "pipeline AND report",
            "--output-dir",
            str(search_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )
    payload = json.loads((search_dir / "query_result.json").read_text(encoding="utf-8"))
    evidence_id = payload["matches"][0]["evidence_id"]

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_drilla.cli",
            "inspect-evidence",
            "--view-dir",
            str(VIEW_DIR),
            "--evidence-id",
            evidence_id,
            "--context",
            "1",
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    inspection = json.loads(completed.stdout)
    assert inspection["evidence_id"] == evidence_id
    assert "row" in inspection
    assert "context_before" in inspection
    assert "context_after" in inspection
