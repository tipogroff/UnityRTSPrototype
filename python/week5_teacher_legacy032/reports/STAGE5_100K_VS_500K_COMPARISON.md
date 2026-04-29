# STAGE5 100K vs 500K Comparison

- Date: 2026-04-30
- baseline_run_id: legacy032_24x24_teacher_main_20260429T162331Z
- baseline_stage: stage_000100000
- candidate_run_id: legacy032_24x24_teacher_main_20260429T171506Z
- candidate_stage: stage_000500000
- baseline_gate_json: python/week5_teacher_legacy032/reports/stage5_gate_000100000_20260429T164521Z.json
- candidate_gate_json: python/week5_teacher_legacy032/reports/stage5_gate_000500000_20260429T190313Z.json
- note: 500k is a from-scratch staged checkpoint with larger total_timesteps, not a resumed continuation from 100k.

## Comparison Table

| metric | 100k | 500k | delta (500k-100k) | interpretation |
|---|---:|---:|---:|---|
| gate_decision | PASS | PASS | 0 | technical gate remained PASS |
| mean_return stochastic | -7.5 | -7.5 | 0.0 | no return improvement |
| mean_return deterministic | -10.0 | -10.0 | 0.0 | deterministic performance unchanged |
| stochastic noop_share | 0.1663495256 | 0.1664351852 | +0.0000856596 | slightly more noop, minor |
| deterministic noop_share | 0.9965651659 | 0.9965651659 | 0.0 | still extremely high (collapse risk remains) |
| effective_activity_share stochastic | 0.8336504744 | 0.8335648148 | -0.0000856596 | still high and > 0 |
| move_share stochastic | 0.1662045632 | 0.1662025578 | -0.0000020054 | effectively unchanged and nonzero |
| attack_action_count stochastic | 579601 | 579623 | +22 | raw count, depends on episode length |
| produce_action_count stochastic | 585077 | 584767 | -310 | raw count, depends on episode length |
| policy_entropy_proxy stochastic | 0.0009317504 | 0.0007871015 | -0.0001446489 | lower entropy; monitor for stronger collapse |
| repeated_same_action_share stochastic | 0.1909982364 | 0.1910809494 | +0.0000827129 | essentially unchanged |
| env_matches_target_24x24 | true | true | 0 | must stay true (OK) |
| mask_used_during_eval | true | true | 0 | must stay true (OK) |

## Interpretation

- Technical compatibility is stable at 500k: checkpoint load, architecture load, inference, target 24x24 env match, and mask usage all remained valid.
- Behavior quality is mostly flat vs 100k on key returns: no deterministic or stochastic return gain.
- Deterministic policy still exhibits near-total noop share (~0.9966), which is a continuing warning signal.
- Stochastic policy remains active (effective_activity_share > 0, nonzero move share), but does not show clear improvement trend versus 100k.

## Conclusion

- Stage 5B is technically successful but behavior gain over 100k is not demonstrated.
- Recommended decision: READY_FOR_1M_WITH_WARNINGS.
