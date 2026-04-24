using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Threading.Tasks;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace RTS.ML
{
    public enum Week6PlayerControlMode
    {
        Idle = 0,
        HeuristicBaseline = 1,
        StudentInference = 2,
    }

    public readonly struct StudentPolicyExecutionReport
    {
        private readonly AgentAction[] _decodedActions;
        private readonly string[] _rejectionReasons;
        private readonly StudentLiveFilterDiagnostics _filterDiagnostics;
        private readonly StudentMaskAwareDiagnostics _maskAwareDiagnostics;

        public StudentPolicyExecutionReport(
            Owner playerId,
            bool bridgeSucceeded,
            bool usedCanonicalStepInput,
            IReadOnlyList<AgentAction> decodedActions,
            int acceptedCount,
            int rejectedCount,
            IReadOnlyList<string> rejectionReasons,
            StudentLiveFilterDiagnostics filterDiagnostics,
            StudentMaskAwareDiagnostics maskAwareDiagnostics,
            string error)
        {
            PlayerId = playerId;
            BridgeSucceeded = bridgeSucceeded;
            UsedCanonicalStepInput = usedCanonicalStepInput;
            _decodedActions = Copy(decodedActions);
            _rejectionReasons = CopyStrings(rejectionReasons);
            _filterDiagnostics = filterDiagnostics;
            _maskAwareDiagnostics = maskAwareDiagnostics;
            AcceptedCount = acceptedCount;
            RejectedCount = rejectedCount;
            Error = error ?? string.Empty;
        }

        public Owner PlayerId { get; }
        public bool BridgeSucceeded { get; }
        public bool UsedCanonicalStepInput { get; }
        public IReadOnlyList<AgentAction> DecodedActions => _decodedActions;
        public int DecodedActionCount => _decodedActions.Length;
        public IReadOnlyList<string> RejectionReasons => _rejectionReasons;
        public StudentLiveFilterDiagnostics FilterDiagnostics => _filterDiagnostics;
        public StudentMaskAwareDiagnostics MaskAwareDiagnostics => _maskAwareDiagnostics;
        public int AcceptedCount { get; }
        public int RejectedCount { get; }
        public string Error { get; }

        private static AgentAction[] Copy(IReadOnlyList<AgentAction> source)
        {
            if (source == null || source.Count == 0)
            {
                return Array.Empty<AgentAction>();
            }

            var copy = new AgentAction[source.Count];
            for (int i = 0; i < source.Count; i++)
            {
                copy[i] = source[i];
            }

            return copy;
        }

        private static string[] CopyStrings(IReadOnlyList<string> source)
        {
            if (source == null || source.Count == 0)
            {
                return Array.Empty<string>();
            }

            var copy = new string[source.Count];
            for (int i = 0; i < source.Count; i++)
            {
                copy[i] = source[i] ?? string.Empty;
            }

            return copy;
        }
    }

    public readonly struct StudentLiveFilterDiagnostics
    {
        public StudentLiveFilterDiagnostics(
            int candidateCellsTotal,
            int eligibleOwnActorCells,
            int filteredOutNeutralCells,
            int filteredOutEnemyCells,
            int filteredOutNoncontrollableCells,
            int commandsBuiltAfterFilter,
            int commandsSubmittedAfterFilter,
            int wrongOwnerRejectionsAfterFilter)
        {
            CandidateCellsTotal = candidateCellsTotal;
            EligibleOwnActorCells = eligibleOwnActorCells;
            FilteredOutNeutralCells = filteredOutNeutralCells;
            FilteredOutEnemyCells = filteredOutEnemyCells;
            FilteredOutNoncontrollableCells = filteredOutNoncontrollableCells;
            CommandsBuiltAfterFilter = commandsBuiltAfterFilter;
            CommandsSubmittedAfterFilter = commandsSubmittedAfterFilter;
            WrongOwnerRejectionsAfterFilter = wrongOwnerRejectionsAfterFilter;
        }

        public static StudentLiveFilterDiagnostics Empty =>
            new StudentLiveFilterDiagnostics(0, 0, 0, 0, 0, 0, 0, 0);

        public int CandidateCellsTotal { get; }
        public int EligibleOwnActorCells { get; }
        public int FilteredOutNeutralCells { get; }
        public int FilteredOutEnemyCells { get; }
        public int FilteredOutNoncontrollableCells { get; }
        public int CommandsBuiltAfterFilter { get; }
        public int CommandsSubmittedAfterFilter { get; }
        public int WrongOwnerRejectionsAfterFilter { get; }

        public StudentLiveFilterDiagnostics WithSubmissionOutcome(
            int commandsBuiltAfterFilter,
            int commandsSubmittedAfterFilter,
            int wrongOwnerRejectionsAfterFilter)
        {
            return new StudentLiveFilterDiagnostics(
                CandidateCellsTotal,
                EligibleOwnActorCells,
                FilteredOutNeutralCells,
                FilteredOutEnemyCells,
                FilteredOutNoncontrollableCells,
                commandsBuiltAfterFilter,
                commandsSubmittedAfterFilter,
                wrongOwnerRejectionsAfterFilter);
        }
    }

    /// <summary>
    /// Diagnostics for runtime mask-aware constrained action-type selection in the student live path.
    ///
    /// Enabled = true means the pre-submit mask check was active for this step.
    /// MaskedOutActionTypeChoicesCount counts cells where the model's chosen action_type was
    /// explicitly masked out and the cell was treated as NoOp (safe fallback).
    /// PreMaskRaw/PostMask histograms reveal the gap between raw policy bias and submitted types.
    ///
    /// This does not replace authoritative runtime validation. It is a pre-submit helper only.
    /// </summary>
    public readonly struct StudentMaskAwareDiagnostics
    {
        public StudentMaskAwareDiagnostics(
            bool enabled,
            int maskedOutActionTypeChoicesCount,
            int fallbackToNoopCount,
            IReadOnlyDictionary<UnitActionType, int> preMaskRawHistogram,
            IReadOnlyDictionary<UnitActionType, int> postMaskHistogram)
        {
            Enabled = enabled;
            MaskedOutActionTypeChoicesCount = maskedOutActionTypeChoicesCount;
            FallbackToNoopCount = fallbackToNoopCount;
            PreMaskRawHistogram = preMaskRawHistogram ?? EmptyHistogram;
            PostMaskHistogram = postMaskHistogram ?? EmptyHistogram;
        }

        private static readonly IReadOnlyDictionary<UnitActionType, int> EmptyHistogram =
            new Dictionary<UnitActionType, int>();

        public bool Enabled { get; }
        public int MaskedOutActionTypeChoicesCount { get; }
        public int FallbackToNoopCount { get; }
        public IReadOnlyDictionary<UnitActionType, int> PreMaskRawHistogram { get; }
        public IReadOnlyDictionary<UnitActionType, int> PostMaskHistogram { get; }

        public static StudentMaskAwareDiagnostics Empty =>
            new StudentMaskAwareDiagnostics(false, 0, 0, null, null);
    }

    public readonly struct StudentBridgeRuntimeSnapshot
    {
        public StudentBridgeRuntimeSnapshot(
            bool serverStarted,
            bool serverShutdownClean,
            int decisionRequestsSent,
            int decisionRequestsSucceeded,
            int decisionRequestsFailed,
            int studentCommandsSubmitted,
            string lastError)
        {
            ServerStarted = serverStarted;
            ServerShutdownClean = serverShutdownClean;
            DecisionRequestsSent = decisionRequestsSent;
            DecisionRequestsSucceeded = decisionRequestsSucceeded;
            DecisionRequestsFailed = decisionRequestsFailed;
            StudentCommandsSubmitted = studentCommandsSubmitted;
            LastError = lastError ?? string.Empty;
        }

        public bool ServerStarted { get; }
        public bool ServerShutdownClean { get; }
        public int DecisionRequestsSent { get; }
        public int DecisionRequestsSucceeded { get; }
        public int DecisionRequestsFailed { get; }
        public int StudentCommandsSubmitted { get; }
        public string LastError { get; }
    }

    [DisallowMultipleComponent]
    public sealed class Week6StudentPolicyAdapter : MonoBehaviour
    {
        private const string ExpectedStudentCheckpointFileName = "student_bc_transfer_best.pt";

        [Serializable]
        private sealed class BridgeReadyEnvelope
        {
            public string status;
            public string checkpoint_path;
            public int checkpoint_epoch;
            public string checkpoint_model_variant;
            public string error;
        }

        [Serializable]
        private sealed class BridgeRequestEnvelope
        {
            public string command;
            public int request_id;
            public string observation_bin;
            public string output_json;
        }

        [Serializable]
        private sealed class BridgeResponseEnvelope
        {
            public string status;
            public int request_id;
            public string output_json;
            public string error;
        }

        [Serializable]
        private sealed class AdapterResult
        {
            public string status;
            public string error;
            public string checkpoint_path;
            public int checkpoint_epoch;
            public string checkpoint_model_variant;
            public int[] observation_shape;
            public string observation_dtype;
            public int observation_element_count;
            public string[] branch_order;
            public int[] branch_sizes;
            public string[] logits_keys;
            public int action_flat_size;
            public int[] action_flat;
        }

        [Header("Scene references")]
        [SerializeField] private GridManager _gridManager;
        [SerializeField] private UnitRegistry _unitRegistry;
        [SerializeField] private ResourceManager _resourceManager;
        [SerializeField] private MatchManager _matchManager;
        [SerializeField] private MatchBootstrap _matchBootstrap;

        [Header("Python bridge")]
        [SerializeField] private bool _verboseLogs;
        [SerializeField] private bool _validateObservationEachStep;
        [SerializeField] private int _serverStartupTimeoutMs = 15000;
        [SerializeField] private int _requestTimeoutMs = 5000;
        [SerializeField] private int _maxDecisionRequestsPerEpisode = 200;
        [SerializeField] private string _pythonExecutableRelativePath = ".venv/Scripts/python.exe";
        [SerializeField] private string _bridgeScriptRelativePath = "python/week6_student/student_inference_server.py";
        [SerializeField] private string _checkpointRelativePath = "python/week6_student/runs/day3_transfer_bc_main_20260423/student_bc_transfer_best.pt";
        [SerializeField] private string _artifactDirectoryRelativePath = "python/week6_student/tmp/day5_sanity";
        [SerializeField] private string _artifactFilePrefix = "day5_sanity";
        [SerializeField] private int _artifactRingSlots = 4;
        [SerializeField] private bool _cleanupTempArtifactsOnReset = true;
        [SerializeField] private string _device = "cpu";

        private readonly Dictionary<Owner, StudentPolicyExecutionReport> _lastReportByPlayer = new Dictionary<Owner, StudentPolicyExecutionReport>(2);

        private ObservationBuilder _observationBuilder;
        private MlPolicyPipelineFacade _policyPipeline;
        private Process _bridgeProcess;
        private StreamWriter _bridgeStdIn;
        private StreamReader _bridgeStdOut;
        private string _lastBridgeStdErr = string.Empty;
        private string _lastRuntimeError = string.Empty;
        private string _projectRoot = string.Empty;
        private int _requestId;
        private int _decisionIndex;
        private int _decisionRequestsSent;
        private int _decisionRequestsSucceeded;
        private int _decisionRequestsFailed;
        private int _studentCommandsSubmitted;
        private bool _serverStarted;
        private bool _serverShutdownClean;

        public void Initialize(
            GridManager gridManager,
            UnitRegistry unitRegistry,
            ResourceManager resourceManager,
            MatchManager matchManager,
            MatchBootstrap matchBootstrap = null)
        {
            _gridManager = gridManager;
            _unitRegistry = unitRegistry;
            _resourceManager = resourceManager;
            _matchManager = matchManager;
            _matchBootstrap = matchBootstrap;

            EnsurePipeline();
        }

        public void ResetEpisodeState()
        {
            _lastReportByPlayer.Clear();
            _decisionIndex = 0;
            _decisionRequestsSent = 0;
            _decisionRequestsSucceeded = 0;
            _decisionRequestsFailed = 0;
            _studentCommandsSubmitted = 0;
            _lastRuntimeError = string.Empty;
            _lastBridgeStdErr = string.Empty;
            _serverStarted = _bridgeProcess != null && !_bridgeProcess.HasExited;
            _serverShutdownClean = false;

            if (_cleanupTempArtifactsOnReset)
            {
                CleanupDedicatedTempArtifacts();
            }
        }

        public bool TryGetLastExecutionReport(Owner playerId, out StudentPolicyExecutionReport report)
        {
            return _lastReportByPlayer.TryGetValue(playerId, out report);
        }

        public StudentBridgeRuntimeSnapshot GetRuntimeSnapshot()
        {
            return new StudentBridgeRuntimeSnapshot(
                _serverStarted,
                _serverShutdownClean,
                _decisionRequestsSent,
                _decisionRequestsSucceeded,
                _decisionRequestsFailed,
                _studentCommandsSubmitted,
                _lastRuntimeError);
        }

        public string CheckpointRelativePath => _checkpointRelativePath;

            public bool ShutdownBridgeForSanity()
            {
                ShutdownBridge();
                return _serverShutdownClean;
            }

        internal StudentPolicyExecutionReport ExecuteDecision(Owner playerId, in RlLoopStepInput stepInput)
        {
            EnsurePipeline();

            if (_maxDecisionRequestsPerEpisode > 0 && _decisionRequestsSent >= _maxDecisionRequestsPerEpisode)
            {
                return RecordFailure(playerId, false, $"Decision request cap reached ({_maxDecisionRequestsPerEpisode}).");
            }

            _decisionRequestsSent++;

            if (!CanRun())
            {
                return RecordFailure(playerId, false, "Student policy pipeline is not ready.");
            }

            if (!EnsureBridgeStarted(out string bridgeError))
            {
                return RecordFailure(playerId, false, bridgeError);
            }

            bool canUseCanonical = stepInput.Perspective == playerId
                && stepInput.CanonicalObservation.SpatialObservation != null
                && stepInput.CanonicalMask != null;

            ObservationPackage observationPackage = canUseCanonical
                ? stepInput.CanonicalObservation
                : _policyPipeline.BuildObservationPackage(playerId, ObservationMode.UnityMvpTransfer);

            if (_validateObservationEachStep)
            {
                ObservationValidationResult validation = _observationBuilder.ValidateObservation(observationPackage.SpatialObservation);
                if (!validation.IsValid)
                {
                    return RecordFailure(
                        playerId,
                        canUseCanonical,
                        "Observation validation failed before student inference: " + validation);
                }
            }

            _decisionIndex++;
            string artifactDir = GetArtifactDirectory();
            int ringSlots = Mathf.Max(1, _artifactRingSlots);
            int slotIndex = (_decisionIndex - 1) % ringSlots;
            string stepStem = $"{_artifactFilePrefix}_{playerId.ToString().ToLowerInvariant()}_slot{slotIndex:D2}";
            string observationBinPath = Path.Combine(artifactDir, stepStem + "_observation.bin");
            string outputJsonPath = Path.Combine(artifactDir, stepStem + "_adapter.json");

            try
            {
                WriteFloat32Buffer(observationPackage.SpatialObservation, observationBinPath);

                var request = new BridgeRequestEnvelope
                {
                    command = "infer",
                    request_id = ++_requestId,
                    observation_bin = observationBinPath,
                    output_json = outputJsonPath,
                };

                _bridgeStdIn.WriteLine(JsonUtility.ToJson(request));
                _bridgeStdIn.Flush();

                if (!TryReadBridgeLine(_requestTimeoutMs, out string responseLine, out string readError))
                {
                    return RecordFailure(playerId, canUseCanonical, "Student bridge response timeout/error: " + readError);
                }

                if (string.IsNullOrWhiteSpace(responseLine))
                {
                    return RecordFailure(playerId, canUseCanonical, "Student bridge returned an empty response line.");
                }

                BridgeResponseEnvelope response = JsonUtility.FromJson<BridgeResponseEnvelope>(responseLine);
                if (response == null)
                {
                    return RecordFailure(playerId, canUseCanonical, "Cannot parse student bridge response.");
                }

                if (!string.Equals(response.status, "ok", StringComparison.Ordinal))
                {
                    return RecordFailure(
                        playerId,
                        canUseCanonical,
                        "Student bridge inference failed: " + response.error);
                }

                if (!File.Exists(response.output_json))
                {
                    return RecordFailure(
                        playerId,
                        canUseCanonical,
                        "Student bridge did not produce adapter JSON: " + response.output_json);
                }

                AdapterResult adapterResult = JsonUtility.FromJson<AdapterResult>(File.ReadAllText(response.output_json));
                if (adapterResult == null)
                {
                    return RecordFailure(playerId, canUseCanonical, "Cannot parse adapter JSON payload.");
                }

                if (!string.Equals(adapterResult.status, "ok", StringComparison.Ordinal))
                {
                    return RecordFailure(
                        playerId,
                        canUseCanonical,
                        "Student adapter payload is not ok: " + adapterResult.error);
                }

                if (!ValidateAdapterPayload(adapterResult, out string payloadError))
                {
                    return RecordFailure(playerId, canUseCanonical, payloadError);
                }

                ActionMaskSet mask = canUseCanonical
                    ? stepInput.CanonicalMask
                    : _policyPipeline.BuildTransferCompatibleMask(playerId);

                StudentLiveFilterDiagnostics filterDiagnostics = BuildStudentFilterDiagnostics(playerId, mask, out List<int> eligibleCellIndices);

                PolicyExecutionReport execution = _policyPipeline.ExecuteTransferCompatibleMaskAware(
                    adapterResult.action_flat,
                    playerId,
                    eligibleCellIndices,
                    mask,
                    out int maskedOutChoicesCount,
                    out int fallbackToNoopCount,
                    out Dictionary<UnitActionType, int> preMaskHistogram,
                    out Dictionary<UnitActionType, int> postMaskHistogram,
                    "week6-day5-student-live");

                var maskAwareDiagnostics = new StudentMaskAwareDiagnostics(
                    enabled: true,
                    maskedOutActionTypeChoicesCount: maskedOutChoicesCount,
                    fallbackToNoopCount: fallbackToNoopCount,
                    preMaskRawHistogram: preMaskHistogram,
                    postMaskHistogram: postMaskHistogram);

                int commandsBuiltAfterFilter = execution.DecodedActions.Count;
                int commandsSubmittedAfterFilter = execution.AcceptedCount + execution.RejectedCount;
                int wrongOwnerRejectionsAfterFilter = CountWrongOwnerRejections(execution.RejectionReasons);
                filterDiagnostics = filterDiagnostics.WithSubmissionOutcome(
                    commandsBuiltAfterFilter,
                    commandsSubmittedAfterFilter,
                    wrongOwnerRejectionsAfterFilter);

                StudentPolicyExecutionReport report = new StudentPolicyExecutionReport(
                    playerId,
                    bridgeSucceeded: true,
                    usedCanonicalStepInput: canUseCanonical,
                    decodedActions: execution.DecodedActions,
                    acceptedCount: execution.AcceptedCount,
                    rejectedCount: execution.RejectedCount,
                    rejectionReasons: execution.RejectionReasons,
                    filterDiagnostics: filterDiagnostics,
                    maskAwareDiagnostics: maskAwareDiagnostics,
                    error: string.Empty);

                _decisionRequestsSucceeded++;
                _studentCommandsSubmitted += report.AcceptedCount + report.RejectedCount;
                _lastRuntimeError = string.Empty;

                if (_verboseLogs)
                {
                    Debug.Log(
                        $"[Week6StudentPolicyAdapter] player={playerId}, canonical={canUseCanonical}, " +
                        $"decoded={report.DecodedActionCount}, accepted={report.AcceptedCount}, rejected={report.RejectedCount}, " +
                        $"eligibleCells={report.FilterDiagnostics.EligibleOwnActorCells}, builtAfterFilter={report.FilterDiagnostics.CommandsBuiltAfterFilter}, " +
                        $"wrongOwnerAfterFilter={report.FilterDiagnostics.WrongOwnerRejectionsAfterFilter}, " +
                        $"maskedOut={report.MaskAwareDiagnostics.MaskedOutActionTypeChoicesCount}, fallbackNoop={report.MaskAwareDiagnostics.FallbackToNoopCount}");
                }

                _lastReportByPlayer[playerId] = report;
                return report;
            }
            catch (Exception ex)
            {
                return RecordFailure(playerId, canUseCanonical, "Student live inference failed: " + ex.Message);
            }
        }

        private void OnDisable()
        {
            ShutdownBridge();
        }

        private void OnDestroy()
        {
            ShutdownBridge();
        }

        private StudentPolicyExecutionReport BuildFailureReport(Owner playerId, bool usedCanonicalStepInput, string error)
        {
            string finalError = error ?? string.Empty;
            if (!string.IsNullOrWhiteSpace(_lastBridgeStdErr))
            {
                finalError = finalError + " | stderr=" + _lastBridgeStdErr;
            }

            return new StudentPolicyExecutionReport(
                playerId,
                bridgeSucceeded: false,
                usedCanonicalStepInput: usedCanonicalStepInput,
                decodedActions: Array.Empty<AgentAction>(),
                acceptedCount: 0,
                rejectedCount: 0,
                rejectionReasons: Array.Empty<string>(),
                filterDiagnostics: StudentLiveFilterDiagnostics.Empty,
                maskAwareDiagnostics: StudentMaskAwareDiagnostics.Empty,
                error: finalError);
        }

            private StudentPolicyExecutionReport RecordFailure(Owner playerId, bool usedCanonicalStepInput, string error)
            {
                _decisionRequestsFailed++;
                _lastRuntimeError = error ?? string.Empty;
                StudentPolicyExecutionReport report = BuildFailureReport(playerId, usedCanonicalStepInput, error);
                _lastReportByPlayer[playerId] = report;
                return report;
            }

        private bool CanRun()
        {
            return _observationBuilder != null && _policyPipeline != null;
        }

        private void EnsurePipeline()
        {
            if (_gridManager == null)
            {
                _gridManager = GridManager.Instance;
            }

            if (_unitRegistry == null)
            {
                _unitRegistry = UnitRegistry.Instance;
            }

            if (_resourceManager == null)
            {
                _resourceManager = ResourceManager.Instance;
            }

            if (_matchManager == null)
            {
                _matchManager = MatchManager.Instance;
            }

            if (_matchBootstrap == null)
            {
                _matchBootstrap = MatchBootstrap.Instance;
            }

            if (_observationBuilder == null && _gridManager != null && _unitRegistry != null)
            {
                _observationBuilder = new ObservationBuilder(_gridManager, _unitRegistry, _resourceManager);
            }

            if (_policyPipeline == null && _gridManager != null && _unitRegistry != null && _matchManager != null)
            {
                _policyPipeline = new MlPolicyPipelineFacade(
                    _gridManager,
                    _unitRegistry,
                    _resourceManager,
                    _matchManager,
                    _matchBootstrap);
            }

            if (string.IsNullOrWhiteSpace(_projectRoot))
            {
                _projectRoot = ResolveProjectRoot();
            }
        }

        private bool EnsureBridgeStarted(out string error)
        {
            error = string.Empty;

            if (_bridgeProcess != null && !_bridgeProcess.HasExited && _bridgeStdIn != null && _bridgeStdOut != null)
            {
                return true;
            }

            ShutdownBridge();
            EnsurePipeline();

            if (string.IsNullOrWhiteSpace(_projectRoot))
            {
                error = "Cannot resolve Unity project root for student bridge.";
                return false;
            }

            string pythonPath = Path.GetFullPath(Path.Combine(_projectRoot, _pythonExecutableRelativePath));
            string bridgeScriptPath = Path.GetFullPath(Path.Combine(_projectRoot, _bridgeScriptRelativePath));
            string checkpointPath = Path.GetFullPath(Path.Combine(_projectRoot, _checkpointRelativePath));

            if (!File.Exists(pythonPath))
            {
                error = "Python executable not found: " + pythonPath;
                return false;
            }

            if (!File.Exists(bridgeScriptPath))
            {
                error = "Student bridge script not found: " + bridgeScriptPath;
                return false;
            }

            if (!File.Exists(checkpointPath))
            {
                error = "Student checkpoint not found: " + checkpointPath;
                return false;
            }

            if (!string.Equals(Path.GetFileName(checkpointPath), ExpectedStudentCheckpointFileName, StringComparison.OrdinalIgnoreCase))
            {
                error = "Unexpected checkpoint file name for Day 5 bridge: " + checkpointPath;
                return false;
            }

            try
            {
                string arguments =
                    Quote(bridgeScriptPath) + " " +
                    "--checkpoint " + Quote(checkpointPath) + " " +
                    "--device " + Quote(_device);

                var startInfo = new ProcessStartInfo
                {
                    FileName = pythonPath,
                    Arguments = arguments,
                    WorkingDirectory = _projectRoot,
                    UseShellExecute = false,
                    RedirectStandardInput = true,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true,
                };

                _bridgeProcess = new Process { StartInfo = startInfo, EnableRaisingEvents = true };
                _bridgeProcess.ErrorDataReceived += OnBridgeErrorDataReceived;
                _bridgeProcess.Start();
                _bridgeProcess.BeginErrorReadLine();

                _bridgeStdIn = _bridgeProcess.StandardInput;
                _bridgeStdOut = _bridgeProcess.StandardOutput;

                if (!TryReadBridgeLine(_serverStartupTimeoutMs, out string readyLine, out string readyError))
                {
                    error = "Student bridge did not emit ready handshake: " + readyError;
                    ShutdownBridge();
                    return false;
                }

                if (string.IsNullOrWhiteSpace(readyLine))
                {
                    error = "Student bridge did not emit ready handshake.";
                    ShutdownBridge();
                    return false;
                }

                BridgeReadyEnvelope ready = JsonUtility.FromJson<BridgeReadyEnvelope>(readyLine);
                if (ready == null || !string.Equals(ready.status, "ready", StringComparison.Ordinal))
                {
                    error = "Student bridge ready handshake failed: " + readyLine;
                    ShutdownBridge();
                    return false;
                }

                if (_verboseLogs)
                {
                    Debug.Log(
                        $"[Week6StudentPolicyAdapter] Student bridge ready. checkpoint={ready.checkpoint_path}, " +
                        $"epoch={ready.checkpoint_epoch}, model={ready.checkpoint_model_variant}");
                }

                _serverStarted = true;
                _serverShutdownClean = false;

                return true;
            }
            catch (Exception ex)
            {
                error = "Failed to start student bridge: " + ex.Message;
                ShutdownBridge();
                return false;
            }
        }

        private void OnBridgeErrorDataReceived(object sender, DataReceivedEventArgs args)
        {
            if (!string.IsNullOrWhiteSpace(args.Data))
            {
                _lastBridgeStdErr = args.Data;
                if (_verboseLogs)
                {
                    Debug.LogWarning("[Week6StudentPolicyAdapter] bridge stderr: " + args.Data);
                }
            }
        }

        private void ShutdownBridge()
        {
            bool shutdownAcknowledged = false;

            try
            {
                if (_bridgeProcess != null && !_bridgeProcess.HasExited && _bridgeStdIn != null)
                {
                    var request = new BridgeRequestEnvelope
                    {
                        command = "shutdown",
                        request_id = 0,
                    };
                    _bridgeStdIn.WriteLine(JsonUtility.ToJson(request));
                    _bridgeStdIn.Flush();

                    if (TryReadBridgeLine(Mathf.Max(1000, _requestTimeoutMs), out string shutdownLine, out _)
                        && !string.IsNullOrWhiteSpace(shutdownLine)
                        && shutdownLine.Contains("\"status\":\"ok\"", StringComparison.Ordinal)
                        && shutdownLine.Contains("shutdown", StringComparison.OrdinalIgnoreCase))
                    {
                        shutdownAcknowledged = true;
                    }
                }
            }
            catch
            {
                // Best-effort shutdown only.
            }

            if (_bridgeProcess != null)
            {
                try
                {
                    if (!_bridgeProcess.HasExited)
                    {
                        _bridgeProcess.Kill();
                    }
                }
                catch
                {
                    // Best-effort shutdown only.
                }

                _bridgeProcess.ErrorDataReceived -= OnBridgeErrorDataReceived;
                _bridgeProcess.Dispose();
            }

            _bridgeProcess = null;
            _bridgeStdIn = null;
            _bridgeStdOut = null;
            _serverStarted = false;
            _serverShutdownClean = shutdownAcknowledged;
        }

        private string GetArtifactDirectory()
        {
            string directory = Path.GetFullPath(Path.Combine(_projectRoot, _artifactDirectoryRelativePath));
            Directory.CreateDirectory(directory);
            return directory;
        }

        private static string ResolveProjectRoot()
        {
            string assetsPath = Application.dataPath;
            if (string.IsNullOrWhiteSpace(assetsPath))
            {
                return string.Empty;
            }

            DirectoryInfo assetsDir = new DirectoryInfo(assetsPath);
            return assetsDir.Parent != null ? assetsDir.Parent.FullName : string.Empty;
        }

        private static string Quote(string value)
        {
            return "\"" + value + "\"";
        }

        private bool TryReadBridgeLine(int timeoutMs, out string line, out string error)
        {
            line = string.Empty;
            error = string.Empty;

            if (_bridgeStdOut == null)
            {
                error = "Bridge stdout is not initialized.";
                return false;
            }

            try
            {
                Task<string> readTask = _bridgeStdOut.ReadLineAsync();
                int boundedTimeout = Mathf.Max(1, timeoutMs);
                if (!readTask.Wait(boundedTimeout))
                {
                    error = $"timeout after {boundedTimeout}ms";
                    return false;
                }

                line = readTask.Result;
                return true;
            }
            catch (Exception ex)
            {
                error = ex.Message;
                return false;
            }
        }

        private void CleanupDedicatedTempArtifacts()
        {
            if (string.IsNullOrWhiteSpace(_projectRoot))
            {
                return;
            }

            string dedicatedRelative = "python/week6_student/tmp/day5_sanity";
            string dedicatedPath = Path.GetFullPath(Path.Combine(_projectRoot, dedicatedRelative));
            string runtimePath = Path.GetFullPath(Path.Combine(_projectRoot, _artifactDirectoryRelativePath));
            if (!string.Equals(dedicatedPath, runtimePath, StringComparison.OrdinalIgnoreCase))
            {
                return;
            }

            if (!Directory.Exists(runtimePath))
            {
                return;
            }

            string prefix = string.IsNullOrWhiteSpace(_artifactFilePrefix) ? "day5_sanity" : _artifactFilePrefix;
            string searchPattern = prefix + "*";

            foreach (string file in Directory.EnumerateFiles(runtimePath, searchPattern, SearchOption.TopDirectoryOnly))
            {
                try
                {
                    File.Delete(file);
                }
                catch (Exception ex)
                {
                    if (_verboseLogs)
                    {
                        Debug.LogWarning("[Week6StudentPolicyAdapter] Failed to cleanup temp artifact: " + file + " | " + ex.Message);
                    }
                }
            }
        }

        private static void WriteFloat32Buffer(float[] values, string path)
        {
            using var stream = new FileStream(path, FileMode.Create, FileAccess.Write, FileShare.None);
            using var writer = new BinaryWriter(stream);
            for (int i = 0; i < values.Length; i++)
            {
                writer.Write(values[i]);
            }
        }

        private static bool ValidateAdapterPayload(AdapterResult adapter, out string error)
        {
            error = string.Empty;

            if (adapter.observation_shape == null || adapter.observation_shape.Length != 3)
            {
                error = "Adapter did not return observation_shape [H,W,C].";
                return false;
            }

            if (adapter.observation_shape[0] != ObservationContract.GridH
                || adapter.observation_shape[1] != ObservationContract.GridW
                || adapter.observation_shape[2] != ObservationContract.ChannelsPerCell)
            {
                error =
                    "Observation shape mismatch from adapter. " +
                    $"Expected [{ObservationContract.GridH},{ObservationContract.GridW},{ObservationContract.ChannelsPerCell}], " +
                    $"got [{adapter.observation_shape[0]},{adapter.observation_shape[1]},{adapter.observation_shape[2]}]";
                return false;
            }

            if (!string.Equals(adapter.observation_dtype, "float32", StringComparison.OrdinalIgnoreCase))
            {
                error = "Observation dtype mismatch from adapter. Expected float32, got " + adapter.observation_dtype;
                return false;
            }

            if (adapter.action_flat == null || adapter.action_flat_size != ActionContract.TotalActionFlatSize)
            {
                error =
                    "Action flat size mismatch from adapter. " +
                    $"Expected {ActionContract.TotalActionFlatSize}, got {adapter.action_flat_size}";
                return false;
            }

            return true;
        }

        private StudentLiveFilterDiagnostics BuildStudentFilterDiagnostics(
            Owner playerId,
            ActionMaskSet mask,
            out List<int> eligibleCellIndices)
        {
            eligibleCellIndices = new List<int>(mask != null ? Mathf.Max(mask.AvailableActorCount, 0) : 0);

            int candidateCellsTotal = ActionContract.TotalCells;
            int filteredOutNeutralCells = 0;
            int filteredOutEnemyCells = 0;
            int filteredOutNoncontrollableCells = 0;
            int eligibleOwnActorCells = 0;

            for (int cellIndex = 0; cellIndex < ActionContract.TotalCells; cellIndex++)
            {
                GridPosition position = GridPosition.FromFlatIndex(cellIndex);
                UnitRuntime unit = _gridManager.GetOccupant(position);

                if (unit == null || !unit.IsAlive || unit.Type == UnitType.Resource)
                {
                    filteredOutNoncontrollableCells++;
                    continue;
                }

                if (unit.Owner == Owner.Neutral)
                {
                    filteredOutNeutralCells++;
                    continue;
                }

                if (unit.Owner != playerId)
                {
                    filteredOutEnemyCells++;
                    continue;
                }

                bool eligibleByMask = mask != null
                    && mask.ActorCellMask != null
                    && cellIndex >= 0
                    && cellIndex < mask.ActorCellMask.Length
                    && mask.ActorCellMask[cellIndex];

                if (!eligibleByMask)
                {
                    filteredOutNoncontrollableCells++;
                    continue;
                }

                eligibleOwnActorCells++;
                eligibleCellIndices.Add(cellIndex);
            }

            return new StudentLiveFilterDiagnostics(
                candidateCellsTotal,
                eligibleOwnActorCells,
                filteredOutNeutralCells,
                filteredOutEnemyCells,
                filteredOutNoncontrollableCells,
                0,
                0,
                0);
        }

        private static int CountWrongOwnerRejections(IReadOnlyList<string> rejectionReasons)
        {
            if (rejectionReasons == null || rejectionReasons.Count == 0)
            {
                return 0;
            }

            int count = 0;
            for (int i = 0; i < rejectionReasons.Count; i++)
            {
                string reason = rejectionReasons[i];
                if (string.IsNullOrWhiteSpace(reason))
                {
                    continue;
                }

                if (reason.IndexOf("belongs to", StringComparison.OrdinalIgnoreCase) >= 0
                    || reason.IndexOf("not Player", StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    count++;
                }
            }

            return count;
        }
    }
}