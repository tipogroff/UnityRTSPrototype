using RTS.Core;
using RTS.Gameplay;
using UnityEngine;
using System.IO;

#if UNITY_EDITOR
using UnityEditor;
#endif

namespace RTS.ML
{
    [DisallowMultipleComponent]
    public sealed class Week6VisualInspectionRunner : MonoBehaviour
    {
        [Header("Visual Inspection")]
        [SerializeField] private Owner _studentControlledPlayer = Owner.Player1;
        [SerializeField] private bool _autoStartOnPlay = true;
        [SerializeField] private bool _showOverlay = true;
        [SerializeField] private bool _logTerminalSummary = true;

        [Header("Overlay")]
        [SerializeField] private Vector2 _overlayPosition = new Vector2(14f, 14f);

        [Header("Output")]
        [SerializeField] private string _jsonReportRelativePath = "python/week6_student/tmp/week6_visual/week6_visual_episode_diagnostics.json";

        private EpisodeController _episodeController;
        private MatchManager _matchManager;
        private Week6StudentPolicyAdapter _studentAdapter;
        private HeuristicPolicyAdapter _heuristicAdapter;
        private Week6EpisodeDiagnosticsCollector _diagnosticsCollector;
        private bool _terminalReportWritten;

        private int _acceptedStudentCommands;
        private int _invalidStudentCommands;
        private int _runtimeRejectedStudentCommands;
        private int _lastCollectedStep = -1;
        private int _lastCollectedEpisode = -1;
        private string _lastTerminalReason = "none";
        private bool _sessionActive;

        private void OnEnable()
        {
            ResolveReferences();
            SubscribeToMatchEvents();
        }

        private void Start()
        {
            if (_autoStartOnPlay && !_sessionActive)
            {
                StartVisualInspectionMatch();
            }
        }

        private void OnDisable()
        {
            UnsubscribeFromMatchEvents();
            UnsubscribeHeuristicEvents();
        }

        private void Update()
        {
            if (!_sessionActive)
            {
                return;
            }

            ResolveReferences();
            if (_episodeController == null || _matchManager == null)
            {
                return;
            }

            if (_episodeController.EpisodeIndex != _lastCollectedEpisode)
            {
                _lastCollectedEpisode = _episodeController.EpisodeIndex;
                _lastCollectedStep = -1;
            }

            int currentStep = _matchManager.Step;
            if (currentStep == _lastCollectedStep)
            {
                return;
            }

            _lastCollectedStep = currentStep;

            if (_episodeController.TryGetWeek6StudentExecutionReport(_studentControlledPlayer, out StudentPolicyExecutionReport report))
            {
                _acceptedStudentCommands += report.AcceptedCount;
                _invalidStudentCommands += report.RejectedCount;
                _diagnosticsCollector?.RecordStudentDecodedActions(report.DecodedActions);
                _diagnosticsCollector?.RecordStudentRejectionReasons(report.RejectionReasons);
            }

            if (currentStep > 0)
            {
                _diagnosticsCollector?.RecordStepCompleted();
            }

            EpisodeEndReport terminalReport = _episodeController.LastTerminalReport;
            if (terminalReport.IsTerminal)
            {
                _lastTerminalReason = terminalReport.TerminalReason.ToString();
            }
        }

        private void OnGUI()
        {
            if (!_showOverlay)
            {
                return;
            }

            ResolveReferences();

            string studentSide = _studentControlledPlayer.ToString();
            string baselineSide = _studentControlledPlayer == Owner.Player1 ? Owner.Player2.ToString() : Owner.Player1.ToString();
            StudentBridgeRuntimeSnapshot snapshot = _studentAdapter != null
                ? _studentAdapter.GetRuntimeSnapshot()
                : default;

            GUILayout.BeginArea(new Rect(_overlayPosition.x, _overlayPosition.y, 520f, 190f), GUI.skin.box);
            GUILayout.Label("Week 6 Visual Inspection");
            GUILayout.Label($"Student side: {studentSide} | Baseline side: {baselineSide}");
            GUILayout.Label($"Checkpoint: {GetCheckpointPathLabel()}");
            GUILayout.Label($"Session active: {_sessionActive}");
            GUILayout.Label($"Student decisions sent: {snapshot.DecisionRequestsSent} (ok={snapshot.DecisionRequestsSucceeded}, failed={snapshot.DecisionRequestsFailed})");
            GUILayout.Label($"Student accepted/invalid commands: {_acceptedStudentCommands}/{_invalidStudentCommands}");
            GUILayout.Label($"Runtime rejected (student side): {_runtimeRejectedStudentCommands}");
            GUILayout.Label($"Last terminal reason: {_lastTerminalReason}");
            GUILayout.EndArea();
        }

#if UNITY_EDITOR
        [ContextMenu("Start Visual Inspection Match")]
        private void ContextMenuStartVisualInspectionMatch()
        {
            if (!EditorApplication.isPlaying)
            {
                EditorUtility.DisplayDialog("Play Mode Required", "Please enter Play Mode before starting visual inspection.", "OK");
                return;
            }

            StartVisualInspectionMatch();
        }

        [ContextMenu("Restart Visual Inspection Match")]
        private void ContextMenuRestartVisualInspectionMatch()
        {
            if (!EditorApplication.isPlaying)
            {
                EditorUtility.DisplayDialog("Play Mode Required", "Please enter Play Mode before restarting visual inspection.", "OK");
                return;
            }

            RestartVisualInspectionMatch();
        }
#endif

        public void StartVisualInspectionMatch()
        {
            ResolveReferences();
            if (_episodeController == null)
            {
                Debug.LogError("[Week6VisualInspectionRunner] EpisodeController is missing.");
                return;
            }

            ConfigureWeek6ControlModes();
            ResetSessionCounters();
            InitializeDiagnosticsCollector();
            SubscribeHeuristicEvents();
            _sessionActive = true;

            _episodeController.StartNewEpisode();
        }

        public void RestartVisualInspectionMatch()
        {
            StartVisualInspectionMatch();
        }

        private void ConfigureWeek6ControlModes()
        {
            Week6PlayerControlMode player1Mode = _studentControlledPlayer == Owner.Player1
                ? Week6PlayerControlMode.StudentInference
                : Week6PlayerControlMode.HeuristicBaseline;
            Week6PlayerControlMode player2Mode = _studentControlledPlayer == Owner.Player2
                ? Week6PlayerControlMode.StudentInference
                : Week6PlayerControlMode.HeuristicBaseline;

            _episodeController.ConfigureWeek6PlayerControlModes(
                enableStudentMatchControl: true,
                player1Mode: player1Mode,
                player2Mode: player2Mode);
        }

        private void ResetSessionCounters()
        {
            _acceptedStudentCommands = 0;
            _invalidStudentCommands = 0;
            _runtimeRejectedStudentCommands = 0;
            _lastCollectedEpisode = -1;
            _lastCollectedStep = -1;
            _lastTerminalReason = "none";
            _terminalReportWritten = false;
        }

        private void ResolveReferences()
        {
            _episodeController = EpisodeController.Instance ?? FindFirstObjectByType<EpisodeController>();
            _matchManager = MatchManager.Instance ?? FindFirstObjectByType<MatchManager>();
            _studentAdapter = FindFirstObjectByType<Week6StudentPolicyAdapter>();
            _heuristicAdapter = FindFirstObjectByType<HeuristicPolicyAdapter>();
        }

        private void SubscribeToMatchEvents()
        {
            if (_matchManager == null)
            {
                return;
            }

            _matchManager.OnCommandRejected -= HandleCommandRejected;
            _matchManager.OnCommandRejected += HandleCommandRejected;

            _matchManager.OnCommandAccepted -= HandleCommandAccepted;
            _matchManager.OnCommandAccepted += HandleCommandAccepted;

            _matchManager.OnMatchEnded -= HandleMatchEnded;
            _matchManager.OnMatchEnded += HandleMatchEnded;
        }

        private void UnsubscribeFromMatchEvents()
        {
            if (_matchManager == null)
            {
                return;
            }

            _matchManager.OnCommandRejected -= HandleCommandRejected;
            _matchManager.OnCommandAccepted -= HandleCommandAccepted;
            _matchManager.OnMatchEnded -= HandleMatchEnded;
        }

        private void SubscribeHeuristicEvents()
        {
            if (_heuristicAdapter == null)
            {
                return;
            }

            _heuristicAdapter.OnActionEvaluated -= HandleHeuristicActionEvaluated;
            _heuristicAdapter.OnActionEvaluated += HandleHeuristicActionEvaluated;
        }

        private void UnsubscribeHeuristicEvents()
        {
            if (_heuristicAdapter == null)
            {
                return;
            }

            _heuristicAdapter.OnActionEvaluated -= HandleHeuristicActionEvaluated;
        }

        private void InitializeDiagnosticsCollector()
        {
            Owner baseline = _studentControlledPlayer == Owner.Player1 ? Owner.Player2 : Owner.Player1;
            _diagnosticsCollector = new Week6EpisodeDiagnosticsCollector(_studentControlledPlayer, baseline);
        }

        private void HandleCommandAccepted(MatchCommand command)
        {
            if (!_sessionActive)
            {
                return;
            }

            _diagnosticsCollector?.RecordRuntimeAccepted(command);
        }

        private void HandleCommandRejected(MatchCommand command, string reason)
        {
            if (!_sessionActive || command.Owner != _studentControlledPlayer)
            {
                _diagnosticsCollector?.RecordRuntimeRejected(command, reason);
                return;
            }

            _runtimeRejectedStudentCommands++;
            _diagnosticsCollector?.RecordRuntimeRejected(command, reason);
        }

        private void HandleHeuristicActionEvaluated(HeuristicActionEvaluation evaluation)
        {
            if (!_sessionActive)
            {
                return;
            }

            _diagnosticsCollector?.RecordHeuristicActionEvaluation(evaluation);
        }

        private void HandleMatchEnded(Owner winner)
        {
            if (_episodeController == null)
            {
                return;
            }

            EpisodeEndReport terminalReport = _episodeController.LastTerminalReport;
            if (terminalReport.IsTerminal)
            {
                _lastTerminalReason = terminalReport.TerminalReason.ToString();
                _diagnosticsCollector?.SetTerminalReason(_lastTerminalReason);

                if (!_terminalReportWritten)
                {
                    WriteCompactDiagnosticsReport();
                    _terminalReportWritten = true;
                }

                if (_logTerminalSummary)
                {
                    Debug.Log(
                        $"[Week6VisualInspectionRunner] Terminal. winner={winner}, reason={terminalReport.TerminalReason}, " +
                        $"studentAccepted={_acceptedStudentCommands}, studentInvalid={_invalidStudentCommands}, " +
                        $"runtimeRejected={_runtimeRejectedStudentCommands}");
                }
            }
        }

        private void WriteCompactDiagnosticsReport()
        {
            if (_diagnosticsCollector == null || _episodeController == null)
            {
                return;
            }

            Week6EpisodeDiagnosticsReport report = _diagnosticsCollector.BuildEpisodeReport(_episodeController.EpisodeIndex);

            string projectRoot = Directory.GetParent(Application.dataPath).FullName;
            string jsonPath = Path.Combine(projectRoot, _jsonReportRelativePath);
            string jsonDir = Path.GetDirectoryName(jsonPath);
            if (!string.IsNullOrWhiteSpace(jsonDir))
            {
                Directory.CreateDirectory(jsonDir);
            }

            File.WriteAllText(jsonPath, JsonUtility.ToJson(report, true));
            Debug.Log("[Week6VisualInspectionRunner] Compact diagnostics report: " + jsonPath);
        }

        private string GetCheckpointPathLabel()
        {
            if (_studentAdapter == null)
            {
                return "n/a";
            }

            string checkpoint = _studentAdapter.CheckpointRelativePath;
            return string.IsNullOrWhiteSpace(checkpoint) ? "(empty)" : checkpoint;
        }
    }
}
