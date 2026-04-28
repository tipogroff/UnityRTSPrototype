# Gridnet Multi-Opponent Eval Summary

- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_teacher_runs\gridnet_fresh_100k_v2_20260428T191104Z\agent_final.pt
- timestamp_utc: 2026-04-28T12:27:02Z
- deterministic_mode: False
- episodes_per_opponent: 4

## Aggregate Verdict: CANDIDATE_VIABLE

PASS on 4/4 opponents. Consider continuation training or BC export.

- pass_count: 4 / 4
- any_positive_position_delta: True

## Per-Opponent Results

| opponent | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|----------|--------|------------|------------|-----------|-----------|---------------|
| randomBiasedAI | PASS | 0.0941 | 0.4475 | 91 | 0.9288 | 344 |
| lightRushAI | PASS | 0.0677 | 0.3767 | 73 | 0.9319 | 349 |
| workerRushAI | PASS | 0.2239 | 0.3859 | 155 | 0.8903 | 599 |
| coacAI | PASS | 0.1448 | 0.3511 | 125 | 0.8884 | 558 |

## Notes
- Each opponent was evaluated in an independent subprocess (separate JVM).
- opponent-sampling=static within each subprocess.
- PASS requires: effective_position_delta_count > 0, actor_level_move_share > 0, no_effect_action_share < 1.0.
