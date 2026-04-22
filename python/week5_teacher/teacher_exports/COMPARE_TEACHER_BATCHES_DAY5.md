# Day 5 Comparative Report: meaningful vs stronger teacher batch

Generated at (UTC): 2026-04-19T14:30:39Z

## Batches
- old_meaningful_batch: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher\teacher_exports\teacher_adapted_day5_first_nonrandom_meaningful
- new_stronger_batch: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher\teacher_exports\teacher_adapted_day5_stronger_teacher_20260419T141742Z

## Contract / Validation outcome

| Metric | old meaningful | new stronger | delta (new-old) | trend |
|---|---:|---:|---:|---|
| Validation pass | 1.000000 | 1.000000 | 0.000000 | same |
| Hard failures | 0.000000 | 0.000000 | 0.000000 | same |
| Warnings | 4.000000 | 7.000000 | 3.000000 | worsened |

## Quality metrics

| Metric | old meaningful | new stronger | delta (new-old) | trend |
|---|---:|---:|---:|---|
| Usable samples | 2000.0000 | 4000.0000 | 2000.0000 | improved |
| Dropped samples | 0.000000 | 0.000000 | 0.000000 | same |
| Conversion loss share | 0.00% | 0.00% | 0.00% | same |
| remap_to_noop_share | 19.97% | 18.92% | -1.04% | improved |
| semantic_weakening_share | 100.00% | 100.00% | 0.00% | same |
| observation_signal_loss_share | 0.00% | 0.00% | 0.00% | same |
| production_actions_survived_share | 60.00% | 59.00% | -1.00% | worsened |
| class imbalance ratio | 19.4545 | 20.0909 | 0.636364 | worsened |
| inactive_branch_anomaly_share | 4.51% | 5.38% | 0.87% | worsened |
- inactive_branch_warning_severity: old=medium, new=medium

## Sanity metrics

| Metric | old meaningful | new stronger | delta (new-old) | trend |
|---|---:|---:|---:|---|
| attack/local-target share | 1.91% | 1.91% | 0.00% | same |
| produce action share | 10.42% | 10.24% | -0.17% | worsened |

Action type distribution shares (old -> new):
- action_type=0: 37.15% -> 38.37%
- action_type=1: 15.80% -> 19.44%
- action_type=2: 17.01% -> 15.28%
- action_type=3: 17.71% -> 14.76%
- action_type=4: 10.42% -> 10.24%
- action_type=5: 1.91% -> 1.91%

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
  - Inactive-branch anomalies are medium severity and should be monitored before BC.

## Recommendation

- preferred_bc_candidate_batch: teacher_adapted_day5_first_nonrandom_meaningful
- comparison_result: not_better
- reasoning:
  - Improved metrics: remap_to_noop_share, usable_samples
  - Worsened metrics: warnings_count, class_imbalance_ratio, inactive_branch_anomaly_share, production_actions_survived_share
  - Decision is based only on adapted/validated data-level outcomes, not on teacher training duration or checkpoint origin.

