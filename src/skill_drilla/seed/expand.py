"""Seed-term expansion strategies and seed run artifact writer."""

from __future__ import annotations

import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skill_drilla.seed.direct_hits import DirectHitRun, collect_direct_hits, iter_view_rows
from skill_drilla.seed.session_neighborhood import collect_session_neighborhood
from skill_drilla.views import compute_recurrence_counts

_TOKEN_RE = re.compile(r"[A-Za-z0-9_'-]+")
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "if", "in", "into", "is", "it", "of", "on", "or", "that", "the", "to", "we", "with", "you", "your"
}
_SUPPORTED_STRATEGIES = {"cooccurrence", "adjacency", "session_neighborhood"}


@dataclass(frozen=True)
class SeedExpansionRun:
    seed_term: str
    view_name: str
    direct_hits: list[dict[str, Any]]
    expansion_hits: list[dict[str, Any]]
    direct_recurrence: dict[str, int]
    expansion_recurrence: dict[str, int]
    related_sessions: dict[str, list[dict[str, Any]]]
    parameters: dict[str, Any]
    reproducibility: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "seed_term": self.seed_term,
            "view_name": self.view_name,
            "direct_hits": self.direct_hits,
            "expansion_hits": self.expansion_hits,
            "direct_recurrence": self.direct_recurrence,
            "expansion_recurrence": self.expansion_recurrence,
            "related_sessions": self.related_sessions,
            "parameters": self.parameters,
            "reproducibility": self.reproducibility,
        }


def build_seed_run(
    view_dir: Path,
    *,
    seed_term: str,
    window: int,
    strategy: str = "cooccurrence",
    expansion_limit: int = 25,
    min_term_frequency: int = 1,
) -> SeedExpansionRun:
    if strategy not in _SUPPORTED_STRATEGIES:
        raise ValueError(f"unsupported expansion strategy: {strategy}")

    summary = json.loads((view_dir / "view_summary.json").read_text(encoding="utf-8"))
    direct_run = collect_direct_hits(view_dir, seed_term)
    direct_hit_ids = {hit.evidence_id for hit in direct_run.hits}
    direct_session_ids = {hit.session_id for hit in direct_run.hits}
    neighborhoods = collect_session_neighborhood(
        view_dir,
        direct_hit_ids=direct_hit_ids,
        direct_session_ids=direct_session_ids,
        window=window,
    )
    expansion_hits = _expand_hits(
        view_dir,
        direct_run=direct_run,
        neighborhoods=neighborhoods,
        strategy=strategy,
        window=window,
        expansion_limit=expansion_limit,
        min_term_frequency=min_term_frequency,
    )
    expansion_recurrence = compute_recurrence_counts(expansion_hits)
    return SeedExpansionRun(
        seed_term=seed_term,
        view_name=summary["view_name"],
        direct_hits=[hit.to_dict() for hit in direct_run.hits],
        expansion_hits=expansion_hits,
        direct_recurrence=direct_run.recurrence,
        expansion_recurrence=expansion_recurrence,
        related_sessions={
            "direct": direct_run.related_sessions,
            "expansion": _build_related_sessions(expansion_hits),
        },
        parameters={
            "strategy": strategy,
            "window": window,
            "expansion_limit": expansion_limit,
            "min_term_frequency": min_term_frequency,
            "supported_strategies": sorted(_SUPPORTED_STRATEGIES),
        },
        reproducibility={
            "view_dir": str(view_dir),
            "view_id": summary.get("view_id"),
            "source_evidence_path": summary.get("source_evidence_path"),
            "subagent_policy": summary.get("subagent_policy"),
            "view_filters": summary.get("filters"),
            "view_recurrence_basis": summary.get("recurrence_basis"),
            "parsed_seed_term": direct_run.parsed_query,
        },
    )


def write_seed_run(output_dir: Path, run: SeedExpansionRun) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "seed_run.json"
    path.write_text(json.dumps(run.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"output_dir": str(output_dir), "seed_run": str(path)}


def _expand_hits(
    view_dir: Path,
    *,
    direct_run: DirectHitRun,
    neighborhoods: dict[str, list[Any]],
    strategy: str,
    window: int,
    expansion_limit: int,
    min_term_frequency: int,
) -> list[dict[str, Any]]:
    direct_hit_ids = {hit.evidence_id for hit in direct_run.hits}
    direct_session_ids = {hit.session_id for hit in direct_run.hits}
    expansion_terms = _discover_expansion_terms(direct_run, window=window, min_term_frequency=min_term_frequency, limit=expansion_limit)
    expansion_term_lookup = {item["term"] for item in expansion_terms}

    rows = list(iter_view_rows(view_dir))
    hits: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        evidence = row["evidence"]
        evidence_id = evidence["evidence_id"]
        if evidence_id in direct_hit_ids or evidence_id in seen:
            continue
        text = evidence.get("content_text") or ""
        tokens = {token.casefold() for token in _tokenize(text)}
        matched_expansion_terms = sorted(term for term in expansion_term_lookup if term in tokens)
        if not matched_expansion_terms:
            continue
        session_id = evidence["session_id"]
        same_session = session_id in direct_session_ids
        include = False
        relationship = strategy
        score = len(matched_expansion_terms)
        if strategy == "cooccurrence":
            include = same_session
            relationship = "session_cooccurrence"
        elif strategy == "adjacency":
            neighborhood_ids = {item.evidence_id for item in neighborhoods.get(session_id, [])}
            include = evidence_id in neighborhood_ids
            relationship = "adjacent_to_direct_hit"
            if include:
                score = max(window + 1 - next(item.distance for item in neighborhoods[session_id] if item.evidence_id == evidence_id), 1)
        elif strategy == "session_neighborhood":
            include = same_session
            relationship = "session_neighborhood"
            if same_session:
                neighbor_map = {item.evidence_id: item.distance for item in neighborhoods.get(session_id, [])}
                score = max(window + 1 - neighbor_map.get(evidence_id, window + 1), 1) + len(matched_expansion_terms)
        if not include:
            continue
        seen.add(evidence_id)
        inspection = row["inspection"]
        hits.append(
            {
                "evidence_id": evidence_id,
                "session_id": session_id,
                "project_id": evidence["project_id"],
                "project_slug": evidence["project_slug"],
                "session_role": evidence.get("session_role"),
                "source_file": inspection["source_file"],
                "source_line": inspection["source_line"],
                "source_anchor": inspection["source_anchor"],
                "content_text": text,
                "matched_expansion_terms": matched_expansion_terms,
                "expansion_strategy": strategy,
                "relationship": relationship,
                "score": score,
                "evidence_reference": {
                    "view_name": row["view_name"],
                    "view_row_id": row["view_row_id"],
                    "view_ordinal": row["view_ordinal"],
                },
            }
        )
    hits.sort(key=lambda item: (-item["score"], item["session_id"], item["source_line"], item["evidence_id"]))
    return hits[:expansion_limit]


def _discover_expansion_terms(direct_run: DirectHitRun, *, window: int, min_term_frequency: int, limit: int) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for hit in direct_run.hits:
        for token in _tokenize(hit.content_text or ""):
            folded = token.casefold()
            if folded in _STOPWORDS:
                continue
            if folded in {part.casefold() for part in _tokenize(direct_run.seed_term)}:
                continue
            counter[folded] += 1
    results: list[dict[str, Any]] = []
    for term, frequency in counter.most_common():
        if frequency < min_term_frequency:
            continue
        results.append(
            {
                "term": term,
                "frequency": frequency,
                "window": window,
                "source": "direct_hits_lexical_neighborhood",
            }
        )
        if len(results) >= limit:
            break
    return results


def _build_related_sessions(expansion_hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for hit in expansion_hits:
        payload = grouped.setdefault(
            hit["session_id"],
            {
                "session_id": hit["session_id"],
                "project_id": hit["project_id"],
                "project_slug": hit["project_slug"],
                "session_role": hit.get("session_role"),
                "hit_count": 0,
                "evidence_ids": [],
                "matched_expansion_terms": [],
            },
        )
        payload["hit_count"] += 1
        payload["evidence_ids"].append(hit["evidence_id"])
        payload["matched_expansion_terms"].extend(hit["matched_expansion_terms"])
    for payload in grouped.values():
        payload["matched_expansion_terms"] = sorted(set(payload["matched_expansion_terms"]))
    return sorted(grouped.values(), key=lambda item: (-item["hit_count"], item["session_id"]))


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text)
