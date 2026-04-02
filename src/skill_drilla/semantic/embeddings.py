"""Embedding methods for optional semantic workflows."""

from __future__ import annotations

from typing import Any, Mapping

from skill_drilla.semantic.base import SemanticEvidenceSlice, SemanticMethod, derived_output_id


class FixtureEmbeddingMethod(SemanticMethod):
    method_name = "embeddings"
    default_parameters = {
        "backend": "fixture",
        "implementation": "fixture-hash-embedding",
        "dimensions": 3,
        "normalize": True,
        "model": "local-fixture",
    }

    def derive(self, evidence_slice: SemanticEvidenceSlice, parameters: Mapping[str, Any]) -> dict[str, Any]:
        backend = str(parameters.get("backend") or "fixture")
        if backend == "fixture":
            return _derive_fixture_embeddings(self.method_name, evidence_slice, parameters)
        if backend == "stella-local":
            return _derive_stella_local_embeddings(self.method_name, evidence_slice, parameters)
        raise ValueError(f"unknown embedding backend: {backend}")


def _derive_fixture_embeddings(method_name: str, evidence_slice: SemanticEvidenceSlice, parameters: Mapping[str, Any]) -> dict[str, Any]:
    rows = []
    for evidence in evidence_slice.evidence:
        text = evidence.get("content_text") or ""
        rows.append(
            {
                "evidence_id": evidence["evidence_id"],
                "session_role": evidence.get("session_role"),
                "semantic_class": evidence.get("semantic_class"),
                "vector": _vectorize(text, int(parameters["dimensions"])),
                "text_length": len(text),
                "vector_dimensions": int(parameters["dimensions"]),
                "normalized": bool(parameters.get("normalize", True)),
                "backend": "fixture",
            }
        )
    return {
        "derived_output_id": derived_output_id(method_name, [row["evidence_id"] for row in rows]),
        "kind": "embedding_index",
        "records": rows,
    }


def _derive_stella_local_embeddings(method_name: str, evidence_slice: SemanticEvidenceSlice, parameters: Mapping[str, Any]) -> dict[str, Any]:
    torch, sentence_transformers = _load_stella_dependencies()
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
    vectors = model.encode(texts, batch_size=batch_size, normalize_embeddings=normalize)

    rows = []
    for evidence, vector in zip(evidence_slice.evidence, vectors, strict=True):
        dense = _sanitize_vector(float(value) for value in vector)
        rows.append(
            {
                "evidence_id": evidence["evidence_id"],
                "session_role": evidence.get("session_role"),
                "semantic_class": evidence.get("semantic_class"),
                "vector": dense,
                "text_length": len(evidence.get("content_text") or ""),
                "vector_dimensions": len(dense),
                "normalized": normalize,
                "backend": "stella-local",
            }
        )

    return {
        "derived_output_id": derived_output_id(method_name, [row["evidence_id"] for row in rows], model_name, device),
        "kind": "embedding_index",
        "records": rows,
    }


def _load_stella_dependencies() -> tuple[Any, Any]:
    try:
        import torch
        import sentence_transformers
    except ImportError as exc:
        raise ImportError(
            "stella-local backend requires optional dependencies. Install ROCm-compatible torch separately, then install sentence-transformers==3.3.1 and transformers==4.46.3. See embedding-test/SETUP.md."
        ) from exc
    return torch, sentence_transformers


def _resolve_device(torch: Any, requested: str) -> str:
    if requested not in {"auto", "cpu", "cuda"}:
        raise ValueError(f"unsupported device: {requested}")
    if requested == "auto":
        return "cuda" if bool(torch.cuda.is_available()) else "cpu"
    return requested


def _sanitize_vector(values) -> list[float]:
    sanitized = []
    for value in values:
        if value != value or value in {float("inf"), float("-inf")}:
            sanitized.append(0.0)
        else:
            sanitized.append(float(value))
    return sanitized


def _vectorize(text: str, dimensions: int) -> list[float]:
    if dimensions <= 0:
        raise ValueError("dimensions must be positive")
    bucket = [0.0] * dimensions
    if not text:
        return bucket
    for index, char in enumerate(text):
        bucket[index % dimensions] += (ord(char) % 31) / 31.0
    scale = float(max(len(text), 1))
    return [round(value / scale, 6) for value in bucket]
