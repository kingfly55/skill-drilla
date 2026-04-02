"""Ranking utilities for detector findings used in report generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class RankedFinding:
    finding: dict[str, Any]
    score: float
    rank: int
    ranking_factors: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding["finding_id"],
            "title": self.finding["title"],
            "score": self.score,
            "rank": self.rank,
            "ranking_factors": self.ranking_factors,
        }


DEFAULT_RANKING_WEIGHTS = {
    "distinct_sessions": 5.0,
    "raw_occurrences": 3.0,
    "distinct_projects": 2.0,
    "distinct_evidence": 1.0,
}


def score_finding(
    finding: Mapping[str, Any],
    *,
    weights: Mapping[str, float] | None = None,
) -> dict[str, Any]:
    recurrence = dict(finding.get("recurrence", {}))
    active_weights = {**DEFAULT_RANKING_WEIGHTS, **(weights or {})}
    weighted_metrics = {
        metric: float(recurrence.get(metric, 0)) * float(weight)
        for metric, weight in active_weights.items()
    }
    score = float(sum(weighted_metrics.values()))
    return {
        "score": score,
        "weights": dict(active_weights),
        "weighted_metrics": weighted_metrics,
        "sort_tuple": (
            recurrence.get("distinct_sessions", 0),
            recurrence.get("raw_occurrences", 0),
            recurrence.get("distinct_projects", 0),
            recurrence.get("distinct_evidence", 0),
            finding.get("title", ""),
        ),
        "criteria_summary": {
            "primary": "distinct_sessions",
            "secondary": "raw_occurrences",
            "tertiary": "distinct_projects",
            "quaternary": "distinct_evidence",
        },
    }



def rank_findings(
    findings: Iterable[Mapping[str, Any]],
    *,
    weights: Mapping[str, float] | None = None,
) -> list[RankedFinding]:
    scored: list[tuple[Mapping[str, Any], dict[str, Any]]] = []
    for finding in findings:
        scored.append((finding, score_finding(finding, weights=weights)))

    scored.sort(
        key=lambda item: (
            -item[1]["sort_tuple"][0],
            -item[1]["sort_tuple"][1],
            -item[1]["sort_tuple"][2],
            -item[1]["sort_tuple"][3],
            item[0].get("title", ""),
        )
    )

    ranked: list[RankedFinding] = []
    for index, (finding, ranking) in enumerate(scored, start=1):
        ranked.append(
            RankedFinding(
                finding=dict(finding),
                score=ranking["score"],
                rank=index,
                ranking_factors=ranking,
            )
        )
    return ranked
