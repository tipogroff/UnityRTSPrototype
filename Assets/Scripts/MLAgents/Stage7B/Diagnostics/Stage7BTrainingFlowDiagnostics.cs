using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using RTS.Gameplay;
using RTS.MLAgents.Stage7B.TeacherReplay;
using Unity.MLAgents;
using Unity.MLAgents.Policies;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.Diagnostics
{
    [DisallowMultipleComponent]
    public sealed class Stage7BTrainingFlowDiagnostics : MonoBehaviour
    {
        [SerializeField] private string _diagnosticJsonRelativePath = "python/stage7b_teacher_replay/stage7b_8b6_episode_boundary_fix_report.json";
        [SerializeField] private string _diagnosticMdRelativePath = "python/stage7b_teacher_replay/stage7b_8b6_episode_boundary_fix_report.md";
        [SerializeField] private float _writeIntervalSeconds = 1f;
        [SerializeField] private bool _enableRuntimeTrainingFlowDiagnostics = false;

        private float _nextWriteTime;
        private bool _isShuttingDown;

        [Serializable]
        private sealed class Snapshot
        {
            public string status;
            public bool trainer_connected;
            public bool trainer_timeout_reproduced;
            public int unity_console_errors;
            public int unity_console_warnings;
            public string behavior_name_runtime;
            public string behavior_type_runtime;
            public bool decision_requester_present;
            public bool decision_requester_enabled;
            public int decision_period;
            public bool take_actions_between_decisions;
            public bool teacher_replay_orchestrator_present;
            public bool teacher_replay_orchestrator_enabled;
            public bool student_teacher_replay_orchestrator_is_null;
            public bool manual_loop_enabled;
            public bool watchdog_manual_fallback_enabled;
            public bool demo_mode_active;
            public bool model_assigned;
            public string inference_device;
            public int on_enable_count;
            public int awake_count;
            public int start_count;
            public int initialize_count;
            public int on_episode_begin_count;
            public int collect_observations_count;
            public int write_mask_count;
            public int heuristic_count;
            public int on_action_received_count;
            public int end_episode_count;
            public int request_decision_count;
            public int request_action_count;
            public float first_collect_observations_time;
            public float first_write_mask_time;
            public float first_on_action_received_time;
            public int first_collect_observations_frame;
            public int first_write_mask_frame;
            public int first_on_action_received_frame;
            public int last_observation_length;
            public int last_observation_nan_count;
            public int last_action_candidate_index;
            public bool last_action_accepted;
            public int reset_calls;
            public int terminal_calls;
            public bool runtime_services_ready;
            public string[] missing_runtime_services;
            public bool stage6b3_baseline_touched;
            public string match_state_after_reset;
            public bool duplicate_spawn_detected;
            public double first_reset_duration_ms;
            public double first_observation_duration_ms;
            public double first_write_mask_duration_ms;
            public double first_on_action_received_duration_ms;
            public int bootstrap_start_new_episode_count;
            public int bootstrap_start_new_episode_skipped_reentrant_count;
            public string bootstrap_start_new_episode_reason;
            public string bootstrap_start_new_episode_caller;
            public string bootstrap_start_new_episode_path;
            public bool bootstrap_has_runtime_episode_started;
            public bool on_episode_begin_start_new_episode_called;
            public bool on_episode_begin_start_new_episode_result;
            public bool trainer_controlled_episode_reset_path;
            public string on_episode_begin_start_new_episode_path;
            public int trainer_controlled_kick_decision_request_count;
            public bool application_is_playing;
            public float time_scale;
            public long academy_step_count;
            public string current_decision_source;
            public bool decision_requester_disabled_by_stage7b;
            public string suspected_blocker;
            public string timeout_phase_classification;
            public string last_lifecycle_event;
            public string lifecycle_trace_path;
            public string generated_utc;
        }

private void Start()
        {
            if (!_enableRuntimeTrainingFlowDiagnostics)
            {
                return;
            }

            WriteSnapshot();
        }

private void Update()
        {
            if (!_enableRuntimeTrainingFlowDiagnostics)
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
            if (!_enableRuntimeTrainingFlowDiagnostics)
            {
                return;
            }

            if (_isShuttingDown || !Application.isPlaying)
            {
                return;
            }

            WriteSnapshot();
        }

        private void OnApplicationQuit()
        {
            // Avoid touching runtime singletons while Unity tears the scene down.
            _isShuttingDown = true;
        }

        private void WriteSnapshot()
        {
            if (!_enableRuntimeTrainingFlowDiagnostics)
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
                string jsonPath = ResolveProjectPath(_diagnosticJsonRelativePath);
                string mdPath = ResolveProjectPath(_diagnosticMdRelativePath);
                EnsureParentDirectory(jsonPath);
                EnsureParentDirectory(mdPath);

                string json = JsonUtility.ToJson(snapshot, true);
                File.WriteAllText(jsonPath, json, Encoding.UTF8);
                File.WriteAllText(mdPath, BuildMarkdown(snapshot), Encoding.UTF8);
            }
            catch (Exception ex)
            {
                Debug.LogWarning("[Stage7B][Diagnostics] Failed to write training flow diagnostic: " + ex.Message);
            }
        }

        private Snapshot BuildSnapshot()
        {
            NormalizeStage8B5OutputPaths();
            StudentMlAgent agent = FindFirstObjectByType<StudentMlAgent>();
            MlAgentsTrainingBootstrap bootstrap = FindFirstObjectByType<MlAgentsTrainingBootstrap>();
            Stage7BTeacherReplayDemoOrchestrator sceneOrchestrator = FindAnyOrchestratorInScene();

            var snapshot = new Snapshot
            {
                status = "IN_PROGRESS",
                unity_console_errors = 0,
                unity_console_warnings = 0,
                behavior_name_runtime = "unknown",
                behavior_type_runtime = "unknown",
                decision_requester_present = false,
                decision_requester_enabled = false,
                decision_period = 0,
                take_actions_between_decisions = false,
                teacher_replay_orchestrator_present = sceneOrchestrator != null,
                teacher_replay_orchestrator_enabled = sceneOrchestrator != null && sceneOrchestrator.isActiveAndEnabled,
                student_teacher_replay_orchestrator_is_null = true,
                manual_loop_enabled = false,
                watchdog_manual_fallback_enabled = false,
                demo_mode_active = false,
                model_assigned = false,
                inference_device = "unknown",
                runtime_services_ready = false,
                missing_runtime_services = Array.Empty<string>(),
                stage6b3_baseline_touched = false,
                match_state_after_reset = "unknown",
                duplicate_spawn_detected = false,
                application_is_playing = Application.isPlaying,
                time_scale = Time.timeScale,
                academy_step_count = TryGetAcademyStepCount(),
                current_decision_source = "unknown",
                decision_requester_disabled_by_stage7b = false,
                suspected_blocker = "unknown",
                timeout_phase_classification = "unclassified",
                last_lifecycle_event = ReadLastLifecycleEvent(),
                lifecycle_trace_path = "python/stage7b_teacher_replay/stage7b_8b6_lifecycle_trace.jsonl",
                generated_utc = DateTime.UtcNow.ToString("o")
            };

            Academy academy = Academy.IsInitialized ? Academy.Instance : null;
            snapshot.trainer_connected = academy != null && academy.IsCommunicatorOn;

            if (agent != null)
            {
                BehaviorParameters behavior = agent.GetComponent<BehaviorParameters>();
                Unity.MLAgents.DecisionRequester requester = agent.GetComponent<Unity.MLAgents.DecisionRequester>();
                Stage7BTeacherReplayDemoOrchestrator attachedOrchestrator = agent.TeacherReplayOrchestrator;

                snapshot.behavior_name_runtime = behavior != null ? behavior.BehaviorName : "missing";
                snapshot.behavior_type_runtime = behavior != null ? behavior.BehaviorType.ToString() : "missing";
                snapshot.model_assigned = behavior != null && behavior.Model != null;
                snapshot.inference_device = behavior != null ? behavior.InferenceDevice.ToString() : "missing";

                snapshot.decision_requester_present = requester != null;
                snapshot.decision_requester_enabled = requester != null && requester.enabled;
                snapshot.decision_period = requester != null ? requester.DecisionPeriod : 0;
                snapshot.take_actions_between_decisions = requester != null && requester.TakeActionsBetweenDecisions;

                snapshot.student_teacher_replay_orchestrator_is_null = attachedOrchestrator == null;
                snapshot.demo_mode_active = attachedOrchestrator != null && attachedOrchestrator.IsActive;

                snapshot.awake_count = agent.AwakeCount;
                snapshot.on_enable_count = agent.OnEnableCount;
                snapshot.start_count = agent.StartCount;
                snapshot.initialize_count = agent.InitializeCount;
                snapshot.on_episode_begin_count = agent.OnEpisodeBeginCount;
                snapshot.collect_observations_count = agent.Trace.CollectObservationsCalls;
                snapshot.write_mask_count = agent.Trace.WriteMaskCalls;
                snapshot.heuristic_count = agent.HeuristicCallCount;
                snapshot.on_action_received_count = agent.Trace.OnActionReceivedCalls;
                snapshot.end_episode_count = agent.EndEpisodeCount;
                snapshot.request_decision_count = agent.ManualRequestDecisionCount;
                snapshot.request_action_count = agent.ManualRequestActionCount;
                snapshot.first_collect_observations_time = agent.FirstCollectObservationsTime;
                snapshot.first_write_mask_time = agent.FirstWriteMaskTime;
                snapshot.first_on_action_received_time = agent.FirstOnActionReceivedTime;
                snapshot.first_collect_observations_frame = agent.FirstCollectObservationsFrame;
                snapshot.first_write_mask_frame = agent.FirstWriteMaskFrame;
                snapshot.first_on_action_received_frame = agent.FirstOnActionReceivedFrame;
                snapshot.last_observation_length = agent.LastObservationLength;
                snapshot.last_observation_nan_count = agent.LastObservationNanCount;
                snapshot.last_action_candidate_index = agent.LastActionCandidateIndex;
                snapshot.last_action_accepted = agent.LastActionAccepted;
                snapshot.reset_calls = agent.Trace.ResetCount;
                snapshot.terminal_calls = agent.TerminalCount;
                snapshot.first_reset_duration_ms = agent.FirstResetDurationMs;
                snapshot.first_observation_duration_ms = agent.FirstObservationDurationMs;
                snapshot.first_write_mask_duration_ms = agent.FirstWriteMaskDurationMs;
                snapshot.first_on_action_received_duration_ms = agent.FirstOnActionReceivedDurationMs;
                snapshot.on_episode_begin_start_new_episode_called = agent.OnEpisodeBeginStartNewEpisodeCalled;
                snapshot.on_episode_begin_start_new_episode_result = agent.OnEpisodeBeginStartNewEpisodeResult;
                snapshot.trainer_controlled_episode_reset_path = agent.OnEpisodeBeginUsedTrainerControlledEpisodeResetPath;
                snapshot.on_episode_begin_start_new_episode_path = agent.OnEpisodeBeginStartNewEpisodePath;
                snapshot.trainer_controlled_kick_decision_request_count = agent.TrainerControlledKickDecisionRequestCount;
                snapshot.current_decision_source = agent.CurrentDecisionSource;

                snapshot.manual_loop_enabled = !string.IsNullOrWhiteSpace(snapshot.current_decision_source)
                                              && snapshot.current_decision_source.IndexOf("manual_fixed_update", StringComparison.OrdinalIgnoreCase) >= 0;
                snapshot.watchdog_manual_fallback_enabled = agent.DecisionRequesterWatchdogFallbackEnabled
                                                            || agent.DecisionRequesterWatchdogFallbackActive;

                snapshot.decision_requester_disabled_by_stage7b = requester != null
                    && !requester.enabled
                    && !snapshot.demo_mode_active
                    && snapshot.current_decision_source.IndexOf("decision_requester", StringComparison.OrdinalIgnoreCase) < 0;
            }

            var missing = new List<string>();
            if (bootstrap == null)
            {
                missing.Add("MlAgentsTrainingBootstrap");
            }
            else
            {
                if (bootstrap.MatchBootstrap == null) missing.Add("MatchBootstrap");
                if (bootstrap.MatchManager == null) missing.Add("MatchManager");
                if (bootstrap.GridManager == null) missing.Add("GridManager");
                if (bootstrap.UnitRegistry == null) missing.Add("UnitRegistry");
                if (bootstrap.ResourceManager == null) missing.Add("ResourceManager");
                if (bootstrap.StudentAgent == null) missing.Add("StudentMlAgent");

                snapshot.duplicate_spawn_detected = bootstrap.DuplicateSpawnDetected;
                snapshot.match_state_after_reset = bootstrap.MatchManager != null
                    ? bootstrap.MatchManager.Phase.ToString()
                    : "missing";
                snapshot.bootstrap_start_new_episode_count = bootstrap.StartNewEpisodeInvocationCount;
                snapshot.bootstrap_start_new_episode_skipped_reentrant_count = bootstrap.StartNewEpisodeSkippedReentrantCount;
                snapshot.bootstrap_start_new_episode_reason = bootstrap.LastStartNewEpisodeReason;
                snapshot.bootstrap_start_new_episode_caller = bootstrap.LastStartNewEpisodeCaller;
                snapshot.bootstrap_start_new_episode_path = bootstrap.LastStartNewEpisodePath;
                snapshot.bootstrap_has_runtime_episode_started = bootstrap.HasRuntimeEpisodeStarted;
            }

            snapshot.runtime_services_ready = missing.Count == 0;
            snapshot.missing_runtime_services = missing.ToArray();
            snapshot.trainer_timeout_reproduced = snapshot.trainer_connected
                                                  && snapshot.on_action_received_count == 0
                                                  && snapshot.collect_observations_count == 0
                                                  && snapshot.application_is_playing;
            snapshot.timeout_phase_classification = ClassifyTimeoutPhase(snapshot);
            snapshot.suspected_blocker = DetermineSuspectedBlocker(snapshot);
            snapshot.status = snapshot.suspected_blocker == "unknown" ? "IN_PROGRESS" : "DIAGNOSED";
            return snapshot;
        }

        private void NormalizeStage8B5OutputPaths()
        {
            if (!string.IsNullOrWhiteSpace(_diagnosticJsonRelativePath)
                && (_diagnosticJsonRelativePath.IndexOf("stage7b_8b1_", StringComparison.OrdinalIgnoreCase) >= 0
                    || _diagnosticJsonRelativePath.IndexOf("stage7b_8b5_", StringComparison.OrdinalIgnoreCase) >= 0))
            {
                _diagnosticJsonRelativePath = "python/stage7b_teacher_replay/stage7b_8b6_episode_boundary_fix_report.json";
            }

            if (!string.IsNullOrWhiteSpace(_diagnosticMdRelativePath)
                && (_diagnosticMdRelativePath.IndexOf("stage7b_8b1_", StringComparison.OrdinalIgnoreCase) >= 0
                    || _diagnosticMdRelativePath.IndexOf("stage7b_8b5_", StringComparison.OrdinalIgnoreCase) >= 0))
            {
                _diagnosticMdRelativePath = "python/stage7b_teacher_replay/stage7b_8b6_episode_boundary_fix_report.md";
            }
        }

        private static string ReadLastLifecycleEvent()
        {
            string path = ResolveProjectPath("python/stage7b_teacher_replay/stage7b_8b6_lifecycle_trace.jsonl");
            if (!File.Exists(path))
            {
                return "missing_trace";
            }

            try
            {
                string[] lines = File.ReadAllLines(path, Encoding.UTF8);
                for (int i = lines.Length - 1; i >= 0; i--)
                {
                    string line = lines[i];
                    if (string.IsNullOrWhiteSpace(line))
                    {
                        continue;
                    }

                    const string token = "\"phase\":\"";
                    int tokenIndex = line.IndexOf(token, StringComparison.Ordinal);
                    if (tokenIndex < 0)
                    {
                        return line;
                    }

                    int start = tokenIndex + token.Length;
                    int end = line.IndexOf('"', start);
                    return end > start ? line.Substring(start, end - start) : line;
                }
            }
            catch
            {
                return "trace_read_failed";
            }

            return "empty_trace";
        }

        private static string ClassifyTimeoutPhase(Snapshot s)
        {
            if (s.on_episode_begin_count == 0)
            {
                return s.trainer_connected
                    ? "after_unity_connect_before_on_episode_begin"
                    : "before_unity_connect_before_on_episode_begin";
            }

            if (s.collect_observations_count == 0)
            {
                return s.trainer_connected
                    ? "after_on_episode_begin_before_collect_observations"
                    : "before_communicator_after_on_episode_begin_before_collect_observations";
            }

            if (s.write_mask_count == 0)
            {
                return s.trainer_connected
                    ? "after_collect_observations_before_write_discrete_action_mask"
                    : "before_communicator_after_collect_observations_before_write_discrete_action_mask";
            }

            if (s.on_action_received_count == 0)
            {
                return s.trainer_connected
                    ? "after_write_discrete_action_mask_before_on_action_received"
                    : "before_communicator_after_write_discrete_action_mask_before_on_action_received";
            }

            return s.trainer_connected
                ? "after_on_action_received_or_later"
                : "before_communicator_after_on_action_received_or_later";
        }

        private static string DetermineSuspectedBlocker(Snapshot s)
        {
            if (s.collect_observations_count == 0)
            {
                if (string.Equals(s.behavior_type_runtime, "HeuristicOnly", StringComparison.OrdinalIgnoreCase))
                {
                    return "agent_not_in_trainer_loop_behavior_type_heuristic_only";
                }

                if (!s.decision_requester_enabled)
                {
                    return "agent_not_participating_decision_requester_disabled";
                }

                return "agent_not_participating_in_academy_loop";
            }

            if (s.collect_observations_count > 0 && s.on_action_received_count == 0)
            {
                if (!s.decision_requester_enabled)
                {
                    return "no_actions_decision_requester_disabled";
                }

                if (s.demo_mode_active || !s.student_teacher_replay_orchestrator_is_null)
                {
                    return "demo_orchestrator_intercepts_actions";
                }

                return "no_actions_after_observation_check_request_cycle";
            }

            if (!s.runtime_services_ready)
            {
                return "runtime_services_missing_in_reset_path";
            }

            if (s.demo_mode_active || !s.student_teacher_replay_orchestrator_is_null)
            {
                return "stage7_demo_mode_active";
            }

            if (string.Equals(s.behavior_type_runtime, "HeuristicOnly", StringComparison.OrdinalIgnoreCase))
            {
                return "runtime_behavior_type_not_default";
            }

            return "unknown";
        }

        private static Stage7BTeacherReplayDemoOrchestrator FindAnyOrchestratorInScene()
        {
            Stage7BTeacherReplayDemoOrchestrator[] all = FindObjectsByType<Stage7BTeacherReplayDemoOrchestrator>(
                FindObjectsInactive.Include,
                FindObjectsSortMode.None);
            return all != null && all.Length > 0 ? all[0] : null;
        }

        private static long TryGetAcademyStepCount()
        {
            Academy academy = Academy.IsInitialized ? Academy.Instance : null;
            if (academy == null)
            {
                return -1;
            }

            return academy.StepCount;
        }

        private static string ResolveProjectPath(string relativePath)
        {
            string relative = string.IsNullOrWhiteSpace(relativePath)
                ? "python/stage7b_teacher_replay/stage7b_8b1_training_flow_diagnostic.json"
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
            var sb = new StringBuilder(2048);
            sb.AppendLine("# Stage7B-8B.6 Episode Boundary Fix Diagnostic");
            sb.AppendLine();
            sb.AppendLine("status: " + s.status);
            sb.AppendLine("suspected_blocker: " + s.suspected_blocker);
            sb.AppendLine("trainer_connected: " + s.trainer_connected.ToString().ToLowerInvariant());
            sb.AppendLine("behavior_name_runtime: " + s.behavior_name_runtime);
            sb.AppendLine("behavior_type_runtime: " + s.behavior_type_runtime);
            sb.AppendLine("decision_requester_enabled: " + s.decision_requester_enabled.ToString().ToLowerInvariant());
            sb.AppendLine("teacher_replay_orchestrator_present: " + s.teacher_replay_orchestrator_present.ToString().ToLowerInvariant());
            sb.AppendLine("teacher_replay_orchestrator_enabled: " + s.teacher_replay_orchestrator_enabled.ToString().ToLowerInvariant());
            sb.AppendLine("student_teacher_replay_orchestrator_is_null: " + s.student_teacher_replay_orchestrator_is_null.ToString().ToLowerInvariant());
            sb.AppendLine();
            sb.AppendLine("## Counters");
            sb.AppendLine("- on_enable_count: " + s.on_enable_count);
            sb.AppendLine("- awake_count: " + s.awake_count);
            sb.AppendLine("- start_count: " + s.start_count);
            sb.AppendLine("- initialize_count: " + s.initialize_count);
            sb.AppendLine("- on_episode_begin_count: " + s.on_episode_begin_count);
            sb.AppendLine("- collect_observations_count: " + s.collect_observations_count);
            sb.AppendLine("- write_mask_count: " + s.write_mask_count);
            sb.AppendLine("- heuristic_count: " + s.heuristic_count);
            sb.AppendLine("- on_action_received_count: " + s.on_action_received_count);
            sb.AppendLine("- end_episode_count: " + s.end_episode_count);
            sb.AppendLine("- first_write_mask_frame: " + s.first_write_mask_frame);
            sb.AppendLine("- first_write_mask_time: " + s.first_write_mask_time);
            sb.AppendLine("- first_on_action_received_frame: " + s.first_on_action_received_frame);
            sb.AppendLine("- first_on_action_received_time: " + s.first_on_action_received_time);
            sb.AppendLine();
            sb.AppendLine("## StartNewEpisode Boundary");
            sb.AppendLine("- bootstrap_start_new_episode_count: " + s.bootstrap_start_new_episode_count);
            sb.AppendLine("- bootstrap_start_new_episode_skipped_reentrant_count: " + s.bootstrap_start_new_episode_skipped_reentrant_count);
            sb.AppendLine("- bootstrap_start_new_episode_reason: " + s.bootstrap_start_new_episode_reason);
            sb.AppendLine("- bootstrap_start_new_episode_caller: " + s.bootstrap_start_new_episode_caller);
            sb.AppendLine("- bootstrap_start_new_episode_path: " + s.bootstrap_start_new_episode_path);
            sb.AppendLine("- bootstrap_has_runtime_episode_started: " + s.bootstrap_has_runtime_episode_started.ToString().ToLowerInvariant());
            sb.AppendLine("- on_episode_begin_start_new_episode_called: " + s.on_episode_begin_start_new_episode_called.ToString().ToLowerInvariant());
            sb.AppendLine("- on_episode_begin_start_new_episode_result: " + s.on_episode_begin_start_new_episode_result.ToString().ToLowerInvariant());
            sb.AppendLine("- trainer_controlled_episode_reset_path: " + s.trainer_controlled_episode_reset_path.ToString().ToLowerInvariant());
            sb.AppendLine("- on_episode_begin_start_new_episode_path: " + s.on_episode_begin_start_new_episode_path);
            sb.AppendLine("- trainer_controlled_kick_decision_request_count: " + s.trainer_controlled_kick_decision_request_count);
            sb.AppendLine();
            sb.AppendLine("## Timeout Classification");
            sb.AppendLine("- timeout_phase_classification: " + s.timeout_phase_classification);
            sb.AppendLine("- last_lifecycle_event: " + s.last_lifecycle_event);
            sb.AppendLine("- lifecycle_trace_path: " + s.lifecycle_trace_path);
            sb.AppendLine();
            sb.AppendLine("## Runtime Services");
            sb.AppendLine("- runtime_services_ready: " + s.runtime_services_ready.ToString().ToLowerInvariant());
            if (s.missing_runtime_services != null && s.missing_runtime_services.Length > 0)
            {
                sb.AppendLine("- missing_runtime_services: " + string.Join(", ", s.missing_runtime_services));
            }
            else
            {
                sb.AppendLine("- missing_runtime_services: none");
            }

            sb.AppendLine("- match_state_after_reset: " + s.match_state_after_reset);
            sb.AppendLine("- duplicate_spawn_detected: " + s.duplicate_spawn_detected.ToString().ToLowerInvariant());
            sb.AppendLine();
            sb.AppendLine("generated_utc: " + s.generated_utc);
            return sb.ToString();
        }
    }
}
