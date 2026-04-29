# Legacy032 Teacher Training Plan

**Status**: Stage 4R PASS — READY_FOR_24X24_100K_TRAINING  
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

### Legacy gym.make / global single-action mode

```python
global_single_action_24x24_nvec = [576, 6, 4, 4, 4, 4, 7, 576]
```

### Legacy MicroRTSGridModeVecEnv / teacher training mode

```python
gridmode_24x24_nvec = [576, 6, 4, 4, 4, 4, 7, 49]
gridmode_per_cell_branch_sizes = [6, 4, 4, 4, 4, 7, 49]
```

### Unity v2 target

```python
unity_v2_branch_sizes = [6, 4, 4, 4, 4, 7, 49]
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
- Confirm mode-specific nvec:
  - global single-action reference: `[576,6,4,4,4,4,7,576]`
  - GridMode teacher path: `[576,6,4,4,4,4,7,49]`
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

Important interpretation for Stage 3 artifacts:

- Stage 3 16x16 checkpoints are reference-internal proof artifacts only.
- They must not be treated as 24x24-aligned teacher checkpoints for Unity transfer decisions.

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

### Stage 4 — 24x24 training/evaluation alignment (original)

**Entry points**:

- `scripts/ppo_gridnet_legacy032_24x24_local_save.py`
- `scripts/verify_legacy032_24x24_training_contract.py`
- `scripts/train_teacher_legacy032_24x24.py`
- `scripts/evaluate_teacher_legacy032.py` (`--env-mode target_24x24_gridmode`)

Tasks:

- Audit reference script for 16x16 hardcoded assumptions.
- Patch training path in legacy032 workspace only.
- Verify 24x24 contract/mask/policy-forward before training.
- Run short 10k smoke training only if contract probe PASS.
- Evaluate smoke checkpoint in target 24x24 gridmode.

Current Stage 4 result (2026-04-29, superseded by Stage 4R):

- Contract probe status: `BLOCKED_CONTRACT_MISMATCH` (superseded)
- Confirmed observation in gridmode env: `[24,24,27]`
- Confirmed action nvec in gridmode env: `[576,6,4,4,4,4,7,49]` (not `[576,6,4,4,4,4,7,576]`)
- Mask path available via `env.vec_client.getMasks(0)`
- Policy masked sampling failed under current reference encoder/decoder topology due shape mismatch
- 10k smoke training not started (blocked by contract probe)

Correction note:

- Stage 4 original `BLOCKED_CONTRACT_MISMATCH` classification was superseded by Stage 4R.
- Root cause of Stage 4 contract block was incorrect expected contract for GridMode.

### Stage 4R — GridMode contract correction + architecture fix

**Entry points**:

- `scripts/verify_legacy032_24x24_training_contract.py`
- `scripts/ppo_gridnet_legacy032_24x24_local_save.py`
- `scripts/train_teacher_legacy032_24x24.py`
- `scripts/evaluate_teacher_legacy032.py` (`--env-mode target_24x24_gridmode`)

Stage 4R corrections:

- Correct GridMode expected nvec for 24x24: `[576,6,4,4,4,4,7,49]`.
- Preserve global single-action 24x24 contract `[576,6,4,4,4,4,7,576]` as separate reference mode only.
- Implement resolution-aware actor head so actor output HxW matches env HxW on 24x24.

Stage 4R result (2026-04-29):

- contract probe: `PASS`
- 10k smoke training: `PASS`
- checkpoint saved: yes
- behavior gate in `target_24x24_gridmode`: `PASS`
- env_matches_target_24x24: true
- mask_used_during_eval: true

Stage 4R decision:

- `READY_FOR_24X24_100K_TRAINING`

Acceptance criteria:

- [x] Stage 4 audit created
- [x] 24x24 patched script created in legacy032 workspace
- [x] 24x24 contract probe script created and executed
- [x] evaluator updated with `target_24x24_gridmode`
- [x] contract probe PASS
- [x] 10k smoke training completed
- [x] 24x24 smoke checkpoint evaluated by behavior gate

Stage gate status:

- Historical gate was: do not run 500k/1M/3M/5M until Stage 4 24x24 alignment is resolved.
- Current state: resolved in Stage 4R (`READY_FOR_24X24_100K_TRAINING`).

---

### Stage 5 — 24x24 staged teacher training

**Entry point**: corrected 24x24 GridMode training path rooted in Stage 4R trainer artifacts

Primary trainer/runtime path:

- `scripts/ppo_gridnet_legacy032_24x24_local_save.py`
- `scripts/run_24x24_staged_teacher_training_legacy032.py`
- architecture_name: `legacy032_resolution_aware_gridnet_v1`

Stage 5A result (2026-04-29):

- status: `PASS`
- decision: `READY_FOR_500K`
- run_id: `legacy032_24x24_teacher_main_20260429T162331Z`
- preflight report: `reports/stage5a_24x24_contract_probe.json` (`PASS`)
- training report: `reports/stage5_24x24_training_20260429T162331Z.json`
- checkpoint path: `teacher_models/legacy032_24x24_teacher_main_20260429T162331Z/stage_000100000/agent_final.pt`
- metadata path: `teacher_models/legacy032_24x24_teacher_main_20260429T162331Z/stage_000100000/model_metadata.json`
- gate report: `reports/stage5_gate_000100000_20260429T164521Z.json` (`PASS`)
- gate checks: `env_matches_target_24x24=true`, `mask_used_during_eval=true`, `inference_ok=true`, action distribution recorded, `effective_activity_share=0.8336504744224422`

Stage 5A acceptance checklist:

- [x] stage5a_24x24_contract_probe.json exists and PASS
- [x] run_24x24_staged_teacher_training_legacy032.py exists
- [x] 100k training run executed
- [x] checkpoint + metadata saved
- [x] behavior gate executed in `target_24x24_gridmode`
- [x] STAGE5A_100K_TRAINING_REPORT.md exists
- [x] STAGE5A_COMPLETION_REPORT.md exists

Recommendation:

- Stage 5B 500k is allowed after explicit approval, using the same corrected 24x24 pipeline only.
- Future checkpoints (500k/1M/3M/5M) remain planned and are not marked complete.

Stage 5B result (2026-04-29):

- status: `PASS_WITH_WARNINGS`
- decision: `READY_FOR_1M_WITH_WARNINGS`
- run_id: `legacy032_24x24_teacher_main_20260429T171506Z`
- preflight report: `reports/stage5b_24x24_contract_probe.json` (`PASS`)
- machine report: `reports/stage5_24x24_training_20260429T171506Z.json`
- checkpoint path: `teacher_models/legacy032_24x24_teacher_main_20260429T171506Z/stage_000500000/agent_final.pt`
- metadata path: `teacher_models/legacy032_24x24_teacher_main_20260429T171506Z/stage_000500000/model_metadata.json`
- gate report: `reports/stage5_gate_000500000_20260429T190313Z.json` (`PASS`)
- comparison report: `reports/STAGE5_100K_VS_500K_COMPARISON.md`
- baseline used: `legacy032_24x24_teacher_main_20260429T162331Z / stage_000100000`
- run interpretation: `500k is a from-scratch staged checkpoint with larger total_timesteps, not a resumed continuation from 100k.`

Stage 5B acceptance checklist:

- [x] stage5b_24x24_contract_probe.json exists and PASS
- [x] 500k training run executed
- [x] checkpoint + metadata saved
- [x] behavior gate executed in `target_24x24_gridmode`
- [x] STAGE5B_500K_TRAINING_REPORT.md exists
- [x] STAGE5B_COMPLETION_REPORT.md exists
- [x] STAGE5_100K_VS_500K_COMPARISON.md exists

Stage 5B recommendation:

- Technical compatibility remains stable (`env_matches_target_24x24=true`, `mask_used_during_eval=true`, inference/load checks true).
- Behavior quality did not materially improve versus 100k (stochastic and deterministic mean returns unchanged; deterministic noop share remains very high).
- Proceed to 1M only with warnings and mandatory follow-up diagnostics if signs of deterministic collapse persist.

Planned checkpoints:

- `100000`, `500000`, `1000000`, `3000000`, `5000000`

Rule:

- Use corrected Stage 4R path only.
- Do not use 16x16 reference-internal path for transfer-readiness decisions.

---

### Stage 6 — Raw rollout export

**Entry point**: `scripts/export_teacher_rollout_legacy032.py` (to be created)

Tasks:
- Run trained teacher for N episodes (target: ≥200 episodes)
- Export per-episode: observations, raw actions, rewards, dones
- Save to `teacher_rollouts/` (namespaced by run timestamp)
- Record rollout summary: episode count, mean return, action distribution

Contract note for corrected GridMode exports:

- For corrected 24x24 GridMode path, attack branch is already local 7×7 (`49`).

Acceptance criteria:
- [ ] Rollout export completes
- [ ] `teacher_rollouts/{run_id}/rollout_summary.json` written
- [ ] Observations are 27-channel, shape `[T, 24, 24, 27]`
- [ ] Raw actions recorded with GridMode contract `[576,6,4,4,4,4,7,49]` for corrected Stage 4R path

---

### Stage 7 — Adapter to Unity v2

**Entry point**: `scripts/adapt_legacy032_to_unity_v2.py` (to be created)

Tasks:
- Call `adapt_teacher_dataset.py` with `--target-action-contract v2_gridnet_compatible`
  (or a dedicated 0.3.2-aware adapter if needed)
- If trajectories are exported from corrected 24x24 GridMode path, keep local 7×7 attack branch (`49`) unchanged.
- Global `576` → local `49` attack-target remap is needed only for trajectories exported from gym.make/global single-action mode.
- Always verify actor-cell alignment, branch ranges, inactive branches, masks, and Unity v2 tensor layout.
- Record conversion report in `teacher_exports/{run_id}/conversion_report.json`

Known risk:
- For corrected GridMode exports, attack branch is already local 7×7 (`49`).
- For gym.make/global single-action exports, attack is global flat `576` and requires explicit spatial remap to local 7×7 (`49`).

Acceptance criteria:
- [ ] Adapter runs to completion with zero dropped samples (or documented drop reason)
- [ ] `remap_to_noop_count` for attack-target remap is within acceptable threshold
- [ ] `conversion_report.json` shows `semantic_weakening_share == 0.0` or explained
- [ ] Output branch sizes confirmed as `[6,4,4,4,4,7,49]`

---

### Stage 8 — v2 validation and BC-ready packaging

**Entry point**: validate + package scripts (to be migrated from `python/week5_teacher/`)

Tasks:
- Validate adapted dataset:
  - `EXPECTED_ACTION_BRANCH_SIZES = (6,4,4,4,4,7,49)` (migration item from v1)
  - Action range checks, obs shape checks
- Build BC-ready package:
  - `EXPECTED_BRANCH_SIZES = (6,4,4,4,4,7,49)` (migration item from v1)
  - Write to `teacher_exports_bc/{run_id}/`
- Write `reports/stage8_bc_ready.json`

Known migration items (from LEGACY032_STAGE0_AUDIT.md):
- `validate_adapted_dataset.py` — `EXPECTED_ACTION_BRANCH_SIZES` hardcoded to v1;
  must be updated or replaced before Stage 8
- `build_bc_ready_dataset_day6.py` — `EXPECTED_BRANCH_SIZES` hardcoded to v1;
  must be updated or replaced before Stage 8

Acceptance criteria:
- [ ] Validation report: zero contract violations
- [ ] BC package written with correct branch sizes `[6,4,4,4,4,7,49]`
- [ ] `reports/stage8_bc_ready.json` written
- [ ] Package is usable by student BC training loop

---

## Known risks

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Attack-target remap (global 576 → local 49) may drop attack samples for gym.make/global-single exports | High | Prefer corrected GridMode export path where attack branch is already local 49; remap only when source mode is global single-action |
| numpy fallback (`1.25.2` instead of `1.21.6`) may affect obs reproducibility | Medium | Stage 1 probe records exact numpy version; compare with paper baseline |
| v0.6.1 / 0.3.2 obs channel layout differences for some map configurations | Medium | Stage 1 probe confirms 27-channel layout explicitly |
| `validate_adapted_dataset.py` and `build_bc_ready_dataset_day6.py` have hardcoded v1 contract | High | Do not use these scripts until migrated to v2 constant (Stage 8 migration item) |
| Direct weight transfer assumption | High | Not a goal of this pipeline; explicitly excluded from scope |
| Artifact mixing with v0.6.1 outputs | High | All outputs namespaced to `python/week5_teacher_legacy032/` subdirectories |

## Long-run gating policy

- Future long training must use the 24x24-aligned Stage 4 path once Stage 4 passes.
- 16x16 reference-internal path can be used only for historical comparison/debug, not for transfer-readiness claims.
- Stage 4 original remains historical/superseded; Stage 4R is the active baseline for Stage 5+.
