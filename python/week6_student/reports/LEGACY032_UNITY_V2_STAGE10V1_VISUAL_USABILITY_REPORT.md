# LEGACY032_UNITY_V2_STAGE10V1_VISUAL_USABILITY_REPORT

## 1. Scope
- Stage 10V.1 visual diagnostic usability improvements only.
- No training.
- No PPO.
- No checkpoint/dataset changes.
- No action/observation contract changes.
- No runtime command semantics changes in ActionApplier or MatchManager.
- No inference bridge protocol changes.

## 2. Implemented usability changes

### 2.1 Pause and run clarity
- Added explicit visual status banner in overlay:
  - VISUAL MODE: PAUSED
  - VISUAL MODE: RUNNING
- Added always-visible control hints for step/pause/reset/snapshot.

### 2.2 Optional bounded autoplay
- Added runtime controls in runner:
  - SetAutoVisualPlaybackEnabled(bool)
  - RunVisualPlaybackSteps(int)
  - RunVisualPlaybackUntilTerminalOrLimit(int)
- Added bounded auto-play execution in Update with step interval.
- Added stop conditions:
  - terminal reached
  - requested step budget exhausted
  - no observable step advance

### 2.3 Baseline visibility
- Added explicit baseline status block in overlay:
  - last baseline action
  - last produce type
  - accepted flag
  - rejection reason
  - last baseline command summary
  - accepted/rejected counters
- Added baseline command/rejection gizmo markers (separate from student markers).

### 2.4 Focus visibility for B2 and C3
- Added world-space labels projected into Game view for focus cells:
  - B2: predicted action, command_built, reason
  - C3: predicted action, command_built, reason

### 2.5 Base visual cell fit in visual inspection
- Added scene-runtime visual override in visual inspection runner:
  - base XZ scale forced to 0.85 (clamped [0.5..1.0])
- Old visual base XZ scale: 1.8 (from Base prefab source values).
- New visual base XZ scale in Stage10V.1 visual mode: 0.85.
- Decision rationale:
  - implemented as runner-scoped runtime override for inspection usability
  - avoids broad prefab asset mutation risk in unrelated scenes

### 2.6 Control mode legend clarity
- Replaced control legend source with direct EpisodeController mode reflection:
  - P1 and P2 labels now show the effective configured control modes.

## 3. Editor menu updates
- Updated menu file with Stage10V.1 actions:
  - RTS/Week6/Visual Inspection/Enable Auto Visual Playback
  - RTS/Week6/Visual Inspection/Disable Auto Visual Playback
  - RTS/Week6/Visual Inspection/Run 10 Visual Steps
  - RTS/Week6/Visual Inspection/Run Until Terminal Or 100 Steps

## 4. Validation

### 4.1 Compilation
- Checked:
  - Assets/Scripts/ML/Week6VisualInspectionRunner.cs
  - Assets/Scripts/ML/Editor/Week6VisualInspectionRunnerMenu.cs
- Result: no compile errors.

### 4.2 Smoke evidence
- Existing visual controls remained callable (Start/Restart, Step Once, Dump Snapshot).
- Snapshot artifact confirmed:
  - python/week6_student/reports/stage10v_visual_snapshot_step0001.json
  - LastWriteTime: 2026-05-02 20:30:08
- Runtime logs include baseline side activity (example):
  - Player2 starts production Worker
  - Player2 Worker built Barracks at (23,22)
- Screenshot artifact saved:
  - Assets/Screenshots/stage10v1_visual_usability_smoke.png

### 4.3 Known MCP execution limitation during this run
- New menu entries for bounded autoplay were added in code and compiled.
- MCP ExecuteMenuItem returned invalid/context-dependent for those new entries in this session.
- This appears to be a Unity editor menu-state/session routing limitation of the MCP execution path, not a compile failure.

## 5. Files changed
- Assets/Scripts/ML/Week6VisualInspectionRunner.cs
- Assets/Scripts/ML/Editor/Week6VisualInspectionRunnerMenu.cs
- python/week6_student/reports/LEGACY032_UNITY_V2_STAGE10V1_VISUAL_USABILITY_REPORT.md

## 6. Safety and non-regression statement
- No changes in student policy output contract or branch sizes.
- No changes in action decode/apply acceptance semantics.
- No changes in checkpoint/training pipeline.
- Changes are visual diagnostics and control usability only.

## 7. Remaining risk
- Full runtime validation of new menu autoplay actions needs direct in-editor click verification in a fresh editor UI session.
- MCP screenshot from Main Camera was blank in this run and is not sufficient for visual composition verification.

## 8. Decision
- GO_FOR_STAGE10V1_MANUAL_EDITOR_UI_CONFIRMATION
