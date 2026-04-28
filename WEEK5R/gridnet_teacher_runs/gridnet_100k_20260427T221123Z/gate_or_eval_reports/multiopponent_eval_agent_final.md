# Gridnet Multi-Opponent Eval Summary

- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_teacher_runs\gridnet_100k_20260427T221123Z\agent_final.pt
- timestamp_utc: 2026-04-27T16:29:59Z
- deterministic_mode: False
- episodes_per_opponent: 4

## Aggregate Verdict: CANDIDATE_VIABLE

PASS on 4/4 opponents. Consider continuation training or BC export.

- pass_count: 4 / 4
- any_positive_position_delta: True

## Per-Opponent Results

| opponent | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|----------|--------|------------|------------|-----------|-----------|---------------|
| randomBiasedAI | PASS | 0.3246 | 0.5437 | 203 | 0.8366 | 785 |
| lightRushAI | PASS | 0.3538 | 0.5211 | 206 | 0.7981 | 744 |
| workerRushAI | PASS | 0.2436 | 0.4749 | 168 | 0.8762 | 708 |
| coacAI | PASS | 0.3166 | 0.4196 | 193 | 0.8391 | 767 |

## Notes
- Each opponent was evaluated in an independent subprocess (separate JVM).
- opponent-sampling=static within each subprocess.
- PASS requires: effective_position_delta_count > 0, actor_level_move_share > 0, no_effect_action_share < 1.0.
