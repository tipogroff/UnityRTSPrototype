# HumanPlay-3H.1 HUD Cleanup and Resource UX Report

## Result

Status: `partial_pass`.

UI cleanup and resource UX updates are implemented and compile cleanly. Manual Game View validation remains for final runtime confirmation.

## UI Issue Fixed

The lower command panel still exposed legacy direct-action buttons that were redundant with the RMB context/order flow. This pass removes those obsolete controls and reinforces the RMB-driven control model with clear contextual hints and resource visibility improvements.

## Files Changed

- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- `Assets/Scripts/Presentation/UI/CommandPanelView.cs`
- `Assets/Scripts/Presentation/UI/ContextActionMenuView.cs`
- `Assets/Scripts/Presentation/UI/TopResourceBarView.cs`
- `Assets/Scripts/Presentation/PlayerCommandController.cs`
- `Assets/Scripts/Presentation/ResourceVisualStateController.cs`
- `Assets/Scripts/Presentation/ResourceVisualStateController.cs.meta`
- `HUMAN_PLAY_3H1_HUD_RESOURCE_UX_REPORT.md`
- `human_play_3h1_hud_resource_ux_validation.json`

## Obsolete Buttons Removed/Hidden

From lower command panel:

- Removed direct unit buttons: `Move`, `Harvest`, `Attack`, `Return`.
- Removed lower-panel `Build Barracks` button so build remains RMB-context only.
- Kept `Stop` button and made it relevant to selection (`interactable` only when selection exists).
- Kept selection info + active order status + group status text.

Production panel behavior remains unchanged:

- Base: `Worker`
- Barracks: `Light`, `Heavy`, `Ranged`

## Resource Amount Display Behavior

Because resources are not part of Player2 drag/unit selection (kept unchanged), resource info is shown through hover/context UX:

- Command panel now shows hovered resource info:
  - `Hover resource: X remaining (Active)`
  - `Hover resource: X remaining (Exhausted)`
- If no hovered resource:
  - `Hover resource: none`

This provides real-time remaining amount visibility without changing selection semantics.

## Exhausted Resource Visual Behavior

Added `ResourceVisualStateController` (presentation-only):

- Polls resource unit visuals and `ResourceNode` state.
- Active resources keep normal tint.
- Exhausted resources are tinted gray.
- Exhausted resources show world-space label: `Exhausted`.
- Visual state updates automatically when resource reaches 0.
- No gameplay/resource logic is changed.

## Context Menu Hint Behavior

Enhanced `ContextActionMenuView` with hint text and info-only mode:

- Move/free cell context:
  - Single unit: move hint.
  - Worker on free cell: move/build hint.
  - Multi-select: `Move Group` + group-attack hint.
- Gather context:
  - Active resource: `Gather` with hint `Worker will gather and return automatically.`
  - Exhausted resource: explicit info popup `Resource is exhausted.`
- Attack context:
  - Single: attack hint.
  - Multi: attack area hint.

Also improved occupied-cell worker feedback in `PlayerCommandController`:

- `Build cell is occupied.`

## HUD Hint Behavior

Added compact control hints to command status block (non-intrusive, lower HUD area):

- Single selection hint block:
  - LMB select, Drag select units, RMB empty move, RMB resource gather, RMB enemy attack, RMB free with Worker build, Stop cancel.
- Multi-selection hint block:
  - RMB empty group move, RMB enemy area group attack, Stop cancel.

This supports the current RMB control scheme without reintroducing old action buttons.

## Resource Stockpile in Top Bar

Top bar still shows Player2 stockpile and now uses clearer label:

- `P2 Human Resources: X`

This remains live-updating via `MatchManager.GetResources(Owner.Player2)`.

## Validation Performed

1. Unity compile check:
- `get_errors` reports 0 C# errors in changed scripts and workspace-level diagnostics.

2. Unity console check:
- No new errors from this patch set; existing project warnings remain unrelated.

3. Static safety scans (UI/order presentation scope):
- No direct `ResourceNode` amount mutation in UI/order code.
- No direct `PlayerState` resource mutation in UI/order code.
- No direct movement bypass (`transform.position`, `UnitRuntime.MoveTo`, `GridManager.MoveUnit`) in UI/order code.
- No direct HP mutation or unit destruction in UI/order code.
- No `MatchManager.StepMatch` calls in UI/order code.

4. Hard constraints audit:
- No ActionDecoder changes.
- No ActionApplier changes.
- No Week7 baseline scene modifications.
- No Python/training/checkpoint files edited by this 3H.1 patch set.

## Manual Checklist (for user)

1. Start Demo.
2. Select Worker.
3. Confirm old `Move/Harvest/Attack/Return` lower-panel buttons are gone.
4. Confirm `Stop` remains.
5. RMB empty cell: Move still works.
6. RMB resource: Gather still works.
7. Deplete a resource.
8. Confirm remaining amount reaches 0 in hover info.
9. Confirm exhausted visual state appears (gray + `Exhausted` label).
10. RMB exhausted resource: confirm explicit exhausted message.
11. Select Base: confirm `Produce Worker` remains.
12. Select Barracks: confirm `Light/Heavy/Ranged` production remains.
13. Select multiple units: confirm group hints/status.
14. Confirm Group Move and Attack Area still work.
15. Confirm HUD control hints are readable and non-intrusive.

## Known Limitations

- Manual runtime confirmation is pending in Game View.
- Resource hover info depends on pointer ray hit/cell resolution; behavior is consistent with existing RMB targeting assumptions.
- Exhausted label is static world text (simple presentation) and intentionally lightweight.

## Constraints Confirmation

- No gameplay mechanics added.
- No combat/pathfinding/production/resource runtime semantics changed.
- No direct gameplay mutation from UI (movement/resource/HP/destroy).
- Existing command routing remains unchanged.
