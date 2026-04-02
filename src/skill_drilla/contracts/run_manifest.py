"""Run-manifest contract helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUIRED_MANIFEST_FIELDS = {
    "command",
    "started_at",
    "completed_at",
    "config_fingerprint",
    "input_scope",
    "artifact_paths",
}


@dataclass(frozen=True)
class RunContext:
    command: str
    config_fingerprint: str
    input_scope: dict[str, Any]
    artifact_paths: dict[str, str]
    started_at: str


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def start_run(command: str, config_fingerprint: str, input_scope: dict[str, Any], artifact_paths: dict[str, str]) -> RunContext:
    return RunContext(
        command=command,
        config_fingerprint=config_fingerprint,
        input_scope=input_scope,
        artifact_paths=artifact_paths,
        started_at=utc_now_iso(),
    )


def finalize_run(context: RunContext, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = {
        "command": context.command,
        "started_at": context.started_at,
        "completed_at": utc_now_iso(),
        "config_fingerprint": context.config_fingerprint,
        "input_scope": context.input_scope,
        "artifact_paths": context.artifact_paths,
    }
    if extra:
        manifest.update(extra)
    validate_manifest_dict(manifest)
    return manifest


def validate_manifest_dict(manifest: dict[str, Any]) -> None:
    missing = REQUIRED_MANIFEST_FIELDS.difference(manifest)
    if missing:
        raise ValueError(f"run manifest missing required fields: {sorted(missing)}")


def write_manifest(output_path: Path, manifest: dict[str, Any]) -> Path:
    validate_manifest_dict(manifest)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path
