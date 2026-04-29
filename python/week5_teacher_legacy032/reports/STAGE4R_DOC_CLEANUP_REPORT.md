# STAGE4R Documentation Cleanup Report

Date: 2026-04-29
Scope: Documentation cleanup before Stage 5 only (no training runs, no Unity/ML logic changes)

## Files updated

- `python/week5_teacher_legacy032/LEGACY032_TEACHER_TRAINING_PLAN.md`
- `python/week5_teacher_legacy032/reports/STAGE4_24X24_ALIGNMENT_REPORT.md`
- `python/week5_teacher_legacy032/reports/STAGE4_COMPLETION_REPORT.md`
- `python/week5_teacher_legacy032/scripts/README.md`

## Stale statements found

- Unqualified teacher contract was documented as `[6,4,4,4,4,7,576]` in places where GridMode teacher training contract should be explicit.
- Stage 4R section still contained unchecked acceptance items (`probe PASS`, `10k smoke`, `behavior gate`) despite Stage 4R PASS status.
- Stage 6/7 wording implied global `576 -> 49` attack remap as universal requirement.
- Script README stage mapping for export/adapter still reflected old numbering.
- Historical Stage 4 reports had correction notes but needed explicit superseded interpretation near old `49 vs 576` blocker phrasing.

## Stale statements corrected

- Added explicit mode split in expected contracts:
  - gym.make/global single-action: `[576,6,4,4,4,4,7,576]`
  - MicroRTSGridModeVecEnv 24x24 teacher mode: `[576,6,4,4,4,4,7,49]`
  - per-cell branch sizes: `[6,4,4,4,4,7,49]`
  - Unity v2 target branches: `[6,4,4,4,4,7,49]`
  - action tensor per sample: `[576,7]`
- Marked Stage 4R acceptance checklist as completed (`[x]`) for PASS outcomes.
- Clarified Stage 5 as corrected 24x24 GridMode path with:
  - `ppo_gridnet_legacy032_24x24_local_save.py`
  - `architecture_name = legacy032_resolution_aware_gridnet_v1`
- Clarified Stage 6/7 semantics:
  - corrected GridMode exports already use local attack `49`
  - global `576 -> 49` remap only applies to gym.make/global single-action exports
- Added superseded interpretation in historical Stage 4 reports:
  - old `49 vs 576` contract blocker interpretation is historical and superseded
  - true resolved blocker was architecture spatial shape mismatch
- Updated README stage numbering and guidance:
  - Stage 6 export, Stage 7 adapter, Stage 8 validation/packaging
  - `run_staged_teacher_training_legacy032.py` is historical Stage 3 line and not for transfer-readiness when it follows 16x16 reference path
  - `evaluate_teacher_legacy032.py --env-mode target_24x24_gridmode` is target GridMode validation (not global single-action mode)

## Final contract table

| Mode | Observation | Action representation | Attack target |
|------|-------------|------------------------|---------------|
| gym.make/global single-action | `[24,24,27]` | `[576,6,4,4,4,4,7,576]` | global flat 576 |
| MicroRTSGridModeVecEnv 24x24 | `[24,24,27]` | `[576,6,4,4,4,4,7,49]` | local 7x7 49 |
| Unity v2 | `[24,24,27] / [576,27]` | per-cell `[576,7]`, branches `[6,4,4,4,4,7,49]` | local 7x7 49 |

## Current readiness state

- Stage 4 original: historical/superseded
- Stage 4R: PASS
- Decision: `READY_FOR_24X24_100K_TRAINING`
- Canonical training path for next stage: corrected 24x24 GridMode Stage 4R path only
- 16x16 reference path: historical/debug only; not transfer-ready

## Exact next action

Proceed to Stage 5 — 24×24 staged teacher training, starting with 100k sanity checkpoint using corrected Stage 4R GridMode path.
