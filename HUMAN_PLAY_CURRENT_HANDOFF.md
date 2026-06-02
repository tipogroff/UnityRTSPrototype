# HUMAN_PLAY_CURRENT_HANDOFF

## What Is Playable Right Now
- MainMenu -> HumanPlay demo launch path is active.
- Demo mode is AI (Player1) vs Human (Player2).
- Human controls support:
  - selection (single + drag unit-only),
  - move and group move,
  - gather loop,
  - build barracks,
  - base/barracks production,
  - attack and attack area/group attack,
  - stop/cancel,
  - pause/menu/camera controls.
- Resource remaining and exhausted states are visible in HUD and world visuals.

## Authoritative Files and Scenes
- Scenes:
  - Assets/Scenes/MainMenu.unity
  - Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity
  - Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity (protected baseline)
- Build order source:
  - ProjectSettings/EditorBuildSettings.asset
- HumanPlay HUD/presentation:
  - Assets/Prefabs/UI/HumanPlayCanvas.prefab
  - Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs
  - Assets/Scripts/Presentation/UI/ContextActionMenuView.cs
  - Assets/Scripts/Presentation/UI/CommandPanelView.cs
  - Assets/Scripts/Presentation/UI/ProductionPanelView.cs
- Human order/control routing:
  - Assets/Scripts/Presentation/PlayerCommandController.cs
  - Assets/Scripts/Presentation/Orders/HumanOrderController.cs
  - Assets/Scripts/Presentation/Orders/MoveOrder.cs
  - Assets/Scripts/Presentation/Orders/HarvestLoopOrder.cs
  - Assets/Scripts/Presentation/Orders/BuildBarracksOrder.cs
  - Assets/Scripts/Presentation/Orders/AttackOrder.cs
  - Assets/Scripts/Presentation/Orders/GroupOrderPlanner.cs
  - Assets/Scripts/Presentation/Orders/GroupOrderReservationService.cs
- Runtime authority:
  - Assets/Scripts/ML/ActionApplier.cs
  - Assets/Scripts/Gameplay/Match/MatchManager.cs
  - Assets/Scripts/Gameplay/Combat/CombatResolver.cs
- Agent/bootstrap/model:
  - Assets/Scripts/MLAgents/Stage7B/StudentMlAgent.cs
  - Assets/Scripts/MLAgents/Stage7B/MlAgentsTrainingBootstrap.cs
  - Assets/MLAgents/Models/Stage7B_RTS_Student_ImitationSmoke_010.onnx

## Do Not Touch Without Explicit Scope
- Python training pipeline and scripts.
- Checkpoints and ONNX assets.
- Observation/action contract behavior.
- ActionDecoder semantics.
- ActionApplier semantics.
- MatchManager core runtime semantics.
- Week7 baseline scene.
- MainMenu and current HumanPlay demo scenes (post-freeze).

## How To Run Demo
1. Open Assets/Scenes/MainMenu.unity.
2. Enter Play mode.
3. Click Start Demo.
4. In demo scene, HumanPlayModeController auto-starts AIvsPlayer2.
5. Use LMB/drag to select Player2 units and RMB context for commands.

## Core Validation Scenario (Safe Regression Check)
1. From MainMenu, start demo.
2. Select Player2 Worker and issue move.
3. Gather from a resource, then verify return/deposit and resource changes.
4. Build a Barracks with Worker.
5. Produce Light/Heavy/Ranged from Barracks.
6. Issue single attack and group attack area.
7. Use Stop and verify selected orders cancel.
8. Verify exhausted resource visual state remains visible and non-gatherable.

## Known Limitations
- Group attack/group movement are presentation-side fan-out to per-unit orders.
- No full formation/crowd navigation solution in dense combat.
- Slot/reservation guidance can still produce waits/replans in tight engagements.
- No AoE/splash damage.
- No dedicated attack-move command in current HumanPlay controls.
- Production spawn has no dedicated reservation system; relies on local free-neighbor search.

## Next Safe Tasks (If Needed)
- Add non-invasive documentation comments and diagrams only.
- Add tests/diagnostic assertions that do not alter runtime semantics.
- Improve tooling/reporting around command lifecycle and HUD diagnostics.
- Polish UX text/hints that do not alter command routing or runtime behavior.
