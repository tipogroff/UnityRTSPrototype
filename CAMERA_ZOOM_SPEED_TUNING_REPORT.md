# Camera Zoom Speed Tuning Report

## Scope

- Updated `Assets/Scripts/Presentation/Camera/RtsCameraController.cs`.
- Updated serialized camera settings in `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`.
- Did not change WASD movement speed, middle mouse drag speed, match-start focus, gameplay, ML, pacing, `EpisodeController`, or `GameSpeedController`.

## Change

- Increased `RtsCameraController` wheel zoom sensitivity from `8` to `16`.
- Updated the demo scene serialized `_zoomSpeed` from `8` to `16`, because the scene overrides the script default.

## Expected Behavior

- Mouse wheel zoom is approximately twice as responsive.
- Existing `_minZoom` and `_maxZoom` remain unchanged at `6` and `18`.
- Existing smooth zoom movement remains unchanged through `_smoothTime`.
- Camera focus behavior, pause/resume input blocking, WASD movement, and middle mouse drag logic are unchanged.

## Verification

- Confirmed the demo scene serialized `RtsCameraController` value previously overrode `_zoomSpeed`.
- Unity Editor was not connected through MCP in this session, so play-mode checks and console validation were not run here.
- Required manual verification remains:
  - `MainMenu -> Start -> AI против игрока`: check mouse wheel zoom, WASD, and middle mouse drag.
  - Check AI против бота and AI против AI.
  - Confirm Console has 0 compile errors, 0 `NullReferenceException`, and 0 `UnassignedReferenceException`.
