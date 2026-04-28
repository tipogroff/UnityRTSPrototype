# GRIDNET FRESH 100K v2 Effectiveness Review

Run id: gridnet_fresh_100k_v2_20260428T191104Z  
Date: 2026-04-28  
Scope: training effectiveness only (no BC packaging, no student retraining, no Unity import, no runtime changes, no parity claim)

## 1. Training provenance

- Trainer: python/week5_teacher_gridnet/train_teacher_gridnet_project.py
- Launch script: python/week5_teacher_gridnet/run_gridnet_teacher_fresh_100k_v2.ps1
- Fresh-start guarantee:
  - resume_from_checkpoint = none
  - resume_model_metadata = none
  - initial_global_step = 0
- Config:
  - total_timesteps = 100000 (reached global_step=101376)
  - checkpoint_steps = 20000,50000,100000
  - num_bot_envs = 6
  - num_selfplay_envs = 0
  - seed = 1
  - device = cpu
  - map = maps/24x24/basesWorkers24x24.xml

Artifacts present:
- agent_final.pt
- checkpoints/agent_step_000020000.pt
- checkpoints/agent_step_000050000.pt
- checkpoints/agent_step_000100000.pt
- model_metadata.json
- run_manifest.json
- summary.md
- train.log
- gate_or_eval_reports/

Metadata checks:
- observation_shape = [24,24,27]
- action_branch_sizes = [6,4,4,4,4,7,49]
- action_nvec = [576,6,4,4,4,4,7,49]
- initial_global_step = 0
- resume_from_checkpoint = null

## 2. Checkpoint progression

Single-opponent actor-level gate (randomBiasedAI static):

| checkpoint | gate_status | actor_move | actor_noop | pos_delta | no_effect |
|---|---|---:|---:|---:|---:|
| 20k | FAIL_COLLAPSED_NOOP | 0.0000 | 0.9939 | 20 | 1.0000 |
| 50k | FAIL_COLLAPSED_NOOP | 0.0000 | 0.9574 | 20 | 0.9706 |
| 100k | PASS | 0.0055 | 0.9436 | 36 | 0.9737 |
| final | PASS | 0.0055 | 0.9436 | 36 | 0.9737 |

Interpretation:
- Fresh run exits collapse by 100k, but deterministic movement quality remains weak.

## 3. Deterministic multi-opponent eval

Source: multiopponent_eval_agent_final_det.json

Per-opponent table:

| opponent | mode | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|---|---|---|---:|---:|---:|---:|---:|
| randomBiasedAI | deterministic | PASS | 0.0048 | 0.9445 | 36 | 0.9733 | 2876 |
| lightRushAI | deterministic | PASS | 0.0041 | 0.9454 | 36 | 0.9730 | 2884 |
| workerRushAI | deterministic | PASS | 0.0055 | 0.9436 | 36 | 0.9737 | 2864 |
| coacAI | deterministic | PASS | 0.0041 | 0.9454 | 36 | 0.9730 | 2884 |

Aggregate:
- deterministic pass_count: 4/4
- deterministic aggregate verdict: CANDIDATE_VIABLE

## 4. Stochastic multi-opponent eval

Source: multiopponent_eval_agent_final_stoch.json

Per-opponent table:

| opponent | mode | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|---|---|---|---:|---:|---:|---:|---:|
| randomBiasedAI | stochastic | PASS | 0.0941 | 0.4475 | 91 | 0.9288 | 344 |
| lightRushAI | stochastic | PASS | 0.0677 | 0.3767 | 73 | 0.9319 | 349 |
| workerRushAI | stochastic | PASS | 0.2239 | 0.3859 | 155 | 0.8903 | 599 |
| coacAI | stochastic | PASS | 0.1448 | 0.3511 | 125 | 0.8884 | 558 |

Aggregate:
- stochastic pass_count: 4/4
- stochastic aggregate verdict: CANDIDATE_VIABLE

## 5. Visual eval

Source: visual_eval_agent_final.json / visual_eval_agent_final.md

Run config:
- opponent = randomBiasedAI
- max_steps = 300
- fps = 8
- deterministic_mode = true
- visual_eval_status = active

Observed:
- actor_move = 0.0080
- actor_noop = 0.9548
- pos_delta = 13
- no_effect = 0.9762
- ready_movable = 912

Manual markers:
- stands: YES
- moves: YES (rare)
- harvest: YES (rare)
- produce: YES (rare)
- attack: NO

## 6. Rollout A/B

Batch A (det):
- batch_label = gridnet_fresh_100k_v2_det_ab
- episodes = 4, max_steps = 512, deterministic = true

Batch B (stoch):
- batch_label = gridnet_fresh_100k_v2_stoch_ab
- episodes = 4, max_steps = 512, deterministic = false

Returns:

| batch | mean | std |
|---|---:|---:|
| deterministic | 2.00 | 0.00 |
| stochastic | 11.00 | 7.91 |

Action-distribution summary:

| batch | NoOp share | normalized entropy | top action share |
|---|---:|---:|---:|
| deterministic | 0.999776 | 0.001648 | 0.999776 |
| stochastic | 0.167736 | 0.999997 | 0.167736 |

Interpretation:
- Deterministic rollout is still effectively NoOp-dominant.
- Stochastic rollout remains near-uniform high-entropy.

## 7. v2 adapter quality

Target contract:
- v2_gridnet_compatible ([6,4,4,4,4,7,49])

Det adapted batch:
- remap_to_noop_share = 0.000000
- semantic_weakening_share = 0.000000
- dropped_samples = 0
- usable_samples = 2048

Stoch adapted batch:
- remap_to_noop_share = 0.000000
- semantic_weakening_share = 0.000000
- dropped_samples = 0
- usable_samples = 2048

Conclusion:
- Adapter path is clean; no data-loss/remap blockers for v2 contract.

## 8. Comparison against old 100k and 200k continuation

Reference runs:
- old 100k: gridnet_100k_20260427T221123Z
- 200k continuation: gridnet_200k_continue_20260428T183153Z

### Fresh 100k vs old 100k

- Deterministic actor-level (final gate):
  - old100k actor_move/noop: 0.0132 / 0.9326
  - fresh100k actor_move/noop: 0.0055 / 0.9436
  - fresh is weaker.
- Visual eval:
  - old100k: actor_move=0.0137, pos_delta=17
  - fresh100k: actor_move=0.0080, pos_delta=13
  - fresh is weaker.
- Stochastic rollout return:
  - old100k mean/std: 12.75 / 5.30
  - fresh100k mean/std: 11.00 / 7.91
  - fresh is weaker.

### Fresh 100k vs 200k continuation

- Deterministic rollout NoOp share:
  - 200k: 0.999766
  - fresh100k: 0.999776
  - fresh is not lower (slightly worse).
- Deterministic multi-opponent actor_move:
  - 200k: 0.0148 (SUSPICIOUS / FAIL_ALL aggregate)
  - fresh100k: 0.0041-0.0055 (PASS labels but weaker movement intensity)
- Stochastic rollout return:
  - 200k: 13.75
  - fresh100k: 11.00
  - fresh is worse.
- Stochastic entropy:
  - both near-uniform (~1.0 normalized entropy)
  - no concentration improvement in fresh.
- Visual behavior:
  - 200k visual: mostly standing, pos_delta=17
  - fresh100k visual: mostly standing, pos_delta=13
  - fresh does not improve activity.

## 9. Decision

Decision: WORSE_REJECT_RUN

Rationale under requested criteria:
- deterministic NoOp share is not lower than 200k continuation (fails criterion)
- deterministic return is still 2.0 (no gain)
- deterministic actor_move is lower than old100k and lower than 200k continuation
- stochastic return is lower than both old100k and 200k continuation
- stochastic normalized entropy remains near-uniform (>0.98)
- visual behavior remains mostly standing and is not more active than references
- v2 adapter is clean, but policy quality is weaker

Non-goals respected:
- no BC-ready packaging
- no student retraining
- no Unity import
- no Unity runtime changes
- no final-teacher-readiness claim
