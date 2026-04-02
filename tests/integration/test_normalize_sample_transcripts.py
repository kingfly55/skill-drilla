import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "normalize" / "sample_inventory.jsonl"
RAW_EVENTS_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "normalize" / "sample_raw_events.jsonl"
SMOKE_INVENTORY = REPO_ROOT / "artifacts" / "chat-analysis" / "discovery" / "smoke-a" / "session_inventory.jsonl"
SMOKE_RAW_EVENTS = REPO_ROOT / "artifacts" / "chat-analysis" / "parse" / "smoke" / "raw_events.jsonl"


def test_normalize_fixture_outputs_are_deterministic(tmp_path: Path):
    output_a = tmp_path / "normalize-a"
    output_b = tmp_path / "normalize-b"
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    command = [
        sys.executable,
        "-m",
        "skill_drilla.cli",
        "normalize",
        "--inventory",
        str(INVENTORY_FIXTURE),
        "--raw-events",
        str(RAW_EVENTS_FIXTURE),
    ]

    subprocess.run([*command, "--output-dir", str(output_a)], check=True, cwd=REPO_ROOT, env=env)
    subprocess.run([*command, "--output-dir", str(output_b)], check=True, cwd=REPO_ROOT, env=env)

    assert (output_a / "evidence.jsonl").read_text(encoding="utf-8") == (
        output_b / "evidence.jsonl"
    ).read_text(encoding="utf-8")
    assert json.loads((output_a / "normalization_diagnostics.json").read_text(encoding="utf-8")) == json.loads(
        (output_b / "normalization_diagnostics.json").read_text(encoding="utf-8")
    )


def test_normalize_fixture_surfaces_ambiguous_and_subagent_context(tmp_path: Path):
    output_dir = tmp_path / "normalize-fixture"
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_drilla.cli",
            "normalize",
            "--inventory",
            str(INVENTORY_FIXTURE),
            "--raw-events",
            str(RAW_EVENTS_FIXTURE),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    evidence = [json.loads(line) for line in (output_dir / "evidence.jsonl").read_text(encoding="utf-8").splitlines()]
    diagnostics = json.loads((output_dir / "normalization_diagnostics.json").read_text(encoding="utf-8"))

    assert any(item["session_role"] == "subagent" for item in evidence)
    assert any(item["semantic_class"] == "unknown_ambiguous" for item in evidence)
    assert diagnostics["ambiguous_items"]
    assert diagnostics["multi_evidence_events"] == 1


def test_normalize_smoke_artifacts_have_expected_contract(tmp_path: Path):
    output_dir = tmp_path / "normalize-smoke"
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_drilla.cli",
            "normalize",
            "--inventory",
            str(SMOKE_INVENTORY),
            "--raw-events",
            str(SMOKE_RAW_EVENTS),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    diagnostics = json.loads((output_dir / "normalization_diagnostics.json").read_text(encoding="utf-8"))
    first = json.loads((output_dir / "evidence.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert {"semantic_class_counts", "inclusion_rationale_counts", "ambiguous_items"} <= set(diagnostics)
    assert {"evidence_id", "raw_event_id", "session_role", "root_session_id"} <= set(first)
