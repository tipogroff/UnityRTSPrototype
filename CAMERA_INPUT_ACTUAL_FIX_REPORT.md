# Camera Input Actual Fix Report

Date: 2026-06-03

## Actual Regression Cause

The runtime failure was reproduced before editing:

```text
UnassignedReferenceException: The variable _camera of RtsCameraController has not been assigned.
RTS.Presentation.CameraControls.RtsCameraController.Awake()
Assets/Scripts/Presentation/Camera/RtsCameraController.cs:57
```

`HumanPlay_Demo_PlayerVsAI.unity` contains one active `RtsCameraController` on the active
`Main Camera`. Its older serialized component block does not contain the newer `_camera`
field. At runtime Unity can represent an unassigned serialized `UnityEngine.Object`
reference as Unity null without it being CLR null.

The previous fallback used:

```csharp
_camera ??= GetComponent<Camera>();
```

`??=` only checks CLR null. It skipped the fallback for Unity null and the following
`_camera.orthographic = true` access threw during `Awake()`. Because `Awake()` aborted,
camera input initialization and all manual camera control failed.

## Fix

Changed:

- `Assets/Scripts/Presentation/Camera/RtsCameraController.cs`
- `CAMERA_INPUT_ACTUAL_FIX_REPORT.md`

`Awake()` now uses Unity-aware null comparison:

```csharp
if (_camera == null)
{
    _camera = GetComponent<Camera>();
}
```

It also reports a clear error and disables the controller if a camera component is
actually missing. No scene rewrite was needed.

## Runtime Verification

Before the fix:

- one active `RtsCameraController` was present on active `Main Camera`;
- Play Mode reproduced the `_camera` `UnassignedReferenceException` in `Awake()`;
- the scene contained no conflicting second camera controller.

After the fix, a temporary editor-only smoke runner launched modes through:

```text
MainMenu -> Start -> requested mode
```

The runner was removed after verification. For AI vs player it measured:

```text
controllers=1 controllerEnabled=True controllerActive=True cameraMatchesComponent=True
match_ready blocked=False position=(14.81, 14.00, 14.81) targetPosition=(14.81, 14.00, 14.81)
wasd targetPosition delta=1.504547
zoom targetZoom delta=6
middle_drag targetPosition delta=2.33238
pause_blocked_wasd targetPosition delta=0 targetZoom delta=0 blocked=True
resumed_wasd targetPosition delta=0.8461846 blocked=False
```

AI vs bot and AI vs AI were launched through the same runtime menu path. Both retained
match-start focus and produced nonzero WASD, wheel zoom, and middle-drag target deltas.
Both held target deltas at zero while pause was active and resumed movement after pause
closed.

Focus remains one-shot: `FocusAfterMatchStart()` applies focus once after one frame and
does not run from `LateUpdate()`. Manual input continues to update `_targetPosition` and
`_targetZoom` afterward.

## Console And Scope

Final script compilation completed with zero compiler errors. Camera runtime passes
produced zero `NullReferenceException` and zero `UnassignedReferenceException`.

An unrelated pre-existing selection teardown issue remains during scene transitions:

```text
MissingReferenceException: SelectionBoxView has been destroyed but is still accessed
SelectionBoxView.EnsureBox()
```

This report does not claim that unrelated selection teardown issue was fixed.

The fix did not modify gameplay rules, command pipeline, ML runtime semantics,
`ActionDecoder`, `ActionApplier`, `MatchManager`, `EpisodeController`,
`MlAgentsTrainingBootstrap`, Python training files, checkpoints, ONNX assets, or
`Week7_MLAgents_StudentVsScriptedBot.unity`.
