# HumanPlay-3G.3 Production Spawn Helper Report

## Result

Status: `partial_pass`. Static implementation and Unity compilation passed. Manual Game View validation remains for the user.

## Root Cause Fixed

`PlayerCommandController` previously passed runtime `ProducibleUnit` enum values `0/1/2/3` into `AgentAction.ProduceUnitType`. Under Action Contract v2, `ActionApplier` interprets that field as the raw produce branch index. Human Base/Barracks production now uses a presentation-side adapter:

| Human command | Raw v2 payload |
| --- | ---: |
| Base -> Worker | 3 |
| Barracks -> Light | 4 |
| Barracks -> Heavy | 5 |
| Barracks -> Ranged | 6 |

## Files Changed

- `Assets/Scripts/Presentation/Orders/ProductionCommandHelper.cs`
- `Assets/Scripts/Presentation/PlayerCommandController.cs`
- `Assets/Scripts/Presentation/UI/ProductionPanelView.cs`
- `Assets/Scripts/Presentation/UI/CommandPanelView.cs`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- `HUMAN_PLAY_3G3_PRODUCTION_SPAWN_HELPER_REPORT.md`
- `human_play_3g3_production_spawn_helper_validation.json`

## Runtime Path

Human production still routes through:

`PlayerCommandController -> ProductionCommandHelper -> AgentAction -> ActionApplier.ApplyAction(..., Owner.Player2) -> MatchManager.ApplyCommand -> BuildingRuntime -> ProductionQueue -> BuildingRuntime completion spawn`

UI/order code does not instantiate units, call `UnitFactory`, or mutate `PlayerState` resources.

## Runtime Audit

- Base production is restricted to Worker.
- Barracks production is restricted to Light, Heavy, and Ranged.
- `ProductionQueue` holds one current unit at a time.
- `BuildingRuntime.StartProducingUnit` performs authoritative resource spending.
- `BuildingRuntime.HandleProductionComplete` spawns through `UnitFactory`.
- Completion spawn scans free neighboring cells in the surrounding `3x3` area.
- Normal Base/Barracks production does not require the UI to choose spawn direction.

## UI Changes

- Production panel is hidden for no selection, Worker, combat units, and multi-selection.
- Base shows Worker; Barracks shows Light, Heavy, and Ranged.
- Worker -> Build Barracks remains hidden and its legacy public handler rejects until HumanPlay-3G.4.
- HUD shows selected producer, Player2 resources, idle/busy queue state, producing unit progress, last command status, and detected completion.
- Busy queues disable production buttons and show `Production queue is busy.`
- Missing definitions reject with `Unit definition missing.`
- Insufficient resources remain authoritatively rejected by `ActionApplier` with a readable reason.

## Known Limitations

- No spawn-cell reservation was added.
- If all surrounding `3x3` cells become occupied at completion, `BuildingRuntime` logs the failure. The HUD can detect queue completion but cannot distinguish a successful spawn from that runtime failure because no public completion-failure event exists.

## Constraint Confirmation

- No Python, training, or checkpoint files changed by this task.
- No observation/action contract or `ActionDecoder` changes.
- No `ActionApplier` semantic changes.
- No `Week7_MLAgents_StudentVsScriptedBot.unity` changes.
- Move, HarvestLoopOrder, stop/cancel, pause menu, and camera code paths were not modified.

## Manual Checklist

1. Start the game from MainMenu.
2. Start Demo and confirm `HumanPlay_Demo_PlayerVsAI`.
3. Select the Player2 Base and click Produce Worker.
4. Confirm resources decrease through runtime, the queue starts, and Worker appears near Base.
5. Select the Player2 Barracks and produce Light, Heavy, and Ranged as resources allow.
6. While a queue is busy, confirm buttons are disabled and the busy message is visible.
7. With insufficient resources, confirm the readable rejection.
8. Block surrounding cells if practical and confirm the runtime limitation is visible in logs.
9. Confirm RMB Move, Gather loop, Stop/cancel, pause menu, and camera still work.

