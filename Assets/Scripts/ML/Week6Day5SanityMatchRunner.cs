using System;
using System.Collections.Generic;
using System.IO;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

#if UNITY_EDITOR
using UnityEditor;
#endif

namespace RTS.ML
{
    [DisallowMultipleComponent]
    public sealed class Week6Day5SanityMatchRunner : MonoBehaviour
    {
        [Serializable]
        private sealed class CompactEpisodeReport
        {
            public string status;
            public string student_controlled_side;
            public string baseline_side;
            public int episodes_run;
            public int decision_requests_sent;
            public int decision_requests_succeeded;
            public int decision_requests_failed;
            public bool server_started;
            public bool server_shutdown_clean;
            public int student_commands_submitted;
            public int baseline_commands_submitted;
            public float invalid_command_share;
            public float ignored_command_share;
            public Week6CountEntry[] action_histogram;
            public float produce_frequency;
            public float attack_frequency;
            public string terminal_reason;
            public string error;
            public int steps_run;
            public int runtime_rejected_count;
            public string generated_at_utc;
            public Week6EpisodeDiagnosticsReport diagnostics;
        }

        [Header("Safe Day5 Sanity")]
        [SerializeField] private int _episodeCount = 1;
        [SerializeField] private int _maxStepsPerEpisode = 200;
        [SerializeField] private int _maxDecisionSubmissionsPerEpisode = 200;
        [SerializeField] private Owner _studentControlledPlayer = Owner.Player1;
        [SerializeField] private bool _verboseLogging = true;

        [Header("Output")]
        [SerializeField] private string _jsonReportRelativePath = "python/week6_student/tmp/day5_sanity/day5_sanity_episode_report.json";

        private EpisodeController _episodeController;
        private MatchManager _matchManager;
        private Week6StudentPolicyAdapter _studentAdapter;
        private readonly Dictionary<UnitActionType, int> _actionHistogram = new Dictionary<UnitActionType, int>();
        private readonly Dictionary<string, int> _runtimeRejectionReasons = new Dictionary<string, int>(StringComparer.Ordinal);
        private HeuristicPolicyAdapter _heuristicAdapter;
        private Week6EpisodeDiagnosticsCollector _diagnosticsCollector;

#if UNITY_EDITOR
        [ContextMenu("Run Week6 Day5 Safe Sanity")]
        private void ContextMenuExecute()
        {
            if (!EditorApplication.isPlaying)
            {
                EditorUtility.DisplayDialog("Play Mode Required", "Please enter Play Mode before running Day 5 safe sanity.", "OK");
                return;
            }

            ExecuteSanityMatches();
        }
#endif

        public void ExecuteSanityMatches()
        {
            ResolveReferences();
            if (_episodeController == null || _matchManager == null || _studentAdapter == null)
            {
                Debug.LogError("[Week6Day5SanityMatchRunner] Required runtime references are missing.");
                return;
            }

            Owner baselineOwner = _studentControlledPlayer == Owner.Player1 ? Owner.Player2 : Owner.Player1;

            // Stop FixedUpdate stepping BEFORE applying configuration to eliminate
            // the auto-start race: no ticks can fire in a half-configured state.
            bool previousAutoStep = _episodeController.AutoStepInFixedUpdate;
            _episodeController.AutoStepInFixedUpdate = false;

            _episodeController.ConfigureWeek6PlayerControlModes(
                enableStudentMatchControl: true,
                player1Mode: _studentControlledPlayer == Owner.Player1 ? Week6PlayerControlMode.StudentInference : Week6PlayerControlMode.HeuristicBaseline,
                player2Mode: _studentControlledPlayer == Owner.Player2 ? Week6PlayerControlMode.StudentInference : Week6PlayerControlMode.HeuristicBaseline);

            CompactEpisodeReport finalReport;
            _heuristicAdapter = FindFirstObjectByType<HeuristicPolicyAdapter>();
            _diagnosticsCollector = new Week6EpisodeDiagnosticsCollector(_studentControlledPlayer, baselineOwner);
            _matchManager.OnCommandRejected += OnCommandRejected;
            _matchManager.OnCommandAccepted += OnCommandAccepted;
            SubscribeHeuristicEvents();
            try
            {
                finalReport = RunBoundedSanity(_episodeCount, baselineOwner);
            }
            finally
            {
                _matchManager.OnCommandRejected -= OnCommandRejected;
                _matchManager.OnCommandAccepted -= OnCommandAccepted;
                UnsubscribeHeuristicEvents();
                _episodeController.AutoStepInFixedUpdate = previousAutoStep;
            }

            finalReport.server_shutdown_clean = _studentAdapter.ShutdownBridgeForSanity();
            WriteCompactReport(finalReport);

            Debug.Log(
                $"[Week6Day5SanityMatchRunner] status={finalReport.status}, episodes={finalReport.episodes_run}, " +
                $"student={finalReport.student_controlled_side}, baseline={finalReport.baseline_side}, " +
                $"requests={finalReport.decision_requests_sent}/{finalReport.decision_requests_succeeded}/{finalReport.decision_requests_failed}, " +
                $"shutdownClean={finalReport.server_shutdown_clean}");
        }

        private CompactEpisodeReport RunBoundedSanity(int requestedEpisodes, Owner baselineOwner)
        {
            int boundedEpisodes = Mathf.Max(1, requestedEpisodes);
            int episodesRun = 0;
            int stepsRun = 0;
            int studentCommandsSubmitted = 0;
            int baselineCommandsSubmitted = 0;
            int runtimeRejectedCount = 0;
            int studentInvalidCommands = 0;
            int produceCount = 0;
            int attackCount = 0;
            string terminalReason = "unknown";
            string status = "pass";
            string error = string.Empty;

            _actionHistogram.Clear();
            _runtimeRejectionReasons.Clear();

            for (int episodeIndex = 0; episodeIndex < boundedEpisodes; episodeIndex++)
            {
                _episodeController.StartNewEpisode();
                episodesRun++;
                _runtimeRejectionReasons.Clear();

                int stepCount = 0;
                while (_episodeController.IsRunning)
                {
                    if (_maxDecisionSubmissionsPerEpisode > 0 && stepCount >= _maxDecisionSubmissionsPerEpisode)
                    {
                        status = "fail";
                        error = $"Decision submission cap reached ({_maxDecisionSubmissionsPerEpisode}).";
                        terminalReason = "DecisionCapStop";
                        _episodeController.ResetEpisode();
                        break;
                    }

                    bool continueRunning = _episodeController.StepEpisodeOnce();
                    stepCount++;
                    stepsRun++;
                    _diagnosticsCollector?.RecordStepCompleted();

                    if (!_episodeController.TryGetWeek6StudentExecutionReport(_studentControlledPlayer, out StudentPolicyExecutionReport report))
                    {
                        status = "fail";
                        error = "Student execution report is missing for current step.";
                        terminalReason = "MissingStudentReport";
                        _episodeController.ResetEpisode();
                        break;
                    }

                    if (!report.BridgeSucceeded)
                    {
                        status = "fail";
                        error = string.IsNullOrWhiteSpace(report.Error)
                            ? "Student bridge request failed."
                            : report.Error;
                        terminalReason = "StudentBridgeFailure";
                        _episodeController.ResetEpisode();
                        break;
                    }

                    int studentSubmittedThisStep = report.AcceptedCount + report.RejectedCount;
                    studentCommandsSubmitted += studentSubmittedThisStep;
                    studentInvalidCommands += report.RejectedCount;
                    _diagnosticsCollector?.RecordStudentDecodedActions(report.DecodedActions);
                    _diagnosticsCollector?.RecordStudentRejectionReasons(report.RejectionReasons);

                    IReadOnlyList<AgentAction> decodedActions = report.DecodedActions;
                    for (int i = 0; i < decodedActions.Count; i++)
                    {
                        AgentAction action = decodedActions[i];
                        IncrementActionCount(_actionHistogram, action.ActionType);
                        if (action.ActionType == UnitActionType.Produce)
                        {
                            produceCount++;
                        }
                        else if (action.ActionType == UnitActionType.Attack)
                        {
                            attackCount++;
                        }
                    }

                    RlLoopStepReport stepReport = _episodeController.LastRlLoopStepReport;
                    int totalSubmittedThisStep = stepReport.ActionsAccepted + stepReport.ActionsRejected;
                    int baselineSubmittedThisStep = Mathf.Max(0, totalSubmittedThisStep - studentSubmittedThisStep);
                    baselineCommandsSubmitted += baselineSubmittedThisStep;

                    if (_maxStepsPerEpisode > 0 && stepCount >= _maxStepsPerEpisode && _episodeController.IsRunning)
                    {
                        terminalReason = "StepCapStop";
                        _episodeController.ResetEpisode();
                        break;
                    }

                    if (!continueRunning)
                    {
                        string runtimeTerminal = _episodeController.LastTerminalReport.TerminalReason.ToString();
                        terminalReason = string.IsNullOrWhiteSpace(runtimeTerminal) ? "Unknown" : runtimeTerminal;
                        break;
                    }

                }

                runtimeRejectedCount += CountDictionaryValues(_runtimeRejectionReasons);

                if (!string.Equals(status, "pass", StringComparison.Ordinal))
                {
                    break;
                }
            }

            StudentBridgeRuntimeSnapshot snapshot = _studentAdapter.GetRuntimeSnapshot();
            float invalidShare = studentCommandsSubmitted > 0
                ? (float)studentInvalidCommands / studentCommandsSubmitted
                : 0f;
            float ignoredShare = (studentCommandsSubmitted + runtimeRejectedCount) > 0
                ? (float)runtimeRejectedCount / (studentCommandsSubmitted + runtimeRejectedCount)
                : 0f;

            return new CompactEpisodeReport
            {
                status = status,
                student_controlled_side = _studentControlledPlayer.ToString(),
                baseline_side = baselineOwner.ToString(),
                episodes_run = episodesRun,
                decision_requests_sent = snapshot.DecisionRequestsSent,
                decision_requests_succeeded = snapshot.DecisionRequestsSucceeded,
                decision_requests_failed = snapshot.DecisionRequestsFailed,
                server_started = snapshot.ServerStarted,
                server_shutdown_clean = snapshot.ServerShutdownClean,
                student_commands_submitted = studentCommandsSubmitted,
                baseline_commands_submitted = baselineCommandsSubmitted,
                invalid_command_share = invalidShare,
                ignored_command_share = ignoredShare,
                action_histogram = ToCountEntries(_actionHistogram),
                produce_frequency = stepsRun > 0 ? (float)produceCount / stepsRun : 0f,
                attack_frequency = stepsRun > 0 ? (float)attackCount / stepsRun : 0f,
                terminal_reason = terminalReason,
                error = string.IsNullOrWhiteSpace(error) ? snapshot.LastError : error,
                steps_run = stepsRun,
                runtime_rejected_count = runtimeRejectedCount,
                generated_at_utc = DateTime.UtcNow.ToString("O"),
                diagnostics = BuildDiagnostics(episodesRun, terminalReason),
            };
        }

        private Week6EpisodeDiagnosticsReport BuildDiagnostics(int episodeIndex, string terminalReason)
        {
            if (_diagnosticsCollector == null)
            {
                return null;
            }

            _diagnosticsCollector.SetTerminalReason(terminalReason);
            return _diagnosticsCollector.BuildEpisodeReport(episodeIndex);
        }

        private void OnCommandAccepted(MatchCommand command)
        {
            _diagnosticsCollector?.RecordRuntimeAccepted(command);
        }

        private void OnCommandRejected(MatchCommand command, string reason)
        {
            _diagnosticsCollector?.RecordRuntimeRejected(command, reason);

            if (command.Owner != _studentControlledPlayer)
            {
                return;
            }

            IncrementStringCount(_runtimeRejectionReasons, reason);
        }

        private void SubscribeHeuristicEvents()
        {
            if (_heuristicAdapter == null)
            {
                return;
            }

            _heuristicAdapter.OnActionEvaluated -= OnHeuristicActionEvaluated;
            _heuristicAdapter.OnActionEvaluated += OnHeuristicActionEvaluated;
        }

        private void UnsubscribeHeuristicEvents()
        {
            if (_heuristicAdapter == null)
            {
                return;
            }

            _heuristicAdapter.OnActionEvaluated -= OnHeuristicActionEvaluated;
        }

        private void OnHeuristicActionEvaluated(HeuristicActionEvaluation evaluation)
        {
            _diagnosticsCollector?.RecordHeuristicActionEvaluation(evaluation);
        }

        private void ResolveReferences()
        {
            _episodeController = EpisodeController.Instance ?? FindFirstObjectByType<EpisodeController>();
            _matchManager = MatchManager.Instance ?? FindFirstObjectByType<MatchManager>();
            _studentAdapter = FindFirstObjectByType<Week6StudentPolicyAdapter>();
        }

        private void WriteCompactReport(CompactEpisodeReport report)
        {
            string projectRoot = Directory.GetParent(Application.dataPath).FullName;
            string jsonPath = Path.Combine(projectRoot, _jsonReportRelativePath);
            string jsonDir = Path.GetDirectoryName(jsonPath);
            if (!string.IsNullOrWhiteSpace(jsonDir))
            {
                Directory.CreateDirectory(jsonDir);
            }

            File.WriteAllText(jsonPath, JsonUtility.ToJson(report, true));
            Debug.Log("[Week6Day5SanityMatchRunner] Compact report: " + jsonPath);
        }

        private static void IncrementActionCount(IDictionary<UnitActionType, int> map, UnitActionType actionType)
        {
            if (!map.TryGetValue(actionType, out int count))
            {
                count = 0;
            }

            map[actionType] = count + 1;
        }

        private static void IncrementStringCount(IDictionary<string, int> map, string key)
        {
            string normalized = string.IsNullOrWhiteSpace(key) ? "unknown" : key;
            if (!map.TryGetValue(normalized, out int count))
            {
                count = 0;
            }

            map[normalized] = count + 1;
        }

        private static Week6CountEntry[] ToCountEntries(IDictionary<UnitActionType, int> counts)
        {
            var entries = new List<Week6CountEntry>(counts.Count);
            foreach (KeyValuePair<UnitActionType, int> kvp in counts)
            {
                entries.Add(new Week6CountEntry { key = kvp.Key.ToString(), value = kvp.Value });
            }

            entries.Sort((left, right) => right.value.CompareTo(left.value));
            return entries.ToArray();
        }

        private static int CountDictionaryValues(IDictionary<string, int> counts)
        {
            int total = 0;
            foreach (KeyValuePair<string, int> kvp in counts)
            {
                total += kvp.Value;
            }

            return total;
        }
    }
}
