import json
from pathlib import Path

from skill_drilla.contracts.run_manifest import (
    REQUIRED_MANIFEST_FIELDS,
    finalize_run,
    start_run,
    validate_manifest_dict,
    write_manifest,
)


def test_run_manifest_contains_required_fields(tmp_path: Path):
    context = start_run(
        command="validate",
        config_fingerprint="a" * 64,
        input_scope={"label": "default-local"},
        artifact_paths={"run_manifest": str(tmp_path / "run_manifest.json")},
    )
    manifest = finalize_run(context)
    assert REQUIRED_MANIFEST_FIELDS.issubset(manifest)
    validate_manifest_dict(manifest)


def test_write_manifest_persists_json(tmp_path: Path):
    manifest = {
        "command": "validate",
        "started_at": "2026-03-30T00:00:00Z",
        "completed_at": "2026-03-30T00:00:01Z",
        "config_fingerprint": "b" * 64,
        "input_scope": {"label": "default-local"},
        "artifact_paths": {"run_manifest": str(tmp_path / "run_manifest.json")},
    }
    output_path = write_manifest(tmp_path / "run_manifest.json", manifest)
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["command"] == "validate"
    assert payload["artifact_paths"]["run_manifest"].endswith("run_manifest.json")
