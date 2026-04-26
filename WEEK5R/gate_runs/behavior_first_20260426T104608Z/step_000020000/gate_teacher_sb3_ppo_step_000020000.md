# Teacher Behavior Gate Report

Generated at (UTC): 2026-04-26T13:15:53Z
Schema: `teacher_behavior_gate.v1`

## Checkpoint
- Path: `C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\retraining_runs\behavior_first_20260426T104608Z\checkpoints\teacher_sb3_ppo_step_000020000.zip`
- Loader: `sb3_contrib.MaskablePPO`
- deterministic_mode: `True`
- Opponent sampling mode: `per_episode`
- Opponents used (actor audit): `coacAI, workerRushAI`

## Gate Verdict
```
STATUS: FAIL_NO_EFFECT_BEHAVIOR
```

### FAIL Reasons
- FAIL_NO_EFFECT_BEHAVIOR: chosen_count=41, no_effect_share=0.9756 > 0.80, pos_delta=0

## Actor-Level Summary
| Metric | Value |
|---|---|
| full_tensor_move_share | 0.0002 (0.02%) |
| actor_level_move_share | 0.0846 (8.46%) |
| actor_noop_share | 0.2786 (27.86%) |
| ready_own_actor_count | 1608 |
| steps_with_ready_actors | 768 |
| steps_with_movable_ready_actors | 24 |
| ready_movable_actor_choice_count | 24 |
| ready_movable_actor_count (legacy alias, step-level proxy) | 24 |

## Effective Behavior Summary
| Metric | Value |
|---|---|
| effective_position_delta_count | 0 |
| no_effect_action_share | 0.9756 (97.56%) |
| chosen_ready_own_actor_count | 41 |
| steps_executed (effective audit) | 100 |

## Visual Sanity Replay
- created: False
- trace path: `None`
- notes path: `None`
- visual verdict: `None`

## Decision Rules Applied
### FAIL_COLLAPSED_NOOP
- Triggered: False
  - ready_movable_actor_count: 24
  - actor_level_move_share: 0.084577
  - effective_position_delta_count: 0
  - actor_noop_share: 0.278607
  - threshold_noop: 0.9
### FAIL_FALSE_FULL_TENSOR_MOVE
- Triggered: False
  - full_tensor_move_share: 0.000231
  - actor_level_move_share: 0.084577
  - threshold_full: 0.1
  - threshold_actor: 0.05
### FAIL_NO_EFFECT_BEHAVIOR
- Triggered: True
  - chosen_ready_own_actor_count: 41
  - no_effect_action_share: 0.97561
  - effective_position_delta_count: 0
  - threshold_no_effect: 0.8
### SUSPICIOUS
- Triggered: False
  - actor_noop_share: 0.278607
  - no_effect_action_share: 0.97561
  - threshold_noop: 0.75
  - threshold_no_effect: 0.6
### PASS
- Triggered: False
  - actor_level_move_share: 0.084577
  - effective_position_delta_count: 0
  - threshold_move: 0.05

## Important Caveats
- This gate runs inside Gym-microRTS only. It does **NOT** claim Gym->Unity semantic parity.
- Full-tensor Move share is **NOT** evidence of real movement. Actor-level Move share is the authoritative signal.
- Effective-behavior state-diff is an observation proxy, not a confirmed internal execution stream.
