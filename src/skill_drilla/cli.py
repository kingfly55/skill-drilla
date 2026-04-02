"""Stable CLI contract for milestone 1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from skill_drilla.config import dump_effective_config, load_config
from skill_drilla.contracts.run_manifest import finalize_run, start_run, write_manifest
from skill_drilla.detect import DETECTOR_REGISTRY, get_detector
from skill_drilla.discovery import apply_scope, discover_corpus, write_discovery_artifacts
from skill_drilla.discovery.inventory import DiscoverySummary, InventoryRecord
from skill_drilla.normalize import write_normalize_artifacts
from skill_drilla.parse import RawEvent, iter_raw_events, write_parse_artifacts
from skill_drilla.search import SearchFilters, inspect_evidence_record, parse_csv_filters, parse_query, run_search, write_search_result
from skill_drilla.notebooks import export_notebook_artifacts
from skill_drilla.report import generate_report
from skill_drilla.seed import build_seed_run, write_seed_run
from skill_drilla.semantic import SemanticEvidenceSlice, get_semantic_method, write_semantic_run
from skill_drilla.episodes import build_episodes, write_episode_artifacts
from skill_drilla.episodes.loader import iter_evidence_rows
from skill_drilla.validate import run_validation
from skill_drilla.views import build_view

STABLE_PIPELINE_COMMANDS = [
    "discover",
    "parse",
    "normalize",
    "build-view",
    "search",
    "seed-expand",
    "detect",
    "report",
    "notebook-export",
    "semantic-run",
    "validate",
    "extract-episodes",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="skill-drilla")
    subparsers = parser.add_subparsers(dest="command", required=True)

    config_parser = subparsers.add_parser("config")
    config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    config_show = config_subparsers.add_parser("show")
    config_show.add_argument("--config", required=True)
    config_show.set_defaults(handler=handle_config_show)

    manifest_smoke = subparsers.add_parser("manifest-smoke")
    manifest_smoke.add_argument("--config", required=True)
    manifest_smoke.add_argument("--output-dir", required=True)
    manifest_smoke.set_defaults(handler=handle_manifest_smoke)

    inspect_evidence_cmd = subparsers.add_parser("inspect-evidence")
    inspect_evidence_cmd.add_argument("--view-dir", required=True)
    inspect_evidence_cmd.add_argument("--evidence-id", required=True)
    inspect_evidence_cmd.add_argument("--context", type=int, default=2)
    inspect_evidence_cmd.set_defaults(handler=handle_inspect_evidence_command)

    for command_name in STABLE_PIPELINE_COMMANDS:
        cmd = subparsers.add_parser(command_name)
        cmd.add_argument("--config", required=False)
        if command_name == "discover":
            cmd.add_argument("--projects-root", required=False)
            cmd.add_argument("--output-dir", required=False)
            cmd.set_defaults(handler=handle_discover_command, stable_command=command_name)
        elif command_name == "parse":
            cmd.add_argument("--inventory", required=False)
            cmd.add_argument("--output-dir", required=False)
            cmd.set_defaults(handler=handle_parse_command, stable_command=command_name)
        elif command_name == "normalize":
            cmd.add_argument("--inventory", required=False)
            cmd.add_argument("--raw-events", required=False)
            cmd.add_argument("--output-dir", required=False)
            cmd.set_defaults(handler=handle_normalize_command, stable_command=command_name)
        elif command_name == "build-view":
            cmd.add_argument("--evidence", required=False)
            cmd.add_argument("--view", required=False)
            cmd.add_argument("--output-dir", required=False)
            cmd.set_defaults(handler=handle_build_view_command, stable_command=command_name)
        elif command_name == "search":
            cmd.add_argument("--view-dir", required=False)
            cmd.add_argument("--query", required=False)
            cmd.add_argument("--output-dir", required=False)
            cmd.add_argument("--project", action="append", dest="projects")
            cmd.add_argument("--session", action="append", dest="sessions")
            cmd.add_argument("--semantic-class", action="append", dest="semantic_classes")
            cmd.add_argument("--include-subagents", action="store_true")
            cmd.add_argument("--root-only", action="store_true")
            cmd.set_defaults(handler=handle_search_command, stable_command=command_name)
        elif command_name == "seed-expand":
            cmd.add_argument("--view-dir", required=False)
            cmd.add_argument("--term", required=False)
            cmd.add_argument("--output-dir", required=False)
            cmd.add_argument("--strategy", choices=["cooccurrence", "adjacency", "session_neighborhood"], default="cooccurrence")
            cmd.add_argument("--window", type=int, default=3)
            cmd.add_argument("--expansion-limit", type=int, default=25)
            cmd.add_argument("--min-term-frequency", type=int, default=1)
            cmd.set_defaults(handler=handle_seed_expand_command, stable_command=command_name)
        elif command_name == "detect":
            cmd.add_argument("--view-dir", required=False)
            cmd.add_argument("--detector", choices=sorted(DETECTOR_REGISTRY), required=False)
            cmd.add_argument("--output-dir", required=False)
            cmd.set_defaults(handler=handle_detect_command, stable_command=command_name)
        elif command_name == "report":
            cmd.add_argument("--detector-run", action="append", dest="detector_runs")
            cmd.add_argument("--view", action="append", dest="views")
            cmd.add_argument("--detector-name", action="append", dest="detectors")
            cmd.add_argument("--title", required=False)
            cmd.add_argument("--output-dir", required=False)
            cmd.set_defaults(handler=handle_report_command, stable_command=command_name)
        elif command_name == "notebook-export":
            cmd.add_argument("--inventory", action="append", dest="inventory_paths")
            cmd.add_argument("--parse-diagnostics", action="append", dest="parse_diagnostics_paths")
            cmd.add_argument("--evidence", action="append", dest="evidence_paths")
            cmd.add_argument("--view-dir", action="append", dest="view_dirs")
            cmd.add_argument("--seed-run", action="append", dest="seed_run_paths")
            cmd.add_argument("--detector-run", action="append", dest="detector_run_paths")
            cmd.add_argument("--report-metadata", action="append", dest="report_metadata_paths")
            cmd.add_argument("--output-dir", required=False)
            cmd.set_defaults(handler=handle_notebook_export_command, stable_command=command_name)
        elif command_name == "semantic-run":
            cmd.add_argument("--view-dir", required=False)
            cmd.add_argument("--method", choices=["embeddings", "clustering", "interpretation", "skill-mining"], required=False)
            cmd.add_argument("--backend", choices=["fixture", "stella-local", "pydantic-ai"], required=False)
            cmd.add_argument("--model-name", required=False)
            cmd.add_argument("--device", choices=["auto", "cpu", "cuda"], required=False)
            cmd.add_argument("--batch-size", type=int, required=False)
            cmd.add_argument("--torch-dtype", choices=["float16", "float32"], required=False)
            cmd.add_argument("--trust-remote-code", action="store_true")
            cmd.add_argument("--hf-cache-dir", required=False)
            cmd.add_argument("--distance-threshold", type=float, required=False)
            cmd.add_argument("--min-cluster-size", type=int, required=False)
            cmd.add_argument("--disabled-by-default-check", action="store_true")
            cmd.add_argument("--output-dir", required=False)
            # skill-mining specific
            cmd.add_argument("--episode-dir", required=False)
            cmd.add_argument("--base-url", required=False)
            cmd.add_argument("--api-key", required=False)
            cmd.add_argument("--max-skills", type=int, required=False)
            cmd.set_defaults(handler=handle_semantic_run_command, stable_command=command_name)
        elif command_name == "validate":
            cmd.add_argument("--projects-root", required=False)
            cmd.add_argument("--output-dir", required=False)
            cmd.set_defaults(handler=handle_validate_command, stable_command=command_name)
        elif command_name == "extract-episodes":
            cmd.add_argument("--evidence", required=False)
            cmd.add_argument("--run-label", required=False)
            cmd.add_argument("--output-dir", required=False)
            cmd.set_defaults(handler=handle_extract_episodes_command, stable_command=command_name)
        else:
            cmd.set_defaults(handler=handle_stub_command, stable_command=command_name)

    return parser


def handle_config_show(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    print(dump_effective_config(config))
    return 0


def handle_manifest_smoke(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    context = start_run(
        command="manifest-smoke",
        config_fingerprint=config.fingerprint,
        input_scope=config.input_scope,
        artifact_paths={
            "output_dir": str(output_dir),
            "run_manifest": str(output_dir / "run_manifest.json"),
            "effective_config": str(output_dir / "effective_config.json"),
        },
    )
    effective_config_path = output_dir / "effective_config.json"
    effective_config_path.write_text(dump_effective_config(config) + "\n", encoding="utf-8")
    manifest = finalize_run(context)
    write_manifest(output_dir / "run_manifest.json", manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True))
    return 0


def handle_discover_command(args: argparse.Namespace) -> int:
    config = load_config(args.config) if args.config else None
    if config is None:
        raise ValueError("discover requires --config")

    projects_root = Path(args.projects_root or config.data["paths"]["source_root"])
    output_dir = Path(args.output_dir or config.data["paths"]["discovery_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    discovery = discover_corpus(projects_root)
    scoped = apply_scope(discovery.records, config.input_scope)
    summary = DiscoverySummary.from_records(discovery.records, scoped.excluded_records)
    artifact_paths = write_discovery_artifacts(
        output_dir,
        records=discovery.records,
        scoped=scoped,
        summary=summary,
        project_count=len(discovery.projects),
    )

    effective_config_path = output_dir / "effective_config.json"
    effective_config_path.write_text(dump_effective_config(config) + "\n", encoding="utf-8")
    artifact_paths.update(
        {
            "run_manifest": str(output_dir / "run_manifest.json"),
            "effective_config": str(effective_config_path),
        }
    )
    context = start_run(
        command="discover",
        config_fingerprint=config.fingerprint,
        input_scope=config.input_scope,
        artifact_paths=artifact_paths,
    )
    manifest = finalize_run(
        context,
        extra={
            "counts": {
                "projects": len(discovery.projects),
                "sessions": len(discovery.records),
                "scoped_sessions": len(scoped.records),
                "excluded_sessions": len(scoped.excluded_records),
            }
        },
    )
    write_manifest(output_dir / "run_manifest.json", manifest)
    print(json.dumps(
        {
            "command": "discover",
            "projects": len(discovery.projects),
            "sessions": len(discovery.records),
            "scoped_sessions": len(scoped.records),
            "output_dir": str(output_dir),
        },
        indent=2,
        sort_keys=True,
    ))
    return 0


def handle_parse_command(args: argparse.Namespace) -> int:
    inventory_path = Path(args.inventory) if args.inventory else None
    output_dir = Path(args.output_dir) if args.output_dir else None

    if inventory_path is None or output_dir is None:
        raise ValueError("parse requires --inventory and --output-dir")

    inventory_records = tuple(load_inventory_records(inventory_path))
    artifact_paths = write_parse_artifacts(output_dir, inventory_records, iter_raw_events)
    print(json.dumps({
        "command": "parse",
        "inventory": str(inventory_path),
        "sessions": len(inventory_records),
        "output_dir": str(output_dir),
        "artifacts": artifact_paths,
    }, indent=2, sort_keys=True))
    return 0


def handle_normalize_command(args: argparse.Namespace) -> int:
    inventory_path = Path(args.inventory) if args.inventory else None
    raw_events_path = Path(args.raw_events) if args.raw_events else None
    output_dir = Path(args.output_dir) if args.output_dir else None

    if inventory_path is None or raw_events_path is None or output_dir is None:
        raise ValueError("normalize requires --inventory, --raw-events, and --output-dir")

    inventory_records = tuple(load_inventory_records(inventory_path))
    raw_events = tuple(load_raw_events(raw_events_path))
    artifact_paths = write_normalize_artifacts(output_dir, inventory_records, raw_events)
    print(json.dumps({
        "command": "normalize",
        "inventory": str(inventory_path),
        "raw_events": str(raw_events_path),
        "sessions": len(inventory_records),
        "events": len(raw_events),
        "output_dir": str(output_dir),
        "artifacts": artifact_paths,
    }, indent=2, sort_keys=True))
    return 0


def handle_build_view_command(args: argparse.Namespace) -> int:
    evidence_path = Path(args.evidence) if args.evidence else None
    output_dir = Path(args.output_dir) if args.output_dir else None
    view_name = args.view

    if evidence_path is None or output_dir is None or not view_name:
        raise ValueError("build-view requires --evidence, --view, and --output-dir")

    artifact_paths = build_view(view_name, evidence_path, output_dir)
    print(json.dumps({
        "command": "build-view",
        "evidence": str(evidence_path),
        "view": view_name,
        "output_dir": str(output_dir),
        "artifacts": artifact_paths,
    }, indent=2, sort_keys=True))
    return 0


def handle_search_command(args: argparse.Namespace) -> int:
    view_dir = Path(args.view_dir) if args.view_dir else None
    output_dir = Path(args.output_dir) if args.output_dir else None
    query = args.query

    if view_dir is None or output_dir is None or not query:
        raise ValueError("search requires --view-dir, --query, and --output-dir")

    filters = SearchFilters(
        project_slugs=parse_csv_filters(args.projects),
        session_ids=parse_csv_filters(args.sessions),
        semantic_classes=parse_csv_filters(args.semantic_classes),
        include_subagents=False if args.root_only else (True if args.include_subagents else None),
    )
    result = run_search(view_dir, parse_query(query), filters)
    artifact_paths = write_search_result(output_dir, result)
    print(json.dumps({
        "command": "search",
        "view_dir": str(view_dir),
        "output_dir": str(output_dir),
        "artifacts": artifact_paths,
        "match_count": len(result.matches),
        "view_name": result.view_name,
    }, indent=2, sort_keys=True))
    return 0


def handle_inspect_evidence_command(args: argparse.Namespace) -> int:
    view_dir = Path(args.view_dir) if args.view_dir else None
    evidence_id = args.evidence_id
    context = args.context
    if view_dir is None or not evidence_id:
        raise ValueError("inspect-evidence requires --view-dir and --evidence-id")
    payload = inspect_evidence_record(view_dir, evidence_id, context=context)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def handle_seed_expand_command(args: argparse.Namespace) -> int:
    view_dir = Path(args.view_dir) if args.view_dir else None
    output_dir = Path(args.output_dir) if args.output_dir else None
    term = args.term
    if view_dir is None or output_dir is None or not term:
        raise ValueError("seed-expand requires --view-dir, --term, and --output-dir")
    run = build_seed_run(
        view_dir,
        seed_term=term,
        window=args.window,
        strategy=args.strategy,
        expansion_limit=args.expansion_limit,
        min_term_frequency=args.min_term_frequency,
    )
    artifact_paths = write_seed_run(output_dir, run)
    print(json.dumps({
        "command": "seed-expand",
        "view_dir": str(view_dir),
        "output_dir": str(output_dir),
        "artifacts": artifact_paths,
        "view_name": run.view_name,
        "seed_term": run.seed_term,
        "direct_hit_count": len(run.direct_hits),
        "expansion_hit_count": len(run.expansion_hits),
        "strategy": run.parameters["strategy"],
    }, indent=2, sort_keys=True))
    return 0


def handle_detect_command(args: argparse.Namespace) -> int:
    view_dir = Path(args.view_dir) if args.view_dir else None
    output_dir = Path(args.output_dir) if args.output_dir else None
    detector_name = args.detector
    if view_dir is None or output_dir is None or not detector_name:
        raise ValueError("detect requires --view-dir, --detector, and --output-dir")
    detector = get_detector(detector_name)
    run = detector.build_run(view_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    detector_run_path = output_dir / "detector_run.json"
    detector_run_path.write_text(json.dumps(run.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "command": "detect",
        "view_dir": str(view_dir),
        "output_dir": str(output_dir),
        "detector": run.detector,
        "view_name": run.view_name,
        "finding_count": len(run.findings),
        "artifacts": {"detector_run": str(detector_run_path)},
    }, indent=2, sort_keys=True))
    return 0


def handle_report_command(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir) if args.output_dir else None
    detector_run_args = list(args.detector_runs or [])
    if output_dir is None or not detector_run_args:
        raise ValueError("report requires --detector-run and --output-dir")

    artifacts = generate_report(
        [Path(path) for path in detector_run_args],
        output_dir=output_dir,
        view_names=args.views,
        detectors=args.detectors,
        title=args.title,
    )
    print(json.dumps({
        "command": "report",
        "output_dir": str(output_dir),
        "report_title": artifacts.report_title,
        "section_count": artifacts.section_count,
        "artifacts": {
            "report": str(artifacts.report_path),
            "report_metadata": str(artifacts.metadata_path),
        },
    }, indent=2, sort_keys=True))
    return 0


def handle_notebook_export_command(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir) if args.output_dir else None
    if output_dir is None:
        raise ValueError("notebook-export requires --output-dir")

    manifest = export_notebook_artifacts(
        output_dir,
        inventory_paths=args.inventory_paths or (),
        parse_diagnostics_paths=args.parse_diagnostics_paths or (),
        evidence_paths=args.evidence_paths or (),
        view_dirs=args.view_dirs or (),
        seed_run_paths=args.seed_run_paths or (),
        detector_run_paths=args.detector_run_paths or (),
        report_metadata_paths=args.report_metadata_paths or (),
    )
    print(json.dumps({
        "command": "notebook-export",
        "output_dir": str(output_dir),
        "artifacts": {
            "export_manifest": str(output_dir / "export_manifest.json"),
        },
        "manifest": manifest,
    }, indent=2, sort_keys=True))
    return 0


def handle_semantic_run_command(args: argparse.Namespace) -> int:
    output_dir = Path(args.output_dir) if args.output_dir else None
    method_name = args.method
    if output_dir is None or not method_name:
        raise ValueError("semantic-run requires --method and --output-dir")
    if not args.disabled_by_default_check:
        raise ValueError("semantic-run is disabled by default; rerun with --disabled-by-default-check to enable optional semantic analysis")

    if method_name == "skill-mining":
        episode_dir = Path(args.episode_dir) if args.episode_dir else None
        if episode_dir is None:
            raise ValueError("semantic-run --method skill-mining requires --episode-dir")
        parameters: dict[str, object] = {"episode_dir": str(episode_dir)}
        if args.backend:
            parameters["backend"] = args.backend
        if args.base_url:
            parameters["base_url"] = args.base_url
        if args.api_key:
            parameters["api_key"] = args.api_key
        if args.model_name:
            parameters["model"] = args.model_name
        if args.max_skills is not None:
            parameters["max_skills"] = args.max_skills
        run = get_semantic_method(method_name).build_run(None, parameters=parameters)
        artifact_paths = write_semantic_run(output_dir, run)
        print(json.dumps({
            "command": "semantic-run",
            "episode_dir": str(episode_dir),
            "output_dir": str(output_dir),
            "method": run.method,
            "non_canonical": run.non_canonical,
            "parameters": run.parameters,
            "artifacts": artifact_paths,
        }, indent=2, sort_keys=True))
        return 0

    view_dir = Path(args.view_dir) if args.view_dir else None
    if view_dir is None:
        raise ValueError("semantic-run requires --view-dir for this method")

    embed_cluster_params: dict[str, object] | None = None
    if method_name in {"embeddings", "clustering"}:
        embed_cluster_params = {}
        if args.backend:
            embed_cluster_params["backend"] = args.backend
            if method_name == "embeddings":
                embed_cluster_params["implementation"] = "stella-local" if args.backend == "stella-local" else "fixture-hash-embedding"
                if args.backend == "fixture":
                    embed_cluster_params["model"] = "local-fixture"
            else:
                embed_cluster_params["implementation"] = "stella-local-agglomerative" if args.backend == "stella-local" else "keyword-overlap-v1"
                if args.backend == "fixture":
                    embed_cluster_params["model"] = "local-fixture"
        if args.model_name:
            embed_cluster_params["model"] = args.model_name
        if args.device:
            embed_cluster_params["device"] = args.device
        if args.batch_size is not None:
            embed_cluster_params["batch_size"] = args.batch_size
        if args.torch_dtype:
            embed_cluster_params["torch_dtype"] = args.torch_dtype
        if args.trust_remote_code:
            embed_cluster_params["trust_remote_code"] = True
        if args.hf_cache_dir:
            embed_cluster_params["hf_cache_dir"] = args.hf_cache_dir
        if args.distance_threshold is not None:
            embed_cluster_params["distance_threshold"] = args.distance_threshold
        if args.min_cluster_size is not None:
            embed_cluster_params["min_cluster_size"] = args.min_cluster_size
        if not embed_cluster_params:
            embed_cluster_params = None

    evidence_slice = SemanticEvidenceSlice.from_view_dir(view_dir)
    run = get_semantic_method(method_name).build_run(evidence_slice, parameters=embed_cluster_params)
    artifact_paths = write_semantic_run(output_dir, run)
    print(json.dumps({
        "command": "semantic-run",
        "view_dir": str(view_dir),
        "output_dir": str(output_dir),
        "method": run.method,
        "non_canonical": run.non_canonical,
        "parameters": run.parameters,
        "artifacts": artifact_paths,
    }, indent=2, sort_keys=True))
    return 0


def handle_validate_command(args: argparse.Namespace) -> int:
    config_path = args.config
    projects_root = args.projects_root
    output_dir = args.output_dir
    if not config_path or not projects_root or not output_dir:
        raise ValueError("validate requires --config, --projects-root, and --output-dir")
    summary = run_validation(config_path=config_path, projects_root=projects_root, output_dir=output_dir)
    print(json.dumps({
        "command": "validate",
        "projects_root": str(projects_root),
        "output_dir": str(output_dir),
        "summary_path": str(Path(output_dir) / "validation_summary.json"),
        "stages": sorted(summary),
    }, indent=2, sort_keys=True))
    return 0


def load_inventory_records(inventory_path: Path) -> list[InventoryRecord]:
    records: list[InventoryRecord] = []
    with inventory_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            records.append(InventoryRecord(**payload))
    return records


def load_raw_events(raw_events_path: Path) -> list[RawEvent]:
    events: list[RawEvent] = []
    with raw_events_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            payload = json.loads(line)
            events.append(RawEvent(**payload))
    return events


def handle_extract_episodes_command(args: argparse.Namespace) -> int:
    evidence_path = Path(args.evidence) if args.evidence else None
    output_dir = Path(args.output_dir) if args.output_dir else None
    run_label = args.run_label or "default"

    if evidence_path is None or output_dir is None:
        raise ValueError("extract-episodes requires --evidence and --output-dir")

    rows = list(iter_evidence_rows(evidence_path))
    episodes, index = build_episodes(rows)
    artifact_paths = write_episode_artifacts(output_dir, episodes, index, run_label)

    print(json.dumps({
        "command": "extract-episodes",
        "evidence": str(evidence_path),
        "run_label": run_label,
        "output_dir": str(output_dir),
        "episode_count": index.episode_count,
        "turn_count": index.turn_count,
        "artifacts": artifact_paths,
    }, indent=2, sort_keys=True))
    return 0


def handle_stub_command(args: argparse.Namespace) -> int:
    print(json.dumps({
        "command": args.stable_command,
        "status": "declared",
        "message": "Stable CLI contract reserved for later milestones.",
    }, indent=2, sort_keys=True))
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = args.handler
    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
