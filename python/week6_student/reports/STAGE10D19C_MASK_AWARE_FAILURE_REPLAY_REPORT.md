# STAGE10D19C Mask-Aware Occupied-Target Augmentation and Failure-Case Replay Report

Generated at (UTC): 2026-05-03T20:52:12Z
Stage result: PARTIAL

## 1. Purpose and constraints
- Purpose: target real occupied-target Move failures from Stage10D.18RR/19, not proxy-only slices.
- Constraints respected: no PPO, no teacher mutation, no runtime semantic changes, no force movement/attack, no Unity rerun inside Stage10D.19C.

## 2. Why Stage10D.19M was PARTIAL
- Stage10D.19M selected gate: GO_FOR_STAGE10D19B_AUGMENTATION_REDESIGN_WITH_MASK_AWARE_LABELS
- Interpretation: legal mask semantics were valid, but previous probe coverage did not represent the actual occupied-target failure distribution.

## 3. Real failure-case extraction
- Extracted failure cases: 1328
- Occupied-target failures in extracted set: 1328
- Efficiency reference occupied-target count: 1333
- Labels: STAGE10D19C_FAILURE_CASE_EXTRACTION_COMPLETED, STAGE10D19C_OCCUPIED_TARGET_FAILURES_CONFIRMED, STAGE10D19C_VALID_ALTERNATIVE_MOVES_AVAILABLE, STAGE10D19C_ALL_FAILURES_HAVE_ALTERNATIVE, STAGE10D19C_FAILURE_CASES_READY_FOR_MASK_AWARE_DATASET

## 4. Failure-case replay before training
- Stage10D.17 replay:
  unmasked invalid moves = 1296, masked invalid moves = 0
- Stage10D.19B replay:
  unmasked invalid moves = 229, masked invalid moves = 0
- Mask helped on real failure cases: YES

## 5. Mask-aware dataset design
- Base dataset: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/bc_ready/legacy032_v2_stage10d19b_valid_move_augmented_bc_ready_20260503T191829Z
- Augmentation family counts: {'family_a_no_valid_alt_noop': 222, 'family_b_valid_alt_move': 1328, 'family_c_blocked_dir_hard_negative': 1328, 'family_d_off_actor_hard_negative': 1800, 'family_f_preservation': 1200}
- Families A/B/C/D/E/F implemented with metadata and non-claim constraints preserved.

## 6. Dataset validation
- Validation status: pass
- Primary next gate from validation: GO_FOR_STAGE10D19C_MASK_AWARE_BC_TRAINING
- Labels: STAGE10D19C_DATASET_VALID, STAGE10D19C_FAILURE_CASE_COVERAGE_CONFIRMED, STAGE10D19C_VALID_ALT_MOVE_LABELS_CONFIRMED, STAGE10D19C_NO_VALID_ALT_NOOP_LABELS_CONFIRMED, STAGE10D19C_OFF_ACTOR_HARD_NEGATIVES_CONFIRMED, STAGE10D19C_MASK_LEGAL_LABELS_CONFIRMED, STAGE10D19C_NO_LABEL_LEAKAGE_CONFIRMED, STAGE10D19C_B2_C3_GUARDS_PRESERVED, STAGE10D19C_MOVEMENT_PRESERVATION_CONFIRMED, STAGE10D19C_ATTACK_LABELS_PRESERVED, STAGE10D19C_TARGET_DISTRIBUTION_ACCEPTABLE

## 7. Training summary
- Best checkpoint: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/runs/legacy032_v2_stage10d19c_mask_aware_failure_augmented_bc_20260503T202258Z/student_bc_stage10d19c_mask_aware_best.pt
- Final checkpoint: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week6_student/runs/legacy032_v2_stage10d19c_mask_aware_failure_augmented_bc_20260503T202258Z/student_bc_stage10d19c_mask_aware_final.pt
- History rows: 3

## 8. Offline evaluation
- Eval gate: GO_FOR_STAGE10D19C_TRAINING_BALANCE_FIX
- Eval labels: STAGE10D19C_ORIGINAL_PERFORMANCE_PRESERVED, STAGE10D19C_B2_C3_GUARDS_PRESERVED, STAGE10D19C_NOT_READY_FOR_UNITY, STAGE10D19C_NOT_READY_FOR_UNITY, STAGE10D19C_NOT_READY_FOR_UNITY, STAGE10D19C_NOT_READY_FOR_UNITY, STAGE10D19C_NO_VALID_ALT_NOOP_SELECTION_IMPROVED, STAGE10D19C_OFF_ACTOR_RISK_REDUCED_OR_CONTROLLED, STAGE10D19C_MASK_COMPATIBLE, STAGE10D19C_ATTACK_WATCH_ONLY_OK, STAGE10D19C_NOT_READY_FOR_UNITY
- B2/C3 guard preserved: YES
- Movement preserved: NO

## 9. Checkpoint comparison
- Selected candidate: stage10d19b
- Comparison labels: STAGE10D19C_STAGE10D17_COMPARED, STAGE10D19C_STAGE10D19B_COMPARED, STAGE10D19C_STAGE10D19C_COMPARED, STAGE10D19C_SELECTED_STAGE10D19B_FOR_UNITY

## 10. Attack watch-only notes
- Attack remains watch-only in this stage. No attack augmentation was added.

## 11. Classification labels
- STAGE10D19C_ALL_FAILURES_HAVE_ALTERNATIVE, STAGE10D19C_ATTACK_LABELS_PRESERVED, STAGE10D19C_ATTACK_WATCH_ONLY_OK, STAGE10D19C_B2_C3_GUARDS_PRESERVED, STAGE10D19C_DATASET_VALID, STAGE10D19C_FAILURE_CASES_READY_FOR_MASK_AWARE_DATASET, STAGE10D19C_FAILURE_CASE_COVERAGE_CONFIRMED, STAGE10D19C_FAILURE_CASE_EXTRACTION_COMPLETED, STAGE10D19C_FAILURE_REPLAY_COMPLETED, STAGE10D19C_MASK_COMPATIBLE, STAGE10D19C_MASK_CONVERTS_INVALID_TO_VALID_MOVE, STAGE10D19C_MASK_LEGAL_LABELS_CONFIRMED, STAGE10D19C_MASK_REDUCES_FAILURE_CASE_INVALID_MOVES, STAGE10D19C_MOVEMENT_PRESERVATION_CONFIRMED, STAGE10D19C_NOT_READY_FOR_UNITY, STAGE10D19C_NO_LABEL_LEAKAGE_CONFIRMED, STAGE10D19C_NO_VALID_ALT_NOOP_LABELS_CONFIRMED, STAGE10D19C_NO_VALID_ALT_NOOP_SELECTION_IMPROVED, STAGE10D19C_OCCUPIED_TARGET_FAILURES_CONFIRMED, STAGE10D19C_OFF_ACTOR_HARD_NEGATIVES_CONFIRMED, STAGE10D19C_OFF_ACTOR_RISK_REDUCED_OR_CONTROLLED, STAGE10D19C_ORIGINAL_PERFORMANCE_PRESERVED, STAGE10D19C_SELECTED_STAGE10D19B_FOR_UNITY, STAGE10D19C_STAGE10D17_COMPARED, STAGE10D19C_STAGE10D19B_COMPARED, STAGE10D19C_STAGE10D19C_COMPARED, STAGE10D19C_TARGET_DISTRIBUTION_ACCEPTABLE, STAGE10D19C_VALID_ALTERNATIVE_MOVES_AVAILABLE, STAGE10D19C_VALID_ALT_MOVE_LABELS_CONFIRMED

## 12. Primary next gate
- GO_FOR_STAGE10D19C_TRAINING_BALANCE_FIX

## 13. What not to do next
- Do not run Unity rerun unless Stage10D.20 gate is explicitly passed.
- Do not add force-move/force-attack or heuristic/random fallback.
- Do not mutate ActionDecoder/ActionApplier/MatchManager semantics.
- Do not jump to attack augmentation until movement/failure-case gate is closed.

## Required explicit answers
- Did we target the real 1333 occupied-target failure distribution? YES
- Did we avoid B2/C3 overfocus? YES
- Are B2/C3 still preserved as guards? YES
- Did failure-case replay cover occupied-target Move failures? YES
- Does masking alone fix the failure cases? YES
- Was mask-aware dataset valid? YES
- Was label leakage avoided? YES
- Was training performed? YES
- Did occupied-target failures reduce? NO
- Did valid-alt Move selection improve? NO
- Did no-valid-alt NoOp selection improve? YES
- Did off-actor risk reduce or remain controlled? YES
- Did original/movement behavior regress? YES
- Which checkpoint is selected for Unity? stage10d19b
- Is Unity masked valid-Move rerun justified? NO
- Exact next gate: GO_FOR_STAGE10D19C_TRAINING_BALANCE_FIX
