"""Clustering over canonical evidence slices."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Mapping

from skill_drilla.semantic.base import SemanticEvidenceSlice, SemanticMethod, derived_output_id


class DeterministicClusteringMethod(SemanticMethod):
    method_name = "clustering"
    default_parameters = {
        "backend": "fixture",
        "implementation": "keyword-overlap-v1",
        "min_cluster_size": 1,
        "cluster_key": "leading_token",
        "distance_threshold": 0.0,
        "model": "local-fixture",
    }

    def derive(self, evidence_slice: SemanticEvidenceSlice, parameters: Mapping[str, Any]) -> dict[str, Any]:
        backend = str(parameters.get("backend") or "fixture")
        if backend == "fixture":
            return _derive_fixture_clusters(self.method_name, evidence_slice, parameters)
        if backend == "stella-local":
            return _derive_stella_local_clusters(self.method_name, evidence_slice, parameters)
        raise ValueError(f"unknown clustering backend: {backend}")


def _derive_fixture_clusters(method_name: str, evidence_slice: SemanticEvidenceSlice, parameters: Mapping[str, Any]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for evidence in evidence_slice.evidence:
        token = _cluster_token(evidence.get("content_text") or "")
        grouped[token].append(evidence)

    clusters = []
    for label, items in sorted(grouped.items()):
        if len(items) < int(parameters["min_cluster_size"]):
            continue
        evidence_ids = [item["evidence_id"] for item in items]
        clusters.append(
            {
                "cluster_id": derived_output_id(method_name, evidence_ids, label),
                "label": label,
                "size": len(items),
                "evidence_ids": evidence_ids,
                "scope": {
                    "session_roles": sorted({item.get("session_role") or "unknown" for item in items}),
                    "projects": sorted({item.get("project_slug") for item in items}),
                },
                "representative_excerpt": _representative_excerpt(items[0].get("content_text") or ""),
            }
        )
    return {
        "derived_output_id": derived_output_id(
            method_name,
            [item["evidence_id"] for item in evidence_slice.evidence],
            str(len(clusters)),
        ),
        "kind": "clusters",
        "clusters": clusters,
    }


def _derive_stella_local_clusters(method_name: str, evidence_slice: SemanticEvidenceSlice, parameters: Mapping[str, Any]) -> dict[str, Any]:
    torch, sentence_transformers, sklearn_cluster = _load_stella_clustering_dependencies()
    model_name = str(parameters.get("model") or "NovaSearch/stella_en_1.5B_v5")
    normalize = bool(parameters.get("normalize", True))
    batch_size = int(parameters.get("batch_size") or 8)
    trust_remote_code = bool(parameters.get("trust_remote_code", True))
    device = _resolve_device(torch, str(parameters.get("device") or "auto"))
    torch_dtype_name = str(parameters.get("torch_dtype") or "float16")
    torch_dtype = getattr(torch, torch_dtype_name, None)
    if torch_dtype is None:
        raise ValueError(f"unsupported torch dtype: {torch_dtype_name}")

    model_kwargs: dict[str, Any] = {"torch_dtype": torch_dtype}
    cache_folder = parameters.get("hf_cache_dir")
    init_kwargs: dict[str, Any] = {
        "trust_remote_code": trust_remote_code,
        "device": device,
        "model_kwargs": model_kwargs,
    }
    if cache_folder:
        init_kwargs["cache_folder"] = str(cache_folder)

    model = sentence_transformers.SentenceTransformer(model_name, **init_kwargs)
    texts = [evidence.get("content_text") or "" for evidence in evidence_slice.evidence]
    raw_vectors = model.encode(texts, batch_size=batch_size, normalize_embeddings=normalize)
    vectors = [_sanitize_vector(float(value) for value in vector) for vector in raw_vectors]

    distance_threshold = float(parameters.get("distance_threshold") or 0.3)
    non_zero_items: list[tuple[dict[str, Any], list[float]]] = []
    zero_items: list[tuple[dict[str, Any], list[float]]] = []
    for evidence, vector in zip(evidence_slice.evidence, vectors, strict=True):
        item = (evidence, _sanitize_vector(float(value) for value in vector))
        if _is_zero_vector(item[1]):
            zero_items.append(item)
        else:
            non_zero_items.append(item)

    grouped: dict[int, list[tuple[dict[str, Any], list[float]]]] = defaultdict(list)
    next_label = 0
    if len(non_zero_items) >= 2:
        clustering = sklearn_cluster.AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=distance_threshold,
            metric="cosine",
            linkage="average",
        )
        labels = clustering.fit_predict([vector for _, vector in non_zero_items])
        for label, (evidence, vector) in zip(labels, non_zero_items, strict=True):
            grouped[int(label)].append((evidence, vector))
        next_label = (max(grouped) + 1) if grouped else 0
    elif len(non_zero_items) == 1:
        grouped[0].append(non_zero_items[0])
        next_label = 1

    for evidence, vector in zero_items:
        grouped[next_label].append((evidence, vector))
        next_label += 1

    clusters = []
    min_cluster_size = int(parameters.get("min_cluster_size") or 1)
    for label, items in sorted(grouped.items(), key=lambda item: item[0]):
        if len(items) < min_cluster_size:
            continue
        evidence_ids = [evidence["evidence_id"] for evidence, _ in items]
        representative_index = _select_representative_index([vector for _, vector in items])
        representative = items[representative_index][0]
        clusters.append(
            {
                "cluster_id": derived_output_id(method_name, evidence_ids, str(label), model_name),
                "label": f"cluster_{label}",
                "size": len(items),
                "evidence_ids": evidence_ids,
                "scope": {
                    "session_roles": sorted({evidence.get("session_role") or "unknown" for evidence, _ in items}),
                    "projects": sorted({evidence.get("project_slug") for evidence, _ in items}),
                },
                "representative_excerpt": _representative_excerpt(representative.get("content_text") or ""),
                "backend": "stella-local",
                "model": model_name,
            }
        )

    return {
        "derived_output_id": derived_output_id(
            method_name,
            [item["evidence_id"] for item in evidence_slice.evidence],
            model_name,
            str(len(clusters)),
            str(distance_threshold),
        ),
        "kind": "clusters",
        "clusters": clusters,
    }


def _load_stella_clustering_dependencies() -> tuple[Any, Any, Any]:
    try:
        import torch
        import sentence_transformers
        from sklearn import cluster as sklearn_cluster
    except ImportError as exc:
        raise ImportError(
            "stella-local clustering requires optional dependencies. Install ROCm-compatible torch separately, then install sentence-transformers==3.3.1 and transformers==4.46.3."
        ) from exc
    return torch, sentence_transformers, sklearn_cluster


def _resolve_device(torch: Any, requested: str) -> str:
    if requested not in {"auto", "cpu", "cuda"}:
        raise ValueError(f"unsupported device: {requested}")
    if requested == "auto":
        return "cuda" if bool(torch.cuda.is_available()) else "cpu"
    return requested


def _select_representative_index(vectors: list[list[float]]) -> int:
    if len(vectors) == 1:
        return 0
    best_index = 0
    best_score = float("-inf")
    for index, vector in enumerate(vectors):
        score = 0.0
        for other in vectors:
            score += _cosine_similarity(vector, other)
        if score > best_score:
            best_score = score
            best_index = index
    return best_index


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = sum(a * a for a in left) ** 0.5
    right_norm = sum(b * b for b in right) ** 0.5
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return numerator / (left_norm * right_norm)


def _sanitize_vector(values) -> list[float]:
    sanitized = []
    for value in values:
        if value != value or value in {float("inf"), float("-inf")}:
            sanitized.append(0.0)
        else:
            sanitized.append(float(value))
    return sanitized


def _is_zero_vector(vector: list[float]) -> bool:
    return all(value == 0.0 for value in vector)


def _cluster_token(text: str) -> str:
    normalized = " ".join(text.lower().split())
    if not normalized:
        return "empty"
    first = normalized.split()[0]
    return "".join(char for char in first if char.isalnum() or char in {"_", "-", "/", "."}) or "misc"


def _representative_excerpt(text: str, limit: int = 120) -> str:
    compact = " ".join(text.split())
    return compact if len(compact) <= limit else compact[: limit - 3] + "..."
