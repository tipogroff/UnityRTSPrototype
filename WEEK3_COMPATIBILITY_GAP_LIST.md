# Week 3 - Compatibility Gap List

Date: 2026-03-23
Purpose: Explicit documentation of differences between LegacyGymCompatibleSpec and UnityMvpTransferSpec.

## Overview

This document is the authoritative source for tracking compatibility gaps between the reference Gym baseline and the practical Unity MVP implementation. It must be updated throughout Week 3 and finalized as an artifact by end of Day 7.

Use this list in:
- Week 3 implementation decisions (which adaptations are intentional, which are technical debt).
- Week 5 when building the teacher pipeline (what transformations are needed for dataset compatibility).
- Chapter 3.3 of the dissertation (formal description of transfer compatibility limitations).

## Primary Gaps (LegacyGymCompatibleSpec → UnityMvpTransferSpec)

### Observation Space

#### Gap: Separate Global Vector
- **Category**: Feature addition
- **Reference-compatible status**: No (not in Gym reference)
- **Motivation**: Runtime telemetry and transfer diagnostics
- **Details**:
  - LegacyGymCompatibleSpec: spatial tensor only, shape [24, 24, 27]
  - UnityMvpTransferSpec: spatial tensor [24, 24, 27] + separate global vector [10]
  - Global vector includes timestamps, resource shares, unit counts, invalid action rates, pending commands.
- **Handling for transfer**: Global vector should be excluded from strict head-to-head Gym-μRTS comparison; it is supplementary.
- **Mitigation**: During BC training and transfer, policy encoder must be trained on spatial tensor only; global vector can be used for auxiliary loss or diagnostics but not forced into Gym-compatible inference.

#### Gap: Normalization Strategy
- **Category**: Implementation detail
- **Reference-compatible status**: Partial (same channels, slightly different normalization bounds)
- **Motivation**: Numerical stability and bounded input for RL policies
- **Details**:
  - All values are normalized to [0, 1] in UnityMvpTransferSpec.
  - Gym-μRTS reference may use different normalization (e.g., resource counts may be unnormalized or use different scales).
- **Mitigation**: Document exact normalization formula and apply inverse transforms during dataset conversion if needed.

### Action Space

#### Gap: Attack Target Parameterization
- **Category**: Space reduction
- **Reference-compatible status**: No
- **Motivation**: MVP simplification (3x3 local neighborhood vs. full-map or larger parameterization in reference semantics)
- **Details**:
  - Reference layer preserves Gym-style attack parameter semantics as far as possible; Gym may support global attack targeting, ranged unit targeting, or continuous coordinates.
  - UnityMvpTransferSpec reduces this to local 3x3 targeting: attack_target_local 0..8 (3x3 neighborhood, center=4).
  - This represents a deliberate constraint for MVP scope.
- **Handling for transfer**: Gym datasets or policies with different attack parameterization must be transformed to local 3x3 representation; out-of-range targets are dropped or remapped.
- **Mitigation**: Explicit adapter layer in Week 5 teacher pipeline.

#### Gap: Reduced Produce Unit Types
- **Category**: Action branch size reduction
- **Reference-compatible status**: Partial (same semantics, subset of possible units)
- **Motivation**: MVP focused on 4 unit types; reference action ecosystem may expose broader unit production semantics
- **Details**:
  - UnityMvpTransferSpec: ProducibleUnit 0..3 (Worker, Light, Heavy, Ranged)
  - Reference action ecosystem may expose broader unit production semantics than the MVP subset.
- **Mitigation**: Dataset conversion must map extended unit types to nearest MVP equivalent or filter out unsupported production actions.

#### Gap: Missing Action Types
- **Category**: Action set reduction
- **Reference-compatible status**: No
- **Motivation**: MVP scoping
- **Details**:
  - UnityMvpTransferSpec action types: 0=NoOp, 1=Move, 2=Harvest, 3=Return, 4=Produce, 5=Attack (6 total)
  - Gym-μRTS may include: Gather variants, Repair, Research, Train, Build structures, etc.
- **Mitigation**: Dataset filtering and action mapping in Week 5.

### Invalid Action Rules (Masking)

#### Gap: Unity Runtime Constraints
- **Category**: Game engine constraints
- **Reference-compatible status**: No
- **Motivation**: Physics and state management in Unity
- **Details**:
  - LegacyGymCompatibleSpec defines high-level invalid semantics (actor must exist, action must be feasible).
  - UnityMvpTransferSpec enforces additional engine-specific rules:
    - production queue occupancy (one unit at a time in MVP, may be different in Gym)
    - exact carry capacity limits for workers
    - building attachment rules (spawn point adjacency)
    - temporal phase coordination (action submission timing)
- **Mitigation**: During mask construction, separate "reference-compatible mask rules" from "Unity-only runtime validation"; both layers remain mandatory (no bypassing server validation).

#### Gap: Actor Lifetime and State Transitions
- **Category**: State machine differences
- **Reference-compatible status**: Partial
- **Motivation**: Unity GameObject lifecycle vs. abstract Gym state
- **Details**:
  - Gym-μRTS: units transition between discrete states (idle, moving, harvesting, etc.) with deterministic timing.
  - Unity MVP: units have MonoBehaviour lifecycle, health points, animation states, physics colliders; destruction and spawning have frame-based delays.
- **Mitigation**: Synchronize state observation and action evaluation frame-by-frame; log any desynchronization warnings.

## Secondary Gaps (Minor/Resolvable)

### Coordinate System
- **Status**: Aligned (row-major, NESW directions, 0-indexed)
- **Risk**: Low

### Owner Encoding
- **Status**: Aligned (neutral, player1, player2)
- **Risk**: Low

### Temporal Resolution
- **Status**: Gym-μRTS default is 1 step/cycle; Unity MVP is 1 step/FixedUpdate. May differ under load.
- **Risk**: Medium (measurable in multi-episode experiments)
- **Mitigation**: Log step timing and reward accumulation; validate episode length consistency.

## Gap Status: Experiment Impact

This section categorizes each primary gap by its effect on transfer learning and fine-tuning experiments.

### Blocks Direct Weight Transfer
- Attack Target Parameterization: requires action remapping before inference; cannot use weights directly without adapter.
- Reduced Produce Unit Types: requires output head adaptation or filtering; cannot use production branch directly if reference has more classes.

### Requires Dataset Adapter
- Separate Global Vector: must exclude from legacy-compatible encoder training; can be used post-hoc for diagnostics.
- Normalization Strategy: inverse transform needed for dataset conversion; document exact formula for reproducibility.
- Missing Action Types: dataset filtering and action mapping in preprocessing.

### Affects Only Diagnostics
- Temporal Resolution: does not block transfer but may shift episode termination timing; log and validate for consistency.

### Negligible for Fine-Tuning
- Coordinate System: fully aligned (row-major, NESW, 0-indexed).
- Owner Encoding: fully aligned (neutral, player1, player2).
- Unity Runtime Constraints: can be handled via action masking without modifying policy weights.
- Actor Lifetime and State Transitions: Unity synchronization is frame-based; transfer is robust if mask is accurate.

## Operationalization

### Week 3 Decisions
- [ ] Day 1: Accept all gaps as listed above; mark as approved.
- [ ] Day 2–4: For each new implementation detail, check against gap list; if unlisted gap appears, add it.
- [ ] Day 7: Finalize gap list; any new gap discovered after Day 7 becomes technical debt for Chapter 3.

### Week 5 Teacher Pipeline
- Import gap list into Python-side preprocessing.
- Create dataset adapters for each major gap (attack target remapping, unit type filter, action type mapping).
- Document adapter behavior and any data loss in conversion.

### Chapter 3.3 Dissertation
1. Reproduce gap list inline as "compatibility bottlenecks".
2. For each gap, describe mitigation strategy and residual risk.
3. Discuss whether gaps materially impact transfer learning experiments or are acceptable trade-offs.

## Version History

- 2026-03-23: Initial draft created during Week 3 Day 1.

## Related Artifacts

- WEEK3_CONTRACT_SPEC.md (sections 2, 3.2, 4.1, 5.2, 7)
- IMPLEMENTATION_PLAN.md (Week 3 Day 7 exit criteria)
