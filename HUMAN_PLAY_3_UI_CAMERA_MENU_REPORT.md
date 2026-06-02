# HumanPlay-3 UI, Camera, Menu Report

Date: 2026-05-17

## Assets

Imported Kenney archives under `Assets/Art/UI/Kenney/`:

- `kenney_ui-pack-rpg-expansion.zip` -> `Assets/Art/UI/Kenney/UI_Pack_RPG_Expansion/`
- `kenney_game-icons.zip` -> `Assets/Art/UI/Kenney/Game_Icons/`

License files are preserved in both target folders.

## Scenes And Prefabs

- Created `Assets/Scenes/MainMenu.unity`.
- Modified `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`.
- Created `Assets/Prefabs/UI/HumanPlayCanvas.prefab`.
- Added `MainMenu` and `HumanPlay_Demo_PlayerVsAI` to build settings.

## Scripts

Created:

- `Assets/Scripts/Presentation/UI/MainMenuController.cs`
- `Assets/Scripts/Presentation/UI/SceneFlowController.cs`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- `Assets/Scripts/Presentation/UI/TopResourceBarView.cs`
- `Assets/Scripts/Presentation/UI/SelectionInfoPanelView.cs`
- `Assets/Scripts/Presentation/UI/CommandPanelView.cs`
- `Assets/Scripts/Presentation/UI/ProductionPanelView.cs`
- `Assets/Scripts/Presentation/UI/MetricsPanelView.cs`
- `Assets/Scripts/Presentation/UI/PanelVisibilityController.cs`
- `Assets/Scripts/Presentation/Camera/RtsCameraController.cs`
- `Assets/Scripts/Editor/Presentation/HumanPlay3UiCameraMenuSetup.cs`

Updated:

- `Assets/Scripts/Presentation/GameSpeedController.cs` to ignore hotkeys while a UI input field is focused and to expose overlay visibility.

## Main Menu

`MainMenu.unity` contains camera, light, and `MenuControllers` with `SceneFlowController` and `MainMenuController`. Runtime UI builds a Kenney-styled menu with:

- `Unity RTS Prototype / Agent vs Player Demo`
- `Start Demo`
- `Settings`
- `Quit`

Settings includes fullscreen toggle and AudioListener volume slider.

## Demo HUD

`HumanPlayCanvas.prefab` is added to the demo scene. It builds a Canvas HUD at runtime:

- Top resource/status bar: Player1 AI resources, Player2 human resources, match phase, step, start/menu controls.
- Bottom panels: selection info, command buttons, production panel.
- Production panel: Base -> Worker, Barracks -> Light/Heavy/Ranged.
- Metrics panel: hidden by default, shows mode, human side, speed, last command status, and rejection reason.
- Pause menu: Continue, Restart Match, Settings, Toggle Metrics, Main Menu, Quit.

Gameplay-affecting UI buttons call existing presentation controllers only. Player2 manual commands still route through `PlayerCommandController -> AgentAction -> ActionApplier -> MatchManager.ApplyCommand`.

## Hotkeys

- `F1`: toggle entire HUD.
- `F2`: toggle metrics.
- `F3`: toggle selection panel.
- `F4`: toggle production panel.
- `Esc`: pause and open pause menu.
- `Space`, `N`, `1/2/3/4`: remain on `GameSpeedController`.

## Diagnostics UI

The old `HumanPlayHudController` component remains in the demo scene but is disabled by default. `GameSpeedController` keeps hotkeys but its OnGUI overlay is disabled.

## Camera

Main Camera is orthographic, rotated to an RTS/isometric view: X 58, Y 45. `RtsCameraController` provides:

- WASD movement using the New Input System when available.
- Mouse wheel zoom.
- Smooth movement and zoom.
- Bounds clamp based on `GridManager` or `GameConstants`.
- Optional middle mouse drag.

Selection and command raycasts still use `Camera.main`, so they follow the new camera.

## Validation Notes

Unity compile check: no C# errors.

Play-mode smoke checks:

- `MainMenu.unity` builds the runtime Canvas without errors.
- `HumanPlay_Demo_PlayerVsAI.unity` builds the runtime Canvas without C# errors.
- No New Input System legacy warnings were observed.

Residual pre-existing presentation warnings in the demo scene:

- `UnitVisualAnimator` missing Animator parameter `IsCarrying`.
- `UnitVisualAnimator` missing Animator trigger `Spawn`.

## Constraints Confirmation

- No Python/training/checkpoint files were edited by this stage.
- No observation/action contract files were changed.
- No `ActionDecoder` or `ActionApplier` semantics were changed.
- `Week7_MLAgents_StudentVsScriptedBot.unity` was not modified.
- No UI path directly calls `transform.position`, `UnitRuntime.MoveTo`, or `GridManager.MoveUnit` for gameplay commands.
