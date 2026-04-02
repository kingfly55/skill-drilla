# Packaging Readiness Report

Analysis of what to ship, what to strip, and what to fix before making this repo public.

---

## Executive summary

The codebase is a **local-first CLI pipeline** that turns exported Claude Code chat transcripts into structured analysis: evidence extraction, episode reconstruction, semantic clustering, and LLM-backed skill mining. The code itself is clean and well-structured (63 Python files, 5,700 lines, 39 test files). The blockers for public distribution are all data/config issues, not code quality issues.

**Three things need to happen:**
1. Remove all personal data (541 MB chat history + 4.1 GB generated artifacts)
2. Fix 18 hardcoded absolute paths in test files
3. Make the LLM endpoint and embedding model configurable via environment variables

---

## What to ship

### Core package (SHIP)

| Path | Lines/Size | Purpose | Action needed |
|---|---|---|---|
| `src/skill_drilla/` | 5,700 lines, 63 files | Full analysis pipeline | Ship as-is |
| `schemas/` | 17 JSON schemas | Artifact validation | Ship as-is |
| `tests/` | 39 test files | Unit, integration, regression, perf | Fix hardcoded paths |
| `configs/chat-analysis.default.yaml` | 680 bytes | Default configuration template | Genericize paths |
| `pyproject.toml` | Package config | Build/install metadata | Add missing deps, update metadata |
| `pytest/__main__.py` | Custom test runner | Lightweight test harness | Ship as-is |
| `ARCHITECTURE.md` | 44 KB | System design doc | Ship as-is |

### Documentation (SHIP — curate)

| Path | Action |
|---|---|
| `docs/user-guide.md` | Ship — primary user doc |
| `docs/semantic/optional-mode.md` | Ship — documents optional semantic layer |
| `docs/skill-mining-llm-calls.md` | Ship — documents the LLM call architecture |
| `docs/architecture/layer-map.md` | Ship — system layering |
| `docs/operators/validation-and-troubleshooting.md` | Ship — ops guide |
| `docs/exec-plans/` | **Strip** — internal development plans, not user-facing |
| `docs/specs/` | **Strip** — original problem specs, internal |
| `docs/notebooks/` | Ship if notebooks are kept |
| `docs/pipeline-desired-flow.md` | Review — may reference personal setup |

### Notebooks (SHIP — as templates)

| Notebook | Size | Verdict |
|---|---|---|
| `01_corpus_exploration.ipynb` | 236 KB | **Ship** — demonstrates search workflow |
| `02_seed_term_analysis.ipynb` | 115 KB | **Ship** — demonstrates seed expansion |
| `03_corpus_audit.ipynb` | 7 KB | **Ship** — demonstrates evidence auditing |
| `04_detector_review.ipynb` | 7 KB | **Ship** — demonstrates detector output review |
| `05_iterative_insight_analysis.ipynb` | 55 KB | **Ship** — demonstrates insight iteration |
| `06_skill_mining_analysis.ipynb` | 56 KB | **Ship** — demonstrates clustering + episode mining (the key deliverable) |

All notebooks need their **output cells stripped** (they contain personal chat data in outputs). Keep the code cells and markdown — they become runnable templates when pointed at any user's own data.

### Standalone demos (OPTIONAL)

| Path | Verdict |
|---|---|
| `embedding-test/` | **Optional** — self-contained embedding playground. Useful for users evaluating models. Could ship as a separate guide. |
| `harness-engineering.md` | **Optional** — philosophy document. Helpful for understanding design rationale but not required to use the tool. |
| `pipeline.py` | **Strip** — this is the adversarial implementation pipeline runner, not part of the analysis tool itself |

---

## What to strip (DO NOT SHIP)

| Path | Size | Why |
|---|---|---|
| `projects/` | 541 MB | Personal Claude Code chat history |
| `artifacts/` | 4.1 GB | Generated from personal data |
| `docs/exec-plans/` | 280 KB | Internal development plans with personal context |
| `docs/specs/` | — | Original problem specs (personal) |
| `pipeline.py` | 48 KB | Adversarial pipeline runner — not part of the analysis tool |

### .gitignore additions needed

```gitignore
# User data — never commit
projects/
artifacts/

# Generated analysis outputs
*.pkl
/tmp/

# Environment
.env
```

---

## Fixes required before shipping

### 1. Hardcoded paths (18 test files) — HIGH PRIORITY

Every integration test and several unit tests contain:
```python
REPO_ROOT = Path("/path/to/skill-drilla")  # was hardcoded
```

**Fix:** Replace with a dynamic resolution pattern:

```python
REPO_ROOT = Path(__file__).resolve().parents[2]  # tests/unit/test_foo.py -> repo root
```

Or use a shared test helper:
```python
# tests/conftest.py (or a helper imported by all tests)
REPO_ROOT = Path(__file__).resolve().parent.parent
```

**Files to fix:**
- `tests/integration/test_end_to_end_validation.py`
- `tests/integration/test_generate_report.py`
- `tests/integration/test_build_standard_views.py`
- `tests/integration/test_parse_diagnostics.py`
- `tests/integration/test_seed_workflow.py`
- `tests/integration/test_discovery_stability.py`
- `tests/integration/test_notebook_exports.py`
- `tests/integration/test_interactive_search_cli.py`
- `tests/integration/test_semantic_optional_mode.py`
- `tests/integration/test_normalize_sample_transcripts.py`
- `tests/unit/test_notebook_loaders.py`
- `tests/unit/test_raw_event_model.py`
- `tests/unit/test_semantic_interfaces.py`
- `tests/unit/test_detector_interface.py`
- `tests/unit/test_seed_direct_hits.py`
- `tests/unit/test_seed_expansion.py`
- `tests/unit/test_search_results.py`

### 2. LLM endpoint configuration — HIGH PRIORITY

The skill-mining module hardcodes:
```python
_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_API_KEY = "sk-your-key-here"
_DEFAULT_MODEL = "openai:gpt-4o-mini"
```

**Fix:** Read from environment variables with sensible defaults:

```python
_DEFAULT_BASE_URL = os.environ.get("SKILLDRILLA_LLM_BASE_URL", "https://api.openai.com/v1")
_DEFAULT_API_KEY = os.environ.get("SKILLDRILLA_LLM_API_KEY", "")
_DEFAULT_MODEL = os.environ.get("SKILLDRILLA_LLM_MODEL", "gpt-4o-mini")
```

And document in a `.env.example`:
```bash
# LLM endpoint for skill-mining (any OpenAI-compatible API)
SKILLDRILLA_LLM_BASE_URL=https://api.openai.com/v1
SKILLDRILLA_LLM_API_KEY=sk-your-key-here
SKILLDRILLA_LLM_MODEL=gpt-4o-mini

# Embedding model for clustering (optional — uses all-MiniLM-L6-v2 by default)
SKILLDRILLA_EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### 3. Embedding model configurability — MEDIUM PRIORITY

The clustering experiments in the notebook hardcode `all-MiniLM-L6-v2`. The `semantic/embeddings.py` already supports configurable models via the `stella-local` backend, but the episode-level clustering code doesn't use it.

**Fix:** Add an `--embedding-model` parameter to the semantic-run CLI command, and have the clustering notebook read from the same config. Default to `all-MiniLM-L6-v2` (free, small, good enough).

### 4. Config template — MEDIUM PRIORITY

`configs/chat-analysis.default.yaml` references paths that are specific to this machine:
```yaml
paths:
  source_root: "projects"
  discovery_dir: "artifacts/chat-analysis/discovery/smoke-a"
```

**Fix:** Make all paths relative to the repo root. Document the expected directory structure:
```
your-repo/
  projects/           # Put your Claude Code exports here
    -project-slug/    # One directory per project
      session-uuid.jsonl
  artifacts/          # Generated by the pipeline (auto-created)
  configs/
    chat-analysis.default.yaml
```

### 5. pyproject.toml updates — MEDIUM PRIORITY

Current issues:
- No `license` field
- `authors` says "Claude Code" — should credit the actual author
- Missing `[project.urls]` for GitHub repo
- Missing `classifiers`
- `description` is vague

Suggested update:
```toml
[project]
name = "skill-drilla"
version = "0.1.0"
description = "Analyze Claude Code chat transcripts to surface recurring patterns, extract skills, and mine workflow episodes"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
semantic-local = [
  "sentence-transformers>=3.0",
  "scikit-learn>=1.4",
  "umap-learn>=0.5",
  "hdbscan>=0.8",
  "matplotlib>=3.7",
]
skill-mining = [
  "pydantic-ai>=1.0",
]
all = [
  "skill-drilla[semantic-local,skill-mining]",
]

[project.urls]
Repository = "https://github.com/your-username/skill-drilla"
```

### 6. README.md — MISSING (HIGH PRIORITY)

No README exists. Need one that covers:
1. What this is (one paragraph)
2. Quick start (5 steps: clone, install, export chats, configure, run)
3. Pipeline overview (discover → parse → normalize → view → detect → report → episodes → clustering → skill-mining)
4. How to get your Claude Code transcripts into the `projects/` folder
5. Environment variables for LLM endpoints
6. Optional dependencies explained
7. Example output screenshots or snippets

---

## Dependency audit

### Core (zero dependencies — good)

The base pipeline has no external dependencies. This is intentional and should be preserved.

### Optional: `semantic-local`

Currently pins exact versions:
```
transformers==4.46.3
sentence-transformers==3.3.1
```

**Fix:** Use minimum version pins instead of exact:
```
sentence-transformers>=3.0
```

And add the clustering deps that are actually required but not listed:
- `scikit-learn` (used by clustering.py and the notebook)
- `umap-learn` (used by notebook clustering)
- `hdbscan` (used by notebook clustering)
- `matplotlib` (used by notebook visualization)

### Optional: `skill-mining`

Currently just `pydantic-ai`. This is correct — it's the only LLM integration dep.

### Missing from optional deps

`numpy` is used implicitly by sentence-transformers but should be listed since the notebook imports it directly.

---

## Test infrastructure

The custom test runner at `pytest/__main__.py` is clever and minimal — it avoids requiring pytest as a dependency. However:

1. It doesn't support `pytest.raises` (uses try/except instead) — documented in the plan
2. It only provides `capsys` and `tmp_path` fixtures
3. Integration tests that use `subprocess.run` with `PYTHONPATH=src` will need the path fix

**Recommendation:** Keep the custom runner for the zero-dependency philosophy, but add a note that standard `pytest` also works if users prefer it.

---

## Skills output location

The current pipeline writes generated skills to `~/.claude/skills/`. For a shared package, skills should be written to a configurable output directory, defaulting to `./output/skills/` within the project.

The `--output-dir` pattern already exists on all CLI commands. The skill generation pipeline (which currently runs as a standalone Python script, not through CLI) should follow the same pattern.

---

## Recommended packaging steps (ordered)

1. **Create `.env.example`** with LLM and embedding model config
2. **Fix hardcoded paths** in 18 test files (use `Path(__file__).resolve().parents[N]`)
3. **Make LLM config env-var-driven** in `skill_mining.py`
4. **Add `projects/` and `artifacts/` to `.gitignore`**
5. **Strip notebook outputs** (keep code cells, remove output cells with personal data)
6. **Remove `docs/exec-plans/` and `docs/specs/`** (internal development artifacts)
7. **Remove `pipeline.py`** (adversarial pipeline runner, not part of the analysis tool)
8. **Update `pyproject.toml`** with proper metadata, license, expanded optional deps
9. **Write `README.md`** with quick start, pipeline overview, and config docs
10. **Write `.env.example`** documenting all configurable endpoints
11. **Add example fixtures** — a small synthetic `projects/` directory with 2-3 fake sessions that demonstrate the pipeline end-to-end without real user data
12. **Tag v0.1.0 and push**

---

## What makes this valuable to share

The unique contribution isn't the CLI plumbing — it's the **analysis methodology**:

1. **Episode reconstruction** from flat evidence rows (grouping by session, collapsing tool calls, compressing assistant responses)
2. **UMAP + HDBSCAN clustering** on sentence embeddings to find semantic request patterns (0.77 silhouette vs 0.23 for KMeans)
3. **Cluster-guided episode selection** for LLM analysis (don't random-sample — use clusters to find the most informative episodes)
4. **Multi-turn playbook extraction** where the LLM reads full episode transcripts and identifies workflow arcs, decision points, and automation opportunities
5. **Nuance mining → skill generation** pipeline that turns episode analysis into actual Claude Code skill files

This is a reusable methodology for anyone with Claude Code transcripts who wants to understand their own patterns and generate skills from them.
