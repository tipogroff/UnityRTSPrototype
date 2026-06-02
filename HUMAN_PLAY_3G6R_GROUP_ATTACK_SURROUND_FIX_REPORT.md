# HumanPlay-3G.6R Group Attack Surround and Continuation Fix Report

## Result

Status: `partial_pass`.

Code repair, diagnostics, and static/compile validation are complete. Unity manual Game View execution is still required for final runtime confirmation of Scenario A/B/C behavior in this environment.

## Root Cause of Non-First Units Stopping

The stop was caused by a high-level order lifecycle gap, not runtime combat semantics:

1. `AttackOrder` had low retry ceilings (`MaxReplans=3`, short repeated rejection thresholds), so non-first attackers could quickly become terminal after transient congestion.
2. Preferred attack approach cells were not persisted/reassigned as target engagement slots across ticks and target movement.
3. On slot/path conflicts (occupied preferred cell, reserved next cell, occupied waypoint), orders reset/replanned too aggressively and could fail early instead of wait/retry.
4. Multi-attacker pressure around one target amplified this path/slot contention: first attacker engaged, others often exhausted retries and stopped.

## Files Changed

- `Assets/Scripts/Presentation/Orders/AttackOrder.cs`
- `Assets/Scripts/Presentation/Orders/GroupOrderPlanner.cs`
- `Assets/Scripts/Presentation/Orders/GroupOrderReservationService.cs`
- `Assets/Scripts/Presentation/Orders/HumanOrderController.cs`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- `HUMAN_PLAY_3G6R_GROUP_ATTACK_SURROUND_FIX_REPORT.md`
- `human_play_3g6r_group_attack_surround_fix_validation.json`

## Focused Diagnostics Added

Prefix: `[HumanGroupAttack3G6R]`

Added coverage:

1. Group attack issue logs in `HumanOrderController.IssueAttackArea()`:
- selected unit count
- attack-capable count
- clicked center/radius
- acquired enemy count
- per-attacker target assignment
- per-attacker preferred attack cell

2. Per-order `AttackOrder` logs at state transitions and submissions:
- attacker id/name/type/grid
- target id/name/type/grid/HP
- attack range
- preferred attack cell
- current order state
- current path length
- next waypoint
- next waypoint occupied/reserved flags
- low-level Move submitted / low-level Attack submitted
- ActionApplier acceptance and rejection reason via `PlayerCommandController.LastCommandAccepted` and `LastCommandRejectedReason`

3. Stop/fail/complete reasons:
- explicit terminal reason in logs
- attacker/target grid and target HP/alive state
- preferred slot
- occupied/reserved ring summary from `GroupOrderReservationService.DescribeAttackRing()`

## Engagement Slot Design (Persistent Per-Target)

Implemented in `GroupOrderReservationService` (extended):

- Persistent per-target slot maps: attacker -> slot around target.
- Target movement invalidation:
  - if target grid changes, old slots for that target are invalidated and recomputed.
- One slot per attacker/target.
- Unique-slot preference:
  - slot picker avoids assigning already-claimed slot when alternatives exist.
- Slot release points:
  - order cancellation
  - order terminal publish
  - target death cleanup
  - attacker replacement/new order via `CancelOrder()` path
- Runtime occupancy remains authoritative:
  - slot is guidance only; order still checks occupancy/reservation/path each tick.

Range handling:

- Melee (`range <= 1`): candidates are Chebyshev distance 1 cells around target.
- Ranged (`range > 1`):
  - prefer current cell when already in range
  - prefer non-adjacent-in-range cells first to avoid melee crowding
  - include adjacent in-range as fallback

## AttackOrder Continuation Fix

`AttackOrder` now:

- Does not terminally fail on first slot/path conflict.
- On occupied/claimed/blocked attack position:
  - waits with `Waiting for attack position.`
  - retries slot acquisition/replan with bounded timeout.
- On reserved or occupied waypoint:
  - waits/replans instead of immediate hard fail.
- On target moved:
  - clears stale path/slot and re-evaluates slot/approach.
- If already in range:
  - attacks immediately, regardless of preferred slot occupancy.
- Ranged in-range units are not forced to move to melee-adjacent cells.
- On attack rejection:
  - out-of-range rejection triggers replan, not immediate terminal stop.
  - non-range rejections are bounded-retried.
- On accepted attack without immediate HP drop:
  - bounded no-damage retries before terminal fail.

## GroupOrderPlanner Improvements

`GroupOrderPlanner.TryPlanGroupAttackApproach()` now:

- Assigns attackers to targets as before (load-balanced deterministic target mapping).
- For each target, assigns unique preferred slots using deterministic path-length-based pair selection:
  - closest viable attacker/slot pair first
  - deterministic tie-breakers by unit and cell order
- Supports mixed melee/ranged slot preference.
- If slots are insufficient, remaining attackers get null preferred slot and rely on dynamic wait/retry behavior.

## Group Order Cancellation/Replacement Cleanup

- `CancelOrder()` path already calls reservation clear; service now also clears attack slot for unit.
- Terminal `AttackOrder` cleanup in `PublishAndRetainTerminal()` safely releases attacker slot and target slot set when target is dead.
- New orders still cancel/replace previous orders before issuing.

## HUD/Status Feedback

`HumanPlayCanvasController.IssueAttackAreaOrder()` now publishes controller reason text directly.

User-visible status examples now emitted by order flow:

- `Group attack: X attackers, Y target(s).`
- `Moving to attack position.`
- `Waiting for attack position.`
- `Replanning attack position.`
- `Attacking target.`
- `Order completed: target destroyed.`
- `Attack failed: ...` (bounded failure reasons)

## Scenario Probe (Manual/Editor)

Manual probe defined for A/B/C with expected logs:

Scenario A:
1. Select 3 Player2 melee units.
2. Attack one Player1 melee unit.
3. Expect:
- one or more attackers engage first,
- others continue moving/waiting/replanning,
- no immediate permanent stop while target alive.
4. Verify `[HumanGroupAttack3G6R]` for slot wait/replan instead of premature terminal fail.

Scenario B:
1. Select 2 melee + 1 ranged Player2 units.
2. Attack one Player1 unit.
3. Expect:
- melee units use different adjacent slots where possible,
- ranged unit attacks from range when possible.

Scenario C:
1. Attack a moving enemy target.
2. Expect:
- `TargetMoved` logs,
- slot/path invalidation and recompute,
- continued approach/attack attempts.

## Command Routing Proof

Routing remains unchanged and per-unit:

`HumanPlayCanvasController -> HumanOrderController -> AttackOrder -> PlayerCommandController.SubmitAttackForUnit / SubmitMoveForUnit -> AgentAction -> ActionApplier.ApplyAction -> MatchManager.ApplyCommand -> runtime step`

No runtime group command was introduced.
No direct transform movement, HP mutation, direct destruction, or `StepMatch` call was added in UI/order code.

## Validation Performed

1. Unity compile/static: `get_errors` reports `No errors found`.
2. Static scans (Orders/UI scope):
- no direct movement bypass (`transform.position=`, `UnitRuntime.MoveTo`, `GridManager.MoveUnit`) in order/UI code
- no direct HP mutation in order/UI code
- no direct unit destroy call in order/UI code
- no direct resource mutation calls in order/UI code
- no `MatchManager.StepMatch` call in order/UI code
3. Changed-file scope audit:
- no `ActionDecoder` change
- no `ActionApplier` semantic change
- no Week7 baseline scene modification
- no Python/training/checkpoint edit by this patch set

## Manual Regression Checklist (to run in Game View)

1. Start Demo.
2. Select 3 Player2 melee units.
3. Issue attack area on one Player1 unit.
4. Confirm first unit attacks.
5. Confirm non-first units continue move/wait/replan/attack while target alive.
6. Confirm no permanent stop while target is alive/reachable.
7. Select mixed melee+ranged and attack one target.
8. Confirm ranged attacks from range where possible.
9. Confirm melee uses different surround positions where possible.
10. Move target; confirm replanning.
11. Press Stop; confirm selected orders cancel.
12. Re-issue group attack; confirm no stale slot lock.
13. Re-check group move, selection, gather, build barracks, production, single attack, single move, pause, camera.

## Known Limitations

- Final runtime pass/fail for scenarios A/B/C still requires manual Game View execution.
- Slot assignment is high-level guidance; runtime occupancy/pathing remains authoritative and can still force bounded wait before eventual fail when truly unreachable.

## Constraints Confirmation

- No Python/training/checkpoint modifications were made by this patch.
- Observation/action contract unchanged.
- `ActionDecoder` semantics unchanged.
- `ActionApplier` semantics unchanged.
- `MatchManager` combat semantics unchanged.
- No edit to `Week7_MLAgents_StudentVsScriptedBot.unity`.
- No UI/order direct move/HP destroy/fake runtime bypass was introduced.
- Commands still route through per-unit `AttackOrder`/`MoveOrder` and normal runtime command application.
