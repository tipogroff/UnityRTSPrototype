# Gridnet Action Contract v2 Migration Plan

Date: 2026-04-28
Status: historical migration plan (v2 contract is now active in Unity code)

## Current Status Update (2026-04-29)

- This plan is kept as migration history.
- Current Unity contract is v2 `[6,4,4,4,4,7,49]`.
- References below to "current v1 target" reflect plan-time state and should be read as historical baseline.

## Current and Target Contracts

- Historical v1 target contract (plan-time): [6,4,4,4,4,4,9]
- New v2 target contract: [6,4,4,4,4,7,49]
- Gym/Gridnet source branch: [6,4,4,4,4,7,49]

## Rationale

- Align adapter target with Gym/Gridnet source action branch.
- Reduce semantic weakening caused by forced remap to NoOp.
- Support 7x7 attack target branch (49) at action-contract level.
- Support Barracks/build-related produce semantics via full produce branch size 7.

## Non-Goals

- Not direct Unity checkpoint compatibility in this step.
- Not BC-ready dataset packaging in this step.
- Not deleting or replacing v1 adapter path.
- Not claiming Gym to Unity runtime parity.

## Scope of This Step

- Python-side adapter path gains explicit target action contract mode:
  - v1_mvp: [6,4,4,4,4,4,9] (default, backward compatible)
  - v2_gridnet_compatible: [6,4,4,4,4,7,49]
- Existing v1 artifacts are preserved and not overwritten.
- No Unity Assets or ML-Agents behavior spec changes in this step.

## Required Unity Follow-Up (Separate Work)

The Unity runtime must be migrated before any v2 runtime parity claims or BC export decisions tied to v2 runtime behavior:

- ActionContract: update branch sizes to include produce=7 and attack target=49.
- ActionDecoder: decode full 7x7 attack target and full produce types.
- ActionMaskBuilder: build valid masks for expanded produce and attack branches.
- ActionApplier: apply expanded semantics safely (including Barracks/build pathways).
- ML-Agents branch spec: update behavior/action specification to v2 contract.
- Tests:
  - unit tests for branch bounds and index decode
  - integration tests for mask/action consistency
  - end-to-end gameplay regression tests for build/attack semantics

## Migration Sequence

1. Keep v1 as default adapter contract to avoid breaking old runs.
2. Run side-by-side v1 and v2 adapter dry runs on the same source rollout batch.
3. Publish comparison report (remap/noise reduction and histogram effects).
4. Implement Unity-side v2 contract and runtime semantics.
5. Re-run v2 adapter validation against Unity v2 runtime.
6. Only then decide BC export path for v2.

## Risk Notes

- v2 adapter output can be contract-compatible at Python level while still requiring Unity runtime updates.
- Lower remap-to-NoOp does not automatically mean BC-ready quality; action distribution can still be near-uniform/high-entropy.
- Do not overwrite or reinterpret Week5 v1 artifacts as v2-equivalent.
