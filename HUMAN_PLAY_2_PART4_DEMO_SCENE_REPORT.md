# HUMAN PLAY 2 - PART 4 Demo Scene Report

## Scope
Prepared a dedicated demo scene for diploma playback and manual control:
- Created: Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity
- Baseline preserved: Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity

Constraints respected:
- No Python/training/checkpoint edits.
- No observation/action contract edits.
- No ActionDecoder or ActionApplier semantic changes.
- No gameplay rule changes.
- No direct movement bypass path introduced.

## Changed Files (Final)
- Added: Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity
- Added: Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity.meta

Unrelated pre-existing workspace change:
- Modified submodule pointer: python/week5_teacher_legacy032/third_party/gym_microrts_legacy032_source

## Demo Scene Target
- Scene path: Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity
- Scene load/save status: successful
- Active roots count in demo scene: 11

## Components Added On PresentationControls
Added/confirmed runtime presentation stack on PresentationControls:
- RTS.Presentation.GameSpeedController
- RTS.Presentation.HumanPlayModeController
- RTS.Presentation.HumanPlayerController
- RTS.Presentation.PlayerSelectionController
- RTS.Presentation.PlayerCommandController
- RTS.Presentation.HumanPlayHudController

## Default Demo Mode
HumanPlayModeController:
- initial mode: Player1VsAI (serialized value: 1)
- auto start on enable: false (serialized value: 0)
- preferred AI mode: StudentInference (serialized value: 2)
- fallback AI mode: HeuristicBaseline (serialized value: 1)

## Control Wiring
Configured references in scene serialization:
- HumanPlayHudController wired to mode/human/selection/command controllers.
- HumanPlayerController wired to mode/selection/command controllers.
- Selection and command cameras wired to Main Camera Camera component.
- Training bootstrap reference wired where required.

Fields intentionally left null where scripts are designed to resolve dependencies at runtime via scene discovery.

## Student/Fallback Behavior
Stage7 bootstrap in demo scene:
- _stage7BRuntimeMode = InferenceOnly (serialized value: 3)
- _forceTrainerControlledMode = false (serialized value: 0)

This supports Player1 manual control + Player2 AI with StudentInference path and heuristic fallback behavior as configured by mode controller.

## Camera Setup
Main Camera exists and is used by both:
- PlayerSelectionController._selectionCamera
- PlayerCommandController._commandCamera

## HUD, Speed, Input
Configured and present:
- HumanPlayHudController enabled, with show HUD true.
- GameSpeedController enabled with hotkeys and overlay.
- HumanPlayMode/HumanPlayer/Selection/Command controllers active in scene.

## Playmode Validation Results
Automated and direct checks completed:
- Demo scene loads and saves successfully.
- Baseline Week7 scene reloads successfully and remains clean (isDirty=false).
- No C# compile errors reported for Assets/Scripts scope.

Manual interactive checks still required in-editor:
- Unit selection and marker behavior in live play.
- Adjacent move acceptance and non-adjacent rejection path.
- HUD button actions (including restart flow).
- Continuous Player2 AI actioning under StudentInference and fallback path when needed.
- End-to-end usability pass for diploma demo narrative.

## Known Limitations / Notes
- Existing non-blocking animator warnings were observed on baseline scene:
  - UnitVisualAnimator missing parameter IsCarrying.
  - UnitVisualAnimator missing trigger Spawn.
- These warnings are pre-existing and unrelated to PART 4 scene setup.

## Baseline Safety Confirmation
Confirmed after final pass:
- Active baseline scene: Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity
- Baseline dirty flag: false
- No baseline scene edits were intentionally performed.

## Compliance Confirmation
Confirmed for PART 4 output:
- Scene-only integration changes.
- No gameplay semantics changed.
- No ML contract/action semantics changed.
- No Python/training/checkpoint artifacts modified as part of implementation.
