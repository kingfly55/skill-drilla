"""Notebook export helpers that package canonical artifacts without reparsing."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Iterable, Sequence

from skill_drilla.notebooks.loaders import load_detector_run


EXPORT_DIR_NAMES = {
    "inventory": "inventory",
    "parse_diagnostics": "parse_diagnostics",
    "evidence": "evidence",
    "corpus_views": "corpus_views",
    "seed_runs": "seed_runs",
    "detector_runs": "detector_runs",
    "reports": "reports",
}



def export_notebook_artifacts(
    output_dir: str | Path,
    *,
    inventory_paths: Sequence[str | Path] = (),
    parse_diagnostics_paths: Sequence[str | Path] = (),
    evidence_paths: Sequence[str | Path] = (),
    view_dirs: Sequence[str | Path] = (),
    seed_run_paths: Sequence[str | Path] = (),
    detector_run_paths: Sequence[str | Path] = (),
    report_metadata_paths: Sequence[str | Path] = (),
) -> dict[str, Any]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    evidence = [Path(path) for path in evidence_paths]
    detector_runs = [Path(path) for path in detector_run_paths]

    inferred_inventory = _infer_inventory_paths(evidence)
    inferred_parse = _infer_parse_diagnostics_paths(evidence)
    inferred_reports = _infer_report_metadata_paths(detector_runs)

    manifest = {
        "inventory": _copy_many(root, "inventory", [*inventory_paths, *inferred_inventory]),
        "parse_diagnostics": _copy_many(root, "parse_diagnostics", [*parse_diagnostics_paths, *inferred_parse]),
        "evidence": _copy_many(root, "evidence", evidence),
        "corpus_views": _copy_many(root, "corpus_views", view_dirs),
        "seed_runs": _copy_many(root, "seed_runs", seed_run_paths),
        "detector_runs": _copy_many(root, "detector_runs", detector_runs),
        "reports": _copy_many(root, "reports", [*report_metadata_paths, *inferred_reports]),
    }

    manifest_path = root / "export_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest["export_manifest"] = str(manifest_path)
    return manifest



def _copy_many(root: Path, category: str, paths: Iterable[str | Path]) -> list[dict[str, str]]:
    dest_dir = root / EXPORT_DIR_NAMES[category]
    dest_dir.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw_path in paths:
        path = Path(raw_path)
        resolved = str(path.resolve())
        if resolved in seen or not path.exists():
            continue
        seen.add(resolved)
        target = dest_dir / _safe_export_name(path)
        if path.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(path, target)
        else:
            shutil.copy2(path, target)
        copied.append({"source": resolved, "exported_path": str(target)})
    copied.sort(key=lambda item: item["source"])
    return copied



def _safe_export_name(path: Path) -> str:
    parent = path.parent.name
    if path.is_dir():
        return path.name
    return f"{parent}__{path.name}" if parent else path.name



def _infer_inventory_paths(evidence_paths: Sequence[Path]) -> list[Path]:
    inferred: list[Path] = []
    for path in evidence_paths:
        artifact_root = _artifact_root(path)
        if artifact_root is None:
            continue
        candidates = sorted((artifact_root / "discovery").glob("**/session_inventory.jsonl"))
        if candidates:
            inferred.append(candidates[0])
    return inferred



def _infer_parse_diagnostics_paths(evidence_paths: Sequence[Path]) -> list[Path]:
    inferred: list[Path] = []
    for path in evidence_paths:
        candidate = path.parent / "parse_diagnostics.json"
        if candidate.exists():
            inferred.append(candidate)
            continue
        artifact_root = _artifact_root(path)
        if artifact_root is None:
            continue
        normalize_scope = path.parent.name
        fallback = artifact_root / "parse" / normalize_scope / "parse_diagnostics.json"
        if fallback.exists():
            inferred.append(fallback)
    return inferred



def _infer_report_metadata_paths(detector_run_paths: Sequence[Path]) -> list[Path]:
    inferred: list[Path] = []
    for path in detector_run_paths:
        artifact_root = _artifact_root(path)
        if artifact_root is None or not path.exists():
            continue
        payload = load_detector_run(path)
        detector_name = payload.get("detector")
        if detector_name:
            candidate = artifact_root / "reports" / str(detector_name) / "report_metadata.json"
            if candidate.exists():
                inferred.append(candidate)
    return inferred



def _artifact_root(path: Path) -> Path | None:
    resolved = path.resolve()
    for parent in (resolved.parent, *resolved.parents):
        if parent.name == "chat-analysis" and parent.parent.name == "artifacts":
            return parent
    return None
