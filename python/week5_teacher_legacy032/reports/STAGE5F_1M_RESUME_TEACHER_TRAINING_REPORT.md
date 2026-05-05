# STAGE5F — 1M Canonical Post-Resume Teacher Training Report

**Classification:** `STAGE5F_1M_COMPLETE_WITH_BEHAVIOR_WARNINGS`

**Recommendation:** `STOP_AT_1M_FOR_REVIEW`

**Generated:** 2026-05-05  
**Run ID:** `legacy032_24x24_teacher_resume_1m_20260504T231107Z`  
**Run Label:** `legacy032_24x24_teacher_resume_1m`  
**Source JSON:** `reports/stage5_24x24_training_20260504T231107Z.json`

---

## Run Identity

This is the **first canonical post-resume teacher run** for the Legacy032 24×24 MicroRTS agent.  
It exercises the full local checkpoint/resume infrastructure introduced in Stage5E, running three
cumulative continuation stages:

| Stage | Cumulative Target | global_step range |
|-------|-------------------|-------------------|
| Stage 1 | 100 000 | 0 → 99 840 |
| Stage 2 | 500 000 | 99 840 → 499 200 |
| Stage 3 | 1 000 000 | 499 200 → 999 936 |

**Semantic model:**  
Each stage resumes from the previous stage's full training checkpoint.  
`schedule_total_timesteps = 3 000 000` across all stages (LR annealing is anchored to the 3M horizon).  
The 1M checkpoint is an **intermediate candidate**, not a final policy.

---

## Preflight Contract Check

| Field | Value |
|-------|-------|
| Status | PASS |
| obs shape | [24, 24, 27] |
| action nvec | [576, 6, 4, 4, 4, 4, 7, 49] |
| contract_gridmode_matches_expected | true |
| mask_available | true |
| mask_source | env.vec_client.getMasks(0) |
| policy_forward_ok | true |
| env_step_ok | true |

---

## Per-Stage Evidence

### Stage 1 — 100k (STARTED_FROM_SCRATCH)

| Field | Value |
|-------|-------|
| training_exit_code | 0 |
| training_status | PASS |
| RESUME_STATUS | STARTED_FROM_SCRATCH |
| CHECKPOINT_STATUS | FULL_CHECKPOINT_SAVED |
| global_step_start | 0 |
| global_step_end | 99 840 |
| target_total_timesteps | 100 000 |
| schedule_total_timesteps | 3 000 000 |
| resumed_from_checkpoint | — (scratch start) |
| optimizer_state_restored | false (n/a — scratch) |
| rng_state_restored | false (n/a — scratch) |
| strict_agent_load | false (n/a — scratch) |
| checkpoint_saved | true |
| full_checkpoint_saved | true |
| metadata_contract_ok | true |
| architecture_name | legacy032_resolution_aware_gridnet_v1 |
| training_duration | 1 737.9 s (~29 min) |
| episode_count (training) | 52 |
| mean_episode_reward (training) | 67.72 |

**Gate — 100k**

| Field | Value |
|-------|-------|
| gate_exit_code | 0 |
| gate_decision | PASS |
| env_matches_target_24x24 | true |
| mask_used_during_eval | true |
| checkpoint_load_ok | true |
| policy_architecture_load_ok | true |
| inference_ok | true |
| eval_observation_shape | [24, 24, 27] |
| eval_action_space | [576, 6, 4, 4, 4, 4, 7, 49] |
| mean_return (gate) | **-10.0** ⚠ |
| noop_share | 16.65% |
| effective_activity_share | 83.35% |
| policy_entropy_proxy | 0.000990 |
| warnings | none |
| errors | none |

---

### Stage 2 — 500k (RESUMED_FROM_FULL_CHECKPOINT)

| Field | Value |
|-------|-------|
| training_exit_code | 0 |
| training_status | PASS |
| RESUME_STATUS | **RESUMED_FROM_FULL_CHECKPOINT** ✓ |
| CHECKPOINT_STATUS | FULL_CHECKPOINT_SAVED |
| global_step_start | 99 840 |
| global_step_end | 499 200 |
| target_total_timesteps | 500 000 |
| schedule_total_timesteps | 3 000 000 |
| resumed_from_checkpoint | stage_000100000/trainer_state_final.pt |
| optimizer_state_restored | **true** ✓ |
| rng_state_restored | **true** ✓ |
| strict_agent_load | **true** ✓ |
| checkpoint_saved | true |
| full_checkpoint_saved | true |
| metadata_contract_ok | true |
| architecture_name | legacy032_resolution_aware_gridnet_v1 |
| training_duration | 5 988.1 s (~99.8 min) |
| episode_count (training) | 151 |
| mean_episode_reward (training) | 117.29 |

**Gate — 500k**

| Field | Value |
|-------|-------|
| gate_exit_code | 0 |
| gate_decision | PASS |
| env_matches_target_24x24 | true |
| mask_used_during_eval | true |
| checkpoint_load_ok | true |
| policy_architecture_load_ok | true |
| inference_ok | true |
| eval_observation_shape | [24, 24, 27] |
| eval_action_space | [576, 6, 4, 4, 4, 4, 7, 49] |
| mean_return (gate) | **-10.0** ⚠ |
| noop_share | 16.63% |
| effective_activity_share | 83.37% |
| policy_entropy_proxy | 0.000265 |
| warnings | none |
| errors | none |

---

### Stage 3 — 1M (RESUMED_FROM_FULL_CHECKPOINT)

| Field | Value |
|-------|-------|
| training_exit_code | 0 |
| training_status | PASS |
| RESUME_STATUS | **RESUMED_FROM_FULL_CHECKPOINT** ✓ |
| CHECKPOINT_STATUS | FULL_CHECKPOINT_SAVED |
| global_step_start | 499 200 |
| global_step_end | 999 936 |
| target_total_timesteps | 1 000 000 |
| schedule_total_timesteps | 3 000 000 |
| resumed_from_checkpoint | stage_000500000/trainer_state_final.pt |
| optimizer_state_restored | **true** ✓ |
| rng_state_restored | **true** ✓ |
| strict_agent_load | **true** ✓ |
| checkpoint_saved | true |
| full_checkpoint_saved | true |
| metadata_contract_ok | true |
| architecture_name | legacy032_resolution_aware_gridnet_v1 |
| training_duration | 8 444.5 s (~140.7 min) |
| episode_count (training) | 164 |
| mean_episode_reward (training) | 171.83 |

**Gate — 1M**

| Field | Value |
|-------|-------|
| gate_exit_code | 0 |
| gate_decision | PASS |
| env_matches_target_24x24 | true |
| mask_used_during_eval | true |
| checkpoint_load_ok | true |
| policy_architecture_load_ok | true |
| inference_ok | true |
| eval_observation_shape | [24, 24, 27] |
| eval_action_space | [576, 6, 4, 4, 4, 4, 7, 49] |
| mean_return (gate) | **-10.0** ⚠ |
| noop_share | 16.62% |
| effective_activity_share | 83.38% |
| policy_entropy_proxy | 0.000206 |
| warnings | none |
| errors | none |

---

## Resume Chain Verification

| Check | Result |
|-------|--------|
| Stage 1 scratch (no fallback) | ✓ STARTED_FROM_SCRATCH |
| Stage 2 resumed from stage 1 full checkpoint | ✓ RESUMED_FROM_FULL_CHECKPOINT |
| Stage 3 resumed from stage 2 full checkpoint | ✓ RESUMED_FROM_FULL_CHECKPOINT |
| optimizer_state_restored stages 2+3 | ✓ true |
| rng_state_restored stages 2+3 | ✓ true |
| strict_agent_load stages 2+3 | ✓ true |
| No scratch fallback in stages 2+3 | ✓ confirmed |
| local_resume_mode=required enforced | ✓ confirmed |

---

## Training Progress Trend

| Stage | mean_episode_reward | gate mean_return | policy_entropy_proxy | noop_share |
|-------|---------------------|------------------|----------------------|------------|
| 100k | 67.72 | -10.0 | 0.000990 | 16.65% |
| 500k | 117.29 | -10.0 | 0.000265 | 16.63% |
| 1M | 171.83 | -10.0 | 0.000206 | 16.62% |

**Positive signals:**
- Training `mean_episode_reward` shows consistent upward trajectory: +73% gain from 100k to 1M.
- Policy entropy decreasing (0.000990 → 0.000206): policy is concentrating, becoming more deterministic.
- No training errors or warnings at any stage.

---

## Behavior Warnings

### ⚠ W1: Gate `mean_return = -10.0` at all three stages

The gate evaluator reports `mean_return = -10.0` across all 8 episodes at each of the three
checkpoints (100k, 500k, 1M). This value corresponds to the loss penalty in the MicroRTS reward
function, indicating that the agent did not win any evaluation episodes at any checkpoint.

This is not necessarily a terminal failure — the gate criteria are satisfied by passing structural
and contract checks, and training `mean_episode_reward` is clearly improving. However, zero wins
in 24 total evaluation episodes (8 × 3 stages) is a behavior flag.

**Likely causes:**
1. Evaluations run for only 6 000 steps max, which may be insufficient to reach a decisive game
   outcome on 24×24 against the built-in AI.
2. The gate opponent AI may require significantly more than 1M timesteps of training to defeat.
3. The dense reward signal driving training improvement (67 → 171) is composite and includes
   non-win components (harvest, produce, etc.); the -10 terminal return may be a sparse signal
   that only fires at actual loss.

### ⚠ W2: Near-uniform action type distribution at gate

All six action types hold ~16.6% share across all stages, including after 1M steps of training.
In a well-trained gridnet policy, one would expect some action types to dominate in the early
game (harvest, produce) relative to others (attack). A fully uniform distribution may indicate
the gate evaluation episodes are too short for the policy to develop game-specific sequences, or
that aggregating across 576 cells flattens the signal.

---

## Artifacts

### Stage 1 — 100k
- `teacher_models/.../stage_000100000/agent_final.pt`
- `teacher_models/.../stage_000100000/trainer_state_final.pt`
- `teacher_models/.../stage_000100000/model_metadata.json`
- `teacher_models/.../stage_000100000/latest_trainer_state.json`
- `reports/stage5_gate_000100000_20260504T234007Z.json`
- `reports/stage5_gate_000100000_20260504T234007Z.md`

### Stage 2 — 500k
- `teacher_models/.../stage_000500000/agent_final.pt`
- `teacher_models/.../stage_000500000/trainer_state_final.pt`
- `teacher_models/.../stage_000500000/model_metadata.json`
- `teacher_models/.../stage_000500000/latest_trainer_state.json`
- `reports/stage5_gate_000500000_20260505T012116Z.json`
- `reports/stage5_gate_000500000_20260505T012116Z.md`

### Stage 3 — 1M
- `teacher_models/.../stage_001000000/agent_final.pt`
- `teacher_models/.../stage_001000000/trainer_state_final.pt`
- `teacher_models/.../stage_001000000/model_metadata.json`
- `teacher_models/.../stage_001000000/latest_trainer_state.json`
- `reports/stage5_gate_001000000_20260505T034329Z.json`
- `reports/stage5_gate_001000000_20260505T034329Z.md`

---

## Classification and Recommendation

**Classification:** `STAGE5F_1M_COMPLETE_WITH_BEHAVIOR_WARNINGS`

All three stages completed with exit code 0. The full resume chain was exercised without any
scratch fallback. All gate structural checks pass. Two behavior warnings are registered (W1, W2)
related to zero gate wins and uniform action type distribution.

**Recommendation:** `STOP_AT_1M_FOR_REVIEW`

Before extending the run to 2M or 3M, the following review items should be addressed:

1. **Win-rate audit:** Run a dedicated evaluation with longer episode limits (e.g., 12 000 steps)
   or more episodes (e.g., 32) against the built-in AI to determine actual win rate at the 1M
   checkpoint. If win rate is 0% at 12k steps, the agent may not yet have crossed the behavioral
   threshold required for downstream BC data collection.

2. **Reward decomposition:** Examine whether the -10.0 gate return is the MicroRTS loss penalty
   or a different shaped signal. Confirm whether training rewards (67 → 171) reflect dense
   intermediate rewards (resource, unit production) rather than game wins.

3. **Decision point:** If win-rate audit shows ≥ 10% wins at 12k steps, proceed to 2M with the
   1M full checkpoint as the resume base. If 0%, evaluate whether to adjust the opponent,
   extend training episodes, or revisit reward shaping before committing to 2M→3M.

---

*Report generated by agent post-run analysis. Source: `stage5_24x24_training_20260504T231107Z.json`.*
