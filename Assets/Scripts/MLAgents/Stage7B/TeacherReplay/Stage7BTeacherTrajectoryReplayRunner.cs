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

        // Stage7B-6I: Runtime Apply Validation output paths
        [SerializeField] private string _runtimeApplyReportJsonPath = "python/stage7b_teacher_replay/stage7b_runtime_apply_validation_report.json";
        [SerializeField] private string _runtimeApplyReportMdPath = "python/stage7b_teacher_replay/stage7b_runtime_apply_validation_report.md";
        [SerializeField] private string _runtimeApplyTraceJsonlPath = "python/stage7b_teacher_replay/stage7b_runtime_apply_trace.jsonl";
        [SerializeField] private string _runtimeApplyPostStateTraceJsonlPath = "python/stage7b_teacher_replay/stage7b_runtime_apply_post_state_trace.jsonl";
        [SerializeField] private string _candidateMismatchDiagnosisJsonPath = "python/stage7b_teacher_replay/stage7b_candidate_mismatch_diagnosis.json";

        // Stage7B-6J: Return Direction Mismatch Audit output paths
        // If _6jReplayReadySourceDir is empty, falls back to _replayReadySourceDir.
        [SerializeField] private string _6jReplayReadySourceDir = "";
        [SerializeField] private string _6jAuditReportJsonPath = "python/stage7b_teacher_replay/stage7b_6j_return_direction_audit_report.json";
        [SerializeField] private string _6jAuditReportMdPath = "python/stage7b_teacher_replay/stage7b_6j_return_direction_audit_report.md";
        [SerializeField] private string _6jReturnMismatchesJsonlPath = "python/stage7b_teacher_replay/stage7b_6j_return_direction_mismatches.jsonl";
        [SerializeField] private string _6jRuntimeApplyTraceJsonlPath = "python/stage7b_teacher_replay/stage7b_6j_runtime_apply_trace.jsonl";

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

        [ContextMenu("Run Stage7B-6I Runtime Apply Validation")]
        public void RunStage7B6IUnityRuntimeApplyValidation()
        {
            var report = Stage7BTeacherReplayReport.CreateDefault();
            report.generatedAtUtc = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ");
            report.summary = "Stage7B-6I Unity runtime apply validation (enableRuntimeApply=true).";
            report.selectedSourcePath = _replayReadySourceDir;
            report.selectedSourceFormat = "legacy032_replay_ready_export";
            report.postStateComparisonMode = "partial";

            var notes = report.notes;
            notes.Add("Stage7B-6I: runtime apply mode enabled. ActionApplier.ApplyAction called for each matched candidate.");
            notes.Add("ML-Agents training/PPO/imitation/.demo were not started by this runner.");
            notes.Add("post_state_comparison_mode=partial: unit count, resource node count, player resources, terminal checked. Per-unit x/y not compared.");

            if (!_loader.TryLoadReplayManifest(_replayReadySourceDir, out Stage7BTeacherReplayManifest manifest, out string manifestDiag))
            {
                report.status = "NO_GO";
                report.IncrementDrop(Stage7BTeacherReplayDropReason.SourceNotReplayReady);
                notes.Add("Failed to load replay manifest: " + manifestDiag);
                Write6IArtifacts(report, new List<string>(), new List<string>(), new List<string>(), new List<Stage7BCandidateMismatchDiagnosisEntry>());
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
                Write6IArtifacts(report, new List<string>(), new List<string>(), new List<string>(), new List<Stage7BCandidateMismatchDiagnosisEntry>());
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
                Write6IArtifacts(report, new List<string>(), new List<string>(), new List<string>(), new List<Stage7BCandidateMismatchDiagnosisEntry>());
                return;
            }

            var synchronizer = new Stage7BTeacherReplayStateSynchronizer(match, grid, registry, bootstrap, resources);
            var resolver = new Stage7BTeacherReplayActionResolver();
            var matcher = new Stage7BTeacherReplayCandidateMatcher();
            var actionApplier = new ActionApplier(grid, registry, match, resources);

            var applyTraceLines = new List<string>(steps.Count * 2);
            var postStateTraceLines = new List<string>(steps.Count);
            var stateSyncTraceLines = new List<string>(steps.Count);
            var mismatchEntries = new List<Stage7BCandidateMismatchDiagnosisEntry>();
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
                    stateSyncTraceLines.Add(JsonUtility.ToJson(stateTrace));
                    continue;
                }

                if (!synchronizer.TrySynchronizeRuntimeState(step.runtime_state_t_json, out Stage7BTeacherReplayDropReason syncDrop, out string syncDiagnostics))
                {
                    report.stateSyncFailedCount++;
                    Stage7BTeacherReplayDropReason effectiveDrop = syncDrop == Stage7BTeacherReplayDropReason.None ? Stage7BTeacherReplayDropReason.StateSyncFailed : syncDrop;
                    report.IncrementDrop(effectiveDrop);
                    stateTrace.state_sync_success = false;
                    stateTrace.drop_reason = ToSnakeCase(effectiveDrop);
                    stateTrace.message = syncDiagnostics;
                    stateSyncTraceLines.Add(JsonUtility.ToJson(stateTrace));
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
                    // 6I requirement: no_teacher_command_steps classified separately, NOT as candidateDropCount.
                    report.noTeacherCommandSteps++;
                    stateTrace.drop_reason = "no_teacher_command_step";
                    stateSyncTraceLines.Add(JsonUtility.ToJson(stateTrace));
                    continue;
                }

                bool stepHadApply = false;

                for (int commandIndex = 0; commandIndex < commands.Length; commandIndex++)
                {
                    Stage7BTeacherReplayTeacherCommand command = commands[commandIndex];
                    report.teacherCommandsTotal++;
                    if (command.action_type != 0)
                    {
                        report.teacherNonNoOpCommandsTotal++;
                        report.nonNoOpTotal++;
                    }

                    var applyTrace = new Stage7BRuntimeApplyTraceEntry
                    {
                        episode_id = step.episodeId,
                        step_id = step.stepId,
                        command_index = commandIndex,
                        actor_flat = command.actor_flat,
                        actor_x = command.actor_x,
                        actor_y = command.actor_y,
                        action_type = command.action_type,
                    };

                    if (!resolver.TryResolveTeacherCommand(command, _playerPerspective, out AgentAction teacherAction, out Stage7BTeacherReplayDropReason resolveDrop))
                    {
                        report.IncrementDrop(resolveDrop);
                        applyTrace.action_summary = "resolve_failed:" + ToSnakeCase(resolveDrop);
                        applyTraceLines.Add(JsonUtility.ToJson(applyTrace));
                        continue;
                    }

                    applyTrace.action_summary = BuildActionSummary(teacherAction);

                    if (!matcher.TryMatch(teacherAction, candidates, out int candidateIndex, out Stage7BTeacherReplayDropReason matchDrop))
                    {
                        report.IncrementDrop(matchDrop);
                        applyTrace.action_summary += " | match_failed:" + ToSnakeCase(matchDrop);
                        applyTraceLines.Add(JsonUtility.ToJson(applyTrace));

                        // Diagnose mismatch
                        var diagEntry = DiagnoseMismatch(step.episodeId, step.stepId, commandIndex, command, teacherAction, candidates, matchDrop);
                        mismatchEntries.Add(diagEntry);
                        continue;
                    }

                    report.candidateMatchCount++;
                    if (command.action_type != 0) report.nonNoOpCandidateMatchCount++;

                    // Runtime apply (always enabled in 6I)
                    report.runtimeApplyAttemptedCount++;
                    applyTrace.runtime_apply_attempted = true;
                    bool applied = actionApplier.ApplyAction(teacherAction, _playerPerspective);
                    applyTrace.runtime_apply_accepted = applied;

                    if (applied)
                    {
                        report.runtimeApplyAcceptedCount++;
                        stepHadApply = true;
                    }
                    else
                    {
                        report.runtimeApplyRejectedCount++;
                        report.IncrementDrop(Stage7BTeacherReplayDropReason.RuntimeApplyRejected);

                        // Capture rejection reason
                        string rejectReason = "unknown";
                        if (actionApplier.RejectionReasonsLastStep != null && actionApplier.RejectionReasonsLastStep.Count > 0)
                        {
                            rejectReason = actionApplier.RejectionReasonsLastStep[0];
                        }

                        applyTrace.reject_reason = rejectReason;
                        report.IncrementHistogram(report.runtimeRejectReasonHistogram, rejectReason);
                        report.IncrementHistogram(report.rejectedActionTypeHistogram, ActionTypeToString(command.action_type));

                        if (report.firstRuntimeRejectStep < 0)
                        {
                            report.firstRuntimeRejectStep = step.stepId;
                            report.firstRuntimeRejectActionSummary = applyTrace.action_summary + " | reject:" + rejectReason;
                        }
                    }

                    applyTraceLines.Add(JsonUtility.ToJson(applyTrace));
                }

                // Advance match state if any apply was attempted this step
                if (report.runtimeApplyAttemptedCount > 0 && stepHadApply)
                {
                    match.StepMatch();
                }

                // Post-state comparison
                if (step.HasRuntimeStateTp1Json)
                {
                    bool postMatch = synchronizer.TryComparePostState(step.runtime_state_tp1_json, out bool terminalMatch, out string postDiag);
                    var postStateEntry = new Stage7BRuntimeApplyPostStateTraceEntry
                    {
                        episode_id = step.episodeId,
                        step_id = step.stepId,
                        post_state_matched = postMatch,
                        terminal_matched = terminalMatch,
                        comparison_mode = "partial",
                        diagnostics = postDiag,
                    };
                    postStateTraceLines.Add(JsonUtility.ToJson(postStateEntry));

                    if (postMatch) report.postStateMatchCount++;
                    else
                    {
                        report.postStateMismatchCount++;
                        report.IncrementDrop(Stage7BTeacherReplayDropReason.PostStateDesync);
                    }

                    if (terminalMatch) report.terminalMatchCount++;
                    else
                    {
                        report.terminalMismatchCount++;
                        report.IncrementDrop(Stage7BTeacherReplayDropReason.TerminalMismatch);
                    }

                    stateTrace.post_state_message = postDiag;
                }

                stateSyncTraceLines.Add(JsonUtility.ToJson(stateTrace));
            }

            FinalizeCandidateCountStats(report, candidateCounts);
            report.RecomputeRates(stateSyncReliable: report.stateSyncSuccessCount > 0);
            report.demoRecordingReady = report.stateSyncSuccessCount > 0
                                       && report.candidateMatchRate >= 0f
                                       && report.candidateMatchRate >= 0.5f
                                       && report.runtimeApplyAttemptedCount > 0
                                       && report.runtimeApplyAcceptRate >= 0.5f
                                       && report.terminalMismatchCount == 0;

            bool hasContractError = contractErrors.Count > 0 || !manifest.replay_ready;
            bool hasStateSync = report.stateSyncSuccessCount > 0;
            bool hasMatchMetrics = report.teacherCommandsTotal > 0 && report.candidateMatchRate >= 0f;
            bool hasApplyMetrics = report.runtimeApplyAttemptedCount > 0;
            report.status = hasContractError || !hasStateSync || !hasMatchMetrics || !hasApplyMetrics ? "NO_GO" : "GO";

            notes.Add("no_teacher_command_steps classified separately, not counted in candidateDropCount.");
            notes.Add("Stage6B3 baseline/checkpoint assets were not modified by this runner.");

            Write6IArtifacts(report, applyTraceLines, postStateTraceLines, stateSyncTraceLines, mismatchEntries);
        }

        private string Resolve6JSourceDir()
        {
            if (!string.IsNullOrWhiteSpace(_6jReplayReadySourceDir))
            {
                return _6jReplayReadySourceDir;
            }

            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            string exportsRoot = Path.Combine(projectRoot, "python", "week5_teacher_legacy032", "teacher_replay_exports");
            if (!Directory.Exists(exportsRoot))
            {
                return _replayReadySourceDir;
            }

            string[] dirs = Directory.GetDirectories(exportsRoot, "stage7b_replay_ready_stage7b6j_return_direction_audit_*");
            if (dirs == null || dirs.Length == 0)
            {
                return _replayReadySourceDir;
            }

            string latest = dirs[0];
            DateTime latestTime = Directory.GetLastWriteTimeUtc(latest);
            for (int i = 1; i < dirs.Length; i++)
            {
                DateTime t = Directory.GetLastWriteTimeUtc(dirs[i]);
                if (t > latestTime)
                {
                    latest = dirs[i];
                    latestTime = t;
                }
            }

            string relative = latest.Replace(projectRoot, string.Empty).TrimStart(Path.DirectorySeparatorChar, Path.AltDirectorySeparatorChar);
            return relative.Replace('\\', '/');
        }

        [ContextMenu("Run Stage7B-6J Return Direction Audit")]
        public void RunStage7B6JReturnDirectionAudit()
        {
            string sourceDir = Resolve6JSourceDir();

            var report = Stage7BTeacherReplayReport.CreateDefault();
            report.generatedAtUtc = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ");
            report.summary = "Stage7B-6J Return direction mismatch audit on larger replay-ready export.";
            report.selectedSourcePath = sourceDir;
            report.selectedSourceFormat = "legacy032_replay_ready_export";
            report.postStateComparisonMode = "partial";

            var notes = report.notes;
            notes.Add("Stage7B-6J: Return direction mismatch audit. Runtime apply enabled.");
            notes.Add("ML-Agents training/PPO/imitation/.demo were not started by this runner.");
            notes.Add("post_state_comparison_mode=partial: unit count, resource node count, player resources, terminal checked.");

            if (!_loader.TryLoadReplayManifest(sourceDir, out Stage7BTeacherReplayManifest manifest, out string manifestDiag))
            {
                report.status = "NO_GO";
                report.IncrementDrop(Stage7BTeacherReplayDropReason.SourceNotReplayReady);
                notes.Add("Failed to load replay manifest: " + manifestDiag);
                Write6JArtifacts(report, new List<string>(), new List<Stage7B6JReturnMismatchEntry>());
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

            if (!_loader.TryLoadReplayReadyJsonl(sourceDir, out List<Stage7BTeacherTrajectoryStep> steps, out string loadDiag))
            {
                report.status = "NO_GO";
                report.IncrementDrop(Stage7BTeacherReplayDropReason.MissingRuntimeStateT);
                notes.Add("Failed to load replay_ready JSONL: " + loadDiag);
                Write6JArtifacts(report, new List<string>(), new List<Stage7B6JReturnMismatchEntry>());
                return;
            }

            // Count unique episodes
            var episodeIds = new HashSet<int>();
            for (int i = 0; i < steps.Count; i++) episodeIds.Add(steps[i].episodeId);
            report.episodesScanned = episodeIds.Count;
            report.episodesReplayAttempted = episodeIds.Count;
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
                notes.Add("Unity runtime service missing. Open Week7 scene first.");
                Write6JArtifacts(report, new List<string>(), new List<Stage7B6JReturnMismatchEntry>());
                return;
            }

            var synchronizer = new Stage7BTeacherReplayStateSynchronizer(match, grid, registry, bootstrap, resources);
            var resolver = new Stage7BTeacherReplayActionResolver();
            var matcher = new Stage7BTeacherReplayCandidateMatcher();
            var actionApplier = new ActionApplier(grid, registry, match, resources);

            var applyTraceLines = new List<string>(steps.Count * 2);
            var returnMismatches = new List<Stage7B6JReturnMismatchEntry>();
            var candidateCounts = new List<int>(steps.Count);

            for (int stepIndex = 0; stepIndex < steps.Count; stepIndex++)
            {
                Stage7BTeacherTrajectoryStep step = steps[stepIndex];

                if (!step.HasRuntimeStateTJson)
                {
                    report.stateSyncFailedCount++;
                    report.IncrementDrop(Stage7BTeacherReplayDropReason.MissingRuntimeStateT);
                    continue;
                }

                if (!synchronizer.TrySynchronizeRuntimeState(step.runtime_state_t_json, out Stage7BTeacherReplayDropReason syncDrop, out _))
                {
                    report.stateSyncFailedCount++;
                    Stage7BTeacherReplayDropReason effectiveDrop = syncDrop == Stage7BTeacherReplayDropReason.None
                        ? Stage7BTeacherReplayDropReason.StateSyncFailed : syncDrop;
                    report.IncrementDrop(effectiveDrop);
                    continue;
                }

                report.stateSyncSuccessCount++;

                var maskBuilder = new ActionMaskBuilder(match, grid, resources, registry, bootstrap);
                var candidateBuilder = new MlAgentsCandidateActionBuilder(maskBuilder);
                MlAgentsCandidateActionList candidates = candidateBuilder.Build(_playerPerspective);

                int candidateCount = candidates.CandidateCount;
                candidateCounts.Add(candidateCount);
                report.candidateOverflowCount += candidates.OverflowCount;

                Stage7BTeacherReplayTeacherCommand[] commands = GetTeacherCommands(step);
                if (commands == null || commands.Length == 0)
                {
                    report.noTeacherCommandSteps++;
                    continue;
                }

                bool stepHadApply = false;

                for (int commandIndex = 0; commandIndex < commands.Length; commandIndex++)
                {
                    Stage7BTeacherReplayTeacherCommand command = commands[commandIndex];
                    report.teacherCommandsTotal++;
                    bool isReturn = command.action_type == 3;
                    if (command.action_type != 0)
                    {
                        report.teacherNonNoOpCommandsTotal++;
                        report.nonNoOpTotal++;
                    }

                    if (isReturn) report.returnCommandsTotal++;

                    var applyTrace = new Stage7BRuntimeApplyTraceEntry
                    {
                        episode_id = step.episodeId,
                        step_id = step.stepId,
                        command_index = commandIndex,
                        actor_flat = command.actor_flat,
                        actor_x = command.actor_x,
                        actor_y = command.actor_y,
                        action_type = command.action_type,
                    };

                    if (!resolver.TryResolveTeacherCommand(command, _playerPerspective, out AgentAction teacherAction, out Stage7BTeacherReplayDropReason resolveDrop))
                    {
                        report.IncrementDrop(resolveDrop);
                        if (isReturn) report.returnCommandsDropped++;
                        applyTrace.action_summary = "resolve_failed:" + ToSnakeCase(resolveDrop);
                        applyTraceLines.Add(JsonUtility.ToJson(applyTrace));
                        continue;
                    }

                    applyTrace.action_summary = BuildActionSummary(teacherAction);

                    if (!matcher.TryMatch(teacherAction, candidates, out int candidateIndex, out Stage7BTeacherReplayDropReason matchDrop))
                    {
                        report.totalMismatches++;
                        report.IncrementDrop(matchDrop);
                        if (matchDrop == Stage7BTeacherReplayDropReason.NoMatchingCandidate)
                        {
                            report.noMatchingCandidateCount++;
                        }
                        if (isReturn) report.returnCommandsDropped++;

                        string nearestReason = FindNearestCandidateReason(teacherAction, candidates);
                        if (!string.IsNullOrWhiteSpace(nearestReason) && nearestReason.Contains("direction_mismatch"))
                        {
                            report.directionMismatchCount++;
                        }

                        applyTrace.action_summary += " | match_failed:" + ToSnakeCase(matchDrop) + " nearest:" + nearestReason;
                        applyTraceLines.Add(JsonUtility.ToJson(applyTrace));

                        report.IncrementHistogram(report.mismatchByActionType, ActionTypeToString(command.action_type));
                        report.IncrementHistogram(report.mismatchByDirection, teacherAction.Direction.ToString());

                        // Return-specific direction mismatch tracking
                        if (isReturn && nearestReason != null && nearestReason.StartsWith("direction_mismatch"))
                        {
                            report.returnDirectionMismatchCount++;
                            Direction teacherDir = teacherAction.Direction;
                            bool hasCandidateDir = TryFindNearestReturnCandidateDirection(teacherAction, candidates, out Direction candidateDirEnum);
                            string candidateDir = hasCandidateDir ? candidateDirEnum.ToString() : "none";
                            string teacherDirStr = teacherDir.ToString();

                            report.IncrementHistogram(report.returnMismatchByTeacherDir, teacherDirStr);
                            report.IncrementHistogram(report.returnMismatchByCandidateDir, candidateDir);

                            bool isOpposite = hasCandidateDir && IsOppositeDirection(teacherDir, candidateDirEnum);
                            bool isYFlip = hasCandidateDir && IsYAxisFlip(teacherDir, candidateDirEnum);
                            bool isXFlip = hasCandidateDir && IsXAxisFlip(teacherDir, candidateDirEnum);

                            GridPosition actorPos = teacherAction.ActorPosition;
                            GridPosition teacherTarget = actorPos.Neighbour(teacherDir);
                            GridPosition unityTarget = hasCandidateDir ? actorPos.Neighbour(candidateDirEnum) : actorPos;
                            bool teacherTargetInside = grid.IsInside(teacherTarget);
                            bool unityTargetInside = grid.IsInside(unityTarget);
                            if (!teacherTargetInside) report.teacherTargetOutsideMapCount++;
                            if (!unityTargetInside) report.unityTargetOutsideMapCount++;

                            Owner actorOwner = ResolveActorOwner(grid, actorPos, _playerPerspective);
                            bool teacherHasBase = teacherTargetInside && CellHasFriendlyBase(grid, teacherTarget, actorOwner);
                            bool unityHasBase = unityTargetInside && CellHasFriendlyBase(grid, unityTarget, actorOwner);
                            if (teacherHasBase) report.targetCellHasBaseTeacherSideCount++;
                            if (unityHasBase) report.targetCellHasBaseUnitySideCount++;

                            bool yAxisInversionSuggested = isYFlip && unityHasBase && !teacherHasBase;
                            bool xAxisInversionSuggested = isXFlip && unityHasBase && !teacherHasBase;

                            string nearbySummary = BuildNearbyBaseResourceSummary(grid, actorPos, teacherTarget, unityTarget, actorOwner);

                            if (isOpposite) report.oppositeDirectionCount++;
                            if (isYFlip) report.yAxisFlipSuspectedCount++;
                            if (isXFlip) report.xAxisFlipSuspectedCount++;

                            var entry = new Stage7B6JReturnMismatchEntry
                            {
                                episode_id = step.episodeId,
                                step_id = step.stepId,
                                command_index = commandIndex,
                                actor_flat = command.actor_flat,
                                actor_x = command.actor_x,
                                actor_y = command.actor_y,
                                teacher_dir = teacherDirStr,
                                candidate_dir = candidateDir,
                                teacher_target_x = teacherTarget.X,
                                teacher_target_y = teacherTarget.Y,
                                unity_target_x = unityTarget.X,
                                unity_target_y = unityTarget.Y,
                                teacher_target_inside_map = teacherTargetInside,
                                unity_target_inside_map = unityTargetInside,
                                teacher_target_has_friendly_base = teacherHasBase,
                                unity_target_has_friendly_base = unityHasBase,
                                is_opposite = isOpposite,
                                is_y_axis_flip = isYFlip,
                                is_x_axis_flip = isXFlip,
                                y_axis_inversion_suggested = yAxisInversionSuggested,
                                x_axis_inversion_suggested = xAxisInversionSuggested,
                                nearest_candidate_reason = nearestReason,
                                teacher_command_json = JsonUtility.ToJson(command),
                                base_resource_nearby_summary = nearbySummary,
                                candidate_count = candidates != null ? candidates.CandidateCount : 0,
                                candidate_list_summary = BuildCandidateListSummary(candidates),
                            };
                            returnMismatches.Add(entry);

                            if (report.first10ReturnMismatches.Count < 10)
                            {
                                report.first10ReturnMismatches.Add(
                                    "ep=" + step.episodeId
                                    + ",step=" + step.stepId
                                    + ",actor=(" + command.actor_x + "," + command.actor_y + ")"
                                    + ",teacher_dir=" + teacherDirStr
                                    + ",candidate_dir=" + candidateDir
                                    + ",nearest=" + nearestReason);
                            }
                        }

                        continue;
                    }

                    report.candidateMatchCount++;
                    if (command.action_type != 0) report.nonNoOpCandidateMatchCount++;
                    if (isReturn) report.returnCommandsMatched++;

                    // Runtime apply always enabled in 6J
                    report.runtimeApplyAttemptedCount++;
                    applyTrace.runtime_apply_attempted = true;
                    bool applied = actionApplier.ApplyAction(teacherAction, _playerPerspective);
                    applyTrace.runtime_apply_accepted = applied;

                    if (applied)
                    {
                        report.runtimeApplyAcceptedCount++;
                        stepHadApply = true;
                    }
                    else
                    {
                        report.runtimeApplyRejectedCount++;
                        report.IncrementDrop(Stage7BTeacherReplayDropReason.RuntimeApplyRejected);

                        string rejectReason = "unknown";
                        if (actionApplier.RejectionReasonsLastStep != null && actionApplier.RejectionReasonsLastStep.Count > 0)
                            rejectReason = actionApplier.RejectionReasonsLastStep[0];

                        applyTrace.reject_reason = rejectReason;
                        report.IncrementHistogram(report.runtimeRejectReasonHistogram, rejectReason);
                        report.IncrementHistogram(report.rejectedActionTypeHistogram, ActionTypeToString(command.action_type));

                        if (report.firstRuntimeRejectStep < 0)
                        {
                            report.firstRuntimeRejectStep = step.stepId;
                            report.firstRuntimeRejectActionSummary = applyTrace.action_summary + " | reject:" + rejectReason;
                        }
                    }

                    applyTraceLines.Add(JsonUtility.ToJson(applyTrace));
                }

                if (report.runtimeApplyAttemptedCount > 0 && stepHadApply)
                    match.StepMatch();

                // Post-state comparison (partial)
                if (step.HasRuntimeStateTp1Json)
                {
                    bool postMatch = synchronizer.TryComparePostState(step.runtime_state_tp1_json, out bool terminalMatch, out _);
                    if (postMatch) report.postStateMatchCount++;
                    else
                    {
                        report.postStateMismatchCount++;
                        report.IncrementDrop(Stage7BTeacherReplayDropReason.PostStateDesync);
                    }

                    if (terminalMatch) report.terminalMatchCount++;
                    else
                    {
                        report.terminalMismatchCount++;
                        report.IncrementDrop(Stage7BTeacherReplayDropReason.TerminalMismatch);
                    }
                }
            }

            FinalizeCandidateCountStats(report, candidateCounts);
            report.RecomputeRates(stateSyncReliable: report.stateSyncSuccessCount > 0);
            report.RecomputeReturnStats();

            report.demoRecordingReady = report.stateSyncSuccessCount > 0
                                       && report.candidateMatchRate >= 0.5f
                                       && report.runtimeApplyAttemptedCount > 0
                                       && report.runtimeApplyAcceptRate >= 0.5f
                                       && report.terminalMismatchCount == 0;

            bool hasContractError = contractErrors.Count > 0 || !manifest.replay_ready;
            bool hasStateSync = report.stateSyncSuccessCount > 0;
            bool hasMatchMetrics = report.teacherCommandsTotal > 0 && report.candidateMatchRate >= 0f;
            bool hasApplyMetrics = report.runtimeApplyAttemptedCount > 0;
            report.status = hasContractError || !hasStateSync || !hasMatchMetrics || !hasApplyMetrics ? "NO_GO" : "GO";

            notes.Add("no_teacher_command_steps classified separately, not counted in candidateDropCount.");
            notes.Add("Stage6B3 baseline/checkpoint assets were not modified by this runner.");

            Write6JArtifacts(report, applyTraceLines, returnMismatches);
        }

        private void Write6JArtifacts(
            Stage7BTeacherReplayReport report,
            List<string> applyTraceLines,
            List<Stage7B6JReturnMismatchEntry> returnMismatches)
        {
            _loader.TrySaveText(_6jRuntimeApplyTraceJsonlPath, string.Join("\n", applyTraceLines), out _);

            // Return mismatch JSONL
            var mismatchLines = new List<string>(returnMismatches.Count);
            for (int i = 0; i < returnMismatches.Count; i++)
                mismatchLines.Add(JsonUtility.ToJson(returnMismatches[i]));
            _loader.TrySaveText(_6jReturnMismatchesJsonlPath, string.Join("\n", mismatchLines), out _);

            string patternHypothesis = ComputePatternHypothesis(report, returnMismatches);

            if (_loader.TrySaveRuntimeReport(_6jAuditReportJsonPath, report, out string jsonPath))
            {
                _loader.TrySaveText(_6jAuditReportMdPath, BuildMarkdown6J(report, returnMismatches, patternHypothesis), out _);
                Debug.Log("[Stage7B][TeacherReplay] Stage7B-6J return direction audit report written: " + jsonPath);
            }
            else
            {
                Debug.LogWarning("[Stage7B][TeacherReplay] Failed to write Stage7B-6J report: " + jsonPath);
            }
        }

        private static string ComputePatternHypothesis(Stage7BTeacherReplayReport report, List<Stage7B6JReturnMismatchEntry> returnMismatches)
        {
            if (returnMismatches == null || returnMismatches.Count == 0) return "no_return_direction_mismatches";
            int total = returnMismatches.Count;
            if (report.yAxisFlipSuspectedCount == total) return "y_axis_flip_systematic (all Return mismatches are North<->South)";
            if (report.xAxisFlipSuspectedCount == total) return "x_axis_flip_systematic (all Return mismatches are East<->West)";
            if (report.oppositeDirectionCount == total) return "opposite_direction_systematic (all Return mismatches have opposite teacher/candidate dir)";
            if (report.yAxisFlipSuspectedCount > total / 2) return "y_axis_flip_dominant (majority of Return mismatches are North<->South)";
            if (report.xAxisFlipSuspectedCount > total / 2) return "x_axis_flip_dominant (majority of Return mismatches are East<->West)";
            return "mixed_direction_mismatch (no clear single axis pattern)";
        }

        private static string BuildMarkdown6J(Stage7BTeacherReplayReport report, List<Stage7B6JReturnMismatchEntry> returnMismatches, string patternHypothesis)
        {
            var sb = new StringBuilder(4096);
            sb.AppendLine("# Stage7B-6J Return Direction Mismatch Audit Report");
            sb.AppendLine();
            sb.AppendLine("- status: " + report.status);
            sb.AppendLine("- generated_at_utc: " + report.generatedAtUtc);
            sb.AppendLine("- source: " + report.selectedSourcePath);
            sb.AppendLine();
            sb.AppendLine("## General Metrics");
            sb.AppendLine();
            sb.AppendLine("- episodes_scanned: " + report.episodesScanned);
            sb.AppendLine("- episodes_replay_attempted: " + report.episodesReplayAttempted);
            sb.AppendLine("- steps_total: " + report.stepsTotal);
            sb.AppendLine("- steps_replay_attempted: " + report.stepsReplayAttempted);
            sb.AppendLine("- teacher_commands_total: " + report.teacherCommandsTotal);
            sb.AppendLine("- teacher_nonnoop_commands_total: " + report.teacherNonNoOpCommandsTotal);
            sb.AppendLine("- no_teacher_command_steps: " + report.noTeacherCommandSteps);
            sb.AppendLine("- state_sync_success_count: " + report.stateSyncSuccessCount);
            sb.AppendLine("- state_sync_failed_count: " + report.stateSyncFailedCount);
            sb.AppendLine("- candidate_count_min: " + ValueOrNull(report.candidateCountMin));
            sb.AppendLine("- candidate_count_mean: " + ValueOrNull(report.candidateCountMean));
            sb.AppendLine("- candidate_count_max: " + ValueOrNull(report.candidateCountMax));
            sb.AppendLine("- candidate_match_count: " + report.candidateMatchCount);
            sb.AppendLine("- candidate_drop_count: " + report.candidateDropCount);
            sb.AppendLine("- candidate_match_rate: " + ValueOrNull(report.candidateMatchRate));
            sb.AppendLine("- nonnoop_candidate_match_rate: " + ValueOrNull(report.nonNoOpCandidateMatchRate));
            sb.AppendLine("- runtime_apply_attempted_count: " + report.runtimeApplyAttemptedCount);
            sb.AppendLine("- runtime_apply_accepted_count: " + report.runtimeApplyAcceptedCount);
            sb.AppendLine("- runtime_apply_rejected_count: " + report.runtimeApplyRejectedCount);
            sb.AppendLine("- runtime_apply_accept_rate: " + ValueOrNull(report.runtimeApplyAcceptRate));
            sb.AppendLine("- total_mismatches: " + report.totalMismatches);
            sb.AppendLine("- no_matching_candidate_count: " + report.noMatchingCandidateCount);
            sb.AppendLine("- direction_mismatch_count: " + report.directionMismatchCount);
            sb.AppendLine("- post_state_match_count: " + report.postStateMatchCount);
            sb.AppendLine("- post_state_mismatch_count: " + report.postStateMismatchCount);
            sb.AppendLine("- terminal_match_count: " + report.terminalMatchCount);
            sb.AppendLine("- terminal_mismatch_count: " + report.terminalMismatchCount);
            sb.AppendLine("- demo_recording_ready: " + report.demoRecordingReady.ToString().ToLowerInvariant());
            sb.AppendLine();
            sb.AppendLine("## Return Direction Audit");
            sb.AppendLine();
            sb.AppendLine("- return_commands_total: " + report.returnCommandsTotal);
            sb.AppendLine("- return_commands_matched: " + report.returnCommandsMatched);
            sb.AppendLine("- return_commands_dropped: " + report.returnCommandsDropped);
            sb.AppendLine("- return_match_rate: " + ValueOrNull(report.returnMatchRate));
            sb.AppendLine("- return_direction_mismatch_count: " + report.returnDirectionMismatchCount);
            sb.AppendLine("- return_direction_mismatch_rate: " + ValueOrNull(report.returnDirectionMismatchRate));
            sb.AppendLine("- opposite_direction_count: " + report.oppositeDirectionCount);
            sb.AppendLine("- y_axis_flip_suspected_count: " + report.yAxisFlipSuspectedCount);
            sb.AppendLine("- x_axis_flip_suspected_count: " + report.xAxisFlipSuspectedCount);
            sb.AppendLine("- teacher_target_outside_map_count: " + report.teacherTargetOutsideMapCount);
            sb.AppendLine("- unity_target_outside_map_count: " + report.unityTargetOutsideMapCount);
            sb.AppendLine("- target_cell_has_base_teacher_side_count: " + report.targetCellHasBaseTeacherSideCount);
            sb.AppendLine("- target_cell_has_base_unity_side_count: " + report.targetCellHasBaseUnitySideCount);
            sb.AppendLine("- pattern_hypothesis: " + patternHypothesis);
            sb.AppendLine();
            sb.AppendLine("### Mismatch by Action Type");
            sb.AppendLine();
            for (int i = 0; i < report.mismatchByActionType.Count; i++)
                sb.AppendLine("- " + report.mismatchByActionType[i].key + ": " + report.mismatchByActionType[i].value);
            sb.AppendLine();
            sb.AppendLine("### Mismatch by Teacher Direction");
            sb.AppendLine();
            for (int i = 0; i < report.mismatchByDirection.Count; i++)
                sb.AppendLine("- " + report.mismatchByDirection[i].key + ": " + report.mismatchByDirection[i].value);
            sb.AppendLine();
            sb.AppendLine("### Return Mismatch by Teacher Direction");
            sb.AppendLine();
            for (int i = 0; i < report.returnMismatchByTeacherDir.Count; i++)
                sb.AppendLine("- " + report.returnMismatchByTeacherDir[i].key + ": " + report.returnMismatchByTeacherDir[i].value);
            sb.AppendLine();
            sb.AppendLine("### Return Mismatch by Candidate Direction");
            sb.AppendLine();
            for (int i = 0; i < report.returnMismatchByCandidateDir.Count; i++)
                sb.AppendLine("- " + report.returnMismatchByCandidateDir[i].key + ": " + report.returnMismatchByCandidateDir[i].value);
            sb.AppendLine();
            sb.AppendLine("## GO / HOLD Decision");
            sb.AppendLine();
            float rdRate = report.returnDirectionMismatchRate;
            string decision;
            if (rdRate < 0f)
                decision = "NO_DATA: returnCommandsTotal=0 — cannot measure Return direction mismatch rate.";
            else if (rdRate <= 0.10f)
                decision = "GO_TO_STAGE7B_7: return_direction_mismatch_rate=" + rdRate.ToString("0.####", CultureInfo.InvariantCulture)
                    + " is low. Return mismatches are non-blocking. Demo recording can proceed.";
            else
                decision = "HOLD_FOR_STAGE7B_6K_FIX: return_direction_mismatch_rate=" + rdRate.ToString("0.####", CultureInfo.InvariantCulture)
                    + " exceeds 10% threshold. Pattern hypothesis: " + patternHypothesis
                    + ". Direction mapping fix required before large demo recording.";
            sb.AppendLine("**Decision: " + decision + "**");
            sb.AppendLine();
            sb.AppendLine("## First Return Direction Mismatches (up to 10)");
            sb.AppendLine();
            int limit = System.Math.Min(returnMismatches == null ? 0 : returnMismatches.Count, 10);
            if (limit == 0)
            {
                sb.AppendLine("- (none)");
            }
            else
            {
                for (int i = 0; i < limit; i++)
                {
                    Stage7B6JReturnMismatchEntry m = returnMismatches[i];
                    sb.AppendLine("### Mismatch " + (i + 1) + ": episode=" + m.episode_id + " step=" + m.step_id);
                    sb.AppendLine("- actor: (" + m.actor_x + "," + m.actor_y + ") flat=" + m.actor_flat);
                    sb.AppendLine("- teacher_dir: " + m.teacher_dir + " | candidate_dir: " + m.candidate_dir);
                    sb.AppendLine("- is_opposite: " + m.is_opposite + " | is_y_axis_flip: " + m.is_y_axis_flip + " | is_x_axis_flip: " + m.is_x_axis_flip);
                    sb.AppendLine("- nearest_candidate_reason: " + m.nearest_candidate_reason);
                    sb.AppendLine("- teacher_target: (" + m.teacher_target_x + "," + m.teacher_target_y + ") inside=" + m.teacher_target_inside_map + " has_base=" + m.teacher_target_has_friendly_base);
                    sb.AppendLine("- unity_target: (" + m.unity_target_x + "," + m.unity_target_y + ") inside=" + m.unity_target_inside_map + " has_base=" + m.unity_target_has_friendly_base);
                    sb.AppendLine("- inversion_suggested: y=" + m.y_axis_inversion_suggested + " x=" + m.x_axis_inversion_suggested);
                    sb.AppendLine("- base_resource_nearby_summary: " + m.base_resource_nearby_summary);
                    sb.AppendLine();
                }
            }

            sb.AppendLine("## first_10_return_mismatches");
            sb.AppendLine();
            if (report.first10ReturnMismatches == null || report.first10ReturnMismatches.Count == 0)
            {
                sb.AppendLine("- (none)");
            }
            else
            {
                for (int i = 0; i < report.first10ReturnMismatches.Count; i++)
                {
                    sb.AppendLine("- " + report.first10ReturnMismatches[i]);
                }
            }

            sb.AppendLine("## Drop Reasons");
            sb.AppendLine();
            for (int i = 0; i < report.dropReasonHistogram.Count; i++)
                sb.AppendLine("- " + report.dropReasonHistogram[i].key + ": " + report.dropReasonHistogram[i].value);
            sb.AppendLine();
            sb.AppendLine("## Notes");
            sb.AppendLine();
            for (int i = 0; i < report.notes.Count; i++)
                sb.AppendLine("- " + report.notes[i]);

            return sb.ToString();
        }

        private static bool TryFindNearestReturnCandidateDirection(AgentAction teacherAction, MlAgentsCandidateActionList candidates, out Direction direction)
        {
            direction = Direction.North;
            if (candidates == null) return false;
            for (int i = 0; i < candidates.AvailableCandidates.Count; i++)
            {
                MlAgentsCandidateAction c = candidates.AvailableCandidates[i];
                if (!c.IsEmpty
                    && c.Action.ActorPosition == teacherAction.ActorPosition
                    && c.Action.ActionType == teacherAction.ActionType)
                {
                    direction = c.Action.Direction;
                    return true;
                }
            }

            return false;
        }

        private static Owner ResolveActorOwner(GridManager grid, GridPosition actorPos, Owner fallback)
        {
            if (grid != null && grid.TryGetOccupant(actorPos, out UnitRuntime actor) && actor != null)
            {
                return actor.Owner;
            }

            return fallback;
        }

        private static bool CellHasFriendlyBase(GridManager grid, GridPosition pos, Owner owner)
        {
            if (grid == null || !grid.IsInside(pos)) return false;
            UnitRuntime occupant = grid.GetOccupant(pos);
            return occupant != null && occupant.Type == UnitType.Base && occupant.Owner == owner;
        }

        private static string BuildNearbyBaseResourceSummary(GridManager grid, GridPosition actorPos, GridPosition teacherTarget, GridPosition unityTarget, Owner owner)
        {
            if (grid == null)
            {
                return "grid_missing";
            }

            int actorAdjFriendlyBase = CountAdjacentType(grid, actorPos, owner, UnitType.Base);
            int actorAdjResource = CountAdjacentType(grid, actorPos, Owner.Neutral, UnitType.Resource);
            int teacherAdjFriendlyBase = CountAdjacentType(grid, teacherTarget, owner, UnitType.Base);
            int unityAdjFriendlyBase = CountAdjacentType(grid, unityTarget, owner, UnitType.Base);

            return "actor_adj_friendly_base=" + actorAdjFriendlyBase
                 + ",actor_adj_resource=" + actorAdjResource
                 + ",teacher_target_adj_friendly_base=" + teacherAdjFriendlyBase
                 + ",unity_target_adj_friendly_base=" + unityAdjFriendlyBase;
        }

        private static int CountAdjacentType(GridManager grid, GridPosition center, Owner owner, UnitType type)
        {
            if (grid == null || !grid.IsInside(center)) return 0;
            int count = 0;
            List<GridPosition> neighbors = grid.GetValidNeighbours(center);
            for (int i = 0; i < neighbors.Count; i++)
            {
                UnitRuntime u = grid.GetOccupant(neighbors[i]);
                if (u != null && u.Type == type && u.Owner == owner)
                {
                    count++;
                }
            }

            return count;
        }

        private static bool IsOppositeDirection(Direction a, Direction b)
        {
            return (a == Direction.North && b == Direction.South)
                || (a == Direction.South && b == Direction.North)
                || (a == Direction.East && b == Direction.West)
                || (a == Direction.West && b == Direction.East);
        }

        private static bool IsYAxisFlip(Direction a, Direction b)
        {
            return (a == Direction.North && b == Direction.South)
                || (a == Direction.South && b == Direction.North);
        }

        private static bool IsXAxisFlip(Direction a, Direction b)
        {
            return (a == Direction.East && b == Direction.West)
                || (a == Direction.West && b == Direction.East);
        }

        private void Write6IArtifacts(
            Stage7BTeacherReplayReport report,
            List<string> applyTraceLines,
            List<string> postStateTraceLines,
            List<string> stateSyncTraceLines,
            List<Stage7BCandidateMismatchDiagnosisEntry> mismatchEntries)
        {
            _loader.TrySaveText(_runtimeApplyTraceJsonlPath, string.Join("\n", applyTraceLines), out _);
            _loader.TrySaveText(_runtimeApplyPostStateTraceJsonlPath, string.Join("\n", postStateTraceLines), out _);

            // Also write the state sync trace for cross-reference
            _loader.TrySaveText(_stateSyncTraceJsonlPath, string.Join("\n", stateSyncTraceLines), out _);

            // Candidate mismatch diagnosis
            var diagReport = new Stage7BCandidateMismatchDiagnosisReport
            {
                generated_at_utc = report.generatedAtUtc,
                total_mismatches = mismatchEntries.Count,
                mismatches = mismatchEntries.ToArray(),
            };
            _loader.TrySaveText(_candidateMismatchDiagnosisJsonPath, JsonUtility.ToJson(diagReport, true), out _);

            if (_loader.TrySaveRuntimeReport(_runtimeApplyReportJsonPath, report, out string jsonPath))
            {
                _loader.TrySaveText(_runtimeApplyReportMdPath, BuildMarkdown6I(report, mismatchEntries), out _);
                Debug.Log("[Stage7B][TeacherReplay] Stage7B-6I runtime apply validation report written: " + jsonPath);
            }
            else
            {
                Debug.LogWarning("[Stage7B][TeacherReplay] Failed to write Stage7B-6I report: " + jsonPath);
            }
        }

        private Stage7BCandidateMismatchDiagnosisEntry DiagnoseMismatch(
            int episodeId, int stepId, int commandIndex,
            Stage7BTeacherReplayTeacherCommand command,
            AgentAction teacherAction,
            MlAgentsCandidateActionList candidates,
            Stage7BTeacherReplayDropReason dropReason)
        {
            var entry = new Stage7BCandidateMismatchDiagnosisEntry
            {
                episode_id = episodeId,
                step_id = stepId,
                command_index = commandIndex,
                actor_flat = command.actor_flat,
                actor_x = command.actor_x,
                actor_y = command.actor_y,
                action_type = command.action_type,
                action_type_name = ActionTypeToString(command.action_type),
                move_dir = command.move_dir,
                produce_dir = command.produce_dir,
                produce_unit_type = command.produce_unit_type,
                target_x = command.target_x,
                target_y = command.target_y,
                drop_reason = ToSnakeCase(dropReason),
                candidate_count = candidates != null ? candidates.CandidateCount : 0,
            };

            // Diagnose nearest candidate reason
            entry.nearest_candidate_reason = FindNearestCandidateReason(teacherAction, candidates);

            // Summarize candidate list
            entry.candidate_list_summary = BuildCandidateListSummary(candidates);

            return entry;
        }

        private static string FindNearestCandidateReason(AgentAction teacherAction, MlAgentsCandidateActionList candidates)
        {
            if (candidates == null || candidates.AvailableCandidates.Count == 0)
            {
                return "no_candidates_available";
            }

            bool actorFound = false;
            bool actionTypeFound = false;

            for (int i = 0; i < candidates.AvailableCandidates.Count; i++)
            {
                MlAgentsCandidateAction c = candidates.AvailableCandidates[i];
                if (c.IsEmpty) continue;

                if (c.Action.ActorPosition == teacherAction.ActorPosition)
                {
                    actorFound = true;
                    if (c.Action.ActionType == teacherAction.ActionType)
                    {
                        actionTypeFound = true;
                        // Actor and type match but something else differs
                        switch (teacherAction.ActionType)
                        {
                            case UnitActionType.Move:
                            case UnitActionType.Harvest:
                            case UnitActionType.Return:
                                if (c.Action.Direction != teacherAction.Direction)
                                    return "direction_mismatch (actor=" + teacherAction.ActorPosition + ", type=" + teacherAction.ActionType + ", teacher_dir=" + teacherAction.Direction + ", cand_dir=" + c.Action.Direction + ")";
                                break;
                            case UnitActionType.Produce:
                                if (c.Action.Direction != teacherAction.Direction)
                                    return "produce_direction_mismatch (teacher_dir=" + teacherAction.Direction + ")";
                                if ((int)c.Action.ProduceUnitType != (int)teacherAction.ProduceUnitType)
                                    return "produce_type_mismatch (teacher=" + teacherAction.ProduceUnitType + ")";
                                break;
                            case UnitActionType.Attack:
                                if (c.Action.AttackTargetPosition != teacherAction.AttackTargetPosition)
                                    return "attack_target_mismatch (teacher_target=" + teacherAction.AttackTargetPosition + ")";
                                break;
                        }
                    }
                }
            }

            if (!actorFound) return "actor_missing_from_candidates (actor=" + teacherAction.ActorPosition + ")";
            if (!actionTypeFound) return "action_type_missing_from_candidates (actor=" + teacherAction.ActorPosition + ", type=" + teacherAction.ActionType + ")";
            return "parameter_mismatch (actor and type found but parameters differ)";
        }

        private static string BuildCandidateListSummary(MlAgentsCandidateActionList candidates)
        {
            if (candidates == null) return "null";
            var sb = new StringBuilder();
            sb.Append("[");
            int limit = System.Math.Min(candidates.AvailableCandidates.Count, 20);
            for (int i = 0; i < limit; i++)
            {
                MlAgentsCandidateAction c = candidates.AvailableCandidates[i];
                if (i > 0) sb.Append(", ");
                sb.Append("{idx=").Append(c.CandidateIndex)
                  .Append(",pos=").Append(c.Action.ActorPosition)
                  .Append(",type=").Append(c.Action.ActionType)
                  .Append("}");
            }

            if (candidates.AvailableCandidates.Count > limit)
            {
                sb.Append(", ...(").Append(candidates.AvailableCandidates.Count - limit).Append(" more)");
            }

            sb.Append("]");
            return sb.ToString();
        }

        private static string BuildActionSummary(AgentAction action)
        {
            return "actor=" + action.ActorPosition + ",type=" + action.ActionType
                   + ",dir=" + action.Direction + ",produce=" + action.ProduceUnitType
                   + ",target=" + action.AttackTargetPosition;
        }

        private static string ActionTypeToString(int actionType)
        {
            switch (actionType)
            {
                case 0: return "noop";
                case 1: return "move";
                case 2: return "harvest";
                case 3: return "return";
                case 4: return "produce";
                case 5: return "attack";
                default: return "unknown_" + actionType;
            }
        }

        private static string BuildMarkdown6I(Stage7BTeacherReplayReport report, List<Stage7BCandidateMismatchDiagnosisEntry> mismatchEntries)
        {
            var sb = new StringBuilder(4096);
            sb.AppendLine("# Stage7B-6I Runtime Apply Validation Report");
            sb.AppendLine();
            sb.AppendLine("- status: " + report.status);
            sb.AppendLine("- generated_at_utc: " + report.generatedAtUtc);
            sb.AppendLine("- source: " + report.selectedSourcePath);
            sb.AppendLine("- post_state_comparison_mode: " + report.postStateComparisonMode);
            sb.AppendLine();
            sb.AppendLine("## Metrics");
            sb.AppendLine();
            sb.AppendLine("- episodes_scanned: " + report.episodesScanned);
            sb.AppendLine("- episodes_replay_attempted: " + report.episodesReplayAttempted);
            sb.AppendLine("- steps_total: " + report.stepsTotal);
            sb.AppendLine("- steps_replay_attempted: " + report.stepsReplayAttempted);
            sb.AppendLine("- teacher_commands_total: " + report.teacherCommandsTotal);
            sb.AppendLine("- teacher_nonnoop_commands_total: " + report.teacherNonNoOpCommandsTotal);
            sb.AppendLine("- no_teacher_command_steps: " + report.noTeacherCommandSteps);
            sb.AppendLine("- state_sync_success_count: " + report.stateSyncSuccessCount);
            sb.AppendLine("- state_sync_failed_count: " + report.stateSyncFailedCount);
            sb.AppendLine("- candidate_count_min: " + ValueOrNull(report.candidateCountMin));
            sb.AppendLine("- candidate_count_mean: " + ValueOrNull(report.candidateCountMean));
            sb.AppendLine("- candidate_count_max: " + ValueOrNull(report.candidateCountMax));
            sb.AppendLine("- candidate_match_count: " + report.candidateMatchCount);
            sb.AppendLine("- candidate_drop_count: " + report.candidateDropCount);
            sb.AppendLine("- candidate_match_rate: " + ValueOrNull(report.candidateMatchRate));
            sb.AppendLine("- nonnoop_candidate_match_rate: " + ValueOrNull(report.nonNoOpCandidateMatchRate));
            sb.AppendLine("- runtime_apply_attempted_count: " + report.runtimeApplyAttemptedCount);
            sb.AppendLine("- runtime_apply_accepted_count: " + report.runtimeApplyAcceptedCount);
            sb.AppendLine("- runtime_apply_rejected_count: " + report.runtimeApplyRejectedCount);
            sb.AppendLine("- runtime_apply_accept_rate: " + ValueOrNull(report.runtimeApplyAcceptRate));
            sb.AppendLine("- first_runtime_reject_step: " + (report.firstRuntimeRejectStep < 0 ? "none" : report.firstRuntimeRejectStep.ToString()));
            sb.AppendLine("- first_runtime_reject_action_summary: " + (report.firstRuntimeRejectActionSummary ?? "none"));
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

            sb.AppendLine();
            sb.AppendLine("## Runtime Reject Reason Histogram");
            sb.AppendLine();
            if (report.runtimeRejectReasonHistogram.Count == 0)
            {
                sb.AppendLine("- (none)");
            }
            else
            {
                for (int i = 0; i < report.runtimeRejectReasonHistogram.Count; i++)
                {
                    Stage7BTeacherReplayMetricEntry row = report.runtimeRejectReasonHistogram[i];
                    sb.AppendLine("- " + row.key + ": " + row.value);
                }
            }

            sb.AppendLine();
            sb.AppendLine("## Rejected Action Type Histogram");
            sb.AppendLine();
            if (report.rejectedActionTypeHistogram.Count == 0)
            {
                sb.AppendLine("- (none)");
            }
            else
            {
                for (int i = 0; i < report.rejectedActionTypeHistogram.Count; i++)
                {
                    Stage7BTeacherReplayMetricEntry row = report.rejectedActionTypeHistogram[i];
                    sb.AppendLine("- " + row.key + ": " + row.value);
                }
            }

            sb.AppendLine();
            sb.AppendLine("## Candidate Mismatch Diagnoses");
            sb.AppendLine();
            if (mismatchEntries == null || mismatchEntries.Count == 0)
            {
                sb.AppendLine("- (none)");
            }
            else
            {
                for (int i = 0; i < mismatchEntries.Count; i++)
                {
                    Stage7BCandidateMismatchDiagnosisEntry d = mismatchEntries[i];
                    sb.AppendLine("### Mismatch " + (i + 1) + ": episode=" + d.episode_id + " step=" + d.step_id);
                    sb.AppendLine("- actor_flat: " + d.actor_flat);
                    sb.AppendLine("- actor_x: " + d.actor_x + ", actor_y: " + d.actor_y);
                    sb.AppendLine("- action_type: " + d.action_type + " (" + d.action_type_name + ")");
                    sb.AppendLine("- drop_reason: " + d.drop_reason);
                    sb.AppendLine("- nearest_candidate_reason: " + d.nearest_candidate_reason);
                    sb.AppendLine("- candidate_count_at_step: " + d.candidate_count);
                    sb.AppendLine("- candidate_list_summary: " + d.candidate_list_summary);
                    sb.AppendLine();
                }
            }

            sb.AppendLine("## Notes");
            sb.AppendLine();
            for (int i = 0; i < report.notes.Count; i++)
            {
                sb.AppendLine("- " + report.notes[i]);
            }

            return sb.ToString();
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
            sb.AppendLine("- post_state_comparison_mode: " + report.postStateComparisonMode);
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
        [Serializable]
        private sealed class Stage7BRuntimeApplyTraceEntry
        {
            public int episode_id;
            public int step_id;
            public int command_index;
            public int actor_flat;
            public int actor_x;
            public int actor_y;
            public int action_type;
            public bool runtime_apply_attempted;
            public bool runtime_apply_accepted;
            public string reject_reason;
            public string action_summary;
        }

        [Serializable]
        private sealed class Stage7BRuntimeApplyPostStateTraceEntry
        {
            public int episode_id;
            public int step_id;
            public bool post_state_matched;
            public bool terminal_matched;
            public string comparison_mode;
            public string diagnostics;
        }

        [Serializable]
        private sealed class Stage7BCandidateMismatchDiagnosisEntry
        {
            public int episode_id;
            public int step_id;
            public int command_index;
            public int actor_flat;
            public int actor_x;
            public int actor_y;
            public int action_type;
            public string action_type_name;
            public int move_dir;
            public int produce_dir;
            public int produce_unit_type;
            public int target_x;
            public int target_y;
            public string drop_reason;
            public string nearest_candidate_reason;
            public int candidate_count;
            public string candidate_list_summary;
        }

        [Serializable]
        private sealed class Stage7BCandidateMismatchDiagnosisReport
        {
            public string generated_at_utc;
            public int total_mismatches;
            public Stage7BCandidateMismatchDiagnosisEntry[] mismatches;
        }

        [Serializable]
        private sealed class Stage7B6JReturnMismatchEntry
        {
            public int episode_id;
            public int step_id;
            public int command_index;
            public int actor_flat;
            public int actor_x;
            public int actor_y;
            public string teacher_dir;
            public string candidate_dir;
            public int teacher_target_x;
            public int teacher_target_y;
            public int unity_target_x;
            public int unity_target_y;
            public bool teacher_target_inside_map;
            public bool unity_target_inside_map;
            public bool teacher_target_has_friendly_base;
            public bool unity_target_has_friendly_base;
            public bool is_opposite;
            public bool is_y_axis_flip;
            public bool is_x_axis_flip;
            public bool y_axis_inversion_suggested;
            public bool x_axis_inversion_suggested;
            public string nearest_candidate_reason;
            public string teacher_command_json;
            public string base_resource_nearby_summary;
            public int candidate_count;
            public string candidate_list_summary;
        }

        [Serializable]
        private sealed class Stage7B6JReturnDirectionAuditReport
        {
            public string generated_at_utc;
            public int total_return_mismatches;
            public int opposite_direction_count;
            public int y_axis_flip_suspected_count;
            public int x_axis_flip_suspected_count;
            public string pattern_hypothesis;
            public Stage7B6JReturnMismatchEntry[] mismatches;
        }
    }
}
