"""Scope filtering helpers for discovery inventory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from skill_drilla.discovery.inventory import DiscoverySummary, InventoryRecord


@dataclass(frozen=True)
class ScopedInventory:
    records: tuple[InventoryRecord, ...]
    excluded_records: tuple[InventoryRecord, ...]
    exclusion_reasons: dict[str, int]


@dataclass(frozen=True)
class ScopeDecision:
    included: bool
    reason: str | None


DEFAULT_INCLUDED_REASON = "included"
EXCLUDED_SUBAGENT_REASON = "excluded_subagent"
EXCLUDED_PROJECT_REASON = "excluded_project"
NOT_INCLUDED_PROJECT_REASON = "not_included_project"


def apply_scope(records: Iterable[InventoryRecord], input_scope: dict[str, object]) -> ScopedInventory:
    include_projects = {str(item) for item in input_scope.get("include_projects", [])}
    exclude_projects = {str(item) for item in input_scope.get("exclude_projects", [])}
    include_subagents = bool(input_scope.get("include_subagents", False))

    included: list[InventoryRecord] = []
    excluded: list[InventoryRecord] = []
    reasons: dict[str, int] = {}

    for record in records:
        decision = evaluate_record_scope(
            project_slug=record.project_slug,
            session_role=record.session_role,
            include_projects=include_projects,
            exclude_projects=exclude_projects,
            include_subagents=include_subagents,
        )
        if decision.included:
            included.append(record)
        else:
            excluded.append(record)
            if decision.reason:
                reasons[decision.reason] = reasons.get(decision.reason, 0) + 1

    return ScopedInventory(
        records=tuple(included),
        excluded_records=tuple(excluded),
        exclusion_reasons=dict(sorted(reasons.items())),
    )


def evaluate_record_scope(
    *,
    project_slug: str,
    session_role: str,
    include_projects: set[str],
    exclude_projects: set[str],
    include_subagents: bool,
) -> ScopeDecision:
    if include_projects and project_slug not in include_projects:
        return ScopeDecision(False, NOT_INCLUDED_PROJECT_REASON)
    if project_slug in exclude_projects:
        return ScopeDecision(False, EXCLUDED_PROJECT_REASON)
    if session_role == "subagent" and not include_subagents:
        return ScopeDecision(False, EXCLUDED_SUBAGENT_REASON)
    return ScopeDecision(True, DEFAULT_INCLUDED_REASON)


def summarize_scope(records: Iterable[InventoryRecord], scoped: ScopedInventory) -> dict[str, object]:
    full_summary = DiscoverySummary.from_records(tuple(records), tuple()).to_dict()
    scoped_summary = DiscoverySummary.from_records(scoped.records, scoped.excluded_records).to_dict()
    return {
        **full_summary,
        "scoped_sessions": len(scoped.records),
        "excluded_sessions": len(scoped.excluded_records),
        "exclusion_reasons": scoped.exclusion_reasons,
        "scoped": scoped_summary,
    }
