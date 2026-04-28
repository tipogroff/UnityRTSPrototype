# Gridnet Multi-Opponent Eval Summary

- checkpoint: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_teacher_runs\gridnet_200k_continue_20260428T183153Z\agent_final.pt
- timestamp_utc: 2026-04-28T11:46:19Z
- deterministic_mode: False
- episodes_per_opponent: 4

## Aggregate Verdict: CANDIDATE_VIABLE

PASS on 4/4 opponents. Consider continuation training or BC export.

- pass_count: 4 / 4
- any_positive_position_delta: True

## Per-Opponent Results

| opponent | status | actor_move | actor_noop | pos_delta | no_effect | ready_movable |
|----------|--------|------------|------------|-----------|-----------|---------------|
| randomBiasedAI | PASS | 0.3148 | 0.4594 | 180 | 0.8357 | 573 |
| lightRushAI | PASS | 0.1603 | 0.5212 | 124 | 0.9144 | 383 |
| workerRushAI | PASS | 0.2246 | 0.4725 | 145 | 0.8723 | 491 |
| coacAI | PASS | 0.3231 | 0.4781 | 173 | 0.8533 | 534 |

## Notes
- Each opponent was evaluated in an independent subprocess (separate JVM).
- opponent-sampling=static within each subprocess.
- PASS requires: effective_position_delta_count > 0, actor_level_move_share > 0, no_effect_action_share < 1.0.
