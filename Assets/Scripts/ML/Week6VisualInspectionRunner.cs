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
    public enum Week6VisualRuntimeMode
    {
        Demo = 0,
        Diagnostic = 1,
        Profiler = 2
    }

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

        [Header("Performance Runtime Mode")]
        [SerializeField] private Week6VisualRuntimeMode _runtimeMode = Week6VisualRuntimeMode.Demo;
        [SerializeField] private bool _demoMode = true;
        [SerializeField] private bool _enableOverlay = false;
        [SerializeField] private bool _enableJsonTrace = false;
        [SerializeField] private int _diagnosticSamplingInterval = 10;
        [SerializeField] private int _targetFrameRate = 30;
        [SerializeField] private float _decisionTickIntervalSeconds = 0.2f;
        [SerializeField] private bool _enableProfilerCounters = true;
        [SerializeField] private string _performanceSummaryRelativePath = "stage6b3_playmode_performance_summary.json";

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
        [SerializeField] private bool _writePlayModeStopDiagnostics = true;
        [SerializeField] private string _playModeStopDiagnosticsRelativeDir = "python/week6_student/tmp/stage6b3_static_playmode_stop";
        [SerializeField] private string _softIdleDiagnosticsRelativeDir = "python/week6_student/tmp/stage6b3_static_soft_idle_diagnostic";

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
        private readonly Dictionary<string, CommandEventTelemetry> _commandTelemetryByKey =
            new Dictionary<string, CommandEventTelemetry>(StringComparer.Ordinal);
        private readonly Dictionary<int, List<CommandEventTelemetry>> _commandTelemetryByFlat =
            new Dictionary<int, List<CommandEventTelemetry>>();
        private int _commandTelemetryIdSequence;
        private int _commandTelemetryEventSequence;
        private readonly Dictionary<int, MatchCommand> _lastBaselineAcceptedByActor = new Dictionary<int, MatchCommand>();
        private readonly Dictionary<int, RuntimeRejectionInfo> _lastBaselineRejectedByActor = new Dictionary<int, RuntimeRejectionInfo>();
        private readonly Dictionary<int, ActionDecoder.MaskAwareCellTelemetry> _latestMaskAwareCellTelemetryByFlat =
            new Dictionary<int, ActionDecoder.MaskAwareCellTelemetry>();
        private readonly Dictionary<int, StudentMaskAwareDiagnostics.ActorLegalMaskTelemetry> _latestLegalMaskByFlat =
            new Dictionary<int, StudentMaskAwareDiagnostics.ActorLegalMaskTelemetry>();
        private readonly List<Stage6R5CCommandLifecycleRow> _stage6r5cLifecycleRows = new List<Stage6R5CCommandLifecycleRow>();
        private readonly Dictionary<string, Stage6R5CCommandLifecycleRow> _stage6r5cLifecycleById =
            new Dictionary<string, Stage6R5CCommandLifecycleRow>(StringComparer.Ordinal);
        private readonly Dictionary<string, Queue<string>> _stage6r5cPendingByEventKey =
            new Dictionary<string, Queue<string>>(StringComparer.Ordinal);
        private readonly List<Stage6R5CCommandTerminalEventRow> _stage6r5cTerminalEvents =
            new List<Stage6R5CCommandTerminalEventRow>();
        private readonly Dictionary<int, Stage6B3PlayModeStepTrace> _playModeStepTraceByStep =
            new Dictionary<int, Stage6B3PlayModeStepTrace>();
        private readonly Dictionary<int, int> _heuristicEvaluationsPerStep =
            new Dictionary<int, int>();
        private readonly Dictionary<int, int> _heuristicNonNoOpPerStep =
            new Dictionary<int, int>();
        private readonly Dictionary<int, int> _heuristicAcceptedPerStep =
            new Dictionary<int, int>();
        private readonly Dictionary<int, int> _heuristicRejectedPerStep =
            new Dictionary<int, int>();
        private bool _playModeStopDiagnosticsWritten;
        private bool _performanceSummaryWritten;
        private int _lastStudentAcceptedForTrace;
        private int _lastStudentRejectedForTrace;
        private int _lastBaselineAcceptedForTrace;
        private int _lastBaselineRejectedForTrace;

        private GUIStyle _statusBannerStyle;
        private GUIStyle _worldLabelStyle;

        private AdapterArtifactSnapshot _latestArtifact;
        private ObservationSnapshot _latestObservation;
        private StudentInferenceDiagnosticsSnapshot _latestInferenceDiagnostics;

        // Mode-isolation context (set by Stage10D25 capture sessions)
        private string _captureModeName = string.Empty;
        private Week6PlayerControlMode _capturePlayer1Mode = Week6PlayerControlMode.StudentInference;
        private Week6PlayerControlMode _capturePlayer2Mode = Week6PlayerControlMode.HeuristicBaseline;
        private bool _captureModeContextSet;
        private float[] _latestObservationValues = Array.Empty<float>();
        private int _noOpActorCells;
        private int _nonNoOpActorCells;
        private int _nonActorNonNoOpCells;
        private string _b2TopAction = "n/a";
        private string _c3TopAction = "n/a";
        private string _noOpProbeClassification = "n/a";
        private Stage10RBridgeDebug _latestBridgeDebug;
        private string _flattenAlignmentClassification = "INCONCLUSIVE_NEEDS_MORE_LOGITS";

        private const int FocusFlatWorkerLegacy = 25;
        private const int FocusFlatBaseLegacy = 50;
        private const string StaticHarvestSceneName = "Week6_StudentStaticHarvestLayout";
        private static readonly Color StudentColor = new Color(0.20f, 0.75f, 0.95f, 1f);
        private static readonly Color BaselineColor = new Color(1.00f, 0.55f, 0.20f, 1f);
        private static readonly Color ResourceColor = new Color(0.20f, 1.00f, 0.35f, 1f);
        private static readonly Color EligibleActorColor = new Color(0.95f, 0.95f, 0.20f, 0.95f);
        private static readonly Color NoOpColor = new Color(0.85f, 0.85f, 0.85f, 0.95f);
        private static readonly Color WarningColor = new Color(1.00f, 0.40f, 0.20f, 0.95f);
        private static readonly Color SuccessColor = new Color(0.15f, 0.95f, 0.35f, 0.95f);

        private int FocusFlatWorker => IsStaticHarvestSceneActive()
            ? new GridPosition(2, 2).ToFlatIndex()
            : FocusFlatWorkerLegacy;

        private int FocusFlatBase => IsStaticHarvestSceneActive()
            ? new GridPosition(3, 3).ToFlatIndex()
            : FocusFlatBaseLegacy;

        private string FocusWorkerLabel => IsStaticHarvestSceneActive() ? "C3" : "B2";
        private string FocusBaseLabel => IsStaticHarvestSceneActive() ? "D4" : "C3";

        private static bool IsStaticHarvestSceneActive()
        {
            return string.Equals(SceneManager.GetActiveScene().name, StaticHarvestSceneName, StringComparison.Ordinal);
        }

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
            public string unit_name;
            public string owner;
            public string unit_type;
            public int hp;
            public int carried_resources;
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
            // Mode-isolation telemetry (Stage10D25)
            public string mode;
            public string policy_source;
            public string inference_source;
            public bool uses_student_checkpoint;
            public bool uses_python_adapter;
            public bool uses_heuristic_policy;
            public string action_buffer_source;
            public int player1_resources;
            public int player2_resources;
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
            public bool legal_mask_enabled_for_selection;
            public int total_mask_fallback_to_noop;
            public int total_masked_out_action_type_choices;
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
            public string raw_action_type_top1;
            public int raw_move_dir_top1;
            public int raw_harvest_dir_top1;
            public int raw_return_dir_top1;
            public int raw_produce_dir_top1;
            public int raw_produce_unit_type_top1;
            public int raw_attack_target_local_top1;
            public string masked_action_type;
            public int masked_move_dir;
            public int masked_harvest_dir;
            public int masked_return_dir;
            public int masked_produce_dir;
            public int masked_produce_unit_type;
            public int masked_attack_target_local;
            public bool[] legal_action_type_mask;
            public bool[] legal_move_dir_mask;
            public bool masked_move_dir_legal;
            public bool branch_mask_applied_for_move;
            public string move_dir_mask_fallback_reason;
            public bool branch_parameter_mask_applied;
            public string branch_parameter_mask_reason;
            public string decoder_received_action_type;
            public int decoder_received_move_dir;
            public bool decoder_received_move_dir_legal;
            public string decoder_result_if_predicted_non_noop;
            public bool command_built;
            public bool command_submitted;
            public string command_result_status;
            public long command_id;
            public int command_event_step;
            public int command_event_sequence;
            public string command_event_source;
            public string command_event_key;
            public bool command_event_accepted;
            public bool command_event_rejected;
            public string command_event_conflict;
            public string reject_stage;
            public string reject_callsite;
            public string reject_reason;
            public string reject_reason_raw;
            public string reject_reason_normalized;
            public bool legacy_status_conflict;
            public string decoder_reject_reason;
            public bool applier_submission_reached;
            public bool applier_submitted;
            public bool applier_accepted;
            public bool applier_rejected;
            public string applier_reject_reason;
            public string action_type;
            public int source_cell_from_command;
            public int source_x_from_command;
            public int source_y_from_command;
            public int target_cell_from_command;
            public int target_x_from_command;
            public int target_y_from_command;
            public string unit_id;
            public string unit_owner;
            public string unit_type;
            public int unit_position_x_at_reject;
            public int unit_position_y_at_reject;
            public int unit_cell_at_reject;
            public string occupant_exists_at_target;
            public string occupant_id_at_target;
            public string occupant_owner_at_target;
            public string occupant_type_at_target;
            public int occupant_x_at_target;
            public int occupant_y_at_target;
            public int occupant_cell_at_target;
            public int occupancy_lookup_key_cell;
            public int occupancy_lookup_key_x;
            public int occupancy_lookup_key_y;
            public string try_get_occupant_result;
            public string occupant_ref_exists;
            public int occupant_instance_id;
            public string occupant_name;
            public int occupant_logical_x;
            public int occupant_logical_y;
            public int occupant_logical_cell;
            public string occupant_logical_cell_roundtrip_ok;
            public string occupant_logical_cell_matches_lookup_key;
            public string occupant_logical_cell_matches_target_cell;
            public float occupant_transform_x;
            public float occupant_transform_y;
            public int occupant_visual_grid_x;
            public int occupant_visual_grid_y;
            public int occupant_visual_cell;
            public string occupant_visual_cell_matches_logical_cell;
            public string grid_lookup_by_target_returns_occupant;
            public string grid_lookup_by_occupant_logical_cell_returns_same_occupant;
            public string grid_lookup_by_occupant_visual_cell_returns_same_occupant;
            public string occupancy_map_key_matches_occupant_logical_position;
            public int occupant_cell_reported_previous;
            public string occupancy_lookup_method;
            public string occupancy_lookup_source;
            public string target_in_bounds_at_reject;
            public string target_passable_at_reject;
            public string target_occupied_at_reject;
            public string target_occupied_by_runtime_lookup;
            public string target_occupied_by_snapshot_lookup;
            public int snapshot_step_used_for_attribution;
            public string direct_runtime_lookup_matches_snapshot_lookup;
            public string direct_runtime_target_matches_reconstructed_target;
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

        [Serializable]
        private sealed class Stage6R5CCommandLifecycleRow
        {
            public string diagnostic_command_id;
            public long command_id;
            public int step;
            public int actor_flat_index;
            public string actor_label;
            public string unit_id;
            public string unit_type;
            public string owner;
            public string action_type;
            public int move_dir;
            public int harvest_dir;
            public int return_dir;
            public int produce_dir;
            public int produce_unit_type;
            public int attack_target_local;
            public string decoder_result;
            public string applier_result;
            public string match_manager_result;
            public string final_lifecycle_status;
            public bool decoded_candidate;
            public bool built;
            public bool submitted_to_applier;
            public bool rejected_by_decoder;
            public bool rejected_by_applier;
            public bool accepted_by_applier;
            public bool submitted_to_match_manager;
            public bool applied_by_match_manager;
            public bool rejected_by_match_manager;
            public bool expired_or_unresolved_at_capture_end;
            public string reject_reason;
            public string reject_reason_raw;
            public string command_event_key;
            public int last_event_sequence;
            public string last_event_source;
            public bool finalized;
        }

        [Serializable]
        private sealed class Stage6R5CCommandTerminalEventRow
        {
            public string diagnostic_command_id;
            public long command_id;
            public int step;
            public int actor_flat_index;
            public string actor_label;
            public string owner;
            public string action_type;
            public string event_type;
            public string terminal_bucket;
            public string reason;
            public string source;
            public string command_event_key;
            public int event_sequence;
        }

        [Serializable]
        private sealed class Stage6R5CSceneSanitySnapshot
        {
            public string generated_at_utc;
            public string scene;
            public string mode;
            public int steps_completed;
            public string terminal_reason;
            public string checkpoint_path_used_at_inference;
            public bool uses_heuristic_policy;
            public bool fake_policy_or_stub_seen;
            public bool fallback_used;
        }

        [Serializable]
        private sealed class Stage6R5CActorCellSummary
        {
            public string generated_at_utc;
            public int actor_cells_detected;
            public int actor_cell_predicted_noop_count;
            public int actor_cell_predicted_non_noop_count;
            public int actor_cell_command_built_count;
            public int actor_cell_command_not_built_count;
            public string[] unit_type_prediction_histogram;
        }

        [Serializable]
        private sealed class Stage6B3PlayModeStepTrace
        {
            // General
            public int step;
            public int frame;
            public float unity_time;
            public string match_phase;
            public bool terminal;
            public string terminal_reason;
            public bool episode_running;
            public bool episode_auto_step;
            public string victory_winner;
            public string victory_reason;
            public bool runner_enabled;
            public bool adapter_enabled;
            public float time_scale;

            // Player1 / Stage6B3
            public bool policy_decision_requested;
            public int student_selected_non_noop_count;
            public int student_selected_noop_count;
            public int student_mask_non_noop_available_count;
            public int student_commands_built;
            public int student_commands_accepted;
            public int student_commands_rejected;
            public int student_decision_cap_remaining;
            public string student_runtime_error;

            // Player2 / scripted bot
            public bool scripted_decision_requested;
            public int heuristic_action_evaluations;
            public int scripted_non_noop_count;
            public int scripted_accepted_count;
            public int scripted_rejected_count;

            // Backward compat aliases kept for existing trace readers
            public int student_accepted_delta;
            public int student_rejected_delta;
            public int baseline_accepted_delta;
            public int baseline_rejected_delta;

            // Runtime state
            public int player1_units_alive;
            public int player2_units_alive;
            public int player1_bases;
            public int player2_bases;
            public int player1_resources;
            public int player2_resources;
            public int player1_workers;
            public int player2_workers;
            public int player1_workers_carrying;
            public int player2_workers_carrying;
            public int player1_production_busy_count;
            public int player2_production_busy_count;
            public int active_resource_nodes;
            public int total_remaining_resources;
            public int pending_commands;
        }

        [Serializable]
        private sealed class Stage6B3PlayModeStopSummary
        {
            public string generated_at_utc;
            public string scene;
            public string stop_reason;
            public int stop_step;
            public int stop_frame;
            public float stop_unity_time;
            public bool auto_playback_enabled;
            public bool auto_playback_running;
            public int auto_playback_max_steps;
            public int auto_playback_remaining_steps;
            public int scripted_first_stop_step;
            public int student_first_stop_step;
            public bool matchmanager_still_advancing;
            public string match_phase;
            public bool episode_running;
            public bool episode_auto_step;
            public int trace_row_count;
            public int max_observed_step;
            public bool step_80_boundary_cleared;
            public int student_selected_non_noop_total;
            public int student_selected_noop_total;
            public int student_commands_accepted_total;
            public int student_commands_rejected_total;
            public int scripted_non_noop_total;
            public int scripted_accepted_total;
            public int scripted_rejected_total;
            public int student_mask_non_noop_available_at_stop;
            public int student_decision_cap_remaining_at_stop;
            public int player1_workers_at_stop;
            public int player2_workers_at_stop;
            public int player1_workers_carrying_at_stop;
            public int player2_workers_carrying_at_stop;
            public int player1_production_busy_count_at_stop;
            public int player2_production_busy_count_at_stop;
            public int player1_bases_at_stop;
            public int player2_bases_at_stop;
            public int active_resource_nodes_at_stop;
            public int total_remaining_resources_at_stop;
        }

        private readonly struct RuntimeRejectionInfo
        {
            public RuntimeRejectionInfo(string reason, MatchCommand command)
            {
                Reason = string.IsNullOrWhiteSpace(reason) ? "other" : reason;
                HasCommand = true;
                ActionType = command.ActionType;
                Direction = command.Direction;
            }

            public string Reason { get; }
            public bool HasCommand { get; }
            public UnitActionType ActionType { get; }
            public Direction Direction { get; }
        }

        private readonly struct DirectRuntimeRejectTrace
        {
            public DirectRuntimeRejectTrace(MatchCommandRejectionDiagnostics diagnostics)
            {
                HasTrace = diagnostics.HasDiagnostics;
                RejectCallsite = string.IsNullOrWhiteSpace(diagnostics.RejectCallsite)
                    ? "NOT_EXPOSED"
                    : diagnostics.RejectCallsite;
                RejectReasonRaw = string.IsNullOrWhiteSpace(diagnostics.RejectReasonRaw)
                    ? "NOT_EXPOSED"
                    : diagnostics.RejectReasonRaw;
                RejectReasonNormalized = string.IsNullOrWhiteSpace(diagnostics.RejectReasonNormalized)
                    ? "NOT_EXPOSED"
                    : diagnostics.RejectReasonNormalized;
                ActionType = diagnostics.ActionType.ToString();
                MoveDir = (int)diagnostics.MoveDir;
                SourceCellFromCommand = diagnostics.SourceCellFromCommand;
                SourceXFromCommand = diagnostics.SourceXFromCommand;
                SourceYFromCommand = diagnostics.SourceYFromCommand;
                TargetCellFromCommand = diagnostics.TargetCellFromCommand;
                TargetXFromCommand = diagnostics.TargetXFromCommand;
                TargetYFromCommand = diagnostics.TargetYFromCommand;
                UnitId = string.IsNullOrWhiteSpace(diagnostics.UnitId) ? "NOT_EXPOSED" : diagnostics.UnitId;
                UnitOwner = string.IsNullOrWhiteSpace(diagnostics.UnitOwner) ? "NOT_EXPOSED" : diagnostics.UnitOwner;
                UnitType = string.IsNullOrWhiteSpace(diagnostics.UnitType) ? "NOT_EXPOSED" : diagnostics.UnitType;
                UnitPositionXAtReject = diagnostics.UnitPositionXAtReject;
                UnitPositionYAtReject = diagnostics.UnitPositionYAtReject;
                UnitCellAtReject = diagnostics.UnitCellAtReject;
                OccupantExistsAtTarget = diagnostics.OccupantExistsAtTarget;
                OccupantIdAtTarget = string.IsNullOrWhiteSpace(diagnostics.OccupantIdAtTarget) ? "NOT_EXPOSED" : diagnostics.OccupantIdAtTarget;
                OccupantOwnerAtTarget = string.IsNullOrWhiteSpace(diagnostics.OccupantOwnerAtTarget) ? "NOT_EXPOSED" : diagnostics.OccupantOwnerAtTarget;
                OccupantTypeAtTarget = string.IsNullOrWhiteSpace(diagnostics.OccupantTypeAtTarget) ? "NOT_EXPOSED" : diagnostics.OccupantTypeAtTarget;
                OccupantXAtTarget = diagnostics.OccupantXAtTarget;
                OccupantYAtTarget = diagnostics.OccupantYAtTarget;
                OccupantCellAtTarget = diagnostics.OccupantCellAtTarget;
                OccupancyLookupKeyCell = diagnostics.OccupancyLookupKeyCell;
                OccupancyLookupKeyX = diagnostics.OccupancyLookupKeyX;
                OccupancyLookupKeyY = diagnostics.OccupancyLookupKeyY;
                TryGetOccupantResult = diagnostics.TryGetOccupantResult;
                OccupantRefExists = diagnostics.OccupantRefExists;
                OccupantInstanceId = diagnostics.OccupantInstanceId;
                OccupantName = string.IsNullOrWhiteSpace(diagnostics.OccupantName)
                    ? "NOT_EXPOSED"
                    : diagnostics.OccupantName;
                OccupantLogicalX = diagnostics.OccupantLogicalX;
                OccupantLogicalY = diagnostics.OccupantLogicalY;
                OccupantLogicalCell = diagnostics.OccupantLogicalCell;
                OccupantLogicalCellRoundtripOk = diagnostics.OccupantLogicalCellRoundtripOk;
                OccupantLogicalCellMatchesLookupKey = diagnostics.OccupantLogicalCellMatchesLookupKey;
                OccupantLogicalCellMatchesTargetCell = diagnostics.OccupantLogicalCellMatchesTargetCell;
                OccupantTransformX = diagnostics.OccupantTransformX;
                OccupantTransformY = diagnostics.OccupantTransformY;
                OccupantVisualGridX = diagnostics.OccupantVisualGridX;
                OccupantVisualGridY = diagnostics.OccupantVisualGridY;
                OccupantVisualCell = diagnostics.OccupantVisualCell;
                OccupantVisualCellMatchesLogicalCell = diagnostics.OccupantVisualCellMatchesLogicalCell;
                GridLookupByTargetReturnsOccupant = diagnostics.GridLookupByTargetReturnsOccupant;
                GridLookupByOccupantLogicalCellReturnsSameOccupant = diagnostics.GridLookupByOccupantLogicalCellReturnsSameOccupant;
                GridLookupByOccupantVisualCellReturnsSameOccupant = diagnostics.GridLookupByOccupantVisualCellReturnsSameOccupant;
                OccupancyMapKeyMatchesOccupantLogicalPosition = diagnostics.OccupancyMapKeyMatchesOccupantLogicalPosition;
                OccupantCellReportedPrevious = diagnostics.OccupantCellReportedPrevious;
                OccupancyLookupMethod = string.IsNullOrWhiteSpace(diagnostics.OccupancyLookupMethod)
                    ? "NOT_EXPOSED"
                    : diagnostics.OccupancyLookupMethod;
                OccupancyLookupSource = string.IsNullOrWhiteSpace(diagnostics.OccupancyLookupSource)
                    ? "NOT_EXPOSED"
                    : diagnostics.OccupancyLookupSource;
                TargetInBoundsAtReject = diagnostics.TargetInBoundsAtReject;
                TargetPassableAtReject = diagnostics.TargetPassableAtReject;
                TargetOccupiedAtReject = diagnostics.TargetOccupiedAtReject;
                TargetOccupiedByRuntimeLookup = diagnostics.TargetOccupiedByRuntimeLookup;
                DirectRuntimeTargetMatchesReconstructedTarget = diagnostics.DirectRuntimeTargetMatchesReconstructedTarget;
            }

            public bool HasTrace { get; }
            public string RejectCallsite { get; }
            public string RejectReasonRaw { get; }
            public string RejectReasonNormalized { get; }
            public string ActionType { get; }
            public int MoveDir { get; }
            public int SourceCellFromCommand { get; }
            public int SourceXFromCommand { get; }
            public int SourceYFromCommand { get; }
            public int TargetCellFromCommand { get; }
            public int TargetXFromCommand { get; }
            public int TargetYFromCommand { get; }
            public string UnitId { get; }
            public string UnitOwner { get; }
            public string UnitType { get; }
            public int UnitPositionXAtReject { get; }
            public int UnitPositionYAtReject { get; }
            public int UnitCellAtReject { get; }
            public bool OccupantExistsAtTarget { get; }
            public string OccupantIdAtTarget { get; }
            public string OccupantOwnerAtTarget { get; }
            public string OccupantTypeAtTarget { get; }
            public int OccupantXAtTarget { get; }
            public int OccupantYAtTarget { get; }
            public int OccupantCellAtTarget { get; }
            public int OccupancyLookupKeyCell { get; }
            public int OccupancyLookupKeyX { get; }
            public int OccupancyLookupKeyY { get; }
            public bool TryGetOccupantResult { get; }
            public bool OccupantRefExists { get; }
            public int OccupantInstanceId { get; }
            public string OccupantName { get; }
            public int OccupantLogicalX { get; }
            public int OccupantLogicalY { get; }
            public int OccupantLogicalCell { get; }
            public bool OccupantLogicalCellRoundtripOk { get; }
            public bool OccupantLogicalCellMatchesLookupKey { get; }
            public bool OccupantLogicalCellMatchesTargetCell { get; }
            public float OccupantTransformX { get; }
            public float OccupantTransformY { get; }
            public int OccupantVisualGridX { get; }
            public int OccupantVisualGridY { get; }
            public int OccupantVisualCell { get; }
            public bool OccupantVisualCellMatchesLogicalCell { get; }
            public bool GridLookupByTargetReturnsOccupant { get; }
            public bool GridLookupByOccupantLogicalCellReturnsSameOccupant { get; }
            public bool GridLookupByOccupantVisualCellReturnsSameOccupant { get; }
            public bool OccupancyMapKeyMatchesOccupantLogicalPosition { get; }
            public int OccupantCellReportedPrevious { get; }
            public string OccupancyLookupMethod { get; }
            public string OccupancyLookupSource { get; }
            public bool TargetInBoundsAtReject { get; }
            public bool TargetPassableAtReject { get; }
            public bool TargetOccupiedAtReject { get; }
            public bool TargetOccupiedByRuntimeLookup { get; }
            public bool DirectRuntimeTargetMatchesReconstructedTarget { get; }
        }

        private sealed class CommandEventTelemetry
        {
            public CommandEventTelemetry(long commandId, int step, int flat, string key, MatchCommand command)
            {
                CommandId = commandId;
                Step = step;
                Flat = flat;
                Key = key ?? string.Empty;
                Command = command;
                RejectReason = string.Empty;
                RejectReasonRaw = string.Empty;
                ConflictType = string.Empty;
                DirectRuntimeRejectTrace = default;
            }

            public long CommandId { get; }
            public int Step { get; }
            public int Flat { get; }
            public string Key { get; }
            public MatchCommand Command { get; }
            public bool AcceptedSeen { get; private set; }
            public bool RejectedSeen { get; private set; }
            public string RejectReason { get; private set; }
            public string RejectReasonRaw { get; private set; }
            public int LastEventSequence { get; private set; }
            public string LastEventSource { get; private set; }
            public string ConflictType { get; private set; }
            public DirectRuntimeRejectTrace DirectRuntimeRejectTrace { get; private set; }
            public bool HasDirectRuntimeRejectTrace => DirectRuntimeRejectTrace.HasTrace;

            public bool HasConflictingTerminalEvents => AcceptedSeen && RejectedSeen;

            public void MarkAccepted(int eventSequence)
            {
                AcceptedSeen = true;
                LastEventSequence = Mathf.Max(LastEventSequence, eventSequence);
                LastEventSource = "matchmanager.accepted";
                if (RejectedSeen)
                {
                    ConflictType = "same_command_both_events";
                }
            }

            public void MarkRejected(string reason, string reasonRaw, DirectRuntimeRejectTrace trace, int eventSequence)
            {
                RejectedSeen = true;
                RejectReason = string.IsNullOrWhiteSpace(reason) ? string.Empty : reason;
                RejectReasonRaw = string.IsNullOrWhiteSpace(reasonRaw) ? string.Empty : reasonRaw;
                DirectRuntimeRejectTrace = trace;
                LastEventSequence = Mathf.Max(LastEventSequence, eventSequence);
                LastEventSource = "matchmanager.rejected";
                if (AcceptedSeen)
                {
                    ConflictType = "same_command_both_events";
                }
            }
        }

        private readonly struct CommandTelemetrySelection
        {
            public CommandTelemetrySelection(
                CommandEventTelemetry selected,
                int candidateCount,
                bool anyAcceptedSeen,
                bool anyRejectedSeen,
                bool differentCommandConflict)
            {
                Selected = selected;
                CandidateCount = candidateCount;
                AnyAcceptedSeen = anyAcceptedSeen;
                AnyRejectedSeen = anyRejectedSeen;
                DifferentCommandConflict = differentCommandConflict;
            }

            public CommandEventTelemetry Selected { get; }
            public int CandidateCount { get; }
            public bool AnyAcceptedSeen { get; }
            public bool AnyRejectedSeen { get; }
            public bool DifferentCommandConflict { get; }
            public bool HasAny => CandidateCount > 0;
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
            ApplyRuntimePerformanceSettings();
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

        public void ConfigureRuntimePerformanceMode(
            Week6VisualRuntimeMode mode,
            bool demoMode,
            bool enableOverlay,
            bool enableJsonTrace,
            int diagnosticSamplingInterval,
            int targetFrameRate,
            float decisionTickIntervalSeconds)
        {
            _runtimeMode = mode;
            _demoMode = demoMode;
            _enableOverlay = enableOverlay;
            _enableJsonTrace = enableJsonTrace;
            _diagnosticSamplingInterval = Mathf.Max(1, diagnosticSamplingInterval);
            _targetFrameRate = targetFrameRate;
            _decisionTickIntervalSeconds = Mathf.Max(0f, decisionTickIntervalSeconds);
            ApplyRuntimePerformanceSettings();
        }

        private void ApplyRuntimePerformanceSettings()
        {
            bool demo = _demoMode || _runtimeMode == Week6VisualRuntimeMode.Demo;
            bool profiler = !_demoMode && _runtimeMode == Week6VisualRuntimeMode.Profiler;

            if (demo || profiler)
            {
                _enableOverlay = false;
                _enableJsonTrace = false;
                _showOverlay = false;
                _showGridLabels = false;
                _showActionMarkers = false;
                _writePlayModeStopDiagnostics = false;
            }
            else
            {
                _showOverlay = _enableOverlay;
                _writePlayModeStopDiagnostics = _enableJsonTrace;
            }

            _diagnosticSamplingInterval = Mathf.Max(1, _diagnosticSamplingInterval);
            _decisionTickIntervalSeconds = Mathf.Max(0f, _decisionTickIntervalSeconds);

            if (_targetFrameRate > 0)
            {
                QualitySettings.vSyncCount = 0;
                Application.targetFrameRate = _targetFrameRate;
            }

            if (_episodeController != null)
            {
                _episodeController.DecisionTickIntervalSeconds = _decisionTickIntervalSeconds;
            }

            _performanceSummaryWritten = false;
            Stage6B3PerformanceCounters.Configure(
                _enableProfilerCounters,
                ResolveRuntimeModeLabel(),
                SceneManager.GetActiveScene().path,
                _targetFrameRate,
                _decisionTickIntervalSeconds);
        }

        private bool ShouldSampleDiagnosticsStep(int step)
        {
            if (!_enableJsonTrace)
            {
                return false;
            }

            int interval = Mathf.Max(1, _diagnosticSamplingInterval);
            return step <= 5 || step % interval == 0;
        }

        private bool ShouldRefreshVisualDiagnostics(int step)
        {
            if (!_enableOverlay && !_showGridLabels && !_showActionMarkers && !_enableJsonTrace)
            {
                return false;
            }

            int interval = Mathf.Max(1, _diagnosticSamplingInterval);
            return _enableOverlay || step <= 5 || step % interval == 0;
        }

        private string ResolveRuntimeModeLabel()
        {
            if (_demoMode)
            {
                return "Demo";
            }

            return _runtimeMode.ToString();
        }

        private void OnDisable()
        {
            WritePerformanceSummary("runner_disabled");
            UnsubscribeFromMatchEvents();
            UnsubscribeHeuristicEvents();
        }

        private void Update()
        {
            Stage6B3PerformanceCounters.RecordFrame(Time.unscaledDeltaTime);
            long perfStart = Stage6B3PerformanceCounters.Begin(Stage6B3PerfMetric.VisualRunnerUpdate);

            ResolveReferences();
            HandleKeyboardShortcuts();
            ApplyVisualScaleOverrides();
            UpdateAutoPlayback();

            if (!_sessionActive || _episodeController == null || _matchManager == null)
            {
                Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.VisualRunnerUpdate, perfStart);
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
                Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.VisualRunnerUpdate, perfStart);
                return;
            }

            _lastCollectedStep = currentStep;

            bool hasStudentReport = false;
            StudentPolicyExecutionReport report = default;

            if (_episodeController.TryGetWeek6StudentExecutionReport(_studentControlledPlayer, out report))
            {
                hasStudentReport = true;
                bool sampleDiagnostics = ShouldSampleDiagnosticsStep(currentStep);
                if (sampleDiagnostics)
                {
                    RecordStage6R5CLifecycleForStep(currentStep, report);
                }

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

                if (sampleDiagnostics)
                {
                    _diagnosticsCollector?.RecordStudentDecodedActions(report.DecodedActions);
                    _diagnosticsCollector?.RecordStudentRejectionReasons(report.RejectionReasons);
                    _diagnosticsCollector?.RecordStudentFilterDiagnostics(report.FilterDiagnostics);
                    _diagnosticsCollector?.RecordStudentMaskAwareDiagnostics(report.MaskAwareDiagnostics);
                }

                MergeActionHistogram(_aggregateActionTypeHistogram, report.MaskAwareDiagnostics.PostMaskHistogram);
                MergeActionHistogram(_aggregateActorActionTypeHistogram, report.MaskAwareDiagnostics.PostMaskHistogram);

                if (ShouldRefreshVisualDiagnostics(currentStep))
                {
                    _latestMaskAwareCellTelemetryByFlat.Clear();
                    foreach (KeyValuePair<int, ActionDecoder.MaskAwareCellTelemetry> kvp in report.MaskAwareDiagnostics.CellTelemetryByFlat)
                    {
                        _latestMaskAwareCellTelemetryByFlat[kvp.Key] = kvp.Value;
                    }
                    _latestLegalMaskByFlat.Clear();
                    foreach (KeyValuePair<int, StudentMaskAwareDiagnostics.ActorLegalMaskTelemetry> kvp in report.MaskAwareDiagnostics.LegalMaskByFlat)
                    {
                        _latestLegalMaskByFlat[kvp.Key] = kvp.Value;
                    }
                }

                for (int i = 0; i < report.RejectionReasons.Count; i++)
                {
                    IncrementStringCount(_rejectionReasons, NormalizeReason(report.RejectionReasons[i]));
                }
            }
            else
            {
                _latestMaskAwareCellTelemetryByFlat.Clear();
                _latestLegalMaskByFlat.Clear();
            }

            if (_enableJsonTrace)
            {
                RecordPlayModeStepTrace(currentStep, hasStudentReport, report);
            }

            if (currentStep > 0)
            {
                if (ShouldSampleDiagnosticsStep(currentStep))
                {
                    _diagnosticsCollector?.RecordStepCompleted();
                    FinalizeStage6R5CCompletedSteps(currentStep);
                }
            }

            if (ShouldRefreshVisualDiagnostics(currentStep))
            {
                long refreshStart = Stage6B3PerformanceCounters.Begin(Stage6B3PerfMetric.VisualDiagnosticsRefresh);
                RefreshLatestDiagnosticsFromArtifacts();
                BuildActorRowsForOverlay();
                Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.VisualDiagnosticsRefresh, refreshStart);
            }

            _lastStepSnapshotReady = true;

            EpisodeEndReport terminalReport = _episodeController.LastTerminalReport;
            if (terminalReport.IsTerminal)
            {
                _lastTerminalReason = terminalReport.TerminalReason.ToString();
            }

            Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.VisualRunnerUpdate, perfStart);
        }

        private void OnGUI()
        {
            if (!_showOverlay || !_enableOverlay)
            {
                return;
            }

            long perfStart = Stage6B3PerformanceCounters.Begin(Stage6B3PerfMetric.OnGui);
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
            GUILayout.Label($"Focus cells: {FocusWorkerLabel}(flat{FocusFlatWorker}) top={_b2TopAction}; {FocusBaseLabel}(flat{FocusFlatBase}) top={_c3TopAction}");
            GUILayout.Label($"Probe classification: {_noOpProbeClassification}");
            GUILayout.Label($"Flatten classification: {_flattenAlignmentClassification}");

            ActorCellDiagnosticRow b2Row;
            ActorCellDiagnosticRow c3Row;
            _latestActorRowsByFlatIndex.TryGetValue(FocusFlatWorker, out b2Row);
            _latestActorRowsByFlatIndex.TryGetValue(FocusFlatBase, out c3Row);
            GUILayout.Label(FocusWorkerLabel + " probs: " + BuildFocusProbabilitiesLine(b2Row));
            GUILayout.Label(FocusBaseLabel + " probs: " + BuildFocusProbabilitiesLine(c3Row));

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
            Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.OnGui, perfStart);
        }

        private void OnDrawGizmos()
        {
            if (!_showActionMarkers && !_showGridLabels)
            {
                return;
            }

            long perfStart = Stage6B3PerformanceCounters.Begin(Stage6B3PerfMetric.Gizmos);
            ResolveReferences();
            if (_gridManager == null)
            {
                Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.Gizmos, perfStart);
                return;
            }

            if (_showActionMarkers)
            {
                DrawUnitMarkers();
                DrawActorMarkers();
                DrawBaselineCommandMarkers();
            }

#if UNITY_EDITOR
            if (_showGridLabels)
            {
                DrawGridLabels();
            }
#endif
            Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.Gizmos, perfStart);
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

        /// <summary>
        /// Sets mode-isolation context for snapshot telemetry (Stage10D25).
        /// Call before RunSingleMode to correctly attribute policy source.
        /// </summary>
        public void SetCurrentCaptureModeContext(
            string modeName,
            Week6PlayerControlMode player1Mode,
            Week6PlayerControlMode player2Mode)
        {
            _captureModeName = modeName ?? string.Empty;
            _capturePlayer1Mode = player1Mode;
            _capturePlayer2Mode = player2Mode;
            _captureModeContextSet = true;
        }

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
            _commandTelemetryByKey.Clear();
            _commandTelemetryByFlat.Clear();
            _latestMaskAwareCellTelemetryByFlat.Clear();
            _latestLegalMaskByFlat.Clear();

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
                // Mode-isolation telemetry (Stage10D25)
                mode = _captureModeContextSet ? _captureModeName : "unset",
                policy_source = ResolvePolicySource(),
                inference_source = ResolveInferenceSource(),
                uses_student_checkpoint = ResolveUsesStudentCheckpoint(),
                uses_python_adapter = ResolveUsesPythonAdapter(),
                uses_heuristic_policy = ResolveUsesHeuristicPolicy(),
                action_buffer_source = ResolveActionBufferSource(),
                player1_resources = _matchManager != null ? _matchManager.GetResources(Owner.Player1) : 0,
                player2_resources = _matchManager != null ? _matchManager.GetResources(Owner.Player2) : 0,
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
                adapter_invoked = ResolveAdapterInvoked(),
                inference_request_count = _latestInferenceDiagnostics != null ? _latestInferenceDiagnostics.inference_request_count : 0,
                last_inference_call_utc = _latestInferenceDiagnostics != null ? _latestInferenceDiagnostics.last_inference_call_utc : string.Empty,
                candidate_actor_cells_submitted = _latestInferenceDiagnostics != null ? _latestInferenceDiagnostics.candidate_actor_cells_submitted : 0,
                python_request_status = _latestInferenceDiagnostics != null ? _latestInferenceDiagnostics.python_request_status : string.Empty,
                python_response_status = _latestInferenceDiagnostics != null ? _latestInferenceDiagnostics.python_response_status : string.Empty,
                legal_mask_enabled_for_selection = _studentAdapter != null && _studentAdapter.EnableLegalActionMaskForSelection,
                total_mask_fallback_to_noop = _totalFallbackToNoop,
                total_masked_out_action_type_choices = _totalMaskedOutActionChoices,
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
            int currentStep = _matchManager != null ? _matchManager.Step : 0;
            PruneCommandTelemetry(currentStep);
            var runtimeByFlat = new Dictionary<int, UnitRuntime>(ActionContract.TotalCells);
            var maskTelemetryByFlat = new Dictionary<int, ActionDecoder.MaskAwareCellTelemetry>();
            var legalMaskByFlat = new Dictionary<int, StudentMaskAwareDiagnostics.ActorLegalMaskTelemetry>();

            if (_episodeController != null
                && _episodeController.TryGetWeek6StudentExecutionReport(_studentControlledPlayer, out StudentPolicyExecutionReport liveReport))
            {
                foreach (KeyValuePair<int, ActionDecoder.MaskAwareCellTelemetry> kvp in liveReport.MaskAwareDiagnostics.CellTelemetryByFlat)
                {
                    maskTelemetryByFlat[kvp.Key] = kvp.Value;
                }

                foreach (KeyValuePair<int, StudentMaskAwareDiagnostics.ActorLegalMaskTelemetry> kvp in liveReport.MaskAwareDiagnostics.LegalMaskByFlat)
                {
                    legalMaskByFlat[kvp.Key] = kvp.Value;
                }
            }
            else
            {
                foreach (KeyValuePair<int, ActionDecoder.MaskAwareCellTelemetry> kvp in _latestMaskAwareCellTelemetryByFlat)
                {
                    maskTelemetryByFlat[kvp.Key] = kvp.Value;
                }

                foreach (KeyValuePair<int, StudentMaskAwareDiagnostics.ActorLegalMaskTelemetry> kvp in _latestLegalMaskByFlat)
                {
                    legalMaskByFlat[kvp.Key] = kvp.Value;
                }
            }

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
                bool commandBuilt = predictedNonNoOp && runtimeIsFriendlyActor;
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
                    else
                    {
                        decoderResult = "command_built";
                    }
                }

                bool hasMaskTelemetry = maskTelemetryByFlat.TryGetValue(flat, out ActionDecoder.MaskAwareCellTelemetry maskTelemetry);
                string rawActionTypeTop1 = hasMaskTelemetry
                    ? maskTelemetry.RawActionTypeTop1.ToString()
                    : predictedActionTypeName;
                int rawMoveDirTop1 = hasMaskTelemetry ? maskTelemetry.RawMoveDirTop1 : moveDirFinal;
                int rawHarvestDirTop1 = hasMaskTelemetry ? maskTelemetry.RawHarvestDirTop1 : harvestDirFinal;
                int rawReturnDirTop1 = hasMaskTelemetry ? maskTelemetry.RawReturnDirTop1 : returnDirFinal;
                int rawProduceDirTop1 = hasMaskTelemetry ? maskTelemetry.RawProduceDirTop1 : produceDirFinal;
                int rawProduceUnitTypeTop1 = hasMaskTelemetry ? maskTelemetry.RawProduceUnitTypeTop1 : produceUnitTypeFinal;
                int rawAttackTargetLocalTop1 = hasMaskTelemetry ? maskTelemetry.RawAttackTargetLocalTop1 : attackTargetLocalFinal;
                string maskedActionType = hasMaskTelemetry
                    ? maskTelemetry.MaskedActionType.ToString()
                    : predictedActionTypeName;
                int maskedMoveDir = hasMaskTelemetry ? maskTelemetry.MaskedMoveDir : moveDirFinal;
                int maskedHarvestDir = hasMaskTelemetry ? maskTelemetry.MaskedHarvestDir : harvestDirFinal;
                int maskedReturnDir = hasMaskTelemetry ? maskTelemetry.MaskedReturnDir : returnDirFinal;
                int maskedProduceDir = hasMaskTelemetry ? maskTelemetry.MaskedProduceDir : produceDirFinal;
                int maskedProduceUnitType = hasMaskTelemetry ? maskTelemetry.MaskedProduceUnitType : produceUnitTypeFinal;
                int maskedAttackTargetLocal = hasMaskTelemetry ? maskTelemetry.MaskedAttackTargetLocal : attackTargetLocalFinal;
                bool[] legalActionTypeMask = hasMaskTelemetry ? CopyBoolArray(maskTelemetry.LegalActionTypeMask) : Array.Empty<bool>();
                bool[] legalMoveDirMask = hasMaskTelemetry ? CopyBoolArray(maskTelemetry.LegalMoveDirMask) : Array.Empty<bool>();
                if (!hasMaskTelemetry
                    && legalMaskByFlat.TryGetValue(flat, out StudentMaskAwareDiagnostics.ActorLegalMaskTelemetry legalMaskTelemetry))
                {
                    legalActionTypeMask = CopyBoolArray(legalMaskTelemetry.ActionTypeMask);
                    legalMoveDirMask = CopyBoolArray(legalMaskTelemetry.MoveDirMask);
                }
                bool maskedMoveDirLegal = hasMaskTelemetry
                    ? maskTelemetry.MaskedMoveDirLegal
                    : IsMoveDirLegal(legalMoveDirMask, maskedMoveDir);
                bool branchMaskAppliedForMove = hasMaskTelemetry
                    ? maskTelemetry.BranchMaskAppliedForMove
                    : (predictedActionType == UnitActionType.Move);
                string moveDirMaskFallbackReason = hasMaskTelemetry
                    ? (maskTelemetry.MoveDirMaskFallbackReason ?? string.Empty)
                    : string.Empty;
                bool branchParameterMaskApplied = hasMaskTelemetry && maskTelemetry.BranchParameterMaskApplied;
                string branchParameterMaskReason = hasMaskTelemetry
                    ? (maskTelemetry.BranchParameterMaskReason ?? string.Empty)
                    : string.Empty;

                if (!runtimeIsFriendlyActor)
                {
                    maskedActionType = UnitActionType.NoOp.ToString();
                    maskedMoveDirLegal = true;
                    branchMaskAppliedForMove = false;
                    if (string.IsNullOrWhiteSpace(moveDirMaskFallbackReason))
                    {
                        moveDirMaskFallbackReason = "off_actor_forced_noop";
                    }
                }

                CommandTelemetrySelection telemetrySelection = SelectCommandTelemetry(flat, currentStep, maskedActionType, maskedMoveDir, predictedActionType);
                CommandEventTelemetry selectedTelemetry = telemetrySelection.Selected;

                bool applierAccepted = selectedTelemetry != null && selectedTelemetry.AcceptedSeen;
                bool applierRejected = selectedTelemetry != null && selectedTelemetry.RejectedSeen;
                bool hasCommandEvent = selectedTelemetry != null;
                bool applierSubmitted = commandBuilt || hasCommandEvent;
                string applierRejectReason = string.Empty;
                if (applierRejected)
                {
                    applierRejectReason = selectedTelemetry.RejectReason;
                }

                UnitActionType decoderReceivedActionTypeValue = UnitActionType.NoOp;
                int decoderReceivedMoveDir = 0;
                if (selectedTelemetry != null)
                {
                    decoderReceivedActionTypeValue = selectedTelemetry.Command.ActionType;
                    decoderReceivedMoveDir = (int)selectedTelemetry.Command.Direction;
                }
                else if (hasMaskTelemetry)
                {
                    decoderReceivedActionTypeValue = maskTelemetry.DecoderReceivedActionType;
                    decoderReceivedMoveDir = maskTelemetry.DecoderReceivedMoveDir;
                }

                bool decoderReceivedMoveDirLegal = decoderReceivedActionTypeValue != UnitActionType.Move
                    || IsMoveDirLegal(legalMoveDirMask, decoderReceivedMoveDir);

                bool commandSubmitted = commandBuilt || hasCommandEvent;
                bool sameCommandConflict = selectedTelemetry != null && selectedTelemetry.HasConflictingTerminalEvents;
                bool differentCommandConflict = telemetrySelection.DifferentCommandConflict;
                bool legacyConflict = sameCommandConflict || differentCommandConflict;
                DirectRuntimeRejectTrace directRejectTrace = selectedTelemetry != null
                    ? selectedTelemetry.DirectRuntimeRejectTrace
                    : default;
                string commandResultStatus;
                string rejectStage = string.Empty;
                string rejectReason = string.Empty;
                string rejectReasonRaw = selectedTelemetry != null ? selectedTelemetry.RejectReasonRaw : string.Empty;
                string rejectReasonNormalized = selectedTelemetry != null ? selectedTelemetry.RejectReason : string.Empty;
                string commandEventConflict = string.Empty;

                if (sameCommandConflict)
                {
                    commandResultStatus = "telemetry_conflict";
                    rejectStage = "telemetry";
                    rejectReason = string.IsNullOrWhiteSpace(applierRejectReason)
                        ? "same_command_both_events"
                        : applierRejectReason;
                    commandEventConflict = "same_command_both_events";
                }
                else if (differentCommandConflict)
                {
                    commandResultStatus = "telemetry_conflict";
                    rejectStage = "telemetry";
                    rejectReason = "different_commands_same_flat";
                    commandEventConflict = "different_commands_same_flat";
                }
                else if (!predictedNonNoOp && !hasCommandEvent)
                {
                    commandResultStatus = "not_submitted";
                }
                else if (!commandBuilt)
                {
                    if (hasCommandEvent)
                    {
                        if (applierRejected)
                        {
                            commandResultStatus = "matchmanager_rejected";
                            rejectStage = "matchmanager";
                            rejectReason = applierRejectReason;
                            if (string.IsNullOrWhiteSpace(rejectReasonRaw))
                            {
                                rejectReasonRaw = applierRejectReason;
                            }

                            if (string.IsNullOrWhiteSpace(rejectReasonNormalized))
                            {
                                rejectReasonNormalized = applierRejectReason;
                            }
                        }
                        else
                        {
                            commandResultStatus = "accepted_pending";
                        }
                    }
                    else
                    {
                        commandResultStatus = "decoder_rejected";
                        rejectStage = "decoder";
                        rejectReason = decoderRejectReason;
                    }
                }
                else if (applierRejected)
                {
                    commandResultStatus = "matchmanager_rejected";
                    rejectStage = "matchmanager";
                    rejectReason = applierRejectReason;
                    if (string.IsNullOrWhiteSpace(rejectReasonRaw))
                    {
                        rejectReasonRaw = applierRejectReason;
                    }

                    if (string.IsNullOrWhiteSpace(rejectReasonNormalized))
                    {
                        rejectReasonNormalized = applierRejectReason;
                    }
                }
                else if (applierAccepted)
                {
                    commandResultStatus = "accepted_pending";
                }
                else if (commandBuilt)
                {
                    commandResultStatus = "accepted_pending";
                }
                else
                {
                    commandResultStatus = "not_submitted";
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
                    raw_action_type_top1 = rawActionTypeTop1,
                    raw_move_dir_top1 = rawMoveDirTop1,
                    raw_harvest_dir_top1 = rawHarvestDirTop1,
                    raw_return_dir_top1 = rawReturnDirTop1,
                    raw_produce_dir_top1 = rawProduceDirTop1,
                    raw_produce_unit_type_top1 = rawProduceUnitTypeTop1,
                    raw_attack_target_local_top1 = rawAttackTargetLocalTop1,
                    masked_action_type = maskedActionType,
                    masked_move_dir = maskedMoveDir,
                    masked_harvest_dir = maskedHarvestDir,
                    masked_return_dir = maskedReturnDir,
                    masked_produce_dir = maskedProduceDir,
                    masked_produce_unit_type = maskedProduceUnitType,
                    masked_attack_target_local = maskedAttackTargetLocal,
                    legal_action_type_mask = legalActionTypeMask,
                    legal_move_dir_mask = legalMoveDirMask,
                    masked_move_dir_legal = maskedMoveDirLegal,
                    branch_mask_applied_for_move = branchMaskAppliedForMove,
                    move_dir_mask_fallback_reason = moveDirMaskFallbackReason,
                    branch_parameter_mask_applied = branchParameterMaskApplied,
                    branch_parameter_mask_reason = branchParameterMaskReason,
                    decoder_received_action_type = decoderReceivedActionTypeValue.ToString(),
                    decoder_received_move_dir = decoderReceivedMoveDir,
                    decoder_received_move_dir_legal = decoderReceivedMoveDirLegal,
                    decoder_result_if_predicted_non_noop = hasCommandEvent && !predictedNonNoOp
                        ? "external_command_submission"
                        : decoderResult,
                    command_built = commandBuilt,
                    command_submitted = commandSubmitted,
                    command_result_status = commandResultStatus,
                    command_id = selectedTelemetry != null ? selectedTelemetry.CommandId : 0L,
                    command_event_step = selectedTelemetry != null ? selectedTelemetry.Step : -1,
                    command_event_sequence = selectedTelemetry != null ? selectedTelemetry.LastEventSequence : 0,
                    command_event_source = selectedTelemetry != null
                        ? (selectedTelemetry.LastEventSource ?? string.Empty)
                        : "none",
                    command_event_key = selectedTelemetry != null ? selectedTelemetry.Key : string.Empty,
                    command_event_accepted = selectedTelemetry != null && selectedTelemetry.AcceptedSeen,
                    command_event_rejected = selectedTelemetry != null && selectedTelemetry.RejectedSeen,
                    command_event_conflict = commandEventConflict,
                    reject_stage = rejectStage,
                    reject_callsite = directRejectTrace.HasTrace ? directRejectTrace.RejectCallsite : "NOT_EXPOSED",
                    reject_reason = rejectReason,
                    reject_reason_raw = string.IsNullOrWhiteSpace(rejectReasonRaw) ? "NOT_EXPOSED" : rejectReasonRaw,
                    reject_reason_normalized = string.IsNullOrWhiteSpace(rejectReasonNormalized) ? "NOT_EXPOSED" : rejectReasonNormalized,
                    legacy_status_conflict = legacyConflict,
                    decoder_reject_reason = decoderRejectReason,
                    applier_submission_reached = applierSubmitted,
                    applier_submitted = applierSubmitted,
                    applier_accepted = applierAccepted,
                    applier_rejected = applierRejected,
                    applier_reject_reason = applierRejectReason,
                    action_type = selectedTelemetry != null
                        ? selectedTelemetry.Command.ActionType.ToString()
                        : "NOT_EXPOSED",
                    source_cell_from_command = directRejectTrace.HasTrace ? directRejectTrace.SourceCellFromCommand : -1,
                    source_x_from_command = directRejectTrace.HasTrace ? directRejectTrace.SourceXFromCommand : -1,
                    source_y_from_command = directRejectTrace.HasTrace ? directRejectTrace.SourceYFromCommand : -1,
                    target_cell_from_command = directRejectTrace.HasTrace ? directRejectTrace.TargetCellFromCommand : -1,
                    target_x_from_command = directRejectTrace.HasTrace ? directRejectTrace.TargetXFromCommand : -1,
                    target_y_from_command = directRejectTrace.HasTrace ? directRejectTrace.TargetYFromCommand : -1,
                    unit_id = directRejectTrace.HasTrace ? directRejectTrace.UnitId : "NOT_EXPOSED",
                    unit_owner = directRejectTrace.HasTrace ? directRejectTrace.UnitOwner : "NOT_EXPOSED",
                    unit_type = directRejectTrace.HasTrace ? directRejectTrace.UnitType : "NOT_EXPOSED",
                    unit_position_x_at_reject = directRejectTrace.HasTrace ? directRejectTrace.UnitPositionXAtReject : -1,
                    unit_position_y_at_reject = directRejectTrace.HasTrace ? directRejectTrace.UnitPositionYAtReject : -1,
                    unit_cell_at_reject = directRejectTrace.HasTrace ? directRejectTrace.UnitCellAtReject : -1,
                    occupant_exists_at_target = directRejectTrace.HasTrace ? directRejectTrace.OccupantExistsAtTarget.ToString() : "NOT_EXPOSED",
                    occupant_id_at_target = directRejectTrace.HasTrace ? directRejectTrace.OccupantIdAtTarget : "NOT_EXPOSED",
                    occupant_owner_at_target = directRejectTrace.HasTrace ? directRejectTrace.OccupantOwnerAtTarget : "NOT_EXPOSED",
                    occupant_type_at_target = directRejectTrace.HasTrace ? directRejectTrace.OccupantTypeAtTarget : "NOT_EXPOSED",
                    occupant_x_at_target = directRejectTrace.HasTrace ? directRejectTrace.OccupantXAtTarget : -1,
                    occupant_y_at_target = directRejectTrace.HasTrace ? directRejectTrace.OccupantYAtTarget : -1,
                    occupant_cell_at_target = directRejectTrace.HasTrace ? directRejectTrace.OccupantCellAtTarget : -1,
                    occupancy_lookup_key_cell = directRejectTrace.HasTrace ? directRejectTrace.OccupancyLookupKeyCell : -1,
                    occupancy_lookup_key_x = directRejectTrace.HasTrace ? directRejectTrace.OccupancyLookupKeyX : -1,
                    occupancy_lookup_key_y = directRejectTrace.HasTrace ? directRejectTrace.OccupancyLookupKeyY : -1,
                    try_get_occupant_result = directRejectTrace.HasTrace ? directRejectTrace.TryGetOccupantResult.ToString() : "NOT_EXPOSED",
                    occupant_ref_exists = directRejectTrace.HasTrace ? directRejectTrace.OccupantRefExists.ToString() : "NOT_EXPOSED",
                    occupant_instance_id = directRejectTrace.HasTrace ? directRejectTrace.OccupantInstanceId : 0,
                    occupant_name = directRejectTrace.HasTrace ? directRejectTrace.OccupantName : "NOT_EXPOSED",
                    occupant_logical_x = directRejectTrace.HasTrace ? directRejectTrace.OccupantLogicalX : -1,
                    occupant_logical_y = directRejectTrace.HasTrace ? directRejectTrace.OccupantLogicalY : -1,
                    occupant_logical_cell = directRejectTrace.HasTrace ? directRejectTrace.OccupantLogicalCell : -1,
                    occupant_logical_cell_roundtrip_ok = directRejectTrace.HasTrace ? directRejectTrace.OccupantLogicalCellRoundtripOk.ToString() : "NOT_EXPOSED",
                    occupant_logical_cell_matches_lookup_key = directRejectTrace.HasTrace ? directRejectTrace.OccupantLogicalCellMatchesLookupKey.ToString() : "NOT_EXPOSED",
                    occupant_logical_cell_matches_target_cell = directRejectTrace.HasTrace ? directRejectTrace.OccupantLogicalCellMatchesTargetCell.ToString() : "NOT_EXPOSED",
                    occupant_transform_x = directRejectTrace.HasTrace ? directRejectTrace.OccupantTransformX : float.NaN,
                    occupant_transform_y = directRejectTrace.HasTrace ? directRejectTrace.OccupantTransformY : float.NaN,
                    occupant_visual_grid_x = directRejectTrace.HasTrace ? directRejectTrace.OccupantVisualGridX : -1,
                    occupant_visual_grid_y = directRejectTrace.HasTrace ? directRejectTrace.OccupantVisualGridY : -1,
                    occupant_visual_cell = directRejectTrace.HasTrace ? directRejectTrace.OccupantVisualCell : -1,
                    occupant_visual_cell_matches_logical_cell = directRejectTrace.HasTrace ? directRejectTrace.OccupantVisualCellMatchesLogicalCell.ToString() : "NOT_EXPOSED",
                    grid_lookup_by_target_returns_occupant = directRejectTrace.HasTrace ? directRejectTrace.GridLookupByTargetReturnsOccupant.ToString() : "NOT_EXPOSED",
                    grid_lookup_by_occupant_logical_cell_returns_same_occupant = directRejectTrace.HasTrace ? directRejectTrace.GridLookupByOccupantLogicalCellReturnsSameOccupant.ToString() : "NOT_EXPOSED",
                    grid_lookup_by_occupant_visual_cell_returns_same_occupant = directRejectTrace.HasTrace ? directRejectTrace.GridLookupByOccupantVisualCellReturnsSameOccupant.ToString() : "NOT_EXPOSED",
                    occupancy_map_key_matches_occupant_logical_position = directRejectTrace.HasTrace ? directRejectTrace.OccupancyMapKeyMatchesOccupantLogicalPosition.ToString() : "NOT_EXPOSED",
                    occupant_cell_reported_previous = directRejectTrace.HasTrace ? directRejectTrace.OccupantCellReportedPrevious : -1,
                    occupancy_lookup_method = directRejectTrace.HasTrace ? directRejectTrace.OccupancyLookupMethod : "NOT_EXPOSED",
                    occupancy_lookup_source = directRejectTrace.HasTrace ? directRejectTrace.OccupancyLookupSource : "NOT_EXPOSED",
                    target_in_bounds_at_reject = directRejectTrace.HasTrace ? directRejectTrace.TargetInBoundsAtReject.ToString() : "NOT_EXPOSED",
                    target_passable_at_reject = directRejectTrace.HasTrace ? directRejectTrace.TargetPassableAtReject.ToString() : "NOT_EXPOSED",
                    target_occupied_at_reject = directRejectTrace.HasTrace ? directRejectTrace.TargetOccupiedAtReject.ToString() : "NOT_EXPOSED",
                    target_occupied_by_runtime_lookup = directRejectTrace.HasTrace ? directRejectTrace.TargetOccupiedByRuntimeLookup.ToString() : "NOT_EXPOSED",
                    target_occupied_by_snapshot_lookup = "INFERENCE_ONLY_NOT_FROM_MATCHMANAGER",
                    snapshot_step_used_for_attribution = -1,
                    direct_runtime_lookup_matches_snapshot_lookup = "NOT_COMPUTED_RUNTIME",
                    direct_runtime_target_matches_reconstructed_target = directRejectTrace.HasTrace
                        ? directRejectTrace.DirectRuntimeTargetMatchesReconstructedTarget.ToString()
                        : "NOT_EXPOSED",
                };

                rows.Add(row);
            }

            return rows;
        }

        private static bool[] CopyBoolArray(bool[] source)
        {
            if (source == null || source.Length == 0)
            {
                return Array.Empty<bool>();
            }

            var copy = new bool[source.Length];
            Array.Copy(source, copy, source.Length);
            return copy;
        }

        private static bool IsMoveDirLegal(bool[] moveDirMask, int moveDir)
        {
            return moveDirMask != null
                   && moveDir >= 0
                   && moveDir < moveDirMask.Length
                   && moveDirMask[moveDir];
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
            _commandTelemetryByKey.Clear();
            _commandTelemetryByFlat.Clear();
            _commandTelemetryIdSequence = 0;
            _commandTelemetryEventSequence = 0;
            _latestMaskAwareCellTelemetryByFlat.Clear();
            _latestLegalMaskByFlat.Clear();
            _lastBaselineAcceptedByActor.Clear();
            _lastBaselineRejectedByActor.Clear();
            _stage6r5cLifecycleRows.Clear();
            _stage6r5cLifecycleById.Clear();
            _stage6r5cPendingByEventKey.Clear();
            _stage6r5cTerminalEvents.Clear();
            _playModeStepTraceByStep.Clear();
            _heuristicEvaluationsPerStep.Clear();
            _heuristicNonNoOpPerStep.Clear();
            _heuristicAcceptedPerStep.Clear();
            _heuristicRejectedPerStep.Clear();
            _playModeStopDiagnosticsWritten = false;
            _performanceSummaryWritten = false;
            _lastStudentAcceptedForTrace = 0;
            _lastStudentRejectedForTrace = 0;
            _lastBaselineAcceptedForTrace = 0;
            _lastBaselineRejectedForTrace = 0;

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

            _matchManager.OnCommandRejectedDetailed -= HandleCommandRejectedDetailed;
            _matchManager.OnCommandRejectedDetailed += HandleCommandRejectedDetailed;

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

            _matchManager.OnCommandRejectedDetailed -= HandleCommandRejectedDetailed;
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
            if (!_enableJsonTrace)
            {
                _diagnosticsCollector = null;
                return;
            }

            Owner baseline = _studentControlledPlayer == Owner.Player1 ? Owner.Player2 : Owner.Player1;
            _diagnosticsCollector = new Week6EpisodeDiagnosticsCollector(_studentControlledPlayer, baseline);
        }

        private void HandleCommandAccepted(MatchCommand command)
        {
            if (!_sessionActive)
            {
                return;
            }

            if (_enableJsonTrace)
            {
                _diagnosticsCollector?.RecordRuntimeAccepted(command);
            }

            if (command.Owner == _studentControlledPlayer)
            {
                RecordCommandTelemetry(command, accepted: true, reason: string.Empty);
                if (_enableJsonTrace)
                {
                    RecordStage6R5CTerminalEvent(command, accepted: true, normalizedReason: string.Empty, rawReason: string.Empty, diagnostics: default);
                }
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
            HandleCommandRejectedInternal(command, reason, MatchCommandRejectionDiagnostics.None);
        }

        private void HandleCommandRejectedDetailed(MatchCommand command, string reason, MatchCommandRejectionDiagnostics diagnostics)
        {
            HandleCommandRejectedInternal(command, reason, diagnostics);
        }

        private void HandleCommandRejectedInternal(MatchCommand command, string reason, MatchCommandRejectionDiagnostics diagnostics)
        {
            if (!_sessionActive)
            {
                return;
            }

            if (_enableJsonTrace)
            {
                _diagnosticsCollector?.RecordRuntimeRejected(command, reason);
            }

            if (command.Owner != _studentControlledPlayer)
            {
                int baselineFlat = ToFlatIndex(command.UnitPosition);
                _lastBaselineRejectedByActor[baselineFlat] = new RuntimeRejectionInfo(NormalizeReason(reason), command);
                _baselineRejectedCount++;
                _baselineLastCommandSummary = BuildCommandSummary(command, accepted: false, NormalizeReason(reason));
                return;
            }

            _runtimeRejectedStudentCommands++;
            _ignoredStudentCommands = _runtimeRejectedStudentCommands;
            _lastStepApplyCommandCalled = true;

            string normalizedReason = NormalizeReason(reason);
            RecordCommandTelemetry(command, accepted: false, reason: normalizedReason, rawReason: reason, diagnostics: diagnostics);
            if (_enableJsonTrace)
            {
                RecordStage6R5CTerminalEvent(command, accepted: false, normalizedReason: normalizedReason, rawReason: reason, diagnostics: diagnostics);
            }
            IncrementStringCount(_runtimeRejectionReasons, normalizedReason);
        }

        private void HandleHeuristicActionEvaluated(HeuristicActionEvaluation evaluation)
        {
            if (!_sessionActive)
            {
                return;
            }

            Stage6B3PerformanceCounters.Increment(Stage6B3PerfMetric.HeuristicDecision);

            if (_enableJsonTrace)
            {
                _diagnosticsCollector?.RecordHeuristicActionEvaluation(evaluation);
            }

            int step = _matchManager != null ? _matchManager.Step : -1;
            if (_enableJsonTrace && step >= 0)
            {
                if (!_heuristicEvaluationsPerStep.TryGetValue(step, out int count))
                {
                    count = 0;
                }

                _heuristicEvaluationsPerStep[step] = count + 1;
            }

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

            // Track non-NoOp, accepted, rejected counts per step for soft-idle analysis
            if (_enableJsonTrace && step >= 0)
            {
                bool isNonNoOp = evaluation.ActionType != UnitActionType.NoOp;
                if (isNonNoOp)
                {
                    _heuristicNonNoOpPerStep.TryGetValue(step, out int nnCount);
                    _heuristicNonNoOpPerStep[step] = nnCount + 1;
                }
                if (evaluation.Accepted)
                {
                    _heuristicAcceptedPerStep.TryGetValue(step, out int accCount);
                    _heuristicAcceptedPerStep[step] = accCount + 1;
                }
                else if (!string.IsNullOrEmpty(evaluation.RejectionReason))
                {
                    _heuristicRejectedPerStep.TryGetValue(step, out int rejCount);
                    _heuristicRejectedPerStep[step] = rejCount + 1;
                }
            }
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
                    FinalizeStage6R5CCaptureEnd();
                    WriteStage6R5CTelemetryArtifacts();
                    WriteCompactDiagnosticsReport();
                    _terminalReportWritten = true;
                }

                // Flush soft-idle diagnostics when episode ends in continuous mode
                // (StopAutoPlayback is not called in continuous mode)
                if (!_manualStepMode && !_autoPlaybackEnabledRuntime)
                {
                    WritePlayModeStopDiagnostics("episode_terminal_continuous_mode");
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

        private void OnApplicationQuit()
        {
            // Flush soft-idle diagnostics when user exits Play Mode in continuous mode
            if (_writePlayModeStopDiagnostics && !_playModeStopDiagnosticsWritten && _playModeStepTraceByStep.Count > 0)
            {
                WritePlayModeStopDiagnostics("application_quit_continuous_mode");
            }

            WritePerformanceSummary("application_quit");
        }

        private void WritePerformanceSummary(string note)
        {
            if (_performanceSummaryWritten || !Application.isPlaying || !Stage6B3PerformanceCounters.Enabled)
            {
                return;
            }

            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? string.Empty;
            if (string.IsNullOrWhiteSpace(projectRoot))
            {
                return;
            }

            string outputPath = Path.GetFullPath(Path.Combine(projectRoot, _performanceSummaryRelativePath));
            StudentBridgeRuntimeSnapshot runtime = _studentAdapter != null
                ? _studentAdapter.GetRuntimeSnapshot()
                : default;

            Stage6B3PerformanceCounters.WriteSummary(
                outputPath,
                GetCurrentStep(),
                GetCurrentStep() > 80,
                _studentAdapter != null && _studentAdapter.EnableLegalActionMaskForSelection,
                GetCheckpointPathLabel(),
                _acceptedStudentCommands,
                _invalidStudentCommands,
                runtime.DecisionRequestsSent,
                runtime.DecisionRequestsSucceeded,
                note);

            _performanceSummaryWritten = true;
        }

        private void WriteCompactDiagnosticsReport()
        {
            if (!_enableJsonTrace || _diagnosticsCollector == null || _episodeController == null)
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
                _enableOverlay = !_enableOverlay;
                _showOverlay = _enableOverlay;
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
                StopAutoPlayback("terminal_reached");
                return;
            }

            if (_autoPlaybackRemainingSteps <= 0)
            {
                StopAutoPlayback("step_budget_reached");
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
                StopAutoPlayback("step_stalled");
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

        private void StopAutoPlayback(string reason = "manual_or_disabled")
        {
            _autoPlaybackRunning = false;
            _autoPlaybackRemainingSteps = 0;

            int step = _matchManager != null ? _matchManager.Step : -1;
            Debug.LogWarning(
                "[Week6VisualInspectionRunner][AutoPlaybackStop] "
                + "reason=" + reason
                + ", step=" + step
                + ", frame=" + Time.frameCount
                + ", time=" + Time.time.ToString("F3", CultureInfo.InvariantCulture)
                + ", manualStepMode=" + _manualStepMode
                + ", autoStepInFixedUpdate=" + (_episodeController != null && _episodeController.AutoStepInFixedUpdate));

            WritePlayModeStopDiagnostics(reason);
        }

        private void RecordPlayModeStepTrace(int step, bool hasStudentReport, StudentPolicyExecutionReport report)
        {
            if (!_writePlayModeStopDiagnostics || _matchManager == null)
            {
                return;
            }

            MatchStateSnapshot state = _matchManager.GetMatchState();
            StudentBridgeRuntimeSnapshot runtime = _studentAdapter != null
                ? _studentAdapter.GetRuntimeSnapshot()
                : default;

            int studentAcceptedDelta = _acceptedStudentCommands - _lastStudentAcceptedForTrace;
            int studentRejectedDelta = _invalidStudentCommands - _lastStudentRejectedForTrace;
            int baselineAcceptedDelta = _baselineAcceptedCount - _lastBaselineAcceptedForTrace;
            int baselineRejectedDelta = _baselineRejectedCount - _lastBaselineRejectedForTrace;

            _lastStudentAcceptedForTrace = _acceptedStudentCommands;
            _lastStudentRejectedForTrace = _invalidStudentCommands;
            _lastBaselineAcceptedForTrace = _baselineAcceptedCount;
            _lastBaselineRejectedForTrace = _baselineRejectedCount;

            int heuristicEvaluations = _heuristicEvaluationsPerStep.TryGetValue(step, out int count) ? count : 0;
            int scriptedNonNoOp     = _heuristicNonNoOpPerStep.TryGetValue(step, out int nnc) ? nnc : 0;
            int scriptedAccepted    = _heuristicAcceptedPerStep.TryGetValue(step, out int acc) ? acc : 0;
            int scriptedRejected    = _heuristicRejectedPerStep.TryGetValue(step, out int rej) ? rej : 0;

            // Count student non-noop vs noop
            int studentNonNoop = 0;
            int studentNoop = 0;
            if (hasStudentReport && report.DecodedActions != null)
            {
                for (int i = 0; i < report.DecodedActions.Count; i++)
                {
                    if (report.DecodedActions[i].ActionType != UnitActionType.NoOp)
                        studentNonNoop++;
                    else
                        studentNoop++;
                }
            }

            // Count legal mask non-noop slots available for student
            int maskNonNoopAvailable = 0;
            foreach (KeyValuePair<int, StudentMaskAwareDiagnostics.ActorLegalMaskTelemetry> kvp in _latestLegalMaskByFlat)
            {
                bool[] actionTypeMask = kvp.Value.ActionTypeMask;
                if (actionTypeMask == null)
                {
                    continue;
                }

                bool hasAnyNonNoOpLegal = false;
                for (int actionType = 1; actionType < actionTypeMask.Length; actionType++)
                {
                    if (actionTypeMask[actionType])
                    {
                        hasAnyNonNoOpLegal = true;
                        break;
                    }
                }

                if (hasAnyNonNoOpLegal)
                {
                    maskNonNoopAvailable++;
                }
            }

            // Decision cap remaining
            int decisionCapRemaining = -1;
            if (_studentAdapter != null)
            {
                int maxCap = GetPrivateField(_studentAdapter, "_maxDecisionRequestsPerEpisode", -1);
                int sent   = runtime.DecisionRequestsSent;
                decisionCapRemaining = maxCap > 0 ? Mathf.Max(0, maxCap - sent) : -1;
            }

            // Scan unit registry for rich runtime state
            int p1Workers = 0, p2Workers = 0;
            int p1Carrying = 0, p2Carrying = 0;
            int p1ProdBusy = 0, p2ProdBusy = 0;
            if (_unitRegistry != null)
            {
                System.Collections.Generic.List<UnitRuntime> allUnits = _unitRegistry.GetAllUnits();
                for (int i = 0; i < allUnits.Count; i++)
                {
                    UnitRuntime u = allUnits[i];
                    if (u == null || !u.IsAlive) continue;

                    if (u.Type == UnitType.Worker)
                    {
                        if (u.Owner == Owner.Player1)
                        {
                            p1Workers++;
                            if (u.CarriedResources > 0) p1Carrying++;
                        }
                        else if (u.Owner == Owner.Player2)
                        {
                            p2Workers++;
                            if (u.CarriedResources > 0) p2Carrying++;
                        }
                    }
                    else if (u.IsBuilding)
                    {
                        BuildingRuntime building = u.GetComponent<BuildingRuntime>();
                        if (building != null)
                        {
                            ProductionQueue pq = building.GetProductionQueue();
                            if (pq != null && pq.IsProducing)
                            {
                                if (u.Owner == Owner.Player1) p1ProdBusy++;
                                else if (u.Owner == Owner.Player2) p2ProdBusy++;
                            }
                        }
                    }
                }
            }

            // Resource node state
            int activeNodes = _resourceManager != null ? _resourceManager.GetActiveResourceCount() : -1;
            int totalResources = _resourceManager != null ? _resourceManager.GetTotalAvailableResources() : -1;

            string terminalReason = _episodeController != null && _episodeController.LastTerminalReport.IsTerminal
                ? _episodeController.LastTerminalReport.TerminalReason.ToString()
                : state.EndReason.ToString();

            var trace = new Stage6B3PlayModeStepTrace
            {
                step = step,
                frame = Time.frameCount,
                unity_time = Time.time,
                match_phase = state.Phase.ToString(),
                terminal = (_episodeController != null && _episodeController.LastTerminalReport.IsTerminal) || state.Phase == MatchPhase.Ended,
                terminal_reason = terminalReason,
                episode_running = _episodeController != null && _episodeController.IsRunning,
                episode_auto_step = _episodeController != null && _episodeController.AutoStepInFixedUpdate,
                victory_winner = state.Winner.ToString(),
                victory_reason = state.EndReason.ToString(),
                runner_enabled = isActiveAndEnabled,
                adapter_enabled = _studentAdapter != null && _studentAdapter.isActiveAndEnabled,
                time_scale = Time.timeScale,

                policy_decision_requested = hasStudentReport || studentNonNoop > 0,
                student_selected_non_noop_count = studentNonNoop,
                student_selected_noop_count = studentNoop,
                student_mask_non_noop_available_count = maskNonNoopAvailable,
                student_commands_built = studentAcceptedDelta + studentRejectedDelta,
                student_commands_accepted = studentAcceptedDelta,
                student_commands_rejected = studentRejectedDelta,
                student_decision_cap_remaining = decisionCapRemaining,
                student_runtime_error = runtime.LastError ?? string.Empty,

                scripted_decision_requested = heuristicEvaluations > 0 || baselineAcceptedDelta > 0 || baselineRejectedDelta > 0,
                heuristic_action_evaluations = heuristicEvaluations,
                scripted_non_noop_count = scriptedNonNoOp,
                scripted_accepted_count = scriptedAccepted,
                scripted_rejected_count = scriptedRejected,

                // Backward compat
                student_accepted_delta = studentAcceptedDelta,
                student_rejected_delta = studentRejectedDelta,
                baseline_accepted_delta = baselineAcceptedDelta,
                baseline_rejected_delta = baselineRejectedDelta,

                player1_units_alive = state.Player1UnitCount,
                player2_units_alive = state.Player2UnitCount,
                player1_bases = state.Player1BaseCount,
                player2_bases = state.Player2BaseCount,
                player1_resources = state.Player1Resources,
                player2_resources = state.Player2Resources,
                player1_workers = p1Workers,
                player2_workers = p2Workers,
                player1_workers_carrying = p1Carrying,
                player2_workers_carrying = p2Carrying,
                player1_production_busy_count = p1ProdBusy,
                player2_production_busy_count = p2ProdBusy,
                active_resource_nodes = activeNodes,
                total_remaining_resources = totalResources,
                pending_commands = state.PendingCommands,
            };

            _playModeStepTraceByStep[step] = trace;
        }

        private void WritePlayModeStopDiagnostics(string reason)
        {
            if (!_writePlayModeStopDiagnostics || _playModeStopDiagnosticsWritten)
            {
                return;
            }

            string projectRoot = Directory.GetParent(Application.dataPath).FullName;

            // Soft-idle diagnostic output (primary)
            string softIdleDir = string.IsNullOrWhiteSpace(_softIdleDiagnosticsRelativeDir)
                ? null
                : Path.Combine(projectRoot, _softIdleDiagnosticsRelativeDir);

            // Legacy stop diagnostic output (backward compat)
            string legacyDir = string.IsNullOrWhiteSpace(_playModeStopDiagnosticsRelativeDir)
                ? null
                : Path.Combine(projectRoot, _playModeStopDiagnosticsRelativeDir);

            if (softIdleDir == null && legacyDir == null)
            {
                return;
            }

            var sortedSteps = new List<int>(_playModeStepTraceByStep.Keys);
            sortedSteps.Sort();

            // Compute stop boundaries
            int scriptedStopStep = -1;
            int studentStopStep = -1;
            bool seenScriptedActive = false;
            bool seenStudentActive = false;
            for (int i = 0; i < sortedSteps.Count; i++)
            {
                Stage6B3PlayModeStepTrace trace = _playModeStepTraceByStep[sortedSteps[i]];
                if (trace.scripted_decision_requested)
                {
                    seenScriptedActive = true;
                }
                else if (seenScriptedActive && scriptedStopStep < 0)
                {
                    scriptedStopStep = trace.step;
                }

                if (trace.policy_decision_requested)
                {
                    seenStudentActive = true;
                }
                else if (seenStudentActive && studentStopStep < 0)
                {
                    studentStopStep = trace.step;
                }
            }

            int maxObservedStep = sortedSteps.Count > 0 ? sortedSteps[sortedSteps.Count - 1] : -1;
            int studentNonNoOpTotal = 0;
            int studentNoOpTotal = 0;
            int studentAcceptedTotal = 0;
            int studentRejectedTotal = 0;
            int scriptedNonNoOpTotal = 0;
            int scriptedAcceptedTotal = 0;
            int scriptedRejectedTotal = 0;
            for (int i = 0; i < sortedSteps.Count; i++)
            {
                Stage6B3PlayModeStepTrace trace = _playModeStepTraceByStep[sortedSteps[i]];
                studentNonNoOpTotal += trace.student_selected_non_noop_count;
                studentNoOpTotal += trace.student_selected_noop_count;
                studentAcceptedTotal += trace.student_commands_accepted;
                studentRejectedTotal += trace.student_commands_rejected;
                scriptedNonNoOpTotal += trace.scripted_non_noop_count;
                scriptedAcceptedTotal += trace.scripted_accepted_count;
                scriptedRejectedTotal += trace.scripted_rejected_count;
            }

            Stage6B3PlayModeStepTrace stopTrace = default;
            bool hasStopTrace = _matchManager != null
                && _playModeStepTraceByStep.TryGetValue(_matchManager.Step, out stopTrace);

            MatchStateSnapshot state = _matchManager != null ? _matchManager.GetMatchState() : default;
            var summary = new Stage6B3PlayModeStopSummary
            {
                generated_at_utc = DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture),
                scene = SceneManager.GetActiveScene().path,
                stop_reason = reason ?? "unknown",
                stop_step = _matchManager != null ? _matchManager.Step : -1,
                stop_frame = Time.frameCount,
                stop_unity_time = Time.time,
                auto_playback_enabled = _autoPlaybackEnabledRuntime,
                auto_playback_running = _autoPlaybackRunning,
                auto_playback_max_steps = _autoVisualPlaybackMaxSteps,
                auto_playback_remaining_steps = _autoPlaybackRemainingSteps,
                scripted_first_stop_step = scriptedStopStep,
                student_first_stop_step = studentStopStep,
                matchmanager_still_advancing = state.Phase == MatchPhase.Running,
                match_phase = state.Phase.ToString(),
                episode_running = _episodeController != null && _episodeController.IsRunning,
                episode_auto_step = _episodeController != null && _episodeController.AutoStepInFixedUpdate,
                trace_row_count = sortedSteps.Count,
                max_observed_step = maxObservedStep,
                step_80_boundary_cleared = maxObservedStep > 80,
                student_selected_non_noop_total = studentNonNoOpTotal,
                student_selected_noop_total = studentNoOpTotal,
                student_commands_accepted_total = studentAcceptedTotal,
                student_commands_rejected_total = studentRejectedTotal,
                scripted_non_noop_total = scriptedNonNoOpTotal,
                scripted_accepted_total = scriptedAcceptedTotal,
                scripted_rejected_total = scriptedRejectedTotal,
                student_mask_non_noop_available_at_stop = hasStopTrace ? stopTrace.student_mask_non_noop_available_count : -1,
                student_decision_cap_remaining_at_stop = hasStopTrace ? stopTrace.student_decision_cap_remaining : -1,
                player1_workers_at_stop = hasStopTrace ? stopTrace.player1_workers : -1,
                player2_workers_at_stop = hasStopTrace ? stopTrace.player2_workers : -1,
                player1_workers_carrying_at_stop = hasStopTrace ? stopTrace.player1_workers_carrying : -1,
                player2_workers_carrying_at_stop = hasStopTrace ? stopTrace.player2_workers_carrying : -1,
                player1_production_busy_count_at_stop = hasStopTrace ? stopTrace.player1_production_busy_count : -1,
                player2_production_busy_count_at_stop = hasStopTrace ? stopTrace.player2_production_busy_count : -1,
                player1_bases_at_stop = hasStopTrace ? stopTrace.player1_bases : -1,
                player2_bases_at_stop = hasStopTrace ? stopTrace.player2_bases : -1,
                active_resource_nodes_at_stop = hasStopTrace ? stopTrace.active_resource_nodes : -1,
                total_remaining_resources_at_stop = hasStopTrace ? stopTrace.total_remaining_resources : -1,
            };

            string summaryJson = JsonUtility.ToJson(summary, true);

            // Write soft-idle diagnostic artifacts (primary)
            if (softIdleDir != null)
            {
                Directory.CreateDirectory(softIdleDir);
                string softIdleTrace   = Path.Combine(softIdleDir, "stage6b3_static_soft_idle_trace.jsonl");
                string softIdleSummary = Path.Combine(softIdleDir, "stage6b3_static_soft_idle_summary.json");
                using (var writer = new StreamWriter(softIdleTrace, false, new UTF8Encoding(true)))
                {
                    for (int i = 0; i < sortedSteps.Count; i++)
                    {
                        writer.WriteLine(JsonUtility.ToJson(_playModeStepTraceByStep[sortedSteps[i]]));
                    }
                }
                File.WriteAllText(softIdleSummary, summaryJson, Encoding.UTF8);
                Debug.Log("[Week6VisualInspectionRunner] Soft-idle diagnostics written to: " + softIdleDir);
            }

            // Write legacy stop diagnostic artifacts (backward compat)
            if (legacyDir != null)
            {
                Directory.CreateDirectory(legacyDir);
                string legacyTrace   = Path.Combine(legacyDir, "stage6b3_static_playmode_stop_trace.jsonl");
                string legacySummary = Path.Combine(legacyDir, "stage6b3_static_playmode_stop_diagnostic.json");
                using (var writer = new StreamWriter(legacyTrace, false, new UTF8Encoding(true)))
                {
                    for (int i = 0; i < sortedSteps.Count; i++)
                    {
                        writer.WriteLine(JsonUtility.ToJson(_playModeStepTraceByStep[sortedSteps[i]]));
                    }
                }
                File.WriteAllText(legacySummary, summaryJson, Encoding.UTF8);
            }

            _playModeStopDiagnosticsWritten = true;
            string writtenTo = softIdleDir ?? legacyDir ?? "(none)";
            Debug.Log("[Week6VisualInspectionRunner] Playmode stop diagnostics written to: " + writtenTo);
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
            int currentStep = _matchManager != null ? _matchManager.Step : 0;
            PruneCommandTelemetry(currentStep);

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

                    CommandTelemetrySelection commandSelection = SelectCommandTelemetry(flat, currentStep, predicted.ToString(), move, predicted);
                    bool commandBuilt = commandSelection.HasAny;
                    bool actionApplierReached = commandBuilt;
                    bool applyCommandReached = commandBuilt;
                    string reason = ResolveCommandNotBuiltReason(flat, predicted, commandBuilt, commandSelection.Selected);
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

                    if (flat == FocusFlatWorker)
                    {
                        _b2TopAction = ResolveTopActionLabel(flat, actionType.ToString());
                    }

                    if (flat == FocusFlatBase)
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
                    unit_name = unit.name,
                    owner = unit.Owner.ToString(),
                    unit_type = unit.Type.ToString(),
                    hp = unit.HP,
                    carried_resources = unit.CarriedResources,
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
            AddFocusCellSnapshot(focus, FocusFlatWorker, FocusWorkerLabel);
            AddFocusCellSnapshot(focus, FocusFlatBase, FocusBaseLabel);
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
            lines.Add($"{FocusWorkerLabel} formula check: expected={b2Expected}, actual={FocusFlatWorker}, pass={b2Expected == FocusFlatWorker}");
            lines.Add($"{FocusBaseLabel} formula check: expected={c3Expected}, actual={FocusFlatBase}, pass={c3Expected == FocusFlatBase}");

            lines.Add(FocusWorkerLabel + " observation unit alignment: " + BuildFocusUnitAlignmentLine(FocusFlatWorker, "Worker"));
            lines.Add(FocusBaseLabel + " observation unit alignment: " + BuildFocusUnitAlignmentLine(FocusFlatBase, "Base"));

            lines.Add(FocusWorkerLabel + " predicted row alignment: pass=" + (_latestActorRowsByFlatIndex.ContainsKey(FocusFlatWorker)).ToString());
            lines.Add(FocusBaseLabel + " predicted row alignment: pass=" + (_latestActorRowsByFlatIndex.ContainsKey(FocusFlatBase)).ToString());

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
            _latestActorRowsByFlatIndex.TryGetValue(FocusFlatWorker, out b2);
            _latestActorRowsByFlatIndex.TryGetValue(FocusFlatBase, out c3);

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

            if (BuildFocusUnitAlignmentLine(FocusFlatWorker, "Worker").IndexOf("pass=True", StringComparison.Ordinal) < 0)
            {
                mismatch = true;
            }

            if (BuildFocusUnitAlignmentLine(FocusFlatBase, "Base").IndexOf("pass=True", StringComparison.Ordinal) < 0)
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

                if (_latestActorRowsByFlatIndex.TryGetValue(FocusFlatWorker, out ActorCellDiagnosticRow b2))
            {
                DrawWorldLabel(
                    b2.Unit,
                    $"{FocusWorkerLabel} Student predicted: {b2.PredictedActionType} | top3={b2.Top3ActionType} | margin={b2.NoopMargin.ToString("F3", CultureInfo.InvariantCulture)} | command_built={b2.CommandBuilt} | reason={b2.CommandNotBuiltReason}");
            }

                if (_latestActorRowsByFlatIndex.TryGetValue(FocusFlatBase, out ActorCellDiagnosticRow c3))
            {
                DrawWorldLabel(
                    c3.Unit,
                    $"{FocusBaseLabel} Student predicted: {c3.PredictedActionType} | top3={c3.Top3ActionType} | margin={c3.NoopMargin.ToString("F3", CultureInfo.InvariantCulture)} | command_built={c3.CommandBuilt} | reason={c3.CommandNotBuiltReason}");
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
                CommandTelemetrySelection selection = SelectCommandTelemetry(
                    flatIndex,
                    _matchManager != null ? _matchManager.Step : 0,
                    predictedActionType.ToString(),
                    0,
                    predictedActionType);

                if (selection.Selected != null && selection.Selected.RejectedSeen)
                {
                    return "runtime_rejected:" + selection.Selected.RejectReason;
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

            return "not_built_in_decoder_or_filter";
        }

        private string ResolveCommandNotBuiltReason(
            int flatIndex,
            UnitActionType predictedActionType,
            bool commandBuilt,
            CommandEventTelemetry selectedTelemetry)
        {
            if (commandBuilt && selectedTelemetry != null && selectedTelemetry.RejectedSeen)
            {
                return "runtime_rejected:" + selectedTelemetry.RejectReason;
            }

            return ResolveCommandNotBuiltReason(flatIndex, predictedActionType, commandBuilt);
        }

        private void RecordStage6R5CLifecycleForStep(int step, StudentPolicyExecutionReport report)
        {
            if (report.DecodedActions == null || report.DecodedActions.Count == 0)
            {
                return;
            }

            var perFlatActionSequence = new Dictionary<string, int>(StringComparer.Ordinal);

            for (int i = 0; i < report.DecodedActions.Count; i++)
            {
                AgentAction action = report.DecodedActions[i];
                if (action.ActionType == UnitActionType.NoOp)
                {
                    continue;
                }

                int flat = ToFlatIndex(action.ActorPosition);
                string actionType = action.ActionType.ToString();
                string seqKey = string.Format(CultureInfo.InvariantCulture, "{0}|{1}", flat, actionType);
                int sequence = 1;
                if (perFlatActionSequence.TryGetValue(seqKey, out int previous))
                {
                    sequence = previous + 1;
                }

                perFlatActionSequence[seqKey] = sequence;
                string diagnosticId = string.Format(
                    CultureInfo.InvariantCulture,
                    "{0}:{1}:{2}:{3}",
                    step,
                    flat,
                    actionType,
                    sequence);

                if (_stage6r5cLifecycleById.ContainsKey(diagnosticId))
                {
                    continue;
                }

                MatchCommand command = CreateMatchCommandFromAgentAction(_studentControlledPlayer, action);
                string eventKey = BuildCommandTelemetryKey(step, command);

                var row = new Stage6R5CCommandLifecycleRow
                {
                    diagnostic_command_id = diagnosticId,
                    command_id = 0L,
                    step = step,
                    actor_flat_index = flat,
                    actor_label = ToCellLabel(action.ActorPosition),
                    unit_id = "NOT_EXPOSED",
                    unit_type = ResolveUnitTypeLabelAt(action.ActorPosition),
                    owner = _studentControlledPlayer.ToString(),
                    action_type = actionType,
                    move_dir = action.ActionType == UnitActionType.Move ? (int)action.Direction : 0,
                    harvest_dir = action.ActionType == UnitActionType.Harvest ? (int)action.Direction : 0,
                    return_dir = action.ActionType == UnitActionType.Return ? (int)action.Direction : 0,
                    produce_dir = action.ActionType == UnitActionType.Produce ? (int)action.Direction : 0,
                    produce_unit_type = action.ActionType == UnitActionType.Produce ? (int)action.ProduceUnitType : 0,
                    attack_target_local = action.ActionType == UnitActionType.Attack ? AttackTargetToLocal(action.ActorPosition, action.AttackTargetPosition) : 24,
                    decoder_result = "command_built",
                    applier_result = "submitted_to_applier",
                    match_manager_result = "pending",
                    final_lifecycle_status = "submitted_to_match_manager",
                    decoded_candidate = true,
                    built = true,
                    submitted_to_applier = true,
                    rejected_by_decoder = false,
                    rejected_by_applier = false,
                    accepted_by_applier = false,
                    submitted_to_match_manager = true,
                    applied_by_match_manager = false,
                    rejected_by_match_manager = false,
                    expired_or_unresolved_at_capture_end = false,
                    reject_reason = string.Empty,
                    reject_reason_raw = string.Empty,
                    command_event_key = eventKey,
                    last_event_sequence = 0,
                    last_event_source = "student_decoded",
                    finalized = false,
                };

                _stage6r5cLifecycleRows.Add(row);
                _stage6r5cLifecycleById[diagnosticId] = row;

                if (!_stage6r5cPendingByEventKey.TryGetValue(eventKey, out Queue<string> queue))
                {
                    queue = new Queue<string>();
                    _stage6r5cPendingByEventKey[eventKey] = queue;
                }

                queue.Enqueue(diagnosticId);
            }
        }

        private void RecordStage6R5CTerminalEvent(
            MatchCommand command,
            bool accepted,
            string normalizedReason,
            string rawReason,
            MatchCommandRejectionDiagnostics diagnostics)
        {
            int step = _matchManager != null ? _matchManager.Step : 0;
            string eventKey = BuildCommandTelemetryKey(step, command);

            Stage6R5CCommandLifecycleRow row = null;
            string diagnosticId = string.Empty;
            if (_stage6r5cPendingByEventKey.TryGetValue(eventKey, out Queue<string> queue) && queue.Count > 0)
            {
                diagnosticId = queue.Dequeue();
                _stage6r5cLifecycleById.TryGetValue(diagnosticId, out row);
            }

            if (row == null)
            {
                string orphanId = string.Format(CultureInfo.InvariantCulture, "{0}:{1}:{2}:{3}", step, ToFlatIndex(command.UnitPosition), command.ActionType, "orphan");
                row = new Stage6R5CCommandLifecycleRow
                {
                    diagnostic_command_id = orphanId,
                    command_id = 0L,
                    step = step,
                    actor_flat_index = ToFlatIndex(command.UnitPosition),
                    actor_label = ToCellLabel(command.UnitPosition),
                    unit_id = "NOT_EXPOSED",
                    unit_type = "NOT_EXPOSED",
                    owner = command.Owner.ToString(),
                    action_type = command.ActionType.ToString(),
                    move_dir = command.ActionType == UnitActionType.Move ? (int)command.Direction : 0,
                    harvest_dir = command.ActionType == UnitActionType.Harvest ? (int)command.Direction : 0,
                    return_dir = command.ActionType == UnitActionType.Return ? (int)command.Direction : 0,
                    produce_dir = command.ActionType == UnitActionType.Produce ? (int)command.Direction : 0,
                    produce_unit_type = command.ActionType == UnitActionType.Produce ? (int)command.ProduceUnitType : 0,
                    attack_target_local = command.ActionType == UnitActionType.Attack ? AttackTargetToLocal(command.UnitPosition, command.AttackTarget) : 24,
                    decoder_result = "unknown",
                    applier_result = "unknown",
                    match_manager_result = "pending",
                    final_lifecycle_status = "submitted_to_match_manager",
                    decoded_candidate = false,
                    built = true,
                    submitted_to_applier = true,
                    rejected_by_decoder = false,
                    rejected_by_applier = false,
                    accepted_by_applier = false,
                    submitted_to_match_manager = true,
                    applied_by_match_manager = false,
                    rejected_by_match_manager = false,
                    expired_or_unresolved_at_capture_end = false,
                    reject_reason = string.Empty,
                    reject_reason_raw = string.Empty,
                    command_event_key = eventKey,
                    last_event_sequence = 0,
                    last_event_source = "orphan_event",
                    finalized = false,
                };
                _stage6r5cLifecycleRows.Add(row);
                _stage6r5cLifecycleById[orphanId] = row;
                diagnosticId = orphanId;
            }

            if (_commandTelemetryByKey.TryGetValue(eventKey, out CommandEventTelemetry telemetry))
            {
                row.command_id = telemetry.CommandId;
                row.last_event_sequence = telemetry.LastEventSequence;
                row.last_event_source = telemetry.LastEventSource ?? string.Empty;
            }

            if (accepted)
            {
                row.accepted_by_applier = true;
                row.applier_result = "accepted_by_applier";
                row.match_manager_result = "submitted_to_match_manager";
                row.final_lifecycle_status = "submitted_to_match_manager";
            }
            else
            {
                row.rejected_by_match_manager = true;
                row.applier_result = "accepted_by_applier";
                row.match_manager_result = "rejected_by_match_manager";
                row.final_lifecycle_status = "rejected_by_match_manager";
                row.reject_reason = string.IsNullOrWhiteSpace(normalizedReason) ? NormalizeReason(rawReason) : normalizedReason;
                row.reject_reason_raw = string.IsNullOrWhiteSpace(rawReason) ? row.reject_reason : rawReason;
                row.finalized = true;
            }

            _stage6r5cTerminalEvents.Add(new Stage6R5CCommandTerminalEventRow
            {
                diagnostic_command_id = diagnosticId,
                command_id = row.command_id,
                step = step,
                actor_flat_index = row.actor_flat_index,
                actor_label = row.actor_label,
                owner = row.owner,
                action_type = row.action_type,
                event_type = accepted ? "accepted_by_applier" : "rejected_by_match_manager",
                terminal_bucket = accepted ? "pending_terminal_resolution" : "rejected_by_match_manager",
                reason = accepted ? string.Empty : row.reject_reason,
                source = accepted ? "matchmanager.accepted" : "matchmanager.rejected",
                command_event_key = eventKey,
                event_sequence = row.last_event_sequence,
            });
        }

        private void FinalizeStage6R5CCompletedSteps(int currentStep)
        {
            for (int i = 0; i < _stage6r5cLifecycleRows.Count; i++)
            {
                Stage6R5CCommandLifecycleRow row = _stage6r5cLifecycleRows[i];
                if (row.finalized || row.step >= currentStep)
                {
                    continue;
                }

                if (row.rejected_by_match_manager)
                {
                    row.finalized = true;
                    continue;
                }

                if (row.accepted_by_applier)
                {
                    row.applied_by_match_manager = true;
                    row.match_manager_result = "applied_by_match_manager";
                    row.final_lifecycle_status = "applied_by_match_manager";
                    row.finalized = true;

                    _stage6r5cTerminalEvents.Add(new Stage6R5CCommandTerminalEventRow
                    {
                        diagnostic_command_id = row.diagnostic_command_id,
                        command_id = row.command_id,
                        step = row.step,
                        actor_flat_index = row.actor_flat_index,
                        actor_label = row.actor_label,
                        owner = row.owner,
                        action_type = row.action_type,
                        event_type = "applied_by_match_manager",
                        terminal_bucket = "applied_by_match_manager",
                        reason = string.Empty,
                        source = "matchmanager.step_finalization",
                        command_event_key = row.command_event_key,
                        event_sequence = row.last_event_sequence,
                    });
                }
            }
        }

        private void FinalizeStage6R5CCaptureEnd()
        {
            int currentStep = _matchManager != null ? _matchManager.Step : 0;
            FinalizeStage6R5CCompletedSteps(currentStep + 1);

            for (int i = 0; i < _stage6r5cLifecycleRows.Count; i++)
            {
                Stage6R5CCommandLifecycleRow row = _stage6r5cLifecycleRows[i];
                if (row.finalized)
                {
                    continue;
                }

                row.expired_or_unresolved_at_capture_end = true;
                row.match_manager_result = "expired_or_unresolved_at_capture_end";
                row.final_lifecycle_status = "expired_or_unresolved_at_capture_end";
                row.finalized = true;

                _stage6r5cTerminalEvents.Add(new Stage6R5CCommandTerminalEventRow
                {
                    diagnostic_command_id = row.diagnostic_command_id,
                    command_id = row.command_id,
                    step = row.step,
                    actor_flat_index = row.actor_flat_index,
                    actor_label = row.actor_label,
                    owner = row.owner,
                    action_type = row.action_type,
                    event_type = "expired_or_unresolved_at_capture_end",
                    terminal_bucket = "expired_or_unresolved_at_capture_end",
                    reason = string.IsNullOrWhiteSpace(row.reject_reason) ? "bounded_capture_end" : row.reject_reason,
                    source = "capture_end",
                    command_event_key = row.command_event_key,
                    event_sequence = row.last_event_sequence,
                });
            }
        }

        private void WriteStage6R5CTelemetryArtifacts()
        {
            string projectRoot = Directory.GetParent(Application.dataPath).FullName;
            string reportsDir = Path.Combine(projectRoot, _stepSnapshotOutputDirectoryRelativePath);
            Directory.CreateDirectory(reportsDir);

            string lifecyclePath = Path.Combine(reportsDir, "stage6r5c_command_lifecycle_trace.jsonl");
            string terminalPath = Path.Combine(reportsDir, "stage6r5c_command_terminal_events.jsonl");
            string scenePath = Path.Combine(reportsDir, "stage6r5c_scene_sanity_snapshot.json");
            string actorSummaryPath = Path.Combine(reportsDir, "stage6r5c_actor_cell_summary.json");

            _stage6r5cLifecycleRows.Sort((a, b) =>
            {
                int c = a.step.CompareTo(b.step);
                if (c != 0) return c;
                c = a.actor_flat_index.CompareTo(b.actor_flat_index);
                if (c != 0) return c;
                return string.CompareOrdinal(a.diagnostic_command_id, b.diagnostic_command_id);
            });

            using (var writer = new StreamWriter(lifecyclePath, false, new UTF8Encoding(true)))
            {
                for (int i = 0; i < _stage6r5cLifecycleRows.Count; i++)
                {
                    writer.WriteLine(JsonUtility.ToJson(_stage6r5cLifecycleRows[i]));
                }
            }

            using (var writer = new StreamWriter(terminalPath, false, new UTF8Encoding(true)))
            {
                for (int i = 0; i < _stage6r5cTerminalEvents.Count; i++)
                {
                    writer.WriteLine(JsonUtility.ToJson(_stage6r5cTerminalEvents[i]));
                }
            }

            var scene = new Stage6R5CSceneSanitySnapshot
            {
                generated_at_utc = DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture),
                scene = SceneManager.GetActiveScene().path,
                mode = "student_live_policy",
                steps_completed = _matchManager != null ? _matchManager.Step : 0,
                terminal_reason = _lastTerminalReason,
                checkpoint_path_used_at_inference = _latestInferenceDiagnostics != null
                    ? _latestInferenceDiagnostics.checkpoint_path_used_at_inference
                    : string.Empty,
                uses_heuristic_policy = ResolveUsesHeuristicPolicy(),
                fake_policy_or_stub_seen = ResolveInferenceSource().IndexOf("stub", StringComparison.OrdinalIgnoreCase) >= 0,
                fallback_used = ResolveUsesHeuristicPolicy(),
            };

            File.WriteAllText(scenePath, JsonUtility.ToJson(scene, true), Encoding.UTF8);

            var unitTypeCounts = new Dictionary<string, int>(StringComparer.Ordinal);
            int predictedNoOp = 0;
            int predictedNonNoOp = 0;
            int commandBuilt = 0;
            for (int i = 0; i < _latestActorRows.Count; i++)
            {
                ActorCellDiagnosticRow row = _latestActorRows[i];
                string unitType = row.Unit != null ? row.Unit.Type.ToString() : "Unknown";
                if (!unitTypeCounts.TryGetValue(unitType, out int count))
                {
                    count = 0;
                }

                unitTypeCounts[unitType] = count + 1;
                if (row.PredictedActionType == UnitActionType.NoOp)
                {
                    predictedNoOp++;
                }
                else
                {
                    predictedNonNoOp++;
                }

                if (row.CommandBuilt)
                {
                    commandBuilt++;
                }
            }

            var histLines = new List<string>();
            foreach (KeyValuePair<string, int> kvp in unitTypeCounts)
            {
                histLines.Add(kvp.Key + ":" + kvp.Value.ToString(CultureInfo.InvariantCulture));
            }
            histLines.Sort(StringComparer.Ordinal);

            var actorSummary = new Stage6R5CActorCellSummary
            {
                generated_at_utc = DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture),
                actor_cells_detected = _latestActorRows.Count,
                actor_cell_predicted_noop_count = predictedNoOp,
                actor_cell_predicted_non_noop_count = predictedNonNoOp,
                actor_cell_command_built_count = commandBuilt,
                actor_cell_command_not_built_count = Mathf.Max(0, _latestActorRows.Count - commandBuilt),
                unit_type_prediction_histogram = histLines.ToArray(),
            };

            File.WriteAllText(actorSummaryPath, JsonUtility.ToJson(actorSummary, true), Encoding.UTF8);
            Debug.Log("[Week6VisualInspectionRunner] Stage6R5C telemetry artifacts written to: " + reportsDir);
        }

        private static MatchCommand CreateMatchCommandFromAgentAction(Owner owner, AgentAction action)
        {
            return new MatchCommand(
            owner: owner,
                unitPosition: action.ActorPosition,
                actionType: action.ActionType,
                direction: action.Direction,
                produceUnitType: action.ProduceUnitType,
                attackTarget: action.AttackTargetPosition,
                hasAttackTarget: action.ActionType == UnitActionType.Attack);
        }

        private string ResolveUnitTypeLabelAt(GridPosition position)
        {
            if (_unitRegistry == null)
            {
                return "NOT_EXPOSED";
            }

            List<UnitRuntime> allUnits = _unitRegistry.GetAllUnits();
            for (int i = 0; i < allUnits.Count; i++)
            {
                UnitRuntime unit = allUnits[i];
                if (unit == null || !unit.IsAlive)
                {
                    continue;
                }

                if (unit.Owner == _studentControlledPlayer && unit.GridPos == position)
                {
                    return unit.Type.ToString();
                }
            }

            return "NOT_EXPOSED";
        }

        private static int AttackTargetToLocal(GridPosition source, GridPosition target)
        {
            int dx = Mathf.Clamp(target.X - source.X, -3, 3);
            int dy = Mathf.Clamp(target.Y - source.Y, -3, 3);
            return (dy + 3) * 7 + (dx + 3);
        }

        private void RecordCommandTelemetry(
            MatchCommand command,
            bool accepted,
            string reason,
            string rawReason = "",
            MatchCommandRejectionDiagnostics diagnostics = default)
        {
            int step = _matchManager != null ? _matchManager.Step : 0;
            int flat = ToFlatIndex(command.UnitPosition);
            string key = BuildCommandTelemetryKey(step, command);

            if (!_commandTelemetryByKey.TryGetValue(key, out CommandEventTelemetry telemetry))
            {
                long commandId = ++_commandTelemetryIdSequence;
                telemetry = new CommandEventTelemetry(commandId, step, flat, key, command);
                _commandTelemetryByKey[key] = telemetry;

                if (!_commandTelemetryByFlat.TryGetValue(flat, out List<CommandEventTelemetry> byFlat))
                {
                    byFlat = new List<CommandEventTelemetry>();
                    _commandTelemetryByFlat[flat] = byFlat;
                }

                byFlat.Add(telemetry);
            }

            int eventSequence = ++_commandTelemetryEventSequence;
            if (accepted)
            {
                telemetry.MarkAccepted(eventSequence);
            }
            else
            {
                string normalized = string.IsNullOrWhiteSpace(reason) ? NormalizeReason(rawReason) : reason;
                string raw = string.IsNullOrWhiteSpace(rawReason) ? reason : rawReason;
                telemetry.MarkRejected(normalized, raw, new DirectRuntimeRejectTrace(diagnostics), eventSequence);
            }
        }

        private static string BuildCommandTelemetryKey(int step, MatchCommand command)
        {
            int unitFlat = ToFlatIndex(command.UnitPosition);
            int attackFlat = command.HasAttackTarget ? ToFlatIndex(command.AttackTarget) : -1;
            return string.Format(
                CultureInfo.InvariantCulture,
                "{0}|{1}|{2}|{3}|{4}|{5}|{6}|{7}",
                step,
                command.Owner,
                unitFlat,
                command.ActionType,
                command.Direction,
                command.ProduceUnitType,
                attackFlat,
                command.HasAttackTarget ? 1 : 0);
        }

        private void PruneCommandTelemetry(int currentStep)
        {
            int minStepToKeep = Mathf.Max(0, currentStep - 2);
            var removeKeys = new List<string>();

            foreach (KeyValuePair<string, CommandEventTelemetry> kvp in _commandTelemetryByKey)
            {
                if (kvp.Value.Step < minStepToKeep)
                {
                    removeKeys.Add(kvp.Key);
                }
            }

            for (int i = 0; i < removeKeys.Count; i++)
            {
                _commandTelemetryByKey.Remove(removeKeys[i]);
            }

            var flatKeys = new List<int>(_commandTelemetryByFlat.Keys);
            for (int i = 0; i < flatKeys.Count; i++)
            {
                int flat = flatKeys[i];
                List<CommandEventTelemetry> items = _commandTelemetryByFlat[flat];
                items.RemoveAll(item => item.Step < minStepToKeep);
                if (items.Count == 0)
                {
                    _commandTelemetryByFlat.Remove(flat);
                }
            }
        }

        private CommandTelemetrySelection SelectCommandTelemetry(
            int flat,
            int currentStep,
            string maskedActionType,
            int maskedMoveDir,
            UnitActionType predictedActionType)
        {
            if (!_commandTelemetryByFlat.TryGetValue(flat, out List<CommandEventTelemetry> items) || items == null || items.Count == 0)
            {
                return default;
            }

            UnitActionType expectedActionType = ParseActionTypeOrFallback(maskedActionType, predictedActionType);
            int minStep = Mathf.Max(0, currentStep - 1);

            int candidateCount = 0;
            bool anyAcceptedSeen = false;
            bool anyRejectedSeen = false;
            bool differentCommandConflict = false;

            CommandEventTelemetry selected = null;
            CommandEventTelemetry acceptedRecord = null;
            CommandEventTelemetry rejectedRecord = null;
            int bestScore = int.MinValue;
            int bestSequence = int.MinValue;

            for (int i = 0; i < items.Count; i++)
            {
                CommandEventTelemetry item = items[i];
                if (item == null || item.Step < minStep || item.Step > currentStep)
                {
                    continue;
                }

                candidateCount++;

                if (item.AcceptedSeen)
                {
                    anyAcceptedSeen = true;
                    acceptedRecord = acceptedRecord ?? item;
                }

                if (item.RejectedSeen)
                {
                    anyRejectedSeen = true;
                    rejectedRecord = rejectedRecord ?? item;
                }

                int score = 0;
                if (item.Command.ActionType == expectedActionType)
                {
                    score += 8;
                    if (expectedActionType == UnitActionType.Move && (int)item.Command.Direction == maskedMoveDir)
                    {
                        score += 8;
                    }
                }

                if (item.Step == currentStep)
                {
                    score += 4;
                }
                else if (item.Step == currentStep - 1)
                {
                    score += 2;
                }

                int sequence = item.LastEventSequence;
                if (score > bestScore || (score == bestScore && sequence > bestSequence))
                {
                    bestScore = score;
                    bestSequence = sequence;
                    selected = item;
                }
            }

            if (acceptedRecord != null && rejectedRecord != null && acceptedRecord.CommandId != rejectedRecord.CommandId)
            {
                differentCommandConflict = true;
            }

            return new CommandTelemetrySelection(
                selected,
                candidateCount,
                anyAcceptedSeen,
                anyRejectedSeen,
                differentCommandConflict);
        }

        private static UnitActionType ParseActionTypeOrFallback(string actionTypeText, UnitActionType fallback)
        {
            if (string.IsNullOrWhiteSpace(actionTypeText))
            {
                return fallback;
            }

            if (Enum.TryParse(actionTypeText, ignoreCase: true, out UnitActionType parsed))
            {
                return parsed;
            }

            return fallback;
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

        // Mode-isolation telemetry helpers (Stage10D25)
        private bool IsHeuristicOnlyMode()
        {
            if (!_captureModeContextSet)
            {
                return false;
            }
            return _capturePlayer1Mode == Week6PlayerControlMode.HeuristicBaseline
                && _capturePlayer2Mode == Week6PlayerControlMode.HeuristicBaseline;
        }

        private bool ResolveAdapterInvoked()
        {
            if (IsHeuristicOnlyMode())
            {
                return false;
            }
            return _latestInferenceDiagnostics != null && _latestInferenceDiagnostics.adapter_invoked;
        }

        private string ResolvePolicySource()
        {
            if (!_captureModeContextSet)
            {
                return "unknown";
            }
            if (_capturePlayer1Mode == Week6PlayerControlMode.StudentInference)
            {
                return "student_checkpoint";
            }
            if (_capturePlayer1Mode == Week6PlayerControlMode.HeuristicBaseline)
            {
                return "heuristic_policy";
            }
            return _capturePlayer1Mode.ToString().ToLowerInvariant();
        }

        private string ResolveInferenceSource()
        {
            if (IsHeuristicOnlyMode())
            {
                return "heuristic_policy";
            }
            if (_captureModeContextSet && _capturePlayer1Mode == Week6PlayerControlMode.StudentInference)
            {
                return "python_adapter_bridge";
            }
            return "unknown";
        }

        private bool ResolveUsesStudentCheckpoint()
        {
            if (IsHeuristicOnlyMode())
            {
                return false;
            }
            return _captureModeContextSet && _capturePlayer1Mode == Week6PlayerControlMode.StudentInference;
        }

        private bool ResolveUsesPythonAdapter()
        {
            return ResolveUsesStudentCheckpoint();
        }

        private bool ResolveUsesHeuristicPolicy()
        {
            return _captureModeContextSet && _capturePlayer1Mode == Week6PlayerControlMode.HeuristicBaseline;
        }

        private string ResolveActionBufferSource()
        {
            if (IsHeuristicOnlyMode())
            {
                return "heuristic_policy_adapter";
            }
            if (_captureModeContextSet && _capturePlayer1Mode == Week6PlayerControlMode.StudentInference)
            {
                return "student_week6_python_bridge";
            }
            return "unknown";
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
