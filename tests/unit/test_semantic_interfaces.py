import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from skill_drilla.semantic import SEMANTIC_METHODS, SemanticEvidenceSlice, get_semantic_method, write_semantic_run


REPO_ROOT = Path(__file__).resolve().parents[2]
VIEW_DIR = REPO_ROOT / "artifacts" / "chat-analysis" / "views" / "user_nl_root_only"


def test_semantic_registry_exposes_optional_methods():
    assert set(SEMANTIC_METHODS) == {"embeddings", "clustering", "interpretation", "skill-mining"}


def test_semantic_slice_preserves_canonical_evidence_metadata():
    evidence_slice = SemanticEvidenceSlice.from_view_dir(VIEW_DIR)
    canonical_input = evidence_slice.canonical_input()

    assert evidence_slice.view_name == "user_nl_root_only"
    assert canonical_input["evidence_count"] == len(evidence_slice.evidence)
    assert canonical_input["evidence_ids"]
    assert {"root"} <= set(canonical_input["session_roles"])
    first = evidence_slice.evidence[0]
    assert {"evidence_id", "session_role", "semantic_class", "project_slug", "scope"} <= set(first)


def test_clustering_run_is_non_canonical_and_reproducible(tmp_path: Path):
    evidence_slice = SemanticEvidenceSlice.from_view_dir(VIEW_DIR)
    run = get_semantic_method("clustering").build_run(evidence_slice)

    assert run.method == "clustering"
    assert run.non_canonical is True
    assert run.parameters["implementation"] == "keyword-overlap-v1"
    assert run.parameters["model"] == "local-fixture"
    assert run.derived_output["kind"] == "clusters"
    assert "clusters" in run.derived_output
    if run.derived_output["clusters"]:
        cluster = run.derived_output["clusters"][0]
        assert {"cluster_id", "evidence_ids", "scope", "label"} <= set(cluster)

    artifacts = write_semantic_run(tmp_path, run)
    payload = json.loads(Path(artifacts["semantic_run"]).read_text(encoding="utf-8"))
    assert payload["non_canonical"] is True
    assert payload["canonical_input"]["view_name"] == "user_nl_root_only"


def test_embedding_and_interpretation_runs_preserve_evidence_ids():
    evidence_slice = SemanticEvidenceSlice.from_view_dir(VIEW_DIR)
    evidence_ids = {item["evidence_id"] for item in evidence_slice.evidence}

    embedding_run = get_semantic_method("embeddings").build_run(evidence_slice)
    interpretation_run = get_semantic_method("interpretation").build_run(evidence_slice)

    assert embedding_run.parameters["backend"] == "fixture"
    assert {row["evidence_id"] for row in embedding_run.derived_output["records"]} == evidence_ids
    assert {row["evidence_id"] for row in interpretation_run.derived_output["examples"]} <= evidence_ids


def test_stella_local_embedding_backend_preserves_evidence_ids():
    evidence_slice = SemanticEvidenceSlice.from_view_dir(VIEW_DIR)

    class FakeModel:
        def __init__(self, model_name: str, **kwargs):
            self.model_name = model_name
            self.kwargs = kwargs

        def encode(self, texts, batch_size: int, normalize_embeddings: bool):
            assert batch_size == 4
            assert normalize_embeddings is True
            return [[float(index), float(index) + 0.5] for index, _ in enumerate(texts, start=1)]

    fake_torch = SimpleNamespace(
        float16="float16",
        float32="float32",
        cuda=SimpleNamespace(is_available=lambda: True),
    )
    fake_sentence_transformers = SimpleNamespace(SentenceTransformer=FakeModel)

    with patch("skill_drilla.semantic.embeddings._load_stella_dependencies", return_value=(fake_torch, fake_sentence_transformers)):
        run = get_semantic_method("embeddings").build_run(
            evidence_slice,
            parameters={
                "backend": "stella-local",
                "implementation": "stella-local",
                "model": "NovaSearch/stella_en_1.5B_v5",
                "device": "cuda",
                "batch_size": 4,
                "torch_dtype": "float16",
                "trust_remote_code": True,
                "normalize": True,
            },
        )

    assert run.parameters["backend"] == "stella-local"
    assert run.parameters["model"] == "NovaSearch/stella_en_1.5B_v5"
    assert run.derived_output["kind"] == "embedding_index"
    assert {row["evidence_id"] for row in run.derived_output["records"]} == {
        item["evidence_id"] for item in evidence_slice.evidence
    }
    assert all(row["vector_dimensions"] == 2 for row in run.derived_output["records"])
    assert all(row["backend"] == "stella-local" for row in run.derived_output["records"])


def test_stella_local_embedding_backend_requires_optional_dependencies():
    evidence_slice = SemanticEvidenceSlice.from_view_dir(VIEW_DIR)

    with patch(
        "skill_drilla.semantic.embeddings._load_stella_dependencies",
        side_effect=ImportError("stella-local backend requires optional dependencies"),
    ):
        try:
            get_semantic_method("embeddings").build_run(
                evidence_slice,
                parameters={"backend": "stella-local", "implementation": "stella-local"},
            )
        except ImportError as exc:
            assert "stella-local backend requires optional dependencies" in str(exc)
        else:
            raise AssertionError("expected stella-local backend to require optional dependencies")


def test_stella_local_clustering_backend_groups_evidence():
    evidence_slice = SemanticEvidenceSlice.from_view_dir(VIEW_DIR)

    class FakeModel:
        def __init__(self, model_name: str, **kwargs):
            self.model_name = model_name
            self.kwargs = kwargs

        def encode(self, texts, batch_size: int, normalize_embeddings: bool):
            assert batch_size == 3
            assert normalize_embeddings is True
            vectors = []
            for index, _ in enumerate(texts):
                if index < 2:
                    vectors.append([1.0, 0.0])
                else:
                    vectors.append([0.0, 1.0])
            return vectors

    class FakeAgglomerativeClustering:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def fit_predict(self, vectors):
            return [0 if vector[0] > vector[1] else 1 for vector in vectors]

    fake_torch = SimpleNamespace(
        float16="float16",
        float32="float32",
        cuda=SimpleNamespace(is_available=lambda: True),
    )
    fake_sentence_transformers = SimpleNamespace(SentenceTransformer=FakeModel)
    fake_sklearn_cluster = SimpleNamespace(AgglomerativeClustering=FakeAgglomerativeClustering)

    with patch(
        "skill_drilla.semantic.clustering._load_stella_clustering_dependencies",
        return_value=(fake_torch, fake_sentence_transformers, fake_sklearn_cluster),
    ):
        run = get_semantic_method("clustering").build_run(
            evidence_slice,
            parameters={
                "backend": "stella-local",
                "implementation": "stella-local-agglomerative",
                "model": "NovaSearch/stella_en_1.5B_v5",
                "device": "cuda",
                "batch_size": 3,
                "torch_dtype": "float16",
                "trust_remote_code": True,
                "normalize": True,
                "distance_threshold": 0.3,
                "min_cluster_size": 1,
            },
        )

    assert run.method == "clustering"
    assert run.parameters["backend"] == "stella-local"
    assert run.parameters["implementation"] == "stella-local-agglomerative"
    assert run.derived_output["kind"] == "clusters"
    assert run.derived_output["clusters"]
    assert all(cluster["backend"] == "stella-local" for cluster in run.derived_output["clusters"])
    assert all(cluster["model"] == "NovaSearch/stella_en_1.5B_v5" for cluster in run.derived_output["clusters"])


def test_stella_local_clustering_backend_requires_optional_dependencies():
    evidence_slice = SemanticEvidenceSlice.from_view_dir(VIEW_DIR)

    with patch(
        "skill_drilla.semantic.clustering._load_stella_clustering_dependencies",
        side_effect=ImportError("stella-local clustering requires optional dependencies"),
    ):
        try:
            get_semantic_method("clustering").build_run(
                evidence_slice,
                parameters={"backend": "stella-local", "implementation": "stella-local-agglomerative"},
            )
        except ImportError as exc:
            assert "stella-local clustering requires optional dependencies" in str(exc)
        else:
            raise AssertionError("expected stella-local clustering backend to require optional dependencies")
