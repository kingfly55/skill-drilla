"""Pydantic AI-backed skill-mining semantic method for episode analysis."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from skill_drilla.semantic.base import SemanticEvidenceSlice, SemanticMethod, SemanticRun, derived_output_id


_DEFAULT_BASE_URL = os.environ.get("SKILLDRILLA_LLM_BASE_URL", "https://api.openai.com/v1")
_DEFAULT_API_KEY = os.environ.get("SKILLDRILLA_LLM_API_KEY", "")
_DEFAULT_MODEL = os.environ.get("SKILLDRILLA_LLM_MODEL", "gpt-4o-mini")
_DEFAULT_MODEL_HEAVY = os.environ.get("SKILLDRILLA_LLM_MODEL_HEAVY", os.environ.get("SKILLDRILLA_LLM_MODEL", "gpt-4o"))


class SkillMiningMethod(SemanticMethod):
    """
    Optional skill-mining semantic method.

    Reads episode artifacts produced by ``extract-episodes`` and generates
    candidate skills representing recurring request patterns.

    Two backends:
    - ``fixture``: deterministic keyword-cluster grouping, no LLM required.
    - ``pydantic-ai``: LLM-backed generalization via Pydantic AI, routed
      through an OpenAI-compatible endpoint at ``base_url``.

    All output is ``non_canonical: true``.
    """

    method_name = "skill-mining"
    default_parameters: dict[str, Any] = {
        "backend": "fixture",
        "implementation": "keyword-cluster-v1",
        "base_url": _DEFAULT_BASE_URL,
        "model": _DEFAULT_MODEL,
        "max_skills": 10,
        "max_turns_per_skill": 3,
        "max_episode_turns": 5,
        "model_heavy": _DEFAULT_MODEL_HEAVY,
    }

    def build_run(
        self,
        evidence_slice: SemanticEvidenceSlice | None,
        *,
        parameters: Mapping[str, Any] | None = None,
    ) -> SemanticRun:
        merged: dict[str, Any] = {**self.default_parameters, **(parameters or {})}

        episodes = _load_episodes(merged.get("episode_dir"))

        canonical_input: dict[str, Any] = {
            "episode_dir": merged.get("episode_dir"),
            "episode_count": len(episodes),
            "episode_ids": [ep.get("episode_id") for ep in episodes],
        }

        derived_output = self.derive_from_episodes(episodes, merged)

        # Never persist the api_key in stored parameters
        stored_params = {k: v for k, v in merged.items() if k != "api_key"}

        return SemanticRun(
            method=self.method_name,
            canonical_input=canonical_input,
            derived_output=derived_output,
            parameters=stored_params,
            non_canonical=True,
        )

    def derive(self, evidence_slice: SemanticEvidenceSlice, parameters: Mapping[str, Any]) -> dict[str, Any]:
        # Fallback used when called via base-class pathway; episodes come from parameters.
        return self.derive_from_episodes([], parameters)

    def derive_from_episodes(self, episodes: list[dict[str, Any]], parameters: Mapping[str, Any]) -> dict[str, Any]:
        backend = parameters.get("backend", "fixture")
        if backend == "fixture":
            return _derive_fixture(episodes, parameters)
        if backend == "pydantic-ai":
            api_key = parameters.get("api_key", _DEFAULT_API_KEY)
            return _derive_pydantic_ai(episodes, parameters, api_key)
        raise ValueError(f"unknown skill-mining backend: {backend!r}")


# ---------------------------------------------------------------------------
# Episode loading
# ---------------------------------------------------------------------------

def _load_episodes(episode_dir: str | None) -> list[dict[str, Any]]:
    """Load episodes from an episode directory (episodes.jsonl)."""
    if not episode_dir:
        return []
    ep_dir = Path(episode_dir)
    episodes_path = ep_dir / "episodes.jsonl"
    if not episodes_path.exists():
        return []
    episodes = []
    for line in episodes_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            episodes.append(json.loads(line))
    return episodes


# ---------------------------------------------------------------------------
# Fixture (deterministic) backend
# ---------------------------------------------------------------------------

def _derive_fixture(episodes: list[dict[str, Any]], parameters: Mapping[str, Any]) -> dict[str, Any]:
    """Deterministic keyword-based skill clustering — no LLM required."""
    max_skills = int(parameters.get("max_skills", 10))
    max_turns_per_skill = int(parameters.get("max_turns_per_skill", 3))

    user_turns = _collect_user_turns(episodes, int(parameters.get("max_episode_turns", 5)))

    # Group by leading token (deterministic, order-stable)
    clusters: dict[str, list[dict[str, Any]]] = {}
    for turn in user_turns:
        token = _leading_token(turn.get("content_text") or "")
        if token not in clusters:
            clusters[token] = []
        clusters[token].append(turn)

    candidate_skills = []
    for token, turns in sorted(clusters.items()):
        if len(candidate_skills) >= max_skills:
            break
        rep_turns = turns[:max_turns_per_skill]
        skill_id = derived_output_id(
            "skill-mining",
            [t["evidence_id"] for t in rep_turns if t.get("evidence_id")],
            token,
        )
        candidate_skills.append({
            "skill_id": skill_id,
            "candidate_label": token,
            "description": f"Requests beginning with '{token}'",
            "confidence": None,
            "turn_count": len(turns),
            "representative_episode_ids": _unique_preserve_order(
                t.get("episode_id") for t in rep_turns
            ),
            "representative_turn_refs": [
                _turn_ref(t) for t in rep_turns
            ],
            "supporting_evidence_ids": [
                t.get("evidence_id") for t in turns if t.get("evidence_id")
            ],
        })

    output_id = derived_output_id(
        "skill-mining",
        [t.get("evidence_id") for t in user_turns if t.get("evidence_id")],
        "fixture",
    )
    return {
        "derived_output_id": output_id,
        "kind": "skill_mining",
        "non_canonical": True,
        "implementation": parameters.get("implementation", "keyword-cluster-v1"),
        "candidate_skill_count": len(candidate_skills),
        "candidate_skills": candidate_skills,
        "scope": {
            "episode_count": len(episodes),
            "user_turn_count": len(user_turns),
        },
        "caveats": [
            "Fixture backend: deterministic keyword-based grouping, not LLM-backed.",
            "Candidate skills are not verified or normalized by a model.",
        ],
    }


# ---------------------------------------------------------------------------
# Pydantic AI (LLM-backed) backend
# ---------------------------------------------------------------------------

def _derive_pydantic_ai(
    episodes: list[dict[str, Any]],
    parameters: Mapping[str, Any],
    api_key: str,
) -> dict[str, Any]:
    """LLM-backed skill mining via Pydantic AI, routed through OpenAI-compatible endpoint."""
    Agent, make_model, SkillMiningResult = _load_pydantic_ai_dependencies()

    base_url = parameters.get("base_url", _DEFAULT_BASE_URL)
    model_name = parameters.get("model", _DEFAULT_MODEL)
    max_skills = int(parameters.get("max_skills", 10))
    max_episode_turns = int(parameters.get("max_episode_turns", 5))
    max_turns_per_skill = int(parameters.get("max_turns_per_skill", 3))

    user_turns = _collect_user_turns(episodes, max_episode_turns)

    if not user_turns:
        return _empty_output(episodes, parameters, "no user turns found in episodes")

    # Build bounded excerpt list for LLM context
    excerpts = []
    for i, turn in enumerate(user_turns[:50]):
        text = _summarize_text(turn.get("content_text") or "", 200)
        excerpts.append(f"[{i + 1}] {text}")

    prompt = _build_prompt(excerpts, max_skills)

    # Strip the "openai:" prefix if present — the provider takes the bare model name
    raw_model_name = model_name.removeprefix("openai:")
    openai_model = make_model(raw_model_name, base_url, api_key)
    agent = Agent(openai_model, output_type=SkillMiningResult)
    result = agent.run_sync(prompt)
    mined = result.output

    candidate_skills = []
    for skill in mined.candidate_skills[:max_skills]:
        rep_turns = [
            user_turns[idx - 1]
            for idx in skill.turn_indices[:max_turns_per_skill]
            if 1 <= idx <= len(user_turns)
        ]
        if not rep_turns:
            rep_turns = user_turns[:1]

        skill_id = derived_output_id(
            "skill-mining",
            [t["evidence_id"] for t in rep_turns if t.get("evidence_id")],
            skill.candidate_label,
        )
        candidate_skills.append({
            "skill_id": skill_id,
            "candidate_label": skill.candidate_label,
            "description": skill.description,
            "confidence": skill.confidence,
            "turn_count": len(skill.turn_indices),
            "representative_episode_ids": _unique_preserve_order(
                t.get("episode_id") for t in rep_turns
            ),
            "representative_turn_refs": [_turn_ref(t) for t in rep_turns],
            "supporting_evidence_ids": [
                t.get("evidence_id") for t in rep_turns if t.get("evidence_id")
            ],
        })

    output_id = derived_output_id(
        "skill-mining",
        [t.get("evidence_id") for t in user_turns if t.get("evidence_id")],
        "pydantic-ai",
    )
    return {
        "derived_output_id": output_id,
        "kind": "skill_mining",
        "non_canonical": True,
        "implementation": parameters.get("implementation", "pydantic-ai-v1"),
        "candidate_skill_count": len(candidate_skills),
        "candidate_skills": candidate_skills,
        "scope": {
            "episode_count": len(episodes),
            "user_turn_count": len(user_turns),
        },
        "model_config": {
            "base_url": base_url,
            "model": model_name,
        },
        "caveats": [
            "Pydantic AI backend: LLM-backed skill generalization.",
            "Output is non-canonical and model-dependent.",
        ],
    }


def _build_prompt(excerpts: list[str], max_skills: int) -> str:
    joined = "\n".join(excerpts)
    return (
        f"You are analyzing request episodes from a software development AI assistant.\n"
        f"Below are user requests extracted from transcripts.\n"
        f"Identify up to {max_skills} candidate skills representing recurring request patterns.\n\n"
        f"User requests:\n{joined}\n\n"
        f"For each candidate skill:\n"
        f"- candidate_label: short name (2-5 words, underscore_separated)\n"
        f"- description: one sentence describing the skill\n"
        f"- confidence: float 0.0-1.0 (how confident this is a recurring pattern)\n"
        f"- turn_indices: list of 1-based turn numbers exemplifying this skill\n\n"
        f"Only include skills that appear in at least 2 requests. "
        f"Return your answer as structured data."
    )


def _load_pydantic_ai_dependencies():
    """Lazily import pydantic-ai and return (Agent, provider_factory, SkillMiningResult)."""
    try:
        from pydantic import BaseModel
        from pydantic_ai import Agent
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider
    except ImportError as exc:
        raise ImportError(
            "pydantic-ai is required for the pydantic-ai skill-mining backend. "
            "Install it with: pip install pydantic-ai  "
            "(or: pip install 'skill-drilla[skill-mining]')"
        ) from exc

    class CandidateSkillItem(BaseModel):
        candidate_label: str
        description: str
        confidence: float
        turn_indices: list[int]

    class SkillMiningResult(BaseModel):
        candidate_skills: list[CandidateSkillItem]

    def make_model(model_name: str, base_url: str, api_key: str) -> OpenAIChatModel:
        provider = OpenAIProvider(base_url=base_url, api_key=api_key)
        return OpenAIChatModel(model_name, provider=provider)

    return Agent, make_model, SkillMiningResult


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _collect_user_turns(episodes: list[dict[str, Any]], max_per_episode: int) -> list[dict[str, Any]]:
    """Extract user NL turns across all episodes, capped per episode."""
    turns = []
    for episode in episodes:
        count = 0
        for turn in episode.get("turns", []):
            if turn.get("role") == "user":
                turns.append(turn)
                count += 1
                if count >= max_per_episode:
                    break
    return turns


def _turn_ref(turn: dict[str, Any]) -> dict[str, Any]:
    return {
        "turn_id": turn.get("turn_id"),
        "evidence_id": turn.get("evidence_id"),
        "raw_event_id": turn.get("raw_event_id"),
        "session_id": turn.get("session_id"),
        "excerpt": _summarize_text(turn.get("content_text") or "", 80),
    }


def _leading_token(text: str) -> str:
    words = text.split()
    return words[0].lower() if words else "_empty_"


def _summarize_text(text: str, limit: int = 80) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 3] + "..."


def _unique_preserve_order(values) -> list:
    seen: set = set()
    result = []
    for v in values:
        if v is not None and v not in seen:
            seen.add(v)
            result.append(v)
    return result


def _empty_output(episodes: list[dict[str, Any]], parameters: Mapping[str, Any], reason: str) -> dict[str, Any]:
    output_id = derived_output_id("skill-mining", [], reason)
    return {
        "derived_output_id": output_id,
        "kind": "skill_mining",
        "non_canonical": True,
        "implementation": parameters.get("implementation", "keyword-cluster-v1"),
        "candidate_skill_count": 0,
        "candidate_skills": [],
        "scope": {
            "episode_count": len(episodes),
            "user_turn_count": 0,
        },
        "caveats": [reason],
    }
