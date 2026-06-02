# HumanPlay-2 Pre-Implementation Audit

Date: 2026-05-13
Scope: PART 0 audit before HumanPlay-2 implementation.

## Files and Scene Audited

- `Assets/Scripts/Presentation/GameSpeedController.cs`
- `Assets/Scripts/Gameplay/Match/EpisodeController.cs`
- `Assets/Scripts/ML/ActionApplier.cs`
- `Assets/Scripts/ML/ActionDecoder.cs`
- `Assets/Scripts/ML/AgentAction.cs`
- `Assets/Scripts/ML/ActionMaskBuilder.cs`
- `Assets/Scripts/ML/MlPolicyPipelineFacade.cs`
- `Assets/Scripts/Gameplay/Entities/UnitRuntime.cs`
- `Assets/Scripts/Gameplay/Match/MatchManager.cs`
- `Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity`

## 1) Current AI action apply path

Authoritative path is intact and already production-safe:

1. Decision source (heuristic/student/idle) selected in `EpisodeController.BuildDecisionSource()`.
2. `RlLoopCoordinator.ExecuteFullStep(...)` runs canonical step phases.
3. Policy output is decoded by `ActionDecoder` into `AgentAction` values.
4. Commands are submitted via `ActionApplier.ApplyAction/ApplyActions`.
5. `ActionApplier` validates runtime constraints and calls `MatchManager.ApplyCommand(...)` with `MatchCommand`.
6. `MatchManager.StepMatch()` executes movement/economy/production/combat and final runtime truth.

Important: `ActionApplier` explicitly documents masks as advisory only; runtime authority remains in `ActionApplier` + `MatchManager`.

## 2) Safe human command submission path

Safe path for human control is:

- Human input -> structured `AgentAction` or `MatchCommand` ->
- `ActionApplier.ApplyAction(s)` or `EpisodeController.ApplyCommand(s)` ->
- `MatchManager.ApplyCommand(s)` -> `MatchManager.StepMatch()`.

Unsafe direct paths to avoid (confirmed by audit):

- direct `UnitRuntime.MoveTo(...)` from presentation input;
- direct transform mutation (`transform.position`);
- direct `GridManager.MoveUnit(...)` bypassing command validation.

`UnitRuntime.MoveTo` is a gameplay primitive but not acceptable as user-input command path for HumanPlay-2.

## 3) AgentAction constructor/factory accessibility

`AgentAction` is a public readonly struct with:

- public constructor;
- public factories: `CreateNoOp(...)`, `CreateInvalid(...)`.

Conclusion: API is sufficiently public to construct player actions without modifying ML semantics.

## 4) Scene references that must be wired

Observed in `Week7_MLAgents_StudentVsScriptedBot.unity`:

- `PresentationControls` object with `GameSpeedController` is present;
- `MlAgentsTrainingBootstrap` and Stage7B diagnostics/orchestrator components are present;
- `EpisodeController` is not serialized in this scene as an existing component entry.

Implication for HumanPlay-2 wiring:

- HumanPlay presentation controllers should resolve `EpisodeController` dynamically (instance/find/create-safe behavior already exists in EpisodeController dependencies);
- Human mode controllers should optionally reference `MlAgentsTrainingBootstrap` to gate off human controls in `TrainerControlled` mode;
- UI buttons should call only controller methods, not gameplay internals.

## 5) What can be automated via bootstrap

`MlAgentsTrainingBootstrap` already automates:

- runtime object resolution (`GridManager`, `UnitRegistry`, `ResourceManager`, `MatchManager`, `MatchBootstrap`, etc.);
- episode startup/reset via `StartNewEpisode(...)`;
- mode-dependent ML-Agents behavior setup.

What it does not provide directly:

- a human/demo mode menu abstraction;
- ownership-aware manual side selection;
- player UI command orchestration.

Therefore HumanPlay-2 should add a small presentation layer on top, reusing EpisodeController/MatchManager truth path.

## Risk notes before implementation

- Keep `GameSpeedController` presentation-only and preserve TrainerControlled safety gate.
- Do not modify Python/training/checkpoint pipeline files.
- Do not alter observation/action contract or `ActionDecoder`/`ActionApplier` action semantics.
- Ensure human mode on one side uses no automatic decisions for that side (Idle or explicit HumanManual mode).
