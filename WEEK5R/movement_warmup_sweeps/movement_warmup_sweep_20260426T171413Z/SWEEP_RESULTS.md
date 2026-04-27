# Movement Warmup Sweep Results: movement_warmup_sweep_20260426T171413Z

## Ranking Rule
1. pos_delta > 0 at 10k
2. lower no_effect at 10k
3. higher actor_move at 10k (target > 0.05)
4. lower actor_noop at 10k without no-effect collapse
5. move_action_position_delta_events > 0

## Ranked Runs
1. move_heavy_seed170 | status=completed_with_failures | pos_delta10k=0 | no_effect10k=1.0 | actor_move10k=0.003425 | actor_noop10k=0.986301 | move_action_position_delta_events=28
2. baseline_mild_seed170 | status=completed_with_failures | pos_delta10k=0 | no_effect10k=1.0 | actor_move10k=0.0 | actor_noop10k=0.993939 | move_action_position_delta_events=29
3. stronger_balanced_seed170 | status=completed_with_failures | pos_delta10k=0 | no_effect10k=1.0 | actor_move10k=0.0 | actor_noop10k=0.997972 | move_action_position_delta_events=27
4. stronger_noeffect_seed170 | status=completed_with_failures | pos_delta10k=0 | no_effect10k=1.0 | actor_move10k=0.0 | actor_noop10k=0.997972 | move_action_position_delta_events=35

## Summary Table
| run_key | status | actor_move_2k | actor_move_5k | actor_move_10k | actor_noop_10k | pos_delta_10k | no_effect_10k | movement_warmup_success_10k | move_action_position_delta_events | nonmove_position_delta_events |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| move_heavy_seed170 | completed_with_failures | 0.0412 | 0.0000 | 0.0034 | 0.9863 | 0 | 1.0000 | False | 28 | 5854 |
| baseline_mild_seed170 | completed_with_failures | 0.0131 | 0.0131 | 0.0000 | 0.9939 | 0 | 1.0000 | False | 29 | 6025 |
| stronger_balanced_seed170 | completed_with_failures | 0.0013 | 0.0085 | 0.0000 | 0.9980 | 0 | 1.0000 | False | 27 | 5949 |
| stronger_noeffect_seed170 | completed_with_failures | 0.0046 | 0.0101 | 0.0000 | 0.9980 | 0 | 1.0000 | False | 35 | 6167 |

## Artifacts
- JSON: WEEK5R/movement_warmup_sweeps/movement_warmup_sweep_20260426T171413Z/sweep_results.json
- Sweep root: WEEK5R/movement_warmup_sweeps/movement_warmup_sweep_20260426T171413Z
