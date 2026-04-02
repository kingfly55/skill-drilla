"""Performance measurement helpers for validation runs."""

from __future__ import annotations

import json
import time
import tracemalloc
from pathlib import Path
from typing import Any, Callable


def measure_callable(name: str, func: Callable[[], Any]) -> tuple[Any, dict[str, Any]]:
    started = time.perf_counter()
    result = func()
    elapsed = time.perf_counter() - started
    return result, {"name": name, "runtime_seconds": round(elapsed, 6)}


def measure_streaming_memory(path: str | Path) -> dict[str, float]:
    target = Path(path)
    tracemalloc.start()
    line_count = 0
    with target.open("r", encoding="utf-8") as handle:
        for _ in handle:
            line_count += 1
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "streamed_line_count": line_count,
        "streaming_memory_peak_mb": round(peak / (1024 * 1024), 6),
    }


def build_performance_summary(*, validate_runtime_seconds: float, streaming_memory_peak_mb: float, command_runtimes: dict[str, float], streamed_line_count: int) -> dict[str, Any]:
    return {
        "validate_runtime_seconds": round(validate_runtime_seconds, 6),
        "streaming_memory_peak_mb": round(streaming_memory_peak_mb, 6),
        "command_runtimes": {key: round(value, 6) for key, value in sorted(command_runtimes.items())},
        "streamed_line_count": streamed_line_count,
    }


def write_performance_summary(output_path: str | Path, payload: dict[str, Any]) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
