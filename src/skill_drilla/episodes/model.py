"""Data models for deterministic episode extraction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolContext:
    """Subordinate tool call/result pair collapsed from one raw_event_id."""

    tool_use_id: str | None
    tool_name: str | None
    call_text: str | None
    result_text: str | None
    is_error: bool | None
    call_evidence_id: str | None
    result_evidence_id: str | None
    raw_event_id: str
    raw_event_index: int
    session_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "tool_use_id": self.tool_use_id,
            "tool_name": self.tool_name,
            "call_text": self.call_text,
            "result_text": self.result_text,
            "is_error": self.is_error,
            "call_evidence_id": self.call_evidence_id,
            "result_evidence_id": self.result_evidence_id,
            "raw_event_id": self.raw_event_id,
            "raw_event_index": self.raw_event_index,
            "session_id": self.session_id,
        }


@dataclass(frozen=True)
class EpisodeTurn:
    """
    One visible NL turn in an episode transcript.

    Multiple evidence rows sharing a raw_event_id collapse into one turn.
    Tool call/result siblings go into tool_context, not into visible content.
    Provenance fields (evidence_id, raw_event_id, raw_event_index, session_id)
    are never stripped.
    """

    turn_id: str
    episode_id: str
    turn_index: int
    role: str
    content_text: str | None
    compressed_text: str | None
    tool_context: tuple[ToolContext, ...]
    # provenance — never stripped
    evidence_id: str
    raw_event_id: str
    raw_event_index: int
    session_id: str
    root_session_id: str | None
    parent_session_id: str | None
    session_role: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_id": self.turn_id,
            "episode_id": self.episode_id,
            "turn_index": self.turn_index,
            "role": self.role,
            "content_text": self.content_text,
            "compressed_text": self.compressed_text,
            "tool_context": [tc.to_dict() for tc in self.tool_context],
            "evidence_id": self.evidence_id,
            "raw_event_id": self.raw_event_id,
            "raw_event_index": self.raw_event_index,
            "session_id": self.session_id,
            "root_session_id": self.root_session_id,
            "parent_session_id": self.parent_session_id,
            "session_role": self.session_role,
        }


@dataclass(frozen=True)
class Episode:
    """
    One root conversation thread identified by a group key (root_session_id or session_id).

    Subagent sessions are represented only as child_episode_refs — their content
    is not inlined as turns. This preserves chronology and context budget.
    """

    episode_id: str
    root_session_id: str
    project_id: str
    project_slug: str
    turn_count: int
    turns: tuple[EpisodeTurn, ...]
    child_episode_refs: tuple[str, ...]
    session_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "root_session_id": self.root_session_id,
            "project_id": self.project_id,
            "project_slug": self.project_slug,
            "turn_count": self.turn_count,
            "turns": [t.to_dict() for t in self.turns],
            "child_episode_refs": list(self.child_episode_refs),
            "session_ids": list(self.session_ids),
        }


@dataclass(frozen=True)
class EpisodeIndex:
    """Written as episode_index.json alongside episodes.jsonl."""

    run_id: str
    episode_count: int
    turn_count: int
    root_session_ids: tuple[str, ...]
    episode_ids: tuple[str, ...]
    child_ref_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "episode_count": self.episode_count,
            "turn_count": self.turn_count,
            "root_session_ids": list(self.root_session_ids),
            "episode_ids": list(self.episode_ids),
            "child_ref_count": self.child_ref_count,
        }
