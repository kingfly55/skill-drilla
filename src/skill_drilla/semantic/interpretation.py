"""Local deterministic interpretation helpers for semantic outputs."""

from __future__ import annotations

from typing import Any, Mapping

from skill_drilla.semantic.base import SemanticEvidenceSlice, SemanticMethod, derived_output_id


class FixtureInterpretationMethod(SemanticMethod):
    method_name = "interpretation"
    default_parameters = {
        "implementation": "rule-based-summary-v1",
        "prompt_style": "fixture-summary",
        "max_examples": 3,
    }

    def derive(self, evidence_slice: SemanticEvidenceSlice, parameters: Mapping[str, Any]) -> dict[str, Any]:
        examples = []
        for evidence in evidence_slice.evidence[: int(parameters["max_examples"] )]:
            examples.append(
                {
                    "evidence_id": evidence["evidence_id"],
                    "session_role": evidence.get("session_role"),
                    "summary": _summarize(evidence.get("content_text") or ""),
                }
            )
        session_roles = sorted({item.get("session_role") or "unknown" for item in evidence_slice.evidence})
        return {
            "derived_output_id": derived_output_id(
                self.method_name,
                [item["evidence_id"] for item in evidence_slice.evidence],
                *session_roles,
            ),
            "kind": "interpretation",
            "summary": f"Derived semantic interpretation over {len(evidence_slice.evidence)} evidence items from view {evidence_slice.view_name}.",
            "scope": {
                "view_name": evidence_slice.view_name,
                "session_roles": session_roles,
            },
            "examples": examples,
        }


def _summarize(text: str, limit: int = 80) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 3] + "..."
