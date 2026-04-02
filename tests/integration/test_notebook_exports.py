import json
import os
import subprocess
import sys
from pathlib import Path

from skill_drilla.notebooks import export_notebook_artifacts


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = REPO_ROOT / "artifacts" / "chat-analysis"
EVIDENCE = ARTIFACTS / "normalize" / "smoke" / "evidence.jsonl"
DETECTOR_RUN = ARTIFACTS / "detectors" / "repeated_instructions" / "detector_run.json"



def test_export_notebook_artifacts_copies_canonical_inputs(tmp_path: Path):
    manifest = export_notebook_artifacts(tmp_path, evidence_paths=[EVIDENCE], detector_run_paths=[DETECTOR_RUN])

    assert {"inventory", "evidence", "detector_runs", "reports"} <= set(manifest)
    assert manifest["inventory"]
    assert manifest["evidence"]
    assert manifest["detector_runs"]
    assert manifest["reports"]
    assert (tmp_path / "export_manifest.json").exists()



def test_notebook_export_cli_writes_expected_manifest(tmp_path: Path):
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_drilla.cli",
            "notebook-export",
            "--evidence",
            str(EVIDENCE),
            "--detector-run",
            str(DETECTOR_RUN),
            "--output-dir",
            str(tmp_path),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    manifest = json.loads((tmp_path / "export_manifest.json").read_text(encoding="utf-8"))
    assert {"inventory", "evidence", "detector_runs", "reports"} <= set(manifest)
    assert manifest["inventory"][0]["exported_path"].endswith("session_inventory.jsonl")
    assert manifest["evidence"][0]["exported_path"].endswith("evidence.jsonl")
    assert manifest["detector_runs"][0]["exported_path"].endswith("detector_run.json")
    assert manifest["reports"][0]["exported_path"].endswith("report_metadata.json")
