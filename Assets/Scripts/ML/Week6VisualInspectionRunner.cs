using RTS.Core;
using RTS.Gameplay;
using UnityEngine;
using System;
using System.Collections.Generic;
using System.IO;
using System.Globalization;
using System.Text;
using System.Reflection;
using System.Text.RegularExpressions;
using UnityEngine.SceneManagement;

#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

#if UNITY_EDITOR
using UnityEditor;
using Handles = UnityEditor.Handles;
#endif

namespace RTS.ML
{
    [DisallowMultipleComponent]
    public sealed class Week6VisualInspectionRunner : MonoBehaviour
    {
        [Header("Visual Inspection")]
        [SerializeField] private Owner _studentControlledPlayer = Owner.Player1;
        [SerializeField] private bool _autoStartOnPlay = true;
        [SerializeField] private bool _initializeAndPauseOnPlayWhenAutoStartDisabled = true;
        [SerializeField] private bool _showOverlay = true;
        [SerializeField] private bool _logTerminalSummary = true;
        [SerializeField] private bool _showGridLabels = true;
        [SerializeField] private bool _showActionMarkers = true;

        [Header("Overlay")]
        [SerializeField] private Vector2 _overlayPosition = new Vector2(14f, 14f);
        [SerializeField] private float _overlayWidth = 760f;
        [SerializeField] private float _overlayHeight = 680f;

        [Header("Camera")]
        [SerializeField] private bool _autoConfigureTopDownCamera = true;
        [SerializeField] private bool _forceOrthographicCamera = true;
        [SerializeField] private bool _flipVerticalToMatchMicroRtsTopLeft = true;
        [SerializeField] private float _cameraHeight = 30f;
        [SerializeField] private float _cameraTiltDegrees = 90f;
        [SerializeField] private float _orthographicPadding = 1.5f;

        [Header("Manual Controls")]
        [SerializeField] private bool _manualStepMode = true;
        [SerializeField] private bool _autoVisualPlaybackOnPlay = false;
        [SerializeField] private int _autoVisualPlaybackMaxSteps = 100;
        [SerializeField] private float _autoVisualPlaybackStepIntervalSeconds = 0.35f;

        [Header("Visual Usability")]
        [SerializeField] private bool _applyBaseVisualScaleOverrideInInspection = true;
        [SerializeField] private float _baseVisualCellScale = 0.85f;

        [Header("Output")]
        [SerializeField] private string _jsonReportRelativePath = "python/week6_student/tmp/week6_visual/week6_visual_episode_diagnostics.json";
        [SerializeField] private string _stepSnapshotOutputDirectoryRelativePath = "python/week6_student/reports";
        [SerializeField] private string _stepSnapshotFilePrefix = "stage10r_noop_collapse_snapshot_step";

        private EpisodeController _episodeController;
        private MatchManager _matchManager;
        private MatchBootstrap _matchBootstrap;
        private GridManager _gridManager;
        private UnitRegistry _unitRegistry;
        private ResourceManager _resourceManager;
        private Week6StudentPolicyAdapter _studentAdapter;
        private HeuristicPolicyAdapter _heuristicAdapter;
        private Week6EpisodeDiagnosticsCollector _diagnosticsCollector;
        private bool _terminalReportWritten;
        private bool _simulationPaused;
        private bool _lastStepApplyCommandCalled;
        private bool _lastStepActionApplierReached;
        private bool _lastStepSnapshotReady;
        private string _lastSnapshotPath = string.Empty;
        private bool _autoPlaybackEnabledRuntime;
        private bool _autoPlaybackRunning;
        private int _autoPlaybackRemainingSteps;
        private float _nextAutoPlaybackAt;
        private int _lastAutoPlaybackStep;
        private bool _legacyInputUnavailable;

        private Owner _baselineOwner = Owner.Player2;
        private UnitActionType _baselineLastActionType = UnitActionType.NoOp;
        private ProducibleUnit _baselineLastProduceType = ProducibleUnit.Worker;
        private bool _baselineLastAccepted;
        private string _baselineLastReason = "none";
        private string _baselineLastCommandSummary = "none";
        private int _baselineAcceptedCount;
        private int _baselineRejectedCount;

        private int _acceptedStudentCommands;
        private int _invalidStudentCommands;
        private int _runtimeRejectedStudentCommands;
        private int _ignoredStudentCommands;
        private int _totalCommandsBuiltAfterFilter;
        private int _totalCommandsSubmittedAfterFilter;
        private int _totalWrongOwnerAfterFilter;
        private int _totalCandidateCells;
        private int _totalEligibleOwnActorCells;
        private int _totalFallbackToNoop;
        private int _totalMaskedOutActionChoices;
        private int _lastCollectedStep = -1;
        private int _lastCollectedEpisode = -1;
        private string _lastTerminalReason = "none";
        private bool _sessionActive;

        private readonly Dictionary<string, int> _rejectionReasons = new Dictionary<string, int>(StringComparer.Ordinal);
        private readonly Dictionary<string, int> _runtimeRejectionReasons = new Dictionary<string, int>(StringComparer.Ordinal);
        private readonly Dictionary<UnitActionType, int> _aggregateActionTypeHistogram = CreateActionHistogram();
        private readonly Dictionary<UnitActionType, int> _aggregateActorActionTypeHistogram = CreateActionHistogram();
        private readonly Dictionary<int, ActorCellDiagnosticRow> _latestActorRowsByFlatIndex = new Dictionary<int, ActorCellDiagnosticRow>();
        private readonly List<ActorCellDiagnosticRow> _latestActorRows = new List<ActorCellDiagnosticRow>();
        private readonly List<string> _statusLines = new List<string>(12);
        private readonly Dictionary<int, MatchCommand> _lastAcceptedByActor = new Dictionary<int, MatchCommand>();
        private readonly Dictionary<int, RuntimeRejectionInfo> _lastRejectedByActor = new Dictionary<int, RuntimeRejectionInfo>();
        private readonly Dictionary<int, MatchCommand> _lastBaselineAcceptedByActor = new Dictionary<int, MatchCommand>();
        private readonly Dictionary<int, RuntimeRejectionInfo> _lastBaselineRejectedByActor = new Dictionary<int, RuntimeRejectionInfo>();

        private GUIStyle _statusBannerStyle;
        private GUIStyle _worldLabelStyle;

        private AdapterArtifactSnapshot _latestArtifact;
        private ObservationSnapshot _latestObservation;
        private StudentInferenceDiagnosticsSnapshot _latestInferenceDiagnostics;
        private float[] _latestObservationValues = Array.Empty<float>();
        private int _noOpActorCells;
        private int _nonNoOpActorCells;
        private int _nonActorNonNoOpCells;
        private string _b2TopAction = "n/a";
        private string _c3TopAction = "n/a";
        private string _noOpProbeClassification = "n/a";
        private Stage10RBridgeDebug _latestBridgeDebug;
        private string _flattenAlignmentClassification = "INCONCLUSIVE_NEEDS_MORE_LOGITS";

        private const int FocusFlatWorkerB2 = 25;
        private const int FocusFlatBaseC3 = 50;
        private static readonly Color StudentColor = new Color(0.20f, 0.75f, 0.95f, 1f);
        private static readonly Color BaselineColor = new Color(1.00f, 0.55f, 0.20f, 1f);
        private static readonly Color ResourceColor = new Color(0.20f, 1.00f, 0.35f, 1f);
        private static readonly Color EligibleActorColor = new Color(0.95f, 0.95f, 0.20f, 0.95f);
        private static readonly Color NoOpColor = new Color(0.85f, 0.85f, 0.85f, 0.95f);
        private static readonly Color WarningColor = new Color(1.00f, 0.40f, 0.20f, 0.95f);
        private static readonly Color SuccessColor = new Color(0.15f, 0.95f, 0.35f, 0.95f);

        [Serializable]
        private sealed class AdapterArtifactJson
        {
            public string status;
            public string action_contract_version;
            public string checkpoint_model_variant;
            public int checkpoint_epoch;
            public int[] observation_shape;
            public string observation_dtype;
            public int observation_element_count;
            public string[] branch_order;
            public int[] branch_sizes;
            public string[] logits_keys;
            public int action_flat_size;
            public int[] action_flat;
            public Stage10RBridgeDebug stage10r_debug;
        }

        [Serializable]
        private sealed class Stage10RBridgeDebug
        {
            public string controlled_player;
            public string owner_encoding_mode;
            public string flatten_formula;
            public string[] observation_channel_names;
            public FocusCellBridgeDiagnostic[] focus_cells;
            public OwnActorActionSummary[] own_actor_action_type_summary;
            public GlobalCellActionTypeDiagnostic[] global_cell_action_type_diagnostics;
            public FlattenAlignmentCheck[] flatten_alignment_checks;
            public ObservationVsBcExpectation[] observation_vs_bc_expectation;
        }

        [Serializable]
        private sealed class GlobalCellActionTypeDiagnostic
        {
            public int flat_index;
            public int[] grid_position;
            public string logical_label;
            public string owner_guess;
            public string unit_type_guess;
            public float[] action_type_logits;
            public float[] action_type_probabilities;
            public int predicted_action_type;
            public string predicted_action_type_name;
            public float non_noop_probability;
            public ActionTypeTopK[] action_type_top3;
        }

        [Serializable]
        private sealed class FocusCellBridgeDiagnostic
        {
            public string logical_label;
            public int[] grid_position;
            public int flat_index;
            public string owner_guess;
            public string unit_type_guess;
            public bool eligible_actor_guess;
            public int predicted_action_type;
            public string predicted_action_type_name;
            public float[] action_type_logits;
            public float[] action_type_probabilities;
            public ActionTypeTopK[] action_type_top3;
            public float noop_probability;
            public float best_non_noop_probability;
            public float noop_margin;
            public int move_dir;
            public int harvest_dir;
            public int return_dir;
            public int produce_dir;
            public int produce_unit_type;
            public int attack_target_local;
            public float[] cell_observation_channels;
        }

        [Serializable]
        private sealed class ActionTypeTopK
        {
            public int class_id;
            public string class_name;
            public float logit;
            public float probability;
        }

        [Serializable]
        private sealed class OwnActorActionSummary
        {
            public int flat_index;
            public int[] grid_position;
            public string logical_label;
            public int predicted_action_type;
            public string predicted_action_type_name;
            public float top1_probability;
            public int top2_action_type;
            public string top2_action_type_name;
            public float top2_probability;
            public float noop_margin;
        }

        [Serializable]
        private sealed class FlattenAlignmentCheck
        {
            public string check;
            public bool pass;
            public int expected;
            public int actual;
            public string expected_text;
            public string actual_text;
        }

        [Serializable]
        private sealed class ObservationVsBcExpectation
        {
            public string logical_label;
            public string unit_type_guess;
            public string owner_guess;
            public bool expected_unit_channel_active;
            public bool owner_channel_active;
            public bool suspicious;
        }

        [Serializable]
        private sealed class ActorCellSnapshot
        {
            public string unit_type;
            public string grid_position;
            public string logical_cell;
            public int flat_index;
            public bool eligible;
            public string predicted_action_type;
            public string predicted_action_type_source;
            public string top3_action_type;
            public int move_dir;
            public int harvest_dir;
            public int return_dir;
            public int produce_dir;
            public int produce_unit_type;
            public int attack_target_local;
            public bool command_built;
            public string command_not_built_reason;
            public bool action_applier_reached;
            public bool apply_command_reached;
            public string owner;
            public bool logits_probabilities_available;
            public string logits_probabilities_unavailable_reason;
            public float[] action_type_logits;
            public float[] action_type_probabilities;
            public ActionTypeTopK[] action_type_top3;
            public float noop_probability;
            public float best_non_noop_probability;
            public float noop_margin;
            public float[] cell_observation_channels;
            public string[] observation_channel_names;
        }

        [Serializable]
        private sealed class FocusCellSnapshot
        {
            public string logical_label;
            public int[] grid_position;
            public int flat_index;
            public string unit_type;
            public string owner;
            public bool eligible_actor;
            public string predicted_action_type;
            public string predicted_action_type_source;
            public bool logits_probabilities_available;
            public string logits_probabilities_unavailable_reason;
            public float[] action_type_logits;
            public float[] action_type_probabilities;
            public ActionTypeTopK[] action_type_top3;
            public float noop_probability;
            public float best_non_noop_probability;
            public float noop_margin;
            public int move_dir;
            public int harvest_dir;
            public int return_dir;
            public int produce_dir;
            public int produce_unit_type;
            public int attack_target_local;
            public bool command_built;
            public string command_not_built_reason;
            public float[] cell_observation_channels;
            public string[] observation_channel_names;
        }

        [Serializable]
        private sealed class UnitSnapshot
        {
            public string owner;
            public string unit_type;
            public int x;
            public int y;
            public string logical_cell;
            public int flat_index;
        }

        [Serializable]
        private sealed class Stage10VisualSnapshot
        {
            public string generated_at_utc;
            public int step;
            public string scene;
            public string checkpoint;
            public string checkpoint_path_used_at_inference;
            public UnitSnapshot[] unit_positions;
            public ActorCellSnapshot[] actor_cells;
            public int[] observation_shape;
            public float observation_min;
            public float observation_max;
            public bool observation_has_nan;
            public bool observation_has_inf;
            public int[] model_input_shape;
            public bool logits_shapes_captured;
            public string[] logits_shape_lines;
            public string[] predicted_action_tensor_bounds;
            public string flatten_formula;
            public string owner_encoding_mode;
            public string controlled_player;
            public bool adapter_invoked;
            public int inference_request_count;
            public string last_inference_call_utc;
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
            public string adapter_artifact_last_output_json_path;
            public FocusCellSnapshot[] focus_cell_diagnostics;
            public string[] flatten_alignment_checks;
            public string[] observation_vs_bc_expectation;
            public string[] own_actor_summary;
            public string root_cause_classification;
            public string decision;
            public string offline_bridge_consistency;
            public bool action_applier_reached;
            public bool apply_command_reached;
            public int commands_built;
            public int commands_submitted;
            public int accepted;
            public int rejected;
            public int ignored;
            public string[] rejection_histogram;
        }

        [Serializable]
        private sealed class Stage10D10TopCell
        {
            public int cell_index;
            public int x;
            public int y;
            public string visual_label;
            public bool runtime_is_friendly_actor;
            public string predicted_action_type;
            public float score;
        }

        [Serializable]
        private sealed class Stage10D10ReasonCount
        {
            public string reason;
            public int count;
        }

        [Serializable]
        private sealed class Stage10D10CellRow
        {
            public int cell_index;
            public int x;
            public int y;
            public string visual_label;
            public string decoded_observation_owner;
            public string decoded_observation_unit_type;
            public bool runtime_is_friendly_actor;
            public bool runtime_is_friendly_worker;
            public bool runtime_is_friendly_base;
            public bool runtime_is_enemy;
            public bool runtime_is_resource;
            public bool runtime_is_empty;
            public float[] action_type_logits;
            public float[] action_type_probabilities;
            public float p_noop;
            public float p_move;
            public float p_harvest;
            public float p_return;
            public float p_produce;
            public float p_attack;
            public string predicted_action_type;
            public float non_noop_prob;
            public ActionTypeTopK[] top3_action_type_probabilities;
            public int move_dir;
            public int harvest_dir;
            public int return_dir;
            public int produce_dir;
            public int produce_unit_type;
            public int attack_target_local;
            public string decoder_result_if_predicted_non_noop;
            public bool command_built;
            public string decoder_reject_reason;
            public bool applier_submission_reached;
            public bool applier_submitted;
            public bool applier_accepted;
            public bool applier_rejected;
            public string applier_reject_reason;
        }

        [Serializable]
        private sealed class Stage10D10GlobalSummary
        {
            public string generated_at_utc;
            public int step;
            public int total_cells;
            public int friendly_actor_cell_count;
            public int friendly_worker_count;
            public int friendly_base_count;
            public float global_predicted_noop_share;
            public float actor_cell_predicted_noop_share;
            public float worker_predicted_noop_share;
            public float base_predicted_noop_share;
            public float max_non_noop_probability_globally;
            public float max_non_noop_probability_on_actor_cells;
            public Stage10D10TopCell[] top_k_non_noop_probability_cells;
            public Stage10D10TopCell[] top_k_harvest_probability_cells;
            public Stage10D10TopCell[] top_k_produce_probability_cells;
            public Stage10D10TopCell[] top_k_attack_probability_cells;
            public int non_noop_predictions_on_actor_cells;
            public int non_noop_predictions_off_actor_cells;
            public int commands_built;
            public int commands_submitted;
            public int commands_accepted;
            public Stage10D10ReasonCount[] decoder_reject_counts_by_reason;
            public Stage10D10ReasonCount[] applier_reject_counts_by_reason;
            public string classification;
            public string classification_rationale;
        }

        [Serializable]
        private sealed class Stage10D10GlobalSnapshot
        {
            public string generated_at_utc;
            public int step;
            public string scene;
            public string checkpoint;
            public string checkpoint_path_used_at_inference;
            public string controlled_player;
            public string flatten_formula;
            public string owner_encoding_mode;
            public Stage10D10GlobalSummary summary;
            public Stage10D10CellRow[] cells;
        }

        private readonly struct RuntimeRejectionInfo
        {
            public RuntimeRejectionInfo(string reason)
            {
                Reason = string.IsNullOrWhiteSpace(reason) ? "other" : reason;
            }

            public string Reason { get; }
        }

        private readonly struct AdapterArtifactSnapshot
        {
            public AdapterArtifactSnapshot(
                bool isAvailable,
                string artifactPath,
                int[] observationShape,
                int[] branchSizes,
                string[] logitsKeys,
                int actionFlatSize,
                int[] actionFlat,
                Dictionary<string, int[]> logitsShapes,
                Stage10RBridgeDebug stage10RDebug)
            {
                IsAvailable = isAvailable;
                ArtifactPath = artifactPath ?? string.Empty;
                ObservationShape = observationShape ?? Array.Empty<int>();
                BranchSizes = branchSizes ?? Array.Empty<int>();
                LogitsKeys = logitsKeys ?? Array.Empty<string>();
                ActionFlatSize = actionFlatSize;
                ActionFlat = actionFlat ?? Array.Empty<int>();
                LogitsShapes = logitsShapes ?? new Dictionary<string, int[]>(StringComparer.Ordinal);
                Stage10RDebug = stage10RDebug;
            }

            public bool IsAvailable { get; }
            public string ArtifactPath { get; }
            public int[] ObservationShape { get; }
            public int[] BranchSizes { get; }
            public string[] LogitsKeys { get; }
            public int ActionFlatSize { get; }
            public int[] ActionFlat { get; }
            public Dictionary<string, int[]> LogitsShapes { get; }
            public Stage10RBridgeDebug Stage10RDebug { get; }
        }

        private readonly struct ObservationSnapshot
        {
            public ObservationSnapshot(float minValue, float maxValue, bool hasNaN, bool hasInf, int ownUnits, int enemyUnits, int resourceCount)
            {
                MinValue = minValue;
                MaxValue = maxValue;
                HasNaN = hasNaN;
                HasInf = hasInf;
                OwnUnits = ownUnits;
                EnemyUnits = enemyUnits;
                ResourceCount = resourceCount;
            }

            public float MinValue { get; }
            public float MaxValue { get; }
            public bool HasNaN { get; }
            public bool HasInf { get; }
            public int OwnUnits { get; }
            public int EnemyUnits { get; }
            public int ResourceCount { get; }
        }

        private sealed class ActorCellDiagnosticRow
        {
            public UnitRuntime Unit;
            public int FlatIndex;
            public string LogicalCell;
            public bool Eligible;
            public UnitActionType PredictedActionType;
            public string PredictedActionTypeSource;
            public int MoveDir;
            public int HarvestDir;
            public int ReturnDir;
            public int ProduceDir;
            public int ProduceUnitType;
            public int AttackTargetLocal;
            public bool CommandBuilt;
            public bool ActionApplierReached;
            public bool ApplyCommandReached;
            public string CommandNotBuiltReason;
            public string Top3ActionType;
            public string Owner;
            public bool LogitsAvailable;
            public string LogitsUnavailableReason;
            public float[] ActionTypeLogits;
            public float[] ActionTypeProbabilities;
            public ActionTypeTopK[] ActionTypeTop3;
            public float NoopProbability;
            public float BestNonNoopProbability;
            public float NoopMargin;
            public float[] CellObservationChannels;
            public string[] ObservationChannelNames;
        }

        private void OnEnable()
        {
            ResolveReferences();
            SubscribeToMatchEvents();
        }

        private void Start()
        {
            ConfigureCameraForVisualInspection();
            _autoPlaybackEnabledRuntime = _autoVisualPlaybackOnPlay;

            if (_autoStartOnPlay && !_sessionActive)
            {
                StartVisualInspectionMatch(pauseBeforeFirstDecision: _manualStepMode);
            }
            else if (!_autoStartOnPlay && _initializeAndPauseOnPlayWhenAutoStartDisabled && !_sessionActive)
            {
                StartVisualInspectionMatch(pauseBeforeFirstDecision: true);
            }

            if (_autoPlaybackEnabledRuntime)
            {
                RunVisualPlaybackUntilTerminalOrLimit(_autoVisualPlaybackMaxSteps);
            }
        }

        private void OnDisable()
        {
            UnsubscribeFromMatchEvents();
            UnsubscribeHeuristicEvents();
        }

        private void Update()
        {
            ResolveReferences();
            HandleKeyboardShortcuts();
            ApplyVisualScaleOverrides();
            UpdateAutoPlayback();

            if (!_sessionActive || _episodeController == null || _matchManager == null)
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
                _ignoredStudentCommands = _runtimeRejectedStudentCommands;
                _lastStepActionApplierReached = report.FilterDiagnostics.CommandsBuiltAfterFilter > 0;
                _lastStepApplyCommandCalled = report.AcceptedCount > 0 || report.RejectedCount > 0 || _lastStepApplyCommandCalled;
                _totalCommandsBuiltAfterFilter += report.FilterDiagnostics.CommandsBuiltAfterFilter;
                _totalCommandsSubmittedAfterFilter += report.FilterDiagnostics.CommandsSubmittedAfterFilter;
                _totalWrongOwnerAfterFilter += report.FilterDiagnostics.WrongOwnerRejectionsAfterFilter;
                _totalCandidateCells += report.FilterDiagnostics.CandidateCellsTotal;
                _totalEligibleOwnActorCells += report.FilterDiagnostics.EligibleOwnActorCells;
                _totalFallbackToNoop += report.MaskAwareDiagnostics.FallbackToNoopCount;
                _totalMaskedOutActionChoices += report.MaskAwareDiagnostics.MaskedOutActionTypeChoicesCount;

                _diagnosticsCollector?.RecordStudentDecodedActions(report.DecodedActions);
                _diagnosticsCollector?.RecordStudentRejectionReasons(report.RejectionReasons);
                _diagnosticsCollector?.RecordStudentFilterDiagnostics(report.FilterDiagnostics);
                _diagnosticsCollector?.RecordStudentMaskAwareDiagnostics(report.MaskAwareDiagnostics);

                MergeActionHistogram(_aggregateActionTypeHistogram, report.MaskAwareDiagnostics.PostMaskHistogram);
                MergeActionHistogram(_aggregateActorActionTypeHistogram, report.MaskAwareDiagnostics.PostMaskHistogram);

                for (int i = 0; i < report.RejectionReasons.Count; i++)
                {
                    IncrementStringCount(_rejectionReasons, NormalizeReason(report.RejectionReasons[i]));
                }
            }

            if (currentStep > 0)
            {
                _diagnosticsCollector?.RecordStepCompleted();
            }

            RefreshLatestDiagnosticsFromArtifacts();
            BuildActorRowsForOverlay();
            _lastStepSnapshotReady = true;

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

            GUILayout.BeginArea(new Rect(_overlayPosition.x, _overlayPosition.y, _overlayWidth, _overlayHeight), GUI.skin.box);
            GUILayout.Label("Week 6 Student Visual Diagnostic Mode (Stage10V)");
            DrawStatusBanner();
            GUILayout.Label($"VISUAL MODE: {(_simulationPaused ? "PAUSED" : "RUNNING")} | CurrentStep={GetCurrentStep()} | ManualStepModeActive={_manualStepMode} | AutoPlaybackEnabled={_autoPlaybackEnabledRuntime} | AutoPlaybackRunning={_autoPlaybackRunning} | AutoStepsLeft={Mathf.Max(0, _autoPlaybackRemainingSteps)}");
            GUILayout.Label("Press N / RightArrow to advance one step");
            GUILayout.Label("Press Space to pause/resume | Press R to reset | Press L to dump snapshot");
            GUILayout.Label($"Controls: Space pause/resume | N/Right step | R reset | D overlay | G labels | A markers | L dump snapshot");
            GUILayout.Space(4f);

            GUILayout.Label($"Scene: {SceneManager.GetActiveScene().name} | Preset={GetScenarioPreset()} | Map=24x24 | Step={GetCurrentStep()} / Max={GetMaxSteps()}");
            GUILayout.Label($"Terminal: {_lastTerminalReason} | Winner={GetWinnerLabel()} | Running={IsRunningLabel()} | Paused={_simulationPaused}");
            GUILayout.Label($"Control: P1={GetPlayerModeLabel(1)}, P2={GetPlayerModeLabel(2)}, ActiveRunners={CountActiveRunners()}");
            GUILayout.Label($"Checkpoint: {GetCheckpointPathLabel()}");
            GUILayout.Label($"Bridge: started={snapshot.ServerStarted}, requests={snapshot.DecisionRequestsSent}/{snapshot.DecisionRequestsSucceeded}/{snapshot.DecisionRequestsFailed}, lastError={(string.IsNullOrWhiteSpace(snapshot.LastError) ? "none" : snapshot.LastError)}");
            GUILayout.Label($"Baseline (P2) last action: owner={_baselineOwner}, action={_baselineLastActionType}, produce={_baselineLastProduceType}, accepted={_baselineLastAccepted}, reason={_baselineLastReason}");
            GUILayout.Label($"Baseline last command: {_baselineLastCommandSummary} | accepted/rejected={_baselineAcceptedCount}/{_baselineRejectedCount}");
            GUILayout.Space(4f);

            GUILayout.Label($"Observation: shape=[24,24,27], min/max={_latestObservation.MinValue.ToString("F4", CultureInfo.InvariantCulture)}/{_latestObservation.MaxValue.ToString("F4", CultureInfo.InvariantCulture)}, NaN={_latestObservation.HasNaN}, Inf={_latestObservation.HasInf}, own={_latestObservation.OwnUnits}, enemy={_latestObservation.EnemyUnits}, resources={_latestObservation.ResourceCount}");
            GUILayout.Label("Observation global vector fed into strict BC path: no");

            int logitsShapeCount = _latestArtifact.LogitsShapes != null ? _latestArtifact.LogitsShapes.Count : 0;
            GUILayout.Label($"Inference: modelInput=[{FormatIntArray(_latestArtifact.ObservationShape)}], predicted=[576,7], branches=[{FormatIntArray(_latestArtifact.BranchSizes)}], logitsShapesCaptured={logitsShapeCount > 0}");
            GUILayout.Label($"Action histogram(all-cells from latest artifact): {FormatActionHistogramFromArtifact(_latestArtifact.ActionFlat)}");
            GUILayout.Label($"NoOp share={FormatNoOpShareFromArtifact(_latestArtifact.ActionFlat)} | non-NoOp share={FormatNonNoOpShareFromArtifact(_latestArtifact.ActionFlat)}");

            GUILayout.Space(4f);
            GUILayout.Label($"NoOp collapse probe: actorChecked={_latestActorRows.Count}, actorNoOp={_noOpActorCells}, actorNonNoOp={_nonNoOpActorCells}, nonActorNonNoOp={_nonActorNonNoOpCells}");
            GUILayout.Label($"Focus cells: B2(flat25) top={_b2TopAction}; C3(flat50) top={_c3TopAction}");
            GUILayout.Label($"Probe classification: {_noOpProbeClassification}");
            GUILayout.Label($"Flatten classification: {_flattenAlignmentClassification}");

            ActorCellDiagnosticRow b2Row;
            ActorCellDiagnosticRow c3Row;
            _latestActorRowsByFlatIndex.TryGetValue(FocusFlatWorkerB2, out b2Row);
            _latestActorRowsByFlatIndex.TryGetValue(FocusFlatBaseC3, out c3Row);
            GUILayout.Label("B2 probs: " + BuildFocusProbabilitiesLine(b2Row));
            GUILayout.Label("C3 probs: " + BuildFocusProbabilitiesLine(c3Row));

            GUILayout.Space(4f);
            GUILayout.Label($"Decoder/Applier: built={_totalCommandsBuiltAfterFilter}, submitted={_totalCommandsSubmittedAfterFilter}, ActionApplierCalled={_lastStepActionApplierReached}, ApplyCommandCalled={_lastStepApplyCommandCalled}, accepted={_acceptedStudentCommands}, rejected={_invalidStudentCommands}, ignored={_ignoredStudentCommands}");
            GUILayout.Label($"Filter diagnostics: candidateCells={_totalCandidateCells}, eligibleOwnActorCells={_totalEligibleOwnActorCells}, wrongOwnerAfterFilter={_totalWrongOwnerAfterFilter}, fallbackNoOp={_totalFallbackToNoop}, maskedOutActionType={_totalMaskedOutActionChoices}");
            GUILayout.Label("Runtime rejection histogram: " + FormatStringHistogram(_runtimeRejectionReasons));

            GUILayout.Space(6f);
            GUILayout.Label("Actor cells (Player1):");
            for (int i = 0; i < _latestActorRows.Count; i++)
            {
                ActorCellDiagnosticRow row = _latestActorRows[i];
                GUILayout.Label(BuildActorRowLine(row));
            }

            if (_latestActorRows.Count == 0)
            {
                GUILayout.Label("- none");
            }

            if (_lastStepSnapshotReady)
            {
                GUILayout.Space(4f);
                GUILayout.Label("Last snapshot: " + (_lastSnapshotPath.Length > 0 ? _lastSnapshotPath : "not dumped yet"));
            }

            GUILayout.EndArea();

            DrawFocusCellLabels();
        }

        private void OnDrawGizmos()
        {
            if (!_showActionMarkers)
            {
                return;
            }

            ResolveReferences();
            if (_gridManager == null)
            {
                return;
            }

            DrawUnitMarkers();
            DrawActorMarkers();
            DrawBaselineCommandMarkers();

#if UNITY_EDITOR
            if (_showGridLabels)
            {
                DrawGridLabels();
            }
#endif
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

            StartVisualInspectionMatch(pauseBeforeFirstDecision: _manualStepMode);
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

        [ContextMenu("Step Visual Inspection Once")]
        private void ContextMenuStepOnce()
        {
            if (!EditorApplication.isPlaying)
            {
                EditorUtility.DisplayDialog("Play Mode Required", "Please enter Play Mode before stepping.", "OK");
                return;
            }

            StepManualOnce();
        }

        [ContextMenu("Dump Visual Snapshot")]
        private void ContextMenuDumpSnapshot()
        {
            if (!EditorApplication.isPlaying)
            {
                EditorUtility.DisplayDialog("Play Mode Required", "Please enter Play Mode before dumping snapshot.", "OK");
                return;
            }

            DumpCurrentStepDiagnostics();
        }
#endif

        public void StartVisualInspectionMatch(bool pauseBeforeFirstDecision = false)
        {
            ResolveReferences();
            if (_episodeController == null || _matchManager == null)
            {
                Debug.LogError("[Week6VisualInspectionRunner] EpisodeController or MatchManager is missing.");
                return;
            }

            ConfigureWeek6ControlModes();
            ResetSessionCounters();
            InitializeDiagnosticsCollector();
            SubscribeHeuristicEvents();
            _sessionActive = true;

            _episodeController.AutoStepInFixedUpdate = !pauseBeforeFirstDecision;
            _simulationPaused = pauseBeforeFirstDecision;
            _episodeController.StartNewEpisode();

            RefreshLatestDiagnosticsFromArtifacts();
            BuildActorRowsForOverlay();
        }

        public void RestartVisualInspectionMatch()
        {
            StartVisualInspectionMatch(pauseBeforeFirstDecision: _manualStepMode);
        }

        public void SetAutoVisualPlaybackEnabled(bool enabled)
        {
            _autoPlaybackEnabledRuntime = enabled;
            if (!enabled)
            {
                StopAutoPlayback();
            }
        }

        public void RunVisualPlaybackSteps(int steps)
        {
            if (steps <= 0)
            {
                return;
            }

            EnsureSessionForPlayback();
            _simulationPaused = true;
            _episodeController.AutoStepInFixedUpdate = false;
            _autoPlaybackRunning = true;
            _autoPlaybackRemainingSteps = Mathf.Min(steps, Mathf.Max(1, _autoVisualPlaybackMaxSteps));
            _nextAutoPlaybackAt = Time.time + Mathf.Max(0.05f, _autoVisualPlaybackStepIntervalSeconds);
            _lastAutoPlaybackStep = GetCurrentStep();
        }

        public void RunVisualPlaybackUntilTerminalOrLimit(int maxSteps)
        {
            int bounded = Mathf.Clamp(maxSteps, 1, 1000);
            RunVisualPlaybackSteps(bounded);
        }

        public void StepManualOnce()
        {
            ResolveReferences();
            if (_episodeController == null || !_sessionActive)
            {
                return;
            }

            _episodeController.AutoStepInFixedUpdate = false;
            _simulationPaused = true;
            _lastStepApplyCommandCalled = false;
            _lastAcceptedByActor.Clear();
            _lastRejectedByActor.Clear();

            bool stillRunning = _episodeController.StepEpisodeOnce();
            RefreshLatestDiagnosticsFromArtifacts();
            BuildActorRowsForOverlay();

            if (!stillRunning)
            {
                EpisodeEndReport terminalReport = _episodeController.LastTerminalReport;
                if (terminalReport.IsTerminal)
                {
                    _lastTerminalReason = terminalReport.TerminalReason.ToString();
                }
            }
        }

        public void TogglePauseResume()
        {
            ResolveReferences();
            if (_episodeController == null)
            {
                return;
            }

            _simulationPaused = !_simulationPaused;
            _episodeController.AutoStepInFixedUpdate = !_simulationPaused;
        }

        public void DumpCurrentStepDiagnostics()
        {
            ResolveReferences();
            if (_matchManager == null)
            {
                return;
            }

            RefreshLatestDiagnosticsFromArtifacts();
            BuildActorRowsForOverlay();

            string projectRoot = Directory.GetParent(Application.dataPath).FullName;
            string outputDir = Path.Combine(projectRoot, _stepSnapshotOutputDirectoryRelativePath);
            Directory.CreateDirectory(outputDir);

            int step = _matchManager.Step;
            string effectivePrefix = _stepSnapshotFilePrefix;
            if (string.IsNullOrWhiteSpace(effectivePrefix) || effectivePrefix.StartsWith("stage10v_", StringComparison.OrdinalIgnoreCase))
            {
                effectivePrefix = "stage10r_noop_collapse_snapshot_step";
            }

            string fileName = effectivePrefix + step.ToString("D4", CultureInfo.InvariantCulture) + ".json";
            string path = Path.Combine(outputDir, fileName);

            var unitSnapshots = BuildUnitSnapshots();
            var actorSnapshots = BuildActorCellSnapshots();
            var focusSnapshots = BuildFocusCellSnapshots();
            string[] flattenChecks = BuildFlattenAlignmentLines();
            string[] observationVsBc = BuildObservationVsBcLines();
            string[] ownActorSummary = BuildOwnActorSummaryLines();
            string rootCause = ClassifyRootCause();
            string decision = ClassifyDecision(rootCause);

            var snapshot = new Stage10VisualSnapshot
            {
                generated_at_utc = DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture),
                step = step,
                scene = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name,
                checkpoint = GetCheckpointPathLabel(),
                checkpoint_path_used_at_inference = _latestInferenceDiagnostics != null
                    ? _latestInferenceDiagnostics.checkpoint_path_used_at_inference
                    : string.Empty,
                unit_positions = unitSnapshots.ToArray(),
                actor_cells = actorSnapshots.ToArray(),
                observation_shape = new[] { 24, 24, 27 },
                observation_min = _latestObservation.MinValue,
                observation_max = _latestObservation.MaxValue,
                observation_has_nan = _latestObservation.HasNaN,
                observation_has_inf = _latestObservation.HasInf,
                model_input_shape = _latestArtifact.ObservationShape,
                logits_shapes_captured = _latestArtifact.LogitsShapes != null && _latestArtifact.LogitsShapes.Count > 0,
                logits_shape_lines = BuildLogitsShapeLines(),
                predicted_action_tensor_bounds = BuildPredictedActionBoundsLines(),
                flatten_formula = _latestBridgeDebug != null && !string.IsNullOrWhiteSpace(_latestBridgeDebug.flatten_formula)
                    ? _latestBridgeDebug.flatten_formula
                    : "flat_index = row * 24 + col",
                owner_encoding_mode = _latestBridgeDebug != null && !string.IsNullOrWhiteSpace(_latestBridgeDebug.owner_encoding_mode)
                    ? _latestBridgeDebug.owner_encoding_mode
                    : "unavailable",
                controlled_player = _latestBridgeDebug != null && !string.IsNullOrWhiteSpace(_latestBridgeDebug.controlled_player)
                    ? _latestBridgeDebug.controlled_player
                    : _studentControlledPlayer.ToString(),
                adapter_invoked = _latestInferenceDiagnostics != null && _latestInferenceDiagnostics.adapter_invoked,
                inference_request_count = _latestInferenceDiagnostics != null ? _latestInferenceDiagnostics.inference_request_count : 0,
                last_inference_call_utc = _latestInferenceDiagnostics != null ? _latestInferenceDiagnostics.last_inference_call_utc : string.Empty,
                candidate_actor_cells_submitted = _latestInferenceDiagnostics != null ? _latestInferenceDiagnostics.candidate_actor_cells_submitted : 0,
                python_request_status = _latestInferenceDiagnostics != null ? _latestInferenceDiagnostics.python_request_status : string.Empty,
                python_response_status = _latestInferenceDiagnostics != null ? _latestInferenceDiagnostics.python_response_status : string.Empty,
                raw_bridge_response_keys = _latestInferenceDiagnostics != null ? _latestInferenceDiagnostics.raw_bridge_response_keys : Array.Empty<string>(),
                raw_adapter_response_keys = _latestInferenceDiagnostics != null ? _latestInferenceDiagnostics.raw_adapter_response_keys : Array.Empty<string>(),
                parsed_logits_available = _latestInferenceDiagnostics != null && _latestInferenceDiagnostics.parsed_logits_available,
                parsed_action_type_probabilities_available = _latestInferenceDiagnostics != null && _latestInferenceDiagnostics.parsed_action_type_probabilities_available,
                parsed_action_type_top3_available = _latestInferenceDiagnostics != null && _latestInferenceDiagnostics.parsed_action_type_top3_available,
                adapter_artifact_created = _latestInferenceDiagnostics != null && _latestInferenceDiagnostics.adapter_artifact_created,
                adapter_artifact_missing_reason = ResolveAdapterArtifactMissingReason(),
                adapter_artifact_last_output_json_path = _latestInferenceDiagnostics != null ? _latestInferenceDiagnostics.last_output_json_path : string.Empty,
                focus_cell_diagnostics = focusSnapshots.ToArray(),
                flatten_alignment_checks = flattenChecks,
                observation_vs_bc_expectation = observationVsBc,
                own_actor_summary = ownActorSummary,
                root_cause_classification = rootCause,
                decision = decision,
                offline_bridge_consistency = "not_implemented",
                action_applier_reached = _lastStepActionApplierReached,
                apply_command_reached = _lastStepApplyCommandCalled,
                commands_built = _totalCommandsBuiltAfterFilter,
                commands_submitted = _totalCommandsSubmittedAfterFilter,
                accepted = _acceptedStudentCommands,
                rejected = _invalidStudentCommands,
                ignored = _ignoredStudentCommands,
                rejection_histogram = BuildHistogramLines(_runtimeRejectionReasons),
            };

            File.WriteAllText(path, JsonUtility.ToJson(snapshot, true), Encoding.UTF8);
            _lastSnapshotPath = path;
            Debug.Log("[Week6VisualInspectionRunner] Step diagnostics snapshot: " + path);

            DumpStage10D10GlobalRuntimeDiagnostics(outputDir, step);
        }

        private void DumpStage10D10GlobalRuntimeDiagnostics(string outputDir, int step)
        {
            List<Stage10D10CellRow> rows = BuildStage10D10CellRows();
            Stage10D10GlobalSummary summary = BuildStage10D10Summary(rows, step);

            string stepSuffix = step.ToString("D4", CultureInfo.InvariantCulture);
            string logitsSnapshotPath = Path.Combine(outputDir, "stage10d10_global_runtime_logits_snapshot_step" + stepSuffix + ".json");
            string cellTablePath = Path.Combine(outputDir, "stage10d10_global_runtime_cell_table_step" + stepSuffix + ".jsonl");
            string summaryPath = Path.Combine(outputDir, "stage10d10_global_runtime_summary.json");
            string reportPath = Path.Combine(outputDir, "STAGE10D10_GLOBAL_RUNTIME_NOOP_DIAGNOSTIC_REPORT.md");

            var snapshot = new Stage10D10GlobalSnapshot
            {
                generated_at_utc = DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture),
                step = step,
                scene = SceneManager.GetActiveScene().name,
                checkpoint = GetCheckpointPathLabel(),
                checkpoint_path_used_at_inference = _latestInferenceDiagnostics != null
                    ? _latestInferenceDiagnostics.checkpoint_path_used_at_inference
                    : string.Empty,
                controlled_player = _latestBridgeDebug != null && !string.IsNullOrWhiteSpace(_latestBridgeDebug.controlled_player)
                    ? _latestBridgeDebug.controlled_player
                    : _studentControlledPlayer.ToString(),
                flatten_formula = _latestBridgeDebug != null && !string.IsNullOrWhiteSpace(_latestBridgeDebug.flatten_formula)
                    ? _latestBridgeDebug.flatten_formula
                    : "flat_index = row * 24 + col",
                owner_encoding_mode = _latestBridgeDebug != null && !string.IsNullOrWhiteSpace(_latestBridgeDebug.owner_encoding_mode)
                    ? _latestBridgeDebug.owner_encoding_mode
                    : "unavailable",
                summary = summary,
                cells = rows.ToArray(),
            };

            File.WriteAllText(logitsSnapshotPath, JsonUtility.ToJson(snapshot, true), Encoding.UTF8);

            using (var writer = new StreamWriter(cellTablePath, false, new UTF8Encoding(true)))
            {
                for (int i = 0; i < rows.Count; i++)
                {
                    writer.WriteLine(JsonUtility.ToJson(rows[i]));
                }
            }

            File.WriteAllText(summaryPath, JsonUtility.ToJson(summary, true), Encoding.UTF8);
            File.WriteAllText(reportPath, BuildStage10D10MarkdownReport(summary, logitsSnapshotPath, cellTablePath, summaryPath), Encoding.UTF8);

            Debug.Log("[Week6VisualInspectionRunner] Stage10D.10 global diagnostics written: " + logitsSnapshotPath);
        }

        private List<Stage10D10CellRow> BuildStage10D10CellRows()
        {
            var rows = new List<Stage10D10CellRow>(ActionContract.TotalCells);
            var runtimeByFlat = new Dictionary<int, UnitRuntime>(ActionContract.TotalCells);

            if (_unitRegistry != null)
            {
                List<UnitRuntime> units = _unitRegistry.GetAllUnits();
                for (int i = 0; i < units.Count; i++)
                {
                    UnitRuntime unit = units[i];
                    if (unit == null || !unit.IsAlive)
                    {
                        continue;
                    }

                    int flat = ToFlatIndex(unit.GridPos);
                    runtimeByFlat[flat] = unit;
                }
            }

            Dictionary<int, GlobalCellActionTypeDiagnostic> globalDiagByFlat = BuildGlobalCellDiagnosticsMap();

            for (int flat = 0; flat < ActionContract.TotalCells; flat++)
            {
                GridPosition position = GridPosition.FromFlatIndex(flat);
                UnitRuntime runtimeUnit = null;
                runtimeByFlat.TryGetValue(flat, out runtimeUnit);
                ActorCellDiagnosticRow actorRow = null;
                _latestActorRowsByFlatIndex.TryGetValue(flat, out actorRow);

                GlobalCellActionTypeDiagnostic globalDiag = null;
                globalDiagByFlat.TryGetValue(flat, out globalDiag);

                float[] cellChannels = GetCellObservationChannels(flat, null);
                string decodedOwner = InferOwnerFromChannels(cellChannels);
                string decodedUnitType = InferUnitTypeFromChannelsSafe(cellChannels);

                bool runtimeIsFriendlyActor = runtimeUnit != null
                    && runtimeUnit.Owner == _studentControlledPlayer
                    && runtimeUnit.Type != UnitType.Resource;
                bool runtimeIsFriendlyWorker = runtimeUnit != null
                    && runtimeUnit.Owner == _studentControlledPlayer
                    && runtimeUnit.Type == UnitType.Worker;
                bool runtimeIsFriendlyBase = runtimeUnit != null
                    && runtimeUnit.Owner == _studentControlledPlayer
                    && runtimeUnit.Type == UnitType.Base;
                bool runtimeIsEnemy = runtimeUnit != null
                    && runtimeUnit.Owner != _studentControlledPlayer
                    && runtimeUnit.Owner != Owner.Neutral;
                bool runtimeIsResource = runtimeUnit != null && runtimeUnit.Type == UnitType.Resource;
                bool runtimeIsEmpty = runtimeUnit == null;

                float[] probs = null;
                float[] logits = null;
                ActionTypeTopK[] top3 = null;
                UnitActionType predictedActionType = UnitActionType.NoOp;
                string predictedActionTypeName = UnitActionType.NoOp.ToString();
                float nonNoOpProb = 0f;

                if (globalDiag != null
                    && globalDiag.action_type_probabilities != null
                    && globalDiag.action_type_probabilities.Length == 6
                    && globalDiag.action_type_logits != null
                    && globalDiag.action_type_logits.Length == 6)
                {
                    probs = globalDiag.action_type_probabilities;
                    logits = globalDiag.action_type_logits;
                    top3 = globalDiag.action_type_top3;
                    predictedActionType = ToUnitActionType(globalDiag.predicted_action_type);
                    predictedActionTypeName = string.IsNullOrWhiteSpace(globalDiag.predicted_action_type_name)
                        ? predictedActionType.ToString()
                        : globalDiag.predicted_action_type_name;
                    nonNoOpProb = Mathf.Clamp01(globalDiag.non_noop_probability);
                }
                else
                {
                    int move;
                    int harvest;
                    int ret;
                    int produceDir;
                    int produceType;
                    int attackLocal;
                    ExtractBranchValues(_latestArtifact.ActionFlat, flat, out predictedActionType, out move, out harvest, out ret, out produceDir, out produceType, out attackLocal);
                    predictedActionTypeName = predictedActionType.ToString();
                    nonNoOpProb = predictedActionType == UnitActionType.NoOp ? 0f : 1f;
                }

                int moveDirFinal;
                int harvestDirFinal;
                int returnDirFinal;
                int produceDirFinal;
                int produceUnitTypeFinal;
                int attackTargetLocalFinal;
                UnitActionType ignored;
                ExtractBranchValues(
                    _latestArtifact.ActionFlat,
                    flat,
                    out ignored,
                    out moveDirFinal,
                    out harvestDirFinal,
                    out returnDirFinal,
                    out produceDirFinal,
                    out produceUnitTypeFinal,
                    out attackTargetLocalFinal);

                bool predictedNonNoOp = predictedActionType != UnitActionType.NoOp;
                bool commandBuilt = _lastAcceptedByActor.ContainsKey(flat) || _lastRejectedByActor.ContainsKey(flat);
                string decoderRejectReason = string.Empty;
                string decoderResult = "predicted_noop";
                if (predictedNonNoOp)
                {
                    if (!runtimeIsFriendlyActor)
                    {
                        decoderRejectReason = "non_actor_cell";
                        decoderResult = "predicted_non_noop_on_non_actor_cell";
                        commandBuilt = false;
                    }
                    else if (commandBuilt)
                    {
                        decoderResult = "command_built";
                    }
                    else
                    {
                        decoderRejectReason = ResolveCommandNotBuiltReason(flat, predictedActionType, false);
                        decoderResult = "decoder_blocked";
                    }
                }

                bool applierAccepted = _lastAcceptedByActor.ContainsKey(flat);
                bool applierRejected = _lastRejectedByActor.ContainsKey(flat);
                bool applierSubmitted = commandBuilt;
                string applierRejectReason = string.Empty;
                if (applierRejected && _lastRejectedByActor.TryGetValue(flat, out RuntimeRejectionInfo rejInfo))
                {
                    applierRejectReason = rejInfo.Reason;
                }

                string visualLabel = globalDiag != null && !string.IsNullOrWhiteSpace(globalDiag.logical_label)
                    ? globalDiag.logical_label
                    : ToCellLabel(position);

                var row = new Stage10D10CellRow
                {
                    cell_index = flat,
                    x = position.X,
                    y = position.Y,
                    visual_label = visualLabel,
                    decoded_observation_owner = decodedOwner,
                    decoded_observation_unit_type = decodedUnitType,
                    runtime_is_friendly_actor = runtimeIsFriendlyActor,
                    runtime_is_friendly_worker = runtimeIsFriendlyWorker,
                    runtime_is_friendly_base = runtimeIsFriendlyBase,
                    runtime_is_enemy = runtimeIsEnemy,
                    runtime_is_resource = runtimeIsResource,
                    runtime_is_empty = runtimeIsEmpty,
                    action_type_logits = logits,
                    action_type_probabilities = probs,
                    p_noop = GetProbability(probs, 0),
                    p_move = GetProbability(probs, 1),
                    p_harvest = GetProbability(probs, 2),
                    p_return = GetProbability(probs, 3),
                    p_produce = GetProbability(probs, 4),
                    p_attack = GetProbability(probs, 5),
                    predicted_action_type = predictedActionTypeName,
                    non_noop_prob = nonNoOpProb,
                    top3_action_type_probabilities = top3,
                    move_dir = moveDirFinal,
                    harvest_dir = harvestDirFinal,
                    return_dir = returnDirFinal,
                    produce_dir = produceDirFinal,
                    produce_unit_type = produceUnitTypeFinal,
                    attack_target_local = attackTargetLocalFinal,
                    decoder_result_if_predicted_non_noop = decoderResult,
                    command_built = commandBuilt,
                    decoder_reject_reason = decoderRejectReason,
                    applier_submission_reached = applierSubmitted,
                    applier_submitted = applierSubmitted,
                    applier_accepted = applierAccepted,
                    applier_rejected = applierRejected,
                    applier_reject_reason = applierRejectReason,
                };

                rows.Add(row);
            }

            return rows;
        }

        private Dictionary<int, GlobalCellActionTypeDiagnostic> BuildGlobalCellDiagnosticsMap()
        {
            var map = new Dictionary<int, GlobalCellActionTypeDiagnostic>(ActionContract.TotalCells);
            if (_latestBridgeDebug == null || _latestBridgeDebug.global_cell_action_type_diagnostics == null)
            {
                return map;
            }

            for (int i = 0; i < _latestBridgeDebug.global_cell_action_type_diagnostics.Length; i++)
            {
                GlobalCellActionTypeDiagnostic item = _latestBridgeDebug.global_cell_action_type_diagnostics[i];
                if (item == null)
                {
                    continue;
                }

                if (item.flat_index < 0 || item.flat_index >= ActionContract.TotalCells)
                {
                    continue;
                }

                map[item.flat_index] = item;
            }

            return map;
        }

        private Stage10D10GlobalSummary BuildStage10D10Summary(List<Stage10D10CellRow> rows, int step)
        {
            int totalCells = rows != null ? rows.Count : 0;
            int friendlyActorCount = 0;
            int friendlyWorkerCount = 0;
            int friendlyBaseCount = 0;
            int globalNoOpCount = 0;
            int actorNoOpCount = 0;
            int workerNoOpCount = 0;
            int baseNoOpCount = 0;
            int nonNoOpOnActor = 0;
            int nonNoOpOffActor = 0;
            float maxNonNoOpGlobal = 0f;
            float maxNonNoOpOnActor = 0f;

            var decoderRejectHistogram = new Dictionary<string, int>(StringComparer.Ordinal);
            var applierRejectHistogram = new Dictionary<string, int>(StringComparer.Ordinal);

            for (int i = 0; i < totalCells; i++)
            {
                Stage10D10CellRow row = rows[i];

                if (row.predicted_action_type == UnitActionType.NoOp.ToString())
                {
                    globalNoOpCount++;
                }

                if (row.runtime_is_friendly_actor)
                {
                    friendlyActorCount++;
                    if (row.predicted_action_type == UnitActionType.NoOp.ToString())
                    {
                        actorNoOpCount++;
                    }
                    else
                    {
                        nonNoOpOnActor++;
                    }

                    if (row.non_noop_prob > maxNonNoOpOnActor)
                    {
                        maxNonNoOpOnActor = row.non_noop_prob;
                    }
                }
                else if (row.predicted_action_type != UnitActionType.NoOp.ToString())
                {
                    nonNoOpOffActor++;
                }

                if (row.runtime_is_friendly_worker)
                {
                    friendlyWorkerCount++;
                    if (row.predicted_action_type == UnitActionType.NoOp.ToString())
                    {
                        workerNoOpCount++;
                    }
                }

                if (row.runtime_is_friendly_base)
                {
                    friendlyBaseCount++;
                    if (row.predicted_action_type == UnitActionType.NoOp.ToString())
                    {
                        baseNoOpCount++;
                    }
                }

                if (row.non_noop_prob > maxNonNoOpGlobal)
                {
                    maxNonNoOpGlobal = row.non_noop_prob;
                }

                if (!string.IsNullOrWhiteSpace(row.decoder_reject_reason))
                {
                    IncrementStringCount(decoderRejectHistogram, row.decoder_reject_reason);
                }

                if (row.applier_rejected && !string.IsNullOrWhiteSpace(row.applier_reject_reason))
                {
                    IncrementStringCount(applierRejectHistogram, row.applier_reject_reason);
                }
            }

            string classification = ClassifyStage10D10(
                friendlyActorCount,
                actorNoOpCount,
                nonNoOpOnActor,
                nonNoOpOffActor,
                maxNonNoOpOnActor,
                _totalCommandsBuiltAfterFilter,
                _totalCommandsSubmittedAfterFilter,
                _acceptedStudentCommands,
                applierRejectHistogram.Count);
            string rationale = BuildStage10D10ClassificationRationale(
                classification,
                friendlyActorCount,
                actorNoOpCount,
                nonNoOpOnActor,
                nonNoOpOffActor,
                maxNonNoOpOnActor);

            return new Stage10D10GlobalSummary
            {
                generated_at_utc = DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture),
                step = step,
                total_cells = totalCells,
                friendly_actor_cell_count = friendlyActorCount,
                friendly_worker_count = friendlyWorkerCount,
                friendly_base_count = friendlyBaseCount,
                global_predicted_noop_share = SafeShare(globalNoOpCount, totalCells),
                actor_cell_predicted_noop_share = SafeShare(actorNoOpCount, friendlyActorCount),
                worker_predicted_noop_share = SafeShare(workerNoOpCount, friendlyWorkerCount),
                base_predicted_noop_share = SafeShare(baseNoOpCount, friendlyBaseCount),
                max_non_noop_probability_globally = maxNonNoOpGlobal,
                max_non_noop_probability_on_actor_cells = maxNonNoOpOnActor,
                top_k_non_noop_probability_cells = BuildTopKCells(rows, 8, "non_noop"),
                top_k_harvest_probability_cells = BuildTopKCells(rows, 8, "harvest"),
                top_k_produce_probability_cells = BuildTopKCells(rows, 8, "produce"),
                top_k_attack_probability_cells = BuildTopKCells(rows, 8, "attack"),
                non_noop_predictions_on_actor_cells = nonNoOpOnActor,
                non_noop_predictions_off_actor_cells = nonNoOpOffActor,
                commands_built = _totalCommandsBuiltAfterFilter,
                commands_submitted = _totalCommandsSubmittedAfterFilter,
                commands_accepted = _acceptedStudentCommands,
                decoder_reject_counts_by_reason = BuildReasonCounts(decoderRejectHistogram),
                applier_reject_counts_by_reason = BuildReasonCounts(applierRejectHistogram),
                classification = classification,
                classification_rationale = rationale,
            };
        }

        private static float SafeShare(int numerator, int denominator)
        {
            if (denominator <= 0)
            {
                return 0f;
            }

            return numerator / (float)denominator;
        }

        private static float GetProbability(float[] probabilities, int index)
        {
            if (probabilities == null || probabilities.Length <= index || index < 0)
            {
                return 0f;
            }

            return probabilities[index];
        }

        private static string InferOwnerFromChannels(float[] channels)
        {
            if (channels == null || channels.Length < 5)
            {
                return "Unknown";
            }

            int best = 2;
            float value = float.NegativeInfinity;
            for (int i = 2; i <= 4; i++)
            {
                if (channels[i] > value)
                {
                    value = channels[i];
                    best = i;
                }
            }

            return best switch
            {
                3 => "Player1",
                4 => "Player2",
                _ => "Neutral",
            };
        }

        private static string InferUnitTypeFromChannelsSafe(float[] channels)
        {
            if (channels == null || channels.Length < 12)
            {
                return "Unknown";
            }

            return InferUnitTypeFromChannels(channels);
        }

        private static Stage10D10ReasonCount[] BuildReasonCounts(Dictionary<string, int> histogram)
        {
            if (histogram == null || histogram.Count == 0)
            {
                return Array.Empty<Stage10D10ReasonCount>();
            }

            var entries = new List<KeyValuePair<string, int>>(histogram);
            entries.Sort((left, right) => right.Value.CompareTo(left.Value));

            var result = new Stage10D10ReasonCount[entries.Count];
            for (int i = 0; i < entries.Count; i++)
            {
                result[i] = new Stage10D10ReasonCount
                {
                    reason = entries[i].Key,
                    count = entries[i].Value,
                };
            }

            return result;
        }

        private static Stage10D10TopCell[] BuildTopKCells(List<Stage10D10CellRow> rows, int k, string metric)
        {
            if (rows == null || rows.Count == 0 || k <= 0)
            {
                return Array.Empty<Stage10D10TopCell>();
            }

            var scored = new List<Stage10D10TopCell>(rows.Count);
            for (int i = 0; i < rows.Count; i++)
            {
                Stage10D10CellRow row = rows[i];
                float score = metric switch
                {
                    "harvest" => row.p_harvest,
                    "produce" => row.p_produce,
                    "attack" => row.p_attack,
                    _ => row.non_noop_prob,
                };

                scored.Add(new Stage10D10TopCell
                {
                    cell_index = row.cell_index,
                    x = row.x,
                    y = row.y,
                    visual_label = row.visual_label,
                    runtime_is_friendly_actor = row.runtime_is_friendly_actor,
                    predicted_action_type = row.predicted_action_type,
                    score = score,
                });
            }

            scored.Sort((left, right) =>
            {
                int cmp = right.score.CompareTo(left.score);
                if (cmp != 0)
                {
                    return cmp;
                }

                return left.cell_index.CompareTo(right.cell_index);
            });

            if (scored.Count > k)
            {
                scored.RemoveRange(k, scored.Count - k);
            }

            return scored.ToArray();
        }

        private static string ClassifyStage10D10(
            int friendlyActorCount,
            int actorNoOpCount,
            int nonNoOpOnActor,
            int nonNoOpOffActor,
            float maxNonNoOpOnActor,
            int commandsBuilt,
            int commandsSubmitted,
            int commandsAccepted,
            int applierRejectReasonKinds)
        {
            if (friendlyActorCount <= 0)
            {
                return "ACTOR_CELL_RECOGNITION_FAILURE";
            }

            float actorNoOpShare = SafeShare(actorNoOpCount, friendlyActorCount);
            if (actorNoOpShare >= 0.95f && nonNoOpOnActor == 0 && maxNonNoOpOnActor <= 0.20f)
            {
                return "GLOBAL_NOOP_COLLAPSE";
            }

            if (nonNoOpOnActor == 0 && nonNoOpOffActor > 0)
            {
                return "MEANINGFUL_ACTION_MISLOCALIZATION";
            }

            if (nonNoOpOnActor > 0 && commandsBuilt <= 0)
            {
                return "DECODER_BLOCKED_AFTER_NON_NOOP";
            }

            if (commandsBuilt > 0 && commandsSubmitted > 0 && commandsAccepted <= 0 && applierRejectReasonKinds > 0)
            {
                return "APPLIER_BLOCKED_AFTER_COMMAND_BUILD";
            }

            return "MIXED_OR_INCONCLUSIVE";
        }

        private static string BuildStage10D10ClassificationRationale(
            string classification,
            int friendlyActorCount,
            int actorNoOpCount,
            int nonNoOpOnActor,
            int nonNoOpOffActor,
            float maxNonNoOpOnActor)
        {
            return classification switch
            {
                "ACTOR_CELL_RECOGNITION_FAILURE" => "No friendly runtime actor cells were observed in the sampled step.",
                "GLOBAL_NOOP_COLLAPSE" => "Actor cells are almost entirely NoOp with low non-NoOp probability peaks.",
                "MEANINGFUL_ACTION_MISLOCALIZATION" => "Non-NoOp confidence appears away from runtime actor cells.",
                "DECODER_BLOCKED_AFTER_NON_NOOP" => "Actor cells predict non-NoOp, but decoder does not build commands.",
                "APPLIER_BLOCKED_AFTER_COMMAND_BUILD" => "Commands are built/submitted but not accepted by runtime applier.",
                _ => string.Format(
                    CultureInfo.InvariantCulture,
                    "Mixed evidence: actor_count={0}, actor_noop={1}, actor_non_noop={2}, off_actor_non_noop={3}, max_actor_non_noop_prob={4:F3}.",
                    friendlyActorCount,
                    actorNoOpCount,
                    nonNoOpOnActor,
                    nonNoOpOffActor,
                    maxNonNoOpOnActor),
            };
        }

        private string BuildStage10D10MarkdownReport(
            Stage10D10GlobalSummary summary,
            string logitsSnapshotPath,
            string cellTablePath,
            string summaryPath)
        {
            var lines = new List<string>
            {
                "# STAGE10D10 Global Runtime NoOp Persistence Diagnostic Report",
                string.Empty,
                "- generated_at_utc: " + summary.generated_at_utc,
                "- step: " + summary.step.ToString(CultureInfo.InvariantCulture),
                "- classification: " + summary.classification,
                "- rationale: " + summary.classification_rationale,
                string.Empty,
                "## Required Metrics",
                "- total_cells: " + summary.total_cells.ToString(CultureInfo.InvariantCulture),
                "- friendly_actor_cell_count: " + summary.friendly_actor_cell_count.ToString(CultureInfo.InvariantCulture),
                "- friendly_worker_count: " + summary.friendly_worker_count.ToString(CultureInfo.InvariantCulture),
                "- friendly_base_count: " + summary.friendly_base_count.ToString(CultureInfo.InvariantCulture),
                "- global_predicted_noop_share: " + summary.global_predicted_noop_share.ToString("F6", CultureInfo.InvariantCulture),
                "- actor_cell_predicted_noop_share: " + summary.actor_cell_predicted_noop_share.ToString("F6", CultureInfo.InvariantCulture),
                "- worker_predicted_noop_share: " + summary.worker_predicted_noop_share.ToString("F6", CultureInfo.InvariantCulture),
                "- base_predicted_noop_share: " + summary.base_predicted_noop_share.ToString("F6", CultureInfo.InvariantCulture),
                "- max_non_noop_probability_globally: " + summary.max_non_noop_probability_globally.ToString("F6", CultureInfo.InvariantCulture),
                "- max_non_noop_probability_on_actor_cells: " + summary.max_non_noop_probability_on_actor_cells.ToString("F6", CultureInfo.InvariantCulture),
                "- non_noop_predictions_on_actor_cells: " + summary.non_noop_predictions_on_actor_cells.ToString(CultureInfo.InvariantCulture),
                "- non_noop_predictions_off_actor_cells: " + summary.non_noop_predictions_off_actor_cells.ToString(CultureInfo.InvariantCulture),
                "- commands_built: " + summary.commands_built.ToString(CultureInfo.InvariantCulture),
                "- commands_submitted: " + summary.commands_submitted.ToString(CultureInfo.InvariantCulture),
                "- commands_accepted: " + summary.commands_accepted.ToString(CultureInfo.InvariantCulture),
                string.Empty,
                "## Top-K Non-NoOp Cells",
            };

            AppendTopCells(lines, summary.top_k_non_noop_probability_cells);
            lines.Add(string.Empty);
            lines.Add("## Top-K Harvest Probability Cells");
            AppendTopCells(lines, summary.top_k_harvest_probability_cells);
            lines.Add(string.Empty);
            lines.Add("## Top-K Produce Probability Cells");
            AppendTopCells(lines, summary.top_k_produce_probability_cells);
            lines.Add(string.Empty);
            lines.Add("## Top-K Attack Probability Cells");
            AppendTopCells(lines, summary.top_k_attack_probability_cells);
            lines.Add(string.Empty);
            lines.Add("## Decoder Reject Counts");
            AppendReasonCounts(lines, summary.decoder_reject_counts_by_reason);
            lines.Add(string.Empty);
            lines.Add("## Applier Reject Counts");
            AppendReasonCounts(lines, summary.applier_reject_counts_by_reason);
            lines.Add(string.Empty);
            lines.Add("## Artifact Paths");
            lines.Add("- logits_snapshot_json: " + logitsSnapshotPath);
            lines.Add("- cell_table_jsonl: " + cellTablePath);
            lines.Add("- summary_json: " + summaryPath);

            return string.Join("\n", lines) + "\n";
        }

        private static void AppendTopCells(List<string> lines, Stage10D10TopCell[] cells)
        {
            if (cells == null || cells.Length == 0)
            {
                lines.Add("- none");
                return;
            }

            for (int i = 0; i < cells.Length; i++)
            {
                Stage10D10TopCell cell = cells[i];
                lines.Add(string.Format(
                    CultureInfo.InvariantCulture,
                    "- cell={0} ({1},{2}) label={3}, score={4:F6}, predicted={5}, runtime_actor={6}",
                    cell.cell_index,
                    cell.x,
                    cell.y,
                    string.IsNullOrWhiteSpace(cell.visual_label) ? "n/a" : cell.visual_label,
                    cell.score,
                    string.IsNullOrWhiteSpace(cell.predicted_action_type) ? "n/a" : cell.predicted_action_type,
                    cell.runtime_is_friendly_actor));
            }
        }

        private static void AppendReasonCounts(List<string> lines, Stage10D10ReasonCount[] counts)
        {
            if (counts == null || counts.Length == 0)
            {
                lines.Add("- none");
                return;
            }

            for (int i = 0; i < counts.Length; i++)
            {
                Stage10D10ReasonCount item = counts[i];
                if (item == null)
                {
                    continue;
                }

                lines.Add("- " + item.reason + ": " + item.count.ToString(CultureInfo.InvariantCulture));
            }
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
            _ignoredStudentCommands = 0;
            _totalCommandsBuiltAfterFilter = 0;
            _totalCommandsSubmittedAfterFilter = 0;
            _totalWrongOwnerAfterFilter = 0;
            _totalCandidateCells = 0;
            _totalEligibleOwnActorCells = 0;
            _totalFallbackToNoop = 0;
            _totalMaskedOutActionChoices = 0;
            _lastStepApplyCommandCalled = false;
            _lastStepActionApplierReached = false;
            _lastStepSnapshotReady = false;
            _lastSnapshotPath = string.Empty;
            _lastCollectedEpisode = -1;
            _lastCollectedStep = -1;
            _lastTerminalReason = "none";
            _terminalReportWritten = false;
            _autoPlaybackRunning = false;
            _autoPlaybackRemainingSteps = 0;
            _lastAutoPlaybackStep = 0;
            _latestObservationValues = Array.Empty<float>();
            _latestBridgeDebug = null;
            _latestInferenceDiagnostics = null;
            _flattenAlignmentClassification = "INCONCLUSIVE_NEEDS_MORE_LOGITS";

            _baselineOwner = _studentControlledPlayer == Owner.Player1 ? Owner.Player2 : Owner.Player1;
            _baselineLastActionType = UnitActionType.NoOp;
            _baselineLastProduceType = ProducibleUnit.Worker;
            _baselineLastAccepted = false;
            _baselineLastReason = "none";
            _baselineLastCommandSummary = "none";
            _baselineAcceptedCount = 0;
            _baselineRejectedCount = 0;

            _rejectionReasons.Clear();
            _runtimeRejectionReasons.Clear();
            _latestActorRowsByFlatIndex.Clear();
            _latestActorRows.Clear();
            _lastAcceptedByActor.Clear();
            _lastRejectedByActor.Clear();
            _lastBaselineAcceptedByActor.Clear();
            _lastBaselineRejectedByActor.Clear();

            ResetActionHistogram(_aggregateActionTypeHistogram);
            ResetActionHistogram(_aggregateActorActionTypeHistogram);
        }

        private void ResolveReferences()
        {
            _episodeController = EpisodeController.Instance ?? FindFirstObjectByType<EpisodeController>();
            _matchManager = MatchManager.Instance ?? FindFirstObjectByType<MatchManager>();
            _matchBootstrap = MatchBootstrap.Instance ?? FindFirstObjectByType<MatchBootstrap>();
            _gridManager = GridManager.Instance ?? FindFirstObjectByType<GridManager>();
            _unitRegistry = UnitRegistry.Instance ?? FindFirstObjectByType<UnitRegistry>();
            _resourceManager = ResourceManager.Instance ?? FindFirstObjectByType<ResourceManager>();
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

            if (command.Owner == _studentControlledPlayer)
            {
                int flat = ToFlatIndex(command.UnitPosition);
                _lastAcceptedByActor[flat] = command;
                _lastStepApplyCommandCalled = true;
            }
            else
            {
                int flat = ToFlatIndex(command.UnitPosition);
                _lastBaselineAcceptedByActor[flat] = command;
                _baselineAcceptedCount++;
                _baselineLastCommandSummary = BuildCommandSummary(command, accepted: true, "none");
            }
        }

        private void HandleCommandRejected(MatchCommand command, string reason)
        {
            if (!_sessionActive)
            {
                return;
            }

            _diagnosticsCollector?.RecordRuntimeRejected(command, reason);

            if (command.Owner != _studentControlledPlayer)
            {
                int baselineFlat = ToFlatIndex(command.UnitPosition);
                _lastBaselineRejectedByActor[baselineFlat] = new RuntimeRejectionInfo(NormalizeReason(reason));
                _baselineRejectedCount++;
                _baselineLastCommandSummary = BuildCommandSummary(command, accepted: false, NormalizeReason(reason));
                return;
            }

            _runtimeRejectedStudentCommands++;
            _ignoredStudentCommands = _runtimeRejectedStudentCommands;
            _lastStepApplyCommandCalled = true;

            int flat = ToFlatIndex(command.UnitPosition);
            _lastRejectedByActor[flat] = new RuntimeRejectionInfo(NormalizeReason(reason));
            IncrementStringCount(_runtimeRejectionReasons, NormalizeReason(reason));
        }

        private void HandleHeuristicActionEvaluated(HeuristicActionEvaluation evaluation)
        {
            if (!_sessionActive)
            {
                return;
            }

            _diagnosticsCollector?.RecordHeuristicActionEvaluation(evaluation);

            if (evaluation.PlayerId == _studentControlledPlayer)
            {
                return;
            }

            _baselineOwner = evaluation.PlayerId;
            _baselineLastActionType = evaluation.ActionType;
            _baselineLastProduceType = evaluation.ProduceUnitType;
            _baselineLastAccepted = evaluation.Accepted;
            _baselineLastReason = string.IsNullOrWhiteSpace(evaluation.RejectionReason)
                ? "none"
                : NormalizeReason(evaluation.RejectionReason);
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

        private void HandleKeyboardShortcuts()
        {
            if (!Application.isPlaying)
            {
                return;
            }

            if (GetKeyDownCompat(KeyCode.D))
            {
                _showOverlay = !_showOverlay;
            }

            if (GetKeyDownCompat(KeyCode.G))
            {
                _showGridLabels = !_showGridLabels;
            }

            if (GetKeyDownCompat(KeyCode.A))
            {
                _showActionMarkers = !_showActionMarkers;
            }

            if (GetKeyDownCompat(KeyCode.Space))
            {
                StopAutoPlayback();
                TogglePauseResume();
            }

            if (GetKeyDownCompat(KeyCode.N) || GetKeyDownCompat(KeyCode.RightArrow))
            {
                StopAutoPlayback();
                StepManualOnce();
            }

            if (GetKeyDownCompat(KeyCode.R))
            {
                StopAutoPlayback();
                RestartVisualInspectionMatch();
            }

            if (GetKeyDownCompat(KeyCode.L))
            {
                DumpCurrentStepDiagnostics();
            }
        }

        private bool GetKeyDownCompat(KeyCode key)
        {
#if ENABLE_INPUT_SYSTEM
            if (Keyboard.current != null && TryGetInputSystemKeyDown(key, out bool isPressed))
            {
                return isPressed;
            }
#endif

            if (_legacyInputUnavailable)
            {
                return false;
            }

            try
            {
                return Input.GetKeyDown(key);
            }
            catch (InvalidOperationException)
            {
                _legacyInputUnavailable = true;
                return false;
            }
        }

#if ENABLE_INPUT_SYSTEM
        private static bool TryGetInputSystemKeyDown(KeyCode key, out bool isPressed)
        {
            isPressed = false;
            Keyboard keyboard = Keyboard.current;
            if (keyboard == null)
            {
                return false;
            }

            switch (key)
            {
                case KeyCode.D:
                    isPressed = keyboard.dKey.wasPressedThisFrame;
                    return true;
                case KeyCode.G:
                    isPressed = keyboard.gKey.wasPressedThisFrame;
                    return true;
                case KeyCode.A:
                    isPressed = keyboard.aKey.wasPressedThisFrame;
                    return true;
                case KeyCode.Space:
                    isPressed = keyboard.spaceKey.wasPressedThisFrame;
                    return true;
                case KeyCode.N:
                    isPressed = keyboard.nKey.wasPressedThisFrame;
                    return true;
                case KeyCode.RightArrow:
                    isPressed = keyboard.rightArrowKey.wasPressedThisFrame;
                    return true;
                case KeyCode.R:
                    isPressed = keyboard.rKey.wasPressedThisFrame;
                    return true;
                case KeyCode.L:
                    isPressed = keyboard.lKey.wasPressedThisFrame;
                    return true;
                default:
                    return false;
            }
        }
#endif

        private void UpdateAutoPlayback()
        {
            if (!_autoPlaybackRunning || !_sessionActive || _episodeController == null)
            {
                return;
            }

            if (_episodeController.LastTerminalReport.IsTerminal)
            {
                StopAutoPlayback();
                return;
            }

            if (_autoPlaybackRemainingSteps <= 0)
            {
                StopAutoPlayback();
                return;
            }

            if (Time.time < _nextAutoPlaybackAt)
            {
                return;
            }

            int before = GetCurrentStep();
            StepManualOnce();
            int after = GetCurrentStep();
            _autoPlaybackRemainingSteps--;
            _nextAutoPlaybackAt = Time.time + Mathf.Max(0.05f, _autoVisualPlaybackStepIntervalSeconds);

            if (after <= before)
            {
                StopAutoPlayback();
            }
        }

        private void EnsureSessionForPlayback()
        {
            if (_sessionActive)
            {
                return;
            }

            StartVisualInspectionMatch(pauseBeforeFirstDecision: true);
        }

        private void StopAutoPlayback()
        {
            _autoPlaybackRunning = false;
            _autoPlaybackRemainingSteps = 0;
        }

        private void ApplyVisualScaleOverrides()
        {
            if (!_applyBaseVisualScaleOverrideInInspection || _unitRegistry == null)
            {
                return;
            }

            float cellScale = Mathf.Clamp(_baseVisualCellScale, 0.5f, 1.0f);
            List<UnitRuntime> units = _unitRegistry.GetAllUnits();
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit == null || !unit.IsAlive || unit.Type != UnitType.Base)
                {
                    continue;
                }

                Vector3 current = unit.transform.localScale;
                unit.transform.localScale = new Vector3(cellScale, current.y, cellScale);
            }
        }

        private void RefreshLatestDiagnosticsFromArtifacts()
        {
            ResolveReferences();
            _latestObservation = CaptureObservationSnapshot();
            _latestInferenceDiagnostics = _studentAdapter != null
                ? _studentAdapter.GetInferenceDiagnosticsSnapshot()
                : null;

            string artifactDirRel = GetPrivateField(_studentAdapter, "_artifactDirectoryRelativePath", "python/week6_student/tmp/day5_sanity");
            string artifactPrefix = GetPrivateField(_studentAdapter, "_artifactFilePrefix", "day5_sanity");
            string projectRoot = Directory.GetParent(Application.dataPath).FullName;
            string fallbackOutputJsonPath = _latestInferenceDiagnostics != null
                ? _latestInferenceDiagnostics.last_output_json_path
                : string.Empty;

            if (!TryReadLatestAdapterArtifact(projectRoot, artifactDirRel, artifactPrefix, fallbackOutputJsonPath, out AdapterArtifactSnapshot artifact))
            {
                _latestArtifact = default;
                _latestBridgeDebug = null;
                return;
            }

            _latestArtifact = artifact;
            _latestBridgeDebug = artifact.Stage10RDebug;
        }

        private void BuildActorRowsForOverlay()
        {
            _latestActorRowsByFlatIndex.Clear();
            _latestActorRows.Clear();

            _noOpActorCells = 0;
            _nonNoOpActorCells = 0;
            _nonActorNonNoOpCells = 0;
            _b2TopAction = "n/a";
            _c3TopAction = "n/a";

            var actorFlats = new HashSet<int>();
            if (_unitRegistry != null)
            {
                List<UnitRuntime> ownUnits = _unitRegistry.GetUnitsByOwner(_studentControlledPlayer);
                for (int i = 0; i < ownUnits.Count; i++)
                {
                    UnitRuntime unit = ownUnits[i];
                    if (unit == null || !unit.IsAlive)
                    {
                        continue;
                    }

                    int flat = ToFlatIndex(unit.GridPos);
                    actorFlats.Add(flat);

                    UnitActionType predicted = UnitActionType.NoOp;
                    int move = 0;
                    int harvest = 0;
                    int ret = 0;
                    int produceDir = 0;
                    int produceType = 0;
                    int attackLocal = 24;

                    if (_latestArtifact.IsAvailable)
                    {
                        ExtractBranchValues(_latestArtifact.ActionFlat, flat, out predicted, out move, out harvest, out ret, out produceDir, out produceType, out attackLocal);
                    }

                    string predictedActionSource = _latestArtifact.IsAvailable
                        ? "model_action_flat_argmax"
                        : "fallback_no_adapter_artifact";

                    bool commandBuilt = _lastAcceptedByActor.ContainsKey(flat) || _lastRejectedByActor.ContainsKey(flat);
                    bool actionApplierReached = commandBuilt;
                    bool applyCommandReached = commandBuilt;
                    string reason = ResolveCommandNotBuiltReason(flat, predicted, commandBuilt);
                    string top3 = "unavailable";
                    bool logitsAvailable = false;
                    string logitsUnavailableReason = "bridge payload missing";
                    float[] actionTypeLogits = null;
                    float[] actionTypeProbabilities = null;
                    ActionTypeTopK[] actionTypeTop3 = null;
                    float noopProbability = 0f;
                    float bestNonNoopProbability = 0f;
                    float noopMargin = 0f;
                    float[] cellObservationChannels = null;
                    string[] observationChannelNames = null;
                    string ownerLabel = unit.Owner.ToString();

                    FocusCellBridgeDiagnostic focus = FindFocusCellDiagnostic(flat);
                    if (focus != null)
                    {
                        logitsAvailable = focus.action_type_logits != null
                            && focus.action_type_probabilities != null
                            && focus.action_type_top3 != null
                            && focus.action_type_logits.Length == 6
                            && focus.action_type_probabilities.Length == 6;
                        logitsUnavailableReason = logitsAvailable ? string.Empty : "bridge payload missing";
                        actionTypeLogits = focus.action_type_logits;
                        actionTypeProbabilities = focus.action_type_probabilities;
                        actionTypeTop3 = focus.action_type_top3;
                        noopProbability = focus.noop_probability;
                        bestNonNoopProbability = focus.best_non_noop_probability;
                        noopMargin = focus.noop_margin;
                        cellObservationChannels = focus.cell_observation_channels;
                        observationChannelNames = _latestBridgeDebug != null ? _latestBridgeDebug.observation_channel_names : null;
                        top3 = BuildTop3Label(focus.action_type_top3);
                        ownerLabel = string.IsNullOrWhiteSpace(focus.owner_guess) ? ownerLabel : focus.owner_guess;
                        if (logitsAvailable)
                        {
                            predictedActionSource = "model_logits";
                        }
                    }

                    var row = new ActorCellDiagnosticRow
                    {
                        Unit = unit,
                        FlatIndex = flat,
                        LogicalCell = ToCellLabel(unit.GridPos),
                        Eligible = true,
                        PredictedActionType = predicted,
                        PredictedActionTypeSource = predictedActionSource,
                        MoveDir = move,
                        HarvestDir = harvest,
                        ReturnDir = ret,
                        ProduceDir = produceDir,
                        ProduceUnitType = produceType,
                        AttackTargetLocal = attackLocal,
                        CommandBuilt = commandBuilt,
                        ActionApplierReached = actionApplierReached,
                        ApplyCommandReached = applyCommandReached,
                        CommandNotBuiltReason = reason,
                        Top3ActionType = top3,
                        Owner = ownerLabel,
                        LogitsAvailable = logitsAvailable,
                        LogitsUnavailableReason = logitsUnavailableReason,
                        ActionTypeLogits = actionTypeLogits,
                        ActionTypeProbabilities = actionTypeProbabilities,
                        ActionTypeTop3 = actionTypeTop3,
                        NoopProbability = noopProbability,
                        BestNonNoopProbability = bestNonNoopProbability,
                        NoopMargin = noopMargin,
                        CellObservationChannels = cellObservationChannels,
                        ObservationChannelNames = observationChannelNames,
                    };

                    _latestActorRowsByFlatIndex[flat] = row;
                    _latestActorRows.Add(row);

                    if (predicted == UnitActionType.NoOp)
                    {
                        _noOpActorCells++;
                    }
                    else
                    {
                        _nonNoOpActorCells++;
                    }
                }
            }

            _latestActorRows.Sort((left, right) => left.FlatIndex.CompareTo(right.FlatIndex));

            if (_latestArtifact.IsAvailable)
            {
                for (int flat = 0; flat < ActionContract.TotalCells; flat++)
                {
                    UnitActionType actionType;
                    int move;
                    int harvest;
                    int ret;
                    int produceDir;
                    int produceType;
                    int attackLocal;
                    ExtractBranchValues(_latestArtifact.ActionFlat, flat, out actionType, out move, out harvest, out ret, out produceDir, out produceType, out attackLocal);
                    if (!actorFlats.Contains(flat) && actionType != UnitActionType.NoOp)
                    {
                        _nonActorNonNoOpCells++;
                    }

                    if (flat == FocusFlatWorkerB2)
                    {
                        _b2TopAction = ResolveTopActionLabel(flat, actionType.ToString());
                    }

                    if (flat == FocusFlatBaseC3)
                    {
                        _c3TopAction = ResolveTopActionLabel(flat, actionType.ToString());
                    }
                }
            }

            _flattenAlignmentClassification = BuildFlattenClassification();

            if (_flattenAlignmentClassification == "FLATTEN_OR_CELL_ALIGNMENT_MISMATCH")
            {
                _noOpProbeClassification = _flattenAlignmentClassification;
            }
            else if (_noOpActorCells == _latestActorRows.Count && _latestActorRows.Count > 0)
            {
                _noOpProbeClassification = "INCONCLUSIVE_NEEDS_MORE_LOGITS";
            }
            else if (_nonNoOpActorCells > 0 && _totalCommandsBuiltAfterFilter == 0)
            {
                _noOpProbeClassification = "POSTPROCESS_DECODER_FILTER_ISSUE";
            }
            else if (_totalCommandsBuiltAfterFilter > 0 && _runtimeRejectedStudentCommands > 0)
            {
                _noOpProbeClassification = "RUNTIME_APPLIER_SEMANTICS_ISSUE";
            }
            else
            {
                _noOpProbeClassification = "INDETERMINATE";
            }
        }

        private List<UnitSnapshot> BuildUnitSnapshots()
        {
            var units = new List<UnitSnapshot>();
            if (_unitRegistry == null)
            {
                return units;
            }

            List<UnitRuntime> all = _unitRegistry.GetAllUnits();
            for (int i = 0; i < all.Count; i++)
            {
                UnitRuntime unit = all[i];
                if (unit == null || !unit.IsAlive)
                {
                    continue;
                }

                units.Add(new UnitSnapshot
                {
                    owner = unit.Owner.ToString(),
                    unit_type = unit.Type.ToString(),
                    x = unit.GridPos.X,
                    y = unit.GridPos.Y,
                    logical_cell = ToCellLabel(unit.GridPos),
                    flat_index = ToFlatIndex(unit.GridPos),
                });
            }

            return units;
        }

        private List<ActorCellSnapshot> BuildActorCellSnapshots()
        {
            var snapshots = new List<ActorCellSnapshot>(_latestActorRows.Count);
            for (int i = 0; i < _latestActorRows.Count; i++)
            {
                ActorCellDiagnosticRow row = _latestActorRows[i];
                snapshots.Add(new ActorCellSnapshot
                {
                    unit_type = row.Unit != null ? row.Unit.Type.ToString() : "Unknown",
                    grid_position = row.Unit != null ? $"({row.Unit.GridPos.X},{row.Unit.GridPos.Y})" : "(?,?)",
                    logical_cell = row.LogicalCell,
                    flat_index = row.FlatIndex,
                    eligible = row.Eligible,
                    predicted_action_type = row.PredictedActionType.ToString(),
                    predicted_action_type_source = string.IsNullOrWhiteSpace(row.PredictedActionTypeSource) ? "unavailable" : row.PredictedActionTypeSource,
                    top3_action_type = row.Top3ActionType,
                    move_dir = row.MoveDir,
                    harvest_dir = row.HarvestDir,
                    return_dir = row.ReturnDir,
                    produce_dir = row.ProduceDir,
                    produce_unit_type = row.ProduceUnitType,
                    attack_target_local = row.AttackTargetLocal,
                    command_built = row.CommandBuilt,
                    command_not_built_reason = row.CommandNotBuiltReason,
                    action_applier_reached = row.ActionApplierReached,
                    apply_command_reached = row.ApplyCommandReached,
                    owner = row.Owner,
                    logits_probabilities_available = row.LogitsAvailable,
                    logits_probabilities_unavailable_reason = row.LogitsAvailable ? string.Empty : row.LogitsUnavailableReason,
                    action_type_logits = row.ActionTypeLogits,
                    action_type_probabilities = row.ActionTypeProbabilities,
                    action_type_top3 = row.ActionTypeTop3,
                    noop_probability = row.NoopProbability,
                    best_non_noop_probability = row.BestNonNoopProbability,
                    noop_margin = row.NoopMargin,
                    cell_observation_channels = row.CellObservationChannels,
                    observation_channel_names = row.ObservationChannelNames,
                });
            }

            return snapshots;
        }

        private List<FocusCellSnapshot> BuildFocusCellSnapshots()
        {
            var focus = new List<FocusCellSnapshot>(2);
            AddFocusCellSnapshot(focus, FocusFlatWorkerB2, "B2");
            AddFocusCellSnapshot(focus, FocusFlatBaseC3, "C3");
            return focus;
        }

        private void AddFocusCellSnapshot(List<FocusCellSnapshot> focus, int flatIndex, string logicalLabel)
        {
            if (focus == null)
            {
                return;
            }

            ActorCellDiagnosticRow row = null;
            _latestActorRowsByFlatIndex.TryGetValue(flatIndex, out row);
            FocusCellBridgeDiagnostic bridge = FindFocusCellDiagnostic(flatIndex);

            GridPosition position = GridPosition.FromFlatIndex(flatIndex);
            string predicted = row != null ? row.PredictedActionType.ToString() : "NoOp";
            string predictedSource = row != null && !string.IsNullOrWhiteSpace(row.PredictedActionTypeSource)
                ? row.PredictedActionTypeSource
                : (_latestArtifact.IsAvailable ? "model_action_flat_argmax" : "fallback_no_adapter_artifact");
            bool logitsAvailable = row != null && row.LogitsAvailable;

            focus.Add(new FocusCellSnapshot
            {
                logical_label = logicalLabel,
                grid_position = new[] { position.X, position.Y },
                flat_index = flatIndex,
                unit_type = row != null && row.Unit != null ? row.Unit.Type.ToString() : (bridge != null ? bridge.unit_type_guess : "Unknown"),
                owner = row != null ? row.Owner : (bridge != null ? bridge.owner_guess : "Unknown"),
                eligible_actor = row != null ? row.Eligible : (bridge != null && bridge.eligible_actor_guess),
                predicted_action_type = predicted,
                predicted_action_type_source = predictedSource,
                logits_probabilities_available = logitsAvailable,
                logits_probabilities_unavailable_reason = logitsAvailable ? string.Empty : "bridge payload missing",
                action_type_logits = row != null ? row.ActionTypeLogits : null,
                action_type_probabilities = row != null ? row.ActionTypeProbabilities : null,
                action_type_top3 = row != null ? row.ActionTypeTop3 : null,
                noop_probability = row != null ? row.NoopProbability : 0f,
                best_non_noop_probability = row != null ? row.BestNonNoopProbability : 0f,
                noop_margin = row != null ? row.NoopMargin : 0f,
                move_dir = row != null ? row.MoveDir : (bridge != null ? bridge.move_dir : 0),
                harvest_dir = row != null ? row.HarvestDir : (bridge != null ? bridge.harvest_dir : 0),
                return_dir = row != null ? row.ReturnDir : (bridge != null ? bridge.return_dir : 0),
                produce_dir = row != null ? row.ProduceDir : (bridge != null ? bridge.produce_dir : 0),
                produce_unit_type = row != null ? row.ProduceUnitType : (bridge != null ? bridge.produce_unit_type : 0),
                attack_target_local = row != null ? row.AttackTargetLocal : (bridge != null ? bridge.attack_target_local : 0),
                command_built = row != null && row.CommandBuilt,
                command_not_built_reason = row != null ? row.CommandNotBuiltReason : "unavailable",
                cell_observation_channels = GetCellObservationChannels(flatIndex, bridge),
                observation_channel_names = GetObservationChannelNames(),
            });
        }

        private string[] BuildFlattenAlignmentLines()
        {
            var lines = new List<string>();
            int b2Expected = (1 * ObservationContract.GridW) + 1;
            int c3Expected = (2 * ObservationContract.GridW) + 2;
            lines.Add($"B2 formula check: expected={b2Expected}, actual={FocusFlatWorkerB2}, pass={b2Expected == FocusFlatWorkerB2}");
            lines.Add($"C3 formula check: expected={c3Expected}, actual={FocusFlatBaseC3}, pass={c3Expected == FocusFlatBaseC3}");

            lines.Add("B2 observation unit alignment: " + BuildFocusUnitAlignmentLine(FocusFlatWorkerB2, "Worker"));
            lines.Add("C3 observation unit alignment: " + BuildFocusUnitAlignmentLine(FocusFlatBaseC3, "Base"));

            lines.Add("B2 predicted row alignment: pass=" + (_latestActorRowsByFlatIndex.ContainsKey(FocusFlatWorkerB2)).ToString());
            lines.Add("C3 predicted row alignment: pass=" + (_latestActorRowsByFlatIndex.ContainsKey(FocusFlatBaseC3)).ToString());

            if (_latestBridgeDebug != null && _latestBridgeDebug.flatten_alignment_checks != null)
            {
                for (int i = 0; i < _latestBridgeDebug.flatten_alignment_checks.Length; i++)
                {
                    FlattenAlignmentCheck check = _latestBridgeDebug.flatten_alignment_checks[i];
                    if (check == null)
                    {
                        continue;
                    }

                    string expected = !string.IsNullOrWhiteSpace(check.expected_text)
                        ? check.expected_text
                        : check.expected.ToString(CultureInfo.InvariantCulture);
                    string actual = !string.IsNullOrWhiteSpace(check.actual_text)
                        ? check.actual_text
                        : check.actual.ToString(CultureInfo.InvariantCulture);
                    lines.Add($"bridge::{check.check}: pass={check.pass}, expected={expected}, actual={actual}");
                }
            }

            return lines.ToArray();
        }

        private string[] BuildObservationVsBcLines()
        {
            var lines = new List<string>();
            if (_latestBridgeDebug == null || _latestBridgeDebug.observation_vs_bc_expectation == null || _latestBridgeDebug.observation_vs_bc_expectation.Length == 0)
            {
                lines.Add("observation_vs_bc: unavailable (bridge payload missing)");
                return lines.ToArray();
            }

            for (int i = 0; i < _latestBridgeDebug.observation_vs_bc_expectation.Length; i++)
            {
                ObservationVsBcExpectation item = _latestBridgeDebug.observation_vs_bc_expectation[i];
                if (item == null)
                {
                    continue;
                }

                lines.Add(
                    $"{item.logical_label}: unit={item.unit_type_guess}, owner={item.owner_guess}, " +
                    $"unitChannelOk={item.expected_unit_channel_active}, ownerChannelOk={item.owner_channel_active}, suspicious={item.suspicious}");
            }

            return lines.ToArray();
        }

        private string[] BuildOwnActorSummaryLines()
        {
            var lines = new List<string>();
            if (_latestBridgeDebug == null || _latestBridgeDebug.own_actor_action_type_summary == null)
            {
                lines.Add("own_actor_summary: unavailable (bridge payload missing)");
                return lines.ToArray();
            }

            for (int i = 0; i < _latestBridgeDebug.own_actor_action_type_summary.Length; i++)
            {
                OwnActorActionSummary row = _latestBridgeDebug.own_actor_action_type_summary[i];
                if (row == null)
                {
                    continue;
                }

                lines.Add(
                    $"flat={row.flat_index} {row.logical_label}: top1={row.predicted_action_type_name} ({row.top1_probability.ToString("F4", CultureInfo.InvariantCulture)}), " +
                    $"top2={row.top2_action_type_name} ({row.top2_probability.ToString("F4", CultureInfo.InvariantCulture)}), " +
                    $"noop_margin={row.noop_margin.ToString("F4", CultureInfo.InvariantCulture)}");
            }

            return lines.ToArray();
        }

        private string ClassifyRootCause()
        {
            if (_flattenAlignmentClassification == "FLATTEN_OR_CELL_ALIGNMENT_MISMATCH")
            {
                return _flattenAlignmentClassification;
            }

            ActorCellDiagnosticRow b2 = null;
            ActorCellDiagnosticRow c3 = null;
            _latestActorRowsByFlatIndex.TryGetValue(FocusFlatWorkerB2, out b2);
            _latestActorRowsByFlatIndex.TryGetValue(FocusFlatBaseC3, out c3);

            bool bothNoop = b2 != null && c3 != null
                && b2.PredictedActionType == UnitActionType.NoOp
                && c3.PredictedActionType == UnitActionType.NoOp;

            bool highNoopConfidence = b2 != null && c3 != null
                && b2.LogitsAvailable && c3.LogitsAvailable
                && b2.NoopProbability >= 0.50f && c3.NoopProbability >= 0.50f;

            bool observationSuspicious = false;
            if (_latestBridgeDebug != null && _latestBridgeDebug.observation_vs_bc_expectation != null)
            {
                for (int i = 0; i < _latestBridgeDebug.observation_vs_bc_expectation.Length; i++)
                {
                    ObservationVsBcExpectation item = _latestBridgeDebug.observation_vs_bc_expectation[i];
                    if (item != null && item.suspicious)
                    {
                        observationSuspicious = true;
                        break;
                    }
                }
            }

            if (bothNoop && observationSuspicious)
            {
                return "OBSERVATION_ENCODING_MISMATCH_CAUSES_NOOP";
            }

            if (bothNoop && highNoopConfidence)
            {
                return "MODEL_CONFIDENT_NOOP_ON_UNITY_OBSERVATION";
            }

            if (b2 != null && c3 != null)
            {
                bool predictsAnyNonNoop = b2.PredictedActionType != UnitActionType.NoOp || c3.PredictedActionType != UnitActionType.NoOp;
                if (predictsAnyNonNoop && _totalCommandsBuiltAfterFilter == 0)
                {
                    return "POSTPROCESS_DECODER_FILTER_ISSUE";
                }
            }

            if (_totalCommandsBuiltAfterFilter > 0 && _runtimeRejectedStudentCommands > 0)
            {
                return "RUNTIME_APPLIER_SEMANTICS_ISSUE";
            }

            return "INCONCLUSIVE_NEEDS_MORE_LOGITS";
        }

        private static string ClassifyDecision(string rootCause)
        {
            return rootCause switch
            {
                "MODEL_CONFIDENT_NOOP_ON_UNITY_OBSERVATION" => "GO_FOR_MODEL_DATA_REMEDIATION",
                "OBSERVATION_ENCODING_MISMATCH_CAUSES_NOOP" => "GO_FOR_OBSERVATION_REMEDIATION",
                "FLATTEN_OR_CELL_ALIGNMENT_MISMATCH" => "GO_FOR_OBSERVATION_REMEDIATION",
                "POSTPROCESS_DECODER_FILTER_ISSUE" => "GO_FOR_POSTPROCESS_REMEDIATION",
                "RUNTIME_APPLIER_SEMANTICS_ISSUE" => "GO_FOR_RUNTIME_SEMANTICS_REMEDIATION",
                _ => "GO_FOR_NEXT_DIAGNOSTIC",
            };
        }

        private string BuildFlattenClassification()
        {
            bool mismatch = false;
            if (_latestBridgeDebug != null && _latestBridgeDebug.flatten_alignment_checks != null)
            {
                for (int i = 0; i < _latestBridgeDebug.flatten_alignment_checks.Length; i++)
                {
                    FlattenAlignmentCheck check = _latestBridgeDebug.flatten_alignment_checks[i];
                    if (check != null && !check.pass)
                    {
                        mismatch = true;
                        break;
                    }
                }
            }

            if (BuildFocusUnitAlignmentLine(FocusFlatWorkerB2, "Worker").IndexOf("pass=True", StringComparison.Ordinal) < 0)
            {
                mismatch = true;
            }

            if (BuildFocusUnitAlignmentLine(FocusFlatBaseC3, "Base").IndexOf("pass=True", StringComparison.Ordinal) < 0)
            {
                mismatch = true;
            }

            return mismatch ? "FLATTEN_OR_CELL_ALIGNMENT_MISMATCH" : "FLATTEN_ALIGNMENT_OK";
        }

        private string BuildFocusUnitAlignmentLine(int flatIndex, string expectedUnit)
        {
            float[] channels = GetCellObservationChannels(flatIndex, FindFocusCellDiagnostic(flatIndex));
            if (channels == null || channels.Length < 12)
            {
                return "pass=False, reason=observation_slice_missing";
            }

            string actual = InferUnitTypeFromChannels(channels);
            bool pass = string.Equals(actual, expectedUnit, StringComparison.Ordinal);
            return $"expected={expectedUnit}, actual={actual}, pass={pass}";
        }

        private FocusCellBridgeDiagnostic FindFocusCellDiagnostic(int flatIndex)
        {
            if (_latestBridgeDebug == null || _latestBridgeDebug.focus_cells == null)
            {
                return null;
            }

            for (int i = 0; i < _latestBridgeDebug.focus_cells.Length; i++)
            {
                FocusCellBridgeDiagnostic cell = _latestBridgeDebug.focus_cells[i];
                if (cell != null && cell.flat_index == flatIndex)
                {
                    return cell;
                }
            }

            return null;
        }

        private string ResolveTopActionLabel(int flatIndex, string fallback)
        {
            FocusCellBridgeDiagnostic focus = FindFocusCellDiagnostic(flatIndex);
            if (focus != null && !string.IsNullOrWhiteSpace(focus.predicted_action_type_name))
            {
                return focus.predicted_action_type_name;
            }

            return fallback;
        }

        private static string BuildTop3Label(ActionTypeTopK[] top3)
        {
            if (top3 == null || top3.Length == 0)
            {
                return "unavailable";
            }

            var parts = new List<string>(top3.Length);
            for (int i = 0; i < top3.Length; i++)
            {
                ActionTypeTopK item = top3[i];
                if (item == null)
                {
                    continue;
                }

                parts.Add(
                    item.class_name + "(" + item.class_id.ToString(CultureInfo.InvariantCulture) + ",p=" +
                    item.probability.ToString("F3", CultureInfo.InvariantCulture) + ")");
            }

            return parts.Count > 0 ? string.Join(" > ", parts) : "unavailable";
        }

        private static string BuildFocusProbabilitiesLine(ActorCellDiagnosticRow row)
        {
            if (row == null || !row.LogitsAvailable || row.ActionTypeProbabilities == null || row.ActionTypeProbabilities.Length != 6)
            {
                return "logits/probabilities: unavailable | reason: bridge payload missing";
            }

            float[] p = row.ActionTypeProbabilities;
            return string.Format(
                CultureInfo.InvariantCulture,
                "NoOp={0:F3}, Move={1:F3}, Harvest={2:F3}, Return={3:F3}, Produce={4:F3}, Attack={5:F3}, margin={6:F3}",
                p[0], p[1], p[2], p[3], p[4], p[5], row.NoopMargin);
        }

        private float[] GetCellObservationChannels(int flatIndex, FocusCellBridgeDiagnostic fallback)
        {
            if (flatIndex >= 0 && flatIndex < ObservationContract.GridH * ObservationContract.GridW && _latestObservationValues != null)
            {
                int baseOffset = flatIndex * ObservationContract.ChannelsPerCell;
                if (baseOffset >= 0 && baseOffset + ObservationContract.ChannelsPerCell <= _latestObservationValues.Length)
                {
                    var slice = new float[ObservationContract.ChannelsPerCell];
                    Array.Copy(_latestObservationValues, baseOffset, slice, 0, ObservationContract.ChannelsPerCell);
                    return slice;
                }
            }

            return fallback != null ? fallback.cell_observation_channels : null;
        }

        private string[] GetObservationChannelNames()
        {
            if (_latestBridgeDebug != null && _latestBridgeDebug.observation_channel_names != null && _latestBridgeDebug.observation_channel_names.Length == 27)
            {
                return _latestBridgeDebug.observation_channel_names;
            }

            return new[]
            {
                "hit_points", "resources", "owner_neutral", "owner_player1", "owner_player2",
                "unit_resource", "unit_base", "unit_barracks", "unit_worker", "unit_light", "unit_heavy", "unit_ranged",
                "action_noop", "action_move", "action_harvest", "action_return", "action_produce", "action_attack",
                "dir_north", "dir_east", "dir_south", "dir_west",
                "produce_worker", "produce_light", "produce_heavy", "produce_ranged", "attack_target_index"
            };
        }

        private static string InferUnitTypeFromChannels(float[] channels)
        {
            int best = 5;
            float value = float.NegativeInfinity;
            for (int i = 5; i <= 11; i++)
            {
                if (channels[i] > value)
                {
                    value = channels[i];
                    best = i;
                }
            }

            return best switch
            {
                5 => "Resource",
                6 => "Base",
                7 => "Barracks",
                8 => "Worker",
                9 => "Light",
                10 => "Heavy",
                11 => "Ranged",
                _ => "Unknown",
            };
        }

        private string[] BuildLogitsShapeLines()
        {
            if (_latestArtifact.LogitsShapes == null || _latestArtifact.LogitsShapes.Count == 0)
            {
                return Array.Empty<string>();
            }

            var lines = new List<string>(_latestArtifact.LogitsShapes.Count);
            foreach (KeyValuePair<string, int[]> kvp in _latestArtifact.LogitsShapes)
            {
                lines.Add(kvp.Key + ": [" + string.Join(",", kvp.Value) + "]");
            }

            return lines.ToArray();
        }

        private string[] BuildPredictedActionBoundsLines()
        {
            var lines = new List<string>();
            if (!_latestArtifact.IsAvailable)
            {
                return lines.ToArray();
            }

            int[] min = { int.MaxValue, int.MaxValue, int.MaxValue, int.MaxValue, int.MaxValue, int.MaxValue, int.MaxValue };
            int[] max = { int.MinValue, int.MinValue, int.MinValue, int.MinValue, int.MinValue, int.MinValue, int.MinValue };
            for (int flat = 0; flat < ActionContract.TotalCells; flat++)
            {
                UnitActionType actionType;
                int move;
                int harvest;
                int ret;
                int produceDir;
                int produceType;
                int attackLocal;
                ExtractBranchValues(_latestArtifact.ActionFlat, flat, out actionType, out move, out harvest, out ret, out produceDir, out produceType, out attackLocal);

                int[] values = { (int)actionType, move, harvest, ret, produceDir, produceType, attackLocal };
                for (int i = 0; i < values.Length; i++)
                {
                    if (values[i] < min[i]) min[i] = values[i];
                    if (values[i] > max[i]) max[i] = values[i];
                }
            }

            string[] names = { "action_type", "move_dir", "harvest_dir", "return_dir", "produce_dir", "produce_unit_type", "attack_target_local" };
            for (int i = 0; i < names.Length; i++)
            {
                lines.Add(names[i] + ": min=" + min[i] + ", max=" + max[i]);
            }

            return lines.ToArray();
        }

        private string[] BuildHistogramLines(Dictionary<string, int> histogram)
        {
            if (histogram == null || histogram.Count == 0)
            {
                return Array.Empty<string>();
            }

            var entries = new List<KeyValuePair<string, int>>(histogram);
            entries.Sort((left, right) => right.Value.CompareTo(left.Value));

            var lines = new string[entries.Count];
            for (int i = 0; i < entries.Count; i++)
            {
                lines[i] = entries[i].Key + ": " + entries[i].Value;
            }

            return lines;
        }

        private ObservationSnapshot CaptureObservationSnapshot()
        {
            if (_gridManager == null || _unitRegistry == null || _resourceManager == null)
            {
                return new ObservationSnapshot(0f, 0f, true, true, 0, 0, 0);
            }

            var builder = new ObservationBuilder(_gridManager, _unitRegistry, _resourceManager);
            ObservationPackage package = builder.BuildObservationPackage(_studentControlledPlayer, ObservationMode.UnityMvpTransfer);
            float[] values = package.SpatialObservation ?? Array.Empty<float>();
            _latestObservationValues = values;

            float min = float.PositiveInfinity;
            float max = float.NegativeInfinity;
            bool hasNaN = false;
            bool hasInf = false;
            for (int i = 0; i < values.Length; i++)
            {
                float value = values[i];
                if (float.IsNaN(value))
                {
                    hasNaN = true;
                    continue;
                }

                if (float.IsInfinity(value))
                {
                    hasInf = true;
                    continue;
                }

                if (value < min) min = value;
                if (value > max) max = value;
            }

            if (float.IsPositiveInfinity(min))
            {
                min = 0f;
                max = 0f;
            }

            int own = 0;
            int enemy = 0;
            int resources = 0;
            List<UnitRuntime> units = _unitRegistry.GetAllUnits();
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit == null || !unit.IsAlive)
                {
                    continue;
                }

                if (unit.Owner == _studentControlledPlayer)
                {
                    own++;
                }
                else if (unit.Owner != Owner.Neutral)
                {
                    enemy++;
                }
                else if (unit.Type == UnitType.Resource)
                {
                    resources++;
                }
            }

            return new ObservationSnapshot(min, max, hasNaN, hasInf, own, enemy, resources);
        }

        private bool TryReadLatestAdapterArtifact(string projectRoot, string artifactDirRel, string artifactPrefix, string fallbackOutputJsonPath, out AdapterArtifactSnapshot snapshot)
        {
            snapshot = default;
            if (_studentAdapter == null)
            {
                return false;
            }

            string dir = Path.GetFullPath(Path.Combine(projectRoot, artifactDirRel));
            if (!Directory.Exists(dir))
            {
                return TryReadFallbackAdapterArtifact(fallbackOutputJsonPath, out snapshot);
            }

            string pattern = string.IsNullOrWhiteSpace(artifactPrefix)
                ? "*_adapter.json"
                : artifactPrefix + "*_adapter.json";

            string[] files = Directory.GetFiles(dir, pattern, SearchOption.TopDirectoryOnly);
            if (files.Length == 0)
            {
                return TryReadFallbackAdapterArtifact(fallbackOutputJsonPath, out snapshot);
            }

            Array.Sort(files, (left, right) => File.GetLastWriteTimeUtc(right).CompareTo(File.GetLastWriteTimeUtc(left)));
            string latest = files[0];
            string json = File.ReadAllText(latest, Encoding.UTF8);
            var parsed = JsonUtility.FromJson<AdapterArtifactJson>(json);
            if (parsed == null)
            {
                return TryReadFallbackAdapterArtifact(fallbackOutputJsonPath, out snapshot);
            }

            snapshot = new AdapterArtifactSnapshot(
                true,
                latest,
                parsed.observation_shape,
                parsed.branch_sizes,
                parsed.logits_keys,
                parsed.action_flat_size,
                parsed.action_flat,
                ParseLogitsShapes(json),
                parsed.stage10r_debug);
            return true;
        }

        private bool TryReadFallbackAdapterArtifact(string fallbackOutputJsonPath, out AdapterArtifactSnapshot snapshot)
        {
            snapshot = default;
            if (string.IsNullOrWhiteSpace(fallbackOutputJsonPath))
            {
                return false;
            }

            if (!File.Exists(fallbackOutputJsonPath))
            {
                return false;
            }

            string json = File.ReadAllText(fallbackOutputJsonPath, Encoding.UTF8);
            var parsed = JsonUtility.FromJson<AdapterArtifactJson>(json);
            if (parsed == null)
            {
                return false;
            }

            snapshot = new AdapterArtifactSnapshot(
                true,
                fallbackOutputJsonPath,
                parsed.observation_shape,
                parsed.branch_sizes,
                parsed.logits_keys,
                parsed.action_flat_size,
                parsed.action_flat,
                ParseLogitsShapes(json),
                parsed.stage10r_debug);
            return true;
        }

        private Dictionary<string, int[]> ParseLogitsShapes(string json)
        {
            var result = new Dictionary<string, int[]>(StringComparer.Ordinal);
            if (string.IsNullOrWhiteSpace(json))
            {
                return result;
            }

            Match container = Regex.Match(json, "\"model_output_logits_shapes\"\\s*:\\s*\\{(?<body>.*?)\\}\\s*(,|\\})", RegexOptions.Singleline);
            if (!container.Success)
            {
                return result;
            }

            MatchCollection entries = Regex.Matches(container.Groups["body"].Value, "\"(?<key>[^\"]+)\"\\s*:\\s*\\[(?<vals>[^\\]]*)\\]");
            for (int i = 0; i < entries.Count; i++)
            {
                Match entry = entries[i];
                string key = entry.Groups["key"].Value;
                string[] raw = entry.Groups["vals"].Value.Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
                var vals = new List<int>(raw.Length);
                for (int j = 0; j < raw.Length; j++)
                {
                    int value;
                    if (int.TryParse(raw[j].Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out value))
                    {
                        vals.Add(value);
                    }
                }

                result[key] = vals.ToArray();
            }

            return result;
        }

        private void ConfigureCameraForVisualInspection()
        {
            if (!_autoConfigureTopDownCamera)
            {
                return;
            }

            Camera cameraRef = Camera.main != null ? Camera.main : FindFirstObjectByType<Camera>();
            if (cameraRef == null)
            {
                return;
            }

            if (_forceOrthographicCamera)
            {
                cameraRef.orthographic = true;
            }

            float width = ObservationContract.GridW;
            float height = ObservationContract.GridH;
            float halfExtent = Mathf.Max(width, height) * 0.5f;
            cameraRef.orthographicSize = halfExtent + _orthographicPadding;
            cameraRef.transform.position = new Vector3((width - 1f) * 0.5f, _cameraHeight, (height - 1f) * 0.5f);

            // Keep map logic untouched, but orient the top-down camera so low-Y cells
            // are shown at the top of the screen (A1/B1 in top-left area).
            if (_flipVerticalToMatchMicroRtsTopLeft)
            {
                // Rotate the current top-down view 90+180=270 degrees to the left (or 90 right).
                cameraRef.transform.rotation = Quaternion.LookRotation(Vector3.down, Vector3.left);
            }
            else
            {
                cameraRef.transform.rotation = Quaternion.Euler(_cameraTiltDegrees, 0f, 0f);
            }
        }

        private void DrawUnitMarkers()
        {
            if (_unitRegistry == null)
            {
                return;
            }

            List<UnitRuntime> units = _unitRegistry.GetAllUnits();
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit == null || !unit.IsAlive)
                {
                    continue;
                }

                Color color = unit.Owner == _studentControlledPlayer
                    ? StudentColor
                    : (unit.Owner == Owner.Neutral ? ResourceColor : BaselineColor);

                Gizmos.color = color;
                Vector3 pos = unit.transform.position;
                float scale = unit.Type == UnitType.Base ? 0.9f : 0.55f;
                if (unit.Type == UnitType.Resource)
                {
                    Gizmos.DrawSphere(pos + Vector3.up * 0.25f, 0.35f);
                }
                else
                {
                    Gizmos.DrawCube(pos + Vector3.up * 0.15f, new Vector3(scale, 0.25f, scale));
                }
            }
        }

        private void DrawActorMarkers()
        {
            for (int i = 0; i < _latestActorRows.Count; i++)
            {
                ActorCellDiagnosticRow row = _latestActorRows[i];
                if (row.Unit == null)
                {
                    continue;
                }

                Vector3 basePos = row.Unit.transform.position;

                Gizmos.color = EligibleActorColor;
                Gizmos.DrawWireCube(basePos + Vector3.up * 0.05f, new Vector3(1.05f, 0.05f, 1.05f));

                Color markerColor = row.CommandBuilt
                    ? SuccessColor
                    : (row.PredictedActionType == UnitActionType.NoOp ? NoOpColor : WarningColor);

                Gizmos.color = markerColor;
                Gizmos.DrawSphere(basePos + Vector3.up * 0.65f, 0.15f);

                DrawPredictedActionGlyph(row, basePos + Vector3.up * 0.15f, markerColor);
            }
        }

        private void DrawBaselineCommandMarkers()
        {
            foreach (KeyValuePair<int, MatchCommand> kvp in _lastBaselineAcceptedByActor)
            {
                DrawCommandMarker(kvp.Value, SuccessColor, 0.75f);
            }

            foreach (KeyValuePair<int, RuntimeRejectionInfo> kvp in _lastBaselineRejectedByActor)
            {
                GridPosition pos = GridPosition.FromFlatIndex(kvp.Key);
                Vector3 world = pos.ToWorldPosition();
                Gizmos.color = WarningColor;
                Gizmos.DrawWireSphere(world + Vector3.up * 0.95f, 0.2f);
            }
        }

        private void DrawCommandMarker(MatchCommand command, Color color, float height)
        {
            Vector3 origin = command.UnitPosition.ToWorldPosition() + Vector3.up * height;
            Gizmos.color = color;
            Gizmos.DrawSphere(origin, 0.12f);

            if (command.ActionType == UnitActionType.Attack && command.HasAttackTarget)
            {
                Vector3 target = command.AttackTarget.ToWorldPosition() + Vector3.up * 0.2f;
                Gizmos.DrawLine(origin, target);
                Gizmos.DrawWireCube(target, new Vector3(0.4f, 0.05f, 0.4f));
                return;
            }

            Vector3 dir = command.Direction switch
            {
                Direction.North => Vector3.forward,
                Direction.East => Vector3.right,
                Direction.South => Vector3.back,
                Direction.West => Vector3.left,
                _ => Vector3.zero,
            };

            if (dir != Vector3.zero)
            {
                Gizmos.DrawLine(origin, origin + dir * 0.7f);
            }
        }

        private void DrawStatusBanner()
        {
            if (_statusBannerStyle == null)
            {
                _statusBannerStyle = new GUIStyle(GUI.skin.box)
                {
                    fontSize = 22,
                    fontStyle = FontStyle.Bold,
                    alignment = TextAnchor.MiddleCenter,
                };
            }

            Color old = GUI.color;
            GUI.color = _simulationPaused ? new Color(1f, 0.8f, 0.2f, 1f) : new Color(0.25f, 0.95f, 0.35f, 1f);
            GUILayout.Box(_simulationPaused ? "VISUAL MODE: PAUSED" : "VISUAL MODE: RUNNING", _statusBannerStyle, GUILayout.Height(38f));
            GUI.color = old;
        }

        private void DrawFocusCellLabels()
        {
            if (Camera.main == null)
            {
                return;
            }

            if (_worldLabelStyle == null)
            {
                _worldLabelStyle = new GUIStyle(GUI.skin.box)
                {
                    fontSize = 11,
                    alignment = TextAnchor.MiddleLeft,
                    normal = { textColor = Color.white }
                };
            }

            if (_latestActorRowsByFlatIndex.TryGetValue(FocusFlatWorkerB2, out ActorCellDiagnosticRow b2))
            {
                DrawWorldLabel(
                    b2.Unit,
                    $"B2 Student predicted: {b2.PredictedActionType} | top3={b2.Top3ActionType} | margin={b2.NoopMargin.ToString("F3", CultureInfo.InvariantCulture)} | command_built={b2.CommandBuilt} | reason={b2.CommandNotBuiltReason}");
            }

            if (_latestActorRowsByFlatIndex.TryGetValue(FocusFlatBaseC3, out ActorCellDiagnosticRow c3))
            {
                DrawWorldLabel(
                    c3.Unit,
                    $"C3 Student predicted: {c3.PredictedActionType} | top3={c3.Top3ActionType} | margin={c3.NoopMargin.ToString("F3", CultureInfo.InvariantCulture)} | command_built={c3.CommandBuilt} | reason={c3.CommandNotBuiltReason}");
            }
        }

        private void DrawWorldLabel(UnitRuntime unit, string text)
        {
            if (unit == null || Camera.main == null)
            {
                return;
            }

            Vector3 world = unit.transform.position + Vector3.up * 1.25f;
            Vector3 screen = Camera.main.WorldToScreenPoint(world);
            if (screen.z <= 0f)
            {
                return;
            }

            float x = screen.x - 220f;
            float y = Screen.height - screen.y - 18f;
            GUI.color = new Color(0f, 0f, 0f, 0.75f);
            GUI.Box(new Rect(x, y, 440f, 20f), GUIContent.none);
            GUI.color = Color.white;
            GUI.Label(new Rect(x + 4f, y + 2f, 432f, 18f), text, _worldLabelStyle);
        }

        private void DrawPredictedActionGlyph(ActorCellDiagnosticRow row, Vector3 origin, Color color)
        {
            Vector3 dir = DirectionToVector(row.PredictedActionType, row.MoveDir, row.HarvestDir, row.ReturnDir, row.ProduceDir);
            Gizmos.color = color;

            if (row.PredictedActionType == UnitActionType.Attack)
            {
                Vector2Int offset = AttackLocalToOffset(row.AttackTargetLocal);
                Vector3 target = origin + new Vector3(offset.x, 0f, offset.y);
                Gizmos.DrawLine(origin, target);
                Gizmos.DrawWireCube(target + Vector3.up * 0.02f, new Vector3(0.5f, 0.02f, 0.5f));
                return;
            }

            if (row.PredictedActionType == UnitActionType.NoOp)
            {
                Gizmos.DrawWireSphere(origin + Vector3.up * 0.15f, 0.2f);
                return;
            }

            if (dir != Vector3.zero)
            {
                Gizmos.DrawLine(origin, origin + dir * 0.8f);
            }
        }

        private void DrawGridLabels()
        {
            float y = 0.02f;
            Color previousColor = Handles.color;
            Handles.color = new Color(0.95f, 0.95f, 0.95f, 0.8f);

            for (int x = 0; x < ObservationContract.GridW; x++)
            {
                string column = ColumnLabel(x);
                Handles.Label(new Vector3(x, y, -0.65f), column);
            }

            for (int yIndex = 0; yIndex < ObservationContract.GridH; yIndex++)
            {
                Handles.Label(new Vector3(-0.75f, y, yIndex), (yIndex + 1).ToString(CultureInfo.InvariantCulture));
            }

            Handles.color = previousColor;
        }

        private string BuildActorRowLine(ActorCellDiagnosticRow row)
        {
            string unitType = row.Unit != null ? row.Unit.Type.ToString() : "Unknown";
            string pos = row.Unit != null ? $"({row.Unit.GridPos.X},{row.Unit.GridPos.Y})" : "(?,?)";
            string built = row.CommandBuilt ? "yes" : "no";
            string logits = row.LogitsAvailable
                ? ("noop_p=" + row.NoopProbability.ToString("F3", CultureInfo.InvariantCulture) + ", margin=" + row.NoopMargin.ToString("F3", CultureInfo.InvariantCulture))
                : ("logits_unavailable=" + row.LogitsUnavailableReason);

            return $"- {unitType} {row.LogicalCell} {pos} flat={row.FlatIndex}, owner={row.Owner}, eligible={row.Eligible}, action={row.PredictedActionType}, top3={row.Top3ActionType}, {logits}, branches=[m:{row.MoveDir},h:{row.HarvestDir},r:{row.ReturnDir},pd:{row.ProduceDir},pt:{row.ProduceUnitType},atk:{row.AttackTargetLocal}], built={built}, reason={row.CommandNotBuiltReason}";
        }

        private string ResolveCommandNotBuiltReason(int flatIndex, UnitActionType predictedActionType, bool commandBuilt)
        {
            if (commandBuilt)
            {
                if (_lastRejectedByActor.TryGetValue(flatIndex, out RuntimeRejectionInfo runtimeRejected))
                {
                    return "runtime_rejected:" + runtimeRejected.Reason;
                }

                return "built_and_submitted";
            }

            if (!_latestArtifact.IsAvailable)
            {
                if (_latestInferenceDiagnostics == null || _latestInferenceDiagnostics.inference_request_count <= 0)
                {
                    return "no_inference_requests_yet";
                }

                return "artifact_missing_after_inference";
            }

            if (predictedActionType == UnitActionType.NoOp)
            {
                return "predicted_noop";
            }

            if (_lastRejectedByActor.TryGetValue(flatIndex, out RuntimeRejectionInfo rejected))
            {
                return "runtime_rejected:" + rejected.Reason;
            }

            return "not_built_in_decoder_or_filter";
        }

        private string ResolveAdapterArtifactMissingReason()
        {
            if (_latestArtifact.IsAvailable)
            {
                return string.Empty;
            }

            if (_latestInferenceDiagnostics == null)
            {
                return "adapter_diagnostics_unavailable";
            }

            if (_latestInferenceDiagnostics.inference_request_count <= 0)
            {
                return "no_inference_requests_yet";
            }

            if (!string.IsNullOrWhiteSpace(_latestInferenceDiagnostics.adapter_artifact_missing_reason))
            {
                return _latestInferenceDiagnostics.adapter_artifact_missing_reason;
            }

            return "adapter_artifact_missing_after_inference";
        }

        private void ExtractBranchValues(
            int[] actionFlat,
            int flatIndex,
            out UnitActionType actionType,
            out int moveDir,
            out int harvestDir,
            out int returnDir,
            out int produceDir,
            out int produceType,
            out int attackLocal)
        {
            actionType = UnitActionType.NoOp;
            moveDir = 0;
            harvestDir = 0;
            returnDir = 0;
            produceDir = 0;
            produceType = 0;
            attackLocal = 24;

            if (actionFlat == null || actionFlat.Length != ActionContract.TotalActionFlatSize || flatIndex < 0 || flatIndex >= ActionContract.TotalCells)
            {
                return;
            }

            int baseOffset = flatIndex * ActionContract.ActionFlatSize;
            int rawType = SafeGet(actionFlat, baseOffset + ActionContract.BranchOffset(ActionContract.BRANCH_ACTION_TYPE));
            moveDir = SafeGet(actionFlat, baseOffset + ActionContract.BranchOffset(ActionContract.BRANCH_MOVE_DIR));
            harvestDir = SafeGet(actionFlat, baseOffset + ActionContract.BranchOffset(ActionContract.BRANCH_HARVEST_DIR));
            returnDir = SafeGet(actionFlat, baseOffset + ActionContract.BranchOffset(ActionContract.BRANCH_RETURN_DIR));
            produceDir = SafeGet(actionFlat, baseOffset + ActionContract.BranchOffset(ActionContract.BRANCH_PRODUCE_DIR));
            produceType = SafeGet(actionFlat, baseOffset + ActionContract.BranchOffset(ActionContract.BRANCH_PRODUCE_UNIT_TYPE));
            attackLocal = SafeGet(actionFlat, baseOffset + ActionContract.BranchOffset(ActionContract.BRANCH_ATTACK_TARGET));

            actionType = ToUnitActionType(rawType);
        }

        private static int SafeGet(int[] values, int index)
        {
            if (values == null || index < 0 || index >= values.Length)
            {
                return 0;
            }

            return values[index];
        }

        private static UnitActionType ToUnitActionType(int value)
        {
            switch (value)
            {
                case 1: return UnitActionType.Move;
                case 2: return UnitActionType.Harvest;
                case 3: return UnitActionType.Return;
                case 4: return UnitActionType.Produce;
                case 5: return UnitActionType.Attack;
                default: return UnitActionType.NoOp;
            }
        }

        private int GetCurrentStep()
        {
            return _matchManager != null ? _matchManager.Step : 0;
        }

        private int GetMaxSteps()
        {
            return _matchManager != null ? _matchManager.MaxSteps : 0;
        }

        private string GetWinnerLabel()
        {
            if (_matchManager == null)
            {
                return "n/a";
            }

            return _matchManager.Winner.ToString();
        }

        private string IsRunningLabel()
        {
            return _episodeController != null && _episodeController.IsRunning ? "yes" : "no";
        }

        private int GetScenarioPreset()
        {
            if (_matchBootstrap == null)
            {
                return -1;
            }

            return GetPrivateEnumInt(_matchBootstrap, "_scenarioPreset", -1);
        }

        private int CountActiveRunners()
        {
            return FindObjectsByType<Week6VisualInspectionRunner>(FindObjectsSortMode.None).Length;
        }

        private string GetPlayerModeLabel(int playerIndex)
        {
            if (_episodeController == null)
            {
                return "n/a";
            }

            if (playerIndex == 1)
            {
                Week6PlayerControlMode mode1 = GetPrivateField(_episodeController, "_player1DecisionMode", Week6PlayerControlMode.HeuristicBaseline);
                return mode1.ToString();
            }

            Week6PlayerControlMode mode2 = GetPrivateField(_episodeController, "_player2DecisionMode", Week6PlayerControlMode.HeuristicBaseline);
            return mode2.ToString();
        }

        private string BuildCommandSummary(MatchCommand command, bool accepted, string reason)
        {
            string status = accepted ? "accepted" : "rejected";
            string suffix = accepted ? string.Empty : (", reason=" + reason);
            return $"owner={command.Owner}, action={command.ActionType}, at={ToCellLabel(command.UnitPosition)}({command.UnitPosition.X},{command.UnitPosition.Y}), status={status}{suffix}";
        }

        private static Vector3 DirectionToVector(UnitActionType actionType, int moveDir, int harvestDir, int returnDir, int produceDir)
        {
            int dir = actionType switch
            {
                UnitActionType.Move => moveDir,
                UnitActionType.Harvest => harvestDir,
                UnitActionType.Return => returnDir,
                UnitActionType.Produce => produceDir,
                _ => 0,
            };

            switch (dir)
            {
                case 0: return Vector3.forward;
                case 1: return Vector3.right;
                case 2: return Vector3.back;
                case 3: return Vector3.left;
                default: return Vector3.zero;
            }
        }

        private static Vector2Int AttackLocalToOffset(int attackLocal)
        {
            int clamped = Mathf.Clamp(attackLocal, 0, ActionContract.SIZE_ATTACK_TARGET - 1);
            int x = (clamped % 7) - 3;
            int y = (clamped / 7) - 3;
            return new Vector2Int(x, y);
        }

        private static int ToFlatIndex(GridPosition pos)
        {
            return pos.Y * ObservationContract.GridW + pos.X;
        }

        private static string ToCellLabel(GridPosition pos)
        {
            return ColumnLabel(pos.X) + (pos.Y + 1).ToString(CultureInfo.InvariantCulture);
        }

        private static string ColumnLabel(int x)
        {
            int clamped = Mathf.Clamp(x, 0, ObservationContract.GridW - 1);
            return ((char)('A' + clamped)).ToString();
        }

        private static string NormalizeReason(string reason)
        {
            if (string.IsNullOrWhiteSpace(reason))
            {
                return "other";
            }

            string lower = reason.ToLowerInvariant();
            if (lower.Contains("belongs to") || lower.Contains("another owner")) return "wrong_owner";
            if (lower.Contains("occupied")) return "occupied_target";
            if (lower.Contains("queue") || lower.Contains("already has a command")) return "production_queue_busy";
            if (lower.Contains("insufficient") || lower.Contains("not enough")) return "insufficient_resources";
            if (lower.Contains("unsupported") || lower.Contains("cannot produce")) return "unsupported_action";
            if (lower.Contains("no enemy") || lower.Contains("cannot attack")) return "invalid_attack_target";
            if (lower.Contains("out of range") || lower.Contains("out of bounds")) return "target_out_of_range";
            if (lower.Contains("direction")) return "invalid_direction";
            return "other";
        }

        private static string FormatIntArray(int[] values)
        {
            if (values == null || values.Length == 0)
            {
                return "n/a";
            }

            return string.Join(",", values);
        }

        private static string FormatActionHistogramFromArtifact(int[] actionFlat)
        {
            if (actionFlat == null || actionFlat.Length != ActionContract.TotalActionFlatSize)
            {
                return "unavailable";
            }

            int noop = 0;
            int move = 0;
            int harvest = 0;
            int ret = 0;
            int produce = 0;
            int attack = 0;
            for (int flat = 0; flat < ActionContract.TotalCells; flat++)
            {
                int value = actionFlat[flat * ActionContract.ActionFlatSize + ActionContract.BranchOffset(ActionContract.BRANCH_ACTION_TYPE)];
                switch (value)
                {
                    case 1: move++; break;
                    case 2: harvest++; break;
                    case 3: ret++; break;
                    case 4: produce++; break;
                    case 5: attack++; break;
                    default: noop++; break;
                }
            }

            return $"NoOp={noop}, Move={move}, Harvest={harvest}, Return={ret}, Produce={produce}, Attack={attack}";
        }

        private static string FormatNoOpShareFromArtifact(int[] actionFlat)
        {
            if (actionFlat == null || actionFlat.Length != ActionContract.TotalActionFlatSize)
            {
                return "n/a";
            }

            int noop = 0;
            for (int flat = 0; flat < ActionContract.TotalCells; flat++)
            {
                int value = actionFlat[flat * ActionContract.ActionFlatSize + ActionContract.BranchOffset(ActionContract.BRANCH_ACTION_TYPE)];
                if (value == 0)
                {
                    noop++;
                }
            }

            float share = noop / (float)ActionContract.TotalCells;
            return share.ToString("P2", CultureInfo.InvariantCulture);
        }

        private static string FormatNonNoOpShareFromArtifact(int[] actionFlat)
        {
            if (actionFlat == null || actionFlat.Length != ActionContract.TotalActionFlatSize)
            {
                return "n/a";
            }

            int nonNoOp = 0;
            for (int flat = 0; flat < ActionContract.TotalCells; flat++)
            {
                int value = actionFlat[flat * ActionContract.ActionFlatSize + ActionContract.BranchOffset(ActionContract.BRANCH_ACTION_TYPE)];
                if (value != 0)
                {
                    nonNoOp++;
                }
            }

            float share = nonNoOp / (float)ActionContract.TotalCells;
            return share.ToString("P2", CultureInfo.InvariantCulture);
        }

        private static string FormatStringHistogram(Dictionary<string, int> histogram)
        {
            if (histogram == null || histogram.Count == 0)
            {
                return "none";
            }

            var entries = new List<KeyValuePair<string, int>>(histogram);
            entries.Sort((left, right) => right.Value.CompareTo(left.Value));

            var sb = new StringBuilder();
            for (int i = 0; i < entries.Count; i++)
            {
                if (i > 0)
                {
                    sb.Append(", ");
                }

                sb.Append(entries[i].Key);
                sb.Append('=');
                sb.Append(entries[i].Value);
            }

            return sb.ToString();
        }

        private static Dictionary<UnitActionType, int> CreateActionHistogram()
        {
            return new Dictionary<UnitActionType, int>
            {
                [UnitActionType.NoOp] = 0,
                [UnitActionType.Move] = 0,
                [UnitActionType.Harvest] = 0,
                [UnitActionType.Return] = 0,
                [UnitActionType.Produce] = 0,
                [UnitActionType.Attack] = 0,
            };
        }

        private static void ResetActionHistogram(Dictionary<UnitActionType, int> histogram)
        {
            if (histogram == null)
            {
                return;
            }

            var keys = new List<UnitActionType>(histogram.Keys);
            for (int i = 0; i < keys.Count; i++)
            {
                histogram[keys[i]] = 0;
            }
        }

        private static void MergeActionHistogram(Dictionary<UnitActionType, int> target, IReadOnlyDictionary<UnitActionType, int> source)
        {
            if (target == null || source == null)
            {
                return;
            }

            foreach (KeyValuePair<UnitActionType, int> kvp in source)
            {
                if (!target.TryGetValue(kvp.Key, out int value))
                {
                    value = 0;
                }

                target[kvp.Key] = value + kvp.Value;
            }
        }

        private static void IncrementStringCount(Dictionary<string, int> histogram, string key)
        {
            if (histogram == null)
            {
                return;
            }

            string normalized = string.IsNullOrWhiteSpace(key) ? "other" : key;
            if (!histogram.TryGetValue(normalized, out int value))
            {
                value = 0;
            }

            histogram[normalized] = value + 1;
        }

        private static T GetPrivateField<T>(object source, string fieldName, T fallback)
        {
            if (source == null)
            {
                return fallback;
            }

            FieldInfo field = source.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            if (field == null)
            {
                return fallback;
            }

            object raw = field.GetValue(source);
            return raw is T typed ? typed : fallback;
        }

        private static int GetPrivateEnumInt(object source, string fieldName, int fallback)
        {
            if (source == null)
            {
                return fallback;
            }

            FieldInfo field = source.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            if (field == null)
            {
                return fallback;
            }

            object raw = field.GetValue(source);
            if (raw == null)
            {
                return fallback;
            }

            try
            {
                return Convert.ToInt32(raw, CultureInfo.InvariantCulture);
            }
            catch
            {
                return fallback;
            }
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
