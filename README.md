# Skill Drilla

Mine your Claude Code chat history to discover what you actually do, how you work, and what should become reusable skills.

Skill Drilla reads your Claude Code transcripts, reconstructs multi-turn conversation episodes, clusters them semantically, and uses an LLM to extract the implicit workflows and playbooks you follow — then generates actual Claude Code skill files from those patterns.

## Why

You've had hundreds of conversations with Claude Code. Buried in those transcripts are recurring patterns — workflows you follow repeatedly, instructions you retype, debugging loops you run through every time. Skill Drilla finds those patterns and turns them into skills so you don't have to remember or repeat them.

## What you get

1. **Pattern detection** — find repeated instructions, change requests, and workflow patterns across all your sessions
2. **Episode reconstruction** — group your evidence into multi-turn conversation threads with tool context collapsed
3. **Semantic clustering** — embed all your user turns, reduce dimensions with UMAP, cluster with HDBSCAN to find natural request groupings (0.77 silhouette vs 0.23 for KMeans)
4. **Workflow arc analysis** — classify episodes by shape (multi-phase, plan-then-execute, debug loop, etc.) and extract the step-by-step playbook you follow
5. **Skill generation** — feed episode clusters to an LLM that writes comprehensive Claude Code skill files encoding every nuance, edge case, and decision point from your actual usage

## Setup

### Requirements

- Python 3.11+
- Claude Code chat history (stored at `~/.claude/projects/` by default)
- An OpenAI-compatible LLM API key (for skill mining — any provider works)

### Install

```bash
git clone https://github.com/kingfly55/skill-drilla.git
cd skill-drilla

# Install with all features (recommended)
pip install -e '.[all]'
```

This installs the core pipeline plus:
- `sentence-transformers`, `umap-learn`, `hdbscan`, `scikit-learn`, `matplotlib` — for clustering
- `pydantic-ai` — for LLM-backed skill mining

If you only want the base pipeline (pattern detection, episode extraction — no ML, no LLM):
```bash
pip install -e .
```

### Configure your LLM endpoint

Skill mining requires an LLM. Any OpenAI-compatible API works — OpenAI, Anthropic via a proxy, local models via llama.cpp/vllm/Ollama, etc.

```bash
cp .env.example .env
```

Edit `.env`:
```bash
SKILLDRILLA_LLM_BASE_URL=https://api.openai.com/v1   # or your local endpoint
SKILLDRILLA_LLM_API_KEY=sk-your-key-here
SKILLDRILLA_LLM_MODEL=gpt-4o-mini                     # or any model your endpoint serves
```

### Verify your transcripts exist

Claude Code stores conversation transcripts at `~/.claude/projects/`. Check:

```bash
ls ~/.claude/projects/
# You should see directories like: -home-user-my-project/
# Each containing .jsonl session files
```

If your transcripts are elsewhere, you'll pass the path explicitly in the next step.

## Running the full analysis

### Option A: One command (base pipeline)

```bash
./run-analysis.sh
# or with a custom transcript path:
./run-analysis.sh /path/to/your/transcripts
```

This runs the **base pipeline**: discover → parse → normalize → build views → detect patterns → extract episodes → generate report. It takes a few minutes depending on how many sessions you have.

The script checks your Python version, confirms `skill-drilla` is installed, reports which optional extras are available, and shows progress for each stage.

**What this does NOT do**: clustering or LLM skill mining. Those require additional steps below.

### Option B: Full analysis with clustering and skill mining

After running the base pipeline:

```bash
# Step 1: Run the base pipeline
./run-analysis.sh

# Step 2: Open the clustering + skill mining notebook
jupyter notebook notebooks/06_skill_mining_analysis.ipynb
```

The notebook walks through:
1. Loading your corpus view (user natural language turns)
2. Encoding with MiniLM-L6 sentence embeddings
3. UMAP dimensionality reduction + HDBSCAN density clustering
4. LLM-based cluster labelling (names each cluster by what users are doing)
5. Selecting the best episodes per cluster
6. Feeding full episode transcripts to the LLM for playbook extraction
7. Generating candidate skill definitions

### Option C: CLI-only skill mining (no notebook)

```bash
# After running the base pipeline:
skill-drilla semantic-run \
  --method skill-mining \
  --episode-dir artifacts/chat-analysis/episodes/default \
  --backend pydantic-ai \
  --disabled-by-default-check \
  --output-dir artifacts/chat-analysis/semantic/skill-mining
```

This uses the fixture backend by default (deterministic, no LLM). Pass `--backend pydantic-ai` for LLM-backed analysis.

## Pipeline overview

```
~/.claude/projects/ (your Claude Code transcripts)
        │
        ▼
   ┌─────────┐    ┌───────┐    ┌───────────┐    ┌────────────┐
   │ discover │───▶│ parse │───▶│ normalize │───▶│ build-view │
   └─────────┘    └───────┘    └───────────┘    └─────┬──────┘
                                     │                 │
                                     │          ┌──────┴──────┐
                                     │          ▼             ▼
                                     │     ┌────────┐    ┌────────┐
                                     │     │ detect │    │ search │
                                     │     └───┬────┘    └────────┘
                                     │         ▼
                                     │     ┌────────┐
                                     │     │ report │
                                     │     └────────┘
                                     ▼
                              ┌──────────────────┐
                              │ extract-episodes  │
                              └────────┬─────────┘
                                       ▼
                              ┌──────────────────┐
                              │  semantic-run     │
                              │  (skill-mining)   │
                              └────────┬─────────┘
                                       ▼
                         ┌─────────────┴─────────────┐
                         ▼                           ▼
                  fixture backend            pydantic-ai backend
                  (deterministic)            (LLM-backed — the good stuff)
```

## What the output looks like

After running the base pipeline, you'll have:

- **`artifacts/chat-analysis/reports/summary/report.md`** — human-readable report of detected patterns (repeated instructions, change requests, workflow patterns)
- **`artifacts/chat-analysis/episodes/default/episodes.jsonl`** — every conversation reconstructed as a multi-turn episode with user turns, compressed assistant responses, and linked tool context
- **`artifacts/chat-analysis/views/user_nl_root_only/`** — filtered corpus of just your user natural language turns, ready for clustering

After running clustering + skill mining:

- **Cluster map** — your user turns grouped into 20-50 semantically coherent categories (e.g. "run_next_milestone", "adversarial_plan_review", "test_driven_bugfix")
- **Episode arc classifications** — each multi-turn conversation classified by workflow shape
- **Playbook extractions** — the implicit step-by-step process you follow for complex tasks
- **Candidate skill files** — actual Claude Code SKILL.md files ready to drop into `~/.claude/skills/`

## Environment variables

| Variable | Default | Required for |
|---|---|---|
| `SKILLDRILLA_LLM_BASE_URL` | `https://api.openai.com/v1` | LLM skill mining |
| `SKILLDRILLA_LLM_API_KEY` | _(empty)_ | LLM skill mining |
| `SKILLDRILLA_LLM_MODEL` | `gpt-4o-mini` | LLM skill mining |
| `SKILLDRILLA_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Clustering (auto-downloads) |

## Available CLI commands

| Command | Purpose |
|---|---|
| `discover` | Find Claude Code projects and sessions |
| `parse` | Extract raw events from transcripts |
| `normalize` | Classify and normalize into canonical evidence |
| `build-view` | Create filtered corpus views |
| `search` | Query evidence with keyword/boolean filters |
| `seed-expand` | Expand seed terms via co-occurrence/adjacency |
| `detect` | Run pattern detectors (7 built-in) |
| `report` | Generate analysis reports from detector runs |
| `extract-episodes` | Reconstruct multi-turn episodes from evidence |
| `semantic-run` | Embeddings, clustering, interpretation, skill-mining |
| `validate` | End-to-end validation suite |
| `inspect-evidence` | Inspect individual evidence records |

## Available detectors

| Detector | What it finds |
|---|---|
| `repeated_instructions` | Identical normalized instructions across sessions |
| `change_requests` | Recurring revision/update requests around the same focus |
| `refinement_requests` | Configuration and workflow refinement patterns |
| `workflow_patterns` | Repeated multi-step workflow sequences |
| `agent_failures` | Patterns in agent failure/recovery |
| `corrections_frustrations` | User corrections and frustration signals |
| `output_quality` | Output quality complaint patterns |

## Running tests

```bash
# Unit tests (no external data needed)
PYTHONPATH=src python3 pytest/__main__.py tests/unit/*.py

# Single test file
PYTHONPATH=src python3 pytest/__main__.py tests/unit/test_cli.py

# Standard pytest also works
pytest tests/
```

## Project structure

```
skill-drilla/
  src/skill_drilla/       # Core library (63 modules, zero core dependencies)
  tests/                  # Unit, integration, regression, performance tests
  schemas/                # JSON schema definitions for all artifact types
  configs/                # Default pipeline configuration
  notebooks/              # 6 Jupyter analysis notebooks
  docs/                   # User guide, architecture docs, operator guides
  pytest/                 # Lightweight custom test runner
  run-analysis.sh         # One-command pipeline runner
  projects/               # Your chat transcripts go here (gitignored)
  artifacts/              # Generated pipeline output (auto-created)
```

## Troubleshooting

**"Could not find Claude Code transcripts"**
Claude Code stores transcripts at `~/.claude/projects/`. If yours are elsewhere: `./run-analysis.sh /path/to/transcripts`

**"No .jsonl transcript files found"**
Expected structure: `~/.claude/projects/-project-name/session-uuid.jsonl`. Each `.jsonl` is one conversation session.

**"ModuleNotFoundError: sentence_transformers"**
You need the clustering extras: `pip install -e '.[semantic-local]'`

**"Empty API key" / skill mining returns nothing**
Copy `.env.example` to `.env` and add your LLM API key. Any OpenAI-compatible endpoint works.

**Pipeline is slow on large corpora**
Normal. 500+ sessions takes a few minutes. Evidence files can be 100+ MB.

**Integration tests fail**
Most need pipeline artifacts. Run `./run-analysis.sh` first.

## Design principles

- **Zero core dependencies** — base pipeline runs on Python 3.11+ with nothing else
- **Local-first** — data never leaves your machine unless you configure an LLM endpoint
- **Traceable** — every finding → evidence_id → raw_event_id → exact transcript line
- **Non-canonical by default** — all LLM output is marked `non_canonical: true`
- **Inspectable** — every intermediate artifact is human-readable JSON/JSONL

## License

MIT
