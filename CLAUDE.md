# CLAUDE.md

## What this is

Skill Drilla is a CLI pipeline that turns Claude Code chat transcripts into structured analysis: evidence extraction, episode reconstruction, semantic clustering, and LLM-backed skill mining.

## Setup

```bash
pip install -e '.[all]'
```

For base pipeline only (zero dependencies): `pip install -e .`

## Running the pipeline

```bash
# Full pipeline — auto-detects transcripts at ~/.claude/projects/
./run-analysis.sh

# Custom transcript location
./run-analysis.sh /path/to/transcripts
```

## Running tests

```bash
# Unit tests (no external data needed)
PYTHONPATH=src python3 pytest/__main__.py tests/unit/*.py

# Single test file
PYTHONPATH=src python3 pytest/__main__.py tests/unit/test_cli.py

# Integration tests (require running the pipeline first to generate artifacts/)
PYTHONPATH=src python3 pytest/__main__.py tests/integration/test_extract_episodes_cli.py
```

The custom test runner at `pytest/__main__.py` supports `capsys` and `tmp_path` fixtures. Do NOT use `pytest.raises` — use try/except instead.

## Project layout

```
src/skill_drilla/        # Core library — 63 modules, zero core dependencies
  cli.py                 # All CLI commands — entry point
  episodes/              # Episode reconstruction from evidence
  semantic/              # Embeddings, clustering, skill mining
  detect/                # 7 pattern detectors
  normalize/             # Evidence classification and normalization
  parse/                 # Raw transcript parsing
  discovery/             # Project/session discovery
  views/                 # Corpus view filtering
  search/                # Evidence search and inspection
  report/                # Report generation
  validate/              # End-to-end validation
tests/                   # Unit, integration, regression, performance
schemas/                 # JSON schemas for all artifact types
configs/                 # Default pipeline configuration
notebooks/               # 6 Jupyter analysis notebooks
```

## CLI commands

The stable pipeline commands (in execution order):

1. `skill-drilla discover` — find projects and sessions
2. `skill-drilla parse` — extract raw events from transcripts
3. `skill-drilla normalize` — classify into canonical evidence
4. `skill-drilla build-view` — create filtered corpus views
5. `skill-drilla search` — query evidence
6. `skill-drilla detect` — run pattern detectors
7. `skill-drilla report` — generate analysis reports
8. `skill-drilla extract-episodes` — reconstruct multi-turn episodes
9. `skill-drilla semantic-run` — optional: embeddings, clustering, skill-mining

## Key conventions

- All data models use frozen dataclasses (`@dataclass(frozen=True)`)
- Zero external dependencies in core — optional extras only for ML/LLM features
- All paths use `pathlib.Path`, never raw strings
- Semantic/LLM outputs are always marked `non_canonical: true`
- Every finding traces back to `evidence_id` → `raw_event_id` → source transcript line
- Config lives at `configs/chat-analysis.default.yaml` — paths are relative to repo root

## Environment variables (for LLM features)

```
SKILLDRILLA_LLM_BASE_URL    # OpenAI-compatible endpoint (default: https://api.openai.com/v1)
SKILLDRILLA_LLM_API_KEY     # API key for skill mining
SKILLDRILLA_LLM_MODEL       # Model name (default: gpt-4o-mini)
SKILLDRILLA_EMBEDDING_MODEL  # Sentence-transformer model (default: all-MiniLM-L6-v2)
```

## Adding a new detector

1. Create `src/skill_drilla/detect/your_detector.py`
2. Subclass `BaseDetector` from `detect/base.py`
3. Implement `iter_candidates()` — yields `FindingCandidate` objects
4. Register in `detect/__init__.py` under `DETECTOR_REGISTRY`
5. Add tests in `tests/unit/`

## Adding a new view

1. Add the view definition in `src/skill_drilla/views/definitions.py`
2. Register in `VIEW_DEFINITIONS` dict
3. The view is automatically available via `skill-drilla build-view --view your_view_name`

## Common issues

- **"No .jsonl transcript files found"** — Claude Code stores transcripts at `~/.claude/projects/`. Check that path exists and contains `.jsonl` files.
- **"ModuleNotFoundError: sentence_transformers"** — Install optional extras: `pip install -e '.[semantic-local]'`
- **"SKILLDRILLA_LLM_API_KEY not set"** — Copy `.env.example` to `.env` and add your API key. Only needed for `semantic-run --method skill-mining --backend pydantic-ai`.
- **Integration tests fail** — Most integration tests require pipeline artifacts. Run `./run-analysis.sh` first.
