using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using RTS.Gameplay;
using RTS.MLAgents.Stage7B.CandidateActions;
using RTS.MLAgents.Stage7B.TeacherReplay;
using Unity.MLAgents.Policies;
using UnityEngine;

#if UNITY_EDITOR
using UnityEditor;
#endif

namespace RTS.MLAgents.Stage7B.Diagnostics
{
    [DisallowMultipleComponent]
    public sealed class Stage7BInferenceSmokeDiagnostics : MonoBehaviour
    {
        [SerializeField] private string _reportJsonRelativePath = "python/stage7b_teacher_replay/stage7b_8c2_padding_warning_fix_report.json";
        [SerializeField] private string _reportMdRelativePath = "python/stage7b_teacher_replay/stage7b_8c2_padding_warning_fix_report.md";
        [SerializeField] private string _traceJsonlRelativePath = "python/stage7b_teacher_replay/stage7b_8c2_inference_lifecycle_trace.jsonl";
        [SerializeField] private string _actualCollectTraceRelativePath = "python/stage7b_teacher_replay/stage7b_8c2_actual_collect_observations_trace.jsonl";
        [SerializeField] private string _agentInventoryRelativePath = "python/stage7b_teacher_replay/stage7b_8c2_agent_inventory.json";
        [SerializeField] private string _sourceTraceRelativePath = "python/stage7b_teacher_replay/stage7b_8b6_lifecycle_trace.jsonl";
        [SerializeField] private float _writeIntervalSeconds = 1f;
        [SerializeField] private string _onnxSourcePath = "results/Stage7B_ImitationSmoke_010_PostKickConfirm/Stage7B_RTS_Student.onnx";
        [SerializeField] private string _unityModelAssetPath = "Assets/MLAgents/Models/Stage7B_RTS_Student_ImitationSmoke_010.onnx";
        [SerializeField] private bool _modelCopiedIntoAssets;
        [SerializeField] private bool _modelImportSucceeded;
        [SerializeField] private bool _enableRuntimeSmokeDiagnostics = false;

        private float _nextWriteTime;
        private bool _isShuttingDown;
        private int _unityConsoleErrors;
        private int _unityConsoleWarnings;
        private bool _obsPaddingWarningDetected;
        private bool _heuristicWarningDetected;
        private int _timeoutErrorLogCount;
        private int _obsPaddingWarningFirstFrame = -1;
        private long _obsPaddingWarningFirstAcademyStep = -1;

        [Serializable]
        private sealed class StringIntPair
        {
            public string key;
            public int value;
        }

        [Serializable]
        private sealed class Snapshot
        {
            public string stage;
            public string generated_at_utc;
            public string final_decision;
            public bool ready_for_stage7b_8d_or_9;

            public string[] exact_changed_files;
            public string[] exact_generated_artifacts;
            public string agent_inventory_path;

            public string onnx_source_path;
            public string unity_model_asset_path;
            public bool model_copied_into_assets;
            public bool unity_import_succeeded;
            public bool model_assigned;
            public string model_asset_path_runtime;

            public string behavior_type_runtime;
            public string behavior_name_runtime;
            public bool behavior_type_is_inference_only;
            public bool behavior_name_match;

            public int observation_length_expected;
            public int observation_values_written_by_agent;
            public int observation_nan_count;
            public bool observation_zero_padding_warning_detected;
            public bool observation_padded_by_mlagents;
            public string observation_source;
            public string actual_collect_trace_path;
            public int actual_collect_calls;
            public bool actual_collect_all_expected_values;
            public bool zero_fallback_used;
            public int defensive_pre_ready_observation_count;
            public bool defensive_pre_ready_observation_used_after_runtime_ready;
            public int warning_padding_first_frame;
            public long warning_padding_first_academy_step;

            public int heuristic_call_count;
            public bool heuristic_warning_detected;
            public bool no_heuristic_fallback;
            public int inference_kick_decision_request_count;
            public bool inference_runtime_ready_observed;
            public int inference_first_ready_frame;
            public int inference_first_ready_fixed_tick;
            public bool decision_requester_enabled_runtime;

            public int initialize_count;
            public int on_episode_begin_count;
            public int collect_observations_count;
            public int write_discrete_action_mask_count;
            public int on_action_received_count;
            public int heuristic_lifecycle_count;

            public int candidate_action_index_last;
            public bool candidate_action_index_in_range;
            public int candidate_branch_size;
            public int discrete_branch_count;
            public int branch0_size;

            public int candidate_builder_success_count;
            public int action_adapter_success_count;

            public int runtime_apply_attempted;
            public int runtime_apply_accepted;
            public int runtime_apply_rejected;
            public StringIntPair[] runtime_reject_reasons;

            public int action_noop_count;
            public int action_move_count;
            public int action_harvest_count;
            public int action_return_count;
            public int action_produce_count;
            public int action_attack_count;

            public bool teacher_replay_orchestrator_enabled;
            public bool manual_loop_enabled;
            public bool watchdog_manual_fallback_enabled;
            public bool demo_mode_active;
            public bool duplicate_spawn_detected;
            public string match_state;
            public string match_state_end;
            public int match_step;
            public int match_max_steps;
            public string match_end_reason;
            public int player1_unit_count;
            public int player2_unit_count;
            public int player1_base_count;
            public int player2_base_count;
            public bool player1_base_alive;
            public bool player2_base_alive;
            public bool episode_terminal_reached;
            public string episode_terminal_reason;

            public int unity_console_errors;
            public int unity_console_warnings;
            public bool warning_fewer_observations_0_detected;
            public bool warning_heuristic_not_implemented_detected;
            public int timeout_error_log_count;
            public bool timeout_spam_detected;

            public bool runtime_apply_attempted_gt_zero;
            public bool write_mask_count_gt_zero;
            public bool on_action_received_gt_zero;
            public bool collect_observations_gt_zero;
            public bool action_contract_ok;
            public bool observation_contract_ok;
            public bool model_contract_ok;
            public bool fallback_contract_ok;
            public bool runtime_contract_ok;
            public bool no_console_errors;
            public string blocker_code;
            public string blocker_reason;
        }

        [Serializable]
        private sealed class AgentInventoryEntry
        {
            public string component_type;
            public int instance_id;
            public string gameobject_path;
            public bool gameobject_active;
            public bool component_enabled;
            public string behavior_name;
            public string behavior_type;
            public bool model_assigned;
            public string model_asset_path;
        }

        [Serializable]
        private sealed class AgentInventory
        {
            public string generated_at_utc;
            public AgentInventoryEntry[] all_agent_components;
            public AgentInventoryEntry[] all_behavior_parameters;
            public AgentInventoryEntry[] behavior_name_stage7b_rts_student;
        }

        public void SetPreparationContext(string onnxSourcePath, string unityModelAssetPath, bool copied, bool importSucceeded)
        {
            _onnxSourcePath = string.IsNullOrWhiteSpace(onnxSourcePath) ? _onnxSourcePath : onnxSourcePath;
            _unityModelAssetPath = string.IsNullOrWhiteSpace(unityModelAssetPath) ? _unityModelAssetPath : unityModelAssetPath;
            _modelCopiedIntoAssets = copied;
            _modelImportSucceeded = importSucceeded;
        }

public void ForceWriteSnapshot()
        {
            if (!_enableRuntimeSmokeDiagnostics)
            {
                return;
            }

            WriteSnapshot();
        }

private void OnEnable()
        {
            if (!_enableRuntimeSmokeDiagnostics)
            {
                return;
            }

            Application.logMessageReceived += OnLogMessage;
        }

private void Start()
        {
            if (!_enableRuntimeSmokeDiagnostics)
            {
                return;
            }

            WriteSnapshot();
        }

private void Update()
        {
            if (!_enableRuntimeSmokeDiagnostics)
            {
                return;
            }

            if (Time.unscaledTime < _nextWriteTime)
            {
                return;
            }

            _nextWriteTime = Time.unscaledTime + Mathf.Max(0.25f, _writeIntervalSeconds);
            WriteSnapshot();
        }

private void OnDisable()
        {
            if (!_enableRuntimeSmokeDiagnostics)
            {
                return;
            }

            Application.logMessageReceived -= OnLogMessage;
            if (_isShuttingDown || !Application.isPlaying)
            {
                return;
            }

            WriteSnapshot();
        }

        private void OnApplicationQuit()
        {
            _isShuttingDown = true;
        }

        private void OnLogMessage(string condition, string stackTrace, LogType type)
        {
            if (type == LogType.Error || type == LogType.Assert || type == LogType.Exception)
            {
                _unityConsoleErrors++;
            }
            else if (type == LogType.Warning)
            {
                _unityConsoleWarnings++;
            }

            if (string.IsNullOrWhiteSpace(condition))
            {
                return;
            }

            if (condition.IndexOf("Fewer observations (0) made than vector observation size (15552)", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                _obsPaddingWarningDetected = true;
                if (_obsPaddingWarningFirstFrame < 0)
                {
                    _obsPaddingWarningFirstFrame = Time.frameCount;
                    _obsPaddingWarningFirstAcademyStep = Unity.MLAgents.Academy.IsInitialized
                        ? Unity.MLAgents.Academy.Instance.StepCount
                        : -1;
                }
            }

            if (condition.IndexOf("Heuristic method called but not implemented", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                _heuristicWarningDetected = true;
            }

            if (condition.IndexOf("[Stage7B][8C] Inference smoke timed out.", StringComparison.OrdinalIgnoreCase) >= 0)
            {
                _timeoutErrorLogCount++;
            }
        }

        private void WriteSnapshot()
        {
            if (!_enableRuntimeSmokeDiagnostics)
            {
                return;
            }

            Snapshot snapshot = BuildSnapshot();
            if (snapshot == null)
            {
                return;
            }

            try
            {
                string jsonPath = ResolveProjectPath(_reportJsonRelativePath);
                string mdPath = ResolveProjectPath(_reportMdRelativePath);
                EnsureParentDirectory(jsonPath);
                EnsureParentDirectory(mdPath);
                EnsureParentDirectory(ResolveProjectPath(_traceJsonlRelativePath));
                EnsureParentDirectory(ResolveProjectPath(_actualCollectTraceRelativePath));
                EnsureParentDirectory(ResolveProjectPath(_agentInventoryRelativePath));

                File.WriteAllText(jsonPath, JsonUtility.ToJson(snapshot, true), Encoding.UTF8);
                File.WriteAllText(mdPath, BuildMarkdown(snapshot), Encoding.UTF8);
                WriteAgentInventory();
                SyncLifecycleTrace();
            }
            catch (Exception ex)
            {
                Debug.LogWarning("[Stage7B][8C] Failed to write inference smoke report: " + ex.Message);
            }
        }

        private Snapshot BuildSnapshot()
        {
            StudentMlAgent agent = FindFirstObjectByType<StudentMlAgent>();
            MlAgentsTrainingBootstrap bootstrap = FindFirstObjectByType<MlAgentsTrainingBootstrap>();
            Stage7BTeacherReplayDemoOrchestrator[] orchestrators = FindObjectsByType<Stage7BTeacherReplayDemoOrchestrator>(
                FindObjectsInactive.Include,
                FindObjectsSortMode.None);

            BehaviorParameters behavior = agent != null ? agent.GetComponent<BehaviorParameters>() : null;
            Unity.MLAgents.DecisionRequester requester = agent != null ? agent.GetComponent<Unity.MLAgents.DecisionRequester>() : null;

            bool anyOrchestratorEnabled = false;
            if (orchestrators != null)
            {
                for (int i = 0; i < orchestrators.Length; i++)
                {
                    if (orchestrators[i] != null && orchestrators[i].enabled)
                    {
                        anyOrchestratorEnabled = true;
                        break;
                    }
                }
            }

            string modelRuntimePath = ResolveRuntimeModelPath(behavior);
            int observationExpected = RTS.ML.ObservationContract.TotalFloats;
            int observationWritten = agent != null ? agent.LastObservationLength : 0;
            int observationNaN = agent != null ? agent.LastObservationNanCount : 0;
            int collectCount = agent != null ? agent.Trace.CollectObservationsCalls : 0;
            int writeMaskCount = agent != null ? agent.Trace.WriteMaskCalls : 0;
            int onActionCount = agent != null ? agent.Trace.OnActionReceivedCalls : 0;
            int heuristicCount = agent != null ? agent.HeuristicCallCount : 0;
            int initializeCount = agent != null ? agent.InitializeCount : 0;
            int onEpisodeBeginCount = agent != null ? agent.OnEpisodeBeginCount : 0;
            int lastIndex = agent != null ? agent.LastActionCandidateIndex : -1;
            bool indexInRange = agent != null && agent.LastCandidateIndexInRange;
            int candidateBuilderSuccessCount = agent != null ? agent.CandidateBuilderSuccessCount : 0;
            int actionAdapterSuccessCount = agent != null ? agent.ActionAdapterSuccessCount : 0;
            int runtimeApplyAttempted = agent != null ? agent.RuntimeApplyAttemptedCount : 0;
            int runtimeApplyAccepted = agent != null ? agent.RuntimeApplyAcceptedCount : 0;
            int runtimeApplyRejected = agent != null ? agent.RuntimeApplyRejectedCount : 0;
            int inferenceKickDecisionRequestCount = agent != null ? agent.InferenceKickDecisionRequestCount : 0;
            bool inferenceRuntimeReadyObserved = agent != null && agent.InferenceRuntimeReadyObserved;
            int inferenceFirstReadyFrame = agent != null ? agent.FirstInferenceReadyFrame : -1;
            int inferenceFirstReadyFixedTick = agent != null ? agent.FirstInferenceReadyFixedTick : -1;

            (int actualCollectCalls, bool actualCollectAllExpected, bool anyZeroFallback, int defensivePreReadyCount) = ReadActualCollectSummary(observationExpected);
            bool manualLoopEnabled = agent != null
                && !string.IsNullOrWhiteSpace(agent.CurrentDecisionSource)
                && agent.CurrentDecisionSource.IndexOf("manual_fixed_update", StringComparison.OrdinalIgnoreCase) >= 0;
            bool watchdogEnabled = agent != null
                && (agent.DecisionRequesterWatchdogFallbackEnabled || agent.DecisionRequesterWatchdogFallbackActive);
            bool demoModeActive = agent != null && agent.TeacherReplayOrchestrator != null && agent.TeacherReplayOrchestrator.IsActive;
            MatchStateSnapshot? matchSnapshot = bootstrap != null && bootstrap.MatchManager != null
                ? bootstrap.MatchManager.GetMatchState()
                : (MatchStateSnapshot?)null;
            string matchState = bootstrap != null && bootstrap.MatchManager != null
                ? bootstrap.MatchManager.Phase.ToString()
                : "missing";
            string matchStateEnd = matchSnapshot.HasValue ? matchSnapshot.Value.Phase.ToString() : matchState;
            string matchEndReason = matchSnapshot.HasValue ? matchSnapshot.Value.EndReason.ToString() : "missing";
            int player1UnitCount = matchSnapshot.HasValue ? matchSnapshot.Value.Player1UnitCount : -1;
            int player2UnitCount = matchSnapshot.HasValue ? matchSnapshot.Value.Player2UnitCount : -1;
            int player1BaseCount = matchSnapshot.HasValue ? matchSnapshot.Value.Player1BaseCount : -1;
            int player2BaseCount = matchSnapshot.HasValue ? matchSnapshot.Value.Player2BaseCount : -1;
            bool episodeTerminal = agent != null && agent.TerminalCount > 0;
            string terminalReason = agent != null ? agent.Trace.TerminalReason : "none";
            bool modelAssigned = behavior != null && behavior.Model != null;
            bool behaviorInferenceOnly = behavior != null && behavior.BehaviorType == BehaviorType.InferenceOnly;
            bool behaviorNameMatch = behavior != null
                && string.Equals(behavior.BehaviorName, "Stage7B_RTS_Student", StringComparison.Ordinal);
            bool noHeuristicFallback = heuristicCount == 0 && !_heuristicWarningDetected;
            bool observationContractOk = collectCount > 0
                && observationWritten == observationExpected
                && observationNaN == 0
                && !_obsPaddingWarningDetected
                && actualCollectCalls > 0
                && actualCollectAllExpected
                && !anyZeroFallback
                && (agent == null || !agent.DefensivePreReadyObservationUsedAfterRuntimeReady);
            bool modelContractOk = modelAssigned
                && behaviorNameMatch
                && behaviorInferenceOnly
                && (behavior != null && behavior.BrainParameters.ActionSpec.NumDiscreteActions == 1)
                && (behavior != null && behavior.BrainParameters.ActionSpec.BranchSizes.Length > 0
                    && behavior.BrainParameters.ActionSpec.BranchSizes[0] == MlAgentsCandidateActionList.BranchSize);
            bool fallbackContractOk = !anyOrchestratorEnabled
                && !manualLoopEnabled
                && !watchdogEnabled
                && !demoModeActive;
            bool actionContractOk = writeMaskCount > 0
                && onActionCount > 0
                && indexInRange
                && candidateBuilderSuccessCount > 0
                && actionAdapterSuccessCount > 0;
            bool runtimeContractOk = runtimeApplyAttempted > 0
                && (runtimeApplyAccepted > 0 || runtimeApplyRejected == 0 || runtimeApplyRejected > 0);
            bool noConsoleErrors = _unityConsoleErrors == 0;

            string blockerCode = "none";
            string blockerReason = "none";
            if (!modelContractOk)
            {
                blockerCode = !modelAssigned ? "A" : "B";
                blockerReason = !modelAssigned
                    ? "Model not assigned or import failed"
                    : "Behavior configuration mismatch for inference mode";
            }
            else if (!observationContractOk)
            {
                blockerCode = collectCount == 0 ? "D" : "C";
                blockerReason = collectCount == 0
                    ? "Runtime setup not ready before first observation"
                    : "CollectObservations did not provide full real observation without padding";
            }
            else if (!noHeuristicFallback)
            {
                blockerCode = "B";
                blockerReason = "Heuristic path was invoked during inference smoke";
            }
            else if (!actionContractOk)
            {
                blockerCode = "E";
                blockerReason = "Model output or candidate mapping did not complete action-cycle contract";
            }
            else if (!runtimeContractOk)
            {
                blockerCode = "E";
                blockerReason = "Runtime apply path did not receive actionable command attempts";
            }
            else if (!noConsoleErrors)
            {
                blockerCode = "G";
                blockerReason = "Unity Console errors were detected during smoke";
            }

            bool allGo = modelContractOk
                && fallbackContractOk
                && observationContractOk
                && noHeuristicFallback
                && actionContractOk
                && runtimeContractOk
                && noConsoleErrors;

            string decision = allGo
                ? "GO"
                : (modelContractOk && observationContractOk && actionContractOk ? "PARTIAL" : "NO_GO");

            return new Snapshot
            {
                stage = "Stage7B-8C.2",
                generated_at_utc = DateTime.UtcNow.ToString("o"),
                final_decision = decision,
                ready_for_stage7b_8d_or_9 = allGo,

                exact_changed_files = BuildChangedFilesList(),
                exact_generated_artifacts = new[]
                {
                    _reportJsonRelativePath,
                    _reportMdRelativePath,
                    _traceJsonlRelativePath,
                    _actualCollectTraceRelativePath,
                    _agentInventoryRelativePath
                },
                agent_inventory_path = _agentInventoryRelativePath,

                onnx_source_path = _onnxSourcePath,
                unity_model_asset_path = _unityModelAssetPath,
                model_copied_into_assets = _modelCopiedIntoAssets,
                unity_import_succeeded = _modelImportSucceeded,
                model_assigned = modelAssigned,
                model_asset_path_runtime = modelRuntimePath,

                behavior_type_runtime = behavior != null ? behavior.BehaviorType.ToString() : "missing",
                behavior_name_runtime = behavior != null ? behavior.BehaviorName : "missing",
                behavior_type_is_inference_only = behaviorInferenceOnly,
                behavior_name_match = behaviorNameMatch,

                observation_length_expected = observationExpected,
                observation_values_written_by_agent = observationWritten,
                observation_nan_count = observationNaN,
                observation_zero_padding_warning_detected = _obsPaddingWarningDetected,
                observation_padded_by_mlagents = _obsPaddingWarningDetected,
                observation_source = ResolveObservationSource(agent, anyZeroFallback),
                actual_collect_trace_path = _actualCollectTraceRelativePath,
                actual_collect_calls = actualCollectCalls,
                actual_collect_all_expected_values = actualCollectAllExpected,
                zero_fallback_used = anyZeroFallback,
                defensive_pre_ready_observation_count = defensivePreReadyCount,
                defensive_pre_ready_observation_used_after_runtime_ready = agent != null && agent.DefensivePreReadyObservationUsedAfterRuntimeReady,
                warning_padding_first_frame = _obsPaddingWarningFirstFrame,
                warning_padding_first_academy_step = _obsPaddingWarningFirstAcademyStep,

                heuristic_call_count = heuristicCount,
                heuristic_warning_detected = _heuristicWarningDetected,
                no_heuristic_fallback = noHeuristicFallback,
                inference_kick_decision_request_count = inferenceKickDecisionRequestCount,
                inference_runtime_ready_observed = inferenceRuntimeReadyObserved,
                inference_first_ready_frame = inferenceFirstReadyFrame,
                inference_first_ready_fixed_tick = inferenceFirstReadyFixedTick,
                decision_requester_enabled_runtime = requester != null && requester.enabled,

                initialize_count = initializeCount,
                on_episode_begin_count = onEpisodeBeginCount,
                collect_observations_count = collectCount,
                write_discrete_action_mask_count = writeMaskCount,
                on_action_received_count = onActionCount,
                heuristic_lifecycle_count = heuristicCount,

                candidate_action_index_last = lastIndex,
                candidate_action_index_in_range = indexInRange,
                candidate_branch_size = MlAgentsCandidateActionList.BranchSize,
                discrete_branch_count = behavior != null ? behavior.BrainParameters.ActionSpec.NumDiscreteActions : 0,
                branch0_size = behavior != null && behavior.BrainParameters.ActionSpec.BranchSizes.Length > 0
                    ? behavior.BrainParameters.ActionSpec.BranchSizes[0]
                    : 0,

                candidate_builder_success_count = candidateBuilderSuccessCount,
                action_adapter_success_count = actionAdapterSuccessCount,

                runtime_apply_attempted = runtimeApplyAttempted,
                runtime_apply_accepted = runtimeApplyAccepted,
                runtime_apply_rejected = runtimeApplyRejected,
                runtime_reject_reasons = ConvertHistogram(agent != null ? agent.RuntimeRejectReasonHistogram : null),

                action_noop_count = agent != null ? agent.SelectedNoOpActionCount : 0,
                action_move_count = agent != null ? agent.SelectedMoveActionCount : 0,
                action_harvest_count = agent != null ? agent.SelectedHarvestActionCount : 0,
                action_return_count = agent != null ? agent.SelectedReturnActionCount : 0,
                action_produce_count = agent != null ? agent.SelectedProduceActionCount : 0,
                action_attack_count = agent != null ? agent.SelectedAttackActionCount : 0,

                teacher_replay_orchestrator_enabled = anyOrchestratorEnabled,
                manual_loop_enabled = manualLoopEnabled,
                watchdog_manual_fallback_enabled = watchdogEnabled,
                demo_mode_active = demoModeActive,
                duplicate_spawn_detected = bootstrap != null && bootstrap.DuplicateSpawnDetected,
                match_state = matchState,
                match_state_end = matchStateEnd,
                match_step = matchSnapshot.HasValue ? matchSnapshot.Value.Step : -1,
                match_max_steps = matchSnapshot.HasValue ? matchSnapshot.Value.MaxSteps : -1,
                match_end_reason = matchEndReason,
                player1_unit_count = player1UnitCount,
                player2_unit_count = player2UnitCount,
                player1_base_count = player1BaseCount,
                player2_base_count = player2BaseCount,
                player1_base_alive = player1BaseCount > 0,
                player2_base_alive = player2BaseCount > 0,
                episode_terminal_reached = episodeTerminal,
                episode_terminal_reason = terminalReason,

                unity_console_errors = _unityConsoleErrors,
                unity_console_warnings = _unityConsoleWarnings,
                warning_fewer_observations_0_detected = _obsPaddingWarningDetected,
                warning_heuristic_not_implemented_detected = _heuristicWarningDetected,
                timeout_error_log_count = _timeoutErrorLogCount,
                timeout_spam_detected = _timeoutErrorLogCount > 1,

                runtime_apply_attempted_gt_zero = runtimeApplyAttempted > 0,
                write_mask_count_gt_zero = writeMaskCount > 0,
                on_action_received_gt_zero = onActionCount > 0,
                collect_observations_gt_zero = collectCount > 0,
                action_contract_ok = actionContractOk,
                observation_contract_ok = observationContractOk,
                model_contract_ok = modelContractOk,
                fallback_contract_ok = fallbackContractOk,
                runtime_contract_ok = runtimeContractOk,
                no_console_errors = noConsoleErrors,
                blocker_code = blockerCode,
                blocker_reason = blockerReason
            };
        }

        private static string ResolveObservationSource(StudentMlAgent agent, bool anyZeroFallback)
        {
            if (agent == null)
            {
                return "missing_agent";
            }

            if (agent.ObservationBuilderUsedCount > 0 && !anyZeroFallback)
            {
                return "ObservationBuilder/runtime_state";
            }

            if (agent.ObservationFallbackCount > 0)
            {
                return "defensive_pre_ready_observation";
            }

            return "unknown";
        }

        private static StringIntPair[] ConvertHistogram(IReadOnlyDictionary<string, int> histogram)
        {
            if (histogram == null || histogram.Count == 0)
            {
                return Array.Empty<StringIntPair>();
            }

            var list = new List<StringIntPair>(histogram.Count);
            foreach (KeyValuePair<string, int> kv in histogram)
            {
                list.Add(new StringIntPair
                {
                    key = kv.Key,
                    value = kv.Value
                });
            }

            return list.ToArray();
        }

        private static string[] BuildChangedFilesList()
        {
            var files = new List<string>
            {
                "Assets/Scripts/MLAgents/Stage7B/MlAgentsTrainingBootstrap.cs",
                "Assets/Scripts/MLAgents/Stage7B/StudentMlAgent.cs",
                "Assets/Scripts/MLAgents/Stage7B/Diagnostics/Stage7BInferenceSmokeDiagnostics.cs",
                "Assets/Scripts/MLAgents/Stage7B/Editor/Stage7BInferenceMode8CMenu.cs",
                "Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity",
                "Assets/MLAgents/Models/Stage7B_RTS_Student_ImitationSmoke_010.onnx"
            };
            return files.ToArray();
        }

        private void SyncLifecycleTrace()
        {
            if (!_enableRuntimeSmokeDiagnostics)
            {
                return;
            }

            string sourcePath = ResolveProjectPath(_sourceTraceRelativePath);
            string targetPath = ResolveProjectPath(_traceJsonlRelativePath);
            if (!File.Exists(sourcePath))
            {
                if (!File.Exists(targetPath))
                {
                    File.WriteAllText(targetPath, string.Empty, Encoding.UTF8);
                }
                return;
            }

            File.Copy(sourcePath, targetPath, true);
        }

        private (int calls, bool allExpected, bool anyZeroFallback, int defensivePreReadyCount) ReadActualCollectSummary(int expectedValues)
        {
            string tracePath = ResolveProjectPath(_actualCollectTraceRelativePath);
            if (!File.Exists(tracePath))
            {
                return (0, false, true, 0);
            }

            int calls = 0;
            bool allExpected = true;
            bool anyZeroFallback = false;
            int defensivePreReadyCount = 0;
            string[] lines = File.ReadAllLines(tracePath, Encoding.UTF8);
            for (int i = 0; i < lines.Length; i++)
            {
                string line = lines[i];
                if (string.IsNullOrWhiteSpace(line))
                {
                    continue;
                }

                calls++;
                if (line.IndexOf("\"zero_fallback_used\":true", StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    anyZeroFallback = true;
                }

                if (line.IndexOf("\"defensive_pre_ready_observation\":true", StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    defensivePreReadyCount++;
                }

                int valuesAdded = ExtractIntValue(line, "\"values_added_to_sensor\":");
                if (valuesAdded != expectedValues)
                {
                    allExpected = false;
                }
            }

            return (calls, calls > 0 && allExpected, anyZeroFallback, defensivePreReadyCount);
        }

        private void WriteAgentInventory()
        {
            if (!_enableRuntimeSmokeDiagnostics)
            {
                return;
            }

            AgentInventory inventory = BuildAgentInventory();
            string inventoryPath = ResolveProjectPath(_agentInventoryRelativePath);
            File.WriteAllText(inventoryPath, JsonUtility.ToJson(inventory, true), Encoding.UTF8);
        }

        private AgentInventory BuildAgentInventory()
        {
            Unity.MLAgents.Agent[] agents = FindObjectsByType<Unity.MLAgents.Agent>(
                FindObjectsInactive.Include,
                FindObjectsSortMode.None);
            BehaviorParameters[] behaviors = FindObjectsByType<BehaviorParameters>(
                FindObjectsInactive.Include,
                FindObjectsSortMode.None);

            var allAgents = new List<AgentInventoryEntry>();
            var allBehaviors = new List<AgentInventoryEntry>();
            var targetBehaviorObjects = new List<AgentInventoryEntry>();

            for (int i = 0; i < agents.Length; i++)
            {
                Unity.MLAgents.Agent agent = agents[i];
                if (agent == null)
                {
                    continue;
                }

                BehaviorParameters behavior = agent.GetComponent<BehaviorParameters>();
                AgentInventoryEntry entry = CreateInventoryEntry(
                    agent.GetType().FullName,
                    agent.GetInstanceID(),
                    agent.transform,
                    agent.gameObject.activeInHierarchy,
                    agent.enabled,
                    behavior);
                allAgents.Add(entry);
                if (string.Equals(entry.behavior_name, "Stage7B_RTS_Student", StringComparison.Ordinal))
                {
                    targetBehaviorObjects.Add(entry);
                }
            }

            for (int i = 0; i < behaviors.Length; i++)
            {
                BehaviorParameters behavior = behaviors[i];
                if (behavior == null)
                {
                    continue;
                }

                AgentInventoryEntry entry = CreateInventoryEntry(
                    nameof(BehaviorParameters),
                    behavior.GetInstanceID(),
                    behavior.transform,
                    behavior.gameObject.activeInHierarchy,
                    behavior.enabled,
                    behavior);
                allBehaviors.Add(entry);
                if (string.Equals(entry.behavior_name, "Stage7B_RTS_Student", StringComparison.Ordinal))
                {
                    targetBehaviorObjects.Add(entry);
                }
            }

            return new AgentInventory
            {
                generated_at_utc = DateTime.UtcNow.ToString("o"),
                all_agent_components = allAgents.ToArray(),
                all_behavior_parameters = allBehaviors.ToArray(),
                behavior_name_stage7b_rts_student = targetBehaviorObjects.ToArray(),
            };
        }

        private static AgentInventoryEntry CreateInventoryEntry(
            string componentType,
            int instanceId,
            Transform transform,
            bool gameObjectActive,
            bool componentEnabled,
            BehaviorParameters behavior)
        {
            return new AgentInventoryEntry
            {
                component_type = componentType ?? "unknown",
                instance_id = instanceId,
                gameobject_path = GetTransformPath(transform),
                gameobject_active = gameObjectActive,
                component_enabled = componentEnabled,
                behavior_name = behavior != null ? behavior.BehaviorName : "missing",
                behavior_type = behavior != null ? behavior.BehaviorType.ToString() : "missing",
                model_assigned = behavior != null && behavior.Model != null,
                model_asset_path = ResolveModelAssetPath(behavior)
            };
        }

        private static string GetTransformPath(Transform value)
        {
            if (value == null)
            {
                return "missing";
            }

            string path = value.name;
            Transform current = value.parent;
            while (current != null)
            {
                path = current.name + "/" + path;
                current = current.parent;
            }

            return path;
        }

        private static string ResolveModelAssetPath(BehaviorParameters behavior)
        {
            if (behavior == null || behavior.Model == null)
            {
                return string.Empty;
            }

#if UNITY_EDITOR
            string path = AssetDatabase.GetAssetPath(behavior.Model);
            if (!string.IsNullOrWhiteSpace(path))
            {
                return path.Replace('\\', '/');
            }
#endif

            return behavior.Model.name;
        }

        private static int ExtractIntValue(string line, string key)
        {
            int keyIndex = line.IndexOf(key, StringComparison.Ordinal);
            if (keyIndex < 0)
            {
                return -1;
            }

            int valueStart = keyIndex + key.Length;
            int valueEnd = valueStart;
            while (valueEnd < line.Length && char.IsDigit(line[valueEnd]))
            {
                valueEnd++;
            }

            if (valueEnd <= valueStart)
            {
                return -1;
            }

            return int.TryParse(line.Substring(valueStart, valueEnd - valueStart), out int value)
                ? value
                : -1;
        }

        private string ResolveRuntimeModelPath(BehaviorParameters behavior)
        {
            if (behavior == null || behavior.Model == null)
            {
                return string.Empty;
            }

#if UNITY_EDITOR
            string assetPath = AssetDatabase.GetAssetPath(behavior.Model);
            if (!string.IsNullOrWhiteSpace(assetPath))
            {
                return assetPath.Replace('\\', '/');
            }
#endif

            return behavior.Model.name;
        }

        private static string ResolveProjectPath(string relativePath)
        {
            string relative = string.IsNullOrWhiteSpace(relativePath)
                ? "python/stage7b_teacher_replay/stage7b_8c_unity_inference_smoke_report.json"
                : relativePath.Replace('\\', '/');

            if (Path.IsPathRooted(relative))
            {
                return relative;
            }

            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            return Path.Combine(projectRoot, relative.Replace('/', Path.DirectorySeparatorChar));
        }

        private static void EnsureParentDirectory(string path)
        {
            string directory = Path.GetDirectoryName(path);
            if (!string.IsNullOrWhiteSpace(directory))
            {
                Directory.CreateDirectory(directory);
            }
        }

        private static string BuildMarkdown(Snapshot s)
        {
            var sb = new StringBuilder(4096);
            sb.AppendLine("# Stage7B-8C.2 Unity Inference Smoke Report");
            sb.AppendLine();
            sb.AppendLine("final_decision: " + s.final_decision);
            sb.AppendLine("ready_for_stage7b_8d_or_9: " + s.ready_for_stage7b_8d_or_9.ToString().ToLowerInvariant());
            sb.AppendLine("blocker_code: " + s.blocker_code);
            sb.AppendLine("blocker_reason: " + s.blocker_reason);
            sb.AppendLine();
            sb.AppendLine("## Model");
            sb.AppendLine("- onnx_source_path: " + s.onnx_source_path);
            sb.AppendLine("- unity_model_asset_path: " + s.unity_model_asset_path);
            sb.AppendLine("- model_copied_into_assets: " + s.model_copied_into_assets.ToString().ToLowerInvariant());
            sb.AppendLine("- unity_import_succeeded: " + s.unity_import_succeeded.ToString().ToLowerInvariant());
            sb.AppendLine("- model_assigned: " + s.model_assigned.ToString().ToLowerInvariant());
            sb.AppendLine("- model_asset_path_runtime: " + s.model_asset_path_runtime);
            sb.AppendLine("- behavior_type_runtime: " + s.behavior_type_runtime);
            sb.AppendLine("- behavior_name_runtime: " + s.behavior_name_runtime);
            sb.AppendLine();
            sb.AppendLine("## Observations");
            sb.AppendLine("- observation_length_expected: " + s.observation_length_expected);
            sb.AppendLine("- observation_values_written_by_agent: " + s.observation_values_written_by_agent);
            sb.AppendLine("- observation_nan_count: " + s.observation_nan_count);
            sb.AppendLine("- observation_source: " + s.observation_source);
            sb.AppendLine("- observation_zero_padding_warning_detected: " + s.observation_zero_padding_warning_detected.ToString().ToLowerInvariant());
            sb.AppendLine("- actual_collect_trace_path: " + s.actual_collect_trace_path);
            sb.AppendLine("- actual_collect_calls: " + s.actual_collect_calls);
            sb.AppendLine("- actual_collect_all_expected_values: " + s.actual_collect_all_expected_values.ToString().ToLowerInvariant());
            sb.AppendLine("- zero_fallback_used: " + s.zero_fallback_used.ToString().ToLowerInvariant());
            sb.AppendLine("- defensive_pre_ready_observation_count: " + s.defensive_pre_ready_observation_count);
            sb.AppendLine("- defensive_pre_ready_observation_used_after_runtime_ready: " + s.defensive_pre_ready_observation_used_after_runtime_ready.ToString().ToLowerInvariant());
            sb.AppendLine("- warning_padding_first_frame: " + s.warning_padding_first_frame);
            sb.AppendLine("- warning_padding_first_academy_step: " + s.warning_padding_first_academy_step);
            sb.AppendLine();
            sb.AppendLine("## Lifecycle");
            sb.AppendLine("- initialize_count: " + s.initialize_count);
            sb.AppendLine("- on_episode_begin_count: " + s.on_episode_begin_count);
            sb.AppendLine("- collect_observations_count: " + s.collect_observations_count);
            sb.AppendLine("- write_discrete_action_mask_count: " + s.write_discrete_action_mask_count);
            sb.AppendLine("- on_action_received_count: " + s.on_action_received_count);
            sb.AppendLine("- heuristic_call_count: " + s.heuristic_call_count);
            sb.AppendLine("- inference_kick_decision_request_count: " + s.inference_kick_decision_request_count);
            sb.AppendLine("- inference_runtime_ready_observed: " + s.inference_runtime_ready_observed.ToString().ToLowerInvariant());
            sb.AppendLine("- inference_first_ready_frame: " + s.inference_first_ready_frame);
            sb.AppendLine("- inference_first_ready_fixed_tick: " + s.inference_first_ready_fixed_tick);
            sb.AppendLine("- decision_requester_enabled_runtime: " + s.decision_requester_enabled_runtime.ToString().ToLowerInvariant());
            sb.AppendLine();
            sb.AppendLine("## Action Cycle");
            sb.AppendLine("- candidate_action_index_last: " + s.candidate_action_index_last);
            sb.AppendLine("- candidate_action_index_in_range: " + s.candidate_action_index_in_range.ToString().ToLowerInvariant());
            sb.AppendLine("- candidate_branch_size: " + s.candidate_branch_size);
            sb.AppendLine("- candidate_builder_success_count: " + s.candidate_builder_success_count);
            sb.AppendLine("- action_adapter_success_count: " + s.action_adapter_success_count);
            sb.AppendLine("- runtime_apply_attempted: " + s.runtime_apply_attempted);
            sb.AppendLine("- runtime_apply_accepted: " + s.runtime_apply_accepted);
            sb.AppendLine("- runtime_apply_rejected: " + s.runtime_apply_rejected);
            sb.AppendLine();
            sb.AppendLine("## Fallback Guards");
            sb.AppendLine("- teacher_replay_orchestrator_enabled: " + s.teacher_replay_orchestrator_enabled.ToString().ToLowerInvariant());
            sb.AppendLine("- manual_loop_enabled: " + s.manual_loop_enabled.ToString().ToLowerInvariant());
            sb.AppendLine("- watchdog_manual_fallback_enabled: " + s.watchdog_manual_fallback_enabled.ToString().ToLowerInvariant());
            sb.AppendLine("- demo_mode_active: " + s.demo_mode_active.ToString().ToLowerInvariant());
            sb.AppendLine("- heuristic_warning_detected: " + s.heuristic_warning_detected.ToString().ToLowerInvariant());
            sb.AppendLine();
            sb.AppendLine("## Console");
            sb.AppendLine("- unity_console_errors: " + s.unity_console_errors);
            sb.AppendLine("- unity_console_warnings: " + s.unity_console_warnings);
            sb.AppendLine("- warning_fewer_observations_0_detected: " + s.warning_fewer_observations_0_detected.ToString().ToLowerInvariant());
            sb.AppendLine("- warning_heuristic_not_implemented_detected: " + s.warning_heuristic_not_implemented_detected.ToString().ToLowerInvariant());
            sb.AppendLine("- timeout_error_log_count: " + s.timeout_error_log_count);
            sb.AppendLine("- timeout_spam_detected: " + s.timeout_spam_detected.ToString().ToLowerInvariant());
            sb.AppendLine();
            sb.AppendLine("## Artifacts");
            sb.AppendLine("- report_json: " + s.exact_generated_artifacts[0]);
            sb.AppendLine("- report_md: " + s.exact_generated_artifacts[1]);
            sb.AppendLine("- lifecycle_trace_jsonl: " + s.exact_generated_artifacts[2]);
            sb.AppendLine("- actual_collect_trace_jsonl: " + s.exact_generated_artifacts[3]);
            sb.AppendLine("- agent_inventory_json: " + s.exact_generated_artifacts[4]);
            sb.AppendLine();
            sb.AppendLine("generated_at_utc: " + s.generated_at_utc);
            return sb.ToString();
        }
    }
}
