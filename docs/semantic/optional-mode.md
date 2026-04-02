# Optional semantic mode

Semantic analysis is an optional, explicitly non-canonical extension layer.

## Principles
- Disabled by default.
- Runs only against canonical materialized corpus views.
- Preserves evidence IDs, role labels, and scope metadata from normalized evidence.
- Writes outputs under dedicated `artifacts/chat-analysis/semantic/...` directories.
- Marks every semantic artifact as `non_canonical: true` so derived interpretations remain separate from baseline corpus truth, detectors, and reports.
- Uses deterministic local fixture/stub implementations for verification.

## CLI usage
```bash
PYTHONPATH="src" \
python -m skill-drilla.cli semantic-run \
  --view-dir "artifacts/chat-analysis/views/user_nl_root_only" \
  --method clustering \
  --disabled-by-default-check \
  --output-dir "artifacts/chat-analysis/semantic/clustering-smoke"
```

The `--disabled-by-default-check` flag is required to acknowledge that semantic mode is opt-in.

## Available methods
- `embeddings` — fixture embeddings by default, with an optional local Stella backend for real vectors.
- `clustering` — deterministic keyword grouping by default, with an optional Stella-backed vector clustering mode.
- `interpretation` — local rule-based summaries over the same slices.

## Stella local backend

The `embeddings` method supports an explicit local backend based on the setup documented in `embedding-test/SETUP.md`.

Requirements:
- ROCm-compatible `torch` installed separately
- `transformers==4.46.3`
- `sentence-transformers==3.3.1`
- `HSA_OVERRIDE_GFX_VERSION=10.3.0` for the documented RX 6600 XT setup

Example:

```bash
HSA_OVERRIDE_GFX_VERSION=10.3.0 \
PYTHONPATH="src" \
python -m skill-drilla.cli semantic-run \
  --view-dir "artifacts/chat-analysis/views/user_nl_root_only" \
  --method embeddings \
  --backend stella-local \
  --model-name "NovaSearch/stella_en_1.5B_v5" \
  --device cuda \
  --torch-dtype float16 \
  --batch-size 8 \
  --trust-remote-code \
  --disabled-by-default-check \
  --output-dir "artifacts/chat-analysis/semantic/embeddings-stella"
```

The default fixture path remains available for deterministic verification and test runs.

Stella-backed clustering uses the same local model stack and adds an agglomerative clustering pass over normalized embeddings. Example:

```bash
HSA_OVERRIDE_GFX_VERSION=10.3.0 \
PYTHONPATH="src" \
python -m skill-drilla.cli semantic-run \
  --view-dir "artifacts/chat-analysis/views/user_nl_root_only" \
  --method clustering \
  --backend stella-local \
  --model-name "NovaSearch/stella_en_1.5B_v5" \
  --device cuda \
  --torch-dtype float16 \
  --batch-size 8 \
  --distance-threshold 0.3 \
  --min-cluster-size 1 \
  --trust-remote-code \
  --disabled-by-default-check \
  --output-dir "artifacts/chat-analysis/semantic/clustering-stella"
```

## Reproducibility
Each semantic run records:
- method name
- canonical input slice metadata
- derived output metadata
- implementation/model parameters
- `non_canonical: true`

This keeps semantic outputs inspectable and reproducible. Fixture runs remain fully offline and deterministic; Stella local runs remain optional and explicitly opt-in.