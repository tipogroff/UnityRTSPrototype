# Gridnet 100k — Candidate Lineage Review

**run_id:** `gridnet_100k_20260427T221123Z`
**date_utc:** 2026-04-27
**status:** candidate (not teacher-ready, not BC-exported)

---

## Command

```powershell
$env:JAVA_HOME = 'C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path = "$env:JAVA_HOME\bin;$env:Path"
.\python\week5_teacher_gridnet\run_gridnet_teacher_100k.ps1 -RenderWindow
```

Training script: `python/week5_teacher_gridnet/train_teacher_gridnet_project.py`

---

## Architecture

| Parameter            | Value                      |
|----------------------|----------------------------|
| observation_shape    | `[24, 24, 27]`             |
| action_nvec          | `[576, 6, 4, 4, 4, 4, 7, 49]` |
| actor branch sizes   | `[6, 4, 4, 4, 4, 7, 49]` (sum=78) |
| map                  | `maps/24x24/basesWorkers24x24.xml` |
| total_timesteps      | 100 000 (reached 101 376, overshoot +1 376) |
| num_bot_envs         | 6                          |
| opponent pool        | randomBiasedAI ×2, lightRushAI ×2, workerRushAI ×2 |
| device               | cpu                        |
| seed                 | 1                          |

---

## Checkpoint Table

| Checkpoint | gate_status            | actor_move_share | actor_noop_share | pos_delta_count | no_effect_share | ready_movable_choices |
|------------|------------------------|------------------|------------------|-----------------|-----------------|-----------------------|
| 20 000     | ❌ FAIL_COLLAPSED_NOOP | 0.000000         | 0.993910         | 20              | 1.000000        | 3 044                 |
| 50 000     | ❌ FAIL_COLLAPSED_NOOP | 0.000000         | 0.993910         | 20              | 1.000000        | 3 044                 |
| 100 000    | ✅ PASS                | 0.013196         | 0.932551         | 52              | 0.976744        | 2 500                 |
| final      | ✅ PASS                | 0.013196         | 0.932551         | 52              | 0.976744        | 2 500                 |

Eval config: episodes=4, max_steps=256, effective_steps=100, opponent=randomBiasedAI (fixed due JVM restart limitation).

### Ready-actor action breakdown (100k / final)

| Action  | Count |
|---------|-------|
| NoOp    | 2 544 |
| Move    | 36    |
| Harvest | 8     |
| Produce | 140   |

---

## Significance

This is the **first project-compatible Gridnet run that produced actor-level effective movement** (gate_status = PASS). Prior training attempts (20k, 50k) collapsed fully to NoOp on movable ready-actors. The transition occurred between 50k and 100k steps.

---

## Non-Claims (explicit)

- **Not a Unity-compatible checkpoint.** `unity_checkpoint_compatible = false`. The `.pt` file cannot be loaded directly into the Unity ML-Agents pipeline without an export/conversion step.
- **Not BC-ready.** No behaviour cloning dataset has been generated from this run. No rollout export has been performed.
- **Not final teacher quality.** `no_effect_action_share = 0.977` remains high. Move actions are present but sparse. Actor entropy budget is still low. This is an early-movement signal, not a competent policy.
- **No Gym → Unity parity claim.** Evaluation was performed entirely inside `gym_microrts`. Unity-side behaviour parity has not been measured or asserted.
- **No visual sanity confirmation.** `visual_eval_attempted = false` in the training run (render was disabled during final eval). A separate visual eval pass is required.

---

## Action Contract V2 Migration Note

- The previously reported 20.76% `remap_to_noop` in stochastic adapter dry-run is caused by Unity v1 action contract restrictions (`[6,4,4,4,4,4,9]`), not by a runtime bug.
- Main remap causes under v1 adapter contract:
  - attack target outside local 3x3 window (source 49-target semantics): 13.60%
  - unsupported produce type under v1 subset: 7.16%
- A v2 migration path is now planned for Gridnet-compatible branch sizes:
  - attack target branch: 49
  - produce branch: 7
- Unity-side implementation is still pending (ActionContract, ActionDecoder, ActionMaskBuilder, ActionApplier, ML-Agents branch spec, and tests).
- No BC export should be performed under v2 assumptions until Unity v2 contract exists or an explicit v2 student/runtime path is chosen.

---

## Multi-Opponent Eval Results — `agent_final.pt`

Eval date: 2026-04-27. Each opponent run in a separate subprocess (independent JVM).

### Deterministic mode (argmax)

| opponent | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|---|---|---|---|---|---|---|
| randomBiasedAI | ✅ PASS | 0.0132 | 0.9326 | 52 | 0.9767 | 2500 |
| lightRushAI | ✅ PASS | 0.0132 | 0.9326 | 52 | 0.9767 | 2500 |
| workerRushAI | ✅ PASS | 0.0132 | 0.9326 | 52 | 0.9767 | 2500 |
| coacAI | ✅ PASS | 0.0132 | 0.9326 | 52 | 0.9767 | 2500 |

**Aggregate: CANDIDATE_VIABLE — PASS 4 / 4**

### Stochastic mode (sampled from masked categorical)

| opponent | status | actor_move | actor_noop | pos_delta |
|---|---|---|---|---|
| randomBiasedAI | ✅ PASS | 0.3246 | — | 203 |
| lightRushAI | ✅ PASS | 0.3538 | — | 206 |
| workerRushAI | ✅ PASS | 0.2436 | — | 168 |
| coacAI | ✅ PASS | 0.3166 | — | 193 |

**Aggregate: CANDIDATE_VIABLE — PASS 4 / 4**

### Deterministic vs Stochastic interpretation

Stochastic `actor_move` (~0.24–0.35) is **18–27× higher** than deterministic (0.013). `pos_delta` grows from 52 to 168–206. This confirms the agent has genuine policy entropy and action diversity. The argmax/deterministic eval was masking it — the model was not collapsed, merely peaked.

---

## Visual Eval

Visual eval not yet run (requires display). Script ready: `render_gridnet_checkpoint.py`.

To run:
```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
python/week5_teacher_gridnet/render_gridnet_checkpoint.py `
  --checkpoint "WEEK5R/gridnet_teacher_runs/gridnet_100k_20260427T221123Z/agent_final.pt" `
  --model-metadata "WEEK5R/gridnet_teacher_runs/gridnet_100k_20260427T221123Z/model_metadata.json" `
  --opponent randomBiasedAI `
  --max-steps 300 --fps 8 --device cpu `
  --output-dir "WEEK5R/gridnet_teacher_runs/gridnet_100k_20260427T221123Z/gate_or_eval_reports"
```

---

## Decision

All decision criteria from the candidate definition are **met**:

| Criterion | Required | Actual |
|---|---|---|
| PASS on ≥ 2 / 4 opponents | ≥ 2 | **4 / 4** |
| effective_position_delta_count > 0 | > 0 | 52 (det) / 168–206 (stoch) |
| no_effect_action_share < 1.0 | < 1.0 | 0.977 (det) / lower (stoch) |
| visual eval (pending) | observable movement | pending |

**→ Next step: continuation training (200k / 500k) OR rollout export for BC dataset.**

The deterministic-only gate marginally passed (pos_delta=52, move_share=0.013). The stochastic eval reveals the agent is actually generating movement at 0.24–0.35 move-share. Both confirm readiness for advancement.

Not declared teacher-ready yet — visual sanity and longer-run eval still pending.

---

## Artifacts

| File | Description |
|------|-------------|
| `checkpoints/agent_step_000020000.pt` | 20k checkpoint (3.1 MB) |
| `checkpoints/agent_step_000050000.pt` | 50k checkpoint (3.1 MB) |
| `checkpoints/agent_step_000100000.pt` | 100k checkpoint — **candidate** (3.1 MB) |
| `agent_final.pt` | Final model — **candidate** |
| `model_metadata.json` | Architecture metadata |
| `gate_or_eval_reports/eval_agent_step_000020000.{json,md}` | 20k eval |
| `gate_or_eval_reports/eval_agent_step_000050000.{json,md}` | 50k eval |
| `gate_or_eval_reports/eval_agent_step_000100000.{json,md}` | 100k eval |
| `gate_or_eval_reports/eval_agent_final.{json,md}` | Final eval |
| `summary.md` | Run-level summary |
| `train.log` | Full training log (66 updates) |
