"""End-to-end validation workflow over canonical local artifacts."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from skill_drilla.config import dump_effective_config, load_config
from skill_drilla.detect import DETECTOR_REGISTRY, get_detector
from skill_drilla.discovery import apply_scope, discover_corpus, write_discovery_artifacts
from skill_drilla.discovery.inventory import DiscoverySummary
from skill_drilla.normalize import write_normalize_artifacts
from skill_drilla.notebooks import export_notebook_artifacts
from skill_drilla.parse import iter_raw_events, write_parse_artifacts
from skill_drilla.report import generate_report
from skill_drilla.search import SearchFilters, parse_query, run_search, write_search_result
from skill_drilla.seed import build_seed_run, write_seed_run
from skill_drilla.validate.performance import build_performance_summary, measure_callable, measure_streaming_memory, write_performance_summary
from skill_drilla.validate.traceability import build_traceability_samples, write_traceability_samples
from skill_drilla.views import STANDARD_VIEW_DEFINITIONS, build_view


def run_validation(*, config_path: str | Path, projects_root: str | Path, output_dir: str | Path) -> dict[str, Any]:
    started = time.perf_counter()
    config = load_config(config_path)
    projects_root_path = Path(projects_root)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    (root / "effective_config.json").write_text(dump_effective_config(config) + "\n", encoding="utf-8")

    runtimes: dict[str, float] = {}

    discovery_dir = root / "discovery"
    discovery_result, perf = measure_callable("discovery", lambda: discover_corpus(projects_root_path))
    runtimes["discovery"] = perf["runtime_seconds"]
    scoped = apply_scope(discovery_result.records, config.input_scope)
    discovery_summary = DiscoverySummary.from_records(discovery_result.records, scoped.excluded_records)
    discovery_artifacts = write_discovery_artifacts(
        discovery_dir,
        records=discovery_result.records,
        scoped=scoped,
        summary=discovery_summary,
        project_count=len(discovery_result.projects),
    )
    discovery_payload = json.loads((discovery_dir / "inventory_summary.json").read_text(encoding="utf-8"))
    discovery_payload["lineage_coverage"] = {
        "confirmed": sum(1 for record in scoped.records if record.lineage_state == "confirmed"),
        "unknown": sum(1 for record in scoped.records if record.lineage_state != "confirmed"),
    }
    (discovery_dir / "inventory_summary.json").write_text(json.dumps(discovery_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    parse_dir = root / "parse"
    _, perf = measure_callable(
        "parse",
        lambda: write_parse_artifacts(parse_dir, scoped.records, iter_raw_events),
    )
    runtimes["parse"] = perf["runtime_seconds"]
    parse_artifacts = {
        "output_dir": str(parse_dir),
        "raw_events": str(parse_dir / "raw_events.jsonl"),
        "parse_diagnostics": str(parse_dir / "parse_diagnostics.json"),
    }

    normalize_dir = root / "normalize"
    _, perf = measure_callable(
        "normalize",
        lambda: write_normalize_artifacts(
            normalize_dir,
            scoped.records,
            _load_jsonl_models(parse_dir / "raw_events.jsonl", model="raw_event"),
        ),
    )
    runtimes["normalize"] = perf["runtime_seconds"]
    normalize_artifacts = {
        "output_dir": str(normalize_dir),
        "evidence": str(normalize_dir / "evidence.jsonl"),
        "normalization_diagnostics": str(normalize_dir / "normalization_diagnostics.json"),
    }

    views_dir = root / "views"
    view_outputs: dict[str, dict[str, str]] = {}
    for view_name in STANDARD_VIEW_DEFINITIONS:
        _, perf = measure_callable(
            f"view:{view_name}",
            lambda view_name=view_name: build_view(view_name, normalize_dir / "evidence.jsonl", views_dir / view_name),
        )
        runtimes[f"view:{view_name}"] = perf["runtime_seconds"]
        view_outputs[view_name] = {
            "output_dir": str(views_dir / view_name),
            "corpus_view": str(views_dir / view_name / "corpus_view.jsonl"),
            "view_summary": str(views_dir / view_name / "view_summary.json"),
        }

    search_dir = root / "search"
    search_result, perf = measure_callable(
        "search",
        lambda: run_search(
            views_dir / "user_nl_root_only",
            parse_query("please OR milestone OR report"),
            SearchFilters(include_subagents=False),
        ),
    )
    runtimes["search"] = perf["runtime_seconds"]
    search_artifacts = write_search_result(search_dir, search_result)

    seed_dir = root / "seed"
    seed_run, perf = measure_callable(
        "seed",
        lambda: build_seed_run(
            views_dir / "user_nl_root_only",
            seed_term="report",
            window=2,
            strategy="session_neighborhood",
            expansion_limit=10,
            min_term_frequency=1,
        ),
    )
    runtimes["seed"] = perf["runtime_seconds"]
    seed_artifacts = write_seed_run(seed_dir, seed_run)

    detectors_dir = root / "detectors"
    detector_paths: list[Path] = []
    detector_summary: dict[str, Any] = {}
    for detector_name in sorted(DETECTOR_REGISTRY):
        detector = get_detector(detector_name)
        detector_output_dir = detectors_dir / detector_name
        detector_output_dir.mkdir(parents=True, exist_ok=True)
        run, perf = measure_callable("detector", lambda detector=detector: detector.build_run(views_dir / "user_nl_root_only"))
        runtimes[f"detector:{detector_name}"] = perf["runtime_seconds"]
        run_path = detector_output_dir / "detector_run.json"
        run_path.write_text(json.dumps(run.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        detector_paths.append(run_path)
        detector_summary[detector_name] = {
            "detector_run": str(run_path),
            "finding_count": len(run.findings),
        }

    reports_dir = root / "reports"
    reports_artifacts, perf = measure_callable(
        "reports",
        lambda: generate_report(detector_paths, output_dir=reports_dir, title="Validation detector findings report"),
    )
    runtimes["reports"] = perf["runtime_seconds"]

    notebooks_dir = root / "notebooks"
    notebook_manifest, perf = measure_callable(
        "notebooks",
        lambda: export_notebook_artifacts(
            notebooks_dir,
            inventory_paths=[discovery_dir / "session_inventory.jsonl"],
            parse_diagnostics_paths=[parse_dir / "parse_diagnostics.json"],
            evidence_paths=[normalize_dir / "evidence.jsonl"],
            view_dirs=[views_dir / name for name in STANDARD_VIEW_DEFINITIONS],
            seed_run_paths=[seed_dir / "seed_run.json"],
            detector_run_paths=detector_paths,
            report_metadata_paths=[reports_dir / "report_metadata.json"],
        ),
    )
    runtimes["notebooks"] = perf["runtime_seconds"]

    traceability_dir = root
    traceability_samples, perf = measure_callable(
        "traceability",
        lambda: build_traceability_samples(
            report_metadata_path=reports_dir / "report_metadata.json",
            detector_run_paths=detector_paths,
            evidence_path=normalize_dir / "evidence.jsonl",
            raw_events_path=parse_dir / "raw_events.jsonl",
            limit=10,
        ),
    )
    runtimes["traceability"] = perf["runtime_seconds"]
    write_traceability_samples(traceability_dir / "traceability_samples.json", traceability_samples)

    memory_metrics = measure_streaming_memory(parse_dir / "raw_events.jsonl")
    performance_summary = build_performance_summary(
        validate_runtime_seconds=time.perf_counter() - started,
        streaming_memory_peak_mb=memory_metrics["streaming_memory_peak_mb"],
        command_runtimes=runtimes,
        streamed_line_count=memory_metrics["streamed_line_count"],
    )
    write_performance_summary(root / "performance_summary.json", performance_summary)

    validation_summary = {
        "discovery": {
            **discovery_artifacts,
            "inventory_summary": str(discovery_dir / "inventory_summary.json"),
            "lineage_coverage": discovery_payload["lineage_coverage"],
        },
        "parse": {
            **parse_artifacts,
            "parse_failures": _extract_parse_failures(parse_dir / "parse_diagnostics.json"),
        },
        "normalize": {
            **normalize_artifacts,
            "classification_ambiguities": _extract_ambiguities(normalize_dir / "normalization_diagnostics.json"),
        },
        "views": {
            "views": view_outputs,
            "recurrence_edge_cases": _build_recurrence_edge_cases(normalize_dir / "evidence.jsonl", views_dir / "user_nl_root_only" / "corpus_view.jsonl"),
        },
        "search": search_artifacts,
        "seed": seed_artifacts,
        "detectors": detector_summary,
        "reports": reports_artifacts.to_dict(),
        "notebooks": notebook_manifest,
        "traceability": {
            "sample_count": len(traceability_samples),
            "traceability_samples": str(root / "traceability_samples.json"),
        },
    }
    write_validation_summary(root / "validation_summary.json", validation_summary)
    return validation_summary


def write_validation_summary(output_path: str | Path, payload: dict[str, Any]) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _extract_parse_failures(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    aggregate = payload.get("aggregate", {})
    return {
        "invalid_lines": aggregate.get("invalid_lines", 0),
        "blank_lines": aggregate.get("blank_lines", 0),
        "non_object_lines": aggregate.get("non_object_lines", 0),
        "unknown_record_shapes": aggregate.get("unknown_record_shapes", 0),
    }


def _extract_ambiguities(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    ambiguous = payload.get("ambiguous_items", [])
    return {
        "count": len(ambiguous),
        "sample": ambiguous[:5],
    }


def _build_recurrence_edge_cases(evidence_path: Path, view_path: Path) -> dict[str, Any]:
    evidence = _load_jsonl(evidence_path)
    view_rows = _load_jsonl(view_path)
    duplicate_raw_event_ids = len(evidence) - len({row["raw_event_id"] for row in evidence})
    duplicate_session_ids = len(view_rows) - len({row["evidence"]["session_id"] for row in view_rows})
    return {
        "multi_evidence_same_raw_event": duplicate_raw_event_ids,
        "repeated_rows_same_session": duplicate_session_ids,
        "included_view_rows": len(view_rows),
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _load_jsonl_models(path: Path, *, model: str) -> list[Any]:
    from skill_drilla.parse.raw_events import RawEvent

    rows = _load_jsonl(path)
    if model == "raw_event":
        return [RawEvent(**row) for row in rows]
    raise ValueError(f"unsupported model type: {model}")
