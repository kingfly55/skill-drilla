"""Deterministic episode reconstruction from canonical evidence rows."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from skill_drilla.contracts.ids import stable_id
from skill_drilla.episodes.model import Episode, EpisodeIndex, EpisodeTurn, ToolContext
from skill_drilla.semantic.interpretation import _summarize

_NL_CLASSES = frozenset({"user_natural_language", "assistant_natural_language"})
_TOOL_CLASSES = frozenset({"tool_call", "tool_result"})
_ASSISTANT_COMPRESS_LIMIT = 300


def build_episodes(
    evidence_rows: Iterable[dict[str, Any]],
) -> tuple[tuple[Episode, ...], EpisodeIndex]:
    """
    Full pipeline: group → collapse → compress → link subagents.
    Returns (episodes, index). Deterministic for a fixed input order.
    """
    groups = _group_by_root_session(evidence_rows)
    episodes = tuple(_build_episode(group_key, rows) for group_key, rows in groups.items())
    index = EpisodeIndex(
        run_id="default",
        episode_count=len(episodes),
        turn_count=sum(e.turn_count for e in episodes),
        root_session_ids=tuple(e.root_session_id for e in episodes),
        episode_ids=tuple(e.episode_id for e in episodes),
        child_ref_count=sum(len(e.child_episode_refs) for e in episodes),
    )
    return episodes, index


def _group_by_root_session(
    rows: Iterable[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """
    Key = root_session_id when present and non-null, else session_id.
    Preserves insertion order within each group.
    """
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        key = row.get("root_session_id") or row.get("session_id") or ""
        if key not in groups:
            groups[key] = []
        groups[key].append(row)
    return groups


def _build_episode(group_key: str, rows: list[dict[str, Any]]) -> Episode:
    """
    Build one Episode from all evidence rows sharing a group key.

    Root-session rows become turns; subagent session_ids are referenced
    as child_episode_refs rather than being inlined as turns.
    """
    episode_id = stable_id("episode", group_key)

    # Separate rows by session_role
    root_rows: list[dict[str, Any]] = []
    subagent_session_ids: list[str] = []
    seen_subagent_sessions: set[str] = set()

    for row in rows:
        role = row.get("session_role") or "unknown"
        if role == "subagent":
            sid = row.get("session_id") or ""
            if sid and sid not in seen_subagent_sessions:
                subagent_session_ids.append(sid)
                seen_subagent_sessions.add(sid)
        else:
            root_rows.append(row)

    # Group root rows by raw_event_id (preserving first-seen order)
    raw_event_groups: dict[str, list[dict[str, Any]]] = {}
    for row in root_rows:
        reid = row.get("raw_event_id") or ""
        if reid not in raw_event_groups:
            raw_event_groups[reid] = []
        raw_event_groups[reid].append(row)

    # Build turns from each raw_event_id group, ordered by raw_event_index
    raw_event_groups_sorted = sorted(
        raw_event_groups.items(),
        key=lambda kv: _min_event_index(kv[1]),
    )

    turns: list[EpisodeTurn] = []
    project_id = ""
    project_slug = ""
    root_session_ids_seen: list[str] = []
    seen_root_sessions: set[str] = set()

    for raw_event_id, group_rows in raw_event_groups_sorted:
        nl_row, tool_contexts = _collapse_raw_event(raw_event_id, group_rows)
        if nl_row is None:
            continue

        # Capture project metadata from first NL row
        if not project_id:
            project_id = nl_row.get("project_id") or ""
            project_slug = nl_row.get("project_slug") or ""

        sid = nl_row.get("session_id") or ""
        if sid and sid not in seen_root_sessions:
            root_session_ids_seen.append(sid)
            seen_root_sessions.add(sid)

        turn = _make_turn(nl_row, tool_contexts, episode_id, len(turns))
        turns.append(turn)

    # Collect all contributing session_ids (root + subagent)
    all_session_ids = root_session_ids_seen + subagent_session_ids

    return Episode(
        episode_id=episode_id,
        root_session_id=group_key,
        project_id=project_id,
        project_slug=project_slug,
        turn_count=len(turns),
        turns=tuple(turns),
        child_episode_refs=tuple(subagent_session_ids),
        session_ids=tuple(all_session_ids),
    )


def _min_event_index(rows: list[dict[str, Any]]) -> int:
    indices = [row.get("raw_event_index") for row in rows if row.get("raw_event_index") is not None]
    return min(indices) if indices else 0


def _collapse_raw_event(
    raw_event_id: str,
    rows: list[dict[str, Any]],
) -> tuple[dict[str, Any] | None, list[ToolContext]]:
    """
    Split rows for one raw_event_id into a primary NL row and tool contexts.

    Non-NL, non-tool rows (thinking, protocol_meta, etc.) are silently skipped.
    Multiple NL rows for the same raw event are concatenated into the first row.
    """
    nl_rows: list[dict[str, Any]] = []
    tool_call_rows: list[dict[str, Any]] = []
    tool_result_rows: list[dict[str, Any]] = []

    for row in rows:
        sc = row.get("semantic_class") or ""
        if sc in _NL_CLASSES:
            nl_rows.append(row)
        elif sc == "tool_call":
            tool_call_rows.append(row)
        elif sc == "tool_result":
            tool_result_rows.append(row)
        # all other classes silently skipped

    tool_contexts = _pair_tool_rows(tool_call_rows, tool_result_rows, raw_event_id)

    if not nl_rows:
        return None, tool_contexts

    # Collapse multiple NL blocks into first row, concatenating content_text
    primary = nl_rows[0]
    if len(nl_rows) > 1:
        texts = [r.get("content_text") or "" for r in nl_rows if r.get("content_text")]
        merged_text = "\n\n".join(texts) if texts else None
        primary = dict(primary)
        primary["content_text"] = merged_text

    return primary, tool_contexts


def _pair_tool_rows(
    call_rows: list[dict[str, Any]],
    result_rows: list[dict[str, Any]],
    raw_event_id: str,
) -> list[ToolContext]:
    """Match tool_call rows to tool_result rows by tool_use_id."""
    result_by_id: dict[str, dict[str, Any]] = {}
    for r in result_rows:
        tid = r.get("tool_use_id")
        if tid:
            result_by_id[tid] = r

    contexts: list[ToolContext] = []
    matched_result_ids: set[str] = set()

    for call in call_rows:
        tid = call.get("tool_use_id")
        result = result_by_id.get(tid) if tid else None
        if tid and result:
            matched_result_ids.add(tid)
        contexts.append(ToolContext(
            tool_use_id=tid,
            tool_name=call.get("tool_name"),
            call_text=call.get("content_text"),
            result_text=result.get("content_text") if result else None,
            is_error=result.get("is_error") if result else None,
            call_evidence_id=call.get("evidence_id"),
            result_evidence_id=result.get("evidence_id") if result else None,
            raw_event_id=call.get("raw_event_id") or raw_event_id,
            raw_event_index=call.get("raw_event_index") or 0,
            session_id=call.get("session_id") or "",
        ))

    # Orphaned results: any result whose tool_use_id was never matched to a call
    for result in result_rows:
        tid = result.get("tool_use_id")
        if tid in matched_result_ids:
            continue
        contexts.append(ToolContext(
            tool_use_id=tid,
            tool_name=result.get("tool_name"),
            call_text=None,
            result_text=result.get("content_text"),
            is_error=result.get("is_error"),
            call_evidence_id=None,
            result_evidence_id=result.get("evidence_id"),
            raw_event_id=result.get("raw_event_id") or raw_event_id,
            raw_event_index=result.get("raw_event_index") or 0,
            session_id=result.get("session_id") or "",
        ))

    return contexts


def _make_turn(
    nl_row: dict[str, Any],
    tool_contexts: list[ToolContext],
    episode_id: str,
    turn_index: int,
) -> EpisodeTurn:
    """Build one EpisodeTurn from a primary NL row and its attached tool contexts."""
    raw_event_id = nl_row.get("raw_event_id") or ""
    turn_id = stable_id("turn", episode_id, raw_event_id, str(turn_index))

    role = "assistant" if nl_row.get("semantic_class") == "assistant_natural_language" else "user"
    content_text = nl_row.get("content_text")

    compressed_text: str | None = None
    if role == "assistant" and content_text:
        compressed_text = _summarize(content_text, limit=_ASSISTANT_COMPRESS_LIMIT)

    return EpisodeTurn(
        turn_id=turn_id,
        episode_id=episode_id,
        turn_index=turn_index,
        role=role,
        content_text=content_text,
        compressed_text=compressed_text,
        tool_context=tuple(tool_contexts),
        evidence_id=nl_row.get("evidence_id") or "",
        raw_event_id=raw_event_id,
        raw_event_index=nl_row.get("raw_event_index") or 0,
        session_id=nl_row.get("session_id") or "",
        root_session_id=nl_row.get("root_session_id"),
        parent_session_id=nl_row.get("parent_session_id"),
        session_role=nl_row.get("session_role") or "unknown",
    )


def write_episode_artifacts(
    output_dir: Path,
    episodes: tuple[Episode, ...],
    index: EpisodeIndex,
    run_label: str,
) -> dict[str, str]:
    """
    Write episodes.jsonl and episode_index.json under output_dir/run_label/.
    Returns a dict of artifact name → path string.
    """
    run_dir = output_dir / run_label
    run_dir.mkdir(parents=True, exist_ok=True)

    episodes_path = run_dir / "episodes.jsonl"
    with episodes_path.open("w", encoding="utf-8") as fh:
        for episode in episodes:
            fh.write(json.dumps(episode.to_dict(), sort_keys=True) + "\n")

    index_path = run_dir / "episode_index.json"
    index_path.write_text(
        json.dumps(index.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    return {
        "episodes": str(episodes_path),
        "episode_index": str(index_path),
    }
