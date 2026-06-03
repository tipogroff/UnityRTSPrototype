# HumanPlay Periodic FPS Drop Fix Report

## Summary

This pass targets the stable short FPS drop observed roughly every 0.5 seconds after the long-match degradation fixes.

No new runtime diagnostics, counters, samplers, file writes, or periodic logs were added.

## Changes

- `Assets/Scripts/Presentation/ResourceVisualStateController.cs`
  - Runtime polling is now disabled by default via `_enableRuntimeRefresh = false`.
  - The controller still applies one visual refresh on enable, but no longer performs periodic full resource scans in normal HumanPlay runtime.

- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
  - HUD refresh interval was increased from `0.2` seconds to `1.0` second.
  - Hovered resource updates now run only in manual player mode.
  - Metrics panel refresh now runs only while the metrics panel is visible.

- `Assets/Scripts/Presentation/VisualEventBridge.cs`
  - With runtime animations disabled and owner visuals already synced, `Update()` returns immediately.
  - Missing-reference retries are capped for frequent retries and fall back to a long retry interval.
  - `VisualGridMovementInterpolator` remains non-required while runtime animations are disabled.
  - Owner/team marker color synchronization remains active.

- `Assets/Scripts/Presentation/VisualGridMovementInterpolator.cs`
  - Movement trace remains opt-in only through the existing default-off trace path.

- `Assets/Prefabs/Worker.prefab`
- `Assets/Prefabs/Light.prefab`
- `Assets/Prefabs/Heavy.prefab`
- `Assets/Prefabs/Ranged.prefab`
  - `VisualGridMovementInterpolator.traceEnabled` was set to `false`.

- `Assets/Scripts/Presentation/PlayerCommandController.cs`
  - Command diagnostics default to disabled.

## Disabled By Default

- Resource visual periodic polling.
- High-frequency HUD refresh.
- Metrics refresh while the metrics panel is hidden.
- VisualEventBridge frequent missing-reference retries after repeated failures.
- Movement interpolation trace flags on unit prefabs.
- Player command diagnostics.

## Opt-In Remains

- Resource visual runtime polling can be re-enabled through `_enableRuntimeRefresh`.
- Existing movement and command diagnostics remain available through their debug flags.

## Manual Verification

Not run in this pass. The requested code cleanup has been applied quietly; manual HumanPlay FPS verification remains for local play testing.

## Remaining Risks

- If exhausted resource tint/labels must update live during HumanPlay, an event-driven refresh should be added later instead of restoring periodic full scans.
- Direct click-triggered `[HumanMove3G1R]` logs still exist, but they are not periodic runtime logs.
