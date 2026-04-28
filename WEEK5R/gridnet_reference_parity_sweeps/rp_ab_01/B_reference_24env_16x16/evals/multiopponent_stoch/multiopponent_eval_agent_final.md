# Gridnet Multi-Opponent Eval Summary

- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_reference_parity_sweeps\rp_ab_01\B_reference_24env_16x16\B_reference_24env_16x16_20260428T143356Z\agent_final.pt
- timestamp_utc: 2026-04-28T14:39:48Z
- deterministic_mode: False
- episodes_per_opponent: 4

## Aggregate Verdict: CANDIDATE_VIABLE

PASS on 4/4 opponents. Consider continuation training or BC export.

- pass_count: 4 / 4
- any_positive_position_delta: True

## Per-Opponent Results

| opponent | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|----------|--------|------------|------------|-----------|-----------|---------------|
| randomBiasedAI | PASS | 0.0801 | 0.5307 | 83 | 0.9393 | 250 |
| lightRushAI | PASS | 0.2047 | 0.3740 | 157 | 0.8701 | 471 |
| workerRushAI | PASS | 0.1946 | 0.4276 | 140 | 0.8822 | 420 |
| coacAI | PASS | 0.1634 | 0.3914 | 124 | 0.9048 | 424 |

## Notes
- Each opponent was evaluated in an independent subprocess (separate JVM).
- opponent-sampling=static within each subprocess.
- PASS requires: effective_position_delta_count > 0, actor_level_move_share > 0, no_effect_action_share < 1.0.
