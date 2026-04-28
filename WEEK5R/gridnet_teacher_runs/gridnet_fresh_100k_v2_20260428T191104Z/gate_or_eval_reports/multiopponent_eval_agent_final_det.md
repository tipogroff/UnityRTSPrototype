# Gridnet Multi-Opponent Eval Summary

- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_teacher_runs\gridnet_fresh_100k_v2_20260428T191104Z\agent_final.pt
- timestamp_utc: 2026-04-28T12:26:36Z
- deterministic_mode: True
- episodes_per_opponent: 4

## Aggregate Verdict: CANDIDATE_VIABLE

PASS on 4/4 opponents. Consider continuation training or BC export.

- pass_count: 4 / 4
- any_positive_position_delta: True

## Per-Opponent Results

| opponent | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|----------|--------|------------|------------|-----------|-----------|---------------|
| randomBiasedAI | PASS | 0.0048 | 0.9445 | 36 | 0.9733 | 2876 |
| lightRushAI | PASS | 0.0041 | 0.9454 | 36 | 0.9730 | 2884 |
| workerRushAI | PASS | 0.0055 | 0.9436 | 36 | 0.9737 | 2864 |
| coacAI | PASS | 0.0041 | 0.9454 | 36 | 0.9730 | 2884 |

## Notes
- Each opponent was evaluated in an independent subprocess (separate JVM).
- opponent-sampling=static within each subprocess.
- PASS requires: effective_position_delta_count > 0, actor_level_move_share > 0, no_effect_action_share < 1.0.
