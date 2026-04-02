"""Lineage helpers for discovered sessions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LineageInfo:
    session_role: str
    lineage_state: str
    parent_session_key: str | None
    root_session_key: str | None
    source: str
    subagent_id: str | None = None


ROOT_ROLE = "root"
SUBAGENT_ROLE = "subagent"
UNKNOWN_ROLE = "unknown"

LINEAGE_CONFIRMED = "confirmed"
LINEAGE_UNKNOWN = "unknown"


def derive_lineage(project_root: Path, transcript_path: Path) -> LineageInfo:
    relative = transcript_path.relative_to(project_root)
    filename = transcript_path.name

    if "subagents" in relative.parts:
        parent_key = _find_parent_session_key(relative.parts)
        if parent_key:
            return LineageInfo(
                session_role=SUBAGENT_ROLE,
                lineage_state=LINEAGE_CONFIRMED,
                parent_session_key=parent_key,
                root_session_key=parent_key,
                source="subagents-directory",
                subagent_id=_subagent_id_from_filename(filename),
            )
        return LineageInfo(
            session_role=SUBAGENT_ROLE,
            lineage_state=LINEAGE_UNKNOWN,
            parent_session_key=None,
            root_session_key=None,
            source="subagents-directory-missing-parent",
            subagent_id=_subagent_id_from_filename(filename),
        )

    if filename.startswith("agent-") and filename.endswith(".jsonl"):
        return LineageInfo(
            session_role=SUBAGENT_ROLE,
            lineage_state=LINEAGE_UNKNOWN,
            parent_session_key=None,
            root_session_key=None,
            source="subagent-filename",
            subagent_id=_subagent_id_from_filename(filename),
        )

    if filename.endswith(".jsonl"):
        session_key = transcript_path.stem
        return LineageInfo(
            session_role=ROOT_ROLE,
            lineage_state=LINEAGE_CONFIRMED,
            parent_session_key=None,
            root_session_key=session_key,
            source="root-transcript",
            subagent_id=None,
        )

    return LineageInfo(
        session_role=UNKNOWN_ROLE,
        lineage_state=LINEAGE_UNKNOWN,
        parent_session_key=None,
        root_session_key=None,
        source="unsupported",
        subagent_id=None,
    )


def _find_parent_session_key(parts: tuple[str, ...] | list[str]) -> str | None:
    for index, part in enumerate(parts):
        if part == "subagents" and index > 0:
            return parts[index - 1]
    return None


def _subagent_id_from_filename(filename: str) -> str | None:
    if not filename.endswith(".jsonl"):
        return None
    stem = filename[:-6]
    return stem if stem.startswith("agent-") else None
