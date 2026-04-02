#!/usr/bin/env bash
# run-analysis.sh — one command to run the full Skill Drilla pipeline
#
# Usage:
#   ./run-analysis.sh                    # uses default transcript location
#   ./run-analysis.sh ~/my-transcripts   # custom transcript directory
#
# Prerequisites:
#   pip install -e .                     # base pipeline (zero dependencies)
#   pip install -e '.[semantic-local]'   # for clustering (recommended)
#   pip install -e '.[skill-mining]'     # for LLM-backed skill mining (optional)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Pre-flight checks ──
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 not found. Install Python 3.11+ first."
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    echo "Error: Python 3.11+ required (found $PY_VERSION)"
    exit 1
fi

if ! command -v skill-drilla &> /dev/null; then
    echo "Error: skill-drilla CLI not found."
    echo ""
    echo "Install it with:"
    echo "  pip install -e ."
    echo ""
    echo "Or for all features:"
    echo "  pip install -e '.[all]'"
    exit 1
fi

CONFIG="configs/chat-analysis.default.yaml"
if [ ! -f "$CONFIG" ]; then
    echo "Error: Config not found at $CONFIG"
    echo "Make sure you're running from the skill-drilla repo root."
    exit 1
fi

# ── Resolve transcript source ──
CLAUDE_PROJECTS="${1:-}"

if [ -z "$CLAUDE_PROJECTS" ]; then
    if [ -d "$HOME/.claude/projects" ]; then
        CLAUDE_PROJECTS="$HOME/.claude/projects"
        echo "Auto-detected Claude Code transcripts at: $CLAUDE_PROJECTS"
    else
        echo "Error: Could not find Claude Code transcripts."
        echo ""
        echo "Claude Code stores transcripts at ~/.claude/projects/"
        echo "Each project is a directory containing .jsonl session files:"
        echo "  ~/.claude/projects/"
        echo "    -project-name/"
        echo "      session-uuid.jsonl"
        echo "      session-uuid.jsonl"
        echo ""
        echo "If yours are elsewhere, pass the path as an argument:"
        echo "  ./run-analysis.sh /path/to/your/transcripts"
        exit 1
    fi
fi

if [ ! -d "$CLAUDE_PROJECTS" ]; then
    echo "Error: Directory not found: $CLAUDE_PROJECTS"
    exit 1
fi

SESSION_COUNT=$(find "$CLAUDE_PROJECTS" -name '*.jsonl' | wc -l)
if [ "$SESSION_COUNT" -eq 0 ]; then
    echo "Error: No .jsonl transcript files found in $CLAUDE_PROJECTS"
    echo ""
    echo "Expected: directories containing .jsonl session files."
    echo "Claude Code stores these at ~/.claude/projects/-project-name/session-uuid.jsonl"
    exit 1
fi

# ── Optional dependency check ──
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Skill Drilla Pipeline                                      ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Source:   $CLAUDE_PROJECTS"
echo "  Sessions: $SESSION_COUNT transcript files"
echo "  Python:   $PY_VERSION"
echo ""

HAS_SEMANTIC=false
HAS_SKILL_MINING=false
if python3 -c "import sentence_transformers" 2>/dev/null; then
    HAS_SEMANTIC=true
    echo "  ✓ sentence-transformers installed (clustering available)"
else
    echo "  ○ sentence-transformers not installed (clustering unavailable)"
    echo "    Install with: pip install -e '.[semantic-local]'"
fi
if python3 -c "import pydantic_ai" 2>/dev/null; then
    HAS_SKILL_MINING=true
    echo "  ✓ pydantic-ai installed (LLM skill mining available)"
else
    echo "  ○ pydantic-ai not installed (LLM skill mining unavailable)"
    echo "    Install with: pip install -e '.[skill-mining]'"
fi
echo ""

# ── Pipeline ──
ARTIFACT_ROOT="artifacts/chat-analysis"

# Copy transcripts into projects/ if not already there
if [ ! -d "projects" ] || [ -z "$(ls -A projects/ 2>/dev/null)" ]; then
    echo "→ Copying transcripts into projects/..."
    mkdir -p projects
    cp -r "$CLAUDE_PROJECTS"/* projects/ 2>/dev/null || true
    echo "  Done."
    echo ""
fi

# Stage 1: Discover
echo "▸ [1/7] Discovering projects and sessions..."
skill-drilla discover \
    --config "$CONFIG" \
    --projects-root projects \
    --output-dir "$ARTIFACT_ROOT/discovery/run" \
    > /dev/null
INVENTORY="$ARTIFACT_ROOT/discovery/run/session_inventory.jsonl"
echo "  ✓ Found $(wc -l < "$INVENTORY") sessions"

# Stage 2: Parse
echo "▸ [2/7] Parsing raw events from transcripts..."
skill-drilla parse \
    --inventory "$INVENTORY" \
    --output-dir "$ARTIFACT_ROOT/parse/run" \
    > /dev/null
echo "  ✓ Raw events written"

# Stage 3: Normalize
echo "▸ [3/7] Normalizing into canonical evidence..."
skill-drilla normalize \
    --inventory "$INVENTORY" \
    --raw-events "$ARTIFACT_ROOT/parse/run/raw_events.jsonl" \
    --output-dir "$ARTIFACT_ROOT/normalize/run" \
    > /dev/null
EVIDENCE="$ARTIFACT_ROOT/normalize/run/evidence.jsonl"
EVIDENCE_COUNT=$(wc -l < "$EVIDENCE")
echo "  ✓ $EVIDENCE_COUNT evidence records"

# Stage 4: Build views
echo "▸ [4/7] Building corpus views..."
for VIEW_NAME in user_nl_root_only root_only_all_roles; do
    skill-drilla build-view \
        --evidence "$EVIDENCE" \
        --view "$VIEW_NAME" \
        --output-dir "$ARTIFACT_ROOT/views/$VIEW_NAME" \
        > /dev/null
done
VIEW_DIR="$ARTIFACT_ROOT/views/user_nl_root_only"
VIEW_COUNT=$(wc -l < "$VIEW_DIR/corpus_view.jsonl")
echo "  ✓ user_nl_root_only: $VIEW_COUNT rows"

# Stage 5: Detect patterns
echo "▸ [5/7] Running pattern detectors..."
DETECTOR_OK=0
DETECTOR_FAIL=0
for DETECTOR in repeated_instructions change_requests refinement_requests workflow_patterns; do
    if skill-drilla detect \
        --view-dir "$VIEW_DIR" \
        --detector "$DETECTOR" \
        --output-dir "$ARTIFACT_ROOT/detectors/$DETECTOR" \
        > /dev/null 2>&1; then
        DETECTOR_OK=$((DETECTOR_OK + 1))
    else
        DETECTOR_FAIL=$((DETECTOR_FAIL + 1))
    fi
done
if [ "$DETECTOR_FAIL" -gt 0 ]; then
    echo "  ✓ $DETECTOR_OK detectors complete ($DETECTOR_FAIL failed — check view data)"
else
    echo "  ✓ $DETECTOR_OK detectors complete"
fi

# Stage 6: Extract episodes
echo "▸ [6/7] Extracting conversation episodes..."
skill-drilla extract-episodes \
    --evidence "$EVIDENCE" \
    --output-dir "$ARTIFACT_ROOT/episodes" \
    > /dev/null
EP_DIR="$ARTIFACT_ROOT/episodes/default"
EP_COUNT=$(python3 -c "import json; print(json.load(open('$EP_DIR/episode_index.json'))['episode_count'])")
TURN_COUNT=$(python3 -c "import json; print(json.load(open('$EP_DIR/episode_index.json'))['turn_count'])")
echo "  ✓ $EP_COUNT episodes, $TURN_COUNT turns"

# Stage 7: Generate report
echo "▸ [7/7] Generating analysis report..."
if [ -f "$ARTIFACT_ROOT/detectors/repeated_instructions/detector_run.json" ]; then
    skill-drilla report \
        --detector-run "$ARTIFACT_ROOT/detectors/repeated_instructions/detector_run.json" \
        --output-dir "$ARTIFACT_ROOT/reports/summary" \
        > /dev/null
    echo "  ✓ Report written"
else
    echo "  ⚠ Skipped — no detector results to report on"
fi

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  Pipeline complete!                                         ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Evidence:  $EVIDENCE ($EVIDENCE_COUNT records)"
echo "  Episodes:  $EP_DIR/episodes.jsonl ($EP_COUNT episodes)"
echo "  Views:     $VIEW_DIR/ ($VIEW_COUNT user turns)"
if [ -f "$ARTIFACT_ROOT/reports/summary/report.md" ]; then
    echo "  Report:    $ARTIFACT_ROOT/reports/summary/report.md"
fi
echo ""
echo "Next steps:"
echo ""
echo "  1. Read the report:"
echo "     cat $ARTIFACT_ROOT/reports/summary/report.md"
echo ""
if [ "$HAS_SEMANTIC" = true ]; then
    echo "  2. Run the clustering notebook:"
    echo "     jupyter notebook notebooks/06_skill_mining_analysis.ipynb"
else
    echo "  2. Install clustering extras, then run the notebook:"
    echo "     pip install -e '.[semantic-local]'"
    echo "     jupyter notebook notebooks/06_skill_mining_analysis.ipynb"
fi
echo ""
if [ "$HAS_SKILL_MINING" = true ]; then
    echo "  3. Run LLM-backed skill mining:"
    echo "     skill-drilla semantic-run --method skill-mining \\"
    echo "       --episode-dir $EP_DIR \\"
    echo "       --disabled-by-default-check \\"
    echo "       --output-dir $ARTIFACT_ROOT/semantic/skill-mining"
else
    echo "  3. Install skill-mining extras for LLM analysis:"
    echo "     pip install -e '.[skill-mining]'"
    echo "     cp .env.example .env  # add your API key"
fi
echo ""
