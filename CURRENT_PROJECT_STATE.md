# CURRENT_PROJECT_STATE

## Overview
This document freezes the currently observed HumanPlay state of UnityRTSPrototype as of 2026-06-02.

Scope of this freeze:
- Documentation and audit only.
- No gameplay/runtime semantics were changed.
- No scenes, prefabs, models, checkpoints, or Python training artifacts were modified by this task.

Manual state confirmed in project context and matched to code/scene wiring:
- Human manual mode is playable.
- UI cleanup is in place with context-driven commands and production panel.
- Obsolete lower panel unit command buttons (Move, Harvest, Attack, Return) are not part of the active HumanPlay canvas command row.
- Resource remaining and exhausted-state visibility are implemented.
- HUD/context hints are present.
- Move, Gather, Build Barracks, Base/Barracks production, Attack, Attack Area, Group Move, and Group Attack are implemented.
- Group attack is presentation-side coordinated fan-out, not a full formation/crowd system.

## Current Scenes

### Build Settings order (authoritative)
From ProjectSettings/EditorBuildSettings.asset:
1. Build index 0: Assets/Scenes/MainMenu.unity (enabled)
2. Build index 1: Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity (enabled)
3. Build index 2: Assets/Scenes/SampleScene.unity (enabled)

### Scene roles and protection
- Assets/Scenes/MainMenu.unity
  - Purpose: user entry scene with Start Demo button.
  - Current status: active entrypoint in build index 0.
  - Protection: must be protected from accidental edits during non-UI-scene tasks.

- Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity
  - Purpose: current playable HumanPlay demo scene.
  - Current status: active demo target in build index 1 and SceneFlowController demo target.
  - Protection: must be protected from accidental gameplay/runtime edits after this freeze.

- Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity
  - Purpose: Week7 baseline/training baseline scene.
  - Current status: legacy baseline scene, not current HumanPlay demo scene, not in current build list.
  - Protection: explicitly do not modify unless a future task directly requires it.

- Other legacy/support scenes (GameScene, Week6_* , Visual*/Animation* scenes)
  - Purpose: historical baselines, diagnostics, visual validation, and setup utility scenes.
  - Current status: not the current HumanPlay demo path.
  - Protection: keep untouched unless future scope explicitly targets them.

## Current Demo Startup Flow
1. App starts in Assets/Scenes/MainMenu.unity (build index 0).
2. MainMenuController Start Demo button calls SceneFlowController.LoadDemo().
3. SceneFlowController loads scene name HumanPlay_Demo_PlayerVsAI.
4. In demo scene, HumanPlayModeController has _initialMode=AIvsPlayer2 and _autoStartOnEnable=1.
5. HumanPlayModeController waits for runtime services, then calls StartAIvsPlayer2().
6. StartAIvsPlayer2 routes through StartHumanVsAi(humanSide=Player2):
   - EpisodeController.ConfigureWeek6PlayerControlModes(enableStudentMatchControl=true, player1=StudentInference, player2=Idle)
   - EpisodeController.StartNewEpisode()
7. HumanPlayerController enables manual input only when:
   - Human side exists,
   - runtime is not TrainerControlled,
   - match phase is Running.
8. PlayerSelectionController and PlayerCommandController are set to human side Player2.
9. HUD/UI is provided by HumanPlayCanvas prefab instance in scene (Assets/Prefabs/UI/HumanPlayCanvas.prefab), which runs HumanPlayCanvasController and builds runtime UI panels/hints.
10. Stage7 bootstrap is configured with _stage7BRuntimeMode=InferenceOnly and _stepScriptedOpponent=0, so scripted opponent stepping is disabled for this demo flow.

## Current AI Agent Configuration

### Agent object and components
- Agent GameObject: Stage7B_StudentMlAgent
- Main agent script: RTS.MLAgents.Stage7B.StudentMlAgent
- BehaviorParameters present on same object
- DecisionRequester present on same object

### Model and behavior
- Behavior name: Stage7B_RTS_Student
- Model asset GUID on BehaviorParameters: 6d127165551f3de4d97e97652c4979c5
- Resolved model asset path: Assets/MLAgents/Models/Stage7B_RTS_Student_ImitationSmoke_010.onnx

### Runtime mode and side ownership
- Stage7 bootstrap object: Stage7B_MLAgentsTrainingBootstrap
- Bootstrap runtime mode: InferenceOnly (_stage7BRuntimeMode=3)
- Bootstrap force trainer controlled: false (_forceTrainerControlledMode=0)
- Student player side in bootstrap: Owner.Player1
- Scripted opponent side in bootstrap: Owner.Player2, but scripted stepping is disabled (_stepScriptedOpponent=0)
- Human mode startup sets Player2 to manual/idle and Player1 to StudentInference through EpisodeController week6 control modes.

### Inference mode details
- Scene-serialized BehaviorParameters.m_BehaviorType is currently 0 (Default) in YAML.
- At runtime, MlAgentsTrainingBootstrap.ApplyRuntimeModeConfiguration() sets behavior type according to InferenceOnly mode and configures decision source policy accordingly.
- Python trainer is not required to run this demo inference mode.

### Observation/action contract references
- Observation contract: Assets/Scripts/ML/ObservationContract.cs
- Action contract and decode: Assets/Scripts/ML/ActionContract.cs, Assets/Scripts/ML/ActionDecoder.cs
- Authoritative apply path: Assets/Scripts/ML/ActionApplier.cs -> MatchManager.ApplyCommand / StepMatch

## Current Human Control Scheme

### Selection
- LMB click: selects a single selectable unit/building on human side (Player2).
- Drag selection:
  - includes only mobile Player2 units (non-building, non-resource).
  - excludes Base and Barracks for multi-select.
- Single-click Base/Barracks is preserved and valid for production context.
- Multi-selection contains controllable mobile units only.

### RMB/context behavior
- RMB empty/free cell:
  - single selected mobile unit: Move order via context menu.
  - multi-selection: Group Move (fan-out to per-unit MoveOrder).
  - selected Player2 Worker also gets Build Barracks context option.
- RMB resource cell:
  - selected single Player2 Worker: Gather loop (HarvestLoopOrder).
  - exhausted resource: explicit exhausted status message/hint.
- RMB enemy/near enemy:
  - single attacker: Attack target acquisition path.
  - multi-selection: Attack Area path with target acquisition and assignment.
- RMB own base while carrying worker cargo:
  - return path is supported via return command path and harvest loop return stage.

### Stop/Cancel
- Stop button is present in active command row.
- Stop triggers cancel of selected active orders through HumanOrderController.CancelAllSelectedOrders().

### Production controls
- Base selected: Produce Worker
- Barracks selected: Produce Light, Heavy, Ranged

## Current Command Pipeline

### Common route invariant
Human input never applies gameplay effects directly. Route is:
1. UI/input (HumanPlayCanvasController + SelectionManager + context/production views)
2. HumanOrderController and order objects (MoveOrder, HarvestLoopOrder, BuildBarracksOrder, AttackOrder)
3. PlayerCommandController helper methods (SubmitMove/Harvest/Return/Produce/Attack)
4. AgentAction submission through ActionApplier.ApplyAction
5. MatchManager.ApplyCommand queues command
6. MatchManager.StepMatch executes authoritative phase logic

### Move (single)
- Input: RMB empty cell from context menu.
- Presentation: HumanPlayCanvasController.HandleMoveContextRequested -> IssueMoveOrder.
- Order: HumanOrderController.IssueMove -> MoveOrder.
- Runtime route: PlayerCommandController.SubmitMoveForUnit -> ActionApplier.ApplyAction(UnitActionType.Move) -> MatchManager.ApplyCommand -> movement phase.

### Group Move
- Input: RMB empty cell with multi-selection.
- Presentation: HumanPlayCanvasController -> IssueGroupMoveOrder.
- Planner: GroupOrderPlanner.TryPlanGroupMove assigns per-unit destination cells.
- Order: HumanOrderController.IssueGroupMove fan-outs to per-unit MoveOrder.
- Runtime route: same per-unit Move pipeline as single move.

### Gather
- Input: RMB resource with selected Player2 Worker.
- Presentation: context gather menu.
- Order: HumanOrderController.IssueHarvestLoop -> HarvestLoopOrder.
- Runtime route per tick:
  - move steps: SubmitMoveForUnit
  - harvest steps: SubmitHarvestForUnit
  - return steps: SubmitReturnForUnit
  - all through ActionApplier -> MatchManager command phases.

### Build Barracks
- Input: RMB free cell with selected Player2 Worker, choose Build Barracks.
- Presentation: HumanPlayCanvasController.IssueBuildBarracksOrder.
- Order: HumanOrderController.IssueBuildBarracks -> BuildBarracksOrder.
- Runtime route: SubmitBuildBarracksForWorker -> AgentAction Produce with raw v2 index 2 -> ActionApplier.ValidateWorkerBuildBarracks -> MatchManager.TryWorkerBuildBarracks.

### Base/Barracks production
- Input: production panel buttons.
- Presentation: HumanPlayCanvasController buttons -> PlayerCommandController.TryProduce*.
- Helper: ProductionCommandHelper builds AgentAction Produce with mapped raw v2 index.
- Runtime route: ActionApplier.ValidateProduceAction -> MatchManager.TryExecuteProduce -> BuildingRuntime.StartProducingUnit -> TickProduction -> spawn.

### Attack (single)
- Input: RMB enemy/near enemy context acquisition.
- Presentation: HumanPlayCanvasController attack context -> IssueAttack/IssueAttackAreaOrder.
- Order: HumanOrderController.IssueAttack -> AttackOrder.
- Runtime route: SubmitAttackForUnit -> ActionApplier.ValidateAttackAction -> MatchManager.TryExecuteAttack -> CombatResolver.TryAttack.

### Attack Area / Group Attack
- Input: RMB enemy area with multi-selection.
- Presentation: HumanPlayCanvasController.HandleAttackAreaContextRequested.
- Planner: GroupOrderPlanner.TryPlanGroupAttackApproach assigns attacker->target and preferred cells.
- Reservation: GroupOrderReservationService slots and movement reservations.
- Order: HumanOrderController.IssueAttackArea fan-out into per-attacker AttackOrder.
- Runtime route: still per-unit AttackOrder -> PlayerCommandController -> ActionApplier -> MatchManager.

### Stop/Cancel
- Input: Stop button.
- Presentation: HumanPlayCanvasController.CancelPrimaryOrder.
- Order control: HumanOrderController.CancelAllSelectedOrders.
- Runtime: stops issuing further per-step submissions for cancelled orders.

## Current UI/HUD State

### Active HUD source
- Demo scene includes HumanPlayCanvas prefab instance (Assets/Prefabs/UI/HumanPlayCanvas.prefab).
- HumanPlayCanvasController builds runtime HUD with:
  - top resource bar,
  - selection panel,
  - command panel,
  - production panel,
  - context action menu,
  - pause menu,
  - settings panel,
  - metrics panel.

### Lower-panel command buttons cleanup
- Active command row contains:
  - Stop
  - Restart
  - Main Menu
- Legacy direct lower-panel buttons Move/Harvest/Attack/Return are not present in active HumanPlayCanvas command row.
- Legacy debug HUD script HumanPlayHudController still exists in code and scene, but is disabled in demo scene.

### Selection and production UI behavior
- Selection panel:
  - single-unit details (type/owner/hp/carry/cell/facing)
  - multi-select aggregate summary.
- Production panel:
  - Base group: Worker only.
  - Barracks group: Light/Heavy/Ranged.
  - queue/progress and last production command status.

### Command/status and hints
- Command panel shows:
  - current mode,
  - last command status/result,
  - order status text,
  - hovered resource remaining/exhausted text,
  - control hints.
- Context menu includes per-action hints (move/build, gather loop, attack area messaging).

### Resource UI state
- Top bar includes Player2 Human Resources.
- Hovered resource line shows remaining amount and Active/Exhausted state.
- Exhausted resources are tinted and labeled via ResourceVisualStateController.

### Pause/menu/camera
- Pause menu supports Continue, Restart, Settings, Toggle Metrics, Main Menu, Quit.
- GameSpeedController supports pause/speed/step controls.
- RtsCameraController supports WASD move, wheel zoom, optional middle-mouse drag.

## Current Economy and Resource Flow
- Resource nodes are finite (ResourceNode with CurrentResources and IsExhausted).
- Remaining amount is exposed in command panel hover text.
- Exhausted nodes remain visible and are visually distinct (tint + Exhausted label).
- Exhausted resources are not gatherable (ActionApplier and order checks reject).

Worker gather loop behavior:
1. Move to a resource-adjacent cell.
2. Harvest while carry capacity allows.
3. Move to friendly base and return cargo.
4. Loop until exhausted, cancelled, or failure.
5. If gather starts while carrying cargo, order transitions to deposit first.

Economic authority:
- Player stockpile changes are runtime-authoritative via MatchManager/AddResources and PlayerState.
- Production and build spending occurs only through runtime production/build paths.

## Current Production and Build Pipeline

### Raw v2 produce payload indices (verified)
- Worker build Barracks: index 2
- Base produce Worker: index 3
- Barracks produce Light: index 4
- Barracks produce Heavy: index 5
- Barracks produce Ranged: index 6

### Build Barracks path
- Worker issues Produce with index 2 and direction toward target cell.
- ActionApplier validates one-barracks-per-owner and resource/cell conditions.
- MatchManager.TryWorkerBuildBarracks spends cost and spawns Barracks via UnitFactory.

### Building production path
- Base and Barracks production routed through BuildingRuntime.StartProducingUnit.
- BuildingRuntime holds ProductionQueue and advances in MatchManager production phase.
- Spawn cell search uses local 3x3 neighbor scan around producer building.

### Runtime restrictions
- Base allowed outputs: Worker only.
- Barracks allowed outputs: Light/Heavy/Ranged only.
- Worker produce path is reserved for Barracks build.
- Owner restriction: worker build rejects if owner already has one living Barracks.

## Current Combat and Attack Pipeline

### Attack command contract in runtime route
- ActorPosition: unit source cell.
- ActionType: Attack.
- AttackTargetPosition: explicit target cell.
- Direction: structurally present but not authoritative for attack intent.
- ProduceUnitType: structurally present but ignored for attack semantics.

### Validation and execution
- ActionApplier validates:
  - actor alive/owned,
  - target in map,
  - not self,
  - in unit-definition attack range (Chebyshev),
  - enemy unit exists at target.
- MatchManager.TryExecuteAttack resolves target and calls CombatResolver.TryAttack.
- CombatResolver uses configured attackDamage/attackRange per unit definition and resolves deaths.

### Attack-capable units and targets
- Attack capability requires runtime definition with attackDamage>0 and attackRange>0.
- Valid targets are alive enemy player units (not neutral resources).

### Single vs group attack behavior
- Single attack: one AttackOrder for selected unit.
- Attack Area/group attack:
  - enemy acquisition in area,
  - per-attacker assignment,
  - preferred attack slots and reservations,
  - fan-out to per-unit AttackOrder.

## Do-Not-Break Invariants

### Protected systems
- Python training pipeline and scripts.
- Checkpoints and ONNX model artifacts.
- Observation/action contract surfaces.
- ActionDecoder semantics.
- ActionApplier semantics.
- MatchManager authoritative movement/combat/resource semantics.
- Week7 baseline scene.
- Current playable HumanPlay demo scene and MainMenu scene unless future task explicitly requires scene edits.

### Command routing invariants
UI/order/presentation code must not directly:
- move transforms for gameplay resolution,
- call UnitRuntime.MoveTo as a direct gameplay bypass,
- call GridManager.MoveUnit as command bypass,
- mutate HP,
- destroy units,
- mutate resource node amounts outside runtime command flow,
- mutate PlayerState resources directly as UI effect,
- instantiate produced units/buildings directly from UI,
- call MatchManager.StepMatch from UI command widgets.

UI/order must continue routing through:
- HumanOrderController and order classes,
- PlayerCommandController helper submission,
- AgentAction,
- ActionApplier,
- MatchManager.

## Known Limitations
- Group attack/group movement are presentation-side coordinated fan-outs into per-unit orders.
- This is not a full formation/crowd navigation system.
- Dense surround cases can still produce waiting/replanning/slot contention and non-ideal movement.
- Reservation and engagement slots are guidance at presentation/order layer; runtime occupancy and combat remain authoritative.
- No AoE/splash damage model in current combat pipeline.
- No dedicated attack-move command in current exposed HumanPlay controls.
- Building production spawn uses local 3x3 neighbor scan and has no explicit spawn reservation system.
- Exhausted resources remain visible by design (with visual exhausted state).
- Existing unrelated workspace modification detected outside this task:
  - python/week5_teacher_legacy032/third_party/gym_microrts_legacy032_source (pre-existing dirty state).

## Validation Summary
- Unity/C# problems check: 0 errors found at audit time.
- Documentation artifacts created by this task only.
- No gameplay script semantic edits performed.
- No scene changes performed.
- No prefab changes performed.
- No model/checkpoint changes performed.
- No Python/training changes performed.
- No ActionDecoder changes performed.
- No ActionApplier changes performed.
- No Week7 baseline scene changes performed.
- No HumanPlay demo scene changes performed.
- No MainMenu scene changes performed.

Uncertainty notes:
- BehaviorParameters serialized behavior type in scene YAML is Default, while bootstrap runtime mode logic explicitly enforces InferenceOnly behavior configuration at runtime.
- HumanPlayCanvasController is provided via prefab instance in demo scene (stripped prefab instance in scene YAML), so many concrete UI element objects are runtime-built rather than scene-serialized as individual children.
