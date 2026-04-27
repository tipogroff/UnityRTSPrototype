# Teacher Behavior Gate Report

Generated at (UTC): 2026-04-26T19:38:36Z
Schema: `teacher_behavior_gate.v1`

## Checkpoint
- Path: `C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\movement_warmup_sweeps\movement_warmup_sweep_20260426T171413Z\runs\stronger_balanced_seed170\retraining_runs\behavior_first_20260426T184712Z\checkpoints\teacher_sb3_ppo_step_000005000.zip`
- Loader: `sb3_contrib.MaskablePPO`
- deterministic_mode: `True`
- Opponent sampling mode: `static`
- Opponents used (actor audit): `passiveAI`

## Gate Verdict
```
STATUS: FAIL_NO_EFFECT_BEHAVIOR
```

### FAIL Reasons
- FAIL_NO_EFFECT_BEHAVIOR: chosen_count=115, no_effect_share=0.9913 > 0.80, pos_delta=0

## Actor-Level Summary
| Metric | Value |
|---|---|
| full_tensor_move_share | 0.0000 (0.00%) |
| actor_level_move_share | 0.0085 (0.85%) |
| actor_noop_share | 0.9394 (93.94%) |
| ready_own_actor_count | 2836 |
| steps_with_ready_actors | 948 |
| steps_with_movable_ready_actors | 8 |
| ready_movable_actor_choice_count | 8 |
| ready_movable_actor_count (legacy alias, step-level proxy) | 8 |

## Effective Behavior Summary
| Metric | Value |
|---|---|
| effective_position_delta_count | 0 |
| no_effect_action_share | 0.9913 (99.13%) |
| chosen_ready_own_actor_count | 115 |
| steps_executed (effective audit) | 100 |

## Visual Sanity Replay
- created: False
- trace path: `None`
- notes path: `None`
- visual verdict: `None`

## Decision Rules Applied
### FAIL_COLLAPSED_NOOP
- Triggered: False
  - ready_movable_actor_count: 8
  - actor_level_move_share: 0.008463
  - effective_position_delta_count: 0
  - actor_noop_share: 0.939351
  - threshold_noop: 0.9
### FAIL_FALSE_FULL_TENSOR_MOVE
- Triggered: False
  - full_tensor_move_share: 4.1e-05
  - actor_level_move_share: 0.008463
  - threshold_full: 0.1
  - threshold_actor: 0.05
### FAIL_NO_EFFECT_BEHAVIOR
- Triggered: True
  - chosen_ready_own_actor_count: 115
  - no_effect_action_share: 0.991304
  - effective_position_delta_count: 0
  - threshold_no_effect: 0.8
### SUSPICIOUS
- Triggered: False
  - actor_noop_share: 0.939351
  - no_effect_action_share: 0.991304
  - threshold_noop: 0.75
  - threshold_no_effect: 0.6
### PASS
- Triggered: False
  - actor_level_move_share: 0.008463
  - effective_position_delta_count: 0
  - threshold_move: 0.05

## Important Caveats
- This gate runs inside Gym-microRTS only. It does **NOT** claim Gym->Unity semantic parity.
- Full-tensor Move share is **NOT** evidence of real movement. Actor-level Move share is the authoritative signal.
- Effective-behavior state-diff is an observation proxy, not a confirmed internal execution stream.
