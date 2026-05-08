# Stage6B3 Play Mode Performance Diagnostic Report

Date: 2026-05-08

Scene: `Assets/Scenes/Week6_StudentStaticHarvestLayout.unity`

Checkpoint: `python/week6_student/checkpoints/Stage6B3_SemanticObservationFix/legacy032_v2_bc_source_valid_semantic_obs_fix_final.pt`

## Result

Status: GO for stable Play Mode demo.

Status: GO for continuing scripted bot / Player2 soft-idle diagnostic.

Correctness constraints preserved:

- Stage6B3 checkpoint inference remains active.
- Legal parameter-level masking remains enabled.
- ActionApplier and MatchManager validation semantics were not changed.
- Runtime path remains continuous Play Mode through `EpisodeController.FixedUpdate`.
- No heuristic fallback, fake logits, PPO, retraining, teacher, dataset, or checkpoint changes.

## Baseline Findings

Baseline was measured before this performance pass on the current Stage6B3 manual Play Mode binding.

Measured baseline stop summary:

- Runtime: 6.14 s
- Max observed step: 308
- Effective decision rate: ~50.1 decision cycles/sec
- Step 80 cleared: true
- Student accepted commands: 227
- Student rejected commands: 0
- Decision cap remaining at stop: 1692
- Stage10D12R raw observation JSON: enabled every decision
- Raw observation JSON size: ~501 KB/write
- Estimated raw observation JSON bandwidth: ~25 MB/sec at ~50 decisions/sec
- Soft-idle trace/stop JSON: enabled
- Overlay/grid/gizmo path: enabled by serialized runner defaults

External process sample during baseline:

- Unity process average: ~5.1% all-core CPU over a short 20 s sample
- On this machine the displayed process percentage was noisy and did not include all child-process attribution consistently.

## Hotspots

After adding lightweight counters, the final demo run shows the real runtime bottleneck:

1. `Week6StudentPolicyAdapter.ExecuteDecision`
   - 506 calls
   - 45,488 ms total
   - 89.9 ms average

2. `Week6StudentPolicyAdapter.BridgeRoundTrip`
   - 506 calls
   - 27,784 ms total
   - 54.9 ms average

3. `Week6VisualInspectionRunner.Update`
   - 586 ms total across 2,155 frames
   - 0.27 ms average

4. `ActionMaskBuilder.BuildTransferCompatibleMask`
   - 1,012 calls
   - 148 ms total
   - 0.15 ms average

5. `ObservationBuilder.BuildObservation`
   - 507 calls
   - 90.6 ms total
   - 0.18 ms average

Observation/mask/decoder/applier are not the dominant CPU cost. The dominant cost is Stage6B3 Python bridge inference/round-trip.

## Changes Applied

Demo mode:

- FPS cap applied: `Application.targetFrameRate = 30`, `QualitySettings.vSyncCount = 0`.
- Decision cadence capped: `decisionTickIntervalSeconds = 0.2`.
- Overlay disabled.
- Grid labels/gizmos/action markers disabled.
- Per-step JSON trace disabled.
- Stage10D12R full raw observation JSON disabled.
- Verbose adapter logs disabled.
- Lightweight performance summary remains enabled.

Diagnostic mode remains available through runner fields:

- `_runtimeMode = Diagnostic`
- `_enableJsonTrace = true`
- `_enableOverlay = true` if needed
- `_diagnosticSamplingInterval = N`

Profiler mode is represented by:

- `_runtimeMode = Profiler`
- JSON trace off
- overlay/gizmos off
- lightweight counters on

## Inspector Fields Added

`Week6VisualInspectionRunner`:

- `_runtimeMode`
- `_demoMode`
- `_enableOverlay`
- `_enableJsonTrace`
- `_diagnosticSamplingInterval`
- `_targetFrameRate`
- `_decisionTickIntervalSeconds`
- `_enableProfilerCounters`
- `_performanceSummaryRelativePath`

`EpisodeController`:

- `_decisionTickIntervalSeconds`

`Week6StudentPolicyAdapter`:

- `_enableFullRawObservationDiagnostic`

## Before / After

| Metric | Before | After |
| --- | ---: | ---: |
| Max observed step | 308 | 506 |
| Step 80 cleared | true | true |
| Effective decision calls/sec | ~50.1 | ~4.5 |
| Observation builds/sec | ~50+ | 4.5 |
| Legal mask builds/sec | ~100+ | 9.0 |
| Inference calls/sec | ~50.1 | 4.5 |
| JSON/raw observation writes/sec | ~50.1 | 0 |
| Adapter binary/artifact writes/sec | ~50.1 | 4.5 |
| Overlay calls/sec | enabled | 0 |
| Gizmo/grid label calls/sec | enabled | 0 |
| Average FPS | not captured by counters | 19.2 |
| Average frame ms | not captured by counters | 53.9 |
| Unity console errors/warnings | none observed | 0 |
| Student accepted commands | 227 | 8340 |
| Student rejected commands | 0 | 0 |

CPU note: process-level CPU percentage was noisy across Unity Editor, child Python process, and Editor background work. The reliable improvement is reduced hot-path work rate and eliminated raw JSON serialization. The remaining CPU/latency hotspot is Stage6B3 Python bridge inference, not Unity rendering, observation, legal mask, decoder, or ActionApplier.

## Regression

Final run:

- Summary JSON: `stage6b3_playmode_performance_summary.json`
- Elapsed: 112.34 s
- Max/current observed step: 506
- Step 80 cleared: true
- Stage6B3 decisions requested: 506
- Stage6B3 decisions succeeded: 506
- Accepted commands: 8340
- Rejected commands: 0
- Legal mask enabled: true
- Checkpoint unchanged: true
- Overlay calls: 0
- Gizmo calls: 0
- Raw observation JSON files written during final run: 0
- Unity console errors/warnings: 0

## Remaining Risk

The Python bridge is now the dominant runtime cost. Further CPU reduction without weakening correctness should target the bridge implementation, for example:

- asynchronous/non-blocking bridge read path;
- batched or lower-overhead IPC;
- keeping tensors in binary form end-to-end;
- reducing adapter JSON parse/read overhead;
- optional lower demo cadence if acceptable visually.

Do not reduce CPU by disabling legal masks, ActionApplier validation, checkpoint inference, or replacing Stage6B3 with a heuristic fallback.
