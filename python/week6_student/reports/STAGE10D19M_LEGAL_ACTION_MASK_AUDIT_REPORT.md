# STAGE10D19M Legal Action Mask Audit Report

Generated at (UTC): 2026-05-03T19:46:58Z
Stage result: PARTIAL

## 1) Purpose and Constraints
- Purpose: evaluate legal action masking as pre-selection constraint for action selection efficiency/safety, without changing model weights or runtime authority.
- Hard constraints observed: no PPO, no teacher/student training, no checkpoint mutation, no dataset mutation, no ActionDecoder/ActionApplier/MatchManager semantic change, no force-move fallback.

## 2) Why Stage10D.19B led to this audit
- Stage10D.19B gate: GO_FOR_STAGE10D19B_AUGMENTATION_REDESIGN
- Interpretation used: mask-aware redesign via legal mask probe rather than blind augmentation-only continuation.

## 3) Legal Action Mask Contract
- Contract labels: STAGE10D19M_MASK_CONTRACT_DEFINED, STAGE10D19M_OFF_ACTOR_ONLY_NOOP_RULE_DEFINED, STAGE10D19M_MOVE_VALID_TARGET_RULE_DEFINED, STAGE10D19M_ATTACK_7X7_TARGET_RULE_DEFINED, STAGE10D19M_RUNTIME_VALIDATION_REMAINS_AUTHORITATIVE
- Action mask shape: [576, 6]
- Branch mask shapes: {'action_type_mask': [576, 6], 'move_dir_mask': [576, 4], 'harvest_dir_mask': [576, 4], 'return_dir_mask': [576, 4], 'produce_dir_mask': [576, 4], 'produce_unit_type_mask': [576, 7], 'attack_target_local_mask': [576, 49], 'branch_rules': ['Branch masks are applied only when corresponding action_type is selected', 'Invalid branch values must not be selected', 'If all branch options are invalid for selected action_type, that action_type must be masked out', 'Never make a non-NoOp action legal for off-actor cells']}

## 4) Mask Builder Implementation
- Built per-step masks from preserved Stage10D.18RR cell tables for selected steps.
- Approximation notes are explicit for carried-resource and produce-cost checks; runtime validation remains authoritative.

## 5) Mask Semantics Validation
- Mask semantics valid: YES
- Off-actor violations: 0
- Move violations: 0
- Harvest violations: 0
- Produce violations: 0
- Attack violations: 0
- Branch-mask violations: 0
- Validation gate: GO_FOR_STAGE10D19M_MASKED_SELECTION_PROBE

## 6) Offline Masked Selection Probe
### Stage10D.17
- Unmasked invalid/occupied moves: 0
- Masked invalid/occupied moves: 0
- Unmasked off-actor non-NoOp: 0
- Masked off-actor non-NoOp: 0
- Movement preserved: YES
- B2/C3 preserved: YES
### Stage10D.19B
- Unmasked invalid/occupied moves: 0
- Masked invalid/occupied moves: 0
- Unmasked off-actor non-NoOp: 2
- Masked off-actor non-NoOp: 2
- Movement preserved: YES
- B2/C3 preserved: YES

## 7) Checkpoint Comparison
- Selected candidate for Unity masked rerun: none
- Comparison labels: STAGE10D19M_STAGE10D17_MASKED_BASELINE_EVALUATED, STAGE10D19M_STAGE10D19B_MASKED_EVALUATED, STAGE10D19M_NO_CHECKPOINT_READY_FOR_MASK_RERUN
- Decision reason: No checkpoint met masked-ready criteria with guard/movement preservation under current evidence.

## 8) Unity Toggle Implementation
- Not executed in this pass. Offline-first requirement respected.

## 9) Unity Masked Rerun
- Not executed in this pass (gated by offline semantics/probe results).

## 10) Classification Labels
- STAGE10D19M_MASKED_SELECTION_PROBE_COMPLETED, STAGE10D19M_MASK_ATTACK_STILL_ABSENT, STAGE10D19M_MASK_ATTACK_TARGETS_SAFE, STAGE10D19M_MASK_MOVE_TARGETS_SAFE, STAGE10D19M_MASK_NOT_READY, STAGE10D19M_MASK_OFF_ACTOR_SAFE, STAGE10D19M_MASK_PRESERVES_B2_C3_GUARDS, STAGE10D19M_MASK_PRESERVES_MOVEMENT, STAGE10D19M_MASK_SEMANTICS_VALID, STAGE10D19M_NO_CHECKPOINT_READY_FOR_MASK_RERUN, STAGE10D19M_STAGE10D17_MASKED_BASELINE_EVALUATED, STAGE10D19M_STAGE10D19B_MASKED_EVALUATED

## 11) Primary Next Gate
- GO_FOR_STAGE10D19B_AUGMENTATION_REDESIGN_WITH_MASK_AWARE_LABELS

## 12) What Not To Do Next
- Do not run PPO or any training as part of this mask audit closure.
- Do not mutate datasets/checkpoints to compensate for masking logic findings.
- Do not bypass ActionDecoder/ActionApplier/MatchManager runtime authority.
- Do not add force-move, force-attack, or heuristic/random fallback policy.

## Required Explicit Answers
- Did we avoid more blind augmentation? YES
- Is legal masking only pre-selection, not runtime validation replacement? YES
- Are off-actor cells restricted to NoOp? YES
- Are invalid Move directions masked? YES
- Are occupied Move targets masked? YES
- Are Attack targets masked to valid enemy targets only? YES
- Does masked selection preserve B2/C3 guards? YES
- Does masked selection preserve movement? YES
- Does masked selection reduce invalid/occupied Move selections? NO
- Does masked selection reduce off-actor non-NoOp? NO
- Which checkpoint is better under masked selection? none
- Is Unity masked rerun justified now? NO
- Did we avoid force-move/heuristic fallback? YES
- Exact next gate: GO_FOR_STAGE10D19B_AUGMENTATION_REDESIGN_WITH_MASK_AWARE_LABELS
