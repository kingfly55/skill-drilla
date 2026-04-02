"""Explicit filtering semantics for corpus views."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ViewFilterPolicy:
    semantic_classes: tuple[str, ...] = ()
    inclusion_statuses: tuple[str, ...] = ()
    session_roles: tuple[str, ...] = ()
    allow_ambiguous: bool = False
    include_excluded: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "semantic_classes": list(self.semantic_classes),
            "inclusion_statuses": list(self.inclusion_statuses),
            "session_roles": list(self.session_roles),
            "allow_ambiguous": self.allow_ambiguous,
            "include_excluded": self.include_excluded,
        }


@dataclass(frozen=True)
class FilterDecision:
    include: bool
    reason: str
    matched_scope: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "include": self.include,
            "reason": self.reason,
            "matched_scope": self.matched_scope,
        }


def apply_view_policy(record: dict[str, Any], policy: ViewFilterPolicy) -> FilterDecision:
    session_role = record.get("session_role") or "unknown"
    if policy.session_roles and session_role not in policy.session_roles:
        return FilterDecision(False, f"session_role_excluded:{session_role}", "session_role")

    inclusion_status = record.get("inclusion_status")
    if inclusion_status == "ambiguous" and not policy.allow_ambiguous:
        return FilterDecision(False, "ambiguous_excluded", "inclusion_status")
    if inclusion_status == "excluded_default" and not policy.include_excluded:
        return FilterDecision(False, "excluded_default_filtered", "inclusion_status")
    if policy.inclusion_statuses and inclusion_status not in policy.inclusion_statuses:
        return FilterDecision(False, f"inclusion_status_excluded:{inclusion_status}", "inclusion_status")

    semantic_class = record.get("semantic_class")
    if policy.semantic_classes and semantic_class not in policy.semantic_classes:
        return FilterDecision(False, f"semantic_class_excluded:{semantic_class}", "semantic_class")

    return FilterDecision(True, "included", "all_filters")
