# Legacy032 Teacher Training Plan

**Status**: Stage 0 skeleton — no training has been run  
**Date created**: 2026-04-29  
**Runtime target**: `gym_microrts==0.3.2`

---

## Goal

Produce a teacher policy trained under `gym_microrts==0.3.2` that can serve as a
source of behavioral trajectories for BC-based transfer to the Unity RTS student.
The teacher's raw rollouts must be adaptable to the Unity v2 action contract via
the existing adapter pipeline (with confirmed v2 target mode).

---

## Scope

- Training a PPO teacher agent against `gym_microrts==0.3.2` (24×24 map,
  multi-opponent or random-enemy variant)
- Exporting raw per-episode trajectories (observations + actions)
- Adapting trajectories to Unity v2 contract `[6,4,4,4,4,7,49]`
- Producing validated BC-ready dataset packages

---

## Non-goals

- Direct weight transfer from the teacher to Unity inference (not proven)
- Modifying Unity C# code
- Modifying `python/week5_teacher/` or `python/week5_teacher_gridnet/` pipelines
- Replacing or superseding the v0.6.1 teacher pipeline
- Any changes to existing `WEEK5R/` output artifacts

---

## Expected contracts

### Observation (teacher side)

```python
observation_shape = [1, 24, 24, 27]   # per-vectorized-env, 27-channel
```

### Action (teacher side — gym_microrts 0.3.2 native)

```python
teacher_branch_sizes = [6, 4, 4, 4, 4, 7, 576]   # last = global flat attack (24x24)
```

### Action (Unity v2 target — adapter output)

```python
unity_v2_branch_sizes = [6, 4, 4, 4, 4, 7, 49]   # last = local 7x7 attack
```

### BC-ready sample shapes

```python
obs_shape_per_sample    = [576, 27]   # 576 cells, 27 channels each
action_shape_per_sample = [576, 7]    # 576 cells, 7 branches (v2)
```

---

## Planned stages

### Stage 1 — Environment probe

**Entry point**: `scripts/legacy032_env_probe.py` (to be created)

Tasks:
- Instantiate `gym_microrts==0.3.2` with 24×24 map
- Print and record: `observation_space.shape`, `action_space.nvec`
- Confirm observation channel count (27 expected)
- Confirm branch sizes per cell: `[6, 4, 4, 4, 4, 7, 576]` or actual value
- Record Java version and venv path
- Write `reports/stage1_env_probe.json`

Acceptance criteria:
- [ ] Env instantiates without error
- [ ] `observation_space.shape == (N, 24, 24, 27)` for N envs
- [ ] Action space nvec confirmed
- [ ] `reports/stage1_env_probe.json` written

---

### Stage 2 — Smoke training

**Entry point**: `scripts/train_teacher_legacy032.py` (to be created)

Tasks:
- Short PPO run (≤10k steps) to confirm training loop works
- Checkpoint saved to `teacher_models/smoke/`
- Training log saved to `teacher_logs/smoke/`

Acceptance criteria:
- [ ] Training completes without crash
- [ ] At least one checkpoint written
- [ ] Loss / reward metrics logged

---

### Stage 3 — Behavior-first gate

**Entry point**: `scripts/evaluate_teacher_legacy032.py` (to be created)

Tasks:
- Evaluate smoke/short checkpoint
- Record `action_type_distribution` (move_share, noop_share, etc.)
- Apply behavior gate: require `move_share > 0.05` (teacher must demonstrate
  intentional movement)
- Write `reports/stage3_behavior_gate.json`

Acceptance criteria:
- [ ] Evaluation runs without error
- [ ] `action_type_distribution` recorded
- [ ] Behavior gate decision written to report

---

### Stage 4 — Main teacher training

**Entry point**: `scripts/train_teacher_legacy032.py` (extended run)

Tasks:
- Full PPO run (target: 100k–500k steps, to be determined)
- Checkpoints saved at regular intervals to `teacher_models/`
- TensorBoard logs (optional) to `teacher_logs/`
- Evaluate final checkpoint with behavior gate

Acceptance criteria:
- [ ] Teacher demonstrates consistent movement and combat behavior
- [ ] Behavior gate PASS at final checkpoint
- [ ] Checkpoint selected for rollout export

---

### Stage 5 — Raw rollout export

**Entry point**: `scripts/export_teacher_rollout_legacy032.py` (to be created)

Tasks:
- Run trained teacher for N episodes (target: ≥200 episodes)
- Export per-episode: observations, raw actions, rewards, dones
- Save to `teacher_rollouts/` (namespaced by run timestamp)
- Record rollout summary: episode count, mean return, action distribution

Acceptance criteria:
- [ ] Rollout export completes
- [ ] `teacher_rollouts/{run_id}/rollout_summary.json` written
- [ ] Observations are 27-channel, shape `[T, 24, 24, 27]`
- [ ] Raw actions recorded as per-cell `[6,4,4,4,4,7,576]` or similar

---

### Stage 6 — Adapter to Unity v2

**Entry point**: `scripts/adapt_legacy032_to_unity_v2.py` (to be created)

Tasks:
- Call `adapt_teacher_dataset.py` with `--target-action-contract v2_gridnet_compatible`
  (or a dedicated 0.3.2-aware adapter if needed)
- Handle **attack-target remap**: global flat index (576) → local 7×7 (49)
- Record conversion report in `teacher_exports/{run_id}/conversion_report.json`

Known risk:
- Attack-target semantic gap: `gym_microrts==0.3.2` encodes attack as a global
  cell index across the 24×24 grid; Unity v2 expects a local 7×7 window centered
  on the attacking unit.  This remap requires spatial coordinate translation and
  must be validated explicitly.

Acceptance criteria:
- [ ] Adapter runs to completion with zero dropped samples (or documented drop reason)
- [ ] `remap_to_noop_count` for attack-target remap is within acceptable threshold
- [ ] `conversion_report.json` shows `semantic_weakening_share == 0.0` or explained
- [ ] Output branch sizes confirmed as `[6,4,4,4,4,7,49]`

---

### Stage 7 — v2 validation and BC-ready packaging

**Entry point**: validate + package scripts (to be migrated from `python/week5_teacher/`)

Tasks:
- Validate adapted dataset:
  - `EXPECTED_ACTION_BRANCH_SIZES = (6,4,4,4,4,7,49)` (migration item from v1)
  - Action range checks, obs shape checks
- Build BC-ready package:
  - `EXPECTED_BRANCH_SIZES = (6,4,4,4,4,7,49)` (migration item from v1)
  - Write to `teacher_exports_bc/{run_id}/`
- Write `reports/stage7_bc_ready.json`

Known migration items (from LEGACY032_STAGE0_AUDIT.md):
- `validate_adapted_dataset.py` — `EXPECTED_ACTION_BRANCH_SIZES` hardcoded to v1;
  must be updated or replaced before Stage 7
- `build_bc_ready_dataset_day6.py` — `EXPECTED_BRANCH_SIZES` hardcoded to v1;
  must be updated or replaced before Stage 7

Acceptance criteria:
- [ ] Validation report: zero contract violations
- [ ] BC package written with correct branch sizes `[6,4,4,4,4,7,49]`
- [ ] `reports/stage7_bc_ready.json` written
- [ ] Package is usable by student BC training loop

---

## Known risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Attack-target remap (global 576 → local 49) may drop most attack samples | High | Design adapter to handle spatial translation; accept partial drop with documentation |
| numpy fallback (`1.25.2` instead of `1.21.6`) may affect obs reproducibility | Medium | Stage 1 probe records exact numpy version; compare with paper baseline |
| v0.6.1 / 0.3.2 obs channel layout differences for some map configurations | Medium | Stage 1 probe confirms 27-channel layout explicitly |
| `validate_adapted_dataset.py` and `build_bc_ready_dataset_day6.py` have hardcoded v1 contract | High | Do not use these scripts until migrated to v2 constant (Stage 7 migration item) |
| Direct weight transfer assumption | High | Not a goal of this pipeline; explicitly excluded from scope |
| Artifact mixing with v0.6.1 outputs | High | All outputs namespaced to `python/week5_teacher_legacy032/` subdirectories |
