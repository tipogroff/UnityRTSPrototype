# Day 5 Comparative Report: meaningful vs stronger teacher batch

Generated at (UTC): 2026-04-22T11:03:19Z

## Batches
- old_meaningful_batch: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher\teacher_exports\teacher_adapted_day5_first_nonrandom_meaningful
- new_stronger_batch: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher\teacher_exports\teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z

## Contract / Validation outcome

| Metric | old meaningful | new stronger | delta (new-old) | trend |
|---|---:|---:|---:|---|
| Validation pass | 1.000000 | 1.000000 | 0.000000 | same |
| Hard failures | 0.000000 | 0.000000 | 0.000000 | same |
| Warnings | 4.000000 | 25.0000 | 21.0000 | worsened |
| Warnings per episode | 4.000000 | 3.125000 | -0.875000 | improved |
- warning_count_not_comparable_when_episode_count_differs: true (reason=episode_count_differs_and_warning_categories_identical)
- warning_check_types (old/new): ['action.inactive_branch_nonzero', 'observation.categorical_soft_sum.current_action', 'observation.categorical_soft_sum.unit_type', 'quality.semantic_weakening'] / ['action.inactive_branch_nonzero', 'observation.categorical_soft_sum.current_action', 'observation.categorical_soft_sum.unit_type', 'quality.semantic_weakening']

## Quality metrics

| Metric | old meaningful | new stronger | delta (new-old) | trend |
|---|---:|---:|---:|---|
| Usable samples | 2000.0000 | 4040.0000 | 2040.0000 | improved |
| Dropped samples | 0.000000 | 0.000000 | 0.000000 | same |
| Conversion loss share | 0.00% | 0.00% | 0.00% | same |
| remap_to_noop_share | 19.97% | 9.38% | -10.59% | improved |
| semantic_weakening_share | 100.00% | 100.00% | 0.00% | same |
| observation_signal_loss_share | 0.00% | 0.00% | 0.00% | same |
| production_actions_survived_share | 60.00% | 58.48% | -1.52% | worsened |
| class imbalance ratio | 19.4545 | 11.5504 | -7.904149 | improved |
| inactive_branch_anomaly_share | 4.51% | 2.60% | -1.91% | improved |
- inactive_branch_warning_severity: old=medium, new=low

## Sanity metrics

| Metric | old meaningful | new stronger | delta (new-old) | trend |
|---|---:|---:|---:|---|
| attack/local-target share | 1.91% | 3.47% | 1.56% | improved |
| produce action share | 10.42% | 5.38% | -5.03% | worsened |

Action type distribution shares (old -> new):
- action_type=0: 37.15% -> 40.11%
- action_type=1: 15.80% -> 39.87%
- action_type=2: 17.01% -> 5.21%
- action_type=3: 17.71% -> 5.97%
- action_type=4: 10.42% -> 5.38%
- action_type=5: 1.91% -> 3.47%

Weak spots detected:
- old meaningful:
  - High remap-to-noop volume indicates semantic weakening pressure from source-to-target action gap.
  - Produce actions survival share is limited; conversion keeps only MVP subset semantics.
  - Attack action share is low after conversion and may weaken combat supervision density.
  - Action class imbalance is strong and may require weighting/oversampling in BC.
  - Inactive-branch anomalies are medium severity and should be monitored before BC.
- new stronger:
  - High remap-to-noop volume indicates semantic weakening pressure from source-to-target action gap.
  - Produce actions survival share is limited; conversion keeps only MVP subset semantics.
  - Attack action share is low after conversion and may weaken combat supervision density.
  - Action class imbalance is strong and may require weighting/oversampling in BC.

## Recommendation

- preferred_bc_candidate_batch: corrective_day3_cpu_20260422T085809Z
- comparison_result: better
- reasoning:
  - Improved metrics: remap_to_noop_share, class_imbalance_ratio, inactive_branch_anomaly_share, usable_samples
  - Worsened metrics: production_actions_survived_share
  - Decision is based only on adapted/validated data-level outcomes, not on teacher training duration or checkpoint origin.

