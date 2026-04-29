# Legacy032 Teacher Training Plan

**Status**: Stage 3 PARTIAL — PASS_WITH_WARNINGS (Stage 3A 100k sanity completed)  
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

**Entry point**: `scripts/train_teacher_legacy032.py`

**Stage 2 result**: COMPLETE — PASS

Stage 2 reports:

- `reports/STAGE2_REFERENCE_SCRIPT_AUDIT.md`
- `reports/stage2_smoke_training_20260429T113844Z.json`
- `reports/stage2_smoke_training_20260429T113844Z.md`
- `reports/STAGE2_SMOKE_TRAINING_REPORT.md`
- `reports/STAGE2_COMPLETION_REPORT.md`

Tasks:
- Short PPO run (≤10k steps) to confirm training loop works
- Checkpoint saved to `teacher_models/smoke/`
- Training log saved to `teacher_logs/smoke/`

Observed Stage 2 artifacts:

- run_id: `legacy032_smoke_20260429T113844Z`
- checkpoint: `teacher_models/legacy032_smoke_20260429T113844Z/agent_final.pt`
- logs: `teacher_logs/legacy032_smoke_20260429T113844Z/`

Mask path details (Stage 2 finding):

- mask path confirmed in reference training code via `envs.vec_client.getMasks(0)`;
- masks are applied in `CategoricalMasked` using `torch.where(...)` before sampling;
- this explains why Stage 1 probe APIs did not expose mask directly.

Acceptance criteria:
- [x] Training completes without crash
- [x] At least one checkpoint written
- [x] Loss / reward metrics logged

Stage 3 dependency note:

- Stage 3 can start from the Stage 2 smoke checkpoint;
- Stage 3 decision status from Stage 2 run: `READY_FOR_STAGE3_BEHAVIOR_GATE`.

---

### Stage 3 — Staged teacher training with behavior gates

**Entry points**:

- `scripts/evaluate_teacher_legacy032.py`
- `scripts/run_staged_teacher_training_legacy032.py`

**Stage 3 status**: PARTIAL — PASS_WITH_WARNINGS

Stage 3 reports:

- `reports/STAGE3_PRETRAINING_AUDIT.md`
- `reports/stage3_smoke_checkpoint_behavior_gate_20260429T122219Z.json`
- `reports/stage3_smoke_checkpoint_behavior_gate_20260429T122219Z.md`
- `reports/stage3_training_20260429T120524Z.json`
- `reports/stage3_training_20260429T120524Z.md`
- `reports/stage3_gate_000100000_20260429T122246Z.json`
- `reports/stage3_gate_000100000_20260429T122246Z.md`
- `reports/STAGE3_STAGED_TRAINING_REPORT.md`
- `reports/STAGE3_COMPLETION_REPORT.md`

What was completed:

- Stage 2 smoke checkpoint evaluator run completed and deferred inference warning closed.
- Stage 3A 100k sanity training completed with checkpoint artifact.
- Behavior gate completed for smoke checkpoint and 100k checkpoint.
- Action distribution recorded; mask usage confirmed in evaluation.

Known warnings:

- Checkpoints are evaluable on reference internal 16x16 env/action space.
- Direct compatibility with target preflight 24x24 env/action space remains unresolved.

Current staged plan:

- completed: `100000`
- planned: `500000, 1000000, 3000000, 5000000`
- optional: `10000000` (only if quality keeps improving)

Acceptance criteria:

- [x] Evaluation runs without crash
- [x] `action_type_distribution` recorded
- [x] Behavior gate decision written
- [x] At least one staged checkpoint created (100k)
- [x] Stage 2 deferred inference warning closed
- [ ] Stage 3 long stages (500k+) still pending

Stage note:

- Stage 3A 100k sanity completed; longer stages remain planned.

---

### Stage 4 — Long-horizon staged continuation

**Entry point**: `scripts/run_staged_teacher_training_legacy032.py`

Tasks:

- Continue staged checkpoints at 500k, 1M, 3M, and 5M.
- Run behavior gates after each checkpoint.
- Select best checkpoint by gate + behavior metrics.

Acceptance criteria:

- [ ] 500k/1M/3M/5M checkpoints completed or explicitly failed with reports
- [ ] Comparative checkpoint table updated with gate outcomes
- [ ] Best candidate selected for downstream export stage

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
