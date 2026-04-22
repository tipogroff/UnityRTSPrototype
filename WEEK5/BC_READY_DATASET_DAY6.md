# Week 5 Day 6: BC-ready Dataset Packaging and Loader Dry Run

Date (UTC): 2026-04-21
Status: complete

## 1) Input source

- Canonical adapted source batch:
  - `python/week5_teacher/teacher_exports/teacher_adapted_day5_first_nonrandom_meaningful`
- Day 5 gate used before packaging:
  - `strict_validation_day5.json` status: `pass`
- Scope boundary:
  - This Day 6 run does not start/stop/modify ongoing teacher training.
  - This Day 6 run only repackages already validated adapted data.

## 2) Day 6 artifacts created

- New packager script:
  - `python/week5_teacher/build_bc_ready_dataset_day6.py`
- New loader dry-run script:
  - `python/week5_teacher/dry_run_bc_loader.py`
- New BC-ready dataset folder:
  - `python/week5_teacher/teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_first_nonrandom_meaningful_20260421T103641Z`
- New Day 6 metadata:
  - `bc_manifest.json`
  - `bc_summary.json`
  - `dry_run_bc_loader_report.json`
- Split files:
  - `bc_train.npz`
  - `bc_validation.npz`
  - `bc_debug.npz`

## 3) Split policy and counts

- Policy:
  - deterministic hash split by `sample_id`
  - `train_ratio=0.9`, `val_ratio=0.1`, `seed=17`
  - debug split is deterministic subset of train, `debug_size=256`
- Counts:
  - train: 1804
  - validation: 196
  - debug: 256
  - total packaged samples: 2000

## 4) Canonical BC-ready sample schema (v1)

Schema version: `day6.bc_ready.v1`

Required fields per sample:

- `input_tensor`
  - dtype: `float32`
  - shape: `[24, 24, 27]`
- `target_action_branches`
  - dtype: `int16`
  - shape: `[576, 7]`
  - branch sizes: `[6, 4, 4, 4, 4, 4, 9]`
- `metadata`
  - `sample_id: string` (`ep{episode_id}_step{step_id}`)
  - `episode_id: int32`
  - `step_id: int32`
  - `source_episode_file: string`
  - `split: train|validation|debug`

Optional fields:

- `optional_mask`
  - not present in current canonical Day 6 batch
  - loader must treat mask as optional and support absence

Diagnostic-only fields:

- `diagnostic_reward_t` (`float32`, if present)
- `diagnostic_done_t` (`bool`, if present)

## 5) Loader dry run result

Executed minimal data-compatibility loader on generated exports:

- command target:
  - `python/week5_teacher/teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_first_nonrandom_meaningful_20260421T103641Z`
- result:
  - status: `pass`
  - checks passed for train/validation/debug
  - no missing required fields
  - batch shape check passed (`batch_size=64`)
  - branch decode/range checks passed
  - optional mask absence handled correctly (`has_optional_mask=false`)

Dry run report:

- `python/week5_teacher/teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_first_nonrandom_meaningful_20260421T103641Z/dry_run_bc_loader_report.json`

## 6) Supervised-target readiness checks

Checks executed from Day 6 manifest logic:

- deterministic target branches: pass
- duplicate `sample_id`: 0
- conflicting labels for same `sample_id`: 0
- action distribution degeneracy:
  - dominant action share: `0.3715`
  - degenerate distribution: `false`
- split structural consistency: pass
- metadata/source link consistency: pass
- warnings: none at Day 6 packaging level

Important interpretation boundary:

- Day 6 proves data packaging + loader compatibility readiness.
- Day 6 does not prove BC training quality or student policy performance.

## 7) Week 6 technical handoff tasks

These are intentionally not implemented in Day 6:

1. Student encoder for `input_tensor [24,24,27]`.
2. BC loss per action branch using branch-size-aware objectives.
3. Mask-aware training/evaluation path (optional mask present/absent compatible).
4. Partial transfer strategy for backbone/head and ablation plan.
5. Class-imbalance mitigation plan (weights/sampling), based on Day 5/Day 6 histograms.
6. Training-time handling of known conversion warnings from Day 5 (semantic weakening, inactive-branch anomalies).

## 8) Day 6 conclusion

Day 6 now provides a BC-ready data layer and reproducible loader compatibility dry run, with explicit schema and manifest-driven checks.

Week 6 can start from these Day 6 artifacts without refactoring Day 4/Day 5 artifact semantics.