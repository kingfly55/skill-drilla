"""Detector framework for evidence-backed pattern analysis over corpus views."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Iterator, Mapping

from skill_drilla.search.index import load_view_artifacts
from skill_drilla.views import RECURRENCE_BASIS_DEFAULT, compute_recurrence_counts

DEFAULT_MAX_EVIDENCE = 5
DEFAULT_MIN_DISTINCT_SESSIONS = 1
DEFAULT_MIN_RAW_OCCURRENCES = 1


@dataclass(frozen=True)
class EvidenceReference:
    evidence_id: str
    session_id: str
    project_id: str
    project_slug: str
    session_role: str | None
    source_file: str
    source_line: int
    source_anchor: str
    excerpt: str | None
    qualification: str

    @classmethod
    def from_row(cls, row: Mapping[str, Any], *, qualification: str) -> "EvidenceReference":
        evidence = row["evidence"]
        inspection = row["inspection"]
        return cls(
            evidence_id=evidence["evidence_id"],
            session_id=evidence["session_id"],
            project_id=evidence["project_id"],
            project_slug=evidence["project_slug"],
            session_role=evidence.get("session_role"),
            source_file=inspection["source_file"],
            source_line=inspection["source_line"],
            source_anchor=inspection["source_anchor"],
            excerpt=_truncate_excerpt(evidence.get("content_text")),
            qualification=qualification,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "session_id": self.session_id,
            "project_id": self.project_id,
            "project_slug": self.project_slug,
            "session_role": self.session_role,
            "source_file": self.source_file,
            "source_line": self.source_line,
            "source_anchor": self.source_anchor,
            "excerpt": self.excerpt,
            "qualification": self.qualification,
        }


@dataclass(frozen=True)
class Finding:
    finding_id: str
    detector: str
    category: str
    title: str
    summary: str
    recurrence: dict[str, int]
    recurrence_basis: dict[str, str]
    evidence: tuple[EvidenceReference, ...]
    detector_metadata: dict[str, Any]
    diagnostics: dict[str, Any]
    caveats: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "detector": self.detector,
            "category": self.category,
            "title": self.title,
            "summary": self.summary,
            "recurrence": self.recurrence,
            "recurrence_basis": self.recurrence_basis,
            "evidence": [item.to_dict() for item in self.evidence],
            "detector_metadata": self.detector_metadata,
            "diagnostics": self.diagnostics,
            "caveats": list(self.caveats),
        }


@dataclass(frozen=True)
class DetectorRun:
    detector: str
    view_name: str
    settings: dict[str, Any]
    findings: tuple[Finding, ...]
    diagnostics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "detector": self.detector,
            "view_name": self.view_name,
            "settings": self.settings,
            "findings": [finding.to_dict() for finding in self.findings],
            "diagnostics": self.diagnostics,
        }


@dataclass(frozen=True)
class FindingCandidate:
    key: str
    category: str
    title: str
    summary: str
    rows: tuple[dict[str, Any], ...]
    diagnostics: dict[str, Any] = field(default_factory=dict)
    caveats: tuple[str, ...] = ()


class BaseDetector:
    detector_name = "base"
    category = "base"
    version = "1.0"
    default_settings: dict[str, Any] = {}

    def build_run(self, view_dir: Path, settings: Mapping[str, Any] | None = None) -> DetectorRun:
        artifacts = load_view_artifacts(view_dir)
        merged_settings = {
            "min_raw_occurrences": DEFAULT_MIN_RAW_OCCURRENCES,
            "min_distinct_sessions": DEFAULT_MIN_DISTINCT_SESSIONS,
            "max_evidence": DEFAULT_MAX_EVIDENCE,
            **self.default_settings,
            **(settings or {}),
        }
        rows = tuple(iter_view_rows(artifacts.corpus_view_path))
        findings: list[Finding] = []
        candidates_seen = 0
        for candidate in self.iter_candidates(rows, merged_settings):
            candidates_seen += 1
            recurrence = compute_recurrence_counts(row["evidence"] for row in candidate.rows)
            if recurrence["raw_occurrences"] < int(merged_settings["min_raw_occurrences"]):
                continue
            if recurrence["distinct_sessions"] < int(merged_settings["min_distinct_sessions"]):
                continue
            evidence = tuple(
                EvidenceReference.from_row(row, qualification=self.describe_qualification(row, candidate))
                for row in candidate.rows[: int(merged_settings["max_evidence"])]
            )
            findings.append(
                Finding(
                    finding_id=_stable_finding_id(self.detector_name, candidate.key),
                    detector=self.detector_name,
                    category=candidate.category,
                    title=candidate.title,
                    summary=candidate.summary,
                    recurrence=recurrence,
                    recurrence_basis=dict(RECURRENCE_BASIS_DEFAULT),
                    evidence=evidence,
                    detector_metadata={
                        "version": self.version,
                        "ruleset": self.detector_name,
                    },
                    diagnostics={
                        **candidate.diagnostics,
                        "candidate_key": candidate.key,
                        "qualified_evidence_count": len(candidate.rows),
                    },
                    caveats=candidate.caveats,
                )
            )
        findings.sort(key=lambda item: (-item.recurrence["distinct_sessions"], -item.recurrence["raw_occurrences"], item.title))
        return DetectorRun(
            detector=self.detector_name,
            view_name=artifacts.view_name,
            settings=merged_settings,
            findings=tuple(findings),
            diagnostics={
                "view_id": artifacts.view_summary.get("view_id"),
                "source_evidence_path": artifacts.view_summary.get("source_evidence_path"),
                "subagent_policy": artifacts.view_summary.get("subagent_policy"),
                "recurrence_basis": artifacts.view_summary.get("recurrence_basis", dict(RECURRENCE_BASIS_DEFAULT)),
                "rows_scanned": len(rows),
                "candidates_considered": candidates_seen,
                "qualified_findings": len(findings),
                "detector_version": self.version,
            },
        )

    def iter_candidates(self, rows: Iterable[dict[str, Any]], settings: Mapping[str, Any]) -> Iterator[FindingCandidate]:
        raise NotImplementedError

    def describe_qualification(self, row: Mapping[str, Any], candidate: FindingCandidate) -> str:
        return f"Matched {candidate.category} detector heuristic"


KEYWORD_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_./:-]{2,}")
STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "your", "have", "just", "what", "when",
    "will", "would", "there", "about", "them", "they", "then", "than", "were", "been", "should", "could",
    "please", "make", "need", "want", "like", "dont", "can't", "cant", "you", "our", "are", "not", "can",
}


def iter_view_rows(corpus_view_path: Path) -> Iterator[dict[str, Any]]:
    with corpus_view_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def canonicalize_text(text: str | None) -> str:
    cleaned = " ".join((text or "").lower().split())
    cleaned = re.sub(r"[^a-z0-9\s_./:-]", " ", cleaned)
    return " ".join(cleaned.split())


def extract_keywords(text: str | None) -> tuple[str, ...]:
    return tuple(
        token for token in KEYWORD_TOKEN_RE.findall(canonicalize_text(text))
        if token not in STOPWORDS
    )


def is_instruction_like(text: str | None) -> bool:
    lowered = canonicalize_text(text)
    return bool(lowered) and (
        lowered.startswith(("add ", "update ", "fix ", "make ", "change ", "implement ", "create ", "write ", "remove ", "set "))
        or " please " in f" {lowered} "
        or lowered.startswith("you are implementing milestone")
    )


def _truncate_excerpt(text: str | None, limit: int = 220) -> str | None:
    if text is None:
        return None
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 3] + "..."


def _stable_finding_id(detector: str, key: str) -> str:
    import hashlib

    return hashlib.sha256(f"{detector}:{key}".encode("utf-8")).hexdigest()
