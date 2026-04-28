# Gridnet Reference-Parity Sweep Results

- sweep_id: reference_parity_20260428T142037Z
- generated_utc: 2026-04-28T14:20:46.442108+00:00
- output_dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\gridnet_reference_parity_sweeps\reference_parity_20260428T142037Z

## Scope
- Branch B Gridnet teacher reference-parity ablation only.
- No Unity runtime modification.
- No BC-ready packaging.
- No student retraining.
- No teacher-ready claim.

## Config Status
| config | status | map | num_bot_envs | num_selfplay_envs | diagnostic_only | project_compatible_24x24 |
|---|---|---|---:|---:|---|---|
| A_project_24env_24x24 | failed | maps/24x24/basesWorkers24x24.xml | 24 | 0 | False | True |
| B_reference_24env_16x16 | failed | maps/16x16/basesWorkers16x16.xml | 24 | 0 | True | False |

## Metrics Summary
| config | det_noop_share | det_return_mean | det_return_std | det_actor_move_mean | det_multi_pass_count | stoch_return_mean | stoch_return_std | stoch_entropy_norm | stoch_top_action_share | adapter_24x24 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| A_project_24env_24x24 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |
| B_reference_24env_16x16 | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a | n/a |

## Baseline Comparison
- Compared against fresh100k v2, old100k, 200k continuation, and reference legacy staged visual behavior.
- Baseline payload is embedded in the JSON results artifact.
- Reference legacy staged visual behavior notes:
  - movement
  - harvesting resources
  - barracks construction
  - unit production
  - attacking
  - 

## Ranking
Priority order used:
1. deterministic NoOp share lower
2. deterministic return > 2.0
3. stochastic entropy lower than 0.98
4. visual behavior more active
5. adapter clean for 24x24 configs
- No completed configs to rank.

## Decision
- NONE_HELPED_MOVE_TO_ENTROPY_REWARD_CURRICULUM_REDESIGN

## Non-Goals Reinforced
- No BC-ready package created in this sweep.
- No student retraining performed.
- No Unity modifications.
- No teacher-ready claim made.

