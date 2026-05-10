using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using RTS.Core;
using RTS.Gameplay;
using RTS.ML;
using RTS.MLAgents.Stage7B.CandidateActions;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.TeacherReplay
{
    [DisallowMultipleComponent]
    public sealed class Stage7BTeacherTrajectoryReplayRunner : MonoBehaviour
    {
        [SerializeField] private string _sourceInventoryPath = "python/stage7b_teacher_replay/stage7b_teacher_replay_source_inventory.json";
        [SerializeField] private string _runtimeProbeReportPath = "python/stage7b_teacher_replay/stage7b_teacher_replay_runtime_probe_report.json";
        [SerializeField] private string _replayReadySourceDir = "python/week5_teacher_legacy032/teacher_replay_exports/stage7b_replay_ready_stage7b6g_smoke_20260510T131624Z";
        [SerializeField] private string _unitySyncReportJsonPath = "python/stage7b_teacher_replay/stage7b_unity_replay_sync_report.json";
        [SerializeField] private string _unitySyncReportMdPath = "python/stage7b_teacher_replay/stage7b_unity_replay_sync_report.md";
        [SerializeField] private string _candidateTraceJsonlPath = "python/stage7b_teacher_replay/stage7b_unity_replay_candidate_trace.jsonl";
        [SerializeField] private string _stateSyncTraceJsonlPath = "python/stage7b_teacher_replay/stage7b_unity_replay_state_sync_trace.jsonl";
        [SerializeField] private Owner _playerPerspective = Owner.Player1;
        [SerializeField] private bool _enableRuntimeApply;
        [SerializeField] private bool _runOnStart;

        private readonly Stage7BTeacherTrajectoryLoader _loader = new Stage7BTeacherTrajectoryLoader();

        private void Start()
        {
            if (_runOnStart)
            {
                RunStage7B6HUnityReplaySync();
            }
        }

        [ContextMenu("Run Stage7B-6H Unity Replay Sync")]
        public void RunStage7B6HUnityReplaySync()
        {
            var report = Stage7BTeacherReplayReport.CreateDefault();
            report.generatedAtUtc = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ");
            report.summary = "Stage7B-6H Unity runtime state sync + candidate matching.";
            report.selectedSourcePath = _replayReadySourceDir;
            report.selectedSourceFormat = "legacy032_replay_ready_export";

            var notes = report.notes;
            notes.Add("ML-Agents training/PPO/imitation/.demo were not started by this runner.");

            if (!_loader.TryLoadReplayManifest(_replayReadySourceDir, out Stage7BTeacherReplayManifest manifest, out string manifestDiag))
            {
                report.status = "NO_GO";
                report.IncrementDrop(Stage7BTeacherReplayDropReason.SourceNotReplayReady);
                notes.Add("Failed to load replay manifest: " + manifestDiag);
                WriteFinalArtifacts(report, new List<string>(), new List<string>());
                return;
            }

            List<string> contractErrors = ValidateManifest(manifest);
            if (contractErrors.Count > 0)
            {
                report.IncrementDrop(Stage7BTeacherReplayDropReason.ManifestContractMismatch);
                notes.Add("Manifest contract mismatch: " + string.Join("; ", contractErrors));
            }

            if (!manifest.replay_ready)
            {
                report.IncrementDrop(Stage7BTeacherReplayDropReason.SourceNotReplayReady);
                notes.Add("Manifest replay_ready=false.");
            }

            if (!_loader.TryLoadReplayReadyJsonl(_replayReadySourceDir, out List<Stage7BTeacherTrajectoryStep> steps, out string loadDiag))
            {
                report.status = "NO_GO";
                report.IncrementDrop(Stage7BTeacherReplayDropReason.MissingRuntimeStateT);
                notes.Add("Failed to load replay_ready JSONL: " + loadDiag);
                WriteFinalArtifacts(report, new List<string>(), new List<string>());
                return;
            }

            report.episodesScanned = 1;
            report.episodesReplayAttempted = 1;
            report.stepsTotal = steps.Count;
            report.stepsReplayAttempted = steps.Count;

            MatchManager match = MatchManager.Instance;
            GridManager grid = GridManager.Instance;
            UnitRegistry registry = UnitRegistry.Instance;
            MatchBootstrap bootstrap = MatchBootstrap.Instance;
            ResourceManager resources = ResourceManager.Instance;

            if (match == null || grid == null || registry == null || bootstrap == null || resources == null)
            {
                report.status = "NO_GO";
                report.IncrementDrop(Stage7BTeacherReplayDropReason.UnityStateApiMissing);
                notes.Add("Unity runtime service missing (MatchManager/GridManager/UnitRegistry/MatchBootstrap/ResourceManager). Open Week7 scene first.");
                WriteFinalArtifacts(report, new List<string>(), new List<string>());
                return;
            }

            var synchronizer = new Stage7BTeacherReplayStateSynchronizer(match, grid, registry, bootstrap, resources);
            var resolver = new Stage7BTeacherReplayActionResolver();
            var matcher = new Stage7BTeacherReplayCandidateMatcher();
            var actionApplier = new ActionApplier(grid, registry, match, resources);

            var candidateTraceLines = new List<string>(steps.Count * 2);
            var stateTraceLines = new List<string>(steps.Count);
            var candidateCounts = new List<int>(steps.Count);

            for (int stepIndex = 0; stepIndex < steps.Count; stepIndex++)
            {
                Stage7BTeacherTrajectoryStep step = steps[stepIndex];
                var stateTrace = new Stage7BUnityReplayStateTrace
                {
                    episode_id = step.episodeId,
                    step_id = step.stepId,
                };

                if (!step.HasRuntimeStateTJson)
                {
                    report.stateSyncFailedCount++;
                    report.IncrementDrop(Stage7BTeacherReplayDropReason.MissingRuntimeStateT);
                    stateTrace.state_sync_success = false;
                    stateTrace.drop_reason = "missing_runtime_state_t";
                    stateTrace.message = "runtime_state_t_json missing";
                    stateTraceLines.Add(JsonUtility.ToJson(stateTrace));
                    continue;
                }

                if (!synchronizer.TrySynchronizeRuntimeState(step.runtime_state_t_json, out Stage7BTeacherReplayDropReason syncDrop, out string syncDiagnostics))
                {
                    report.stateSyncFailedCount++;
                    report.IncrementDrop(syncDrop == Stage7BTeacherReplayDropReason.None ? Stage7BTeacherReplayDropReason.StateSyncFailed : syncDrop);
                    stateTrace.state_sync_success = false;
                    stateTrace.drop_reason = ToSnakeCase(syncDrop == Stage7BTeacherReplayDropReason.None ? Stage7BTeacherReplayDropReason.StateSyncFailed : syncDrop);
                    stateTrace.message = syncDiagnostics;
                    stateTraceLines.Add(JsonUtility.ToJson(stateTrace));
                    continue;
                }

                report.stateSyncSuccessCount++;
                stateTrace.state_sync_success = true;
                stateTrace.message = syncDiagnostics;

                var maskBuilder = new ActionMaskBuilder(match, grid, resources, registry, bootstrap);
                var candidateBuilder = new MlAgentsCandidateActionBuilder(maskBuilder);
                MlAgentsCandidateActionList candidates = candidateBuilder.Build(_playerPerspective);

                int candidateCount = candidates.CandidateCount;
                candidateCounts.Add(candidateCount);
                report.candidateOverflowCount += candidates.OverflowCount;
                if (candidates.OverflowCount > 0)
                {
                    report.IncrementDrop(Stage7BTeacherReplayDropReason.CandidateOverflow);
                }

                stateTrace.candidate_count = candidateCount;
                stateTrace.candidate_overflow = candidates.OverflowCount;

                Stage7BTeacherReplayTeacherCommand[] commands = GetTeacherCommands(step);
                if (commands == null || commands.Length == 0)
                {
                    report.IncrementDrop(Stage7BTeacherReplayDropReason.MissingTeacherCommands);
                    stateTrace.drop_reason = "missing_teacher_commands";
                    stateTraceLines.Add(JsonUtility.ToJson(stateTrace));
                    continue;
                }

                for (int commandIndex = 0; commandIndex < commands.Length; commandIndex++)
                {
                    Stage7BTeacherReplayTeacherCommand command = commands[commandIndex];
                    report.teacherCommandsTotal++;
                    if (command.action_type != 0)
                    {
                        report.teacherNonNoOpCommandsTotal++;
                        report.nonNoOpTotal++;
                    }

                    var trace = new Stage7BUnityReplayCandidateTrace
                    {
                        episode_id = step.episodeId,
                        step_id = step.stepId,
                        command_index = commandIndex,
                        actor_flat = command.actor_flat,
                        action_type = command.action_type,
                        state_sync_success = true,
                    };

                    if (!resolver.TryResolveTeacherCommand(command, _playerPerspective, out AgentAction teacherAction, out Stage7BTeacherReplayDropReason resolveDrop))
                    {
                        report.IncrementDrop(resolveDrop);
                        trace.resolved = false;
                        trace.drop_reason = ToSnakeCase(resolveDrop);
                        candidateTraceLines.Add(JsonUtility.ToJson(trace));
                        continue;
                    }

                    trace.resolved = true;
                    trace.actor_x = teacherAction.ActorPosition.X;
                    trace.actor_y = teacherAction.ActorPosition.Y;

                    if (!matcher.TryMatch(teacherAction, candidates, out int candidateIndex, out Stage7BTeacherReplayDropReason matchDrop))
                    {
                        report.IncrementDrop(matchDrop);
                        trace.candidate_match = false;
                        trace.drop_reason = ToSnakeCase(matchDrop);
                        candidateTraceLines.Add(JsonUtility.ToJson(trace));
                        continue;
                    }

                    report.candidateMatchCount++;
                    if (command.action_type != 0)
                    {
                        report.nonNoOpCandidateMatchCount++;
                    }

                    trace.candidate_match = true;
                    trace.candidate_action_index = candidateIndex;

                    if (_enableRuntimeApply)
                    {
                        report.runtimeApplyAttemptedCount++;
                        bool applied = actionApplier.ApplyAction(teacherAction, _playerPerspective);
                        trace.runtime_apply_attempted = true;
                        trace.runtime_apply_accepted = applied;
                        if (applied)
                        {
                            report.runtimeApplyAcceptedCount++;
                        }
                        else
                        {
                            report.runtimeApplyRejectedCount++;
                            report.IncrementDrop(Stage7BTeacherReplayDropReason.RuntimeApplyRejected);
                        }
                    }

                    candidateTraceLines.Add(JsonUtility.ToJson(trace));
                }

                if (_enableRuntimeApply)
                {
                    match.StepMatch();
                }

                if (step.HasRuntimeStateTp1Json)
                {
                    bool postMatch = synchronizer.TryComparePostState(step.runtime_state_tp1_json, out bool terminalMatch, out string postDiag);
                    if (postMatch)
                    {
                        report.postStateMatchCount++;
                    }
                    else
                    {
                        report.postStateMismatchCount++;
                        report.IncrementDrop(Stage7BTeacherReplayDropReason.PostStateDesync);
                    }

                    if (terminalMatch)
                    {
                        report.terminalMatchCount++;
                    }
                    else
                    {
                        report.terminalMismatchCount++;
                        report.IncrementDrop(Stage7BTeacherReplayDropReason.TerminalMismatch);
                    }

                    stateTrace.post_state_message = postDiag;
                }

                stateTraceLines.Add(JsonUtility.ToJson(stateTrace));
            }

            FinalizeCandidateCountStats(report, candidateCounts);
            report.RecomputeRates(stateSyncReliable: report.stateSyncSuccessCount > 0);
            report.demoRecordingReady = report.stateSyncSuccessCount > 0
                                      && report.candidateMatchRate >= 0f
                                      && report.candidateMatchRate >= 0.5f
                                      && (!_enableRuntimeApply || report.runtimeApplyAcceptRate >= 0.5f)
                                      && report.terminalMismatchCount == 0;

            bool hasContractError = contractErrors.Count > 0 || !manifest.replay_ready;
            bool hasStateSync = report.stateSyncSuccessCount > 0;
            bool hasMatchMetrics = report.teacherCommandsTotal > 0 && report.candidateMatchRate >= 0f;
            report.status = hasContractError || !hasStateSync || !hasMatchMetrics ? "NO_GO" : "GO";

            if (!_enableRuntimeApply)
            {
                notes.Add("Runtime apply disabled by configuration (_enableRuntimeApply=false). Candidate matching was measured without applying commands.");
            }

            notes.Add("Stage6B3 baseline/checkpoint assets were not modified by this runner.");
            WriteFinalArtifacts(report, candidateTraceLines, stateTraceLines);
        }

        [ContextMenu("Run Stage7B-6B Prep Probe")]
        public void RunPrepProbe()
        {
            var report = Stage7BTeacherReplayReport.CreateDefault();

            if (_loader.TryLoadSourceInventory(_sourceInventoryPath, out Stage7BTeacherReplaySourceInventoryBrief inventory, out string invDiagnostics))
            {
                report.selectedSourcePath = inventory.selected_source_path;
                report.selectedSourceFormat = inventory.selected_source_format;
                report.summary = inventory.selected_source_replay_ready
                    ? "Selected source is marked replay-ready by inventory."
                    : "Selected source is not replay-ready for authoritative Unity state sync.";

                if (inventory.no_go_required)
                {
                    report.notes.Add("Inventory NO_GO: " + inventory.no_go_reason);
                    report.IncrementDrop(Stage7BTeacherReplayDropReason.MissingRuntimeState);
                }
            }
            else
            {
                report.notes.Add("Failed to load source inventory: " + invDiagnostics);
                report.IncrementDrop(Stage7BTeacherReplayDropReason.SourceSchemaUnknown);
            }

            if (TryBuildRuntimeCandidates(out int candidateCount, out int overflowCount, out string runtimeDiagnostics))
            {
                report.episodesReplayAttempted = 1;
                report.stepsReplayAttempted = 1;
                report.candidateCountMin = candidateCount;
                report.candidateCountMax = candidateCount;
                report.candidateCountMean = candidateCount;
                report.candidateOverflowCount = overflowCount;
                if (overflowCount > 0)
                {
                    report.IncrementDrop(Stage7BTeacherReplayDropReason.CandidateOverflow);
                }

                report.notes.Add("Candidate builder called on live Unity runtime state.");
                report.notes.Add(runtimeDiagnostics);
            }
            else
            {
                report.notes.Add("Runtime candidate probe skipped: " + runtimeDiagnostics);
                report.IncrementDrop(Stage7BTeacherReplayDropReason.MissingRuntimeState);
            }

            // Prep gate remains strict: without authoritative trajectory state synchronization,
            // candidate match metrics and demo readiness cannot be claimed.
            report.status = "NO_GO";
            report.demoRecordingReady = false;
            report.RecomputeRates(stateSyncReliable: false);

            if (_loader.TrySaveRuntimeReport(_runtimeProbeReportPath, report, out string reportPath))
            {
                Debug.Log("[Stage7B][TeacherReplay] Runtime prep probe report written: " + reportPath);
            }
            else
            {
                Debug.LogWarning("[Stage7B][TeacherReplay] Failed to write runtime prep probe report: " + reportPath);
            }
        }

        private void WriteFinalArtifacts(Stage7BTeacherReplayReport report, List<string> candidateTraceLines, List<string> stateTraceLines)
        {
            if (candidateTraceLines != null)
            {
                _loader.TrySaveText(_candidateTraceJsonlPath, string.Join("\n", candidateTraceLines), out _);
            }

            if (stateTraceLines != null)
            {
                _loader.TrySaveText(_stateSyncTraceJsonlPath, string.Join("\n", stateTraceLines), out _);
            }

            if (_loader.TrySaveRuntimeReport(_unitySyncReportJsonPath, report, out string jsonPath))
            {
                _loader.TrySaveText(_unitySyncReportMdPath, BuildMarkdown(report), out _);
                Debug.Log("[Stage7B][TeacherReplay] Unity replay sync report written: " + jsonPath);
            }
            else
            {
                Debug.LogWarning("[Stage7B][TeacherReplay] Failed to write Unity replay sync report: " + jsonPath);
            }
        }

        private static void FinalizeCandidateCountStats(Stage7BTeacherReplayReport report, List<int> candidateCounts)
        {
            if (candidateCounts == null || candidateCounts.Count == 0)
            {
                report.candidateCountMin = -1;
                report.candidateCountMean = -1f;
                report.candidateCountMax = -1;
                return;
            }

            int min = int.MaxValue;
            int max = int.MinValue;
            int sum = 0;
            for (int i = 0; i < candidateCounts.Count; i++)
            {
                int value = candidateCounts[i];
                if (value < min) min = value;
                if (value > max) max = value;
                sum += value;
            }

            report.candidateCountMin = min;
            report.candidateCountMax = max;
            report.candidateCountMean = (float)sum / candidateCounts.Count;
        }

        private static List<string> ValidateManifest(Stage7BTeacherReplayManifest manifest)
        {
            var errors = new List<string>();
            if (manifest == null)
            {
                errors.Add("manifest is null");
                return errors;
            }

            if (!ArrayMatches(manifest.branch_sizes, new[] { 6, 4, 4, 4, 4, 7, 49 })) errors.Add("branch_sizes mismatch");
            if (manifest.attack_target_size != 49) errors.Add("attack_target_size mismatch");
            if (manifest.attack_target_center_index != 24) errors.Add("attack_target_center_index mismatch");
            if (!ArrayMatches(manifest.observation_shape, new[] { 24, 24, 27 })) errors.Add("observation_shape mismatch");
            if (!ArrayMatches(manifest.action_shape, new[] { 576, 7 })) errors.Add("action_shape mismatch");
            return errors;
        }

        private static bool ArrayMatches(int[] a, int[] b)
        {
            if (a == null || b == null || a.Length != b.Length)
            {
                return false;
            }

            for (int i = 0; i < a.Length; i++)
            {
                if (a[i] != b[i]) return false;
            }

            return true;
        }

        private static Stage7BTeacherReplayTeacherCommand[] GetTeacherCommands(Stage7BTeacherTrajectoryStep step)
        {
            if (step == null)
            {
                return Array.Empty<Stage7BTeacherReplayTeacherCommand>();
            }

            if (step.HasTeacherCommandList)
            {
                return step.teacher_commands_list;
            }

            if (!string.IsNullOrWhiteSpace(step.teacher_commands_t_json))
            {
                return ParseCommandArray(step.teacher_commands_t_json);
            }

            if (!string.IsNullOrWhiteSpace(step.teacher_commands))
            {
                return ParseCommandArray(step.teacher_commands);
            }

            return Array.Empty<Stage7BTeacherReplayTeacherCommand>();
        }

        private static Stage7BTeacherReplayTeacherCommand[] ParseCommandArray(string jsonArray)
        {
            if (string.IsNullOrWhiteSpace(jsonArray))
            {
                return Array.Empty<Stage7BTeacherReplayTeacherCommand>();
            }

            string wrapped = "{\"items\":" + jsonArray + "}";
            Stage7BTeacherReplayTeacherCommandArrayWrapper wrapper = JsonUtility.FromJson<Stage7BTeacherReplayTeacherCommandArrayWrapper>(wrapped);
            return wrapper?.items ?? Array.Empty<Stage7BTeacherReplayTeacherCommand>();
        }

        private static string BuildMarkdown(Stage7BTeacherReplayReport report)
        {
            var sb = new StringBuilder(4096);
            sb.AppendLine("# Stage7B Unity Replay Sync Report");
            sb.AppendLine();
            sb.AppendLine("- status: " + report.status);
            sb.AppendLine("- generated_at_utc: " + report.generatedAtUtc);
            sb.AppendLine("- source: " + report.selectedSourcePath);
            sb.AppendLine();
            sb.AppendLine("## Metrics");
            sb.AppendLine();
            sb.AppendLine("- episodes_scanned: " + report.episodesScanned);
            sb.AppendLine("- episodes_replay_attempted: " + report.episodesReplayAttempted);
            sb.AppendLine("- steps_total: " + report.stepsTotal);
            sb.AppendLine("- steps_replay_attempted: " + report.stepsReplayAttempted);
            sb.AppendLine("- teacher_commands_total: " + report.teacherCommandsTotal);
            sb.AppendLine("- teacher_nonnoop_commands_total: " + report.teacherNonNoOpCommandsTotal);
            sb.AppendLine("- state_sync_success_count: " + report.stateSyncSuccessCount);
            sb.AppendLine("- state_sync_failed_count: " + report.stateSyncFailedCount);
            sb.AppendLine("- candidate_count_min: " + ValueOrNull(report.candidateCountMin));
            sb.AppendLine("- candidate_count_mean: " + ValueOrNull(report.candidateCountMean));
            sb.AppendLine("- candidate_count_max: " + ValueOrNull(report.candidateCountMax));
            sb.AppendLine("- candidate_overflow_count: " + report.candidateOverflowCount);
            sb.AppendLine("- candidate_match_count: " + report.candidateMatchCount);
            sb.AppendLine("- candidate_drop_count: " + report.candidateDropCount);
            sb.AppendLine("- candidate_match_rate: " + ValueOrNull(report.candidateMatchRate));
            sb.AppendLine("- nonnoop_candidate_match_count: " + report.nonNoOpCandidateMatchCount);
            sb.AppendLine("- nonnoop_candidate_match_rate: " + ValueOrNull(report.nonNoOpCandidateMatchRate));
            sb.AppendLine("- runtime_apply_attempted_count: " + report.runtimeApplyAttemptedCount);
            sb.AppendLine("- runtime_apply_accepted_count: " + report.runtimeApplyAcceptedCount);
            sb.AppendLine("- runtime_apply_rejected_count: " + report.runtimeApplyRejectedCount);
            sb.AppendLine("- runtime_apply_accept_rate: " + ValueOrNull(report.runtimeApplyAcceptRate));
            sb.AppendLine("- post_state_match_count: " + report.postStateMatchCount);
            sb.AppendLine("- post_state_mismatch_count: " + report.postStateMismatchCount);
            sb.AppendLine("- terminal_match_count: " + report.terminalMatchCount);
            sb.AppendLine("- terminal_mismatch_count: " + report.terminalMismatchCount);
            sb.AppendLine("- demo_recording_ready: " + report.demoRecordingReady.ToString().ToLowerInvariant());
            sb.AppendLine();
            sb.AppendLine("## Drop Reasons");
            sb.AppendLine();
            for (int i = 0; i < report.dropReasonHistogram.Count; i++)
            {
                Stage7BTeacherReplayMetricEntry row = report.dropReasonHistogram[i];
                sb.AppendLine("- " + row.key + ": " + row.value);
            }

            return sb.ToString();
        }

        private static string ValueOrNull(int value)
        {
            return value < 0 ? "null" : value.ToString(CultureInfo.InvariantCulture);
        }

        private static string ValueOrNull(float value)
        {
            return value < 0f ? "null" : value.ToString("0.######", CultureInfo.InvariantCulture);
        }

        private static string ToSnakeCase(Stage7BTeacherReplayDropReason reason)
        {
            var report = Stage7BTeacherReplayReport.CreateDefault();
            report.IncrementDrop(reason);
            if (report.dropReasonHistogram.Count > 0)
            {
                return report.dropReasonHistogram[0].key;
            }

            return "unknown";
        }

        private bool TryBuildRuntimeCandidates(out int candidateCount, out int overflowCount, out string diagnostics)
        {
            candidateCount = 0;
            overflowCount = 0;
            diagnostics = string.Empty;

            MatchManager match = MatchManager.Instance;
            GridManager grid = GridManager.Instance;
            UnitRegistry registry = UnitRegistry.Instance;
            MatchBootstrap bootstrap = MatchBootstrap.Instance;
            ResourceManager resources = ResourceManager.Instance;

            if (match == null || grid == null || registry == null || bootstrap == null)
            {
                diagnostics = "required runtime services are missing (MatchManager/GridManager/UnitRegistry/MatchBootstrap)";
                return false;
            }

            if (match.Phase != MatchPhase.Running)
            {
                diagnostics = "match is not in Running phase";
                return false;
            }

            var maskBuilder = new ActionMaskBuilder(match, grid, resources, registry, bootstrap);
            var candidateBuilder = new MlAgentsCandidateActionBuilder(maskBuilder);
            MlAgentsCandidateActionList candidates = candidateBuilder.Build(_playerPerspective);

            candidateCount = candidates.CandidateCount;
            overflowCount = candidates.OverflowCount;
            diagnostics = "candidate_count=" + candidateCount + ", overflow=" + overflowCount;
            return true;
        }

        [Serializable]
        private sealed class Stage7BUnityReplayCandidateTrace
        {
            public int episode_id;
            public int step_id;
            public int command_index;
            public int actor_flat;
            public int actor_x;
            public int actor_y;
            public int action_type;
            public bool state_sync_success;
            public bool resolved;
            public bool candidate_match;
            public int candidate_action_index;
            public bool runtime_apply_attempted;
            public bool runtime_apply_accepted;
            public string drop_reason;
        }

        [Serializable]
        private sealed class Stage7BUnityReplayStateTrace
        {
            public int episode_id;
            public int step_id;
            public bool state_sync_success;
            public int candidate_count;
            public int candidate_overflow;
            public string drop_reason;
            public string message;
            public string post_state_message;
        }
    }
}
