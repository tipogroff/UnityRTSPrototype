# Stage 0 Completion Report — Legacy032 Teacher Workspace

**Date**: 2026-04-29  
**Stage**: 0 — Scaffold and documentation  
**Status**: COMPLETE

---

## 1. Created directories

| Directory | Purpose |
|-----------|---------|
| `python/week5_teacher_legacy032/` | Root workspace for 0.3.2 teacher pipeline |
| `python/week5_teacher_legacy032/scripts/` | Future entrypoint scripts |
| `python/week5_teacher_legacy032/teacher_models/` | Future checkpoints |
| `python/week5_teacher_legacy032/teacher_logs/` | Training and evaluation logs |
| `python/week5_teacher_legacy032/teacher_rollouts/` | Raw episode trajectories |
| `python/week5_teacher_legacy032/teacher_exports/` | Adapted datasets (Unity v2) |
| `python/week5_teacher_legacy032/teacher_exports_bc/` | BC-ready packages |
| `python/week5_teacher_legacy032/reports/` | Markdown/JSON reports |

All empty directories contain `.gitkeep` placeholder files.

---

## 2. Created documents

| Document | Location | Purpose |
|----------|----------|---------|
| `README.md` | `python/week5_teacher_legacy032/` | Workspace overview, isolation rationale, transfer pipeline |
| `ENVIRONMENT_LEGACY032.md` | `python/week5_teacher_legacy032/` | Environment spec (confirmed + TBD fields) |
| `LEGACY032_STAGE0_AUDIT.md` | `python/week5_teacher_legacy032/` | Audit of existing Week 5 scripts and known migration items |
| `LEGACY032_TEACHER_TRAINING_PLAN.md` | `python/week5_teacher_legacy032/` | Skeleton training plan (Stages 1–7) |
| `scripts/README.md` | `python/week5_teacher_legacy032/scripts/` | Planned entrypoints (no scripts written yet) |
| `reports/STAGE0_COMPLETION_REPORT.md` | `python/week5_teacher_legacy032/reports/` | This document |

---

## 3. Modified documents

| Document | Change |
|----------|--------|
| `IMPLEMENTATION_PLAN.md` (root) | Added minimal "Legacy gym_microrts==0.3.2 teacher workspace" block under the status section |

No other existing files were modified.

---

## 4. What was found in current Week 5 pipeline

### Directories and their runtime

| Directory | Runtime | State |
|-----------|---------|-------|
| `python/week5_teacher/` | `gym-microrts v0.6.1` | Mixed v1/v2; 24 Python scripts + docs |
| `python/week5_teacher_gridnet/` | `gym-microrts v0.6.1` | Gridnet arch; v2-focused; 12 files |
| `python/week5_teacher_reference/` | `gym_microrts==0.3.2` | Reference reproduction; confirmed passing |
| `WEEK5/` | documentation | Historical specs (v1-era) |
| `WEEK5R/` | output artifacts | Training runs, sweeps, exports |

### Action contract state

- **v1 layout `[6,4,4,4,4,4,9]`** hardcoded in:
  - `build_bc_ready_dataset_day6.py` — `EXPECTED_BRANCH_SIZES`
  - `validate_adapted_dataset.py` — `EXPECTED_ACTION_BRANCH_SIZES`
- **v2 layout `[6,4,4,4,4,7,49]`** used in:
  - `day4_dataset_adapter.py` — `V2_GRIDNET_COMPATIBLE_BRANCH_SIZES`
  - `export_gridnet_teacher_rollout.py` — export metadata
  - `mask_audit/build_mask_audit_report.py`
- **Adapter with dual-contract support**:
  - `adapt_teacher_dataset.py` — accepts `--target-action-contract v1_mvp` (default) or `v2_gridnet_compatible`

### Reference env verification (0.3.2)

The existing `python/week5_teacher_reference/` already contains a confirmed
`reference_env_verify.json` artifact showing:

```
gym_microrts:     0.3.2   (CONFIRMED)
Python:           3.9.13  (CONFIRMED)
gym:              0.17.3  (CONFIRMED)
stable-baselines3: 1.0    (CONFIRMED)
torch:            1.8.0   (CONFIRMED)
JPype1:           1.4.1   (CONFIRMED)
Java:             OpenJDK 17.0.18 (CONFIRMED)
overall_status:   PASS
```

Smoke and long (100k) training runs were also confirmed passing.

---

## 5. Elements that can be reused for legacy032

| Element | Reuse path |
|---------|-----------|
| `ppo_gridnet_diverse_encode_decode_local_save.py` | Direct — already runs under 0.3.2; use as training entry point |
| `verify_reference_env.py`, `run_reference_training_smoke.ps1` | Direct — Stage 1 env probe baseline |
| `adapt_teacher_dataset.py` | With explicit `--target-action-contract v2_gridnet_compatible` flag |
| `day4_dataset_adapter.py` | After confirming attack-target remap (global 576 → local 49) |
| `run_teacher_rollout.py` | Partial — core logic portable; env init must switch to 0.3.2 venv |
| `teacher_behavior_gate.py` | Partial — gate logic portable; env init must change |

---

## 6. Elements requiring migration before use

| Element | Issue | Migration action |
|---------|-------|-----------------|
| `build_bc_ready_dataset_day6.py` | `EXPECTED_BRANCH_SIZES = (6,4,4,4,4,4,9)` — v1 hardcoded | Update constant to `(6,4,4,4,4,7,49)` before Stage 7 |
| `validate_adapted_dataset.py` | `EXPECTED_ACTION_BRANCH_SIZES = (6,4,4,4,4,4,9)` — v1 hardcoded | Update constant to `(6,4,4,4,4,7,49)` before Stage 7 |
| Any script with v0.6.1 env init | Env instantiation not compatible with 0.3.2 venv | Switch import path / venv; wrap in env probe first |
| Attack-target adapter | 0.3.2 global flat attack (576) vs Unity v2 local 7×7 (49) | Write explicit coordinate-translation adapter in Stage 6 |

---

## 7. Intentionally not done at Stage 0

The following actions were explicitly excluded from Stage 0 scope:

- **No teacher training** — no PPO runs, no checkpoints, no logs
- **No rollout export** — no trajectory files
- **No adaptation or BC packaging** — no datasets
- **No changes to `python/week5_teacher/`** — all existing scripts left untouched
- **No changes to `python/week5_teacher_gridnet/`** — left untouched
- **No changes to Unity C# code** — out of scope
- **No changes to adapter logic** — v1/v2 constants not modified
- **No v0.6.1 script imports** into legacy032 workspace
- **No weight transfer claims** — not proven; not attempted
- **No BC training** — future stage

---

## 8. What to do at Stage 1

**Stage 1 — Environment probe** (`scripts/legacy032_env_probe.py`):

1. Instantiate `gym_microrts==0.3.2` with the 24×24 `basesWorkers24x24.xml` map
2. Confirm `observation_space.shape == (N, 24, 24, 27)`
3. Confirm `action_space.nvec` for 24×24 map (expected: `[576, 6, 4, 4, 4, 4, 7, 576]`)
4. Record exact numpy version (fallback `1.25.2` was used in reference env)
5. Write `reports/stage1_env_probe.json`
6. Decide on opponent variant / env_id for teacher training

The `python/week5_teacher_reference/.venv_microrts032_reference/` venv and
`python/week5_teacher_reference/patched_paper_scripts/` are the recommended
starting point for Stage 1.

---

## 9. Key guarantees from Stage 0

- `python/week5_teacher/` is **not modified** — v0.6.1 pipeline intact
- `python/week5_teacher_gridnet/` is **not modified** — v0.6.1 gridnet pipeline intact
- `python/week5_teacher_reference/` is **not modified** — reference artifacts preserved
- **No claim** that teacher is trained
- **No claim** that direct weight transfer is proven
- **Expected action layout explicitly stated** as `[6,4,4,4,4,7,49]` throughout all documents
- **Artifact mixing** between v0.6.1 and 0.3.2 is explicitly warned against in README.md,
  ENVIRONMENT_LEGACY032.md, and LEGACY032_STAGE0_AUDIT.md
