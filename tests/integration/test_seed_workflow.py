import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
VIEW_DIR = REPO_ROOT / "artifacts" / "chat-analysis" / "views" / "user_nl_root_only"


def test_seed_expand_cli_writes_seed_run(tmp_path: Path):
    output_dir = tmp_path / "seed"
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_drilla.cli",
            "seed-expand",
            "--view-dir",
            str(VIEW_DIR),
            "--term",
            "pipeline",
            "--window",
            "3",
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = json.loads((output_dir / "seed_run.json").read_text(encoding="utf-8"))
    assert payload["seed_term"] == "pipeline"
    assert payload["view_name"] == "user_nl_root_only"
    assert isinstance(payload["direct_hits"], list)
    assert isinstance(payload["expansion_hits"], list)
    assert payload["parameters"]["window"] == 3
    assert payload["parameters"]["strategy"] == "cooccurrence"
    assert {"direct", "expansion"} <= set(payload["related_sessions"])
