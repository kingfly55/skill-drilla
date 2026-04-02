import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "configs" / "chat-analysis.default.yaml"
PROJECTS_ROOT = REPO_ROOT / "projects"


def test_discover_outputs_are_stable(tmp_path: Path):
    output_a = tmp_path / "smoke-a"
    output_b = tmp_path / "smoke-b"

    command = [
        sys.executable,
        "-m",
        "skill_drilla.cli",
        "discover",
        "--config",
        str(CONFIG_PATH),
        "--projects-root",
        str(PROJECTS_ROOT),
    ]
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    subprocess.run([*command, "--output-dir", str(output_a)], check=True, cwd=REPO_ROOT, env=env)
    subprocess.run([*command, "--output-dir", str(output_b)], check=True, cwd=REPO_ROOT, env=env)

    assert (output_a / "session_inventory.jsonl").read_text(encoding="utf-8") == (
        output_b / "session_inventory.jsonl"
    ).read_text(encoding="utf-8")
    assert (output_a / "scoped_session_inventory.jsonl").read_text(encoding="utf-8") == (
        output_b / "scoped_session_inventory.jsonl"
    ).read_text(encoding="utf-8")

    summary = json.loads((output_a / "inventory_summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((output_a / "run_manifest.json").read_text(encoding="utf-8"))

    assert {"projects", "sessions", "anomalies"} <= set(summary)
    assert {"include_projects", "exclude_projects", "include_subagents"} <= set(manifest["input_scope"])
