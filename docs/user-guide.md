# Skill Drilla user guide

## What this tool does

Skill Drilla is a local-first CLI for turning exported chat transcript corpora into structured analysis artifacts.

At a high level, the workflow is:

1. discover available chat sessions
2. parse transcript JSONL into canonical raw events
3. normalize raw events into evidence records
4. build one or more corpus views
5. search, expand seed terms, run detectors, and generate reports
6. optionally export notebook bundles or run semantic analysis
7. run the end-to-end validation workflow

The CLI entrypoint is `skill-drilla` and is defined in `src/skill_drilla/cli.py:40`.

## Requirements

- Python 3.11+
- a local checkout of this repository
- transcript exports available under a projects root directory

The package metadata and console script are defined in `pyproject.toml:5` and `pyproject.toml:16`.

## Install and run

From the repository root:

```bash
python -m pip install -e .
```

Then you can use either form:

```bash
skill-drilla --help
```

or:

```bash
PYTHONPATH=src python -m skill-drilla.cli --help
```

## Configuration

The default config lives at `configs/chat-analysis.default.yaml`.

Important fields:

- `paths.source_root` — where the raw project/session exports live
- `paths.artifact_root` — where generated artifacts are written
- `scope.include_projects` / `scope.exclude_projects` — project scoping
- `scope.include_subagents` — whether subagent sessions are included during scoped discovery
- `views.default_view` — default view name in config metadata
- `analysis.seed_expansion_enabled` / `analysis.semantic_run_enabled` — feature flags recorded in config

Show the effective normalized config:

```bash
skill-drilla config show --config configs/chat-analysis.default.yaml
```

## Expected input layout

The CLI is designed to work from a projects root, usually the directory configured by `paths.source_root`.

A typical run points at:

```text
projects/
```

Discovery walks that tree and writes inventory artifacts describing the discovered sessions. The canonical discovery outputs are written by `src/skill_drilla/discovery/writer.py:13`.

## Output layout

By default, artifacts are written under `artifacts/chat-analysis/`.

Common subdirectories used by the workflow include:

- `artifacts/chat-analysis/discovery/`
- `artifacts/chat-analysis/parse/`
- `artifacts/chat-analysis/normalize/`
- `artifacts/chat-analysis/views/`
- `artifacts/chat-analysis/search/`
- `artifacts/chat-analysis/seed/`
- `artifacts/chat-analysis/detectors/`
- `artifacts/chat-analysis/reports/`
- `artifacts/chat-analysis/notebooks/`
- `artifacts/chat-analysis/validation/`

The base artifact layout is defined in `src/skill_drilla/contracts/artifacts.py:9`.

## Quickstart: end-to-end workflow

This is the simplest manual pipeline using the current stable commands.

### 1) Discover sessions

```bash
skill-drilla discover \
  --config configs/chat-analysis.default.yaml \
  --projects-root projects \
  --output-dir artifacts/chat-analysis/discovery/default
```

Main outputs:

- `session_inventory.jsonl`
- `scoped_session_inventory.jsonl`
- `inventory_summary.json`
- `run_manifest.json`
- `effective_config.json`

### 2) Parse discovered sessions into raw events

```bash
skill-drilla parse \
  --inventory artifacts/chat-analysis/discovery/default/scoped_session_inventory.jsonl \
  --output-dir artifacts/chat-analysis/parse/default
```

Main outputs:

- `raw_events.jsonl`
- `parse_diagnostics.json`

### 3) Normalize raw events into evidence

```bash
skill-drilla normalize \
  --inventory artifacts/chat-analysis/discovery/default/scoped_session_inventory.jsonl \
  --raw-events artifacts/chat-analysis/parse/default/raw_events.jsonl \
  --output-dir artifacts/chat-analysis/normalize/default
```

Main outputs:

- `evidence.jsonl`
- `normalization_diagnostics.json`

This step creates canonical evidence records used by downstream analysis.

### 4) Build a corpus view

Choose a built-in view name, for example:

- `user_nl_root_only`
- `assistant_nl_root_only`
- `combined_nl_root_plus_subagent`
- `debug_included_and_excluded`
- `root_only_all_roles`
- `root_plus_subagent_all_roles`

These are defined in `src/skill_drilla/views/definitions.py:41`.

Example:

```bash
skill-drilla build-view \
  --evidence artifacts/chat-analysis/normalize/default/evidence.jsonl \
  --view root_plus_subagent_all_roles \
  --output-dir artifacts/chat-analysis/views/root_plus_subagent_all_roles
```

Main outputs:

- `corpus_view.jsonl`
- `view_summary.json`

### 5) Search a view

```bash
skill-drilla search \
  --view-dir artifacts/chat-analysis/views/root_plus_subagent_all_roles \
  --query "repeated instructions" \
  --output-dir artifacts/chat-analysis/search/repeated-instructions
```

Useful filters:

- `--project <slug>`
- `--session <session-id>`
- `--semantic-class <class>`
- `--include-subagents`
- `--root-only`

### 6) Inspect a specific evidence record

```bash
skill-drilla inspect-evidence \
  --view-dir artifacts/chat-analysis/views/root_plus_subagent_all_roles \
  --evidence-id <evidence-id>
```

This prints a JSON inspection payload for one record plus nearby context.

### 7) Expand from a seed term

```bash
skill-drilla seed-expand \
  --view-dir artifacts/chat-analysis/views/root_plus_subagent_all_roles \
  --term "retry" \
  --strategy session_neighborhood \
  --output-dir artifacts/chat-analysis/seed/retry
```

Supported strategies are declared in `src/skill_drilla/cli.py:96`:

- `cooccurrence`
- `adjacency`
- `session_neighborhood`

### 8) Run a detector

Available detector names are defined in `src/skill_drilla/detect/__init__.py:12`:

- `repeated_instructions`
- `workflow_patterns`
- `corrections_frustrations`
- `refinement_requests`
- `agent_failures`
- `output_quality`
- `change_requests`

Example:

```bash
skill-drilla detect \
  --view-dir artifacts/chat-analysis/views/root_plus_subagent_all_roles \
  --detector repeated_instructions \
  --output-dir artifacts/chat-analysis/detectors/repeated_instructions
```

Main output:

- `detector_run.json`

### 9) Generate a report

```bash
skill-drilla report \
  --detector-run artifacts/chat-analysis/detectors/repeated_instructions/detector_run.json \
  --title "Repeated instructions report" \
  --output-dir artifacts/chat-analysis/reports/repeated_instructions
```

Main outputs:

- `report.md`
- `report_metadata.json`

### 10) Export notebook-friendly artifacts

```bash
skill-drilla notebook-export \
  --evidence artifacts/chat-analysis/normalize/default/evidence.jsonl \
  --view-dir artifacts/chat-analysis/views/root_plus_subagent_all_roles \
  --detector-run artifacts/chat-analysis/detectors/repeated_instructions/detector_run.json \
  --report-metadata artifacts/chat-analysis/reports/repeated_instructions/report_metadata.json \
  --output-dir artifacts/chat-analysis/notebooks/export-default
```

This copies canonical artifacts into an analysis bundle and writes `export_manifest.json`.

For notebook-specific guidance, see `docs/notebooks/usage.md`.

### 11) Optionally run semantic analysis

Semantic analysis is disabled by default and requires an explicit opt-in flag.

Available methods are defined in `src/skill_drilla/semantic/__init__.py:8`:

- `embeddings`
- `clustering`
- `interpretation`

The `embeddings` method now supports two modes:

- default fixture mode for deterministic local verification
- optional Stella local mode for real embeddings using `NovaSearch/stella_en_1.5B_v5`

Fixture example:

```bash
skill-drilla semantic-run \
  --view-dir artifacts/chat-analysis/views/root_plus_subagent_all_roles \
  --method embeddings \
  --backend fixture \
  --disabled-by-default-check \
  --output-dir artifacts/chat-analysis/semantic/embeddings-fixture
```

Stella local example:

```bash
HSA_OVERRIDE_GFX_VERSION=10.3.0 \
skill-drilla semantic-run \
  --view-dir artifacts/chat-analysis/views/root_plus_subagent_all_roles \
  --method embeddings \
  --backend stella-local \
  --model-name NovaSearch/stella_en_1.5B_v5 \
  --device cuda \
  --torch-dtype float16 \
  --batch-size 8 \
  --trust-remote-code \
  --disabled-by-default-check \
  --output-dir artifacts/chat-analysis/semantic/embeddings-stella
```

Fixture clustering remains available as the deterministic semantic grouping mode:

```bash
skill-drilla semantic-run \
  --view-dir artifacts/chat-analysis/views/root_plus_subagent_all_roles \
  --method clustering \
  --backend fixture \
  --disabled-by-default-check \
  --output-dir artifacts/chat-analysis/semantic/clustering-default
```

Stella local clustering uses normalized Stella embeddings plus agglomerative clustering:

```bash
HSA_OVERRIDE_GFX_VERSION=10.3.0 \
skill-drilla semantic-run \
  --view-dir artifacts/chat-analysis/views/root_plus_subagent_all_roles \
  --method clustering \
  --backend stella-local \
  --model-name NovaSearch/stella_en_1.5B_v5 \
  --device cuda \
  --torch-dtype float16 \
  --batch-size 8 \
  --distance-threshold 0.3 \
  --min-cluster-size 1 \
  --trust-remote-code \
  --disabled-by-default-check \
  --output-dir artifacts/chat-analysis/semantic/clustering-stella
```

If you omit `--disabled-by-default-check`, the command intentionally fails.

For the Stella path, install ROCm-compatible `torch` separately, then add the optional semantic-local dependencies documented in `embedding-test/SETUP.md`.

See also `docs/semantic/optional-mode.md`.

### 12) Run the full validation workflow

If you want a single end-to-end smoke test of the whole system:

```bash
skill-drilla validate \
  --config configs/chat-analysis.default.yaml \
  --projects-root projects \
  --output-dir artifacts/chat-analysis/validation/full-smoke
```

This is the best first command when you want to verify the entire repository is wired correctly.

For more detail, see `docs/operators/validation-and-troubleshooting.md`.

## Command reference

### `config show`

Print the normalized effective config as JSON.

```bash
skill-drilla config show --config configs/chat-analysis.default.yaml
```

### `manifest-smoke`

Write a minimal run manifest and effective config to an output directory.

```bash
skill-drilla manifest-smoke \
  --config configs/chat-analysis.default.yaml \
  --output-dir artifacts/chat-analysis/contracts/manifest-smoke
```

### `discover`

Requires:

- `--config`

Optional overrides:

- `--projects-root`
- `--output-dir`

### `parse`

Requires:

- `--inventory`
- `--output-dir`

### `normalize`

Requires:

- `--inventory`
- `--raw-events`
- `--output-dir`

### `build-view`

Requires:

- `--evidence`
- `--view`
- `--output-dir`

### `search`

Requires:

- `--view-dir`
- `--query`
- `--output-dir`

Optional filters:

- `--project`
- `--session`
- `--semantic-class`
- `--include-subagents`
- `--root-only`

### `inspect-evidence`

Requires:

- `--view-dir`
- `--evidence-id`

Optional:

- `--context` (default: `2`)

### `seed-expand`

Requires:

- `--view-dir`
- `--term`
- `--output-dir`

Optional:

- `--strategy`
- `--window`
- `--expansion-limit`
- `--min-term-frequency`

### `detect`

Requires:

- `--view-dir`
- `--detector`
- `--output-dir`

### `report`

Requires:

- one or more `--detector-run`
- `--output-dir`

Optional:

- `--view`
- `--detector-name`
- `--title`

### `notebook-export`

Requires:

- `--output-dir`

Optional repeated inputs:

- `--inventory`
- `--parse-diagnostics`
- `--evidence`
- `--view-dir`
- `--seed-run`
- `--detector-run`
- `--report-metadata`

### `semantic-run`

Requires:

- `--view-dir`
- `--method`
- `--output-dir`
- `--disabled-by-default-check`

### `validate`

Requires:

- `--config`
- `--projects-root`
- `--output-dir`

## Common workflows

### Minimal first run

If you are just trying the tool for the first time, run:

```bash
skill-drilla validate \
  --config configs/chat-analysis.default.yaml \
  --projects-root projects \
  --output-dir artifacts/chat-analysis/validation/first-run
```

Then inspect:

- `validation_summary.json`
- `reports/`
- `notebooks/`

### Incremental analysis

If you want more control, use this sequence:

1. `discover`
2. `parse`
3. `normalize`
4. `build-view`
5. `search` or `detect`
6. `report`

### Root-only vs subagent-inclusive analysis

Use different built-in views depending on whether you want only root sessions or root plus subagent sessions:

- root-only: `user_nl_root_only`, `assistant_nl_root_only`, `root_only_all_roles`
- root + subagent: `combined_nl_root_plus_subagent`, `root_plus_subagent_all_roles`
- debugging: `debug_included_and_excluded`

## Troubleshooting

### `discover requires --config`

`discover` loads scoping and path defaults from config, so `--config` is mandatory.

### `parse requires --inventory and --output-dir`

Point `--inventory` at the discovery inventory file, typically `scoped_session_inventory.jsonl`.

### `normalize requires --inventory, --raw-events, and --output-dir`

Make sure the raw events file came from the matching parse run.

### `unknown view definition`

Use one of the built-in view names from `src/skill_drilla/views/definitions.py:41`.

### `unknown detector`

Use one of the detector names from `src/skill_drilla/detect/__init__.py:12`.

### `semantic-run is disabled by default`

Re-run with `--disabled-by-default-check` if you intentionally want semantic analysis.

### Validation troubleshooting

See `docs/operators/validation-and-troubleshooting.md` for stage-specific troubleshooting guidance.

## Where to go next

- CLI surface: `src/skill_drilla/cli.py:40`
- view definitions: `src/skill_drilla/views/definitions.py:41`
- detector registry: `src/skill_drilla/detect/__init__.py:12`
- notebook workflow: `docs/notebooks/usage.md`
- semantic mode: `docs/semantic/optional-mode.md`
- validation workflow: `docs/operators/validation-and-troubleshooting.md`
