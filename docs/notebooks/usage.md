# Notebook usage

## Purpose

Notebook workflows in this repository are consumers of canonical artifacts. They do not parse raw transcript JSONL files, redefine evidence semantics, or recompute detector findings from transcript source data.

## Canonical inputs

Use notebook helpers from `skill-drilla.notebooks` to read repository-produced artifacts:

- discovery inventory via `load_inventory(...)`
- parse diagnostics via `load_parse_diagnostics(...)`
- normalized evidence via `load_evidence(...)`
- corpus views via `load_corpus_view(...)`
- seed outputs via `load_seed_run(...)`
- detector runs via `load_detector_run(...)`
- report metadata via `load_report_metadata(...)`

These loaders preserve canonical IDs, scope metadata, inclusion status, recurrence semantics, and source anchors already materialized by the CLI workflow.

## Boundaries

Notebook code must:

- read canonical artifact paths under `artifacts/chat-analysis/`
- preserve `evidence_id`, `session_id`, `project_id`, and `view_id` values exactly as stored
- use materialized recurrence metadata from views, detector runs, and reports when comparing outputs
- inspect included, excluded, and ambiguous evidence through canonical `inclusion_status`, `inclusion_rationale`, and `semantic_class` fields

Notebook code must not:

- reparse transcript exports as an alternate ingestion path
- reclassify evidence into a shadow semantic taxonomy
- silently mix root and subagent content without using canonical session metadata
- invent alternate recurrence definitions for notebook-visible summaries without labeling them as derived notebook analysis

## Derived notebook analysis

Notebooks may compute exploratory notebook-local summaries from canonical artifacts, including threshold tuning, sensitivity analysis, and insight shortlists.

When they do, they should:

- clearly label those outputs as notebook-derived analysis rather than canonical repository outputs
- keep joins anchored on canonical identifiers such as `evidence_id`, `session_id`, and `project_id`
- preserve canonical recurrence definitions when comparing detector, report, and view artifacts
- treat semantic outputs such as `semantic_run.json` only as optional non-canonical overlays joined back through canonical evidence IDs

`notebooks/05_iterative_insight_analysis.ipynb` is the reference example for this style of iterative, validation-bundle-driven analysis.

## Export workflow

Use `skill-drilla.cli notebook-export` to collect canonical artifacts into a notebook-friendly bundle. The export copies existing files and writes `export_manifest.json`; it does not generate new semantic outputs.

Example:

```bash
PYTHONPATH="src" \
python -m skill-drilla.cli notebook-export \
  --evidence "artifacts/chat-analysis/normalize/smoke/evidence.jsonl" \
  --detector-run "artifacts/chat-analysis/detectors/repeated_instructions/detector_run.json" \
  --output-dir "artifacts/chat-analysis/notebooks/export-smoke"
```

## Non-interactive verification

Notebook verification is programmatic:

- assert `.ipynb` files exist
- parse notebook JSON as structured documents
- confirm starter code imports `skill-drilla.notebooks.loaders`
- confirm starter code references canonical `artifacts/chat-analysis/` paths
- validate exported manifests and copied artifact files with tests and CLI checks

No notebook UI needs to be opened, and no cells need to be run manually.
