# HumanPlay-3G.5 Attack Context Order Report

## Result

Status: `partial_pass`. Implementation, static validation, and Unity compilation passed. Manual Game View validation remains for the user.

## Runtime Attack Contract

Attack uses an `AgentAction` with:

- `ActorPosition = attacker.GridPos`
- `ActionType = UnitActionType.Attack`
- `AttackTargetPosition = target.GridPos`
- `Direction` is structurally present but not used for Attack execution
- `ProduceUnitType` is structurally present but not used for Attack execution

`ActionApplier.ValidateAttackAction()` is authoritative. It rejects self-targets, out-of-bounds targets, empty cells, friendly targets, neutral targets, resources as attackers, missing runtime attack capability, and targets outside the attacker definition range.

Range is definition-specific Chebyshev distance. Diagonal targets are valid when within `UnitDefinition.attackRange`.

`MatchManager.TryExecuteAttack()` resolves the occupied enemy target and calls `CombatResolver.TryAttack()`. `CombatResolver` applies runtime damage through `UnitRuntime.TakeDamage()` and handles runtime death cleanup. There is no cooldown; runtime limits commanded execution to one submitted attack per attacker per step.

Configured capabilities:

| Type | Damage | Range | Can attack |
| --- | ---: | ---: | --- |
| Worker | 1 | 1 | Yes |
| Light | 2 | 1 | Yes |
| Heavy | 2 | 1 | Yes |
| Ranged | 1 | 3 | Yes |
| Base | 0 | 0 | No |
| Barracks | 0 | 0 | No |

Base and Barracks can be attacked. Resources are excluded from human Attack context and runtime enemy-player target semantics.

## Files Changed

- `Assets/Scripts/Presentation/Orders/AttackOrder.cs`
- `Assets/Scripts/Presentation/Orders/AttackOrder.cs.meta`
- `Assets/Scripts/Presentation/Orders/GridPathfindingService.cs`
- `Assets/Scripts/Presentation/Orders/HumanOrderController.cs`
- `Assets/Scripts/Presentation/Orders/HumanOrderStatus.cs`
- `Assets/Scripts/Presentation/PlayerCommandController.cs`
- `Assets/Scripts/Presentation/UI/CommandPanelView.cs`
- `Assets/Scripts/Presentation/UI/ContextActionMenuView.cs`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- `HUMAN_PLAY_3G5_ATTACK_CONTEXT_ORDER_REPORT.md`
- `human_play_3g5_attack_context_order_validation.json`

## AttackOrder Lifecycle

1. Validate the Player2 attacker, enemy target, runtime capability, services, and match phase.
2. If the target is already in Chebyshev range, submit low-level Attack immediately.
3. Otherwise find the shortest reachable cardinal BFS path to a free attack-range cell.
4. Submit one existing low-level Move per cleanup tick.
5. Replan if the target moved or the current path became blocked.
6. Submit one low-level Attack per cleanup cycle while the target remains alive.
7. Confirm target HP decrease after cleanup and continue attacking.
8. Complete when the target is destroyed. Fail for attacker death, unreachable target, stopped match, or repeated runtime rejection/no-damage results.

HUD order status includes target owner, type, and current HP while AttackOrder is active.

## Context Menu

- RMB on an enemy Player1 unit or building with a capable Player2 unit opens `Attack`.
- RMB enemy with Base/Barracks selected reports that the selected type has no runtime attack capability.
- RMB resources remains routed to Gather for Worker, not Attack.
- RMB own units does not open Attack.
- RMB free cells keeps Move and Worker Build Barracks behavior.
- Every context menu reopen clears previous callbacks and captured targets.

## Command Routing Proof

`ContextActionMenuView -> HumanPlayCanvasController -> HumanOrderController.IssueAttack -> AttackOrder -> PlayerCommandController.SubmitAttackForUnit -> AgentAction -> ActionApplier.ApplyAction(..., Owner.Player2) -> MatchManager.ApplyCommand -> MatchManager.TryExecuteAttack -> CombatResolver.TryAttack`

Presentation code does not modify HP, destroy units, move units directly, or call `MatchManager.StepMatch`.

## Validation Performed

- Unity compilation: `0` C# errors.
- Unity script validation: no errors in new and modified scripts.
- `git diff --check`: no whitespace errors.
- Static scans confirmed no direct HP mutation, destruction, movement bypass, or `StepMatch` call in changed order/UI command code.
- No `ActionDecoder`, `ActionApplier`, Week7 baseline, Python, training, or checkpoint files were changed by this task.

## Known Limitations

- Group attack is intentionally not implemented.
- Attack-move and automatic target acquisition are intentionally not implemented.
- Cells are not reserved while approaching a target. Dynamic blockers trigger replanning.
- Actual HP decrease and destruction remain pending manual Game View validation.

## Manual Checklist

1. Start game from MainMenu and start Demo.
2. Confirm AI vs Player2 mode.
3. Produce a Player2 combat unit if needed.
4. Select a Player2 combat unit and RMB a nearby Player1 unit or building.
5. Confirm `Attack` appears and click it.
6. Confirm target HP decreases through runtime.
7. RMB a far enemy target and confirm approach movement followed by repeated attacks.
8. Confirm target destruction completes the order cleanly.
9. Confirm Stop cancels future attack and move submissions.
10. Confirm Worker can attack according to its runtime definition.
11. Confirm Base/Barracks cannot issue Attack.
12. Confirm own units cannot be attacked.
13. Confirm Resource Gather, Build Barracks, Base/Barracks production, RMB Move, pause menu, and camera still work.

