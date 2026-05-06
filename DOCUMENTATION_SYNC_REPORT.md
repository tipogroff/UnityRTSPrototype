# DOCUMENTATION_SYNC_REPORT

Date: 2026-04-29
Scope: Repository-wide documentation sync against current Unity/Python code contract.

## Current Canonical Pointers (2026-05-06)

- PIPELINE_AUDIT_WEEK5_WEEK6.md
- CURRENT_PIPELINE_RUNBOOK.md

These are the primary current interpretation documents for Week5/Week6 pipeline state.
If older docs conflict, treat them as historical unless they are explicitly marked current canonical.

## 1. Confirmed Source-of-Truth Contract (from code)

### Unity action contract (confirmed)
- Source: `Assets/Scripts/ML/ActionContract.cs`
- Per-cell MultiDiscrete branches: 7
- Branch sizes: `[6,4,4,4,4,7,49]`
- Branch order:
  - `action_type`
  - `move_dir`
  - `harvest_dir`
  - `return_dir`
  - `produce_dir`
  - `produce_unit_type`
  - `attack_target` / `attack_target_local`
- Attack target indexing: local 7x7 (`0..48`, center `24`)
- Total flat action size: `576 * 78 = 44928`

### Unity runtime/mask/decode alignment (confirmed)
- Sources:
  - `Assets/Scripts/ML/ActionDecoder.cs`
  - `Assets/Scripts/ML/ActionApplier.cs`
  - `Assets/Scripts/ML/ActionMaskBuilder.cs`
  - `Assets/Scripts/ML/ActionContractMappings.cs`
- Contract-level produce mapping uses 7 slots (`Resource..Ranged`), with runtime validity gated by actor/building semantics.
- Runtime validation remains authoritative in `ActionApplier`/`MatchManager`; mask is pre-sampling only.

### Python student-side contract (confirmed)
- Source: `python/week6_student/student_branch_contract.py`
- `EXPECTED_BC_BRANCH_SIZES = (6, 4, 4, 4, 4, 7, 49)`
- `ACTION_CONTRACT_VERSION = "v2_gridnet_compatible"`
- Inference adapter uses same v2 branch sizes:
  - Source: `python/week6_student/student_inference_adapter.py`

## 2. What Was Updated

## A) Core spec/runbook updates
- `WEEK3/WEEK3_COMPATIBILITY_GAP_LIST.md`
  - Gap 3 (3x3 attack reduction) and Gap 5 (reduced produce types) moved to resolved/superseded framing.
  - Added current-status update for v2 contract.
- `WEEK3/WEEK3_CONTRACT_SPEC.md`
  - Marked as historical Week 3 baseline.
  - Added explicit current-status override to v2 contract.
- `IMPLEMENTATION_PLAN.md`
  - Added current-status section describing active transfer pipeline and current v2 contract.

## B) Week 6 pipeline docs synchronized to v2
- `WEEK6/WEEK6_DAY1_BC_TRAINING_CONTRACT.md`
- `WEEK6/WEEK6_DAY2_BC_LOOP_SUMMARY.md`
- `WEEK6/WEEK6_DAY3P5_BRANCH_CONTRACT_AND_WIRING_PREP.md`
- `WEEK6/WEEK6_DAY3_STUDENT_ARCHITECTURE_AND_TRANSFER.md`
- `WEEK6/WEEK6_DAY4_STUDENT_INFERENCE_DRYRUN.md`
- `WEEK6/DAY2_STUDENT_INPUT_SOURCE.md`

Main corrections:
- Replaced stale `[6,4,4,4,4,4,9]` claims as current-state with v2 `[6,4,4,4,4,7,49]` where documents are active.
- Corrected Day 4 `action_flat_size` to `44928` and related logits shapes (`produce=7`, `attack=49`).
- Preserved v1 references only as historical baseline context.

## C) Week 5 teacher/adaptation docs updated
- `python/week5_teacher/README.md`
- `python/week5_teacher/ADAPTER_DAY4.md`
- `WEEK5/WEEK5_TEACHER_PIPELINE_SPEC.md`
- `WEEK5/BC_READY_DATASET_DAY6.md`
- `WEEK5/NEW_TEACHER_WEEK5_PIPELINE_SUMMARY.md`
- `WEEK5/PREFERRED_TEACHER_BASELINE_UPDATE.md`

Main corrections:
- Added current-status notes and historical labeling for v1-era reports.
- Documented that old v1 conversion-pressure metrics are not directly transferable to v2 without rerun.
- Clarified adapter supports both v1 and v2 target contracts, and that current Unity-aligned target is v2.

## D) Additional historical/superseded labeling to avoid false-current reads
- `WEEK3/WEEK3_OBSERVATION_AND_ACTION_SUMMARY.md`
- `WEEK3/WEEK3_DAY4_SUMMARY.md`
- `WEEK3/WEEK3_DAY7_SUMMARY.md`
- `WEEK4/WEEK4_DAY5_ATTACK_TARGET_SUMMARY.md`
- `WEEK5R/UNITY_ACTION_CONTRACT_V2_MIGRATION_PLAN.md`
- `WEEK5R/GRIDNET_ACTION_CONTRACT_V2_MIGRATION_PLAN.md`

## E) Comment-only code clarifications (no logic changes)
- `Assets/Scripts/ML/ActionApplier.cs`
- `Assets/Scripts/ML/ActionMaskBuilder.cs`
- `Assets/Scripts/Gameplay/Combat/CombatResolver.cs`

Updated stale comments that still described local 3x3/Chebyshev<=1 as current behavior.

## 3. Outdated Claim Categories Found and Addressed

- Old attack target contract as current (`3x3`, `0..8`) in active docs.
- Old target branch layout as current (`[6,4,4,4,4,4,9]`) in active docs.
- Reduced production type assumptions presented as unresolved/current blockers.
- Old Day 4 inference output size (`20160`) in Week 6 dry-run doc.
- v1-era Week 5 metrics lacking historical caveat for v2 comparability.

## 4. Remaining Code/Doc Mismatch and Migration TODOs

These were not code-changed in this task (by scope), but are now documented as known migration items:

- `python/week5_teacher/build_bc_ready_dataset_day6.py`
  - Hardcodes `EXPECTED_BRANCH_SIZES = (6,4,4,4,4,4,9)` (v1).
- `python/week5_teacher/validate_adapted_dataset.py`
  - Hardcodes `EXPECTED_ACTION_BRANCH_SIZES = (6,4,4,4,4,4,9)` and v1 attack-channel normalization assumptions.
- `python/week5_teacher/adapt_teacher_dataset.py`
  - Supports v2 mode, but default CLI target contract is still `v1_mvp`.
- `python/week6_student/student_bc_model_minimal.py`
  - Head sizes still coded as v1 (`produce=4`, `attack=9`) while shared student branch contract is v2.

Interpretation:
- Repository has mixed v1/v2 tooling strata.
- Active Unity/runtime + main Week 6 branch-contract artifacts are v2.
- Some Week 5 packaging/validation and minimal-model paths still require explicit migration/rerun strategy.

## 5. Validation Steps Recommended After This Documentation Sync

1. Regenerate Week 5 adapted + BC-ready artifacts with explicit v2 target mode and record new manifest.
2. Re-run Week 5 validation with a v2-aware validator path (or migrate existing validator constants first).
3. Re-run Week 6 student dry run against v2-consistent BC artifacts and checkpoint family.
4. Recompute/remap comparison metrics (`remap_to_noop_share`, `production_actions_survived_share`, `semantic_weakening_share`) under v2 before using them in current-state conclusions.

## 6. Claims Policy Applied

The sync intentionally avoids false claims:
- No claim of full semantic parity with Gym-μRTS.
- No claim that direct weight transfer is automatically solved.
- No claim that adapter/BC path is obsolete.

Current accepted wording:
- Structural action-space mismatch is substantially reduced.
- Branch layout is now closer to legacy Gym/Gridnet teacher layout.
- Transfer remains adapter/BC mediated and requires semantic/runtime validation.
