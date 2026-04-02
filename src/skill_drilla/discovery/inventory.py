"""Corpus discovery inventory generation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from skill_drilla.contracts.ids import stable_id
from skill_drilla.discovery.lineage import derive_lineage


@dataclass(frozen=True)
class ProjectRecord:
    project_id: str
    project_slug: str
    project_path: str
    metadata_paths: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_slug": self.project_slug,
            "project_path": self.project_path,
            "metadata_paths": list(self.metadata_paths),
        }


@dataclass(frozen=True)
class InventoryRecord:
    project_id: str
    project_slug: str
    session_id: str
    session_key: str
    transcript_path: str
    transcript_relpath: str
    session_role: str
    lineage_state: str
    parent_session_id: str | None
    root_session_id: str | None
    observed_parent_session_key: str | None
    observed_root_session_key: str | None
    lineage_source: str
    subagent_id: str | None
    metadata_path: str | None
    transcript_format: str
    transcript_size_bytes: int
    transcript_mtime_ns: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_id": self.project_id,
            "project_slug": self.project_slug,
            "session_id": self.session_id,
            "session_key": self.session_key,
            "transcript_path": self.transcript_path,
            "transcript_relpath": self.transcript_relpath,
            "session_role": self.session_role,
            "lineage_state": self.lineage_state,
            "parent_session_id": self.parent_session_id,
            "root_session_id": self.root_session_id,
            "observed_parent_session_key": self.observed_parent_session_key,
            "observed_root_session_key": self.observed_root_session_key,
            "lineage_source": self.lineage_source,
            "subagent_id": self.subagent_id,
            "metadata_path": self.metadata_path,
            "transcript_format": self.transcript_format,
            "transcript_size_bytes": self.transcript_size_bytes,
            "transcript_mtime_ns": self.transcript_mtime_ns,
        }


@dataclass(frozen=True)
class DiscoverySummary:
    projects: int
    sessions: int
    anomalies: dict[str, int]
    session_roles: dict[str, int]
    lineage_states: dict[str, int]
    project_sessions: dict[str, int]

    @classmethod
    def from_records(
        cls,
        records: Iterable[InventoryRecord],
        excluded_records: Iterable[InventoryRecord],
    ) -> "DiscoverySummary":
        record_list = tuple(records)
        excluded_list = tuple(excluded_records)
        anomalies = {
            "unknown_lineage": sum(1 for r in record_list if r.lineage_state == "unknown"),
            "missing_metadata": sum(1 for r in record_list if r.metadata_path is None and r.session_role == "subagent"),
            "excluded": len(excluded_list),
        }
        session_roles = _count_by(record_list, lambda r: r.session_role)
        lineage_states = _count_by(record_list, lambda r: r.lineage_state)
        project_sessions = _count_by(record_list, lambda r: r.project_slug)
        return cls(
            projects=len({r.project_id for r in record_list}),
            sessions=len(record_list),
            anomalies=anomalies,
            session_roles=project_sorted_dict(session_roles),
            lineage_states=project_sorted_dict(lineage_states),
            project_sessions=project_sorted_dict(project_sessions),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "projects": self.projects,
            "sessions": self.sessions,
            "anomalies": self.anomalies,
            "session_roles": self.session_roles,
            "lineage_states": self.lineage_states,
            "project_sessions": self.project_sessions,
        }


@dataclass(frozen=True)
class DiscoveryResult:
    projects: tuple[ProjectRecord, ...]
    records: tuple[InventoryRecord, ...]


def discover_corpus(projects_root: Path) -> DiscoveryResult:
    project_records: list[ProjectRecord] = []
    inventory_records: list[InventoryRecord] = []

    for project_root in sorted([path for path in projects_root.iterdir() if path.is_dir()], key=lambda p: p.name):
        project_id = stable_id("project", project_root.name)
        metadata_paths = _discover_project_metadata(project_root)
        project_records.append(
            ProjectRecord(
                project_id=project_id,
                project_slug=project_root.name,
                project_path=str(project_root),
                metadata_paths=tuple(metadata_paths),
            )
        )

        for transcript_path in _discover_transcripts(project_root):
            metadata_path = _associated_metadata_path(transcript_path)
            lineage = derive_lineage(project_root, transcript_path)
            session_key = str(transcript_path.relative_to(project_root).with_suffix(""))
            session_id = stable_id("session", project_root.name, session_key)
            parent_session_id = (
                stable_id("session", project_root.name, lineage.parent_session_key)
                if lineage.parent_session_key
                else None
            )
            root_session_id = (
                stable_id("session", project_root.name, lineage.root_session_key)
                if lineage.root_session_key
                else None
            )
            stat = transcript_path.stat()
            inventory_records.append(
                InventoryRecord(
                    project_id=project_id,
                    project_slug=project_root.name,
                    session_id=session_id,
                    session_key=session_key,
                    transcript_path=str(transcript_path),
                    transcript_relpath=str(transcript_path.relative_to(project_root)),
                    session_role=lineage.session_role,
                    lineage_state=lineage.lineage_state,
                    parent_session_id=parent_session_id,
                    root_session_id=root_session_id,
                    observed_parent_session_key=lineage.parent_session_key,
                    observed_root_session_key=lineage.root_session_key,
                    lineage_source=lineage.source,
                    subagent_id=lineage.subagent_id,
                    metadata_path=str(metadata_path) if metadata_path else None,
                    transcript_format="jsonl",
                    transcript_size_bytes=stat.st_size,
                    transcript_mtime_ns=stat.st_mtime_ns,
                )
            )

    inventory_records.sort(key=lambda record: (record.project_slug, record.transcript_relpath))
    return DiscoveryResult(projects=tuple(project_records), records=tuple(inventory_records))


def inventory_jsonl_lines(records: Iterable[InventoryRecord]) -> list[str]:
    return [json.dumps(record.to_dict(), sort_keys=True) for record in records]


def _discover_project_metadata(project_root: Path) -> list[str]:
    paths: list[str] = []
    for candidate in sorted(project_root.rglob("*.json")):
        if candidate.name.endswith(".meta.json"):
            continue
        if candidate.name == "bridge-pointer.json" or candidate.name == "sessions-index.json":
            paths.append(str(candidate))
    return paths


def _discover_transcripts(project_root: Path) -> list[Path]:
    transcripts = [path for path in project_root.rglob("*.jsonl") if path.is_file()]
    return sorted(transcripts, key=lambda path: (str(path.relative_to(project_root)), path.name))


def _associated_metadata_path(transcript_path: Path) -> Path | None:
    if transcript_path.parent.name == "subagents":
        candidate = transcript_path.with_suffix(".meta.json")
        if candidate.exists():
            return candidate
    return None


def _count_by(records: Iterable[InventoryRecord], key_fn) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        key = key_fn(record)
        counts[key] = counts.get(key, 0) + 1
    return counts


def project_sorted_dict(values: dict[str, int]) -> dict[str, int]:
    return dict(sorted(values.items(), key=lambda item: item[0]))
