# Contributing

## Setup

```bash
git clone https://github.com/kingfly55/skill-drilla.git
cd skill-drilla
pip install -e '.[all]'
```

## Running tests

```bash
# All unit tests (no external data needed)
PYTHONPATH=src python3 pytest/__main__.py tests/unit/*.py

# Single file
PYTHONPATH=src python3 pytest/__main__.py tests/unit/test_cli.py

# Integration tests (need artifacts/ from a pipeline run first)
PYTHONPATH=src python3 pytest/__main__.py tests/integration/test_extract_episodes_cli.py
```

The custom test runner at `pytest/__main__.py` provides `capsys` and `tmp_path` fixtures. Standard `pytest` also works if you prefer.

**Important**: Do NOT use `pytest.raises` — use try/except instead. The custom runner doesn't support it.

## Code style

Follow the existing codebase. Key conventions:

- **Type hints everywhere** — `from __future__ import annotations` at the top of every file
- **Frozen dataclasses** — all data models use `@dataclass(frozen=True)`
- **pathlib.Path** — never raw string paths
- **Zero core dependencies** — don't add imports that aren't in the Python stdlib to the base package. ML/LLM deps go in `[project.optional-dependencies]` with lazy imports
- **No comments on obvious code** — only where logic isn't self-evident
- **Raise ValueError with a clear message** — don't log errors, let callers handle them

## Adding a detector

1. Create `src/skill_drilla/detect/your_detector.py`
2. Subclass `BaseDetector` (see `detect/base.py`)
3. Implement `iter_candidates(rows, settings)` — yield `FindingCandidate` objects
4. Register in `detect/__init__.py` under `DETECTOR_REGISTRY`
5. Add unit tests in `tests/unit/`
6. Update the detector table in `README.md`

## Adding a view

1. Add definition in `src/skill_drilla/views/definitions.py`
2. Register in `VIEW_DEFINITIONS`
3. Available immediately via `skill-drilla build-view --view your_name`

## Adding a semantic method

1. Create `src/skill_drilla/semantic/your_method.py`
2. Subclass `SemanticMethod` (see `semantic/base.py`)
3. Implement `derive(evidence_slice, parameters)`
4. Register in `semantic/__init__.py` under `SEMANTIC_METHODS`
5. Add the method name to CLI choices in `cli.py`

## Commits

- Use conventional commits: `feat:`, `fix:`, `chore:`, `docs:`
- Keep commits focused — one logical change per commit

## Architecture

See `ARCHITECTURE.md` for the full system design. Key points:

- **User messages are primary** — assistant/tool content is secondary context
- **Normalize before analysis** — everything flows through canonical evidence
- **Traceable** — every finding → evidence_id → raw_event_id → source line
- **Non-canonical by default** — LLM outputs are always `non_canonical: true`
