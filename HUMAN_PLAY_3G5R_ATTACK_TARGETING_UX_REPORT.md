# HumanPlay-3G.5R Attack Targeting UX Report

## Result

Status: `partial_pass`. Implementation, Unity compilation, and static audits passed. Manual Game View validation remains for the user.

## UX Issue Fixed

Human Attack previously required a pixel-accurate RMB hit on a moving enemy and rejected multi-selection before attack context resolution. RMB Attack now resolves enemies from a clicked grid area and issues one existing `AttackOrder` per capable selected Player2 unit.

## Files Changed

- `Assets/Scripts/Presentation/Orders/AttackTargetAcquisitionService.cs`
- `Assets/Scripts/Presentation/Orders/AttackTargetAcquisitionService.cs.meta`
- `Assets/Scripts/Presentation/Orders/HumanOrderController.cs`
- `Assets/Scripts/Presentation/PlayerCommandController.cs`
- `Assets/Scripts/Presentation/UI/ContextActionMenuView.cs`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- `HUMAN_PLAY_3G5R_ATTACK_TARGETING_UX_REPORT.md`
- `human_play_3g5r_attack_targeting_ux_validation.json`

## Configuration

`HumanPlayCanvasController` owns the serialized tuning values:

- Single-unit RMB acquisition radius: `3` grid cells.
- Multi-unit attack area radius: `4` grid cells.

Both radii use Chebyshev grid distance, matching the runtime Attack range distance convention.

## Target Acquisition

`AttackTargetAcquisitionService` provides:

- `TryFindBestEnemyNearCell(...)`
- `FindEnemiesInArea(...)`
- `IsValidEnemyTarget(...)`

Valid targets are alive active enemy player units or buildings. Own units, neutral owners, and resources are excluded.

Selection is deterministic:

1. Lower Chebyshev distance to clicked cell.
2. Lower HP.
3. Lower grid X.
4. Lower grid Y.
5. Lower Unity instance ID.

## Context Behavior

- Direct RMB enemy hit still opens Attack.
- RMB within `3` cells of an enemy opens `Attack <Type>` for a single attacker.
- RMB within `4` cells of enemies opens `Attack Area (<count>)` for multi-selection.
- RMB Worker on an actual resource node keeps Gather priority.
- RMB Worker on its own Base while carrying resources keeps Return priority.
- RMB free cell without nearby enemies keeps Move and optional Build Barracks fallback.
- Empty areas publish `No enemy target in attack area.`
- Every menu reopen clears old callbacks, captured targets, and captured area cells.

## Multi-Unit Assignment

`HumanOrderController.IssueAttackArea(...)` filters dead, non-Player2, and non-attacking selections. Base and Barracks are ignored. Worker, Light, Heavy, and Ranged participate according to runtime definitions.

For each remaining attacker:

1. Prefer the enemy with the fewest assigned attackers.
2. Tie-break by lower Chebyshev distance from attacker to target.
3. Tie-break by lower Unity instance ID.

Each assignment creates and immediately primes a normal `AttackOrder`. There is no group runtime command and no AoE damage.

## Routing Proof

`RMB clicked cell -> AttackTargetAcquisitionService -> ContextActionMenuView -> HumanPlayCanvasController -> HumanOrderController.IssueAttackArea -> HumanOrderController.IssueAttack -> AttackOrder -> PlayerCommandController.SubmitAttackForUnit -> AgentAction -> ActionApplier.ApplyAction -> MatchManager.ApplyCommand -> normal runtime combat`

## Validation Performed

- Unity compilation: `0` C# errors.
- Unity script validation: no errors in modified scripts.
- `git diff --check`: no whitespace errors.
- Static scan: no direct HP mutation in UI/order/acquisition code.
- Static scan: no direct unit destruction in UI/order/acquisition code.
- Static scan: no direct movement bypass in UI/order/acquisition code.
- Static scan: no `MatchManager.StepMatch` call from UI/order/acquisition code.
- No `ActionDecoder`, `ActionApplier`, Week7 baseline, Python, training, or checkpoint changes were made by this task.

## Known Limitations

- This is target acquisition, not attack-move. Orders only use enemies captured from the clicked area when issued.
- AoE and splash damage are intentionally absent.
- No visual area preview was added.
- Stop retains the existing UI behavior: it cancels the primary selected order.

## Manual Checklist

1. Start Demo and confirm AI vs Player2 mode.
2. Produce or select a Player2 combat unit.
3. RMB directly on a Player1 unit and confirm Attack works.
4. RMB one to three cells near a moving Player1 unit and confirm Attack appears.
5. RMB an empty cell far from enemies and confirm Move / Build behavior remains.
6. Select multiple Player2 attackers and RMB near an enemy cluster.
7. Confirm `Attack Area (<count>)` appears.
8. Click it and confirm selected capable units attack area targets through normal AttackOrder behavior.
9. Confirm there is no AoE damage.
10. Confirm Base/Barracks in a mixed selection are ignored.
11. Confirm Worker Gather, Build Barracks, production, Stop/cancel, pause menu, and camera still work.

