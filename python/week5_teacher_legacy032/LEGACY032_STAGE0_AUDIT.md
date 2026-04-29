# Stage 0 Audit: Legacy032 Teacher Pipeline

**Date**: 2026-04-29  
**Auditor**: Stage 0 scaffolding pass  
**Scope**: Existing Week 5 teacher pipeline files relevant to `gym_microrts==0.3.2` isolation

---

## 1. Existing Week 5 teacher directories

| Directory | Runtime | Notes |
|-----------|---------|-------|
| `python/week5_teacher/` | `gym-microrts v0.6.1` (primary) | Mixed v1/v2 state; **do not modify** |
| `python/week5_teacher_gridnet/` | `gym-microrts v0.6.1` | Gridnet architecture; v2-focused; **do not modify** |
| `python/week5_teacher_reference/` | `gym-microrts 0.3.2` | Reference reproduction only; read-only |
| `WEEK5/` | documentation only | Historical pipeline specs |
| `WEEK5R/` | output artifacts | Training runs, sweeps, exports |

---

## 2. Scripts categorized by reuse risk

### 2a. Training / rollout scripts

| Script | Location | Runtime assumed | Reusable? | Notes |
|--------|----------|-----------------|-----------|-------|
| `train_teacher_smoke.py` | `python/week5_teacher/` | v0.6.1 | No — without migration | Env instantiation tied to v0.6.1 venv |
| `train_teacher_behavior_first.py` | `python/week5_teacher/` | v0.6.1 | No — without migration | Same |
| `resume_training.py` | `python/week5_teacher/` | v0.6.1 | No | Same |
| `run_teacher_rollout.py` | `python/week5_teacher/` | v0.6.1 | Partial | Raw rollout logic may be portable; env init must change |
| `train_teacher_gridnet_project.py` | `python/week5_teacher_gridnet/` | v0.6.1 | No — without migration | Gridnet arch; v0.6.1 env only |
| `ppo_gridnet_diverse_encode_decode_local_save.py` | `python/week5_teacher_reference/patched_paper_scripts/` | **0.3.2** | **Yes — starting point** | Paper PPO port; already runs under 0.3.2 |

### 2b. Evaluation scripts

| Script | Location | Runtime assumed | Reusable? | Notes |
|--------|----------|-----------------|-----------|-------|
| `evaluate_teacher_checkpoint.py` | `python/week5_teacher/` | v0.6.1 | No — without migration | Records `action_type_distribution`; env init must change |
| `evaluate_teacher_actor_level.py` | `python/week5_teacher/` | v0.6.1 | Partial | Core metrics logic may port |
| `evaluate_gridnet_actor_level.py` | `python/week5_teacher_gridnet/` | v0.6.1 | No | Gridnet arch specific |
| `teacher_behavior_gate.py` | `python/week5_teacher/` | v0.6.1 | Partial | Gate logic conceptually reusable; env init must change |

### 2c. Export scripts

| Script | Location | Runtime assumed | Reusable? | Notes |
|--------|----------|-----------------|-----------|-------|
| `teacher_export.py` | `python/week5_teacher/` | v0.6.1 | Partial | Raw episode export; env init must change |
| `export_gridnet_teacher_rollout.py` | `python/week5_teacher_gridnet/` | v0.6.1 | No | Gridnet specific |

### 2d. Adapter / conversion scripts

| Script | Location | V1/V2 contract | Reusable? | Notes |
|--------|----------|----------------|-----------|-------|
| `adapt_teacher_dataset.py` | `python/week5_teacher/` | **Dual: v1_mvp (default) / v2_gridnet_compatible** | **Yes — with explicit flag** | Must be called with `--target-action-contract v2_gridnet_compatible` |
| `day4_dataset_adapter.py` | `python/week5_teacher/` | **v2 defined as `(6,4,4,4,4,7,49)`** | **Yes — with review** | Core adapter logic; attack-target remap must be checked for 0.3.2 global→local gap |

### 2e. Validation scripts

| Script | Location | Hardcoded contract | Reusable? | Notes |
|--------|----------|--------------------|-----------|-------|
| `validate_adapted_dataset.py` | `python/week5_teacher/` | **v1 hardcoded: `(6,4,4,4,4,4,9)`** | **No — requires migration** | `EXPECTED_ACTION_BRANCH_SIZES` must be updated to v2 before use |
| `build_pre_bc_sanity_report.py` | `python/week5_teacher/` | TBD | Review required | May contain v1 assumptions |

### 2f. BC dataset building scripts

| Script | Location | Hardcoded contract | Reusable? | Notes |
|--------|----------|--------------------|-----------|-------|
| `build_bc_ready_dataset_day6.py` | `python/week5_teacher/` | **v1 hardcoded: `(6,4,4,4,4,4,9)`** | **No — requires migration** | `EXPECTED_BRANCH_SIZES` must be updated to v2 |
| `dry_run_bc_loader.py` | `python/week5_teacher/` | TBD | Review required | May inherit v1 expectations |

### 2g. Reference reproduction scripts (0.3.2 native)

| Script | Location | Notes |
|--------|----------|-------|
| `verify_reference_env.py` | `python/week5_teacher_reference/scripts/` | **Already confirmed passing on 0.3.2** |
| `collect_reference_artifacts.py` | `python/week5_teacher_reference/scripts/` | Artifact collection, confirmed working |
| `run_reference_training_smoke.ps1` | `python/week5_teacher_reference/scripts/` | **Smoke training confirmed working on 0.3.2** |
| `run_reference_training_long.ps1` | `python/week5_teacher_reference/scripts/` | Long training (100k) confirmed working |

---

## 3. Known v1 layout hardcoding (migration items)

The following scripts still use the **old v1 MVP action contract** `[6,4,4,4,4,4,9]`
and **must not be used as-is** for legacy032 → Unity v2 work:

| Script | Location | Hardcoded constant | Migration action needed |
|--------|----------|--------------------|------------------------|
| `build_bc_ready_dataset_day6.py` | `python/week5_teacher/` | `EXPECTED_BRANCH_SIZES = (6, 4, 4, 4, 4, 4, 9)` | Update to `(6,4,4,4,4,7,49)` |
| `validate_adapted_dataset.py` | `python/week5_teacher/` | `EXPECTED_ACTION_BRANCH_SIZES = (6, 4, 4, 4, 4, 4, 9)` | Update to `(6,4,4,4,4,7,49)` |

> **These scripts must NOT be modified on Stage 0.**  
> They are recorded here as known migration items for Stage 6–7.

---

## 4. Risk of v0.6.1 / 0.3.2 artifact mixing

### High-risk patterns:

- Using `WEEK5R/teacher_exports/` or `WEEK5R/teacher_exports_v2/` as output for 0.3.2
  rollouts — these directories contain v0.6.1-produced artifacts.
- Calling `adapt_teacher_dataset.py` without confirming `--target-action-contract
  v2_gridnet_compatible` — default is `v1_mvp`, which silently produces a wrong dataset.
- Loading a 0.3.2 checkpoint into a v0.6.1 evaluation script — obs space differences
  may cause silent mismatches (both report 27 channels but channel layout may differ
  for certain map configurations).

### Mitigation:

- All legacy032 output must go to `python/week5_teacher_legacy032/{teacher_models,
  teacher_logs, teacher_rollouts, teacher_exports, teacher_exports_bc}/`
  or to `WEEK5R/legacy032_*/` paths.
- Adapter calls must explicitly set `--target-action-contract v2_gridnet_compatible`.

---

## 5. Risk of old v1 layout `[6,4,4,4,4,4,9]` in data

The v1 contract is present in:

- Historical BC packages under `WEEK5R/teacher_exports_bc/` (if any were built with v1 defaults)
- Any `conversion_report.json` from early Day 4 runs that used `--target-action-contract v1_mvp`
- `validate_adapted_dataset.py` output — always v1 (see section 3)

None of these should be used as inputs to the legacy032 pipeline.

---

## 6. Documents currently accurate for v2 contract

| Document | Location | Notes |
|----------|----------|-------|
| `IMPLEMENTATION_PLAN.md` | repo root | Confirms v2 `[6,4,4,4,4,7,49]` as active contract |
| `DOCUMENTATION_SYNC_REPORT.md` | repo root | Sync report confirms v2 contract |
| `python/week5_teacher/README.md` | `python/week5_teacher/` | Updated to reflect v2 migration |
| `WEEK5R/UNITY_ACTION_CONTRACT_V2_MIGRATION_PLAN.md` | `WEEK5R/` | v2 migration plan |
| `WEEK5R/UNITY_ACTION_CONTRACT_V2_SMOKE_REPORT.md` | `WEEK5R/` | v2 smoke report |
| `WEEK5R/GRIDNET_ACTION_CONTRACT_V2_MIGRATION_PLAN.md` | `WEEK5R/` | Gridnet v2 migration |
| `python/week5_teacher/ADAPTER_DAY4.md` | `python/week5_teacher/` | Adapter v2 spec |

---

## 7. Historical documents (not current spec)

| Document | Location | Notes |
|----------|----------|-------|
| `WEEK5/WEEK5_TEACHER_PIPELINE_SPEC.md` | `WEEK5/` | v1-era spec; historical only |
| `WEEK5/BC_READY_DATASET_DAY6.md` | `WEEK5/` | v1 BC dataset spec |
| `WEEK5/TEACHER_SOURCE_SELECTION.md` | `WEEK5/` | Pre-v2 decision record |
| `python/week5_teacher/DAY5_VALIDATION.md` | `python/week5_teacher/` | v1 validation context |

---

## 8. Reference env artifacts (0.3.2 baseline, read-only)

| Artifact | Location | Notes |
|----------|----------|-------|
| `reference_env_verify.json` | `python/week5_teacher_reference/artifacts/` | **Confirmed: 0.3.2 env PASS, 27-channel obs** |
| `reference_reproduction_summary.json` | `python/week5_teacher_reference/artifacts/` | Reference training result |
| `REFERENCE_REPRODUCTION_RESULT.md` | `python/week5_teacher_reference/` | Narrative result |

These confirm that `gym_microrts==0.3.2` runs under Java 17 / Python 3.9 / torch 1.8.0
on this machine.  They are the baseline for Stage 1 env probe.

---

## 9. Summary: what can be reused vs. must be migrated

### Ready to reuse (0.3.2 native):
- `ppo_gridnet_diverse_encode_decode_local_save.py` (reference training entry point)
- `verify_reference_env.py`, `run_reference_training_smoke.ps1`

### Conditionally reusable (env init change required):
- `run_teacher_rollout.py` — core logic portable, env init must switch to 0.3.2
- `teacher_export.py` — same
- `teacher_behavior_gate.py` — gate logic portable
- `adapt_teacher_dataset.py` — usable with `--target-action-contract v2_gridnet_compatible`
- `day4_dataset_adapter.py` — attack-target remap for 0.3.2 global→local gap must be verified

### Must migrate before use (hardcoded v1 contract):
- `build_bc_ready_dataset_day6.py` — `EXPECTED_BRANCH_SIZES` constant must change
- `validate_adapted_dataset.py` — `EXPECTED_ACTION_BRANCH_SIZES` constant must change

### Must not touch (v0.6.1 pipeline, out of scope):
- All other scripts in `python/week5_teacher/`
- All scripts in `python/week5_teacher_gridnet/`
