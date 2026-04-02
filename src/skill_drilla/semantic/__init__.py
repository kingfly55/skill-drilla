"""Optional semantic analysis extension points."""

from skill_drilla.semantic.base import SemanticEvidenceSlice, SemanticMethod, SemanticRun, write_semantic_run
from skill_drilla.semantic.clustering import DeterministicClusteringMethod
from skill_drilla.semantic.embeddings import FixtureEmbeddingMethod
from skill_drilla.semantic.interpretation import FixtureInterpretationMethod
from skill_drilla.semantic.skill_mining import SkillMiningMethod

SEMANTIC_METHODS = {
    "embeddings": FixtureEmbeddingMethod(),
    "clustering": DeterministicClusteringMethod(),
    "interpretation": FixtureInterpretationMethod(),
    "skill-mining": SkillMiningMethod(),
}


def get_semantic_method(name: str) -> SemanticMethod:
    try:
        return SEMANTIC_METHODS[name]
    except KeyError as exc:
        raise ValueError(f"unknown semantic method: {name}") from exc


__all__ = [
    "DeterministicClusteringMethod",
    "FixtureEmbeddingMethod",
    "FixtureInterpretationMethod",
    "SEMANTIC_METHODS",
    "SemanticEvidenceSlice",
    "SemanticMethod",
    "SemanticRun",
    "SkillMiningMethod",
    "get_semantic_method",
    "write_semantic_run",
]
