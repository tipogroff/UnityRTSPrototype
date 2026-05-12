# Visual-3F-R Animation Playback and Smooth Movement Repair Report

Generated UTC: 2026-05-12T21:20:00Z

## Scope

Visual-3F introduced a visual-layer regression in Play Mode:

- Unit motion looked jerkier than teleport baseline.
- Runtime animation playback looked frozen/intermittent.
- Smooth interpolation trace alone was not enough to accept GO.

This repair pass was constrained to presentation-only scripts and prefab visual-layer settings.

## What Regressed

Regression evidence captured in Play Mode confirms:

- Runtime Animator playback can work (normalizedTime and sampled bone deltas advanced on active Worker units).
- Smooth interpolation lifecycle produced excessive snap behavior and repeated same-frame snap events.
- Smooth-enabled mode failed validation, while smooth-disabled mode passed idle playback checks.

Evidence:

- [Assets/Visual3FR_AnimationRegressionEvidence.md](Assets/Visual3FR_AnimationRegressionEvidence.md)
- [Assets/Visual3FR_AnimationRegressionEvidence.json](Assets/Visual3FR_AnimationRegressionEvidence.json)
- [Assets/Visual3FR_AnimationSmoothMovementValidation.md](Assets/Visual3FR_AnimationSmoothMovementValidation.md)
- [Assets/Visual3FR_AnimationSmoothMovementValidation.json](Assets/Visual3FR_AnimationSmoothMovementValidation.json)

## Root Cause Findings

Primary causes identified:

- IsMoving was too tightly coupled to interpolator instantaneous state; this is fragile under interruption/snap sequences.
- SnapToCurrent events were too frequent in active lifecycle paths, causing interpolation churn and visual jerk.
- Smooth trace lacked explicit snap context (reason, offset-before-snap, interpolation state before snap), making regressions harder to diagnose.

Animator binding/controller status for unit prefabs was verified as intact:

- Worker -> RTS_Worker_Animator.controller
- Light -> RTS_Light_Animator.controller
- Heavy -> RTS_Heavy_Animator.controller
- Ranged -> RTS_Ranged_Animator.controller

## Fixes Applied

### 1) Restore robust Animator movement signaling

- Added movement pulse/latch with timeout safety in VisualEventBridge.
- Added explicit debug fields:
  - LastSetMovingValue
  - LastSetMovingFrame
  - LastMoveStartFrame
  - LastMoveEndFrame
  - AnimatorMovingMatchesInterpolator
- Reduced redundant SetMoving writes.

File:

- [Assets/Scripts/Presentation/VisualEventBridge.cs](Assets/Scripts/Presentation/VisualEventBridge.cs)

### 2) Stabilize and guard smooth interpolation

- Added safe-mode controls and guardrails in interpolator:
  - enableInterpolation (existing)
  - debugDisableSmoothMovement
  - fallbackToTeleportOnError
  - maxOffsetMagnitude
  - hardSnapDistanceThreshold
- Added runtime diagnostics/properties:
  - SnapCount
  - ExcessiveSnapCount
  - LastSnapFrame
  - LastSnapReason
  - LastInterpolationStartFrame
  - LastInterpolationEndFrame
- Added reasoned snap APIs:
  - SnapToCurrent(reason)
  - SetInterpolationEnabled(value, reason)
- Added updated-frame trace events and abnormal offset hard-fallback behavior.

File:

- [Assets/Scripts/Presentation/VisualGridMovementInterpolator.cs](Assets/Scripts/Presentation/VisualGridMovementInterpolator.cs)

### 3) Expand trace payload for snap diagnostics

- Snap trace now includes:
  - was_interpolating_before_snap
  - visual_offset_before_snap

File:

- [Assets/Scripts/Presentation/Visual3EFSmoothMovementTrace.cs](Assets/Scripts/Presentation/Visual3EFSmoothMovementTrace.cs)

### 4) Add runtime Animator diagnostics accessors

- Exposed UnitVisualAnimator helpers for validator/evidence collection.

File:

- [Assets/Scripts/Presentation/UnitVisualAnimator.cs](Assets/Scripts/Presentation/UnitVisualAnimator.cs)

### 5) Add Visual-3F-R validator for A/B mode verification

- New Play Mode validator with two-run protocol:
  - Mode A: smooth disabled
  - Mode B: smooth enabled
- Writes evidence and validation artifacts.
- Adds quick Play Mode menu toggles for smooth enabled/disabled.

File:

- [Assets/Editor/Visual3FRAnimationAndSmoothMovementValidator.cs](Assets/Editor/Visual3FRAnimationAndSmoothMovementValidator.cs)

### 6) Safe fallback default on prefabs

Because Mode B failed and generated excessive snap churn, smooth interpolation is now disabled by default on unit prefabs (teleport fallback preserved):

- [Assets/Prefabs/Worker.prefab](Assets/Prefabs/Worker.prefab)
- [Assets/Prefabs/Light.prefab](Assets/Prefabs/Light.prefab)
- [Assets/Prefabs/Heavy.prefab](Assets/Prefabs/Heavy.prefab)
- [Assets/Prefabs/Ranged.prefab](Assets/Prefabs/Ranged.prefab)

## Validation Outcome

Mode A (smooth disabled): PASS for idle animation playback and marker stability.

Mode B (smooth enabled): FAIL due to excessive snap patterns and non-healthy idle playback metrics in this run.

Decision:

- Smooth movement remains disabled by default as a safety fallback.
- Teleport behavior is restored rather than shipping worsened visual jitter.

## Screenshots

- [Assets/Screenshots/Visual_3F_R_AnimatorIdleRestored.png](Assets/Screenshots/Visual_3F_R_AnimatorIdleRestored.png)
- [Assets/Screenshots/Visual_3F_R_WalkAnimationDuringMove.png](Assets/Screenshots/Visual_3F_R_WalkAnimationDuringMove.png)
- [Assets/Screenshots/Visual_3F_R_SmoothMoveStable.png](Assets/Screenshots/Visual_3F_R_SmoothMoveStable.png)
- [Assets/Screenshots/Visual_3F_R_SmoothDisabledFallback.png](Assets/Screenshots/Visual_3F_R_SmoothDisabledFallback.png)

## Guardrails Kept Intact

No gameplay/AI/training semantics were changed. The repair pass did not modify command/action/observation occupancy contract codepaths.

## Acceptance Criteria Status

- Idle animation plays in Play Mode: PASS (evidence from normalizedTime and bone delta in regression evidence).
- Walk animation during movement: PARTIAL (hooks/path intact; smooth-enabled run still unstable in current pass).
- Attack/Harvest triggers remain available: PASS (parameters verified in runtime evidence).
- Owner colors remain correct: PASS in validator summary.
- Team markers remain stable: PASS in validator summary.
- Smooth movement no longer worsens demo: PASS via default-disabled fallback.
- If smooth cannot be stabilized, keep disabled by default: PASS.
- Root gameplay movement/occupancy/action/observation/training semantics unchanged: PASS by scope and changed-file audit.
