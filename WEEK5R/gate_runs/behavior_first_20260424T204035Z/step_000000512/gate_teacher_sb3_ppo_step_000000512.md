# Teacher Behavior Gate Report

Generated at (UTC): 2026-04-24T20:44:37Z
Schema: `teacher_behavior_gate.v1`

## Checkpoint
- Path: `C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\retraining_runs\behavior_first_20260424T204035Z\checkpoints\teacher_sb3_ppo_step_000000512.zip`
- Loader: `sb3_contrib.MaskablePPO`
- Opponent sampling mode: `per_episode`
- Opponents used (actor audit): `workerRushAI`

## Gate Verdict
```
STATUS: FAIL_FALSE_FULL_TENSOR_MOVE
```

### FAIL Reasons
- FAIL_FALSE_FULL_TENSOR_MOVE: full_tensor_move=0.1713 >= 0.10 but actor_level_move=0.0278 < 0.05 (spurious tensor signal, not real movement)
- FAIL_NO_EFFECT_BEHAVIOR: chosen_count=11, no_effect_share=1.0000 > 0.80, pos_delta=0

## Actor-Level Summary
| Metric | Value |
|---|---|
| full_tensor_move_share | 0.1713 (17.13%) |
| actor_level_move_share | 0.0278 (2.78%) |
| actor_noop_share | 0.8889 (88.89%) |
| ready_own_actor_count | 36 |
| steps_with_ready_actors | 32 |
| steps_with_movable_ready_actors | 1 |
| ready_movable_actor_choice_count | 1 |
| ready_movable_actor_count (legacy alias, step-level proxy) | 1 |

## Effective Behavior Summary
| Metric | Value |
|---|---|
| effective_position_delta_count | 0 |
| no_effect_action_share | 1.0000 (100.00%) |
| chosen_ready_own_actor_count | 11 |
| steps_executed (effective audit) | 10 |

## Visual Sanity Replay
- created: False
- trace path: `None`
- notes path: `None`
- visual verdict: `None`

## Decision Rules Applied
### FAIL_COLLAPSED_NOOP
- Triggered: False
  - ready_movable_actor_count: 1
  - actor_level_move_share: 0.027778
  - effective_position_delta_count: 0
  - actor_noop_share: 0.888889
  - threshold_noop: 0.9
### FAIL_FALSE_FULL_TENSOR_MOVE
- Triggered: True
  - full_tensor_move_share: 0.171332
  - actor_level_move_share: 0.027778
  - threshold_full: 0.1
  - threshold_actor: 0.05
### FAIL_NO_EFFECT_BEHAVIOR
- Triggered: True
  - chosen_ready_own_actor_count: 11
  - no_effect_action_share: 1.0
  - effective_position_delta_count: 0
  - threshold_no_effect: 0.8
### SUSPICIOUS
- Triggered: False
  - actor_noop_share: 0.888889
  - no_effect_action_share: 1.0
  - threshold_noop: 0.75
  - threshold_no_effect: 0.6
### PASS
- Triggered: False
  - actor_level_move_share: 0.027778
  - effective_position_delta_count: 0
  - threshold_move: 0.05

## Important Caveats
- This gate runs inside Gym-microRTS only. It does **NOT** claim Gym->Unity semantic parity.
- Full-tensor Move share is **NOT** evidence of real movement. Actor-level Move share is the authoritative signal.
- Effective-behavior state-diff is an observation proxy, not a confirmed internal execution stream.
