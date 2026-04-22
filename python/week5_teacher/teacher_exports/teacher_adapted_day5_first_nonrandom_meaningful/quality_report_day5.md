# Day 5 Adapted Dataset Validation Summary

- Adapted batch dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher\teacher_exports\teacher_adapted_day5_first_nonrandom_meaningful
- Validation status: pass
- Hard failures: 0
- Warnings: 4

## Quality Snapshot

- Usable samples: 2000
- Dropped samples: 0
- Conversion loss share: 0.000000
- Remap-to-noop share: 0.199653
- Semantic weakening share: 1.000000
- Observation signal loss share: 0.000000
- Usable vs dropped ratio: 2000.000000
- Inactive branch anomaly share: 0.045139
- Inactive branch warning severity: medium

## Action Distribution

- action_type=0: 428000
- action_type=1: 182000
- action_type=2: 196000
- action_type=3: 204000
- action_type=4: 120000
- action_type=5: 22000
- Imbalance ratio (max/min non-zero share): 19.454545

## Weak Spots

- High remap-to-noop volume indicates semantic weakening pressure from source-to-target action gap.
- Produce actions survival share is limited; conversion keeps only MVP subset semantics.
- Attack action share is low after conversion and may weaken combat supervision density.
- Action class imbalance is strong and may require weighting/oversampling in BC.
- Inactive-branch anomalies are medium severity and should be monitored before BC.

## Top Problematic Episodes

- episode_id=0, score=9.2222, remap_share=0.199653, weakened_share=1.000000, dropped_share=0.000000

## Warnings

- observation.categorical_soft_sum.unit_type: categorical_soft slice sum exceeds 1; potential multi-hot overlap
- observation.categorical_soft_sum.current_action: categorical_soft slice sum exceeds 1; potential multi-hot overlap
- action.inactive_branch_nonzero: inactive branches contain non-zero values (decoder should ignore them, but this is non-canonical)
- quality.semantic_weakening: conversion includes remap-to-noop events (semantic weakening present)

## Scope

- This validator proves contract-level consistency and sanity metrics only.
- It does not prove full Gym<->Unity semantic parity and does not replace BC evaluation.

## BC Readiness Interpretation

- Proves: Adapted dataset was checked for contract-level structural consistency against explicit Day5 validation policy.
- Proves: Hard contract failures and soft warnings are separated and reproducible.
- Proves: Batch-level and limited episode-level diagnostics are available for next decision point.
- Does not prove: No BC training quality guarantee or policy performance guarantee is established.
- Does not prove: No full Gym<->Unity semantic parity is proven by this validator.
- Does not prove: No Unity runtime behavior equivalence claim is made.
- Next decision option: Run the same validator on newer stronger adapted teacher batches.
- Next decision option: If hard failures remain, fix adapter/contract assumptions before BC smoke.
- Next decision option: If hard failures are resolved, proceed with a short BC smoke in a separate stage.
