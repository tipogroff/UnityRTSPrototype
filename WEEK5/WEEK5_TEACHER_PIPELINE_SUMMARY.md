# WEEK5_TEACHER_PIPELINE_SUMMARY

> STATUS: HISTORICAL BASELINE / DO NOT USE AS CURRENT PIPELINE
> NOTE: Preserved for Week5 traceability. For current Week5/Week6 canonical lineage, use PIPELINE_AUDIT_WEEK5_WEEK6.md and CURRENT_PIPELINE_RUNBOOK.md.

Date (UTC): 2026-04-21
Status: Week 5 closed as teacher-data stage

## 1. Week 5 goal

Week 5 goal was to build a reproducible and contract-aware teacher-side data pipeline for Gym-microRTS to Unity transfer preparation.

Week 5 was explicitly not intended to implement student training, Unity-side BC integration, or direct weight transfer.

## 2. Week 5 achieved artifacts

Teacher runtime and rollout/export path:

- `python/week5_teacher/run_teacher_rollout.py`
- `python/week5_teacher/teacher_export.py`
- raw rollout artifacts in `python/week5_teacher/teacher_rollouts/`
- runtime summaries in `python/week5_teacher/teacher_logs/`

Teacher training path (hardened path exists, not a Day 7 target):

- `python/week5_teacher/train_teacher_smoke.py`
- `python/week5_teacher/resume_training.py`
- checkpoints and metadata in `python/week5_teacher/teacher_models/` and `python/week5_teacher/teacher_logs/`

Adapter and conversion reporting:

- `python/week5_teacher/adapt_teacher_dataset.py`
- `python/week5_teacher/day4_dataset_adapter.py`
- adapted artifacts and conversion reports in `python/week5_teacher/teacher_exports/`

Contract-level validation and quality reporting:

- `python/week5_teacher/validate_adapted_dataset.py`
- `strict_validation_day5.json`, `quality_report_day5.json`, `quality_report_day5.md`

BC-ready data layer and dry run:

- `python/week5_teacher/build_bc_ready_dataset_day6.py`
- `python/week5_teacher/dry_run_bc_loader.py`
- BC-ready exports in `python/week5_teacher/teacher_exports_bc/`

Current preferred BC-ready source (updated 2026-04-22 after corrective rerun — baseline switch):

- `python/week5_teacher/teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z`

Previous preferred (now historical baseline only — do not delete):

- `python/week5_teacher/teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_first_nonrandom_meaningful_20260421T103641Z`

## 3. Canonical public entrypoints

All commands are expected to run with the Week 5 canonical Python env:

- `python/week5_teacher/.venv_day2_py39/Scripts/python.exe`

### 3.1 Rollout and raw export (Day 3)

- Script: `python/week5_teacher/run_teacher_rollout.py`
- Output roots:
  - raw episodes: `python/week5_teacher/teacher_rollouts/`
  - run logs/summaries: `python/week5_teacher/teacher_logs/`

### 3.2 Adapter (Day 4)

- Script: `python/week5_teacher/adapt_teacher_dataset.py`
- Input: one raw batch directory from `teacher_rollouts/`
- Outputs in `python/week5_teacher/teacher_exports/`:
  - `episode_*.adapted.npz`
  - `conversion_report.json`
  - `adapted_batch.summary.json`
  - optional `conversion_debug.jsonl`

### 3.3 Validator (Day 5)

- Script: `python/week5_teacher/validate_adapted_dataset.py`
- Input: one adapted batch directory from `teacher_exports/`
- Outputs:
  - `strict_validation_day5.json`
  - `quality_report_day5.json`
  - `quality_report_day5.md`

### 3.4 BC-ready packaging (Day 6)

- Script: `python/week5_teacher/build_bc_ready_dataset_day6.py`
- Canonical input source (updated 2026-04-22 — baseline switch):
  - `python/week5_teacher/teacher_exports/teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z`
- Previous canonical input source (now historical baseline only):
  - `python/week5_teacher/teacher_exports/teacher_adapted_day5_first_nonrandom_meaningful`
- Outputs in `python/week5_teacher/teacher_exports_bc/<day6_run>/`:
  - `bc_train.npz`
  - `bc_validation.npz`
  - `bc_debug.npz`
  - `bc_manifest.json`
  - `bc_summary.json`

### 3.5 Loader compatibility dry run (Day 6)

- Script: `python/week5_teacher/dry_run_bc_loader.py`
- Input: one BC-ready run directory from `teacher_exports_bc/`
- Output:
  - `dry_run_bc_loader_report.json`

## 4. Canonical Week 5 path (official)

Official Week 5 teacher-data path:

1. `run_teacher_rollout.py` -> raw teacher trajectories
2. `adapt_teacher_dataset.py` -> Unity-contract-shaped adapted trajectories
3. `validate_adapted_dataset.py` -> contract-level pass/fail + quality signals
4. `build_bc_ready_dataset_day6.py` -> split packaging and manifest
5. `dry_run_bc_loader.py` -> student-side loader compatibility proof

This is the canonical path for data-stage completion and Week 6 handoff readiness.

## 5. Week 5 limitations (explicit)

The following limitations remain and are intentionally documented without smoothing:

1. Teacher quality is bounded by currently available teacher policy quality.
2. Adapter mapping is not bijective in multiple branches; it includes approximation.
3. Action filtering and remapping exist (including remap-to-noop pressure).
4. Mask semantics are treated as diagnostic/pre-sampling context, not runtime truth equivalence.
5. Direct Gym->Unity semantic parity is not proven by Week 5.
6. Direct weight transfer remains blocked and was not a Week 5 objective.
7. BC-ready data layer does not prove BC success, convergence, or policy quality.

## 6. Week 6 bridge (explicit handoff)

### 6.1 Canonical input files for Week 6

Current preferred BC-ready run (updated 2026-04-22 — post-correction baseline switch):

- `python/week5_teacher/teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z`

Student-side expected input files:

- `bc_train.npz` (3,650 samples)
- `bc_validation.npz` (390 samples)
- optional `bc_debug.npz` (256 samples)
- `bc_manifest.json`
- `dry_run_bc_loader_report.json`

Previous preferred BC-ready run (now historical baseline only — do not delete):

- `python/week5_teacher/teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_first_nonrandom_meaningful_20260421T103641Z`

### 6.2 Current preferred adapted source reference

Preferred adapted source batch (updated 2026-04-22):

- `python/week5_teacher/teacher_exports/teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z`

Previous preferred adapted source (now historical baseline only):

- `python/week5_teacher/teacher_exports/teacher_adapted_day5_first_nonrandom_meaningful`

Baseline switch documentation:

- `WEEK5/PREFERRED_TEACHER_BASELINE_UPDATE.md` — detailed comparison and switch reasoning
- `python/week5_teacher/teacher_exports/COMPARE_TEACHER_BATCHES_DAY5_corrective_cpu_vs_preferred.json` — machine-readable comparison artifact
- `python/week5_teacher/teacher_exports/COMPARE_TEACHER_BATCHES_DAY5.md` — first comparison (historical)

### 6.3 Risks to monitor during BC integration

1. Semantic weakening share and remap-to-noop pressure.
2. Action class imbalance.
3. Inactive-branch anomaly presence.
4. Optional mask absence in current preferred BC-ready source.
5. Teacher candidate quality drift between future adapted batches.

## 7. Week 5 closure statement

Week 5 is now closed as a reproducible and documented teacher-data stage.

Week 6 can begin from canonical BC-ready manifests and split artifacts without format rediscovery or manual conversion steps.

Post-closure update (2026-04-22): canonical preferred BC-ready source and adapted source have been updated following a corrective rerun and comparison result=better. See `WEEK5/PREFERRED_TEACHER_BASELINE_UPDATE.md` for full comparison, baseline switch reasoning, and traceability record.
