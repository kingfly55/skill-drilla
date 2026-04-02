# Repository layer map

This document maps the approved six-layer architecture to concrete repository paths and generated artifact directories introduced in Milestone 1.

## Source layer

- Repository inputs: `projects/`
- Meaning: immutable exported Claude Code transcript history and any source-adjacent metadata that arrive from exports
- Rule: source artifacts are read-only and are never rewritten in place

## Discovery layer

- Code directories: future discovery implementations will live under `src/skill_drilla/` using dedicated modules added in later milestones
- Generated artifacts: `artifacts/chat-analysis/discovery/`
- Meaning: project inventory, session inventory, scope definitions, and root/subagent lineage metadata

## Normalization layer

- Code directories: future normalization implementations will live under `src/skill_drilla/` using dedicated modules added in later milestones
- Generated artifacts: `artifacts/chat-analysis/normalization/`
- Meaning: streaming interpretations of raw events into stable evidence units with semantic and provenance metadata

## Analysis substrate layer

- Code directories: `src/skill_drilla/contracts/` defines stable identifiers, artifact conventions, and run-manifest contracts that later substrate code will build on
- Generated artifacts: `artifacts/chat-analysis/substrate/`
- Meaning: reusable corpus views, filter definitions, recurrence-aware slices, and other canonical derived analysis inputs

## Analysis consumer layer

- Code directories: `src/skill_drilla/cli.py` exposes the stable command contract for discovery, parsing, normalization, view-building, search, seed expansion, detection, reporting, notebook export, semantic runs, and validation
- Supporting code: `src/skill_drilla/config.py` loads normalized configuration shared by every command
- Generated artifacts: command-specific outputs under `artifacts/chat-analysis/` and contract snapshots under `artifacts/chat-analysis/contracts/`
- Meaning: search, notebooks, detectors, reports, validation, and future semantic workflows consume the same substrate rather than inventing parallel formats

## Decision-support layer

- Code directories: future reporting and export modules will live under `src/skill_drilla/` in later milestones
- Generated artifacts: `artifacts/chat-analysis/reports/`
- Meaning: evidence packs, human-readable reports, and other reproducible outputs used for judgment and follow-up actions

## Cross-layer contract directories

- `configs/chat-analysis.default.yaml` — baseline local-first execution contract shared across all layers
- `schemas/run_manifest.schema.json` — minimum schema every command must satisfy when writing run manifests
- `artifacts/chat-analysis/contracts/` — normalized effective configuration snapshots and manifest-contract smoke outputs
