# HumanPlay Performance Fix Report

## Summary

This change targets the long-match FPS degradation in HumanPlay / ML-Agents inference mode. The fix keeps the trained ONNX model, Python/training pipeline, observation/action contract, action masks, `ActionApplier` validation, player controls, production, and combat rules intact.

## Main Causes Addressed

- Runtime trace files in `StudentMlAgent` were cleared and appended from inference hot paths.
- Combat target selection used an all-units scan per attacker, producing O(N^2) work as unit count grew.
- Unit presentation components performed per-frame animation/reference/owner checks even though runtime animations are currently not functional.
- Death playback spawned `_DeathGhost` clones with animator work and trace writes.
- Debug overlays and scene scans were enabled by default in some HumanPlay UI/runtime helpers.

## Changed Files

- `Assets/Scripts/MLAgents/Stage7B/StudentMlAgent.cs`
- `Assets/Scripts/Presentation/VisualEventBridge.cs`
- `Assets/Scripts/Presentation/UnitVisualAnimator.cs`
- `Assets/Scripts/Presentation/VisualDeathPlaybackSpawner.cs`
- `Assets/Scripts/Presentation/Visual3EDRuntimeAnimationTrace.cs`
- `Assets/Scripts/Gameplay/Combat/CombatResolver.cs`
- `Assets/Scripts/Gameplay/Match/MatchManager.cs`
- `Assets/Scripts/Presentation/GameSpeedController.cs`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- `Assets/Scripts/Presentation/Debug/RuntimePerformanceMonitor.cs`

## Runtime Traces

`StudentMlAgent` now has opt-in runtime file tracing. When disabled, trace clear/write entrypoints return immediately, including actual collect observation trace, action trace, runtime apply trace, decision scheduler trace, shared JSON append, and trace clear helpers.

`Visual3EDRuntimeAnimationTrace` is disabled by default via a static `Enabled` flag. `Reset` and `Record` do not write JSONL or Markdown unless explicitly enabled.

## Animation, VFX, and Death Playback

Runtime animations and VFX are disabled by default through presentation-level flags. Animation calls now short-circuit before animator parameter checks or VFX instantiation.

Owner color and team marker synchronization remain active. Marker renderer discovery is cached in `UnitVisualAnimator`, so owner visual APIs still work without repeated recursive hierarchy scans.

`VisualDeathPlaybackSpawner` is disabled by default and returns `false` without instantiating `_DeathGhost` objects.

## Combat

Automatic combat target acquisition now scans only grid cells within the attacker's Chebyshev attack range using `GridManager.TryGetOccupant`.

Preserved semantics:

- commanded attackers passed through `skipAttackers` are still skipped by automatic combat;
- no self attacks;
- no allied attacks;
- no neutral targets;
- target must be alive;
- Chebyshev range is preserved;
- tie-breaker remains lower distance, then lower HP.

`TryAttack` and damage/death rules are otherwise unchanged.

## Instrumentation

`RuntimePerformanceMonitor` remains lightweight and uses no per-frame or per-step file I/O. Overlay and spike logging are disabled by default. When enabled, summaries include step, FPS window stats, active units, alive units per player, visual bridge count, death ghost count, last candidate count, and combat attacker/check counters.

## Validation Status

Unity compile validation is required after asset refresh. Long HumanPlay step/FPS validation should be run in the Editor for AI vs Player and any available AI vs Bot / AI vs AI modes.

FPS checkpoints to capture:

- step approximately 500;
- step approximately 1000;
- step approximately 3000;
- step approximately 6000.

## Remaining Risks

- The combat grid lookup assumes grid occupancy is authoritative and up to date, matching existing movement/death code expectations.
- The candidate cache is keyed by match step and preserves mask/action correspondence within a decision cycle; unusual external decision scheduling that mutates state without advancing step should still rebuild only when candidates are null.
- Runtime animation diagnostics are still available but must be explicitly re-enabled for debugging.
