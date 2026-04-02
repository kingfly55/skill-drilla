"""Optional semantic analysis contracts and artifact helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from skill_drilla.contracts.ids import stable_id
from skill_drilla.search.index import iter_view_rows, load_view_artifacts


@dataclass(frozen=True)
class SemanticEvidenceSlice:
    view_name: str
    view_id: str | None
    view_dir: Path
    source_evidence_path: str | None
    recurrence_basis: dict[str, Any]
    subagent_policy: str | None
    evidence: tuple[dict[str, Any], ...]

    @classmethod
    def from_view_dir(cls, view_dir: Path) -> "SemanticEvidenceSlice":
        artifacts = load_view_artifacts(view_dir)
        rows = tuple(iter_view_rows(artifacts.corpus_view_path))
        evidence = tuple(_semantic_evidence_record(row["evidence"]) for row in rows)
        return cls(
            view_name=artifacts.view_name,
            view_id=artifacts.view_summary.get("view_id"),
            view_dir=view_dir,
            source_evidence_path=artifacts.view_summary.get("source_evidence_path"),
            recurrence_basis=dict(artifacts.view_summary.get("recurrence_basis", {})),
            subagent_policy=artifacts.view_summary.get("subagent_policy"),
            evidence=evidence,
        )

    def canonical_input(self) -> dict[str, Any]:
        evidence_ids = [item["evidence_id"] for item in self.evidence]
        session_roles = sorted({item.get("session_role") or "unknown" for item in self.evidence})
        semantic_classes = sorted({item.get("semantic_class") or "unknown" for item in self.evidence})
        return {
            "view_name": self.view_name,
            "view_id": self.view_id,
            "view_dir": str(self.view_dir),
            "source_evidence_path": self.source_evidence_path,
            "subagent_policy": self.subagent_policy,
            "recurrence_basis": self.recurrence_basis,
            "evidence_count": len(self.evidence),
            "evidence_ids": evidence_ids,
            "session_roles": session_roles,
            "semantic_classes": semantic_classes,
        }


@dataclass(frozen=True)
class SemanticRun:
    method: str
    canonical_input: dict[str, Any]
    derived_output: dict[str, Any]
    parameters: dict[str, Any]
    non_canonical: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "method": self.method,
            "canonical_input": self.canonical_input,
            "derived_output": self.derived_output,
            "parameters": self.parameters,
            "non_canonical": self.non_canonical,
        }


class SemanticMethod:
    method_name = "base"
    default_parameters: dict[str, Any] = {}

    def build_run(self, evidence_slice: SemanticEvidenceSlice, *, parameters: Mapping[str, Any] | None = None) -> SemanticRun:
        merged = {**self.default_parameters, **(parameters or {})}
        derived_output = self.derive(evidence_slice, merged)
        return SemanticRun(
            method=self.method_name,
            canonical_input=evidence_slice.canonical_input(),
            derived_output=derived_output,
            parameters=dict(merged),
            non_canonical=True,
        )

    def derive(self, evidence_slice: SemanticEvidenceSlice, parameters: Mapping[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


def derived_output_id(method: str, evidence_ids: Sequence[str], *parts: str) -> str:
    return stable_id("semantic", method, *evidence_ids, *parts)


def write_semantic_run(output_dir: Path, run: SemanticRun) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_path = output_dir / "semantic_run.json"
    run_path.write_text(json.dumps(run.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"output_dir": str(output_dir), "semantic_run": str(run_path)}


def _semantic_evidence_record(record: Mapping[str, Any]) -> dict[str, Any]:
    enriched = dict(record)
    enriched.setdefault(
        "scope",
        {
            "project_slug": record.get("project_slug"),
            "session_id": record.get("session_id"),
            "session_role": record.get("session_role"),
            "root_session_id": record.get("root_session_id"),
        },
    )
    return enriched
