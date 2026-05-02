# LEGACY032_UNITY_V2_STAGE10V2_SCENE_ORIENTATION_REPORT

## 1. Scope
- Stage10V2 scene orientation/layout correction for visual inspection only.
- No training, no PPO, no checkpoint changes.
- No dataset regeneration.
- No observation/action contract changes.
- No runtime action-application semantics changes.
- No bootstrap spawn logic changes.

## 2. Root Cause Summary
- Logical spawn placement was already correct in procedural bootstrap:
  - P1 Worker/Base: (1,1)/(2,2)
  - P2 Worker/Base: (22,22)/(21,21)
  - P1 resources: (0,0),(1,0); mirrored for P2.
- Perceived mismatch came from camera orientation/framing in visual inspection mode, not from game-state coordinates.

## 3. Implemented Stage10V2 Changes

### 3.1 Visual-only camera orientation control
- File: Assets/Scripts/ML/Week6VisualInspectionRunner.cs
- Added camera configuration fields:
  - `_flipVerticalToMatchMicroRtsTopLeft` (default: true)
  - `_microRtsTopLeftUpVector` (final tuned default: `(-1, 0, 0)`)
- Updated `ConfigureCameraForVisualInspection()`:
  - Uses `Quaternion.LookRotation(Vector3.down, upVector)` in Stage10V2 mode.
  - Keeps camera centered and orthographic.

### 3.2 Framing fix for rotated top-down view
- In the same method, orthographic fit switched to diagonal-based half extent when Stage10V2 orientation mode is enabled:
  - `halfExtent = sqrt(width^2 + height^2) * 0.5`
- Prevents board clipping after orientation change.

## 4. Validation (Compile + Smoke)

### 4.1 Compile
- Checked file:
  - Assets/Scripts/ML/Week6VisualInspectionRunner.cs
- Result: no compile errors.

### 4.2 Play-mode smoke
- Scene context: Week6 student visual inspection scene.
- Steps executed:
  1. Enter Play Mode.
  2. Start/Restart visual inspection.
  3. Run 3 manual steps via menu command `RTS/Week6/Visual Inspection/Step Once`.
- Console result: 0 errors, 0 warnings during smoke.

### 4.3 Visual evidence artifacts
- Orientation screenshots:
  - Assets/Screenshots/stage10v2_orientation_check.png
  - Assets/Screenshots/stage10v2_orientation_check_v2.png
  - Assets/Screenshots/stage10v2_orientation_check_v3.png
  - Assets/Screenshots/stage10v2_orientation_after_steps.png
  - Assets/Screenshots/stage10v2_orientation_after_tune.png
- Final verified frame (`stage10v2_orientation_after_steps.png`) shows the two start clusters on the expected top-left -> bottom-right diagonal under Stage10V2 camera orientation.

### 4.4 Fine-tuning pass (requested)
- Per follow-up request, the camera up-vector was made stricter (`-X` only) to produce a cleaner left-biased top-left view while keeping the same diagonal semantics.
- Latest evidence frame: `stage10v2_orientation_after_tune.png`.

## 5. Non-regression Statement
- No edits in MatchBootstrap spawn definitions.
- No edits in GridPosition mapping or flat-index contract.
- No edits in action decode/apply/runtime rejection semantics.
- Existing visual diagnostics remain active:
  - overlay/hints
  - B2/C3 focus labels
  - NoOp diagnostics and baseline markers
  - manual controls
  - base-fit visual override behavior

## 6. Files Changed
- Assets/Scripts/ML/Week6VisualInspectionRunner.cs
- python/week6_student/reports/LEGACY032_UNITY_V2_STAGE10V2_SCENE_ORIENTATION_REPORT.md

## 7. Decision
- GO_FOR_VISUAL_NOOP_COLLAPSE_ANALYSIS
