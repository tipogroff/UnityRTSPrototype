# Week 3 Compatibility Gap List

Date: 2026-03-29
Purpose: Finalized Day 7 artifact for tracking real compatibility bottlenecks between the two-layer Week 3 contract and the current Unity runtime.

## Scope and Reading Rules

This document is the authoritative Week 3 artifact for Chapter 3.3 style analysis.

It distinguishes three semantic layers that must not be collapsed:
- `LegacyGymCompatibleSpec`: reference-oriented spatial observation and transfer-compatible action framing.
- `UnityMvpTransferSpec`: Unity transfer adapter surface used to connect the current MVP runtime to later ML work.
- Unity runtime truth: authoritative execution in `ActionApplier` and `MatchManager`, with downstream runtime behavior such as `CombatResolver`.

Important interpretation rules:
- action masking is a pre-sampling layer only and never replaces authoritative validation;
- heuristic/debug tooling is not evidence of full Gym parity;
- resolved Day 6 drifts are listed separately from remaining active gaps, to avoid stale claims.

## Active Compatibility Gaps

### Gap 1: Unity-only Global Feature Vector
- Category: Observation surface extension
- Reference-compatible status: No
- Why exists: `UnityMvpTransferSpec` keeps a separate global feature vector for runtime state, resources, and step progress, while `LegacyGymCompatibleSpec` remains spatial-only.
- Concrete gap: the transfer layer exposes a second tensor that does not exist in the legacy-compatible layer or the reference Gym baseline.
- Impact on transfer: direct encoder parity is broken if a policy expects the extra vector at inference time.
- Mitigation strategy: `ObservationBuilder.BuildGlobalFeatures()` now returns a zero-filled buffer in `LegacyGymCompatible` mode; training/inference parity must be enforced per mode.
- Residual risk: experiments can accidentally compare policies with different input surfaces if mode handling is sloppy.
- Transfer consequence: requires adapter discipline; negligible for fine-tuning if the global vector is excluded or handled as auxiliary input.

### Gap 2: Observation-side Semantic Split for `attack_target`
- Category: Observation semantics mismatch
- Reference-compatible status: Partial
- Why exists: the legacy-compatible layer keeps placeholder-compatible semantics for `attack_target`, while `UnityMvpTransferSpec` uses a tactical enemy-presence signal in the same channel slot.
- Concrete gap: equal tensor shape does not imply equal meaning for channel 26 across the two modes.
- Impact on transfer: weights trained to interpret one meaning can misread the other without retraining or explicit mode control.
- Mitigation strategy: keep mode-specific observation building explicit; document that channel equality by index is not sufficient evidence of semantic equality.
- Residual risk: false compatibility claims if only tensor size/order are checked.
- Transfer consequence: affects direct reuse and diagnostics; requires explicit mode-aware dataset or evaluation logic.

### Gap 3: Attack Target Parameterization Reduced to Local 3x3
- Category: Action-space reduction
- Reference-compatible status: No
- Why exists: Week 3 MVP deliberately constrains attack targeting to the local 3x3 neighborhood to avoid premature expansion of the action surface before the core pipeline is stable.
- Concrete gap: `BRANCH_ATTACK_TARGET` is `0..8` only, centered on the acting unit.
- Impact on transfer: broader attack semantics cannot be transferred directly into the current output head.
- Mitigation strategy: teacher/dataset adapters must remap or drop unsupported targets before training or inference.
- Residual risk: policies trained on wider targeting semantics lose information during projection into the MVP surface.
- Transfer consequence: blocks direct weight transfer; requires dataset adapter or output-head adaptation.

### Gap 4: Explicit Attack Command vs Runtime Combat Resolution
- Category: Runtime semantic mismatch
- Reference-compatible status: Partial
- Why exists: `ActionApplier` validates explicit local attack intent, but final combat execution still remains subject to the current downstream Unity combat flow.
- Concrete gap: accepted attack commands do not yet guarantee strict target-preserving semantics all the way through runtime combat resolution.
- Impact on transfer: a policy may learn to emit valid local targets, while observed combat effect is partially mediated by runtime combat behavior.
- Mitigation strategy: keep this gap explicit in documentation; use smoke tests only to claim pipeline submission plus runtime combat effect, not full target-preserving parity.
- Residual risk: policy debugging may attribute combat outcome differences to policy quality when the remaining mismatch is actually runtime-side.
- Transfer consequence: does not block integration, but weakens strict semantic equivalence claims and matters for dissertation analysis.

### Gap 5: Reduced Produce Semantics and Missing Broader Action Types
- Category: Action-space reduction
- Reference-compatible status: No
- Why exists: Week 3 scope keeps only `NoOp`, `Move`, `Harvest`, `Return`, `Produce`, `Attack` and only the MVP producible unit subset.
- Concrete gap: the current surface omits broader Gym-style action semantics and richer production ecosystems.
- Impact on transfer: datasets or policies with unsupported action heads cannot be consumed directly.
- Mitigation strategy: filter unsupported actions, remap supported produce types, and treat missing action families as out-of-scope for v1.
- Residual risk: training data loss or semantic compression when projecting a richer teacher into the MVP student surface.
- Transfer consequence: blocks direct weight transfer for broader heads; requires dataset adapter.

### Gap 6: Runtime-only Constraints Beyond Mask Semantics
- Category: Runtime validation gap
- Reference-compatible status: No
- Why exists: authoritative runtime validation includes match phase, queue occupancy, command timing, live unit ownership/aliveness, and other engine-specific constraints that are not fully representable as static pre-sampling masks.
- Concrete gap: an action can be allowed by mask yet still be rejected at apply time.
- Impact on transfer: offline policy evaluation can overestimate feasible actions if it assumes masks are authoritative.
- Mitigation strategy: keep `ActionApplier` as the explicit final gate; expose invalid-attempt logs and rejection reasons for diagnostics.
- Residual risk: multi-actor contention and timing-sensitive race conditions remain only partially visible before apply time.
- Transfer consequence: affects diagnostics and runtime reliability more than model topology; important for evaluation protocol.

### Gap 7: Temporal Resolution and Multi-actor Contention
- Category: Runtime coordination limitation
- Reference-compatible status: Partial
- Why exists: Week 3 now supports batch decoding, but authoritative application still resolves duplicate actor commands by `first-wins`, and overall progression remains bound to the Unity step loop.
- Concrete gap: simultaneous intent does not imply simultaneous acceptance when multiple commands contend for the same actor or runtime state transitions occur between sampling and application.
- Impact on transfer: policy behavior under contention can differ from cleaner abstract formulations.
- Mitigation strategy: keep first-wins policy explicit, preserve rejection diagnostics, and avoid claiming that the mask fully represents contention outcomes.
- Residual risk: broader regression coverage is still needed for dense multi-actor scenarios.
- Transfer consequence: mainly affects diagnostics and evaluation stability; usually negligible for fine-tuning, but not for strict semantics discussions.

### Gap 8: Invalid-input Visibility Is a Unity-side Diagnostic Feature
- Category: Diagnostics-only behavior gap
- Reference-compatible status: No
- Why exists: Week 3 now explicitly rejects structurally invalid decoded input and emits `InvalidActionAttemptLog` records instead of silently collapsing those cases into harmless no-ops.
- Concrete gap: invalid decode visibility is richer than a minimal reference-compatible action interface.
- Impact on transfer: none for valid policy outputs; important for debugging adapters, datasets, and heuristic tooling.
- Mitigation strategy: keep invalid-input handling explicit but separate from compatibility claims.
- Residual risk: tooling can overfit to Unity-specific diagnostics if experiments rely on them as if they were part of the reference contract.
- Transfer consequence: affects diagnostics only.

## Resolved During Days 2-6 and Not Counted as Current Gaps

### Resolved Finding A: Move Capability Drift
- Previous issue: building movement permissiveness was misaligned across layers.
- Day 6 resolution: `ActionApplier` coarse capability gating now rejects `Move` for `Base`, `Barracks`, and `Resource`.
- Why it is not listed as active gap: this is now a fixed consistency issue, not a remaining compatibility bottleneck.

### Resolved Finding B: Attack Capability Drift
- Previous issue: attack eligibility in masks and apply-time validation drifted when runtime definitions were stricter than static type checks.
- Day 6 resolution: runtime-authoritative attack capability checks now look at live unit definitions when available.
- Why it is not listed as active gap: current code aligns these layers better; the remaining active issue is the deeper runtime combat semantics gap, not eligibility drift.

### Resolved Finding C: Silent Invalid Decode Fallback
- Previous issue: some invalid decoded actions could degrade into silent no-op behavior.
- Day 6 resolution: invalid decoded actions are now rejected explicitly and logged under `InvalidInput`.
- Why it is not listed as active gap: visibility is now intentional and explicit.

## Impact Classification Summary

### Blocks direct weight transfer
- Gap 3: Attack target parameterization reduced to local 3x3.
- Gap 5: Reduced produce semantics and missing broader action types.

### Requires dataset adapter or explicit projection logic
- Gap 1: Unity-only global feature vector.
- Gap 2: Observation-side semantic split for `attack_target`.
- Gap 5: Reduced produce semantics and missing broader action types.

### Affects runtime diagnostics or evaluation protocol more than model topology
- Gap 6: Runtime-only constraints beyond mask semantics.
- Gap 7: Temporal resolution and multi-actor contention.
- Gap 8: Invalid-input visibility is a Unity-side diagnostic feature.

### Important for dissertation honesty even when integration remains feasible
- Gap 4: Explicit attack command vs runtime combat resolution.

## Use in Week 4 and Chapter 3.3

### Week 4 integration guidance
- future ML consumers should connect through the Week 3 pipeline facade and keep the same downstream authoritative path;
- transfer-compatible policy outputs still require adapter logic for unsupported action semantics;
- evaluation must distinguish mask-level availability from apply-time acceptance.

### Chapter 3.3 guidance
- use the active gap list as the bottleneck inventory;
- use the resolved findings section to show that some Week 3 issues were implementation drift, not enduring compatibility limits;
- keep the residual attack semantics discussion separate from the narrower attack-eligibility fix.

## Related Artifacts
- WEEK3_CONTRACT_SPEC.md
- IMPLEMENTATION_PLAN.md
- Assets/Scripts/ML/WEEK3_DAY6_SUMMARY.md
- Assets/Scripts/ML/WEEK3_DAY7_SUMMARY.md
