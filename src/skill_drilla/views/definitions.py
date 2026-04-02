"""Reusable corpus view definitions and artifact builders."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator

from skill_drilla.contracts.ids import stable_id
from skill_drilla.views.filters import FilterDecision, ViewFilterPolicy, apply_view_policy
from skill_drilla.views.inspect import build_inspection_record
from skill_drilla.views.recurrence import RECURRENCE_BASIS_DEFAULT, compute_recurrence_counts

STANDARD_SUBAGENT_POLICIES = {
    "root_only": "exclude_subagent_sessions",
    "root_plus_subagent": "include_subagent_sessions_separately",
}


@dataclass(frozen=True)
class CorpusViewDefinition:
    view_name: str
    description: str
    filter_policy: ViewFilterPolicy
    recurrence_basis: dict[str, str]
    subagent_policy: str
    include_excluded_records: bool = False

    def metadata(self) -> dict[str, Any]:
        return {
            "view_name": self.view_name,
            "description": self.description,
            "filters": self.filter_policy.to_dict(),
            "recurrence_basis": dict(self.recurrence_basis),
            "subagent_policy": self.subagent_policy,
            "include_excluded_records": self.include_excluded_records,
        }


STANDARD_VIEW_DEFINITIONS: dict[str, CorpusViewDefinition] = {
    "user_nl_root_only": CorpusViewDefinition(
        view_name="user_nl_root_only",
        description="User-authored natural-language evidence from root sessions only.",
        filter_policy=ViewFilterPolicy(
            semantic_classes=("user_natural_language",),
            inclusion_statuses=("included_primary",),
            session_roles=("root",),
            allow_ambiguous=False,
            include_excluded=False,
        ),
        recurrence_basis=RECURRENCE_BASIS_DEFAULT,
        subagent_policy=STANDARD_SUBAGENT_POLICIES["root_only"],
    ),
    "assistant_nl_root_only": CorpusViewDefinition(
        view_name="assistant_nl_root_only",
        description="Assistant natural-language evidence from root sessions only.",
        filter_policy=ViewFilterPolicy(
            semantic_classes=("assistant_natural_language",),
            inclusion_statuses=("included_secondary",),
            session_roles=("root",),
            allow_ambiguous=False,
            include_excluded=False,
        ),
        recurrence_basis=RECURRENCE_BASIS_DEFAULT,
        subagent_policy=STANDARD_SUBAGENT_POLICIES["root_only"],
    ),
    "combined_nl_root_plus_subagent": CorpusViewDefinition(
        view_name="combined_nl_root_plus_subagent",
        description="Combined user and assistant natural-language evidence with role labels across root and subagent sessions.",
        filter_policy=ViewFilterPolicy(
            semantic_classes=("user_natural_language", "assistant_natural_language"),
            inclusion_statuses=("included_primary", "included_secondary"),
            session_roles=("root", "subagent"),
            allow_ambiguous=False,
            include_excluded=False,
        ),
        recurrence_basis=RECURRENCE_BASIS_DEFAULT,
        subagent_policy=STANDARD_SUBAGENT_POLICIES["root_plus_subagent"],
    ),
    "debug_included_and_excluded": CorpusViewDefinition(
        view_name="debug_included_and_excluded",
        description="Debug slice containing included, excluded, and ambiguous evidence across root and subagent sessions.",
        filter_policy=ViewFilterPolicy(
            semantic_classes=(),
            inclusion_statuses=("included_primary", "included_secondary", "excluded_default", "ambiguous"),
            session_roles=("root", "subagent", "unknown"),
            allow_ambiguous=True,
            include_excluded=True,
        ),
        recurrence_basis=RECURRENCE_BASIS_DEFAULT,
        subagent_policy=STANDARD_SUBAGENT_POLICIES["root_plus_subagent"],
        include_excluded_records=True,
    ),
    "root_only_all_roles": CorpusViewDefinition(
        view_name="root_only_all_roles",
        description="All included evidence from root sessions only, preserving role distinctions.",
        filter_policy=ViewFilterPolicy(
            semantic_classes=(),
            inclusion_statuses=("included_primary", "included_secondary"),
            session_roles=("root",),
            allow_ambiguous=False,
            include_excluded=False,
        ),
        recurrence_basis=RECURRENCE_BASIS_DEFAULT,
        subagent_policy=STANDARD_SUBAGENT_POLICIES["root_only"],
    ),
    "root_plus_subagent_all_roles": CorpusViewDefinition(
        view_name="root_plus_subagent_all_roles",
        description="All included evidence from root and subagent sessions, preserving session-role distinctions.",
        filter_policy=ViewFilterPolicy(
            semantic_classes=(),
            inclusion_statuses=("included_primary", "included_secondary"),
            session_roles=("root", "subagent"),
            allow_ambiguous=False,
            include_excluded=False,
        ),
        recurrence_basis=RECURRENCE_BASIS_DEFAULT,
        subagent_policy=STANDARD_SUBAGENT_POLICIES["root_plus_subagent"],
    ),
}


def get_view_definition(view_name: str) -> CorpusViewDefinition:
    try:
        return STANDARD_VIEW_DEFINITIONS[view_name]
    except KeyError as exc:
        raise ValueError(f"unknown view definition: {view_name}") from exc


def iter_evidence_records(evidence_path: Path) -> Iterator[dict[str, Any]]:
    with evidence_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def build_view(view_name: str, evidence_path: Path, output_dir: Path) -> dict[str, str]:
    definition = get_view_definition(view_name)
    return write_view_artifacts(output_dir, definition, iter_evidence_records(evidence_path), evidence_path)


def write_view_artifacts(
    output_dir: Path,
    definition: CorpusViewDefinition,
    evidence_records: Iterable[dict[str, Any]],
    evidence_path: Path | None = None,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    corpus_view_path = output_dir / "corpus_view.jsonl"
    summary_path = output_dir / "view_summary.json"

    included_records: list[dict[str, Any]] = []
    excluded_records: list[dict[str, Any]] = []
    decisions: list[FilterDecision] = []

    with corpus_view_path.open("w", encoding="utf-8") as handle:
        for ordinal, record in enumerate(evidence_records):
            decision = apply_view_policy(record, definition.filter_policy)
            decisions.append(decision)
            if not decision.include:
                excluded_records.append(record)
                continue

            row = {
                "view_name": definition.view_name,
                "view_row_id": stable_id(definition.view_name, record["evidence_id"], str(ordinal)),
                "view_ordinal": ordinal,
                "filter_decision": decision.to_dict(),
                "inspection": build_inspection_record(record),
                "evidence": record,
            }
            included_records.append(record)
            handle.write(json.dumps(row, sort_keys=True) + "\n")

    counts = compute_recurrence_counts(included_records)
    summary = {
        **definition.metadata(),
        "view_id": stable_id("corpus-view", definition.view_name, str(evidence_path or output_dir)),
        "source_evidence_path": str(evidence_path) if evidence_path is not None else None,
        "counts": counts,
        "source_record_count": len(decisions),
        "included_record_count": len(included_records),
        "excluded_record_count": len(excluded_records),
        "excluded_breakdown": _count_by_reason(decisions, include_state=False),
        "included_breakdown": _count_by_reason(decisions, include_state=True),
    }
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "output_dir": str(output_dir),
        "corpus_view": str(corpus_view_path),
        "view_summary": str(summary_path),
    }


def _count_by_reason(decisions: Iterable[FilterDecision], *, include_state: bool) -> dict[str, int]:
    counts: dict[str, int] = {}
    for decision in decisions:
        if decision.include is include_state:
            counts[decision.reason] = counts.get(decision.reason, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))
