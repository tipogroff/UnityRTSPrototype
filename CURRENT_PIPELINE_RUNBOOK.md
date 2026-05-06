# CURRENT_PIPELINE_RUNBOOK.md

> STATUS: CURRENT CANONICAL

Updated: 2026-05-06
Scope: authoritative operational runbook for current Week5/Week6 UnityRTSPrototype pipeline.

## 1. Active Contract (Current)

- Observation tensor (Unity runtime contract): [24,24,27]
- Target action branches (per cell): [6,4,4,4,4,7,49]
- Target tensor shape in BC datasets: [N,576,7]
- Action flat size (Unity runtime): 44928
  - per-cell branch sum: 78
  - total cells: 576
  - 576 * 78 = 44928

Authoritative runtime truth remains in ActionApplier / MatchManager / ApplyCommand.
Action mask remains diagnostic or pre-sampling layer and is not runtime authority.

## 2. Active Dataset Lineage

Current active source lineage for handoff:

- python/week5_teacher_legacy032/teacher_exports_bc/day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z

Observed contract in manifest:

- observation_shape_per_sample: [576,27]
- action_shape_per_sample: [576,7]
- branch_sizes: [6,4,4,4,4,7,49]

## 3. Active Student / Checkpoint Lineage (Known)

Week6 student core is v2-aligned and uses v2 branch contract modules:

- python/week6_student/student_branch_contract.py
- python/week6_student/student_bc_contract.py
- python/week6_student/student_bc_loader.py
- python/week6_student/student_architecture_transfer.py
- python/week6_student/student_inference_adapter.py
- python/week6_student/load_student_checkpoint.py

Known active checkpoint families in current repository evidence:

- stage10d8 semantic branch (example: python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_20260503T093718Z)
- stage10d19c mask-aware branch (example: python/week6_student/runs/legacy032_v2_stage10d19c_mask_aware_failure_augmented_bc_20260503T202258Z)

Note: checkpoint selection policy should be governed by one explicit report or registry to avoid drift between diagnostic scenes and reports.

## 4. Current Unity Runtime Path

Current runtime path for student action application:

- Week6StudentPolicyAdapter
- MlPolicyPipelineFacade
- ActionDecoder
- ActionApplier
- MatchManager.ApplyCommand

Runtime authoritative gate remains ActionApplier and MatchManager semantics.

## 5. Stage10D Status

Stage10D tooling under python/week6_student is diagnostic and remediation oriented.
It is not a single canonical production pipeline.

This includes auditing, augmentation, binding verification, mode-isolation analysis, and targeted retraining experiments.

## 6. Deprecated For Current v2 Handoff

These are deprecated for current v2 handoff and must not be presented as current canonical packaging/validation tools:

- python/week5_teacher/validate_adapted_dataset.py (hardcoded v1 branch constants)
- python/week5_teacher/build_bc_ready_dataset_day6.py (hardcoded v1 branch constants)

python/week5_teacher/adapt_teacher_dataset.py supports v2, but its default target mode historically required explicit v2 selection in canonical commands.

## 7. Historical-Only Note (Day2 Source Doc)

- WEEK6/DAY2_STUDENT_INPUT_SOURCE.md is historical baseline context only.
- Do not use it as current canonical source-of-truth for active lineage.

## 8. Explicit Prerequisite For Day4 DryRun Gate

Week6Day4StudentInferenceDryRun remains SKIPPED_CONFIG_REQUIRED until a v2-compatible checkpoint artifact is provided and bound.

Required condition to move to PASS:

- provide and bind a checkpoint artifact compatible with current v2 student contract and expected checkpoint checks.

## 9. Related Canonical Documents

- PIPELINE_AUDIT_WEEK5_WEEK6.md
- CURRENT_PIPELINE_RUNBOOK.md

These two documents are the top-level pointers for current pipeline interpretation.