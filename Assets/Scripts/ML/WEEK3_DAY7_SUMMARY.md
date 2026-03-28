# WEEK3 Day 7 Summary

Date: 2026-03-29

## Goal

Day 7 was a consolidation pass, not a new gameplay feature pass.

The target state for Week 3 end is:
- the production pipeline remains `observation -> mask -> action -> decoder -> applier -> MatchManager.ApplyCommand()`;
- runtime authority remains in `ActionApplier` and `MatchManager`;
- debug and transfer-compatible layers stay distinct;
- the codebase is ready to connect a real policy in Week 4 without another core refactor.

## API Cleanup Completed

### Public surface reduced where it was only debug-local
The following surfaces were narrowed to `internal` because they are assembly-local diagnostic or smoke-test helpers, not production contract API:
- `ActionDecoder.DecodeDebug(...)`
- `ActionMaskBuilder.BuildDebugMask(...)`
- `DebugActionMaskSet`
- `ActionApplier` diagnostic overloads that accept mask/source context
- `ActionApplier.ResetDiagnostics()`
- `ObservationBuilder.DumpObservation(...)`
- `HeuristicPolicyAdapter` direct debug trace methods:
  - `DecideAndApply(...)`
  - `DecideAndApplyForPreferredActorType(...)`
  - `DecideAndApplyForActor(...)`
  - `TryGetPipelineDiagnostics(...)`
- `DebugActionSelection`
- `HeuristicDecisionTrace`

### Public production-facing surface kept explicit
The following remain public and were clarified rather than hidden:
- `ObservationBuilder.BuildObservation(...)`
- `ObservationBuilder.BuildGlobalFeatures(...)`
- `ObservationBuilder.BuildObservationPackage(...)`
- `ObservationBuilder.ValidateObservation(...)`
- `ActionDecoder.DecodeTransferCompatibleBatch(...)`
- `ActionDecoder.DecodeTransferCompatible(...)`
- `ActionMaskBuilder.BuildTransferCompatibleMask(...)`
- `ActionApplier.ApplyAction(...)`
- `ActionApplier.ApplyActions(...)`
- `InvalidActionAttemptLog` and `InvalidAttemptCategory`
- new `MlPolicyPipelineFacade`
- new `PolicyExecutionReport`

## Duplication Removed Without Collapsing Semantic Layers

### Shared branch/mapping logic centralized
Added `Assets/Scripts/ML/ActionContractMappings.cs` and reused it for:
- direction index conversion
- observation one-hot index conversion
- producible-unit to unit-type mapping
- local 3x3 attack target decoding
- mask string formatting helpers

This removed duplicated branch/enum logic from:
- `ObservationBuilder`
- `ActionDecoder`
- `ActionMaskBuilder`
- `HeuristicPolicyAdapter`

### Debug and transfer-compatible orchestration now converge in one thin wrapper
Added `Assets/Scripts/ML/MlPolicyPipelineFacade.cs`.

This facade provides the minimal Week 4-ready surface to:
- build observation payloads
- build transfer-compatible masks
- decode transfer-compatible action branches
- apply decoded actions through the authoritative runtime path
- execute transfer-compatible action arrays end-to-end

`HeuristicPolicyAdapter` now uses this facade for its observation/mask/decode/apply orchestration. That means the heuristic path and future ML path converge on the same downstream contract without pretending that debug semantics and transfer semantics are identical.

## Documentation Added or Clarified

### Public API XML docs improved
Documentation was updated so public and key contract-adjacent types now explain:
- which semantic layer they belong to
- whether they are production contract, transfer adapter surface, or diagnostics
- where authoritative validation lives
- what is deliberately not guaranteed

Files updated for this:
- `Assets/Scripts/ML/ObservationBuilder.cs`
- `Assets/Scripts/ML/ActionDecoder.cs`
- `Assets/Scripts/ML/ActionMaskBuilder.cs`
- `Assets/Scripts/ML/ActionApplier.cs`
- `Assets/Scripts/ML/AgentAction.cs`
- `Assets/Scripts/ML/MlPolicyPipelineFacade.cs`
- `Assets/Scripts/ML/ActionContract.cs`
- `Assets/Scripts/ML/HeuristicPolicyAdapter.cs`

## v1 Limitations Now Explicitly Fixed in Code and Artifacts

The following limitations are now documented explicitly instead of being left implicit:
- local 3x3 attack target parameterization is a deliberate v1 reduction
- Unity-only global vector exists only in `UnityMvpTransferSpec`
- equal tensor shape does not imply equal meaning for every observation channel across modes
- action masking is not authoritative validation
- runtime-only constraints can still reject mask-allowed actions
- accepted attack intent does not yet imply strict target-preserving runtime combat semantics
- broader Gym action/production semantics are still out of scope for Week 3 v1
- multi-actor contention still resolves through current first-wins and runtime timing rules

A small but important contract fix was also applied:
- `ObservationBuilder.BuildGlobalFeatures(...)` now returns a zero-filled vector in `LegacyGymCompatible` mode, matching the documented claim that the legacy-compatible surface is spatial-only.

## Compatibility Gap List Finalized

`WEEK3_COMPATIBILITY_GAP_LIST.md` was rewritten from draft form into the finalized Day 7 artifact.

It now contains:
- active compatibility bottlenecks only
- resolved Day 6 findings separated from active gaps
- explicit fields for each gap:
  - category
  - reference-compatible status
  - why the gap exists
  - transfer impact
  - mitigation strategy
  - residual risk
  - transfer consequence classification

The final active gaps include:
- Unity-only global feature vector
- observation-side semantic split for `attack_target`
- local 3x3 attack target parameterization
- explicit attack command vs runtime combat resolution
- reduced produce semantics and missing broader action types
- runtime-only constraints beyond mask semantics
- temporal resolution and multi-actor contention
- invalid-input visibility as Unity-side diagnostics

Resolved Day 6 findings are preserved separately:
- move capability drift
- attack capability drift
- silent invalid decode fallback

This makes the gap list usable almost directly as a Chapter 3.3 bottleneck-and-mitigation artifact.

## Week 4 Readiness Achieved

The codebase is now ready to connect a real policy consumer because there is a stable entry surface that exposes exactly the steps Week 4 needs:
- get observation package
- get transfer-compatible mask
- submit transfer-compatible action branches
- decode into `AgentAction`
- apply through the authoritative runtime path

What Day 7 intentionally does **not** do:
- no reward-loop implementation
- no real ML-Agents policy integration
- no alternate shortcut execution path
- no claim of full Gym parity

## Deliberately Unchanged at End of Week 3

These remain conscious end-of-Week-3 limitations, not accidental leftovers:
- attack semantics are still constrained by the current runtime combat flow
- v1 action space still omits broader Gym semantics
- observation-mode distinctions still require explicit handling by downstream consumers
- contention/timing edge cases still need broader regression coverage if Week 4 experiments become denser

## Exit State

Week 3 now ends in the intended state:
- API surface is cleaner and less noisy
- duplicate technical logic is reduced
- semantic layers remain explicit
- v1 limitations are documented honestly
- `WEEK3_COMPATIBILITY_GAP_LIST.md` is finalized for dissertation use
- the system is ready to connect a real policy in Week 4 without reworking the core pipeline
