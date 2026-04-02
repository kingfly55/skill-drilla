"""Configuration loading and normalization."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skill_drilla.contracts.artifacts import ArtifactLayout
from skill_drilla.contracts.ids import config_fingerprint


@dataclass(frozen=True)
class AppConfig:
    data: dict[str, Any]
    source_path: Path
    fingerprint: str

    @property
    def artifact_layout(self) -> ArtifactLayout:
        return ArtifactLayout.from_config(self.data["paths"]["artifact_root"])

    @property
    def input_scope(self) -> dict[str, Any]:
        scope = self.data["scope"]
        return {
            "label": scope["input_scope"],
            "include_projects": list(scope["include_projects"]),
            "exclude_projects": list(scope["exclude_projects"]),
            "include_subagents": bool(scope["include_subagents"]),
        }

    def to_normalized_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(self.data, sort_keys=True))


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip('"\'') for item in inner.split(",") if item.strip()]
    if value.isdigit():
        return int(value)
    return value.strip().strip('"\'')


def _simple_yaml_load(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if ":" not in line:
            raise ValueError(f"Unsupported YAML line: {raw_line!r}")
        key, remainder = line.split(":", 1)
        key = key.strip()
        remainder = remainder.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()
        current = stack[-1][1]

        if remainder == "":
            new_map: dict[str, Any] = {}
            current[key] = new_map
            stack.append((indent, new_map))
        else:
            current[key] = _parse_scalar(remainder)
    return root


def _normalize_config(data: dict[str, Any]) -> dict[str, Any]:
    required_top_level = {"project", "paths", "runtime", "scope", "views", "analysis"}
    missing = required_top_level.difference(data)
    if missing:
        raise ValueError(f"config missing required sections: {sorted(missing)}")

    scope = data["scope"]
    if not isinstance(scope.get("include_projects"), list):
        raise ValueError("scope.include_projects must be a list")
    if not isinstance(scope.get("exclude_projects"), list):
        raise ValueError("scope.exclude_projects must be a list")
    if not isinstance(scope.get("include_subagents"), bool):
        raise ValueError("scope.include_subagents must be a boolean")

    return {
        "analysis": dict(sorted(data["analysis"].items())),
        "paths": dict(sorted(data["paths"].items())),
        "project": dict(sorted(data["project"].items())),
        "runtime": dict(sorted(data["runtime"].items())),
        "scope": {
            "exclude_projects": list(scope["exclude_projects"]),
            "include_projects": list(scope["include_projects"]),
            "include_subagents": scope["include_subagents"],
            "input_scope": scope["input_scope"],
        },
        "views": dict(sorted(data["views"].items())),
    }


def load_config(config_path: str | Path) -> AppConfig:
    path = Path(config_path)
    data = _simple_yaml_load(path.read_text(encoding="utf-8"))
    normalized = _normalize_config(data)
    normalized_json = json.dumps(normalized, indent=2, sort_keys=True)
    return AppConfig(data=normalized, source_path=path, fingerprint=config_fingerprint(normalized_json))


def dump_effective_config(config: AppConfig) -> str:
    payload = config.to_normalized_dict()
    payload["meta"] = {
        "config_path": str(config.source_path),
        "config_fingerprint": config.fingerprint,
    }
    return json.dumps(payload, indent=2, sort_keys=True)
