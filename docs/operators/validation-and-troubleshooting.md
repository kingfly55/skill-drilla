# Validation and troubleshooting

## Validation command

Run the full local validation workflow with:

```bash
PYTHONPATH="src" python -m skill-drilla.cli validate \
  --config "configs/chat-analysis.default.yaml" \
  --projects-root "projects" \
  --output-dir "artifacts/chat-analysis/validation/full-smoke"
```

The workflow is non-interactive and runs discovery, parse, normalize, views, search, seed expansion, all detectors, reporting, notebook export, performance measurement, and traceability sampling.

## Expected artifacts

The validation output directory contains:

- `validation_summary.json` — machine-readable stage summary
- `performance_summary.json` — runtime and streaming-memory metrics
- `traceability_samples.json` — report-to-source traceability samples
- `discovery/` — inventory and lineage coverage artifacts
- `parse/` — raw events and parse diagnostics
- `normalize/` — evidence and ambiguity diagnostics
- `views/` — materialized corpus views and recurrence edge-case counts
- `search/`, `seed/`, `detectors/`, `reports/`, `notebooks/` — downstream validation artifacts

## Troubleshooting

### Validation fails during parse

Inspect `parse/parse_diagnostics.json` and the `parse.parse_failures` section in `validation_summary.json` to see counts for invalid JSON, blank lines, non-object records, and unknown record shapes.

### Validation reports ambiguous records

Inspect `normalize/normalization_diagnostics.json` and `validation_summary.json -> normalize -> classification_ambiguities` for sample ambiguous evidence and source locations.

### Traceability samples are empty

Check that detector runs produced findings, then inspect `reports/report_metadata.json` and `detectors/*/detector_run.json`. Traceability sampling requires at least one report section with evidence references that map back to normalized evidence and raw events.

### Performance numbers look suspicious

Inspect `performance_summary.json`. The validation workflow records total runtime, per-stage runtimes, streamed line count, and peak memory while streaming the parse artifact.
