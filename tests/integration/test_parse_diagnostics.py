import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = REPO_ROOT / "artifacts" / "chat-analysis" / "discovery" / "smoke-a" / "session_inventory.jsonl"


def test_parse_outputs_are_deterministic(tmp_path: Path):
    output_a = tmp_path / "parse-a"
    output_b = tmp_path / "parse-b"
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}
    command = [
        sys.executable,
        "-m",
        "skill_drilla.cli",
        "parse",
        "--inventory",
        str(INVENTORY_PATH),
    ]

    subprocess.run([*command, "--output-dir", str(output_a)], check=True, cwd=REPO_ROOT, env=env)
    subprocess.run([*command, "--output-dir", str(output_b)], check=True, cwd=REPO_ROOT, env=env)

    assert (output_a / "raw_events.jsonl").read_text(encoding="utf-8") == (
        output_b / "raw_events.jsonl"
    ).read_text(encoding="utf-8")
    assert json.loads((output_a / "parse_diagnostics.json").read_text(encoding="utf-8")) == json.loads(
        (output_b / "parse_diagnostics.json").read_text(encoding="utf-8")
    )


def test_parse_diagnostics_surface_invalid_and_unknown_records(tmp_path: Path):
    fixture_inventory = tmp_path / "inventory.jsonl"
    fixture_transcript = REPO_ROOT / "tests" / "fixtures" / "parse" / "sample_session.jsonl"
    fixture_inventory.write_text(
        json.dumps(
            {
                "project_id": "c" * 64,
                "project_slug": "fixture-project",
                "session_id": "d" * 64,
                "session_key": "fixture-session",
                "transcript_path": str(fixture_transcript),
                "transcript_relpath": "sample_session.jsonl",
                "session_role": "root",
                "lineage_state": "confirmed",
                "parent_session_id": None,
                "root_session_id": "d" * 64,
                "observed_parent_session_key": None,
                "observed_root_session_key": "fixture-session",
                "lineage_source": "fixture",
                "subagent_id": None,
                "metadata_path": None,
                "transcript_format": "jsonl",
                "transcript_size_bytes": fixture_transcript.stat().st_size,
                "transcript_mtime_ns": fixture_transcript.stat().st_mtime_ns,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "src")}

    subprocess.run(
        [
            sys.executable,
            "-m",
            "skill_drilla.cli",
            "parse",
            "--inventory",
            str(fixture_inventory),
            "--output-dir",
            str(output_dir),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    diagnostics = json.loads((output_dir / "parse_diagnostics.json").read_text(encoding="utf-8"))
    aggregate = diagnostics["aggregate"]
    assert aggregate["invalid_lines"] == 1
    assert aggregate["unknown_record_shapes"] == 1
    assert aggregate["non_object_lines"] == 1
    assert aggregate["blank_lines"] == 1

    raw_lines = [json.loads(line) for line in (output_dir / "raw_events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [line["parse_status"] for line in raw_lines] == [
        "parsed",
        "parsed",
        "unknown_record_shape",
        "invalid_json",
        "non_object",
        "blank",
    ]
