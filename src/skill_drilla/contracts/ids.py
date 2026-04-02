"""Stable identifier helpers for reproducible artifacts."""

from __future__ import annotations

import hashlib
from typing import Iterable


def stable_id(*parts: str) -> str:
    normalized = "::".join(part.strip() for part in parts if part is not None)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def config_fingerprint(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def join_scope_label(parts: Iterable[str]) -> str:
    values = [part.strip() for part in parts if part and part.strip()]
    return "/".join(values) if values else "default-local"
