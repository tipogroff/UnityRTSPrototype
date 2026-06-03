# Performance Validation Report

- Date UTC: 2026-06-03T17:29:03.2955468Z
- Unity version: 6000.3.10f1
- Warmup seconds: 5,0
- Measurement seconds: 30,0

| Mode | Steps | Units | Resources | Speed | Paused | Avg FPS | Min FPS | Avg ms | Worst ms | >33ms | >50ms | GC0 | GC1 | GC2 |
| --- | ---: | ---: | ---: | ---: | :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| AIvsPlayer | 73->793 | 23->46 | 4->4 | 1 | no | 1,1 | 0,9 | 897,1 | 1151,7 | 34 | 34 | 27 | 27 | 27 |
| AIvsBot | 92->644 | 43->62 | 4->3 | 1 | no | 0,8 | 0,7 | 1265,9 | 1435,7 | 24 | 24 | 32 | 32 | 32 |
| AIvsAI | 191->1663 | 34->50 | 4->3 | 1 | no | 39,2 | 2,3 | 25,5 | 441,3 | 99 | 73 | 37 | 37 | 37 |

## Changes Applied
- Added dev-only RuntimePerformanceMonitor with FPS/frame/GC spike logging.
- Added ProfilerMarker coverage for simulation, ML observation/mask/action, registry, combat, and HUD.
- Removed regular hot-path allocations in UnitRegistry, MatchManager command/combat buffers, decision source creation, and selected UI refresh.
- Gated verbose combat/production/human-move logs behind debug flags.
- Changed HUD panels to update text/visibility only when values change.
