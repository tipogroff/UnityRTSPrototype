# HumanPlay-3F Selection and Command UX Report

Date: 2026-05-17

## Changed Files

- `Assets/Scripts/Presentation/Selection/SelectionManager.cs`
- `Assets/Scripts/Presentation/Selection/SelectionBoxView.cs`
- `Assets/Scripts/Presentation/Selection/SelectableUnitPresenter.cs`
- `Assets/Scripts/Presentation/Selection/SelectionMarkerController.cs`
- `Assets/Scripts/Presentation/PlayerSelectionController.cs`
- `Assets/Scripts/Presentation/PlayerCommandController.cs`
- `Assets/Scripts/Presentation/HumanPlayerController.cs`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- `Assets/Scripts/Presentation/UI/SelectionInfoPanelView.cs`
- `Assets/Scripts/Presentation/UI/CommandPanelView.cs`
- `Assets/Scripts/Presentation/UI/ProductionPanelView.cs`
- `Assets/Scripts/Editor/Presentation/HumanPlay3UiCameraMenuSetup.cs`
- `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`

## Audit Note

Before 3F, `PlayerSelectionController` supported one selected `UnitRuntime`, click selection, and one cylinder marker. `PlayerCommandController` already routed human commands through `AgentAction` and `ActionApplier`; that runtime command path was preserved.

3F upgrades selection into a multi-object presentation model, keeps `PlayerSelectionController.SelectedUnit` as a compatibility facade for primary selection, and gives the Canvas HUD contextual selection/command/production state.

Intentionally out of scope: worker auto-harvest loops, pathfinding, formation/group movement, core gameplay rule changes, observation/action contract changes, and ActionDecoder/ActionApplier semantic changes.

## Selection Architecture

`SelectionManager` owns the current Player2 controllable selection:

- `SelectedUnits`
- `PrimarySelectedUnit`
- `HasSelection`
- `HasMultiSelection`
- `HumanSide`
- `OnSelectionChanged`
- `SelectSingle`, `AddToSelection`, `RemoveFromSelection`, `ClearSelection`, `SetSelection`
- `SetManualInputEnabled`, `SetHumanSide`

Selection rules:

- Human side is Player2 in the demo.
- Only alive, active Player2 non-resource `UnitRuntime` objects are selectable.
- Player1 units and neutral resources are not selected as controllable objects.
- Destroyed, dead, inactive, or owner-changed units are removed automatically.
- Primary selection is deterministic: mobile units are preferred over buildings, then type and grid position.

`PlayerSelectionController` is now a compatibility facade over `SelectionManager`, so existing `HumanPlayerController` and `PlayerCommandController` code continues to use the primary selected object.

## Input Behavior

- Left-click Player2 unit/building: selects it.
- Shift+left-click Player2 unit/building: toggles it in the selection.
- Left-click empty ground without Shift: clears selection.
- Left-click empty ground with Shift: preserves selection.
- Left-click Player1/neutral object: does not select it.
- Clicks and drags beginning over UI are ignored.
- New Input System mouse/keyboard APIs are used when available; legacy calls remain guarded by `ENABLE_LEGACY_INPUT_MANAGER && !ENABLE_INPUT_SYSTEM`.

## Drag Selection

`SelectionBoxView` renders a non-raycast-blocking Canvas rectangle. On release, `SelectionManager` projects Player2 controllable objects through the active selection camera and selects all objects inside the screen rectangle.

Shift+drag adds to the current selection. Small drags below the configured threshold are treated as normal clicks.

## Selection Markers

`SelectionMarkerController` creates non-colliding primitive cylinder markers on the Ignore Raycast layer when available.

- Every selected object gets a marker.
- The primary selection uses a larger yellow marker.
- Secondary selections use green markers.
- Markers follow transforms in `LateUpdate`.
- Markers clear when selection clears or objects become invalid.

## HUD and Command Panel

`SelectionInfoPanelView` now supports:

- no selection: "No unit selected";
- single selection: type, owner, HP, Worker carry, grid cell, facing/state;
- multi-selection: total count, mobile/building counts, primary object, counts by `UnitType`.

`CommandPanelView` now reacts to selection:

- no selection: hides unit command buttons and prompts selection;
- Worker: Move, Harvest, Return, Build Barracks;
- Base: tells the user to use the Production panel;
- Barracks: tells the user to use the Production panel;
- Light/Heavy/Ranged: Move and Attack;
- multi-selection: visible limitation text; group Move/Attack buttons are disabled.

`PlayerCommandController` also rejects command submission while a multi-selection is active with: "Group commands require pathfinding/formation; use single selection." This prevents fake group movement through primary-unit commands.

## Production Panel

`ProductionPanelView` only exposes production buttons for a single production-capable selected object:

- Base: Produce Worker.
- Barracks: Produce Light, Heavy, Ranged.
- No selection, combat unit, Worker, or multi-selection: production groups are hidden.

Production buttons still call `PlayerCommandController`, which submits through the existing `AgentAction -> ActionApplier -> MatchManager.ApplyCommand` runtime validation path.

## Scene and Prefab Wiring

`HumanPlay3UiCameraMenuSetup` now adds/links:

- `SelectionManager`
- `SelectionMarkerController`
- `PlayerSelectionController._selectionManager`

The demo scene was updated by running `RTS/HumanPlay/3A-3E Setup UI Camera Menu`. `HumanPlayCanvasController` creates the drag-selection overlay at runtime and links it to `SelectionManager`.

## Validation

- Unity script refresh/compile: passed, no C# errors.
- Demo scene Play Mode smoke test: entered and exited Play Mode, no C# errors.
- Build settings remain:
  - index 0: `Assets/Scenes/MainMenu.unity`
  - index 1: `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`
- Week7 baseline scene diff checked: no changes detected for `Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity`.
- ActionDecoder/ActionApplier diff checked: no changes detected for `Assets/Scripts/ML/ActionDecoder.cs` or `Assets/Scripts/ML/ActionApplier.cs`.

## Known Limitations

- Multi-unit Move/Attack is deliberately disabled because this stage does not implement pathfinding or formation logic.
- Drag/click interaction was compile- and scene-wiring validated; final visual/manual confirmation should be done in the Unity Game view because MCP does not inject pointer drag gestures for this project.
- Existing unrelated runtime trace/timer files were already dirty or can be touched by Unity Play Mode; no Python/training/checkpoint code was edited for this stage.

## Constraints Confirmation

- Python/training/checkpoints were not intentionally edited.
- Observation/action contract was not changed.
- ML model/checkpoint paths were not changed.
- ActionDecoder and ActionApplier semantics were not changed.
- Week7 baseline scene was not modified.
- UI/input code does not directly move units through `transform.position`, `UnitRuntime.MoveTo`, or `GridManager.MoveUnit`.
- Gameplay command buttons still route through `PlayerCommandController -> AgentAction -> ActionApplier -> MatchManager.ApplyCommand`.
