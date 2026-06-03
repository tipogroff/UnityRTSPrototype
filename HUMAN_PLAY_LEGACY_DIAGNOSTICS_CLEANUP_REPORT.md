# HumanPlay Legacy Diagnostics Cleanup Report

## Summary

Normal HumanPlay runtime should no longer update legacy Stage7B diagnostic artifacts in the project working tree. Runtime writers were changed to explicit opt-in, with default serialized flags set to `false`.

## Diagnostic Writers Found

- `Stage7BHeuristicDryRunLogger`
  - Previously wrote `stage7b_mlagents_heuristic_dryrun.json` from `Start`, periodic `Update`, and `OnDisable`.
  - Also refreshed Python/version metadata through external process commands.
- `Stage7BInferenceSmokeDiagnostics`
  - Previously wrote JSON/MD reports, lifecycle trace sync, and agent inventory from periodic `Update` and `OnDisable`.
  - Also used `FindFirstObjectByType` / `FindObjectsByType` for snapshot and inventory generation.
- `Stage7BTrainingFlowDiagnostics`
  - Previously wrote `stage7b_8b6_episode_boundary_fix_report.json/md` from periodic `Update` and `OnDisable`.
- `Week7ScriptedOpponentPacing`
  - Previously wrote `stage7b_week7_scripted_bot_throttle_report.json` at episode finalization.
- `Stage7BResetTimeoutTrace`
  - Contains lifecycle `.jsonl` writes, but already had `Enabled = false` and early returns before file writes.
- `StudentMlAgent`
  - Contains trace file writers guarded by `_enableRuntimeTraceFiles = false`.

## Runtime Writes Disabled

- Added `_enableRuntimeArtifactWrites = false` to `Stage7BHeuristicDryRunLogger`.
  - `Start`, `Update`, `OnDisable`, `WriteArtifact`, and `RefreshEnvironmentVersions` now return early when disabled.
  - Python process version commands do not run unless explicitly opted in.
- Added `_enableRuntimeSmokeDiagnostics = false` to `Stage7BInferenceSmokeDiagnostics`.
  - `OnEnable`, `Start`, `Update`, `OnDisable`, `ForceWriteSnapshot`, `WriteSnapshot`, `WriteAgentInventory`, and `SyncLifecycleTrace` are guarded.
  - No console subscription, snapshot, inventory, lifecycle sync, or `FindObjectsByType` report pass runs by default.
- Added `_enableRuntimeTrainingFlowDiagnostics = false` to `Stage7BTrainingFlowDiagnostics`.
  - `Start`, `Update`, `OnDisable`, and `WriteSnapshot` are guarded.
- Added `_enableRuntimeReportWrite = false` to `Week7ScriptedOpponentPacing`.
  - Pacing/throttle counters still update in memory.
  - Episode finalization no longer writes the JSON report unless opted in.

## Editor/Smoke Opt-In

- `Stage7BHeuristicDryRunMenu` explicitly enables `_enableRuntimeArtifactWrites` only for the dry-run menu command.
- `Stage7BInferenceMode8CMenu` explicitly enables `_enableRuntimeSmokeDiagnostics` only when it creates or prepares smoke diagnostics.
- `Stage7BPpoFineTuneSmokeMenu` explicitly enables `_enableRuntimeTrainingFlowDiagnostics` only for PPO smoke preparation.
- Normal Play Mode does not set these opt-in flags.

## Scene Cleanup

- Active scene checked: `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`.
- Disabled scene components:
  - `Stage7BHeuristicDryRunLogger` on `Stage7B_HeuristicDryRunLogger`.
  - `Stage7BInferenceSmokeDiagnostics` on `Stage7B_MLAgentsTrainingBootstrap`.
- Their serialized opt-in flags are also `false`.
- `Stage7BTrainingFlowDiagnostics` was not found in the active HumanPlay scene.
- `Week7ScriptedOpponentPacing` was not found in the active HumanPlay scene.

## Safe Remaining File Writes

- `Stage7BHeuristicDryRunLogger`: `File.WriteAllText` remains only behind `_enableRuntimeArtifactWrites`.
- `Stage7BInferenceSmokeDiagnostics`: report, inventory, and trace sync writes remain only behind `_enableRuntimeSmokeDiagnostics`.
- `Stage7BTrainingFlowDiagnostics`: report writes remain only behind `_enableRuntimeTrainingFlowDiagnostics`.
- `Week7ScriptedOpponentPacing`: report write remains only behind `_enableRuntimeReportWrite`.
- `Stage7BResetTimeoutTrace`: writes remain behind static `Enabled = false`.
- `StudentMlAgent`: trace writes remain behind `_enableRuntimeTraceFiles = false`.

## Files That Should No Longer Change In Normal HumanPlay

- `stage7b_mlagents_heuristic_dryrun.json`
- `python/stage7b_teacher_replay/stage7b_8b6_episode_boundary_fix_report.json`
- `python/stage7b_teacher_replay/stage7b_8b6_episode_boundary_fix_report.md`
- `python/stage7b_teacher_replay/stage7b_8d1_agent_inventory.json`
- `python/stage7b_teacher_replay/stage7b_8d1_decision_scheduling_fix_report.json`
- `python/stage7b_teacher_replay/stage7b_8d1_decision_scheduling_fix_report.md`
- `python/stage7b_teacher_replay/stage7b_week7_scripted_bot_throttle_report.json`
- related `stage7b_*` JSONL lifecycle/action/runtime trace files.

## Validation

- Unity script refresh/compile requested and completed.
- Script validation completed with `0 errors` for modified runtime and editor scripts.
- Unity console error check returned `0` errors after compile.
- No manual HumanPlay FPS run was performed.

## Manual Verification

- Run normal HumanPlay Play Mode.
- Confirm Git working tree does not receive modified `stage7b_*.json`, `.md`, or `.jsonl` artifacts.
- Confirm FPS drop cadence again after legacy diagnostics are disabled.
- Use explicit editor smoke/dry-run menus only when diagnostic artifact generation is intended.
