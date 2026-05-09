using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RTS.ML
{
    /// <summary>
    /// Stage6B4 diagnostic probe for Barracks advanced production.
    ///
    /// This probe is intentionally observational/forced-test only:
    /// - it does not change checkpoints;
    /// - it does not train the student;
    /// - it does not add heuristic overrides;
    /// - it does not hard-code live production behavior.
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class Stage6B4_BarracksAdvancedProductionProbe : MonoBehaviour
    {
        private const string Tag = "[Stage6B4]";
        private const string DefaultOutputDir = "python/week6_student/reports/stage6b4_barracks_advanced_production_probe";

        [Header("Execution")]
        [SerializeField] private bool _runForcedProbeOnStart = false;
        [SerializeField] private bool _enableLiveStudentInstrumentation = true;
        [SerializeField] private bool _writeReportOnDestroy = true;
        [SerializeField] private int _forcedProductionTimeoutSteps = 64;
        [SerializeField] private Owner _studentOwner = Owner.Player1;

        [Header("Output")]
        [SerializeField] private string _outputDirectoryRelativePath = DefaultOutputDir;
        [SerializeField] private string _jsonFileName = "stage6b4_barracks_advanced_production_probe.json";
        [SerializeField] private string _markdownFileName = "STAGE6B4_BARRACKS_ADVANCED_PRODUCTION_PROBE.md";

        private GridManager _gridManager;
        private UnitRegistry _unitRegistry;
        private MatchManager _matchManager;
        private MatchBootstrap _matchBootstrap;
        private ResourceManager _resourceManager;
        private EpisodeController _episodeController;
        private Week6StudentPolicyAdapter _studentAdapter;
        private ActionDecoder _decoder;
        private ActionApplier _applier;

        private readonly List<ProductionCaseResult> _runtimeOnlyResults = new List<ProductionCaseResult>();
        private readonly List<ProductionCaseResult> _forcedMlResults = new List<ProductionCaseResult>();
        private MaskProbeResult _maskProbe;
        private readonly List<LiveStepRecord> _liveStepRecords = new List<LiveStepRecord>();
        private readonly List<CommandEventRecord> _commandEvents = new List<CommandEventRecord>();
        private readonly List<ProductionEventRecord> _productionEvents = new List<ProductionEventRecord>();
        private readonly Dictionary<int, QueueSnapshot> _lastQueueByBarracksFlat = new Dictionary<int, QueueSnapshot>();
        private readonly Dictionary<UnitType, int> _lastUnitCounts = new Dictionary<UnitType, int>();

        private bool _forcedProbeCompleted;
        private bool _reportWritten;
        private int _lastLiveStep = -1;
        private int _liveCommandEventStartIndex;
        private int _liveProductionEventStartIndex;

        private void OnEnable()
        {
            ResolveReferences();
            SubscribeMatchEvents();
        }

        private void Start()
        {
            ResolveReferences();
            InitializeUnitCountSnapshot();

            if (_runForcedProbeOnStart)
            {
                StartCoroutine(RunForcedProbeNextFrame());
            }
        }

        private void Update()
        {
            if (!_enableLiveStudentInstrumentation)
            {
                return;
            }

            ResolveReferences();
            CaptureLiveStudentStepIfNeeded();
            PollProductionTransitions();
        }

        private void OnDisable()
        {
            UnsubscribeMatchEvents();
            if (_writeReportOnDestroy)
            {
                WriteReport("component_disabled");
            }
        }

        private void OnDestroy()
        {
            UnsubscribeMatchEvents();
            if (_writeReportOnDestroy)
            {
                WriteReport("component_destroyed");
            }
        }

        [ContextMenu("Run Stage6B4 Forced Barracks Probe")]
        public void RunForcedProbeFromContextMenu()
        {
            ResolveReferences();
            StartCoroutine(RunForcedProbeNextFrame());
        }

        [ContextMenu("Write Stage6B4 Report")]
        public void WriteReportFromContextMenu()
        {
            ResolveReferences();
            WriteReport("context_menu");
        }

        private IEnumerator RunForcedProbeNextFrame()
        {
            yield return null;
            RunForcedProbeNow();
        }

        private void RunForcedProbeNow()
        {
            ResolveReferences();
            _runtimeOnlyResults.Clear();
            _forcedMlResults.Clear();
            _maskProbe = null;

            Debug.Log(Tag + " Starting forced Barracks production probe.");

            foreach (int produceIndex in new[] { 4, 5, 6 })
            {
                _runtimeOnlyResults.Add(RunRuntimeOnlyProductionCase(produceIndex));
            }

            _maskProbe = RunMaskOnlyProbe();

            foreach (int produceIndex in new[] { 4, 5, 6 })
            {
                _forcedMlResults.Add(RunForcedMlProductionCase(produceIndex));
            }

            RunControlledLiveStudentProbe(steps: 3);

            _forcedProbeCompleted = true;
            WriteReport("forced_probe_completed");
            Debug.Log(Tag + " Forced Barracks production probe completed.");
        }

        private ProductionCaseResult RunRuntimeOnlyProductionCase(int produceIndex)
        {
            string unitName = ProduceIndexName(produceIndex);
            var result = CreateCaseResult("runtime_only_match_command", produceIndex);

            if (!PrepareControlledBarracksState(unitName, out UnitRuntime barracks, out Direction direction, out string setupError))
            {
                result.setup_ok = false;
                result.rejection_reason = setupError;
                return result;
            }

            result.setup_ok = true;
            result.barracks_flat = barracks.GridPos.ToFlatIndex();
            result.produce_dir = (int)direction;
            result.resources_before = _matchManager.GetResources(barracks.Owner);
            result.free_adjacent_cardinal = CountFreeCardinalCells(barracks.GridPos);
            result.free_adjacent_8 = CountFreeEightNeighborCells(barracks.GridPos);

            var command = new MatchCommand(
                barracks.Owner,
                barracks.GridPos,
                UnitActionType.Produce,
                direction,
                (ProducibleUnit)RuntimeProduceEnumValue(produceIndex));

            int beforeUnits = CountUnitsByType(ProduceIndexToUnitType(produceIndex), barracks.Owner);
            BuildingRuntime building = barracks.GetComponent<BuildingRuntime>();
            ProductionQueue queueBefore = building != null ? building.GetProductionQueue() : null;
            result.queue_busy_before = queueBefore != null && queueBefore.IsProducing;

            result.matchmanager_apply_command_returned = _matchManager.ApplyCommand(command);
            result.matchmanager_accepted = result.matchmanager_apply_command_returned;

            if (!result.matchmanager_apply_command_returned)
            {
                result.rejection_reason = "MatchManager.ApplyCommand returned false.";
                return result;
            }

            bool stepped = _matchManager.StepMatch();
            result.step_match_called = stepped;

            ProductionQueue queueAfterStart = building != null ? building.GetProductionQueue() : null;
            result.queue_started = queueAfterStart != null
                && queueAfterStart.IsProducing
                && queueAfterStart.CurrentProducingType == ProduceIndexToUnitType(produceIndex);
            result.queue_type_after_start = queueAfterStart != null && queueAfterStart.CurrentProducingType.HasValue
                ? queueAfterStart.CurrentProducingType.Value.ToString()
                : "none";

            CompleteProductionLoop(result, building, ProduceIndexToUnitType(produceIndex), barracks.Owner, beforeUnits);
            return result;
        }

        private ProductionCaseResult RunForcedMlProductionCase(int produceIndex)
        {
            string unitName = ProduceIndexName(produceIndex);
            var result = CreateCaseResult("forced_ml_pipeline_action_flat", produceIndex);

            if (!PrepareControlledBarracksState(unitName, out UnitRuntime barracks, out Direction direction, out string setupError))
            {
                result.setup_ok = false;
                result.rejection_reason = setupError;
                return result;
            }

            result.setup_ok = true;
            result.barracks_flat = barracks.GridPos.ToFlatIndex();
            result.produce_dir = (int)direction;
            result.resources_before = _matchManager.GetResources(barracks.Owner);
            result.free_adjacent_cardinal = CountFreeCardinalCells(barracks.GridPos);
            result.free_adjacent_8 = CountFreeEightNeighborCells(barracks.GridPos);

            int[] actionFlat = BuildForcedProduceActionFlat(barracks.GridPos.ToFlatIndex(), direction, produceIndex);
            result.fake_action_flat_size = actionFlat.Length;
            result.fake_action_type_value = actionFlat[barracks.GridPos.ToFlatIndex() * ActionContract.ActionFlatSize + ActionContract.BranchOffset(ActionContract.BRANCH_ACTION_TYPE)];
            result.fake_produce_unit_type_value = actionFlat[barracks.GridPos.ToFlatIndex() * ActionContract.ActionFlatSize + ActionContract.BranchOffset(ActionContract.BRANCH_PRODUCE_UNIT_TYPE)];

            ActionMaskSet mask = BuildMask();
            ActorActionMask barracksMask = mask?.GetActorMask(barracks.GridPos);
            result.mask_produce_enabled = barracksMask != null && barracksMask.IsActionTypeEnabled(UnitActionType.Produce);
            result.mask_produce_unit_type_enabled = barracksMask != null
                && produceIndex >= 0
                && produceIndex < barracksMask.ProduceUnitTypeMask.Length
                && barracksMask.ProduceUnitTypeMask[produceIndex];

            List<int> eligible = new List<int> { barracks.GridPos.ToFlatIndex() };
            List<AgentAction> decoded = _decoder.DecodeTransferCompatibleBatchMaskAware(
                actionFlat,
                barracks.Owner,
                eligible,
                mask,
                out int maskedOutChoices,
                out int fallbackToNoop,
                out Dictionary<UnitActionType, int> preMaskHistogram,
                out Dictionary<UnitActionType, int> postMaskHistogram,
                out Dictionary<int, ActionDecoder.MaskAwareCellTelemetry> cellTelemetryByFlat);

            result.decoded_action_count = decoded.Count;
            result.masked_out_choices = maskedOutChoices;
            result.fallback_to_noop = fallbackToNoop;
            if (cellTelemetryByFlat.TryGetValue(barracks.GridPos.ToFlatIndex(), out ActionDecoder.MaskAwareCellTelemetry telemetry))
            {
                result.raw_action_type_top1 = telemetry.RawActionTypeTop1.ToString();
                result.raw_produce_unit_type_top1 = telemetry.RawProduceUnitTypeTop1;
                result.postmask_action_type = telemetry.MaskedActionType.ToString();
                result.postmask_produce_unit_type = telemetry.MaskedProduceUnitType;
                result.fallback_reason = telemetry.BranchParameterMaskReason;
            }

            int beforeUnits = CountUnitsByType(ProduceIndexToUnitType(produceIndex), barracks.Owner);
            BuildingRuntime building = barracks.GetComponent<BuildingRuntime>();
            ProductionQueue queueBefore = building != null ? building.GetProductionQueue() : null;
            result.queue_busy_before = queueBefore != null && queueBefore.IsProducing;

            int accepted = _applier.ApplyActions(decoded, barracks.Owner, mask, "stage6b4-forced-ml-pipeline");
            result.action_applier_accepted = accepted > 0;
            result.action_applier_rejected = _applier.RejectedActionsLastStep > 0;
            result.rejection_reason = _applier.RejectionReasonsLastStep.Count > 0 ? _applier.RejectionReasonsLastStep[0] : string.Empty;

            bool stepped = _matchManager.StepMatch();
            result.step_match_called = stepped;
            result.matchmanager_accepted = _matchManager.AcceptedCommandsLastStep > 0;
            result.matchmanager_rejected = _matchManager.InvalidCommandsLastStep > 0;

            ProductionQueue queueAfterStart = building != null ? building.GetProductionQueue() : null;
            result.queue_started = queueAfterStart != null
                && queueAfterStart.IsProducing
                && queueAfterStart.CurrentProducingType == ProduceIndexToUnitType(produceIndex);
            result.queue_type_after_start = queueAfterStart != null && queueAfterStart.CurrentProducingType.HasValue
                ? queueAfterStart.CurrentProducingType.Value.ToString()
                : "none";

            CompleteProductionLoop(result, building, ProduceIndexToUnitType(produceIndex), barracks.Owner, beforeUnits);
            return result;
        }

        private MaskProbeResult RunMaskOnlyProbe()
        {
            var result = new MaskProbeResult();
            result.probed = false;

            if (!PrepareControlledBarracksState("mask_probe", out UnitRuntime barracks, out _, out string setupError))
            {
                result.setup_error = setupError;
                return result;
            }

            ActionMaskSet mask = BuildMask();
            ActorActionMask actorMask = mask?.GetActorMask(barracks.GridPos);
            BuildingRuntime building = barracks.GetComponent<BuildingRuntime>();
            ProductionQueue queue = building != null ? building.GetProductionQueue() : null;

            result.probed = true;
            result.barracks_flat = barracks.GridPos.ToFlatIndex();
            result.resources = _matchManager.GetResources(barracks.Owner);
            result.queue_busy = queue != null && queue.IsProducing;
            result.free_adjacent_cardinal = CountFreeCardinalCells(barracks.GridPos);
            result.free_adjacent_8 = CountFreeEightNeighborCells(barracks.GridPos);
            result.action_type_produce_enabled = actorMask != null && actorMask.IsActionTypeEnabled(UnitActionType.Produce);
            result.produce_dir_enabled_indices = EnabledIndices(actorMask?.ProduceDirectionMask);
            result.produce_unit_type_enabled_indices = EnabledIndices(actorMask?.ProduceUnitTypeMask);
            result.produce_unit_type_enabled_names = EnabledProduceNames(actorMask?.ProduceUnitTypeMask);
            result.unit_definition_reasons = BuildUnitDefinitionReasons(barracks.Owner);

            Debug.Log(
                $"{Tag} Mask probe Barracks flat={result.barracks_flat}, Produce={result.action_type_produce_enabled}, " +
                $"produceDir=[{string.Join(",", result.produce_dir_enabled_indices)}], " +
                $"produceUnit=[{string.Join(",", result.produce_unit_type_enabled_names)}], " +
                $"resources={result.resources}, queueBusy={result.queue_busy}, free4={result.free_adjacent_cardinal}, free8={result.free_adjacent_8}");

            return result;
        }

        private void RunControlledLiveStudentProbe(int steps)
        {
            if (_episodeController == null || _studentAdapter == null)
            {
                Debug.LogWarning(Tag + " Controlled live student probe skipped: EpisodeController or Week6StudentPolicyAdapter missing.");
                return;
            }

            if (!PrepareControlledBarracksState("controlled_live_student", out UnitRuntime barracks, out _, out string setupError))
            {
                Debug.LogWarning(Tag + " Controlled live student probe skipped: " + setupError);
                return;
            }

            _episodeController.ConfigureWeek6PlayerControlModes(
                enableStudentMatchControl: true,
                player1Mode: _studentOwner == Owner.Player1 ? Week6PlayerControlMode.StudentInference : Week6PlayerControlMode.HeuristicBaseline,
                player2Mode: _studentOwner == Owner.Player2 ? Week6PlayerControlMode.StudentInference : Week6PlayerControlMode.HeuristicBaseline);

            _lastLiveStep = -1;
            _lastQueueByBarracksFlat.Clear();
            InitializeUnitCountSnapshot();
            PollProductionTransitions();
            _liveCommandEventStartIndex = _commandEvents.Count;
            _liveProductionEventStartIndex = _productionEvents.Count;
            int boundedSteps = Mathf.Clamp(steps, 1, 16);
            for (int i = 0; i < boundedSteps; i++)
            {
                if (_matchManager == null || _matchManager.Phase != MatchPhase.Running)
                {
                    break;
                }

                _episodeController.StepEpisodeOnce();
                CaptureLiveStudentStepIfNeeded();
                PollProductionTransitions();
            }

            Debug.Log(
                $"{Tag} Controlled live student probe completed for Barracks flat={barracks.GridPos.ToFlatIndex()}, " +
                $"capturedRows={_liveStepRecords.Count}");
        }

        private void CompleteProductionLoop(
            ProductionCaseResult result,
            BuildingRuntime building,
            UnitType producedType,
            Owner owner,
            int beforeUnits)
        {
            if (building == null)
            {
                result.rejection_reason = AppendReason(result.rejection_reason, "BuildingRuntime missing.");
                return;
            }

            for (int i = 0; i < Mathf.Max(1, _forcedProductionTimeoutSteps); i++)
            {
                int currentCount = CountUnitsByType(producedType, owner);
                if (currentCount > beforeUnits)
                {
                    result.production_completed = true;
                    result.unit_spawned = true;
                    result.spawned_count_delta = currentCount - beforeUnits;
                    result.steps_until_spawn = i;
                    break;
                }

                ProductionQueue queue = building.GetProductionQueue();
                if (queue == null || !queue.IsProducing)
                {
                    int after = CountUnitsByType(producedType, owner);
                    result.production_completed = true;
                    result.unit_spawned = after > beforeUnits;
                    result.spawned_count_delta = after - beforeUnits;
                    result.steps_until_spawn = i;
                    break;
                }

                _matchManager.StepMatch();
            }

            result.resources_after = _matchManager.GetResources(owner);
            if (!result.unit_spawned && string.IsNullOrWhiteSpace(result.rejection_reason))
            {
                result.rejection_reason = "Production did not spawn a unit before timeout.";
            }
        }

        private bool PrepareControlledBarracksState(string label, out UnitRuntime barracks, out Direction direction, out string error)
        {
            barracks = null;
            direction = Direction.North;
            error = string.Empty;

            ResolveReferences();
            if (_gridManager == null || _unitRegistry == null || _matchManager == null || _matchBootstrap == null)
            {
                error = "Missing GridManager/UnitRegistry/MatchManager/MatchBootstrap.";
                return false;
            }

            if (_episodeController != null)
            {
                _episodeController.ResetEpisode();
                ResolveReferences();
            }
            else if (_matchManager.Phase != MatchPhase.Running)
            {
                _matchManager.BeginMatch(0, GameConstants.MaxEpisodeSteps);
            }

            GridPosition position = FindFreePositionWithCardinalAndEightNeighbors();
            if (!position.IsInsideMap())
            {
                error = "No free 3x3 area found for controlled Barracks.";
                return false;
            }

            var factory = new UnitFactory(_matchBootstrap.GetConfig(), _gridManager, _gridManager.transform, _unitRegistry);
            barracks = factory.Spawn(UnitType.Barracks, Owner.Player1, position);
            if (barracks == null)
            {
                error = "UnitFactory failed to spawn controlled Barracks.";
                return false;
            }

            BuildingRuntime building = barracks.GetComponent<BuildingRuntime>();
            if (building == null)
            {
                building = barracks.gameObject.AddComponent<BuildingRuntime>();
            }

            building.ResetProduction();
            SubscribeProductionEventsForBarracks(barracks, building);

            int currentResources = _matchManager.GetResources(Owner.Player1);
            if (currentResources < 5000)
            {
                _matchManager.AddResources(Owner.Player1, 5000 - currentResources);
            }

            if (!TryFindFreeCardinalDirection(position, out direction))
            {
                error = "Controlled Barracks has no free cardinal produce_dir.";
                return false;
            }

            Debug.Log($"{Tag} Controlled Barracks for {label}: pos={position}, flat={position.ToFlatIndex()}, dir={direction}");
            return true;
        }

        private void CaptureLiveStudentStepIfNeeded()
        {
            if (_matchManager == null)
            {
                return;
            }

            int step = _matchManager.Step;
            if (step == _lastLiveStep)
            {
                return;
            }

            _lastLiveStep = step;
            List<UnitRuntime> barracksList = FindBarracks(_studentOwner);
            if (barracksList.Count == 0)
            {
                return;
            }

            StudentPolicyExecutionReport report = default;
            bool hasReport = _episodeController != null
                && _episodeController.TryGetWeek6StudentExecutionReport(_studentOwner, out report);

            string artifactJson = TryReadLatestAdapterJson(out string artifactPath) ? File.ReadAllText(artifactPath, Encoding.UTF8) : string.Empty;

            for (int i = 0; i < barracksList.Count; i++)
            {
                UnitRuntime barracks = barracksList[i];
                int flat = barracks.GridPos.ToFlatIndex();
                LiveStepRecord row = BuildLiveStepRecord(step, barracks, hasReport, report, artifactJson, artifactPath);
                _liveStepRecords.Add(row);
                Debug.Log(
                    $"{Tag}[Live] step={step}, flat={flat}, rawAction={row.raw_action_type_top1}, rawProduceType={row.raw_produce_unit_type_top1}, " +
                    $"postmask={row.postmask_action_type}/{row.postmask_produce_unit_type}, maskProduce={row.mask_produce_enabled}, " +
                    $"mask456={row.mask_unit_4_enabled}/{row.mask_unit_5_enabled}/{row.mask_unit_6_enabled}, " +
                    $"applier={row.action_applier_status}, match={row.matchmanager_status}, queue={row.queue_status}, spawned={row.spawned_unit_type}");
            }
        }

        private LiveStepRecord BuildLiveStepRecord(
            int step,
            UnitRuntime barracks,
            bool hasReport,
            StudentPolicyExecutionReport report,
            string adapterJson,
            string artifactPath)
        {
            int flat = barracks.GridPos.ToFlatIndex();
            var row = new LiveStepRecord
            {
                step = step,
                barracks_flat = flat,
                x = barracks.GridPos.X,
                y = barracks.GridPos.Y,
                artifact_path = artifactPath ?? string.Empty,
                has_student_report = hasReport,
                resources = _matchManager != null ? _matchManager.GetResources(barracks.Owner) : 0,
                free_adjacent_cardinal = CountFreeCardinalCells(barracks.GridPos),
                free_adjacent_8 = CountFreeEightNeighborCells(barracks.GridPos),
            };

            BuildingRuntime building = barracks.GetComponent<BuildingRuntime>();
            ProductionQueue queue = building != null ? building.GetProductionQueue() : null;
            row.queue_busy = queue != null && queue.IsProducing;
            row.queue_status = queue == null
                ? "missing"
                : (queue.IsProducing ? queue.CurrentProducingType.ToString() : "idle");

            ActionMaskSet mask = BuildMask();
            ActorActionMask actorMask = mask?.GetActorMask(barracks.GridPos);
            row.mask_produce_enabled = actorMask != null && actorMask.IsActionTypeEnabled(UnitActionType.Produce);
            row.mask_unit_4_enabled = IsEnabled(actorMask?.ProduceUnitTypeMask, 4);
            row.mask_unit_5_enabled = IsEnabled(actorMask?.ProduceUnitTypeMask, 5);
            row.mask_unit_6_enabled = IsEnabled(actorMask?.ProduceUnitTypeMask, 6);

            if (hasReport && report.MaskAwareDiagnostics.CellTelemetryByFlat.TryGetValue(flat, out ActionDecoder.MaskAwareCellTelemetry telemetry))
            {
                row.raw_action_type_top1 = telemetry.RawActionTypeTop1.ToString();
                row.raw_produce_unit_type_top1 = telemetry.RawProduceUnitTypeTop1;
                row.postmask_action_type = telemetry.MaskedActionType.ToString();
                row.postmask_produce_unit_type = telemetry.MaskedProduceUnitType;
                row.fallback_reason = FirstNonEmpty(telemetry.BranchParameterMaskReason, telemetry.MoveDirMaskFallbackReason);
            }
            else
            {
                row.raw_action_type_top1 = ReadActionFlatValue(adapterJson, flat, ActionContract.BRANCH_ACTION_TYPE, ActionContract.SIZE_ACTION_TYPE, out int rawAction)
                    ? ((UnitActionType)rawAction).ToString()
                    : "unavailable";
                row.raw_produce_unit_type_top1 = ReadActionFlatValue(adapterJson, flat, ActionContract.BRANCH_PRODUCE_UNIT_TYPE, ActionContract.SIZE_PRODUCE_UNIT_TYPE, out int rawProduce)
                    ? rawProduce
                    : -1;
                row.postmask_action_type = "unavailable";
                row.postmask_produce_unit_type = -1;
                row.fallback_reason = hasReport ? "no_barracks_cell_telemetry" : "no_student_report";
            }

            FillLogitsFromAdapterJson(adapterJson, flat, row);

            CommandEventRecord commandEvent = row.postmask_action_type == UnitActionType.Produce.ToString()
                ? FindLiveCommandEvent(step, flat)
                : null;
            if (commandEvent != null)
            {
                row.action_applier_status = commandEvent.action_applier_status;
                row.matchmanager_status = commandEvent.matchmanager_status;
                row.rejection_reason = commandEvent.reason;
                row.accepted_command_action = commandEvent.action_type;
                row.accepted_command_produce_unit_type = commandEvent.produce_unit_type;
            }
            else
            {
                row.action_applier_status = "not_observed";
                row.matchmanager_status = "not_observed";
                row.rejection_reason = string.Empty;
                row.accepted_command_action = "none";
                row.accepted_command_produce_unit_type = "none";
            }

            ProductionEventRecord productionEvent = FindLiveProductionEvent(step, flat);
            row.production_event = productionEvent != null ? productionEvent.event_type : "none";
            row.spawned_unit_type = productionEvent != null && productionEvent.event_type == "spawned"
                ? productionEvent.unit_type
                : "none";
            if (row.production_event == "none" &&
                row.queue_busy &&
                row.accepted_command_action == UnitActionType.Produce.ToString())
            {
                row.production_event = "queue_start";
            }

            return row;
        }

        private void FillLogitsFromAdapterJson(string json, int flat, LiveStepRecord row)
        {
            if (string.IsNullOrWhiteSpace(json))
            {
                row.logits_available = false;
                row.logits_unavailable_reason = "adapter_json_unavailable";
                return;
            }

            string cellObject = ExtractGlobalCellDiagnosticObject(json, flat);
            if (string.IsNullOrWhiteSpace(cellObject))
            {
                row.logits_available = false;
                row.logits_unavailable_reason = "global_cell_diagnostic_missing";
                return;
            }

            row.action_type_logits = ExtractFloatArray(cellObject, "action_type_logits");
            row.produce_unit_type_logits = ExtractFloatArray(cellObject, "produce_unit_type_logits");
            row.logits_available = row.action_type_logits.Length == ActionContract.SIZE_ACTION_TYPE;
            row.produce_unit_logits_available = row.produce_unit_type_logits.Length == ActionContract.SIZE_PRODUCE_UNIT_TYPE;
            row.logits_unavailable_reason = row.logits_available ? string.Empty : "action_type_logits_missing";

            row.produce_logit = GetOrNaN(row.action_type_logits, (int)UnitActionType.Produce);
            row.produce_rank = RankDescending(row.action_type_logits, (int)UnitActionType.Produce);
            row.light_logit = GetOrNaN(row.produce_unit_type_logits, 4);
            row.heavy_logit = GetOrNaN(row.produce_unit_type_logits, 5);
            row.ranged_logit = GetOrNaN(row.produce_unit_type_logits, 6);
            row.light_rank = RankDescending(row.produce_unit_type_logits, 4);
            row.heavy_rank = RankDescending(row.produce_unit_type_logits, 5);
            row.ranged_rank = RankDescending(row.produce_unit_type_logits, 6);
        }

        private int[] BuildForcedProduceActionFlat(int actorFlat, Direction direction, int produceIndex)
        {
            int[] actionFlat = new int[ActionContract.TotalActionFlatSize];
            int cellOffset = actorFlat * ActionContract.ActionFlatSize;
            actionFlat[cellOffset + ActionContract.BranchOffset(ActionContract.BRANCH_ACTION_TYPE)] = ActionContract.ACTION_PRODUCE;
            actionFlat[cellOffset + ActionContract.BranchOffset(ActionContract.BRANCH_PRODUCE_DIR)] = (int)direction;
            actionFlat[cellOffset + ActionContract.BranchOffset(ActionContract.BRANCH_PRODUCE_UNIT_TYPE)] = produceIndex;
            return actionFlat;
        }

        private ActionMaskSet BuildMask()
        {
            if (_matchManager == null || _gridManager == null || _unitRegistry == null)
            {
                return null;
            }

            var builder = new ActionMaskBuilder(_matchManager, _gridManager, _resourceManager, _unitRegistry, _matchBootstrap)
            {
                DiagnosticLogging = true
            };
            return builder.BuildTransferCompatibleMask(Owner.Player1);
        }

        private void PollProductionTransitions()
        {
            if (_unitRegistry == null)
            {
                return;
            }

            List<UnitRuntime> units = _unitRegistry.GetAllUnits();
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit == null || !unit.IsAlive || unit.Type != UnitType.Barracks)
                {
                    continue;
                }

                BuildingRuntime building = unit.GetComponent<BuildingRuntime>();
                if (building == null)
                {
                    continue;
                }

                SubscribeProductionEventsForBarracks(unit, building);

                int flat = unit.GridPos.ToFlatIndex();
                ProductionQueue queue = building.GetProductionQueue();
                QueueSnapshot current = QueueSnapshot.From(queue);
                _lastQueueByBarracksFlat.TryGetValue(flat, out QueueSnapshot previous);

                if (!previous.IsProducing && current.IsProducing)
                {
                    _productionEvents.Add(new ProductionEventRecord
                    {
                        step = _matchManager != null ? _matchManager.Step : -1,
                        barracks_flat = flat,
                        event_type = "queue_start",
                        unit_type = current.UnitType,
                    });
                }
                else if (previous.IsProducing && !current.IsProducing)
                {
                    _productionEvents.Add(new ProductionEventRecord
                    {
                        step = _matchManager != null ? _matchManager.Step : -1,
                        barracks_flat = flat,
                        event_type = "queue_complete",
                        unit_type = previous.UnitType,
                    });
                }

                _lastQueueByBarracksFlat[flat] = current;
            }

            foreach (UnitType type in new[] { UnitType.Light, UnitType.Heavy, UnitType.Ranged })
            {
                int current = CountUnitsByType(type, _studentOwner);
                _lastUnitCounts.TryGetValue(type, out int previous);
                if (current > previous)
                {
                    _productionEvents.Add(new ProductionEventRecord
                    {
                        step = _matchManager != null ? _matchManager.Step : -1,
                        barracks_flat = FindAnyBarracksFlat(_studentOwner),
                        event_type = "spawned",
                        unit_type = type.ToString(),
                        count_delta = current - previous,
                    });
                }

                _lastUnitCounts[type] = current;
            }
        }

        private void SubscribeProductionEventsForBarracks(UnitRuntime barracks, BuildingRuntime building)
        {
            if (barracks == null || building == null)
            {
                return;
            }

            building.OnUnitProduced -= HandleUnitProduced;
            building.OnUnitProduced += HandleUnitProduced;
        }

        private void HandleUnitProduced(UnitType unitType)
        {
            _productionEvents.Add(new ProductionEventRecord
            {
                step = _matchManager != null ? _matchManager.Step : -1,
                barracks_flat = FindAnyBarracksFlat(_studentOwner),
                event_type = "spawned",
                unit_type = unitType.ToString(),
                count_delta = 1,
            });
        }

        private void HandleCommandAccepted(MatchCommand command)
        {
            if (command.Owner != _studentOwner || command.ActionType != UnitActionType.Produce)
            {
                return;
            }

            _commandEvents.Add(new CommandEventRecord
            {
                step = _matchManager != null ? _matchManager.Step : -1,
                actor_flat = command.UnitPosition.ToFlatIndex(),
                action_type = command.ActionType.ToString(),
                produce_unit_type = command.ProduceUnitType.ToString(),
                action_applier_status = "accepted_or_submitted",
                matchmanager_status = "accepted",
                reason = string.Empty,
            });
        }

        private void HandleCommandRejected(MatchCommand command, string reason, MatchCommandRejectionDiagnostics diagnostics)
        {
            if (command.Owner != _studentOwner || command.ActionType != UnitActionType.Produce)
            {
                return;
            }

            _commandEvents.Add(new CommandEventRecord
            {
                step = _matchManager != null ? _matchManager.Step : -1,
                actor_flat = command.UnitPosition.ToFlatIndex(),
                action_type = command.ActionType.ToString(),
                produce_unit_type = command.ProduceUnitType.ToString(),
                action_applier_status = "submitted",
                matchmanager_status = "rejected",
                reason = reason ?? string.Empty,
            });
        }

        private void SubscribeMatchEvents()
        {
            if (_matchManager == null)
            {
                return;
            }

            _matchManager.OnCommandAccepted -= HandleCommandAccepted;
            _matchManager.OnCommandAccepted += HandleCommandAccepted;
            _matchManager.OnCommandRejectedDetailed -= HandleCommandRejected;
            _matchManager.OnCommandRejectedDetailed += HandleCommandRejected;
        }

        private void UnsubscribeMatchEvents()
        {
            if (_matchManager == null)
            {
                return;
            }

            _matchManager.OnCommandAccepted -= HandleCommandAccepted;
            _matchManager.OnCommandRejectedDetailed -= HandleCommandRejected;
        }

        private void WriteReport(string reason)
        {
            if (_reportWritten && reason != "context_menu")
            {
                return;
            }

            ResolveReferences();

            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            string outputDir = Path.GetFullPath(Path.Combine(projectRoot, _outputDirectoryRelativePath));
            Directory.CreateDirectory(outputDir);

            ProbeReport report = BuildReport(reason);
            string jsonPath = Path.Combine(outputDir, _jsonFileName);
            string mdPath = Path.Combine(outputDir, _markdownFileName);

            File.WriteAllText(jsonPath, JsonUtility.ToJson(report, true), Encoding.UTF8);
            File.WriteAllText(mdPath, BuildMarkdown(report, jsonPath), Encoding.UTF8);
            _reportWritten = true;

            Debug.Log($"{Tag} Report written: {jsonPath}");
        }

        private ProbeReport BuildReport(string reason)
        {
            HypothesisVerdict[] hypotheses = BuildHypothesisVerdicts();
            return new ProbeReport
            {
                generated_at_utc = DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture),
                scene = SceneManager.GetActiveScene().name,
                reason = reason,
                checkpoint_relative_path = _studentAdapter != null ? _studentAdapter.CheckpointRelativePath : string.Empty,
                forced_probe_completed = _forcedProbeCompleted,
                runtime_only_results = _runtimeOnlyResults.ToArray(),
                mask_probe = _maskProbe,
                forced_ml_pipeline_results = _forcedMlResults.ToArray(),
                live_student_steps = _liveStepRecords.ToArray(),
                command_events = _commandEvents.ToArray(),
                production_events = _productionEvents.ToArray(),
                hypotheses = hypotheses,
                loss_layer = DetermineLossLayer(hypotheses),
            };
        }

        private HypothesisVerdict[] BuildHypothesisVerdicts()
        {
            bool forcedRuntimeAllSpawned = AllSpawned(_runtimeOnlyResults);
            bool forcedMlAllSpawned = AllSpawned(_forcedMlResults);
            bool maskAllows456 = _maskProbe != null
                && _maskProbe.action_type_produce_enabled
                && Contains(_maskProbe.produce_unit_type_enabled_indices, 4)
                && Contains(_maskProbe.produce_unit_type_enabled_indices, 5)
                && Contains(_maskProbe.produce_unit_type_enabled_indices, 6);

            bool liveHasBarracksRows = _liveStepRecords.Count > 0;
            bool liveRawAdvanced = false;
            bool livePostmaskAdvanced = false;
            bool liveAcceptedAdvanced = false;
            bool liveSpawnedAdvanced = false;
            bool liveRejectedAdvanced = false;

            for (int i = 0; i < _liveStepRecords.Count; i++)
            {
                LiveStepRecord row = _liveStepRecords[i];
                if (row.raw_action_type_top1 == UnitActionType.Produce.ToString()
                    && (row.raw_produce_unit_type_top1 == 4 || row.raw_produce_unit_type_top1 == 5 || row.raw_produce_unit_type_top1 == 6))
                {
                    liveRawAdvanced = true;
                }

                if (row.postmask_action_type == UnitActionType.Produce.ToString()
                    && (row.postmask_produce_unit_type == 4 || row.postmask_produce_unit_type == 5 || row.postmask_produce_unit_type == 6))
                {
                    livePostmaskAdvanced = true;
                }

                if (row.matchmanager_status == "accepted"
                    && (row.accepted_command_produce_unit_type == "Light"
                        || row.accepted_command_produce_unit_type == "Heavy"
                        || row.accepted_command_produce_unit_type == "Ranged"))
                {
                    liveAcceptedAdvanced = true;
                }

                if (row.spawned_unit_type == "Light" || row.spawned_unit_type == "Heavy" || row.spawned_unit_type == "Ranged")
                {
                    liveSpawnedAdvanced = true;
                }

                if (row.matchmanager_status == "rejected")
                {
                    liveRejectedAdvanced = true;
                }
            }

            return new[]
            {
                new HypothesisVerdict
                {
                    id = "A",
                    hypothesis = "Unity Barracks production broken",
                    verdict = forcedRuntimeAllSpawned ? "NO-GO" : "GO",
                    evidence = forcedRuntimeAllSpawned
                        ? "Runtime-only MatchCommand path completed and spawned Light/Heavy/Ranged."
                        : "At least one runtime-only forced production case failed to spawn."
                },
                new HypothesisVerdict
                {
                    id = "B",
                    hypothesis = "mask blocks advanced production",
                    verdict = maskAllows456 ? "NO-GO" : "GO",
                    evidence = maskAllows456
                        ? "Mask enables Produce and produce_unit_type indices 4/5/6 for Barracks."
                        : "Mask does not expose Produce or one of indices 4/5/6 for Barracks."
                },
                new HypothesisVerdict
                {
                    id = "C",
                    hypothesis = "decoder/applier mapping broken",
                    verdict = forcedMlAllSpawned ? "NO-GO" : "GO",
                    evidence = forcedMlAllSpawned
                        ? "Fake actionFlat Produce with indices 4/5/6 decodes through mask-aware decoder, ActionApplier, MatchManager, and spawns units."
                        : "At least one forced ML-pipeline case failed."
                },
                new HypothesisVerdict
                {
                    id = "D",
                    hypothesis = "student never selects advanced production",
                    verdict = liveHasBarracksRows && !liveRawAdvanced ? "GO" : "INCONCLUSIVE",
                    evidence = liveHasBarracksRows
                        ? (liveRawAdvanced ? "Live rows contain raw advanced Produce intent." : "Live Barracks rows did not contain raw Produce with indices 4/5/6.")
                        : "No live Barracks student rows captured yet."
                },
                new HypothesisVerdict
                {
                    id = "E",
                    hypothesis = "student selects it but runtime rejects",
                    verdict = livePostmaskAdvanced && liveRejectedAdvanced ? "GO" : "INCONCLUSIVE",
                    evidence = livePostmaskAdvanced
                        ? (liveRejectedAdvanced ? "Postmask advanced Produce was observed with runtime rejection." : "Postmask advanced Produce was observed without rejection evidence.")
                        : "No postmask advanced Produce intent observed."
                },
                new HypothesisVerdict
                {
                    id = "F",
                    hypothesis = "production starts but spawn fails",
                    verdict = (forcedRuntimeAllSpawned && forcedMlAllSpawned) ? "NO-GO" : "INCONCLUSIVE",
                    evidence = (forcedRuntimeAllSpawned && forcedMlAllSpawned)
                        ? "Forced production starts and spawned units on both runtime-only and ML-pipeline paths."
                        : "Forced path did not conclusively prove spawn success for all advanced units."
                },
            };
        }

        private static string DetermineLossLayer(HypothesisVerdict[] hypotheses)
        {
            if (FindVerdict(hypotheses, "A") == "GO") return "runtime_barracks_production";
            if (FindVerdict(hypotheses, "B") == "GO") return "action_mask";
            if (FindVerdict(hypotheses, "C") == "GO") return "decoder_or_action_applier_mapping";
            if (FindVerdict(hypotheses, "D") == "GO") return "student_raw_policy_selection";
            if (FindVerdict(hypotheses, "E") == "GO") return "runtime_rejection_after_student_selection";
            if (FindVerdict(hypotheses, "F") == "GO") return "production_completion_or_spawn";
            return "no_forced_path_failure_detected_live_student_inconclusive_or_policy_selection";
        }

        private static string BuildMarkdown(ProbeReport report, string jsonPath)
        {
            var sb = new StringBuilder(4096);
            sb.AppendLine("# Stage6B4 Barracks Advanced Production Probe");
            sb.AppendLine();
            sb.AppendLine("- generated_at_utc: " + report.generated_at_utc);
            sb.AppendLine("- scene: " + report.scene);
            sb.AppendLine("- checkpoint_relative_path: " + report.checkpoint_relative_path);
            sb.AppendLine("- json_report: " + jsonPath);
            sb.AppendLine("- loss_layer: " + report.loss_layer);
            sb.AppendLine();

            sb.AppendLine("## Forced Runtime Path");
            AppendCaseTable(sb, report.runtime_only_results);
            sb.AppendLine();

            sb.AppendLine("## Mask Probe");
            if (report.mask_probe != null && report.mask_probe.probed)
            {
                sb.AppendLine("- Produce enabled: " + report.mask_probe.action_type_produce_enabled);
                sb.AppendLine("- produce_dir enabled: " + string.Join(",", report.mask_probe.produce_dir_enabled_indices));
                sb.AppendLine("- produce_unit_type enabled: " + string.Join(",", report.mask_probe.produce_unit_type_enabled_names));
                sb.AppendLine("- resources: " + report.mask_probe.resources);
                sb.AppendLine("- queue_busy: " + report.mask_probe.queue_busy);
                sb.AppendLine("- free adjacent cardinal / 8-neighbor: " + report.mask_probe.free_adjacent_cardinal + " / " + report.mask_probe.free_adjacent_8);
                sb.AppendLine("- UnitDefinition reasons: " + string.Join(" | ", report.mask_probe.unit_definition_reasons));
            }
            else
            {
                sb.AppendLine("- Mask probe unavailable: " + (report.mask_probe != null ? report.mask_probe.setup_error : "not run"));
            }
            sb.AppendLine();

            sb.AppendLine("## Forced ML Pipeline Path");
            AppendCaseTable(sb, report.forced_ml_pipeline_results);
            sb.AppendLine();

            sb.AppendLine("## Live Student");
            sb.AppendLine("- captured Barracks steps: " + (report.live_student_steps != null ? report.live_student_steps.Length : 0));
            sb.AppendLine("- command events: " + (report.command_events != null ? report.command_events.Length : 0));
            sb.AppendLine("- production events: " + (report.production_events != null ? report.production_events.Length : 0));
            sb.AppendLine();

            sb.AppendLine("## GO/NO-GO");
            for (int i = 0; i < report.hypotheses.Length; i++)
            {
                HypothesisVerdict h = report.hypotheses[i];
                sb.AppendLine("- " + h.id + ") " + h.hypothesis + ": " + h.verdict + " - " + h.evidence);
            }

            return sb.ToString();
        }

        private static void AppendCaseTable(StringBuilder sb, ProductionCaseResult[] rows)
        {
            sb.AppendLine("| unit | accepted | queue_started | completed | spawned | reason |");
            sb.AppendLine("| --- | --- | --- | --- | --- | --- |");
            if (rows == null || rows.Length == 0)
            {
                sb.AppendLine("| none | false | false | false | false | not run |");
                return;
            }

            for (int i = 0; i < rows.Length; i++)
            {
                ProductionCaseResult row = rows[i];
                bool accepted = row.matchmanager_accepted || row.action_applier_accepted;
                sb.AppendLine("| " + row.produce_unit_name
                    + " | " + accepted
                    + " | " + row.queue_started
                    + " | " + row.production_completed
                    + " | " + row.unit_spawned
                    + " | " + EscapeTable(row.rejection_reason)
                    + " |");
            }
        }

        private void ResolveReferences()
        {
            _gridManager = GridManager.Instance ?? FindFirstObjectByType<GridManager>();
            _unitRegistry = UnitRegistry.Instance ?? FindFirstObjectByType<UnitRegistry>();
            _matchManager = MatchManager.Instance ?? FindFirstObjectByType<MatchManager>();
            _matchBootstrap = MatchBootstrap.Instance ?? FindFirstObjectByType<MatchBootstrap>();
            _resourceManager = ResourceManager.Instance ?? FindFirstObjectByType<ResourceManager>();
            _episodeController = EpisodeController.Instance ?? FindFirstObjectByType<EpisodeController>();
            _studentAdapter = FindFirstObjectByType<Week6StudentPolicyAdapter>();

            if (_gridManager != null && _unitRegistry != null && _matchManager != null)
            {
                _decoder = new ActionDecoder(_gridManager, _unitRegistry);
                _applier = new ActionApplier(_gridManager, _unitRegistry, _matchManager, _resourceManager);
            }
        }

        private GridPosition FindFreePositionWithCardinalAndEightNeighbors()
        {
            for (int y = 2; y < ObservationContract.GridH - 2; y++)
            {
                for (int x = 2; x < ObservationContract.GridW - 2; x++)
                {
                    var pos = new GridPosition(x, y);
                    if (_gridManager.IsCellOccupied(pos))
                    {
                        continue;
                    }

                    if (CountFreeCardinalCells(pos) >= 4 && CountFreeEightNeighborCells(pos) >= 8)
                    {
                        return pos;
                    }
                }
            }

            return new GridPosition(-1, -1);
        }

        private bool TryFindFreeCardinalDirection(GridPosition pos, out Direction direction)
        {
            foreach (Direction candidate in new[] { Direction.North, Direction.East, Direction.South, Direction.West })
            {
                GridPosition target = pos.Neighbour(candidate);
                if (_gridManager.IsInside(target) && !_gridManager.IsCellOccupied(target))
                {
                    direction = candidate;
                    return true;
                }
            }

            direction = Direction.North;
            return false;
        }

        private int CountFreeCardinalCells(GridPosition pos)
        {
            if (_gridManager == null)
            {
                return 0;
            }

            int count = 0;
            foreach (Direction direction in new[] { Direction.North, Direction.East, Direction.South, Direction.West })
            {
                GridPosition target = pos.Neighbour(direction);
                if (_gridManager.IsInside(target) && !_gridManager.IsCellOccupied(target))
                {
                    count++;
                }
            }

            return count;
        }

        private int CountFreeEightNeighborCells(GridPosition pos)
        {
            if (_gridManager == null)
            {
                return 0;
            }

            int count = 0;
            for (int dy = -1; dy <= 1; dy++)
            {
                for (int dx = -1; dx <= 1; dx++)
                {
                    if (dx == 0 && dy == 0)
                    {
                        continue;
                    }

                    var target = new GridPosition(pos.X + dx, pos.Y + dy);
                    if (_gridManager.IsInside(target) && !_gridManager.IsCellOccupied(target))
                    {
                        count++;
                    }
                }
            }

            return count;
        }

        private List<UnitRuntime> FindBarracks(Owner owner)
        {
            var result = new List<UnitRuntime>();
            if (_unitRegistry == null)
            {
                return result;
            }

            List<UnitRuntime> units = _unitRegistry.GetAllUnits();
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit != null && unit.IsAlive && unit.Owner == owner && unit.Type == UnitType.Barracks)
                {
                    result.Add(unit);
                }
            }

            return result;
        }

        private int FindAnyBarracksFlat(Owner owner)
        {
            List<UnitRuntime> barracks = FindBarracks(owner);
            return barracks.Count > 0 ? barracks[0].GridPos.ToFlatIndex() : -1;
        }

        private int CountUnitsByType(UnitType type, Owner owner)
        {
            if (_unitRegistry == null)
            {
                return 0;
            }

            int count = 0;
            List<UnitRuntime> units = _unitRegistry.GetAllUnits();
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit != null && unit.IsAlive && unit.Type == type && unit.Owner == owner)
                {
                    count++;
                }
            }

            return count;
        }

        private void InitializeUnitCountSnapshot()
        {
            _lastUnitCounts[UnitType.Light] = CountUnitsByType(UnitType.Light, _studentOwner);
            _lastUnitCounts[UnitType.Heavy] = CountUnitsByType(UnitType.Heavy, _studentOwner);
            _lastUnitCounts[UnitType.Ranged] = CountUnitsByType(UnitType.Ranged, _studentOwner);
        }

        private string[] BuildUnitDefinitionReasons(Owner owner)
        {
            var reasons = new List<string>();
            GameConfig config = _matchBootstrap != null ? _matchBootstrap.GetConfig() : null;
            foreach (int idx in new[] { 4, 5, 6 })
            {
                UnitType type = ProduceIndexToUnitType(idx);
                UnitDefinition def = config != null ? config.GetDefinition(type) : null;
                if (def == null)
                {
                    reasons.Add(idx + "=" + type + ":missing UnitDefinition");
                }
                else
                {
                    int resources = _matchManager != null ? _matchManager.GetResources(owner) : 0;
                    reasons.Add(idx + "=" + type + ":ok cost=" + def.productionCost + " time=" + def.productionTime + " affordable=" + (resources >= def.productionCost));
                }
            }

            return reasons.ToArray();
        }

        private bool TryReadLatestAdapterJson(out string path)
        {
            path = string.Empty;
            if (_studentAdapter == null)
            {
                return false;
            }

            StudentInferenceDiagnosticsSnapshot snapshot = _studentAdapter.GetInferenceDiagnosticsSnapshot();
            if (!string.IsNullOrWhiteSpace(snapshot.last_output_json_path) && File.Exists(snapshot.last_output_json_path))
            {
                path = snapshot.last_output_json_path;
                return true;
            }

            return false;
        }

        private static bool ReadActionFlatValue(string json, int flat, int branch, int branchSize, out int value)
        {
            value = -1;
            int[] values = ExtractIntArray(json, "action_flat");
            if (values.Length != ActionContract.TotalActionFlatSize)
            {
                return false;
            }

            int offset = flat * ActionContract.ActionFlatSize + ActionContract.BranchOffset(branch);
            if (offset < 0 || offset >= values.Length)
            {
                return false;
            }

            value = values[offset];
            return value >= 0 && value < branchSize;
        }

        private static string ExtractGlobalCellDiagnosticObject(string json, int flat)
        {
            if (string.IsNullOrWhiteSpace(json))
            {
                return string.Empty;
            }

            int sectionStart = json.IndexOf("\"global_cell_action_type_diagnostics\"", StringComparison.Ordinal);
            if (sectionStart < 0)
            {
                return string.Empty;
            }

            int arrayStart = json.IndexOf('[', sectionStart);
            if (arrayStart < 0)
            {
                return string.Empty;
            }

            int arrayEnd = FindMatchingJsonDelimiter(json, arrayStart, '[', ']');
            if (arrayEnd <= arrayStart)
            {
                return string.Empty;
            }

            string diagnostics = json.Substring(arrayStart, arrayEnd - arrayStart + 1);
            string needle = "\"flat_index\"\\s*:\\s*" + flat.ToString(CultureInfo.InvariantCulture);
            Match match = Regex.Match(diagnostics, needle);
            if (!match.Success)
            {
                return string.Empty;
            }

            int start = diagnostics.LastIndexOf('{', match.Index);
            if (start < 0)
            {
                return string.Empty;
            }

            int depth = 0;
            bool inString = false;
            bool escape = false;
            for (int i = start; i < diagnostics.Length; i++)
            {
                char c = diagnostics[i];
                if (escape)
                {
                    escape = false;
                    continue;
                }

                if (c == '\\' && inString)
                {
                    escape = true;
                    continue;
                }

                if (c == '"')
                {
                    inString = !inString;
                    continue;
                }

                if (inString)
                {
                    continue;
                }

                if (c == '{') depth++;
                else if (c == '}')
                {
                    depth--;
                    if (depth == 0)
                    {
                        return diagnostics.Substring(start, i - start + 1);
                    }
                }
            }

            return string.Empty;
        }

        private static int FindMatchingJsonDelimiter(string json, int start, char open, char close)
        {
            int depth = 0;
            bool inString = false;
            bool escape = false;
            for (int i = start; i < json.Length; i++)
            {
                char c = json[i];
                if (escape)
                {
                    escape = false;
                    continue;
                }

                if (c == '\\' && inString)
                {
                    escape = true;
                    continue;
                }

                if (c == '"')
                {
                    inString = !inString;
                    continue;
                }

                if (inString)
                {
                    continue;
                }

                if (c == open)
                {
                    depth++;
                }
                else if (c == close)
                {
                    depth--;
                    if (depth == 0)
                    {
                        return i;
                    }
                }
            }

            return -1;
        }

        private static int[] ExtractIntArray(string json, string key)
        {
            string body = ExtractArrayBody(json, key);
            if (string.IsNullOrWhiteSpace(body))
            {
                return Array.Empty<int>();
            }

            string[] raw = body.Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            var values = new List<int>(raw.Length);
            for (int i = 0; i < raw.Length; i++)
            {
                if (int.TryParse(raw[i].Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out int value))
                {
                    values.Add(value);
                }
            }

            return values.ToArray();
        }

        private static float[] ExtractFloatArray(string json, string key)
        {
            string body = ExtractArrayBody(json, key);
            if (string.IsNullOrWhiteSpace(body))
            {
                return Array.Empty<float>();
            }

            string[] raw = body.Split(new[] { ',' }, StringSplitOptions.RemoveEmptyEntries);
            var values = new List<float>(raw.Length);
            for (int i = 0; i < raw.Length; i++)
            {
                if (float.TryParse(raw[i].Trim(), NumberStyles.Float, CultureInfo.InvariantCulture, out float value))
                {
                    values.Add(value);
                }
            }

            return values.ToArray();
        }

        private static string ExtractArrayBody(string json, string key)
        {
            if (string.IsNullOrWhiteSpace(json))
            {
                return string.Empty;
            }

            Match match = Regex.Match(json, "\"" + Regex.Escape(key) + "\"\\s*:\\s*\\[(?<body>.*?)\\]", RegexOptions.Singleline);
            return match.Success ? match.Groups["body"].Value : string.Empty;
        }

        private static float GetOrNaN(float[] values, int index)
        {
            return values != null && index >= 0 && index < values.Length ? values[index] : float.NaN;
        }

        private static int RankDescending(float[] values, int index)
        {
            if (values == null || index < 0 || index >= values.Length)
            {
                return -1;
            }

            int rank = 1;
            float target = values[index];
            for (int i = 0; i < values.Length; i++)
            {
                if (values[i] > target)
                {
                    rank++;
                }
            }

            return rank;
        }

        private static int[] EnabledIndices(bool[] mask)
        {
            if (mask == null)
            {
                return Array.Empty<int>();
            }

            var values = new List<int>();
            for (int i = 0; i < mask.Length; i++)
            {
                if (mask[i])
                {
                    values.Add(i);
                }
            }

            return values.ToArray();
        }

        private static string[] EnabledProduceNames(bool[] mask)
        {
            int[] indices = EnabledIndices(mask);
            var names = new string[indices.Length];
            for (int i = 0; i < indices.Length; i++)
            {
                names[i] = indices[i] + "=" + ProduceIndexName(indices[i]);
            }

            return names;
        }

        private static bool IsEnabled(bool[] mask, int index)
        {
            return mask != null && index >= 0 && index < mask.Length && mask[index];
        }

        private static bool Contains(int[] values, int needle)
        {
            if (values == null)
            {
                return false;
            }

            for (int i = 0; i < values.Length; i++)
            {
                if (values[i] == needle)
                {
                    return true;
                }
            }

            return false;
        }

        private static bool AllSpawned(List<ProductionCaseResult> rows)
        {
            if (rows == null || rows.Count < 3)
            {
                return false;
            }

            for (int i = 0; i < rows.Count; i++)
            {
                if (!rows[i].unit_spawned)
                {
                    return false;
                }
            }

            return true;
        }

        private static string FindVerdict(HypothesisVerdict[] hypotheses, string id)
        {
            if (hypotheses == null)
            {
                return "INCONCLUSIVE";
            }

            for (int i = 0; i < hypotheses.Length; i++)
            {
                if (hypotheses[i].id == id)
                {
                    return hypotheses[i].verdict;
                }
            }

            return "INCONCLUSIVE";
        }

        private CommandEventRecord FindLiveCommandEvent(int step, int flat)
        {
            for (int i = _commandEvents.Count - 1; i >= 0; i--)
            {
                if (i < _liveCommandEventStartIndex)
                {
                    break;
                }

                CommandEventRecord row = _commandEvents[i];
                if (row.actor_flat == flat && row.step <= step && row.step >= step - 1)
                {
                    return row;
                }
            }

            return null;
        }

        private ProductionEventRecord FindLiveProductionEvent(int step, int flat)
        {
            for (int i = _productionEvents.Count - 1; i >= 0; i--)
            {
                if (i < _liveProductionEventStartIndex)
                {
                    break;
                }

                ProductionEventRecord row = _productionEvents[i];
                if ((row.barracks_flat == flat || row.barracks_flat < 0) && row.step == step)
                {
                    return row;
                }
            }

            return null;
        }

        private static ProductionCaseResult CreateCaseResult(string path, int produceIndex)
        {
            return new ProductionCaseResult
            {
                path = path,
                produce_unit_type_index = produceIndex,
                produce_unit_name = ProduceIndexName(produceIndex),
                setup_ok = false,
                rejection_reason = string.Empty,
            };
        }

        private static UnitType ProduceIndexToUnitType(int index)
        {
            return index switch
            {
                4 => UnitType.Light,
                5 => UnitType.Heavy,
                6 => UnitType.Ranged,
                _ => UnitType.Worker
            };
        }

        private static string ProduceIndexName(int index)
        {
            return index switch
            {
                0 => "Resource",
                1 => "Base",
                2 => "Barracks",
                3 => "Worker",
                4 => "Light",
                5 => "Heavy",
                6 => "Ranged",
                _ => "idx" + index
            };
        }

        private static int RuntimeProduceEnumValue(int produceIndex)
        {
            return produceIndex switch
            {
                4 => (int)ProducibleUnit.Light,
                5 => (int)ProducibleUnit.Heavy,
                6 => (int)ProducibleUnit.Ranged,
                _ => (int)ProducibleUnit.Worker
            };
        }

        private static string FirstNonEmpty(string a, string b)
        {
            return !string.IsNullOrWhiteSpace(a) ? a : (!string.IsNullOrWhiteSpace(b) ? b : string.Empty);
        }

        private static string AppendReason(string current, string addition)
        {
            if (string.IsNullOrWhiteSpace(current))
            {
                return addition ?? string.Empty;
            }

            return current + " " + addition;
        }

        private static string EscapeTable(string value)
        {
            return string.IsNullOrWhiteSpace(value) ? "none" : value.Replace("|", "/");
        }

        [Serializable]
        private sealed class ProbeReport
        {
            public string generated_at_utc;
            public string scene;
            public string reason;
            public string checkpoint_relative_path;
            public bool forced_probe_completed;
            public ProductionCaseResult[] runtime_only_results;
            public MaskProbeResult mask_probe;
            public ProductionCaseResult[] forced_ml_pipeline_results;
            public LiveStepRecord[] live_student_steps;
            public CommandEventRecord[] command_events;
            public ProductionEventRecord[] production_events;
            public HypothesisVerdict[] hypotheses;
            public string loss_layer;
        }

        [Serializable]
        private sealed class ProductionCaseResult
        {
            public string path;
            public int produce_unit_type_index;
            public string produce_unit_name;
            public bool setup_ok;
            public int barracks_flat;
            public int produce_dir;
            public int resources_before;
            public int resources_after;
            public int free_adjacent_cardinal;
            public int free_adjacent_8;
            public bool queue_busy_before;
            public bool matchmanager_apply_command_returned;
            public bool action_applier_accepted;
            public bool action_applier_rejected;
            public bool matchmanager_accepted;
            public bool matchmanager_rejected;
            public bool step_match_called;
            public bool queue_started;
            public string queue_type_after_start;
            public bool production_completed;
            public bool unit_spawned;
            public int spawned_count_delta;
            public int steps_until_spawn;
            public int fake_action_flat_size;
            public int fake_action_type_value;
            public int fake_produce_unit_type_value;
            public bool mask_produce_enabled;
            public bool mask_produce_unit_type_enabled;
            public int decoded_action_count;
            public int masked_out_choices;
            public int fallback_to_noop;
            public string raw_action_type_top1;
            public int raw_produce_unit_type_top1;
            public string postmask_action_type;
            public int postmask_produce_unit_type;
            public string fallback_reason;
            public string rejection_reason;
        }

        [Serializable]
        private sealed class MaskProbeResult
        {
            public bool probed;
            public string setup_error;
            public int barracks_flat;
            public bool action_type_produce_enabled;
            public int[] produce_dir_enabled_indices;
            public int[] produce_unit_type_enabled_indices;
            public string[] produce_unit_type_enabled_names;
            public int resources;
            public bool queue_busy;
            public int free_adjacent_cardinal;
            public int free_adjacent_8;
            public string[] unit_definition_reasons;
        }

        [Serializable]
        private sealed class LiveStepRecord
        {
            public int step;
            public int barracks_flat;
            public int x;
            public int y;
            public bool has_student_report;
            public string artifact_path;
            public string raw_action_type_top1;
            public int raw_produce_unit_type_top1;
            public string postmask_action_type;
            public int postmask_produce_unit_type;
            public bool mask_produce_enabled;
            public bool mask_unit_4_enabled;
            public bool mask_unit_5_enabled;
            public bool mask_unit_6_enabled;
            public string fallback_reason;
            public bool logits_available;
            public bool produce_unit_logits_available;
            public string logits_unavailable_reason;
            public float[] action_type_logits;
            public float[] produce_unit_type_logits;
            public float produce_logit;
            public int produce_rank;
            public float light_logit;
            public int light_rank;
            public float heavy_logit;
            public int heavy_rank;
            public float ranged_logit;
            public int ranged_rank;
            public string action_applier_status;
            public string matchmanager_status;
            public string rejection_reason;
            public string accepted_command_action;
            public string accepted_command_produce_unit_type;
            public bool queue_busy;
            public string queue_status;
            public string production_event;
            public string spawned_unit_type;
            public int resources;
            public int free_adjacent_cardinal;
            public int free_adjacent_8;
        }

        [Serializable]
        private sealed class CommandEventRecord
        {
            public int step;
            public int actor_flat;
            public string action_type;
            public string produce_unit_type;
            public string action_applier_status;
            public string matchmanager_status;
            public string reason;
        }

        [Serializable]
        private sealed class ProductionEventRecord
        {
            public int step;
            public int barracks_flat;
            public string event_type;
            public string unit_type;
            public int count_delta;
        }

        [Serializable]
        private sealed class HypothesisVerdict
        {
            public string id;
            public string hypothesis;
            public string verdict;
            public string evidence;
        }

        private struct QueueSnapshot
        {
            public bool IsProducing;
            public string UnitType;

            public static QueueSnapshot From(ProductionQueue queue)
            {
                return new QueueSnapshot
                {
                    IsProducing = queue != null && queue.IsProducing,
                    UnitType = queue != null && queue.CurrentProducingType.HasValue
                        ? queue.CurrentProducingType.Value.ToString()
                        : "none"
                };
            }
        }
    }
}
