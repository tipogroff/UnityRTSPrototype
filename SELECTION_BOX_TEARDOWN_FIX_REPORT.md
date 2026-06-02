# Selection Box Teardown Fix Report

Date: 2026-06-03

## Actual Cause

The scene-unload failure was reproduced before editing:

```text
MissingReferenceException: SelectionBoxView has been destroyed but is still accessed
SelectionBoxView.EnsureBox()
SelectionBoxView.Hide()
SelectionManager.EndDrag()
SelectionManager.SetManualInputEnabled(false)
PlayerSelectionController.SetManualInputEnabled(false)
HumanPlayerController.OnDisable()
```

During scene unload, the dynamically created `SelectionBoxView` could be destroyed before
`HumanPlayerController.OnDisable()` disabled manual selection. `SelectionManager.EndDrag()`
used:

```csharp
_selectionBoxView?.Hide();
```

The null-conditional operator checks CLR null. A destroyed `UnityEngine.Object` can still
hold a CLR reference, so `Hide()` was invoked on the destroyed component. `Hide()` called
`EnsureBox()`, which attempted `GetComponent<RectTransform>()` and UI creation during
teardown.

`SelectionBoxView` has no `Update`, `LateUpdate`, `OnGUI`, coroutine, or event
subscription. The failure was a retained destroyed Unity-object reference and unload
ordering issue.

## Fix

Changed:

- `Assets/Scripts/Presentation/Selection/SelectionBoxView.cs`
- `Assets/Scripts/Presentation/Selection/SelectionManager.cs`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- `SELECTION_BOX_TEARDOWN_FIX_REPORT.md`

`SelectionBoxView` now:

- marks teardown in `OnDisable()` and `OnDestroy()`;
- hides an existing rectangle without creating new UI during teardown;
- clears owned references in `OnDestroy()`;
- returns without creating UI when disabled or tearing down.

`SelectionManager` now:

- uses Unity-aware `_selectionBoxView == null` checks before `Show()` and `Hide()`;
- clears stale destroyed references;
- exposes `ClearSelectionBoxView()` so the owning canvas can detach only its own view.

`HumanPlayCanvasController.OnDestroy()` now detaches its selection-box view from
`SelectionManager` before clearing the local reference.

No scene edits were required.

## Runtime Verification

A temporary editor-only smoke runner was created for verification and removed afterward.
It executed:

```text
MainMenu -> Start -> AI against player -> drag-select unit -> Main Menu
```

three times. Each drag-selection selected one unit and each transition returned to
`MainMenu` without errors.

It also executed:

```text
MainMenu -> Start -> AI against bot -> Main Menu
MainMenu -> Start -> AI against AI -> Main Menu
```

Final Unity Console result:

```text
0 compile errors
0 MissingReferenceException SelectionBoxView
0 NullReferenceException
```

## Scope

The camera controller and camera fix were not modified.

Gameplay rules, command pipeline, ML runtime semantics, Python training files,
checkpoints, ONNX assets, `ActionDecoder`, `ActionApplier`, `MatchManager`,
`EpisodeController`, `MlAgentsTrainingBootstrap`, and the Week7 scene were not modified.
