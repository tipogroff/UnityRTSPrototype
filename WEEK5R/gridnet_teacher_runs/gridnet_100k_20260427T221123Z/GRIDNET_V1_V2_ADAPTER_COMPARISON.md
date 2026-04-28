# Gridnet 100k Stochastic Batch Adapter Comparison: v1 vs v2

Date: 2026-04-28
Input batch: WEEK5R/gridnet_teacher_rollouts/gridnet_100k_stoch_ab

Compared adapter outputs:
- v1 baseline: WEEK5R/teacher_exports_v2/teacher_adapted_gridnet_100k_stoch_ab_v1_20260428T150711Z
- v2 gridnet-compatible: WEEK5R/teacher_exports_v2/teacher_adapted_gridnet_100k_stoch_ab_v2_20260428T150803Z

Compared reports:
- v1 conversion report: WEEK5R/teacher_exports_v2/teacher_adapted_gridnet_100k_stoch_ab_v1_20260428T150711Z/conversion_report.json
- v2 conversion report: WEEK5R/teacher_exports_v2/teacher_adapted_gridnet_100k_stoch_ab_v2_20260428T150803Z/conversion_report.json

## Contract Modes

- v1 target_action_contract: v1_mvp
- v1 target_branch_sizes: [6,4,4,4,4,4,9]
- v2 target_action_contract: v2_gridnet_compatible
- v2 target_branch_sizes: [6,4,4,4,4,7,49]
- source_branch_sizes (both): [6,4,4,4,4,7,49]

## Core Metrics

Total cell-actions evaluated: 1,179,648 (2048 steps x 576 cells)

| Metric | v1_mvp | v2_gridnet_compatible | Delta |
|---|---:|---:|---:|
| remap_to_noop_count | 244,877 | 0 | -244,877 |
| remap_to_noop_share | 20.7585% | 0.0000% | -20.7585 pp |
| attack_target_remap_count | 160,414 | 0 | -160,414 |
| produce_type_remap_count | 84,463 | 0 | -84,463 |
| semantic_weakening_share | 20.7585% | 0.0000% | -20.7585 pp |
| requires_unity_v2_validation_count | 0 | 244,984 | +244,984 |

## Action Histograms (Before/After)

Input histogram (same for both modes):
- NoOp: 197,713
- Move: 196,361
- Harvest: 196,013
- Return: 196,232
- Produce: 196,576
- Attack: 196,753

v1 output histogram:
- NoOp: 442,590
- Move: 196,361
- Harvest: 196,013
- Return: 196,232
- Produce: 112,113
- Attack: 36,339

v2 output histogram:
- NoOp: 197,713
- Move: 196,361
- Harvest: 196,013
- Return: 196,232
- Produce: 196,576
- Attack: 196,753

## Effective Non-NoOp Share

- v1 effective non-NoOp share: 62.4812%
- v2 effective non-NoOp share: 83.2397%

NoOp share for reference:
- v1 NoOp share: 37.5188%
- v2 NoOp share: 16.7603%

## Interpretation

- Attack remap dropped from 13.60% (160,414 / 1,179,648) to 0 with v2 contract.
- Total remap_to_noop dropped significantly: 20.76% to 0.
- Produce branch no longer collapses types >=4 to NoOp in v2.
- v2 explicitly flags cells requiring Unity runtime migration via requires_unity_v2_validation, instead of silently weakening semantics.

## Hypothesis Check

Expected hypothesis:
- attack remap should drop from 13.60% to 0
- total remap_to_noop should drop significantly
- stochastic batch may become more usable, but still not automatically BC-ready because distribution is near-uniform

Observed:
- confirmed: attack remap 13.60% to 0
- confirmed: total remap_to_noop 20.76% to 0
- confirmed: still not auto BC-ready claim; near-uniform stochastic distribution remains, and Unity v2 runtime implementation is pending

## Guardrails and Non-Claims

- This comparison does not claim Unity runtime parity.
- No BC-ready packaging was generated in this step.
- v1 path remains available as default adapter contract.
- Existing Week5 artifacts were not modified or overwritten.
