# STAGE10D.17 Movement Label Augmentation and Post-Production Policy Expansion

## Summary
- Audit primary gate: GO_FOR_STAGE10D17_BUILD_MOVEMENT_AUGMENTATION
- Dataset validation status: pass
- Training selected epoch: 2
- Final Stage10D.17 gate: GO_FOR_STAGE10D18_RUNTIME_BC_REDEPLOY_EVAL

## 1. Movement Label Audit
- Classification labels: MOVE_LABELS_ABSENT, COMBAT_MOVE_LABELS_ABSENT, ATTACK_LABELS_UNDERREPRESENTED, PRODUCED_UNIT_MOVE_GAP_CONFIRMED, STAGE10D17_MOVEMENT_AUGMENTATION_REQUIRED
- Train actor Move before/after: 0 -> 0
- Validation actor Move before/after: 0 -> 0

## 2. Movement Augmented Dataset Build
- Original train/val: 80692 / 8985
- Augmented train/val: 2121 / 521
- Merged train/val: 82813 / 9506
- Family counts: {'family1_stage10d16_runtime': 1042, 'family3_synthetic_rule_valid_move': 601, 'family4_rally_advance_from_base': 599, 'family5_negative_controls': 400}
- Move by unit: {'Worker': 2242}
- Move by direction: {'east': 2053, 'north': 1, 'south': 187, 'west': 1}

## 3. Dataset Validation
- Labels: MOVEMENT_AUGMENTED_DATASET_VALID, MOVE_TARGETS_PRESENT, MOVE_TARGETS_VALID, MOVE_BRANCH_BOUNDS_VALID, MOVE_TARGET_CELLS_VALID, NO_MOVEMENT_LABEL_LEAKAGE_CONFIRMED, HARVEST_PRODUCE_TARGETS_PRESERVED, NEGATIVE_CONTROLS_PRESENT, TARGET_DISTRIBUTION_ACCEPTABLE
- Branch bounds valid: True
- Leakage confirmed absent: True
- Target distribution acceptable: True

## 4. Supervised Fine-Tune
- Movement augmented val move recall: 46.64%
- Movement augmented val move-dir accuracy: 99.50%
- Stage10D16 replay move success: 100.00%
- Original val actor action-type accuracy: 100.00%
- Worker harvest recall: 100.00%
- Base produce recall: 100.00%
- True raw B2 p_harvest vs p_noop: 99.00% vs 0.00%
- True raw C3 p_produce vs p_noop: 98.72% vs 0.00%

## 5. Offline Eval
- Block A original validation actor acc: 100.00%
- Block B true raw off-actor non-noop: 0
- Block C validation move recall: 46.64%
- Block C validation move-dir accuracy: 99.50%
- Block D validation replay move success: 100.00%

## 6. Snapshot Replay (Optional)
- Validation replay samples: 201
- Validation replay move success: 100.00%
- Validation replay off-actor non-noop: 0

## 7. Constraints and Non-Claims
- No PPO used
- No teacher checkpoint mutation
- No runtime ActionDecoder/ActionApplier semantics mutation
- No runtime movement forcing

## 8. Final Decision
- Selected next gate: GO_FOR_STAGE10D18_RUNTIME_BC_REDEPLOY_EVAL
- Gate reasons: All Stage10D.17 gates passed
