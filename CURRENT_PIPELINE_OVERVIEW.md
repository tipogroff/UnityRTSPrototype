# CURRENT_PIPELINE_OVERVIEW

## Demo Launch Pipeline
1. MainMenu scene loads first (build index 0).
2. MainMenu Start Demo button calls SceneFlowController.LoadDemo().
3. Demo scene HumanPlay_Demo_PlayerVsAI loads.
4. HumanPlayModeController auto-starts initial mode AIvsPlayer2.
5. EpisodeController is configured to Player1 StudentInference and Player2 Idle (manual side).
6. EpisodeController.StartNewEpisode() starts runtime match loop.
7. HumanPlayerController enables manual input on Player2 when match is running.

## AI Inference Pipeline
1. Stage7B_StudentMlAgent holds StudentMlAgent + BehaviorParameters.
2. Model asset: Assets/MLAgents/Models/Stage7B_RTS_Student_ImitationSmoke_010.onnx.
3. Behavior name: Stage7B_RTS_Student.
4. MlAgentsTrainingBootstrap runtime mode is InferenceOnly.
5. Student agent generates actions for Player1 perspective.
6. Actions route to AgentAction(s) and then ActionApplier.
7. ActionApplier validates and queues runtime commands via MatchManager.ApplyCommand.
8. MatchManager.StepMatch executes authoritative phases.

## Human Command Pipeline
1. Input:
   - LMB/drag selection via SelectionManager.
   - RMB context via PlayerCommandController and HumanPlayCanvasController.
   - Production/Stop via HumanPlayCanvasController UI buttons.
2. Presentation/order layer:
   - HumanOrderController creates MoveOrder, HarvestLoopOrder, BuildBarracksOrder, AttackOrder.
   - GroupOrderPlanner and GroupOrderReservationService provide group fan-out guidance.
3. Submission:
   - PlayerCommandController converts to AgentAction and calls ActionApplier.
4. Runtime:
   - ActionApplier validates against runtime constraints and creates MatchCommand.
   - MatchManager queues command and resolves it in step phases.

## Resource/Economy Pipeline
1. ResourceNode holds finite amount and exhausted state.
2. HarvestLoopOrder performs move-harvest-return loop for Worker.
3. Runtime harvest/deposit is executed in MatchManager harvest/deposit phase.
4. Player resources update through MatchManager/AddResources and PlayerState.
5. UI reads resources from MatchManager and resource state from ResourceManager/ResourceNode.
6. ResourceVisualStateController keeps exhausted nodes visible and visually distinct.

## Production/Build Pipeline
1. Production UI calls PlayerCommandController.TryProduce* methods.
2. ProductionCommandHelper maps to raw v2 produce index:
   - Worker->Build Barracks index 2
   - Base->Worker index 3
   - Barracks->Light/Heavy/Ranged indices 4/5/6
3. ActionApplier validates produce/build invariants.
4. MatchManager.TryExecuteProduce routes:
   - Worker produce => TryWorkerBuildBarracks
   - Building produce => BuildingRuntime.StartProducingUnit
5. BuildingRuntime queue advances each step and spawns produced unit in local 3x3 free neighbor cell.

## Combat Pipeline
1. Attack input/context creates AttackOrder (single) or fan-out AttackOrder set (group area attack).
2. PlayerCommandController submits Attack AgentAction.
3. ActionApplier validates attack target, ownership, and range.
4. MatchManager.TryExecuteAttack checks target occupancy/allegiance and calls CombatResolver.TryAttack.
5. CombatResolver applies damage/death using UnitDefinition attack stats.
6. Independent combat tick also runs through CombatResolver.ResolveCombatTick for eligible attackers not skipped.
