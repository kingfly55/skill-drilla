# Skill Drilla

Analyze your Claude Code chat transcripts to surface recurring patterns, extract episode workflows, and mine reusable skills.

Skill Drilla turns exported Claude Code history into structured, traceable analysis. It finds what instructions you repeat, what workflows you follow, and what patterns could become automated skills — without sending your data anywhere.

## What it does

1. **Discovers** your Claude Code projects and sessions
2. **Parses** raw transcript events into structured records
3. **Normalizes** everything into canonical evidence with semantic classification (user NL, assistant NL, tool calls, system records)
4. **Builds filtered views** for targeted analysis (e.g. user turns only, root sessions only)
5. **Detects patterns** via lexical heuristics (repeated instructions, change requests, workflow refinement)
6. **Extracts episodes** — reconstructs multi-turn conversation threads with tool context collapsed and subagents linked (not inlined)
7. **Clusters semantically** — embeds user turns with sentence-transformers, reduces with UMAP, clusters with HDBSCAN to find natural groupings
8. **Mines skills** — feeds episode transcripts to an LLM to extract workflow arcs, playbooks, and candidate skill definitions

## Quick start

```bash
git clone https://github.com/kingfly55/skill-drilla.git
cd skill-drilla
pip install -e '.[all]'    # or just: pip install -e .  (zero-dependency base)
./run-analysis.sh           # auto-detects ~/.claude/projects/ and runs everything
```

That's it. The script finds your Claude Code transcripts, runs the full pipeline (discover → parse → normalize → views → detect → episodes → report), and tells you what to do next.

### What you need

- Python 3.11+
- Claude Code chat history at `~/.claude/projects/` (this is where Claude Code stores transcripts by default)

### Optional extras

```bash
# Clustering and embeddings (sentence-transformers, UMAP, HDBSCAN)
pip install -e '.[semantic-local]'

# LLM-backed skill mining (pydantic-ai)
pip install -e '.[skill-mining]'

# Everything
pip install -e '.[all]'
```

For LLM-backed skill mining, set your API key:

```bash
cp .env.example .env
# Edit .env — any OpenAI-compatible endpoint works
```

### Custom transcript location

If your transcripts aren't at `~/.claude/projects/`:

```bash
./run-analysis.sh /path/to/your/transcripts
```

### Manual pipeline (individual commands)

<details>
<summary>Click to expand step-by-step commands</summary>

```bash
skill-drilla discover --config configs/chat-analysis.default.yaml \
  --projects-root projects --output-dir artifacts/chat-analysis/discovery

skill-drilla parse --inventory artifacts/chat-analysis/discovery/session_inventory.jsonl \
  --output-dir artifacts/chat-analysis/parse

skill-drilla normalize \
  --inventory artifacts/chat-analysis/discovery/session_inventory.jsonl \
  --raw-events artifacts/chat-analysis/parse/raw_events.jsonl \
  --output-dir artifacts/chat-analysis/normalize

skill-drilla build-view \
  --evidence artifacts/chat-analysis/normalize/evidence.jsonl \
  --view user_nl_root_only \
  --output-dir artifacts/chat-analysis/views/user_nl_root_only

skill-drilla detect \
  --view-dir artifacts/chat-analysis/views/user_nl_root_only \
  --detector repeated_instructions \
  --output-dir artifacts/chat-analysis/detectors/repeated_instructions

skill-drilla extract-episodes \
  --evidence artifacts/chat-analysis/normalize/evidence.jsonl \
  --output-dir artifacts/chat-analysis/episodes

skill-drilla report \
  --detector-run artifacts/chat-analysis/detectors/repeated_instructions/detector_run.json \
  --output-dir artifacts/chat-analysis/reports

skill-drilla semantic-run --method skill-mining \
  --episode-dir artifacts/chat-analysis/episodes/default \
  --disabled-by-default-check \
  --output-dir artifacts/chat-analysis/semantic/skill-mining
```

</details>

## Pipeline overview

```
Claude Code transcripts (~/.claude/projects/)
    |
    v
discover ──> parse ──> normalize ──> build-view
                                        |
                        ┌───────────────┼───────────────┐
                        v               v               v
                     detect          search         seed-expand
                        |
                        v
                     report
                                        
normalize ──> extract-episodes ──> semantic-run (skill-mining)
                                        |
                              ┌─────────┴─────────┐
                              v                   v
                    fixture backend         pydantic-ai backend
                    (deterministic)         (LLM-backed)
```

## Clustering and episode analysis (the interesting part)

The real value is in the analysis notebook at `notebooks/06_skill_mining_analysis.ipynb`. It demonstrates:

1. **MiniLM-L6 sentence embeddings** of all user turns
2. **UMAP dimensionality reduction** (384D → 10D)
3. **HDBSCAN density clustering** — finds 28 natural clusters with 0.77 silhouette (vs 0.23 for KMeans)
4. **LLM cluster labelling** — names each cluster by its semantic purpose
5. **Episode-level analysis** — classifies multi-turn conversations by arc shape (multi_phase, plan_then_execute, debug_loop, etc.)
6. **Playbook extraction** — identifies the implicit step-by-step workflow the user follows
7. **Skill chain discovery** — finds which request types commonly follow each other
8. **Skill generation** — produces actual Claude Code skill files from mined patterns

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `SKILLDRILLA_LLM_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible endpoint for skill mining |
| `SKILLDRILLA_LLM_API_KEY` | (empty) | API key for the LLM endpoint |
| `SKILLDRILLA_LLM_MODEL` | `gpt-4o-mini` | Model name for skill mining |
| `SKILLDRILLA_EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformer model for clustering |

Any OpenAI-compatible API works (OpenAI, Anthropic via proxy, local models via llama.cpp/vllm/etc).

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
| `notebook-export` | Export artifacts for Jupyter analysis |
| `semantic-run` | Optional: embeddings, clustering, interpretation, skill-mining |
| `validate` | End-to-end validation suite |
| `extract-episodes` | Reconstruct multi-turn episodes from evidence |
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

## Available views

| View | What it includes |
|---|---|
| `user_nl_root_only` | User natural language from root sessions only |
| `assistant_nl_root_only` | Assistant natural language from root sessions |
| `root_only_all_roles` | All semantic classes from root sessions |
| `combined_nl_root_plus_subagent` | NL from both root and subagent sessions |
| `root_plus_subagent_all_roles` | Everything from root + subagent |
| `debug_included_and_excluded` | All evidence including excluded records |

## Running tests

```bash
# Using the built-in lightweight runner (zero dependencies)
PYTHONPATH=src python pytest/__main__.py tests/unit/test_cli.py

# Run all unit tests
PYTHONPATH=src python pytest/__main__.py tests/unit/*.py

# Standard pytest also works if installed
pytest tests/
```

## Project structure

```
skill-drilla/
  src/skill_drilla/       # Core library (63 modules, zero core dependencies)
  tests/                  # Unit, integration, regression, performance tests
  schemas/                # JSON schema definitions for all artifact types
  configs/                # Default configuration
  notebooks/              # Jupyter analysis notebooks (6 notebooks)
  docs/                   # User guide, architecture docs, operator guides
  pytest/                 # Lightweight custom test runner
  projects/               # YOUR chat transcripts go here (gitignored)
  artifacts/              # Generated pipeline output (auto-created)
```

## Troubleshooting

**"Could not find Claude Code transcripts"**
Claude Code stores transcripts at `~/.claude/projects/`. If yours are elsewhere, pass the path: `./run-analysis.sh /path/to/transcripts`

**"No .jsonl transcript files found"**
The expected structure is `projects/-project-name/session-uuid.jsonl`. Each `.jsonl` file is one conversation session.

**"ModuleNotFoundError: sentence_transformers"**
Install the optional clustering extras: `pip install -e '.[semantic-local]'`

**"SKILLDRILLA_LLM_API_KEY not set" / empty API key**
Copy `.env.example` to `.env` and add your API key. Only needed for `semantic-run --method skill-mining --backend pydantic-ai`.

**Integration tests fail**
Most integration tests require pipeline artifacts. Run `./run-analysis.sh` first to generate them.

**Pipeline is slow on large corpora**
The normalize and parse stages process every transcript sequentially. For 500+ sessions, expect a few minutes. Evidence files can be 100+ MB — this is normal.

## Design principles

- **Zero core dependencies** — the base pipeline runs on Python 3.11+ with nothing else installed
- **Local-first** — your data never leaves your machine unless you explicitly configure an LLM endpoint
- **Traceable** — every finding links back to specific evidence records, which link back to exact transcript lines
- **Non-canonical by default** — all LLM-generated output is explicitly marked `non_canonical: true`
- **Inspectable** — every intermediate artifact is human-readable JSON/JSONL

## License

MIT
