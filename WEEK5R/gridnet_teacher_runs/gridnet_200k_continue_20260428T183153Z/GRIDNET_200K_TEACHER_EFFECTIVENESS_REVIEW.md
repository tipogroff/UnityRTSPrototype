# GRIDNET 200K Teacher Effectiveness Review

Run id: gridnet_200k_continue_20260428T183153Z
Date: 2026-04-28
Scope: Training effectiveness only (no BC packaging, no Unity import, no student retraining, no parity claim)

## 1. Training provenance

- Trainer: python/week5_teacher_gridnet/train_teacher_gridnet_project.py
- Launch script: python/week5_teacher_gridnet/run_gridnet_teacher_continue_200k.ps1
- Continuation source checkpoint: WEEK5R/gridnet_teacher_runs/gridnet_100k_20260427T221123Z/agent_final.pt
- Continuation source metadata: WEEK5R/gridnet_teacher_runs/gridnet_100k_20260427T221123Z/model_metadata.json
- Continuation settings:
  - initial_global_step: 100000
  - total_timesteps: 200000
  - checkpoint_steps: 150000, 200000
  - seed: 1
  - device: cpu
- Final result: completed, global_step_reached=201376, exit=0

Primary artifacts:
- agent_final.pt
- checkpoints/agent_step_000150000.pt
- checkpoints/agent_step_000200000.pt
- model_metadata.json
- run_manifest.json
- summary.md
- gate_or_eval_reports/

## 2. Checkpoint progression

Single-opponent actor-level gate (randomBiasedAI static due JVM limitation):

| checkpoint | gate_status | actor_move | actor_noop | pos_delta | no_effect |
|---|---|---:|---:|---:|---:|
| 150k | FAIL_COLLAPSED_NOOP | 0.0000 | 0.9939 | 20 | 1.0000 |
| 200k | SUSPICIOUS | 0.0148 | 0.9749 | 52 | 1.0000 |
| final | SUSPICIOUS | 0.0148 | 0.9749 | 52 | 1.0000 |

Interpretation:
- There is partial recovery from full collapse at 150k to weak non-collapse at 200k.
- Deterministic non-effect remains maximal (1.0), indicating actions still fail to produce reliable effective behavior.

## 3. Deterministic eval

Multi-opponent deterministic eval (4 opponents):
- Aggregate verdict: FAIL_ALL
- pass_count: 0/4
- All opponents: SUSPICIOUS

Per-opponent table (requested format):

| opponent | mode | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|---|---|---|---:|---:|---:|---:|---:|
| randomBiasedAI | deterministic | SUSPICIOUS | 0.0148 | 0.9749 | 52 | 1.0000 | 2480 |
| lightRushAI | deterministic | SUSPICIOUS | 0.0148 | 0.9749 | 52 | 1.0000 | 2480 |
| workerRushAI | deterministic | SUSPICIOUS | 0.0148 | 0.9749 | 52 | 1.0000 | 2480 |
| coacAI | deterministic | SUSPICIOUS | 0.0148 | 0.9749 | 52 | 1.0000 | 2480 |

Key point:
- Deterministic path is still effectively degenerate for reliable actor-level movement.

## 4. Stochastic eval

Multi-opponent stochastic eval (4 opponents):
- Aggregate verdict: CANDIDATE_VIABLE
- pass_count: 4/4

Per-opponent table (requested format):

| opponent | mode | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|---|---|---|---:|---:|---:|---:|---:|
| randomBiasedAI | stochastic | PASS | 0.3148 | 0.4594 | 180 | 0.8357 | 573 |
| lightRushAI | stochastic | PASS | 0.1603 | 0.5212 | 124 | 0.9144 | 383 |
| workerRushAI | stochastic | PASS | 0.2246 | 0.4725 | 145 | 0.8723 | 491 |
| coacAI | stochastic | PASS | 0.3231 | 0.4781 | 173 | 0.8533 | 534 |

Key point:
- Stochastic path remains the only consistently effective mode.

## 5. Visual eval

Visual run:
- Script: python/week5_teacher_gridnet/render_gridnet_checkpoint.py
- Opponent: randomBiasedAI
- max_steps: 300
- visual_eval_status: active

Observed metrics from visual_eval_agent_final.json:
- actor_level_move_share: 0.0199
- actor_noop_share: 0.9724
- pos_delta_count: 17
- ready_actor_action_counts: NoOp=880, Move=18, Harvest=2, Produce=5, Attack=0

Manual behavior marking (required):
- stands: YES (dominant)
- moves: YES (rare)
- harvest: YES (rare)
- produce: YES (rare)
- attack: NO (not observed)

Conclusion:
- Behavior is mostly stationary with sparse non-NoOp events.

## 6. Rollout A/B

Batch A (deterministic):
- episodes=4, max_steps=512, deterministic=true
- batch_label=gridnet_200k_det_ab

Batch B (stochastic):
- episodes=4, max_steps=512, deterministic=false
- batch_label=gridnet_200k_stoch_ab

Returns:

| batch | mean | std |
|---|---:|---:|
| deterministic | 2.00 | 0.00 |
| stochastic | 13.75 | 5.63 |

Action distribution properties:

| batch | NoOp share | entropy (6-way) | normalized entropy | top action share |
|---|---:|---:|---:|---:|
| deterministic | 0.999766 | 0.002281 | 0.001273 | 0.999766 |
| stochastic | 0.167663 | 1.791755 | 0.999998 | 0.167663 |

Interpretation:
- Deterministic rollout remains nearly pure NoOp.
- Stochastic rollout remains near-uniform (very high entropy, very low concentration).

## 7. v2 adapter quality

Adapter mode used:
- target-action-contract: v2_gridnet_compatible

Deterministic adapted batch metrics:
- remap_to_noop_share: 0.000000
- semantic_weakening_share: 0.000000
- usable_samples: 2048
- dropped_samples: 0
- move survived share: 1.000000
- produce survived share: 1.000000
- attack survived share: 0.000000 (no attack input present)

Stochastic adapted batch metrics:
- remap_to_noop_share: 0.000000
- semantic_weakening_share: 0.000000
- usable_samples: 2048
- dropped_samples: 0
- move survived share: 1.000000
- produce survived share: 1.000000
- attack survived share: 1.000000

Conclusion:
- v2 adapter quality is clean for both batches (no remap-to-noop, no semantic weakening, no drops).

## 8. Comparison against 100k

Reference baseline from prior 100k review:
- deterministic returns mean/std: 2.00 / 0.00
- stochastic returns mean/std: 12.75 / 5.30
- deterministic rollout NoOp share: 0.9997+
- stochastic rollout: near-uniform
- deterministic multi-opponent: previously PASS but weak (actor_noop about 0.9326, no_effect about 0.9767)

200k vs 100k summary:
- stochastic return mean: 12.75 -> 13.75 (small gain)
- deterministic return mean: 2.00 -> 2.00 (no gain)
- deterministic action collapse: still near-total NoOp
- stochastic distribution: still near-uniform (no concentration gain)
- deterministic multi-opponent quality: regressed to FAIL_ALL/SUSPICIOUS
- adapter v2 quality: remains excellent (remap 0, weakening 0, drops 0)

Net effect:
- Migration compatibility improved/maintained at adapter level.
- Teacher policy quality itself is still insufficient and unstable in deterministic mode.

## 9. Decision

Decision: ADJUST_TRAINING_RECIPE

Reasoning against decision criteria:
- multi-opponent eval PASS: only stochastic passes; deterministic fails (criterion not met)
- visual meaningful behavior: mostly standing, very sparse effective actions (criterion not met)
- deterministic not 99% NoOp: not met (NoOp about 99.98% in deterministic rollout)
- stochastic not near-uniform: not met (normalized entropy about 1.0)
- v2 adapter remap_to_noop_share = 0: met
- drops = 0: met
- mean return noticeably better than 100k: not met (only small stochastic gain)
- concentrated action intent: not met

Practical conclusion:
- Do not promote to v2 export candidate yet.
- Main blocker is policy behavior quality, not adapter/contract compatibility.
