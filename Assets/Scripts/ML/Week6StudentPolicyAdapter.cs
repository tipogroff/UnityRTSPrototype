using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text.RegularExpressions;
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
        public readonly struct ActorLegalMaskTelemetry
        {
            public ActorLegalMaskTelemetry(bool[] actionTypeMask, bool[] moveDirMask)
            {
                ActionTypeMask = actionTypeMask ?? Array.Empty<bool>();
                MoveDirMask = moveDirMask ?? Array.Empty<bool>();
            }

            public bool[] ActionTypeMask { get; }
            public bool[] MoveDirMask { get; }
        }

        public StudentMaskAwareDiagnostics(
            bool enabled,
            int maskedOutActionTypeChoicesCount,
            int fallbackToNoopCount,
            IReadOnlyDictionary<UnitActionType, int> preMaskRawHistogram,
            IReadOnlyDictionary<UnitActionType, int> postMaskHistogram,
            IReadOnlyDictionary<int, ActionDecoder.MaskAwareCellTelemetry> cellTelemetryByFlat,
            IReadOnlyDictionary<int, ActorLegalMaskTelemetry> legalMaskByFlat)
        {
            Enabled = enabled;
            MaskedOutActionTypeChoicesCount = maskedOutActionTypeChoicesCount;
            FallbackToNoopCount = fallbackToNoopCount;
            PreMaskRawHistogram = preMaskRawHistogram ?? EmptyHistogram;
            PostMaskHistogram = postMaskHistogram ?? EmptyHistogram;
            CellTelemetryByFlat = cellTelemetryByFlat ?? EmptyCellTelemetry;
            LegalMaskByFlat = legalMaskByFlat ?? EmptyLegalMask;
        }

        private static readonly IReadOnlyDictionary<UnitActionType, int> EmptyHistogram =
            new Dictionary<UnitActionType, int>();
        private static readonly IReadOnlyDictionary<int, ActionDecoder.MaskAwareCellTelemetry> EmptyCellTelemetry =
            new Dictionary<int, ActionDecoder.MaskAwareCellTelemetry>();
        private static readonly IReadOnlyDictionary<int, ActorLegalMaskTelemetry> EmptyLegalMask =
            new Dictionary<int, ActorLegalMaskTelemetry>();

        public bool Enabled { get; }
        public int MaskedOutActionTypeChoicesCount { get; }
        public int FallbackToNoopCount { get; }
        public IReadOnlyDictionary<UnitActionType, int> PreMaskRawHistogram { get; }
        public IReadOnlyDictionary<UnitActionType, int> PostMaskHistogram { get; }
        public IReadOnlyDictionary<int, ActionDecoder.MaskAwareCellTelemetry> CellTelemetryByFlat { get; }
        public IReadOnlyDictionary<int, ActorLegalMaskTelemetry> LegalMaskByFlat { get; }

        public static StudentMaskAwareDiagnostics Empty =>
            new StudentMaskAwareDiagnostics(false, 0, 0, null, null, null, null);
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

    [Serializable]
    public sealed class StudentInferenceDiagnosticsSnapshot
    {
        public bool adapter_invoked;
        public int inference_request_count;
        public string last_inference_call_utc;
        public string checkpoint_path_used_at_inference;
        public int[] observation_shape_sent;
        public int observation_element_count;
        public int candidate_actor_cells_submitted;
        public string python_request_status;
        public string python_response_status;
        public string[] raw_bridge_response_keys;
        public string[] raw_adapter_response_keys;
        public bool parsed_logits_available;
        public bool parsed_action_type_probabilities_available;
        public bool parsed_action_type_top3_available;
        public bool adapter_artifact_created;
        public string adapter_artifact_missing_reason;
        public string last_output_json_path;
        public string stage10d12r_capture_path;
        public string stage10d12r_capture_status;
        public int stage10d12r_capture_json_length;
        public int stage10d12r_capture_cell_count;

        public StudentInferenceDiagnosticsSnapshot Clone()
        {
            return new StudentInferenceDiagnosticsSnapshot
            {
                adapter_invoked = adapter_invoked,
                inference_request_count = inference_request_count,
                last_inference_call_utc = last_inference_call_utc,
                checkpoint_path_used_at_inference = checkpoint_path_used_at_inference,
                observation_shape_sent = observation_shape_sent != null ? (int[])observation_shape_sent.Clone() : Array.Empty<int>(),
                observation_element_count = observation_element_count,
                candidate_actor_cells_submitted = candidate_actor_cells_submitted,
                python_request_status = python_request_status ?? string.Empty,
                python_response_status = python_response_status ?? string.Empty,
                raw_bridge_response_keys = raw_bridge_response_keys != null ? (string[])raw_bridge_response_keys.Clone() : Array.Empty<string>(),
                raw_adapter_response_keys = raw_adapter_response_keys != null ? (string[])raw_adapter_response_keys.Clone() : Array.Empty<string>(),
                parsed_logits_available = parsed_logits_available,
                parsed_action_type_probabilities_available = parsed_action_type_probabilities_available,
                parsed_action_type_top3_available = parsed_action_type_top3_available,
                adapter_artifact_created = adapter_artifact_created,
                adapter_artifact_missing_reason = adapter_artifact_missing_reason ?? string.Empty,
                last_output_json_path = last_output_json_path ?? string.Empty,
                stage10d12r_capture_path = stage10d12r_capture_path ?? string.Empty,
                stage10d12r_capture_status = stage10d12r_capture_status ?? string.Empty,
                stage10d12r_capture_json_length = stage10d12r_capture_json_length,
                stage10d12r_capture_cell_count = stage10d12r_capture_cell_count,
            };
        }

        public void ResetForEpisode()
        {
            adapter_invoked = false;
            inference_request_count = 0;
            last_inference_call_utc = string.Empty;
            checkpoint_path_used_at_inference = string.Empty;
            observation_shape_sent = Array.Empty<int>();
            observation_element_count = 0;
            candidate_actor_cells_submitted = 0;
            python_request_status = "idle";
            python_response_status = string.Empty;
            raw_bridge_response_keys = Array.Empty<string>();
            raw_adapter_response_keys = Array.Empty<string>();
            parsed_logits_available = false;
            parsed_action_type_probabilities_available = false;
            parsed_action_type_top3_available = false;
            adapter_artifact_created = false;
            adapter_artifact_missing_reason = string.Empty;
            last_output_json_path = string.Empty;
            stage10d12r_capture_path = string.Empty;
            stage10d12r_capture_status = "idle";
            stage10d12r_capture_json_length = 0;
            stage10d12r_capture_cell_count = 0;
        }
    }

    [DisallowMultipleComponent]
    public sealed class Week6StudentPolicyAdapter : MonoBehaviour
    {
        private const string CanonicalStage6A2CheckpointRelativePath =
            "python/week6_student/runs/legacy032_v2_bc_short_stage6a2/legacy032_v2_bc_short_stage6a2_smoke_checkpoint.pt";
        // Stage6B2: bind to full BC checkpoint (Stage6B1 best, epoch 5, val_loss 1.8362, model_variant=transfer)
        private const string CanonicalStage6B1CheckpointRelativePath =
            "python/week6_student/runs/legacy032_v2_full_bc_stage6b1/legacy032_v2_full_bc_stage6b1_best.pt";
        private const string ExpectedActionContractVersion = "v2_gridnet_compatible";

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
            public string controlled_player;
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
            public string action_contract_version;
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

        [Serializable]
        private sealed class Stage10D12RCellCapture
        {
            public int flat_index;
            public int x;
            public int y;
            public string logical_label;
            public float[] raw_channel_vector;
            public string decoded_owner;
            public string decoded_unit;
            public string decoded_current_action;
        }

        [Serializable]
        private sealed class Stage10D12RFullRawObservationCapture
        {
            public string generated_at_utc;
            public string stage;
            public string capture_type;
            public int step_index;
            public string controlled_player;
            public string capture_point;
            public int[] tensor_shape;
            public int[] tensor_shape_flat;
            public string flatten_order;
            public string[] channel_names;
            public int channel_count;
            public int cell_count;
            public Stage10D12RCellCapture[] cells;
        }

        [ContextMenu("Run Week6 Adapter Contract Validation Smoke")]
        private void RunAdapterContractValidationSmoke()
        {
            bool passed = RunAdapterContractValidationSmokeForEvidence(out string details);
            Debug.Log(passed
                ? "[Week6StudentPolicyAdapter] Adapter contract validation smoke PASSED: " + details
                : "[Week6StudentPolicyAdapter] Adapter contract validation smoke FAILED: " + details);
        }

        public bool RunAdapterContractValidationSmokeForEvidence(out string details)
        {
            string[] expectedBranchOrder = BuildExpectedBranchOrder();
            int[] expectedBranchSizes = BuildExpectedBranchSizes();

            bool branchShapeMatchesV2 = MatchesArray(expectedBranchSizes, new[] { 6, 4, 4, 4, 4, 7, 49 });
            bool flatSizeMatchesV2 = ActionContract.TotalActionFlatSize == 44928;
            bool contractVersionMatches = string.Equals(ExpectedActionContractVersion, "v2_gridnet_compatible", StringComparison.Ordinal);

            var v2Payload = new AdapterResult
            {
                status = "ok",
                action_contract_version = ExpectedActionContractVersion,
                observation_shape = new[] { ObservationContract.GridH, ObservationContract.GridW, ObservationContract.ChannelsPerCell },
                observation_dtype = "float32",
                branch_order = expectedBranchOrder,
                branch_sizes = expectedBranchSizes,
                action_flat_size = ActionContract.TotalActionFlatSize,
                action_flat = new int[ActionContract.TotalActionFlatSize],
            };

            bool v2Accepted = ValidateAdapterPayload(v2Payload, out string v2Error);

            var v1Payload = new AdapterResult
            {
                status = "ok",
                action_contract_version = "v1_transfer_compatible",
                observation_shape = new[] { ObservationContract.GridH, ObservationContract.GridW, ObservationContract.ChannelsPerCell },
                observation_dtype = "float32",
                branch_order = expectedBranchOrder,
                branch_sizes = new[] { 6, 4, 4, 4, 4, 4, 9 },
                action_flat_size = 20160,
                action_flat = new int[20160],
            };

            bool v1Accepted = ValidateAdapterPayload(v1Payload, out string v1Error);
            bool v1RejectedWithExpectedMessage = !v1Accepted
                && string.Equals(v1Error, "v1 action contract artifact is incompatible with Unity v2 runtime", StringComparison.Ordinal);

            bool passed = v2Accepted
                          && v1RejectedWithExpectedMessage
                          && branchShapeMatchesV2
                          && flatSizeMatchesV2
                          && contractVersionMatches;

            details =
                $"v2Accepted={v2Accepted}, " +
                $"v2Error={(string.IsNullOrWhiteSpace(v2Error) ? "<none>" : v2Error)}, " +
                $"v1RejectedWithExpectedMessage={v1RejectedWithExpectedMessage}, " +
                $"v1Error={(string.IsNullOrWhiteSpace(v1Error) ? "<none>" : v1Error)}, " +
                $"branchSizesV2={branchShapeMatchesV2}, actionFlat44928={flatSizeMatchesV2}, contractVersion={contractVersionMatches}";

            Debug.Log(v2Accepted
                ? "[Week6StudentPolicyAdapter] ✓ v2 manifest payload accepted"
                : "[Week6StudentPolicyAdapter] ✗ v2 manifest payload rejected: " + v2Error);
            Debug.Log(v1RejectedWithExpectedMessage
                ? "[Week6StudentPolicyAdapter] ✓ v1 manifest payload rejected: " + v1Error
                : "[Week6StudentPolicyAdapter] ✗ v1 manifest payload check failed");

            return passed;
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
        [SerializeField] private string _checkpointRelativePath = CanonicalStage6B1CheckpointRelativePath;
        [SerializeField] private bool _enableLegalActionMaskForSelection = false;
        [SerializeField] private bool _enableDynamicOccupancyMoveMaskEnrichment = true;
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
        private readonly StudentInferenceDiagnosticsSnapshot _inferenceDiagnostics = new StudentInferenceDiagnosticsSnapshot();

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
            _inferenceDiagnostics.ResetForEpisode();

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

            public StudentInferenceDiagnosticsSnapshot GetInferenceDiagnosticsSnapshot()
            {
                return _inferenceDiagnostics.Clone();
            }

        public string CheckpointRelativePath => _checkpointRelativePath;
        public bool EnableLegalActionMaskForSelection => _enableLegalActionMaskForSelection;

            public bool ShutdownBridgeForSanity()
            {
                ShutdownBridge();
                return _serverShutdownClean;
            }

        internal StudentPolicyExecutionReport ExecuteDecision(Owner playerId, in RlLoopStepInput stepInput)
        {
            EnsurePipeline();

            _inferenceDiagnostics.adapter_invoked = true;
            _inferenceDiagnostics.inference_request_count++;
            _inferenceDiagnostics.last_inference_call_utc = DateTime.UtcNow.ToString("O");
            _inferenceDiagnostics.checkpoint_path_used_at_inference = _checkpointRelativePath ?? string.Empty;
            _inferenceDiagnostics.python_request_status = "initializing";
            _inferenceDiagnostics.python_response_status = string.Empty;
            _inferenceDiagnostics.raw_bridge_response_keys = Array.Empty<string>();
            _inferenceDiagnostics.raw_adapter_response_keys = Array.Empty<string>();
            _inferenceDiagnostics.parsed_logits_available = false;
            _inferenceDiagnostics.parsed_action_type_probabilities_available = false;
            _inferenceDiagnostics.parsed_action_type_top3_available = false;
            _inferenceDiagnostics.adapter_artifact_created = false;
            _inferenceDiagnostics.adapter_artifact_missing_reason = string.Empty;

            if (_maxDecisionRequestsPerEpisode > 0 && _decisionRequestsSent >= _maxDecisionRequestsPerEpisode)
            {
                _inferenceDiagnostics.python_request_status = "skipped_decision_cap";
                _inferenceDiagnostics.adapter_artifact_missing_reason = "decision_request_cap_reached";
                return RecordFailure(playerId, false, $"Decision request cap reached ({_maxDecisionRequestsPerEpisode}).");
            }

            _decisionRequestsSent++;

            if (!CanRun())
            {
                _inferenceDiagnostics.python_request_status = "pipeline_not_ready";
                _inferenceDiagnostics.adapter_artifact_missing_reason = "student_policy_pipeline_not_ready";
                return RecordFailure(playerId, false, "Student policy pipeline is not ready.");
            }

            if (!EnsureBridgeStarted(out string bridgeError))
            {
                _inferenceDiagnostics.python_request_status = "bridge_start_failed";
                _inferenceDiagnostics.adapter_artifact_missing_reason = "bridge_start_failed";
                return RecordFailure(playerId, false, bridgeError);
            }

            bool canUseCanonical = stepInput.Perspective == playerId
                && stepInput.CanonicalObservation.SpatialObservation != null
                && stepInput.CanonicalMask != null;

            ObservationPackage observationPackage = canUseCanonical
                ? stepInput.CanonicalObservation
                : _policyPipeline.BuildObservationPackage(playerId, ObservationMode.UnityMvpTransfer);

            _inferenceDiagnostics.observation_shape_sent = new[]
            {
                ObservationContract.GridH,
                ObservationContract.GridW,
                ObservationContract.ChannelsPerCell,
            };
            _inferenceDiagnostics.observation_element_count = observationPackage.SpatialObservation != null
                ? observationPackage.SpatialObservation.Length
                : 0;

            if (_validateObservationEachStep)
            {
                ObservationValidationResult validation = _observationBuilder.ValidateObservation(observationPackage.SpatialObservation);
                if (!validation.IsValid)
                {
                    _inferenceDiagnostics.python_request_status = "observation_validation_failed";
                    _inferenceDiagnostics.adapter_artifact_missing_reason = "observation_validation_failed";
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
            _inferenceDiagnostics.last_output_json_path = outputJsonPath;

            try
            {
                WriteFloat32Buffer(observationPackage.SpatialObservation, observationBinPath);

                // Stage10D.12R: Capture full raw runtime observation tensor for diagnostics.
                // Capture point must remain before bridge request send.
                string rawTensorJsonPath = Path.Combine(artifactDir, $"stage10d12r_full_raw_runtime_observation_step{_decisionIndex:D4}.json");
                CaptureFullRawObservationDiagnostic(
                    observationPackage.SpatialObservation,
                    playerId,
                    _decisionIndex,
                    rawTensorJsonPath);

                var request = new BridgeRequestEnvelope
                {
                    command = "infer",
                    request_id = ++_requestId,
                    observation_bin = observationBinPath,
                    output_json = outputJsonPath,
                    controlled_player = playerId.ToString(),
                };

                _inferenceDiagnostics.python_request_status = "request_sent";

                _bridgeStdIn.WriteLine(JsonUtility.ToJson(request));
                _bridgeStdIn.Flush();

                if (!TryReadBridgeLine(_requestTimeoutMs, out string responseLine, out string readError))
                {
                    _inferenceDiagnostics.python_response_status = "response_timeout_or_error";
                    _inferenceDiagnostics.adapter_artifact_missing_reason = "bridge_response_timeout_or_error";
                    return RecordFailure(playerId, canUseCanonical, "Student bridge response timeout/error: " + readError);
                }

                if (string.IsNullOrWhiteSpace(responseLine))
                {
                    _inferenceDiagnostics.python_response_status = "empty_response_line";
                    _inferenceDiagnostics.adapter_artifact_missing_reason = "bridge_empty_response_line";
                    return RecordFailure(playerId, canUseCanonical, "Student bridge returned an empty response line.");
                }

                _inferenceDiagnostics.raw_bridge_response_keys = ExtractTopLevelJsonKeys(responseLine);

                BridgeResponseEnvelope response = JsonUtility.FromJson<BridgeResponseEnvelope>(responseLine);
                if (response == null)
                {
                    _inferenceDiagnostics.python_response_status = "response_parse_failed";
                    _inferenceDiagnostics.adapter_artifact_missing_reason = "bridge_response_parse_failed";
                    return RecordFailure(playerId, canUseCanonical, "Cannot parse student bridge response.");
                }

                _inferenceDiagnostics.python_response_status = string.IsNullOrWhiteSpace(response.status)
                    ? "missing_status"
                    : response.status;

                if (!string.Equals(response.status, "ok", StringComparison.Ordinal))
                {
                    _inferenceDiagnostics.adapter_artifact_missing_reason = "bridge_inference_failed";
                    return RecordFailure(
                        playerId,
                        canUseCanonical,
                        "Student bridge inference failed: " + response.error);
                }

                if (!File.Exists(response.output_json))
                {
                    _inferenceDiagnostics.adapter_artifact_missing_reason = "adapter_json_not_written";
                    return RecordFailure(
                        playerId,
                        canUseCanonical,
                        "Student bridge did not produce adapter JSON: " + response.output_json);
                }

                string adapterJsonText = File.ReadAllText(response.output_json);
                AdapterResult adapterResult = JsonUtility.FromJson<AdapterResult>(adapterJsonText);
                if (adapterResult == null)
                {
                    _inferenceDiagnostics.adapter_artifact_missing_reason = "adapter_json_parse_failed";
                    return RecordFailure(playerId, canUseCanonical, "Cannot parse adapter JSON payload.");
                }

                if (!string.Equals(adapterResult.status, "ok", StringComparison.Ordinal))
                {
                    _inferenceDiagnostics.adapter_artifact_missing_reason = "adapter_status_not_ok";
                    return RecordFailure(
                        playerId,
                        canUseCanonical,
                        "Student adapter payload is not ok: " + adapterResult.error);
                }

                UpdateInferenceDiagnosticsFromAdapterJson(adapterJsonText, response.output_json);

                if (!ValidateAdapterPayload(adapterResult, out string payloadError))
                {
                    _inferenceDiagnostics.adapter_artifact_missing_reason = "adapter_payload_validation_failed";
                    return RecordFailure(playerId, canUseCanonical, payloadError);
                }

                ActionMaskSet mask = canUseCanonical
                    ? stepInput.CanonicalMask
                    : _policyPipeline.BuildTransferCompatibleMask(playerId);

                if (_enableLegalActionMaskForSelection && _enableDynamicOccupancyMoveMaskEnrichment)
                {
                    ApplyDynamicOccupancyMoveMaskEnrichment(mask, playerId);
                }

                StudentLiveFilterDiagnostics filterDiagnostics = BuildStudentFilterDiagnostics(playerId, mask, out List<int> eligibleCellIndices);
                _inferenceDiagnostics.candidate_actor_cells_submitted = eligibleCellIndices.Count;

                PolicyExecutionReport execution;
                StudentMaskAwareDiagnostics maskAwareDiagnostics;
                if (_enableLegalActionMaskForSelection)
                {
                    Dictionary<int, StudentMaskAwareDiagnostics.ActorLegalMaskTelemetry> legalMaskByFlat =
                        BuildActorLegalMaskByFlat(mask);

                    execution = _policyPipeline.ExecuteTransferCompatibleMaskAware(
                        adapterResult.action_flat,
                        playerId,
                        eligibleCellIndices,
                        mask,
                        out int maskedOutChoicesCount,
                        out int fallbackToNoopCount,
                        out Dictionary<UnitActionType, int> preMaskHistogram,
                        out Dictionary<UnitActionType, int> postMaskHistogram,
                        out Dictionary<int, ActionDecoder.MaskAwareCellTelemetry> cellTelemetryByFlat,
                        "week6-day5-student-live");

                    maskAwareDiagnostics = new StudentMaskAwareDiagnostics(
                        enabled: true,
                        maskedOutActionTypeChoicesCount: maskedOutChoicesCount,
                        fallbackToNoopCount: fallbackToNoopCount,
                        preMaskRawHistogram: preMaskHistogram,
                        postMaskHistogram: postMaskHistogram,
                        cellTelemetryByFlat: cellTelemetryByFlat,
                        legalMaskByFlat: legalMaskByFlat);
                }
                else
                {
                    execution = _policyPipeline.ExecuteTransferCompatibleFiltered(
                        adapterResult.action_flat,
                        playerId,
                        eligibleCellIndices,
                        mask,
                        "week6-day5-student-live");

                    maskAwareDiagnostics = StudentMaskAwareDiagnostics.Empty;
                }

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
                _inferenceDiagnostics.python_request_status = "completed";
                _inferenceDiagnostics.adapter_artifact_missing_reason = string.Empty;

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
                _inferenceDiagnostics.python_response_status = "exception";
                _inferenceDiagnostics.adapter_artifact_missing_reason = "exception_during_inference";
                return RecordFailure(playerId, canUseCanonical, "Student live inference failed: " + ex.Message);
            }
        }

        private void UpdateInferenceDiagnosticsFromAdapterJson(string adapterJsonText, string outputJsonPath)
        {
            _inferenceDiagnostics.adapter_artifact_created = true;
            _inferenceDiagnostics.last_output_json_path = outputJsonPath ?? string.Empty;
            _inferenceDiagnostics.raw_adapter_response_keys = ExtractTopLevelJsonKeys(adapterJsonText);
            _inferenceDiagnostics.parsed_logits_available = adapterJsonText != null
                && adapterJsonText.IndexOf("\"model_output_logits_shapes\"", StringComparison.Ordinal) >= 0;
            _inferenceDiagnostics.parsed_action_type_probabilities_available = adapterJsonText != null
                && adapterJsonText.IndexOf("\"action_type_probabilities\"", StringComparison.Ordinal) >= 0;
            _inferenceDiagnostics.parsed_action_type_top3_available = adapterJsonText != null
                && adapterJsonText.IndexOf("\"action_type_top3\"", StringComparison.Ordinal) >= 0;
        }

        private static string[] ExtractTopLevelJsonKeys(string json)
        {
            if (string.IsNullOrWhiteSpace(json))
            {
                return Array.Empty<string>();
            }

            var keys = new List<string>(16);
            MatchCollection matches = Regex.Matches(json, "\"(?<key>[^\"]+)\"\\s*:");
            for (int i = 0; i < matches.Count; i++)
            {
                string key = matches[i].Groups["key"].Value;
                if (string.IsNullOrWhiteSpace(key))
                {
                    continue;
                }

                if (!keys.Contains(key))
                {
                    keys.Add(key);
                }

                if (keys.Count >= 64)
                {
                    break;
                }
            }

            return keys.ToArray();
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

            // Filename family is metadata only; contract compatibility is enforced by
            // bridge initialization and per-response payload validation.
            string checkpointFileName = Path.GetFileName(checkpointPath);
            if (!checkpointFileName.EndsWith(".pt", StringComparison.OrdinalIgnoreCase))
            {
                error = "Student checkpoint must be a PyTorch .pt file: " + checkpointPath;
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

                if (!string.IsNullOrWhiteSpace(ready.checkpoint_model_variant)
                    && !string.Equals(ready.checkpoint_model_variant, "transfer", StringComparison.OrdinalIgnoreCase))
                {
                    error =
                        "Student bridge checkpoint model variant is incompatible. " +
                        $"Expected transfer, got {ready.checkpoint_model_variant}";
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

        // Stage10D.12R: Read-only diagnostic capture of full raw runtime observation tensor
        private void CaptureFullRawObservationDiagnostic(
            float[] spatialObservation,
            Owner playerId,
            int stepIndex,
            string outputJsonPath)
        {
            const int H = ObservationContract.GridH;
            const int W = ObservationContract.GridW;
            const int C = ObservationContract.ChannelsPerCell;

            _inferenceDiagnostics.stage10d12r_capture_path = outputJsonPath ?? string.Empty;
            _inferenceDiagnostics.stage10d12r_capture_status = "initializing";
            _inferenceDiagnostics.stage10d12r_capture_json_length = 0;
            _inferenceDiagnostics.stage10d12r_capture_cell_count = 0;

            try
            {
                if (spatialObservation == null)
                {
                    string reason = "spatialObservation is null";
                    _inferenceDiagnostics.stage10d12r_capture_status = "invalid_observation_null";
                    WriteStage10D12RCaptureErrorSidecar(outputJsonPath, reason, 0, 0, H, W, C, null, null);
                    Debug.LogError("[Stage10D.12R] Capture serialization invalid: " + reason);
                    return;
                }

                if (spatialObservation.Length != H * W * C)
                {
                    string reason = $"Observation size mismatch: expected {H * W * C}, got {spatialObservation.Length}";
                    _inferenceDiagnostics.stage10d12r_capture_status = "invalid_observation_shape";
                    WriteStage10D12RCaptureErrorSidecar(outputJsonPath, reason, 0, spatialObservation.Length, H, W, C, null, null);
                    Debug.LogError("[Stage10D.12R] Capture serialization invalid: " + reason);
                    return;
                }

                for (int i = 0; i < spatialObservation.Length; i++)
                {
                    float v = spatialObservation[i];
                    if (float.IsNaN(v) || float.IsInfinity(v))
                    {
                        string reason = $"Observation contains non-finite value at index {i}";
                        _inferenceDiagnostics.stage10d12r_capture_status = "invalid_observation_non_finite";
                        WriteStage10D12RCaptureErrorSidecar(outputJsonPath, reason, 0, spatialObservation.Length, H, W, C, null, null);
                        Debug.LogError("[Stage10D.12R] Capture serialization invalid: " + reason);
                        return;
                    }
                }

                // Build diagnostic JSON with full raw tensor and metadata
                var channelNames = new[]
                {
                    // Entity attributes (0-11)
                    "ch0_hit_points",
                    "ch1_resources",
                    "ch2_owner_neutral",
                    "ch3_owner_self_friendly",
                    "ch4_owner_enemy",
                    "ch5_unit_resource",
                    "ch6_unit_base",
                    "ch7_unit_barracks",
                    "ch8_unit_worker",
                    "ch9_unit_light",
                    "ch10_unit_heavy",
                    "ch11_unit_ranged",
                    // Current action (12-17)
                    "ch12_action_noop",
                    "ch13_action_move",
                    "ch14_action_harvest",
                    "ch15_action_return",
                    "ch16_action_produce",
                    "ch17_action_attack",
                    // Direction (18-21)
                    "ch18_dir_north",
                    "ch19_dir_east",
                    "ch20_dir_south",
                    "ch21_dir_west",
                    // Produce type (22-25)
                    "ch22_produce_worker",
                    "ch23_produce_light",
                    "ch24_produce_heavy",
                    "ch25_produce_ranged",
                    // Attack target (26)
                    "ch26_attack_target_index",
                };

                // Build cell entries
                var cells = new Stage10D12RCellCapture[H * W];
                for (int flat = 0; flat < H * W; flat++)
                {
                    int y = flat / W;
                    int x = flat % W;
                    
                    var cellChannels = new float[C];
                    for (int c = 0; c < C; c++)
                    {
                        cellChannels[c] = spatialObservation[flat * C + c];
                    }

                    // Decode semantics from channels
                    string decodedOwner = DecodeOwnerFromChannels(cellChannels);
                    string decodedUnit = DecodeUnitFromChannels(cellChannels);
                    string decodedAction = DecodeCurrentActionFromChannels(cellChannels);

                    cells[flat] = new Stage10D12RCellCapture
                    {
                        flat_index = flat,
                        x = x,
                        y = y,
                        logical_label = GetLogicalCellLabel(flat),
                        raw_channel_vector = cellChannels,
                        decoded_owner = decodedOwner,
                        decoded_unit = decodedUnit,
                        decoded_current_action = decodedAction,
                    };
                }

                // Build final diagnostic JSON
                var diagnosticData = new Stage10D12RFullRawObservationCapture
                {
                    generated_at_utc = System.DateTime.UtcNow.ToString("O"),
                    stage = "10D.12R",
                    capture_type = "full_raw_runtime_observation",
                    step_index = stepIndex,
                    controlled_player = playerId.ToString(),
                    capture_point = "after_observation_validation_before_python_bridge_send",
                    tensor_shape = new[] { H, W, C },
                    tensor_shape_flat = new[] { H * W, C },
                    flatten_order = "flat = y * W + x; x = flat % W; y = flat / W",
                    channel_names = channelNames,
                    channel_count = C,
                    cell_count = H * W,
                    cells = cells,
                };

                // Write diagnostic JSON
                string json = JsonUtility.ToJson(diagnosticData, true);
                System.IO.File.WriteAllText(outputJsonPath, json, new System.Text.UTF8Encoding(false));

                bool fileExists = System.IO.File.Exists(outputJsonPath);
                long fileLength = fileExists ? new FileInfo(outputJsonPath).Length : 0L;
                bool hasTensorShape = json.Contains("\"tensor_shape\"");
                bool hasCells = json.Contains("\"cells\"");
                bool hasRawChannelVector = json.Contains("\"raw_channel_vector\"");
                bool hasB2 = json.Contains("\"flat_index\": 25") || json.Contains("\"flat_index\":25");
                bool hasC3 = json.Contains("\"flat_index\": 50") || json.Contains("\"flat_index\":50");

                bool serializationValid = fileExists
                    && fileLength > 10000L
                    && hasTensorShape
                    && hasCells
                    && hasRawChannelVector
                    && hasB2
                    && hasC3;

                _inferenceDiagnostics.stage10d12r_capture_json_length = json.Length;
                _inferenceDiagnostics.stage10d12r_capture_cell_count = H * W;

                if (!serializationValid)
                {
                    string reason =
                        $"post-write validation failed | exists={fileExists} | file_length={fileLength} | " +
                        $"json_length={json.Length} | has_tensor_shape={hasTensorShape} | has_cells={hasCells} | " +
                        $"has_raw_channel_vector={hasRawChannelVector} | has_B2={hasB2} | has_C3={hasC3}";
                    _inferenceDiagnostics.stage10d12r_capture_status = "serialization_invalid";
                    WriteStage10D12RCaptureErrorSidecar(outputJsonPath, reason, json.Length, spatialObservation.Length, H, W, C, null, json);
                    Debug.LogError("[Stage10D.12R] Capture serialization invalid: " + reason);
                    return;
                }

                _inferenceDiagnostics.stage10d12r_capture_status = "ok";

                if (_verboseLogs)
                {
                    Debug.Log($"[Stage10D.12R] Full raw observation captured to {outputJsonPath} (json_length={json.Length}, file_length={fileLength})");
                }
            }
            catch (System.Exception ex)
            {
                _inferenceDiagnostics.stage10d12r_capture_status = "exception";
                WriteStage10D12RCaptureErrorSidecar(
                    outputJsonPath,
                    "exception_during_capture",
                    0,
                    spatialObservation != null ? spatialObservation.Length : 0,
                    H,
                    W,
                    C,
                    ex,
                    null);
                Debug.LogError($"[Stage10D.12R] Failed to capture full raw observation: {ex.Message}");
            }
        }

        private static void WriteStage10D12RCaptureErrorSidecar(
            string outputJsonPath,
            string reason,
            int jsonLength,
            int observationLength,
            int h,
            int w,
            int c,
            Exception exception,
            string jsonSnapshot)
        {
            try
            {
                string sidecarPath = Path.ChangeExtension(outputJsonPath, ".capture_error.txt");
                var lines = new List<string>
                {
                    "[Stage10D.12R] Capture serialization invalid",
                    "utc=" + DateTime.UtcNow.ToString("O"),
                    "output_path=" + (outputJsonPath ?? string.Empty),
                    "reason=" + (reason ?? string.Empty),
                    "json_length=" + jsonLength,
                    "spatial_observation_length=" + observationLength,
                    "H=" + h,
                    "W=" + w,
                    "C=" + c,
                    "json_utility_result_is_empty_object=" + string.Equals(jsonSnapshot, "{}", StringComparison.Ordinal),
                    "exception=" + (exception != null ? exception.ToString() : string.Empty),
                };
                File.WriteAllLines(sidecarPath, lines, new System.Text.UTF8Encoding(false));
            }
            catch
            {
                // Sidecar write is best-effort in diagnostics path.
            }
        }

        private static string DecodeOwnerFromChannels(float[] channels)
        {
            if (channels.Length < 5) return "unknown";
            
            float neutral = channels[2];
            float self = channels[3];
            float enemy = channels[4];
            
            if (self > 0.5f) return "player1_friendly";
            if (enemy > 0.5f) return "player2_enemy";
            if (neutral > 0.5f) return "neutral";
            return "none";
        }

        private static string DecodeUnitFromChannels(float[] channels)
        {
            if (channels.Length < 12) return "none";
            
            float resource = channels[5];
            float base_unit = channels[6];
            float barracks = channels[7];
            float worker = channels[8];
            float light = channels[9];
            float heavy = channels[10];
            float ranged = channels[11];
            
            if (resource > 0.5f) return "resource";
            if (base_unit > 0.5f) return "base";
            if (barracks > 0.5f) return "barracks";
            if (worker > 0.5f) return "worker";
            if (light > 0.5f) return "light";
            if (heavy > 0.5f) return "heavy";
            if (ranged > 0.5f) return "ranged";
            return "none";
        }

        private static string DecodeCurrentActionFromChannels(float[] channels)
        {
            if (channels.Length < 18) return "unknown";
            
            float noop = channels[12];
            float move = channels[13];
            float harvest = channels[14];
            float return_res = channels[15];
            float produce = channels[16];
            float attack = channels[17];
            
            if (noop > 0.5f) return "noop";
            if (move > 0.5f) return "move";
            if (harvest > 0.5f) return "harvest";
            if (return_res > 0.5f) return "return";
            if (produce > 0.5f) return "produce";
            if (attack > 0.5f) return "attack";
            return "none";
        }

        private static string GetLogicalCellLabel(int flatIndex)
        {
            const int W = ObservationContract.GridW;  // 24
            int y = flatIndex / W;
            int x = flatIndex % W;
            
            // Grid reference: column letter + row number (1-indexed from bottom-left, like chess)
            if (x >= 0 && x < 26 && y >= 0 && y < 26)
            {
                char col = (char)('A' + x);
                int row = y + 1;
                return $"{col}{row}";
            }
            
            return $"[{x},{y}]";
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

            string[] expectedBranchOrder = BuildExpectedBranchOrder();
            if (adapter.branch_order == null || adapter.branch_order.Length != expectedBranchOrder.Length)
            {
                error = "Adapter branch_order is missing or malformed.";
                return false;
            }

            for (int i = 0; i < expectedBranchOrder.Length; i++)
            {
                if (!string.Equals(adapter.branch_order[i], expectedBranchOrder[i], StringComparison.Ordinal))
                {
                    error =
                        "Adapter branch_order mismatch. " +
                        $"index={i}, expected={expectedBranchOrder[i]}, got={adapter.branch_order[i]}";
                    return false;
                }
            }

            int[] expectedBranchSizes = BuildExpectedBranchSizes();
            if (adapter.branch_sizes == null || adapter.branch_sizes.Length != expectedBranchSizes.Length)
            {
                error = "Adapter branch_sizes are missing or malformed.";
                return false;
            }

            bool matchesV1Legacy = MatchesArray(adapter.branch_sizes, new[] { 6, 4, 4, 4, 4, 4, 9 });
            if (matchesV1Legacy)
            {
                error = "v1 action contract artifact is incompatible with Unity v2 runtime";
                return false;
            }

            for (int i = 0; i < expectedBranchSizes.Length; i++)
            {
                if (adapter.branch_sizes[i] != expectedBranchSizes[i])
                {
                    error =
                        "Adapter branch_sizes mismatch. " +
                        $"index={i}, expected={expectedBranchSizes[i]}, got={adapter.branch_sizes[i]}";
                    return false;
                }
            }

            if (!string.Equals(adapter.action_contract_version, ExpectedActionContractVersion, StringComparison.Ordinal))
            {
                error =
                    "Adapter action_contract_version mismatch. " +
                    $"Expected {ExpectedActionContractVersion}, got {adapter.action_contract_version}";
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

        private static string[] BuildExpectedBranchOrder()
        {
            return new[]
            {
                "action_type",
                "move_dir",
                "harvest_dir",
                "return_dir",
                "produce_dir",
                "produce_unit_type",
                "attack_target_local",
            };
        }

        private static int[] BuildExpectedBranchSizes()
        {
            return new[]
            {
                ActionContract.SIZE_ACTION_TYPE,
                ActionContract.SIZE_DIRECTION,
                ActionContract.SIZE_DIRECTION,
                ActionContract.SIZE_DIRECTION,
                ActionContract.SIZE_DIRECTION,
                ActionContract.SIZE_PRODUCE_UNIT_TYPE,
                ActionContract.SIZE_ATTACK_TARGET,
            };
        }

        private static bool MatchesArray(int[] actual, int[] expected)
        {
            if (actual == null || expected == null || actual.Length != expected.Length)
            {
                return false;
            }

            for (int i = 0; i < expected.Length; i++)
            {
                if (actual[i] != expected[i])
                {
                    return false;
                }
            }

            return true;
        }

        private static Dictionary<int, StudentMaskAwareDiagnostics.ActorLegalMaskTelemetry> BuildActorLegalMaskByFlat(ActionMaskSet mask)
        {
            var result = new Dictionary<int, StudentMaskAwareDiagnostics.ActorLegalMaskTelemetry>();
            if (mask == null || mask.ActorCellMask == null)
            {
                return result;
            }

            for (int flat = 0; flat < ActionContract.TotalCells; flat++)
            {
                if (flat < 0 || flat >= mask.ActorCellMask.Length || !mask.ActorCellMask[flat])
                {
                    continue;
                }

                ActorActionMask actorMask = mask.GetActorMaskByFlatIndex(flat);
                if (actorMask == null)
                {
                    continue;
                }

                bool[] actionTypeMask = actorMask.ActionTypeMask != null
                    ? (bool[])actorMask.ActionTypeMask.Clone()
                    : Array.Empty<bool>();
                bool[] moveDirMask = actorMask.MoveDirectionMask != null
                    ? (bool[])actorMask.MoveDirectionMask.Clone()
                    : Array.Empty<bool>();

                result[flat] = new StudentMaskAwareDiagnostics.ActorLegalMaskTelemetry(actionTypeMask, moveDirMask);
            }

            return result;
        }

        private void ApplyDynamicOccupancyMoveMaskEnrichment(ActionMaskSet mask, Owner playerId)
        {
            if (mask == null || _gridManager == null)
            {
                return;
            }

            var friendlyReservedTargetCells = new HashSet<int>();
            var enemyReservedTargetCells = new HashSet<int>();

            if (_matchManager != null)
            {
                var reservations = new List<PendingMoveReservation>(64);
                _matchManager.GetKnownMoveReservations(reservations);
                for (int i = 0; i < reservations.Count; i++)
                {
                    PendingMoveReservation reservation = reservations[i];
                    int targetFlat = reservation.Target.ToFlatIndex();
                    if (targetFlat < 0 || targetFlat >= ActionContract.TotalCells)
                    {
                        continue;
                    }

                    if (reservation.Owner == playerId)
                    {
                        friendlyReservedTargetCells.Add(targetFlat);
                    }
                    else if (reservation.Owner == Owner.Player1 || reservation.Owner == Owner.Player2)
                    {
                        enemyReservedTargetCells.Add(targetFlat);
                    }
                }
            }

            for (int flat = 0; flat < ActionContract.TotalCells; flat++)
            {
                if (mask.ActorCellMask == null
                    || flat < 0
                    || flat >= mask.ActorCellMask.Length
                    || !mask.ActorCellMask[flat])
                {
                    continue;
                }

                ActorActionMask actorMask = mask.GetActorMaskByFlatIndex(flat);
                if (actorMask == null || actorMask.MoveDirectionMask == null)
                {
                    continue;
                }

                bool anyMoveDirection = false;
                for (int d = 0; d < actorMask.MoveDirectionMask.Length; d++)
                {
                    if (!actorMask.MoveDirectionMask[d])
                    {
                        continue;
                    }

                    GridPosition target = actorMask.ActorPosition.Neighbour((Direction)d);
                    bool keepLegal = true;

                    if (!_gridManager.IsInside(target))
                    {
                        keepLegal = false;
                    }
                    else
                    {
                        int targetFlat = target.ToFlatIndex();

                        // Authoritative current occupancy (decision-time observable).
                        if (_gridManager.IsCellOccupied(target))
                        {
                            keepLegal = false;
                        }

                        // Evidence-backed command-ledger reservations only; no prediction.
                        if (keepLegal && (friendlyReservedTargetCells.Contains(targetFlat) || enemyReservedTargetCells.Contains(targetFlat)))
                        {
                            keepLegal = false;
                        }
                    }

                    actorMask.MoveDirectionMask[d] = keepLegal;
                    if (keepLegal)
                    {
                        anyMoveDirection = true;
                    }
                }

                if (actorMask.ActionTypeMask != null
                    && (int)UnitActionType.Move >= 0
                    && (int)UnitActionType.Move < actorMask.ActionTypeMask.Length)
                {
                    actorMask.ActionTypeMask[(int)UnitActionType.Move] = anyMoveDirection;
                }
            }
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