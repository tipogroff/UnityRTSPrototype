# Day 5 Adapted Dataset Validation Summary

- Adapted batch dir: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\WEEK5R\teacher_exports_v2\teacher_adapted_gridnet_200k_det_ab_v2_20260428T000000Z
- Validation status: hard_fail
- Hard failures: 1
- Warnings: 8

## Quality Snapshot

- Usable samples: 2048
- Dropped samples: 0
- Conversion loss share: 0.000000
- Remap-to-noop share: 0.000000
- Semantic weakening share: 0.000000
- Observation signal loss share: 0.000000
- Usable vs dropped ratio: 2048.000000
- Inactive branch anomaly share: 0.000000
- Inactive branch warning severity: low

## Action Distribution

- action_type=0: 1179372
- action_type=1: 248
- action_type=2: 8
- action_type=3: 0
- action_type=4: 20
- action_type=5: 0
- Imbalance ratio (max/min non-zero share): 147421.500000

## Weak Spots

- Attack action share is low after conversion and may weaken combat supervision density.
- Action class imbalance is strong and may require weighting/oversampling in BC.

## Top Problematic Episodes

- episode_id=0, score=2.0000, remap_share=0.000000, weakened_share=0.000000, dropped_share=0.000000
- episode_id=1, score=2.0000, remap_share=0.000000, weakened_share=0.000000, dropped_share=0.000000
- episode_id=2, score=2.0000, remap_share=0.000000, weakened_share=0.000000, dropped_share=0.000000
- episode_id=3, score=2.0000, remap_share=0.000000, weakened_share=0.000000, dropped_share=0.000000

## Hard Failures

- metadata.action_branch_contract: conversion_report target_action_branch_sizes mismatch

## Warnings

- observation.categorical_soft_sum.unit_type: categorical_soft slice sum exceeds 1; potential multi-hot overlap
- observation.categorical_soft_sum.current_action: categorical_soft slice sum exceeds 1; potential multi-hot overlap
- observation.categorical_soft_sum.unit_type: categorical_soft slice sum exceeds 1; potential multi-hot overlap
- observation.categorical_soft_sum.current_action: categorical_soft slice sum exceeds 1; potential multi-hot overlap
- observation.categorical_soft_sum.unit_type: categorical_soft slice sum exceeds 1; potential multi-hot overlap
- observation.categorical_soft_sum.current_action: categorical_soft slice sum exceeds 1; potential multi-hot overlap
- observation.categorical_soft_sum.unit_type: categorical_soft slice sum exceeds 1; potential multi-hot overlap
- observation.categorical_soft_sum.current_action: categorical_soft slice sum exceeds 1; potential multi-hot overlap

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
