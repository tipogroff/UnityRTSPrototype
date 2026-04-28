# Unity Action Contract v2 Migration Plan (Gridnet-compatible)

Status: Step 1 completed, Step 2 (decoder/mask compatibility) implemented.

Scope note:
- Python-side v2 adapter path is implemented.
- Unity-side v2 runtime is not implemented yet.
- No Unity parity claim is valid at this stage.
- BC-ready packaging is blocked until Unity-side v2 runtime migration is complete.

## 1) Motivation

Target alignment goals:
- Align Unity action contract with Gym/Gridnet branch layout [6,4,4,4,4,7,49].
- Reduce semantic weakening caused by v1 truncation and remap behavior.
- Support 7x7 attack target selection (49 local indices) for commanded attacks.
- Support full produce branch size 7 for Gridnet-compatible tensor shape.

Observed v1 issue context (from Python-side analysis):
- v1 stochastic Gridnet 100k batch dropped 20.7585% cell-actions in remap_to_noop due to:
  - attack_target outside local 3x3: 160,414 cells
  - produce_type >= 4: 84,463 cells
- v2 adapter outcomes (Python side):
  - remap_to_noop_share = 0
  - semantic_weakening_share = 0
  - effective non-NoOp share = 83.24%

## 2) Current v1 contract (Unity-side)

Current target:
- [6,4,4,4,4,4,9]

Confirmed in Unity:
- Produce branch size = 4
- Attack target branch size = 9 (local 3x3)

Primary source:
- Assets/Scripts/ML/ActionContract.cs
  - SIZE_PRODUCE_UNIT_TYPE = 4
  - SIZE_ATTACK_TARGET = 9
  - AttackOffsets currently contains 9 offsets (3x3 around center)

## 3) Target v2 contract

Target layout:
- [6,4,4,4,4,7,49]

Branch deltas:
- produce_unit_type: 4 -> 7
- attack_target_local: 9 -> 49 (7x7 local window)

## 4) Files/classes to inspect and likely modify

Core action contract and mapping:
- Assets/Scripts/ML/ActionContract.cs
- Assets/Scripts/ML/ActionContractMappings.cs

Decode/mask/apply pipeline:
- Assets/Scripts/ML/ActionDecoder.cs
- Assets/Scripts/ML/ActionMaskBuilder.cs
- Assets/Scripts/ML/ActionApplier.cs

Heuristic and debug adapters:
- Assets/Scripts/ML/HeuristicPolicyAdapter.cs

Bridge/inference shape checks:
- Assets/Scripts/ML/Week6StudentPolicyAdapter.cs
- Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs

Related type definitions and observation coupling:
- Assets/Scripts/Core/UnitType.cs
- Assets/Scripts/ML/ObservationBuilder.cs
- Assets/Scripts/ML/ObservationContract.cs

Tests and smoke scripts (Unity-side):
- Assets/Scripts/ML/ActionMaskBuilderSmokeTest.cs
- Assets/Scripts/ML/ActionApplierSmokeTest.cs
- Assets/Scripts/ML/Day5AttackTargetObservationSmokeTest.cs
- Assets/Scripts/ML/BarracksHeavyRangedSmokeTest.cs
- Assets/Scripts/ML/Day6PipelineSmokeTest.cs

ML-Agents BehaviorParameters note:
- Direct BehaviorParameters usage was not found in Assets C# scan.
- Current pipeline appears to use custom bridge + contract validation, not direct ML-Agents Agent branch config in inspected code.
- If BehaviorParameters are configured only in scene/prefab not present in repository scope, include them in implementation-time verification checklist.

## 5) Index mapping for 7x7 attack_target_local

Target indexing spec:
- index domain: 0..48
- center index: 24

Decode formulas:
- row = idx // 7
- col = idx % 7
- dx = col - 3
- dy = row - 3

Suggested Unity mapping convention:
- local index increments row-major (top-left to bottom-right) across 7x7.
- center cell (self) remains representable at idx=24 and should be mask-disabled for attack actions.

## 6) Runtime validation requirements

Authoritative validity remains in ActionApplier:
- Action masks may expose up to 49 local attack indices.
- ActionApplier remains final authority on acceptance/rejection.

Required behavior for invalid targets:
- Any out-of-range local index decode must fail safely.
- Any out-of-bounds absolute target must be rejected safely.
- Any non-enemy/invalid attack target must be rejected safely (or explicit NoOp fallback policy).

Compatibility safety:
- Decoder must not crash on branch values in new bounds.
- Invalid/out-of-range values must remain deterministic and diagnosable.

## 7) Produce mapping requirements

Branch size policy:
- Keep produce branch width = 7 for contract compatibility.

Important distinction (correct v2 framing):
- All 7 UnitType/world object categories already exist in Unity observation/world surface:
  - Resource, Base, Barracks, Worker, Light, Heavy, Ranged.
- Not all 7 are valid outcomes of Produce action in every context.
- Produce validity is context-dependent by game rules and actor type.

Gym/Gridnet-compatible ordering target for produce branch indices:
- 0 Resource  -> exists as map object, mask-disabled for Produce, runtime reject if submitted
- 1 Base      -> exists as building, mask-disabled while building new Base is not supported
- 2 Barracks  -> valid only for Worker build-barracks context
- 3 Worker    -> valid for Base production
- 4 Light     -> valid for Barracks production
- 5 Heavy     -> valid for Barracks production
- 6 Ranged    -> valid for Barracks production

Context-valid produce mapping policy:
- Base actor:
  - allow Worker
- Barracks actor:
  - allow Light / Heavy / Ranged
- Worker actor:
  - allow Barracks build action
- Resource actor:
  - no Produce
- Base build action:
  - disabled while rule set does not allow building a new Base

Interpretation note:
- "not allowed" means "not valid for Produce in this context", not "type missing from Unity".

## 8) Migration risks

Primary risks:
- Student output head shape changes (branch_sizes/action_flat expectations).
- BC-ready dataset and serialized action tensor shape changes.
- Unity-side branch contract consumers must stay synchronized.
- Existing v1 student checkpoints become incompatible with v2 branch shapes.

Secondary risks:
- Attack offset expansion may alter heuristics/debug defaults that currently assume center index 4.
- Observation diagnostics that mention 3x3 semantics may become stale/misleading.
- Tests that implicitly depend on 9-slot attack or 4-slot produce may fail or become invalid.

Release gate constraints:
- No parity claim before Unity-side v2 decode/mask/apply and validation are done.
- No BC-ready packaging before Unity-side v2 runtime migration and tests are green.

## 9) Test plan (to add/update)

Required tests:
- Branch size test
  - Verify ActionContract reports [6,4,4,4,4,7,49].
- Attack index decode test
  - Verify 0..48 mapping and center=24 geometry.
- Mask shape test
  - Verify attack mask vector length 49 and produce mask length 7.
- Produce mask test
  - Verify supported produce values enabled by runtime rules; unsupported remain masked.
- ActionApplier runtime rejection test
  - Verify out-of-range/invalid target and unsupported produce values are rejected safely.
- End-to-end smoke
  - Verify bridge -> decode -> mask-consistency -> apply path works with v2 shape.

Suggested file targets for tests:
- Assets/Scripts/ML/ActionMaskBuilderSmokeTest.cs
- Assets/Scripts/ML/ActionApplierSmokeTest.cs
- Assets/Scripts/ML/Day5AttackTargetObservationSmokeTest.cs
- Assets/Scripts/ML/Day6PipelineSmokeTest.cs
- Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs

## Unity-side assumptions found (exact files, constants, change intent, risk)

1) Assets/Scripts/ML/ActionContract.cs
- Current:
  - SIZE_PRODUCE_UNIT_TYPE = 4
  - SIZE_ATTACK_TARGET = 9
  - AttackOffsets = 9 entries (3x3)
  - ActionFlatSize = 35
- Likely change:
  - SIZE_PRODUCE_UNIT_TYPE -> 7
  - SIZE_ATTACK_TARGET -> 49
  - AttackOffsets -> 49 entries (7x7)
  - ActionFlatSize recalculation (+43 per cell)
- Risk: High

2) Assets/Scripts/ML/ActionContractMappings.cs
- Current:
  - TryMapProducibleUnitType maps only Worker/Light/Heavy/Ranged.
  - TryGetAttackTargetPosition indexes ActionContract.AttackOffsets.
- Likely change:
  - Align produce mapping to Gym/Gridnet 7-type ordering without remap of produce_type>=4.
  - Enforce context-valid Produce routing (mask + runtime) instead of generic unsupported/reserved interpretation.
  - Keep index safety for 0..48 mapping.
- Risk: High

3) Assets/Scripts/ML/ActionDecoder.cs
- Current:
  - TryValidateProduceUnitType bound uses SIZE_PRODUCE_UNIT_TYPE.
  - Attack decode uses SIZE_ATTACK_TARGET and mapping helper.
  - Debug path text references local 3x3.
- Likely change:
  - Update bounds and diagnostics for 7 and 49.
  - Ensure deterministic invalid handling for unsupported produce values.
- Risk: High

4) Assets/Scripts/ML/ActionMaskBuilder.cs
- Current:
  - ProduceUnitTypeMask length uses SIZE_PRODUCE_UNIT_TYPE.
  - AttackTargetLocalMask length uses SIZE_ATTACK_TARGET.
  - BuildAttackMask loops over attack target size.
  - Production rules currently Base->Worker, Barracks->Light/Heavy/Ranged.
- Likely change:
  - Build 7-slot produce mask while preserving runtime-supported subset behavior.
  - Build/validate 49-slot attack mask with 7x7 geometry and range gates.
- Risk: High

5) Assets/Scripts/ML/ActionApplier.cs
- Current:
  - Authoritative rejection path for produce and attack remains active.
  - Production rule currently Base->Worker, Barracks->Light/Heavy/Ranged, Worker special build-barracks path.
  - Comments explicitly document 3x3 limitation.
- Likely change:
  - Keep authoritative rejection semantics with v2 indices.
  - Update produce validation path for widened contract while preserving safe rejection.
- Risk: High

6) Assets/Scripts/ML/HeuristicPolicyAdapter.cs
- Current:
  - Multiple defaults use attackTargetLocal=4 (v1 center).
  - Selection logic assumes current mask lengths but loops by mask length.
- Likely change:
  - Replace center defaults with 24 where semantic center placeholder is needed.
  - Re-check any assumptions in debug formatting/reasoning.
- Risk: Medium

7) Assets/Scripts/Core/UnitType.cs
- Current:
  - UnitType already includes all 7 world/object categories: Resource, Base, Barracks, Worker, Light, Heavy, Ranged.
  - ProducibleUnit enum currently represents 4 unit-production values (Worker/Light/Heavy/Ranged).
- Likely change:
  - Keep/adjust enum and mapping so v2 branch width 7 matches Gym order while Produce validity remains rule/context-driven.
- Risk: Medium-High

8) Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs
- Current:
  - Validates adapter.branch_order and branch_sizes against ActionContract sizes.
- Likely change:
  - Test expectations will auto-follow ActionContract constants, but expected behavior/docs should be updated for v2 semantics.
- Risk: Medium

9) Assets/Scripts/ML/Week6StudentPolicyAdapter.cs
- Current:
  - Validates action_flat_size against ActionContract.TotalActionFlatSize.
- Likely change:
  - Ensure bridge payload and local checks handle new larger flat size.
- Risk: Medium

10) Assets/Scripts/ML/ObservationBuilder.cs and Assets/Scripts/ML/ObservationContract.cs
- Current:
  - attack_target observation channel text and comments describe local 3x3 semantics.
- Likely change:
  - Align documented semantics and normalization assumptions with v2 local 7x7 target space.
- Risk: Medium

11) Smoke tests and diagnostics
- Current:
  - Multiple tests/logs mention 3x3 and 4-slot produce assumptions.
- Likely change:
  - Update tests to v2 branch widths and revised geometry.
- Risk: Medium

## Proposed implementation sequence (after approval)

1. Contract constants and mapping geometry
- ActionContract + AttackOffsets + mapping helper update.

2. Decode and mask compatibility
- ActionDecoder + ActionMaskBuilder update for [6,4,4,4,4,7,49].

3. Runtime authoritative checks
- ActionApplier produce/attack validation updates with safe reject semantics.

4. Bridge and smoke alignment
- Week6 adapters and smoke tests updated for new tensor sizes and diagnostics.

5. Regression and release gates
- Execute full Unity-side smoke set and verify no unsafe accepts.

## Current step completion note

Historical note: at the time this section was first written, the work was
documentation/repository analysis only and no Unity runtime code was modified.

## Implementation Progress

Step 1 status: completed (minimal safe contract step).

Changed files:
- Assets/Scripts/ML/ActionContract.cs
- Assets/Scripts/ML/ActionContractMappings.cs
- Assets/Scripts/ML/ActionContractV2SmokeTest.cs

What was changed in Step 1:
- Contract branch sizes updated to v2 target [6,4,4,4,4,7,49].
- AttackOffsets expanded to 7x7 row-major local window (49 offsets).
- Added explicit v2 produce-index -> UnitType helper in Gym/Gridnet order.
- Added smoke test covering branch sizes, flat sizes, attack mapping, and produce index mapping.

What was intentionally NOT changed in Step 1:
- No deep ActionApplier behavior migration.
- No ActionMaskBuilder full v2 semantic migration.
- No BC pipeline migration.
- No teacher training pipeline changes.

Step 2 status: completed (small-step decoder + mask compatibility).

Changed files:
- Assets/Scripts/ML/ActionDecoder.cs
- Assets/Scripts/ML/ActionMaskBuilder.cs
- Assets/Scripts/ML/HeuristicPolicyAdapter.cs
- Assets/Scripts/ML/ActionMaskBuilderSmokeTest.cs
- Assets/Scripts/ML/ActionDecoderV2SmokeTest.cs

What was changed in Step 2:
- ActionDecoder updated for v2-facing produce-branch commentary and 7x7 attack-target wording.
- ActionDecoder produce branch conversion now uses v2 index mapping helper (Gym/Gridnet UnitType order).
- ActionMaskBuilder produce mask migrated to 7-slot UnitType-order semantics:
  - Base enables Worker at index 3 when runtime conditions are valid.
  - Barracks enables Light/Heavy/Ranged at indices 4/5/6 when runtime conditions are valid.
  - Worker build-barracks slot moved to index 2.
  - Resource (0) and Base (1) stay disabled under current runtime rules.
- ActionMaskBuilder attack mask explicitly keeps center index 24 disabled and iterates full 49-slot window.
- HeuristicPolicyAdapter debug defaults updated for v2 center placeholder index (24), plus v2 produce index selection for produce actions.
- Smoke checks extended:
  - ActionMaskBuilderSmokeTest now includes explicit v2 mask checks (lengths, center disabled, produce slot semantics).
  - Added ActionDecoderV2SmokeTest for attack index decode and produce branch-bound assumptions.

What was intentionally NOT changed in Step 2:
- No deep ActionApplier migration.
- No BC pipeline migration.
- No teacher training pipeline changes.
- No Unity parity claim.

Pending after Step 2:
- ActionApplier full v2 runtime semantics remain pending as a separate authoritative-runtime step.
