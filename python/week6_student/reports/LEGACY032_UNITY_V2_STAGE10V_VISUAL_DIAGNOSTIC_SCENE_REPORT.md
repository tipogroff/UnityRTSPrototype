# LEGACY032_UNITY_V2_STAGE10V_VISUAL_DIAGNOSTIC_SCENE_REPORT

## 1. Scope
- Stage 10V visual diagnostic scene preparation only.
- No training.
- No PPO.
- No dataset/checkpoint modification.
- No ActionApplier runtime validation semantics changes.
- No MatchManager.ApplyCommand logic changes.
- No ActionDecoder contract semantics changes.
- No ObservationContract/ActionContract branch size changes.
- No behavior quality claim and no semantic parity claim.

## 2. Scene changes
- Target scene: `Assets/Scenes/Week6_StudentVisualInspection.unity`.
- Visual diagnostics implemented by extending runtime diagnostic component:
  - `Assets/Scripts/ML/Week6VisualInspectionRunner.cs`
- Added editor play-mode control entry points:
  - `Assets/Scripts/ML/Editor/Week6VisualInspectionRunnerMenu.cs`

### Camera setup
- Added top-down camera auto-configuration in visual runner:
  - orthographic mode (optional toggle)
  - full 24x24 map framing with padding
  - camera centered over map

### Overlay setup (OnGUI/IMGUI)
- Scene/step/terminal block:
  - scene name
  - scenario preset
  - map size
  - current step and max steps
  - terminal status and winner
- Control/runtime block:
  - player control modes
  - active runner count
  - checkpoint path
  - bridge decision request counters (sent/succeeded/failed)
- Observation block:
  - shape/min/max
  - NaN/Inf flags
  - own/enemy/resources counts
  - strict BC global vector fed: `no`
- Inference block:
  - model input shape
  - predicted tensor shape [576,7]
  - branch sizes [6,4,4,4,4,7,49]
  - logits shapes captured flag
  - aggregate action_type histogram (from latest adapter artifact)
  - NoOp share / non-NoOp share
- Actor-cell table (per own cell):
  - unit type
  - grid position
  - logical label
  - flat index
  - eligible
  - predicted action_type
  - top-3 action_type indicator (N/A when logits values are not exported)
  - selected branch values:
    - move_dir
    - harvest_dir
    - return_dir
    - produce_dir
    - produce_unit_type
    - attack_target_local
  - command built
  - reason if command not built
- Decoder/Applier block:
  - commands built/submitted
  - ActionApplier called
  - MatchManager.ApplyCommand called
  - accepted/rejected/ignored counters
  - runtime rejection histogram

### Visual markers and labels
- Added gizmo markers for:
  - player colors (student, baseline, resources)
  - actor-cell eligibility contour
  - predicted action markers (NoOp marker, directional lines, attack target marker)
  - command state marker (warning/success)
- Added optional grid coordinate labels (A..X and 1..24) in scene view.

### Manual controls
- Implemented runtime keys:
  - `Space`: pause/resume
  - `N` or `RightArrow`: advance one decision step
  - `R`: restart visual inspection match
  - `D`: toggle overlay
  - `G`: toggle grid labels
  - `A`: toggle action markers
  - `L`: dump current-step JSON snapshot
- Added matching editor menu actions for deterministic play-mode stepping:
  - `RTS/Week6/Visual Inspection/Step Once`
  - `RTS/Week6/Visual Inspection/Toggle Pause`
  - `RTS/Week6/Visual Inspection/Dump Snapshot`

## 3. Diagnostic capabilities
- Play Mode now supports controlled visual diagnosis instead of immediate opaque run:
  - match can initialize and pause before first decision
  - stepping can be advanced manually
  - overlay updates per step
- Actor-cell visibility for Player1 includes required focus cells:
  - B2 / (1,1) / flat 25
  - C3 / (2,2) / flat 50
- Action/logit visibility includes:
  - logits tensor shapes per branch
  - predicted action branch values per actor cell
  - action_type dominance metrics and NoOp share
- Command flow visibility includes:
  - built/submitted counters
  - applier/apply path reached flags
  - not-built reason (including `predicted_noop`)

## 4. NoOp collapse probe
- Added dedicated overlay probe block:
  - actor cells checked count
  - actor cells predicted NoOp count
  - actor cells predicted non-NoOp count
  - non-actor cells predicted non-NoOp count
  - top action for flat 25 (B2)
  - top action for flat 50 (C3)
  - rule-based probe classification:
    - `MODEL_OR_OBSERVATION_NOOP_DOMINANCE`
    - `POSTPROCESS_OR_DECODER_FILTER_ISSUE`
    - `RUNTIME_APPLIER_SEMANTICS_ISSUE`

## 5. Files changed
- `Assets/Scripts/ML/Week6VisualInspectionRunner.cs`
- `Assets/Scripts/ML/Editor/Week6VisualInspectionRunnerMenu.cs`
- `python/week6_student/reports/LEGACY032_UNITY_V2_STAGE10V_VISUAL_DIAGNOSTIC_SCENE_REPORT.md`
- generated diagnostic artifact:
  - `python/week6_student/reports/stage10v_visual_snapshot_step0003.json`

## 6. Optional smoke result
- Play Mode entered: yes.
- Steps advanced (manual menu stepping): 3.
- Overlay visible path active: yes (runner active, per-step diagnostics generated).
- Snapshot written: yes.
  - `python/week6_student/reports/stage10v_visual_snapshot_step0003.json`
- No training performed: yes.
- No long match run: yes.

## 7. Remaining risks
- Visual diagnostics do not fix policy behavior.
- Visual diagnostics do not prove behavior quality.
- Unity runtime compatibility remediation may still be required after diagnosis.
- Root cause classification still requires continued visual step-by-step inspection.

## 8. Decision
- `GO_FOR_VISUAL_NOOP_COLLAPSE_ANALYSIS`
