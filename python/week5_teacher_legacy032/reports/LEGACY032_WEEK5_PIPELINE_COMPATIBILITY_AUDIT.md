# LEGACY032 Week 5 Pipeline Compatibility Audit

Date: 2026-05-01
Author: GitHub Copilot (static code/config audit only)

## Scope and constraints
- Objective: compatibility audit of existing Week 5 teacher/export/adaptation pipeline for trained Legacy032 3M teacher.
- This audit does not run training, does not run 5M, and does not perform code modifications.
- This audit does not make direct weight transfer claims.
- This audit does not claim semantic parity between Gym-μRTS and Unity.

## Current teacher (audited artifact)
- Pipeline/runtime family: legacy032 / gym_microrts==0.3.2
- Active workspace: python/week5_teacher_legacy032/
- Run ID: legacy032_24x24_teacher_main_20260430T130208Z
- Checkpoint:
  - python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/agent_final.pt
- Metadata:
  - python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/model_metadata.json

## Contract snapshot (from model metadata)
Source: python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/model_metadata.json
- architecture_name: legacy032_resolution_aware_gridnet_v1
- observation_space: [24,24,27]
- action_space_nvec: [576,6,4,4,4,4,7,49]
- gridmode_expected_nvec: [576,6,4,4,4,4,7,49]
- unity_v2_branch_sizes: [6,4,4,4,4,7,49]
- attack_target_semantics: local_7x7_49

## Target Unity v2 contract (reference)
- Observation per sample: [576,27]
- Action per sample: [576,7]
- Branch sizes: [6,4,4,4,4,7,49]

## Historical v1 contract (not allowed for this transfer)
- Branch sizes: [6,4,4,4,4,4,9]
- produce_unit_type: 4
- attack_target: 3x3 / 9

## Audit coverage
Checked:
- python/week5_teacher_legacy032/
- python/week5_teacher_legacy032/scripts/
- python/week5_teacher/
- python/week5_teacher/adapt_teacher_dataset.py
- python/week5_teacher/day4_dataset_adapter.py
- python/week5_teacher/validate_adapted_dataset.py
- python/week5_teacher/build_bc_ready_dataset_day6.py

## Findings

### 1) Reusable Week 5 pipeline parts
1. Day 4 core adapter engine is reusable with v2 mode.
   - File: python/week5_teacher/day4_dataset_adapter.py
   - Evidence: dual contracts defined; v2 constant exists (`V2_GRIDNET_COMPATIBLE_BRANCH_SIZES = (6,4,4,4,4,7,49)`), conversion logic supports v2 branch routing.
2. Day 4 CLI wrapper is reusable conditionally.
   - File: python/week5_teacher/adapt_teacher_dataset.py
   - Condition: must explicitly pass `--target-action-contract v2_gridnet_compatible`.
3. Legacy032 checkpoint metadata is already aligned with v2 branch layout at teacher head level.
   - File: python/week5_teacher_legacy032/teacher_models/.../model_metadata.json
   - Evidence: `action_space_nvec` and `unity_v2_branch_sizes` include [6,4,4,4,4,7,49].

### 2) Parts tied to old v1 contract [6,4,4,4,4,4,9]
1. Day 4 CLI default still targets v1.
   - File: python/week5_teacher/adapt_teacher_dataset.py
   - Evidence: `--target-action-contract` default = `v1_mvp`.
2. Day 5 validator is hardwired to v1 branch sizes.
   - File: python/week5_teacher/validate_adapted_dataset.py
   - Evidence:
     - `EXPECTED_ACTION_BRANCH_SIZES = (6, 4, 4, 4, 4, 4, 9)`
     - attack-channel allowed values built for 9-target encoding (`OBS_ATTACK_ALLOWED_VALUES ... /9`).
3. Day 6 BC packager is hardwired to v1 branch sizes.
   - File: python/week5_teacher/build_bc_ready_dataset_day6.py
   - Evidence:
     - `EXPECTED_BRANCH_SIZES = (6, 4, 4, 4, 4, 4, 9)`
     - manifest/split metadata reuse this constant as canonical target branch sizes.

### 3) Scripts that must not be run as-is for Legacy032->Unity v2 transfer
1. python/week5_teacher/adapt_teacher_dataset.py
   - Reason: default contract is v1; unsafe if launched without explicit v2 flag.
2. python/week5_teacher/validate_adapted_dataset.py
   - Reason: strict checks expect v1 branch sizes and v1-style attack value set.
3. python/week5_teacher/build_bc_ready_dataset_day6.py
   - Reason: packaged output labels branch sizes as v1.
4. python/week5_teacher/run_teacher_rollout.py (for this specific teacher checkpoint)
   - Reason: loader scope is SB3 checkpoint loading (`--policy-algorithm` ppo/a2c/dqn), while current Legacy032 teacher artifact is PyTorch `agent_final.pt` from custom legacy pipeline.

### 4) Hardcoded [6,4,4,4,4,4,9] locations
1. python/week5_teacher/build_bc_ready_dataset_day6.py
   - `EXPECTED_BRANCH_SIZES = (6, 4, 4, 4, 4, 4, 9)`
2. python/week5_teacher/validate_adapted_dataset.py
   - `EXPECTED_ACTION_BRANCH_SIZES = (6, 4, 4, 4, 4, 4, 9)`
3. python/week5_teacher/day4_dataset_adapter.py
   - `V1_MVP_BRANCH_SIZES = (6, 4, 4, 4, 4, 4, 9)` (supported legacy mode, not removed)
4. python/week5_teacher/adapt_teacher_dataset.py
   - CLI help/default path states v1 contract mode as default.

### 5) Existing v2 [6,4,4,4,4,7,49] support
1. python/week5_teacher/day4_dataset_adapter.py
   - `V2_GRIDNET_COMPATIBLE_BRANCH_SIZES = (6, 4, 4, 4, 4, 7, 49)`
   - branch-aware conversion supports v2 contract path.
2. python/week5_teacher/adapt_teacher_dataset.py
   - accepts `--target-action-contract v2_gridnet_compatible`.
3. python/week5_teacher_legacy032/.../model_metadata.json
   - includes `unity_v2_branch_sizes` and v2-compatible `action_space_nvec`.
4. python/week5_teacher_legacy032/scripts/README.md
   - explicitly references planned adaptation target `[6,4,4,4,4,7,49]`.

### 6) Missing Legacy032-specific scripts (gap list)
Current scripts directory does not contain Stage 6/7 operational bridge scripts (only planned in docs).
Missing now:
1. python/week5_teacher_legacy032/scripts/export_teacher_rollout_legacy032.py
   - Needed to export raw episodes from Legacy032 checkpoint (`agent_final.pt`) into Day 3-like raw dataset schema.
2. python/week5_teacher_legacy032/scripts/adapt_legacy032_to_unity_v2.py
   - Needed as explicit v2-first wrapper around Day 4 adaptation flow (no v1 default ambiguity).
3. python/week5_teacher_legacy032/scripts/validate_adapted_dataset_legacy032_v2.py (or equivalent v2-safe wrapper)
   - Needed to avoid using v1-hardcoded Day 5 validator as-is.
4. python/week5_teacher_legacy032/scripts/build_bc_ready_dataset_legacy032_v2.py (or equivalent v2-safe wrapper)
   - Needed to avoid v1-hardcoded Day 6 branch-size labeling.

## Compatibility decision
- As-is Week 5 pipeline execution for Legacy032->Unity v2 transfer: NO-GO.
- Conditional reuse decision: GO only for selected components under strict constraints:
  - Use Day 4 adapter core with explicit `v2_gridnet_compatible` contract.
  - Do not use Day 5/Day 6 scripts until v2-safe Legacy032-specific equivalents are introduced.
  - Do not route Legacy032 checkpoint through SB3-only rollout loader.

## Safety statements (mandatory)
- Direct weight transfer claim: PROHIBITED at this stage.
- Semantic parity claim (Gym-μRTS vs Unity): PROHIBITED at this stage.

## Practical reuse map
- Reuse now (with constraints):
  - day4_dataset_adapter.py core conversion logic (v2 mode only).
- Reuse with caution:
  - adapt_teacher_dataset.py only when `--target-action-contract v2_gridnet_compatible` is explicitly set.
- Do not reuse as-is for this migration step:
  - validate_adapted_dataset.py
  - build_bc_ready_dataset_day6.py
  - run_teacher_rollout.py for legacy032 checkpoint loading path

## Final audit verdict
- Final verdict for current step objective: COMPLETED.
- Decision: NO-GO for full end-to-end execution as currently wired; partial GO for constrained reuse of Day 4 adapter engine only.
