using System;
using System.Collections.Generic;
using System.Text;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.ML
{
    public readonly struct HeuristicActionEvaluation
    {
        public HeuristicActionEvaluation(
            Owner playerId,
            UnitActionType actionType,
            ProducibleUnit produceUnitType,
            bool accepted,
            string rejectionReason)
        {
            PlayerId = playerId;
            ActionType = actionType;
            ProduceUnitType = produceUnitType;
            Accepted = accepted;
            RejectionReason = rejectionReason ?? string.Empty;
        }

        public Owner PlayerId { get; }
        public UnitActionType ActionType { get; }
        public ProducibleUnit ProduceUnitType { get; }
        public bool Accepted { get; }
        public string RejectionReason { get; }
    }

    internal static class HeuristicV2ActionDefaults
    {
        public const int AttackCenterIndex = 24;
        public const int WorkerProduceIndex = 3;
        public const int BarracksBuildProduceIndex = 2;
    }

    public enum HeuristicControlMode
    {
        Idle = 0,
        Heuristic = 1
    }

    internal readonly struct DebugActionSelection
    {
        public DebugActionSelection(int actorIndexFlat, int actionType, int direction, int produceUnitType, int attackTargetLocal)
        {
            ActorIndexFlat = actorIndexFlat;
            ActionType = actionType;
            Direction = direction;
            ProduceUnitType = produceUnitType;
            AttackTargetLocal = attackTargetLocal;
        }

        public int ActorIndexFlat { get; }
        public int ActionType { get; }
        public int Direction { get; }
        public int ProduceUnitType { get; }
        public int AttackTargetLocal { get; }

        public static DebugActionSelection NoActorNoOp => new DebugActionSelection(
            actorIndexFlat: ActionContract.TotalCells,
            actionType: ActionContract.ACTION_NOOP,
            direction: ActionContract.DIR_NORTH,
            produceUnitType: HeuristicV2ActionDefaults.WorkerProduceIndex,
            attackTargetLocal: HeuristicV2ActionDefaults.AttackCenterIndex);

        public override string ToString()
        {
            return $"debug(actor={ActorIndexFlat},type={ActionType},dir={Direction},produce={ProduceUnitType},attackLocal={AttackTargetLocal})";
        }
    }

    internal readonly struct HeuristicDecisionTrace
    {
        public HeuristicDecisionTrace(
            Owner playerId,
            bool usedPipeline,
            float[] observation,
            ActionMaskSet transferMask,
            DebugActionSelection selectedDebugAction,
            AgentAction decodedAction,
            bool actionAccepted,
            string reason,
            string applierRejection)
        {
            PlayerId = playerId;
            UsedPipeline = usedPipeline;
            Observation = observation;
            TransferMask = transferMask;
            SelectedDebugAction = selectedDebugAction;
            DecodedAction = decodedAction;
            ActionAccepted = actionAccepted;
            Reason = reason;
            ApplierRejection = applierRejection;
        }

        public Owner PlayerId { get; }
        public bool UsedPipeline { get; }
        public float[] Observation { get; }
        public ActionMaskSet TransferMask { get; }
        public DebugActionSelection SelectedDebugAction { get; }
        public AgentAction DecodedAction { get; }
        public bool ActionAccepted { get; }
        public string Reason { get; }
        public string ApplierRejection { get; }

        public string BuildLogLine()
        {
            string acceptance = ActionAccepted ? "accepted" : "rejected";
            string rejection = string.IsNullOrWhiteSpace(ApplierRejection) ? "" : $", rejection={ApplierRejection}";
            return $"player={PlayerId}, selected={SelectedDebugAction}, decoded={DecodedAction.ActionType}, reason={Reason}, result={acceptance}{rejection}";
        }
    }

    /// <summary>
    /// Heuristic controller that intentionally routes decisions through the Week 3 policy pipeline.
    ///
    /// This component is a debug and integration tool. It is not the canonical contract surface
    /// for transfer compatibility and should not be treated as a semantic oracle.
    /// </summary>
    [DisallowMultipleComponent]
    public class HeuristicPolicyAdapter : MonoBehaviour
    {
        [Header("Scene references")]
        [SerializeField] private GridManager _gridManager;
        [SerializeField] private UnitRegistry _unitRegistry;
        [SerializeField] private ResourceManager _resourceManager;
        [SerializeField] private MatchManager _matchManager;
        [SerializeField] private MatchBootstrap _matchBootstrap;

        [Header("Player control")]
        [SerializeField] private HeuristicControlMode _player1Control = HeuristicControlMode.Heuristic;
        [SerializeField] private HeuristicControlMode _player2Control = HeuristicControlMode.Heuristic;

        [Header("Diagnostics")]
        [SerializeField] private bool _enableDecisionLogs = false;
        [SerializeField] private bool _logMaskSummary = false;

        [Header("Heuristic parameters")]
        [SerializeField] private int _maxWorkerLimit = 2;

        private MlPolicyPipelineFacade _policyPipeline;
        private readonly Dictionary<Owner, int> _decisionCycleByPlayer = new Dictionary<Owner, int>(2);

        private readonly List<UnitRuntime> _unitsScratch = new List<UnitRuntime>(64);
        private readonly StringBuilder _logBuilder = new StringBuilder(256);

        public event Action<HeuristicActionEvaluation> OnActionEvaluated;

        // Diagnostic counter: incremented each time a player falls through to the residual
        // obs/mask rebuild path because useCanonicalStepInput was true but stepInput.Perspective
        // did not match that player (= self-play second-player rebuild debt, Day 4/5).
        private int _residualOpponentRebuildCount;

        /// <summary>
        /// Injects runtime references and rebuilds the Week 3 heuristic pipeline wrapper.
        /// </summary>
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

        /// <summary>
        /// Resets internal heuristic state.
        ///
        /// The current heuristic is stateless, but the explicit entry point is kept so Week 4 can
        /// add deterministic state without changing the calling code.
        /// </summary>
        public void ResetHeuristicState()
        {
            // Reserved for future deterministic stateful heuristics.
            _decisionCycleByPlayer.Clear();
        }

        /// <summary>
        /// Executes one heuristic decision step for the currently enabled players.
        ///
        /// Downstream execution still converges into the same ActionApplier and MatchManager path
        /// that a future ML policy will use.
        /// </summary>
        public void ExecuteDecisionStep()
        {
            ExecuteDecisionStepWithCountsInternal(useCanonicalStepInput: false, default);
        }

        /// <summary>
        /// Executes one heuristic decision step and returns aggregated accept/reject counts.
        ///
        /// Unlike <see cref="ExecuteDecisionStep"/> (which returns void), this method surfaces
        /// real per-player decision outcomes from ActionApplier. Each enabled player submits
        /// at most one action per call, so counts are in the range 0–2 for self-play.
        ///
        /// Used by <c>BaselineDecisionSource</c> to populate honest action counts in
        /// <see cref="RlLoopStepReport"/> instead of returning <see cref="PolicyExecutionReport.Empty"/>.
        /// </summary>
        internal (int acceptedTotal, int rejectedTotal) ExecuteDecisionStepWithCounts()
        {
            return ExecuteDecisionStepWithCountsInternal(useCanonicalStepInput: false, default);
        }

        internal (int acceptedTotal, int rejectedTotal) ExecuteDecisionStepWithCounts(in RlLoopStepInput stepInput)
        {
            return ExecuteDecisionStepWithCountsInternal(useCanonicalStepInput: true, stepInput);
        }

        private (int acceptedTotal, int rejectedTotal) ExecuteDecisionStepWithCountsInternal(bool useCanonicalStepInput, in RlLoopStepInput stepInput)
        {
            long perfStart = Stage6B3PerformanceCounters.Begin(Stage6B3PerfMetric.HeuristicDecision);
            EnsurePipeline();
            if (!CanRun())
            {
                Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.HeuristicDecision, perfStart);
                return (0, 0);
            }

            int accepted = 0, rejected = 0;

            if (_player1Control == HeuristicControlMode.Heuristic)
            {
                bool p1CanUseCanonical = useCanonicalStepInput && stepInput.Perspective == Owner.Player1;
                if (!p1CanUseCanonical && useCanonicalStepInput)
                {
                    // Player1 is not the canonical perspective: residual rebuild for opponent.
                    _residualOpponentRebuildCount++;
                }

                var p1Result = ExecutePlayerDecisionBatch(Owner.Player1, p1CanUseCanonical, stepInput);
                accepted += p1Result.accepted;
                rejected += p1Result.rejected;
            }

            if (_player2Control == HeuristicControlMode.Heuristic)
            {
                bool p2CanUseCanonical = useCanonicalStepInput && stepInput.Perspective == Owner.Player2;
                if (!p2CanUseCanonical && useCanonicalStepInput)
                {
                    // Player2 is not the canonical perspective: residual rebuild for opponent.
                    _residualOpponentRebuildCount++;
                }

                var p2Result = ExecutePlayerDecisionBatch(Owner.Player2, p2CanUseCanonical, stepInput);
                accepted += p2Result.accepted;
                rejected += p2Result.rejected;
            }

            Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.HeuristicDecision, perfStart);
            return (accepted, rejected);
        }

        private (int accepted, int rejected) ExecutePlayerDecisionBatch(Owner playerId, bool canUseCanonical, in RlLoopStepInput stepInput)
        {
            DebugActionMaskSet debugMask = canUseCanonical
                ? new DebugActionMaskSet(stepInput.CanonicalMask)
                : _policyPipeline.BuildDebugMask(playerId);

            if (_logMaskSummary)
            {
                Debug.Log($"[HeuristicPolicyAdapter] {playerId} mask built ({debugMask.TransferMask.AvailableActorCount} actors):\n{debugMask.TransferMask.BuildSummaryDump(4)}");
            }

            int accepted = 0;
            int rejected = 0;

            for (int actorIndex = 0; actorIndex < ActionContract.TotalCells; actorIndex++)
            {
                if (!debugMask.ActorIndexMask[actorIndex])
                {
                    continue;
                }

                if (!TrySelectSingleActor(playerId, debugMask, actorIndex, out DebugActionSelection selection, out string reason))
                {
                    continue;
                }

                if (selection.ActionType == ActionContract.ACTION_NOOP)
                {
                    continue;
                }

                PolicyExecutionReport execution = _policyPipeline.ExecuteDebugSelection(selection, playerId, debugMask.TransferMask, "heuristic");
                AgentAction decoded = execution.DecodedActions.Count > 0
                    ? execution.DecodedActions[0]
                    : AgentAction.CreateNoOp(ActionSourceType.Debug);

                bool actionAccepted = execution.AcceptedCount > 0;
                if (actionAccepted)
                {
                    accepted++;
                }
                else
                {
                    rejected++;
                }

                OnActionEvaluated?.Invoke(new HeuristicActionEvaluation(
                    playerId,
                    decoded.ActionType,
                    decoded.ProduceUnitType,
                    actionAccepted,
                    execution.PrimaryRejectionReason));

                if (_enableDecisionLogs)
                {
                    string rejection = string.IsNullOrWhiteSpace(execution.PrimaryRejectionReason)
                        ? string.Empty
                        : $", rejection={execution.PrimaryRejectionReason}";
                    string result = actionAccepted ? "accepted" : "rejected";
                    Debug.Log($"[HeuristicPolicyAdapter] player={playerId}, actor={actorIndex}, selected={selection}, decoded={decoded.ActionType}, reason={reason}, result={result}{rejection}");
                }
            }

            return (accepted, rejected);
        }

        internal HeuristicDecisionTrace DecideAndApply(Owner playerId)
        {
            return DecideAndApplyInternal(playerId, preferredActorType: null, preferredActorIndexFlat: null, useCanonicalStepInput: false, default);
        }

        internal HeuristicDecisionTrace DecideAndApply(Owner playerId, in RlLoopStepInput stepInput)
        {
            return DecideAndApplyInternal(playerId, preferredActorType: null, preferredActorIndexFlat: null, useCanonicalStepInput: true, stepInput);
        }

        internal HeuristicDecisionTrace DecideAndApplyForPreferredActorType(Owner playerId, UnitType preferredActorType)
        {
            return DecideAndApplyInternal(playerId, preferredActorType, preferredActorIndexFlat: null, useCanonicalStepInput: false, default);
        }

        internal HeuristicDecisionTrace DecideAndApplyForActor(Owner playerId, GridPosition actorPosition)
        {
            return DecideAndApplyInternal(playerId, preferredActorType: null, preferredActorIndexFlat: actorPosition.ToFlatIndex(), useCanonicalStepInput: false, default);
        }

        private HeuristicDecisionTrace DecideAndApplyInternal(
            Owner playerId,
            UnitType? preferredActorType,
            int? preferredActorIndexFlat,
            bool useCanonicalStepInput,
            in RlLoopStepInput stepInput)
        {
            EnsurePipeline();

            if (!CanRun())
            {
                return new HeuristicDecisionTrace(
                    playerId,
                    usedPipeline: false,
                    observation: Array.Empty<float>(),
                    transferMask: null,
                    selectedDebugAction: DebugActionSelection.NoActorNoOp,
                    decodedAction: AgentAction.CreateNoOp(ActionSourceType.Debug),
                    actionAccepted: false,
                    reason: "Pipeline is not ready",
                    applierRejection: string.Empty);
            }

            bool canUseCanonical = useCanonicalStepInput
                && stepInput.Perspective == playerId
                && stepInput.CanonicalObservation.SpatialObservation != null
                && stepInput.CanonicalMask != null;

            ObservationPackage package = canUseCanonical
                ? stepInput.CanonicalObservation
                : _policyPipeline.BuildObservationPackage(playerId, ObservationMode.UnityMvpTransfer);
            DebugActionMaskSet debugMask = canUseCanonical
                ? new DebugActionMaskSet(stepInput.CanonicalMask)
                : _policyPipeline.BuildDebugMask(playerId);

            if (_logMaskSummary)
            {
                Debug.Log($"[HeuristicPolicyAdapter] mask summary for {playerId}:\n{debugMask.TransferMask.BuildSummaryDump(4)}");
            }

            DebugActionSelection selection = SelectDebugAction(playerId, debugMask, preferredActorType, preferredActorIndexFlat, out string reason);
            PolicyExecutionReport execution = _policyPipeline.ExecuteDebugSelection(selection, playerId, debugMask.TransferMask, "heuristic");
            AgentAction decoded = execution.DecodedActions.Count > 0
                ? execution.DecodedActions[0]
                : AgentAction.CreateNoOp(ActionSourceType.Debug);
            bool accepted = execution.AcceptedCount > 0;
            string applierRejection = execution.PrimaryRejectionReason;

            var trace = new HeuristicDecisionTrace(
                playerId,
                usedPipeline: true,
                observation: package.SpatialObservation,
                transferMask: debugMask.TransferMask,
                selectedDebugAction: selection,
                decodedAction: decoded,
                actionAccepted: accepted,
                reason: reason,
                applierRejection: applierRejection);

            if (_enableDecisionLogs)
            {
                Debug.Log($"[HeuristicPolicyAdapter] {trace.BuildLogLine()}");
            }

            return trace;
        }

        /// <summary>
        /// Selects which players should be driven by the heuristic adapter.
        /// </summary>
        public void SetPlayerControlModes(HeuristicControlMode player1, HeuristicControlMode player2)
        {
            _player1Control = player1;
            _player2Control = player2;
        }

        internal bool TryGetPipelineDiagnostics(out string diagnostics)
        {
            EnsurePipeline();
            diagnostics = string.Empty;

            if (!CanRun())
            {
                diagnostics = "pipeline-unavailable";
                return false;
            }

            _logBuilder.Clear();
            _logBuilder.Append("pipeline-ready");
            _logBuilder.Append(" | control(P1,P2)=").Append(_player1Control).Append(',').Append(_player2Control);
            _logBuilder.Append(" | residualOpponentRebuilds=").Append(_residualOpponentRebuildCount);
            diagnostics = _logBuilder.ToString();
            return true;
        }

        private DebugActionSelection SelectDebugAction(
            Owner playerId,
            DebugActionMaskSet debugMask,
            UnitType? preferredActorType,
            int? preferredActorIndexFlat,
            out string reason)
        {
            reason = "fallback:no-actor";

            if (debugMask == null)
            {
                reason = "fallback:null-mask";
                return DebugActionSelection.NoActorNoOp;
            }

            if (preferredActorIndexFlat.HasValue)
            {
                if (TrySelectSingleActor(playerId, debugMask, preferredActorIndexFlat.Value, out DebugActionSelection forcedSelection, out reason))
                {
                    return forcedSelection;
                }
            }

            if (preferredActorType.HasValue)
            {
                if (TrySelectFromScan(playerId, debugMask, preferredActorType, selectionPhase: 0, out DebugActionSelection preferredSelection, out reason))
                {
                    return preferredSelection;
                }
            }

            int selectionPhase = GetAndAdvanceSelectionPhase(playerId);
            if (TrySelectFromScan(playerId, debugMask, preferredActorType: null, selectionPhase, out DebugActionSelection anySelection, out reason))
            {
                return anySelection;
            }

            return DebugActionSelection.NoActorNoOp;
        }

        private bool TrySelectFromScan(
            Owner playerId,
            DebugActionMaskSet debugMask,
            UnitType? preferredActorType,
            int selectionPhase,
            out DebugActionSelection selection,
            out string reason)
        {
            selection = DebugActionSelection.NoActorNoOp;
            reason = "fallback:no-actor";

            bool filterByType = preferredActorType.HasValue;
            int[] passOrder = BuildPassOrder(filterByType, selectionPhase);

            for (int passIndex = 0; passIndex < passOrder.Length; passIndex++)
            {
                int pass = passOrder[passIndex];
                for (int actorIndex = 0; actorIndex < ActionContract.TotalCells; actorIndex++)
                {
                    if (!debugMask.ActorIndexMask[actorIndex])
                    {
                        continue;
                    }

                    ActorActionMask actorMask = debugMask.GetActorMask(actorIndex);
                    if (actorMask == null)
                    {
                        continue;
                    }

                    GridPosition actorPos = GridPosition.FromFlatIndex(actorIndex);
                    UnitRuntime actor = _gridManager.GetOccupant(actorPos);
                    if (actor == null || actor.Owner != playerId || !actor.IsAlive)
                    {
                        continue;
                    }

                    if (filterByType && actor.Type != preferredActorType.Value)
                    {
                        continue;
                    }

                    if (pass == 0 && TrySelectWorkerAction(actorIndex, actor, actorMask, out DebugActionSelection workerSelection, out reason))
                    {
                        selection = workerSelection;
                        return true;
                    }

                    if (pass == 1 && TrySelectCombatAction(playerId, actorIndex, actor, actorMask, out DebugActionSelection combatSelection, out reason))
                    {
                        selection = combatSelection;
                        return true;
                    }

                    if (pass == 2 && TrySelectBuildingAction(actorIndex, actor, actorMask, out DebugActionSelection buildingSelection, out reason))
                    {
                        selection = buildingSelection;
                        return true;
                    }

                    if (pass == 3 && actorMask.IsActionTypeEnabled(UnitActionType.NoOp))
                    {
                        reason = $"fallback:no-op actor={actorIndex}";
                        selection = new DebugActionSelection(
                            actorIndexFlat: actorIndex,
                            actionType: ActionContract.ACTION_NOOP,
                            direction: ActionContract.DIR_NORTH,
                            produceUnitType: HeuristicV2ActionDefaults.WorkerProduceIndex,
                            attackTargetLocal: HeuristicV2ActionDefaults.AttackCenterIndex);
                        return true;
                    }
                }
            }

            return false;
        }

        private int[] BuildPassOrder(bool filterByType, int selectionPhase)
        {
            if (filterByType)
            {
                return new[] { 0, 1, 2, 3 };
            }

            switch (selectionPhase % 3)
            {
                case 0:
                    return new[] { 0, 1, 2, 3 }; // Worker -> Combat -> Building -> NoOp
                case 1:
                    return new[] { 1, 0, 2, 3 }; // Combat -> Worker -> Building -> NoOp
                default:
                    return new[] { 2, 0, 1, 3 }; // Building -> Worker -> Combat -> NoOp
            }
        }

        private int GetAndAdvanceSelectionPhase(Owner playerId)
        {
            int current = 0;
            if (_decisionCycleByPlayer.TryGetValue(playerId, out int existing))
            {
                current = existing;
            }

            _decisionCycleByPlayer[playerId] = current + 1;
            return current;
        }

        private bool TrySelectSingleActor(
            Owner playerId,
            DebugActionMaskSet debugMask,
            int actorIndex,
            out DebugActionSelection selection,
            out string reason)
        {
            selection = DebugActionSelection.NoActorNoOp;
            reason = "fallback:no-actor";

            if (actorIndex < 0 || actorIndex >= ActionContract.TotalCells || !debugMask.ActorIndexMask[actorIndex])
            {
                reason = $"fallback:actor-masked index={actorIndex}";
                return false;
            }

            ActorActionMask actorMask = debugMask.GetActorMask(actorIndex);
            GridPosition actorPos = GridPosition.FromFlatIndex(actorIndex);
            UnitRuntime actor = _gridManager.GetOccupant(actorPos);

            if (actorMask == null || actor == null || actor.Owner != playerId || !actor.IsAlive)
            {
                reason = $"fallback:actor-invalid index={actorIndex}";
                return false;
            }

            if (TrySelectWorkerAction(actorIndex, actor, actorMask, out DebugActionSelection workerSelection, out reason))
            {
                selection = workerSelection;
                return true;
            }

            if (TrySelectBuildingAction(actorIndex, actor, actorMask, out DebugActionSelection buildingSelection, out reason))
            {
                selection = buildingSelection;
                return true;
            }

            if (TrySelectCombatAction(playerId, actorIndex, actor, actorMask, out DebugActionSelection combatSelection, out reason))
            {
                selection = combatSelection;
                return true;
            }

            if (actorMask.IsActionTypeEnabled(UnitActionType.NoOp))
            {
                reason = $"fallback:no-op actor={actorIndex}";
                selection = new DebugActionSelection(
                    actorIndex,
                    ActionContract.ACTION_NOOP,
                    ActionContract.DIR_NORTH,
                    HeuristicV2ActionDefaults.WorkerProduceIndex,
                    HeuristicV2ActionDefaults.AttackCenterIndex);
                return true;
            }

            return false;
        }

        private bool TrySelectWorkerAction(
            int actorIndex,
            UnitRuntime worker,
            ActorActionMask actorMask,
            out DebugActionSelection selection,
            out string reason)
        {
            selection = DebugActionSelection.NoActorNoOp;
            reason = string.Empty;

            if (worker.Type != UnitType.Worker)
            {
                return false;
            }

            if (worker.CarriedResources > 0)
            {
                if (actorMask.IsActionTypeEnabled(UnitActionType.Return) &&
                    TryChooseReturnDirection(worker, actorMask, out Direction returnDirection))
                {
                    selection = new DebugActionSelection(
                        actorIndex,
                        ActionContract.ACTION_RETURN,
                        (int)returnDirection,
                        HeuristicV2ActionDefaults.WorkerProduceIndex,
                        HeuristicV2ActionDefaults.AttackCenterIndex);
                    reason = $"worker:return cargo={worker.CarriedResources}";
                    return true;
                }

                if (actorMask.IsActionTypeEnabled(UnitActionType.Move) &&
                    TryChooseMoveDirectionToNearestBase(worker.Owner, worker.GridPos, actorMask.MoveDirectionMask, out Direction moveToBase))
                {
                    selection = new DebugActionSelection(
                        actorIndex,
                        ActionContract.ACTION_MOVE,
                        (int)moveToBase,
                        HeuristicV2ActionDefaults.WorkerProduceIndex,
                        HeuristicV2ActionDefaults.AttackCenterIndex);
                    reason = "worker:move-to-base";
                    return true;
                }
            }

            // Build Barracks if the player owns none yet and the mask permits it.
            // The mask (BuildWorkerBuildMask) already gates on resources and free adjacent cell,
            // so this branch only fires when both conditions are met.
            if (!PlayerHasBarracks(worker.Owner) &&
                actorMask.IsActionTypeEnabled(UnitActionType.Produce) &&
                TryChooseDirection(actorMask.ProduceDirectionMask, out Direction buildBarracksDir))
            {
                selection = new DebugActionSelection(
                    actorIndex,
                    ActionContract.ACTION_PRODUCE,
                    (int)buildBarracksDir,
                    HeuristicV2ActionDefaults.BarracksBuildProduceIndex,
                    HeuristicV2ActionDefaults.AttackCenterIndex);
                reason = "worker:build-barracks";
                return true;
            }

            if (actorMask.IsActionTypeEnabled(UnitActionType.Harvest) &&
                TryChooseHarvestDirection(worker, actorMask, out Direction harvestDir))
            {
                selection = new DebugActionSelection(
                    actorIndex,
                    ActionContract.ACTION_HARVEST,
                    (int)harvestDir,
                    HeuristicV2ActionDefaults.WorkerProduceIndex,
                    HeuristicV2ActionDefaults.AttackCenterIndex);
                reason = "worker:harvest-adjacent";
                return true;
            }

            if (actorMask.IsActionTypeEnabled(UnitActionType.Move) &&
                TryChooseMoveDirectionToNearestResource(worker.GridPos, actorMask.MoveDirectionMask, out Direction moveToResource))
            {
                selection = new DebugActionSelection(
                    actorIndex,
                    ActionContract.ACTION_MOVE,
                    (int)moveToResource,
                    HeuristicV2ActionDefaults.WorkerProduceIndex,
                    HeuristicV2ActionDefaults.AttackCenterIndex);
                reason = "worker:move-to-resource";
                return true;
            }

            return false;
        }

        private bool TrySelectBuildingAction(
            int actorIndex,
            UnitRuntime building,
            ActorActionMask actorMask,
            out DebugActionSelection selection,
            out string reason)
        {
            selection = DebugActionSelection.NoActorNoOp;
            reason = string.Empty;

            if (!building.IsBuilding)
            {
                return false;
            }

            if (!actorMask.IsActionTypeEnabled(UnitActionType.Produce))
            {
                return false;
            }

            if (!TryChooseDirection(actorMask.ProduceDirectionMask, out Direction produceDirection))
            {
                return false;
            }

            if (!TryChooseAffordableProduceType(building.Owner, actorMask.ProduceUnitTypeMask, out int produceTypeIndex))
            {
                return false;
            }

            selection = new DebugActionSelection(
                actorIndex,
                ActionContract.ACTION_PRODUCE,
                (int)produceDirection,
                produceTypeIndex,
                HeuristicV2ActionDefaults.AttackCenterIndex);
            reason = ActionContractMappings.TryMapV2ProduceIndexToUnitType(produceTypeIndex, out UnitType mappedType)
                ? $"building:produce type={mappedType}"
                : $"building:produce index={produceTypeIndex}";
            return true;
        }

        private bool TryChooseAffordableProduceType(Owner owner, bool[] produceTypeMask, out int produceTypeIndex)
        {
            produceTypeIndex = HeuristicV2ActionDefaults.WorkerProduceIndex;
            GameConfig config = _matchBootstrap != null ? _matchBootstrap.GetConfig() : null;
            if (produceTypeMask == null || produceTypeMask.Length == 0 || _matchManager == null || config == null)
            {
                return false;
            }

            PlayerState playerState = _matchManager.GetPlayerState(owner);
            if (playerState == null)
            {
                return false;
            }

            int workerCount = 0;
            IReadOnlyList<UnitRuntime> ownUnits = _unitRegistry != null ? _unitRegistry.GetUnitsByOwner(owner) : null;
            if (ownUnits != null)
            {
                for (int i = 0; i < ownUnits.Count; i++)
                {
                    UnitRuntime unit = ownUnits[i];
                    if (unit != null && unit.IsAlive && unit.Type == UnitType.Worker)
                    {
                        workerCount++;
                    }
                }
            }

            // Prevent infinite worker-only loops that often lead to timeout-only traces.
            int[] preference = workerCount < _maxWorkerLimit
                ? new[] { 3, 4, 5, 6 }
                : new[] { 4, 5, 6, 3 };

            for (int i = 0; i < preference.Length; i++)
            {
                int idx = preference[i];
                if (idx < 0 || idx >= produceTypeMask.Length || !produceTypeMask[idx])
                {
                    continue;
                }

                if (!ActionContractMappings.TryMapV2ProduceIndexToUnitType(idx, out UnitType unitType))
                {
                    continue;
                }

                UnitDefinition definition = config.GetDefinition(unitType);
                if (definition == null)
                {
                    continue;
                }

                // Affordability check uses actual definition cost, aligned with
                // BuildingRuntime.StartProducingUnit and the fixed ActionApplier.ValidateProduceAction.
                if (!playerState.CanAfford(definition.productionCost))
                {
                    continue;
                }

                produceTypeIndex = idx;
                return true;
            }

            return false;
        }

        private bool TrySelectCombatAction(
            Owner playerId,
            int actorIndex,
            UnitRuntime combatUnit,
            ActorActionMask actorMask,
            out DebugActionSelection selection,
            out string reason)
        {
            selection = DebugActionSelection.NoActorNoOp;
            reason = string.Empty;

            if (combatUnit.Type != UnitType.Light && combatUnit.Type != UnitType.Heavy && combatUnit.Type != UnitType.Ranged)
            {
                return false;
            }

            if (actorMask.IsActionTypeEnabled(UnitActionType.Attack) &&
                TryChooseAttackTargetLocal(playerId, combatUnit.GridPos, actorMask.AttackTargetLocalMask, out int attackLocal))
            {
                selection = new DebugActionSelection(
                    actorIndex,
                    ActionContract.ACTION_ATTACK,
                    ActionContract.DIR_NORTH,
                    HeuristicV2ActionDefaults.WorkerProduceIndex,
                    attackLocal);
                reason = $"combat:attack local={attackLocal}";
                return true;
            }

            if (actorMask.IsActionTypeEnabled(UnitActionType.Move) &&
                TryChooseMoveDirectionToNearestEnemy(playerId, combatUnit.GridPos, actorMask.MoveDirectionMask, out Direction moveToEnemy))
            {
                selection = new DebugActionSelection(
                    actorIndex,
                    ActionContract.ACTION_MOVE,
                    (int)moveToEnemy,
                    HeuristicV2ActionDefaults.WorkerProduceIndex,
                    HeuristicV2ActionDefaults.AttackCenterIndex);
                reason = "combat:move-to-enemy";
                return true;
            }

            if (actorMask.IsActionTypeEnabled(UnitActionType.Move) &&
                TryChooseMoveDirectionToEnemyBase(playerId, combatUnit.GridPos, actorMask.MoveDirectionMask, out Direction scoutDirection))
            {
                selection = new DebugActionSelection(
                    actorIndex,
                    ActionContract.ACTION_MOVE,
                    (int)scoutDirection,
                    HeuristicV2ActionDefaults.WorkerProduceIndex,
                    HeuristicV2ActionDefaults.AttackCenterIndex);
                reason = "combat:scout-enemy-base";
                return true;
            }

            return false;
        }

        private bool TryChooseReturnDirection(UnitRuntime worker, ActorActionMask actorMask, out Direction direction)
        {
            direction = Direction.North;

            for (int i = 0; i < actorMask.ReturnDirectionMask.Length; i++)
            {
                if (!actorMask.ReturnDirectionMask[i])
                {
                    continue;
                }

                Direction dir = (Direction)i;
                GridPosition targetPos = worker.GridPos.Neighbour(dir);
                UnitRuntime targetUnit = _gridManager.GetOccupant(targetPos);
                if (targetUnit != null && targetUnit.Owner == worker.Owner && targetUnit.Type == UnitType.Base)
                {
                    direction = dir;
                    return true;
                }
            }

            return false;
        }

        private bool TryChooseHarvestDirection(UnitRuntime worker, ActorActionMask actorMask, out Direction direction)
        {
            direction = Direction.North;

            for (int i = 0; i < actorMask.HarvestDirectionMask.Length; i++)
            {
                if (!actorMask.HarvestDirectionMask[i])
                {
                    continue;
                }

                Direction dir = (Direction)i;
                GridPosition target = worker.GridPos.Neighbour(dir);
                ResourceNode node = _resourceManager?.GetResourceNode(target);
                if (node != null && !node.IsExhausted)
                {
                    direction = dir;
                    return true;
                }
            }

            return false;
        }

        private bool TryChooseMoveDirectionToNearestBase(Owner owner, GridPosition from, bool[] moveMask, out Direction direction)
        {
            direction = Direction.North;
            _unitsScratch.Clear();
            _unitsScratch.AddRange(_unitRegistry.GetBuildingsByOwner(owner));

            GridPosition? nearestBasePos = null;
            int bestBaseDistance = int.MaxValue;
            for (int i = 0; i < _unitsScratch.Count; i++)
            {
                UnitRuntime building = _unitsScratch[i];
                if (building == null || building.Type != UnitType.Base)
                {
                    continue;
                }

                int dist = from.ManhattanDistance(building.GridPos);
                if (dist < bestBaseDistance)
                {
                    bestBaseDistance = dist;
                    nearestBasePos = building.GridPos;
                }
            }

            if (!nearestBasePos.HasValue)
            {
                return TryChooseDirection(moveMask, out direction);
            }

            return TryChooseDirectionTowards(from, nearestBasePos.Value, moveMask, out direction);
        }

        private bool TryChooseMoveDirectionToNearestResource(GridPosition from, bool[] moveMask, out Direction direction)
        {
            direction = Direction.North;
            IEnumerable<ResourceNode> resources = _resourceManager?.GetAllResourceNodes();
            if (resources == null)
            {
                return TryChooseDirection(moveMask, out direction);
            }

            GridPosition? nearestResourcePos = null;
            int bestDistance = int.MaxValue;
            foreach (ResourceNode node in resources)
            {
                if (node == null || node.IsExhausted)
                {
                    continue;
                }

                int dist = from.ManhattanDistance(node.GridPosition);
                if (dist < bestDistance)
                {
                    bestDistance = dist;
                    nearestResourcePos = node.GridPosition;
                }
            }

            if (!nearestResourcePos.HasValue)
            {
                return TryChooseDirection(moveMask, out direction);
            }

            return TryChooseDirectionTowards(from, nearestResourcePos.Value, moveMask, out direction);
        }

        private bool TryChooseMoveDirectionToNearestEnemy(Owner owner, GridPosition from, bool[] moveMask, out Direction direction)
        {
            direction = Direction.North;
            IReadOnlyList<UnitRuntime> allUnits = _unitRegistry.GetAllUnits();
            if (allUnits == null || allUnits.Count == 0)
            {
                return TryChooseDirection(moveMask, out direction);
            }

            GridPosition? nearestEnemyPos = null;
            int bestDistance = int.MaxValue;
            for (int i = 0; i < allUnits.Count; i++)
            {
                UnitRuntime unit = allUnits[i];
                if (unit == null || !unit.IsAlive || unit.Owner == owner || unit.Owner == Owner.Neutral)
                {
                    continue;
                }

                int dist = from.ManhattanDistance(unit.GridPos);
                if (dist < bestDistance)
                {
                    bestDistance = dist;
                    nearestEnemyPos = unit.GridPos;
                }
            }

            if (!nearestEnemyPos.HasValue)
            {
                return TryChooseDirection(moveMask, out direction);
            }

            return TryChooseDirectionTowards(from, nearestEnemyPos.Value, moveMask, out direction);
        }

        private bool TryChooseMoveDirectionToEnemyBase(Owner owner, GridPosition from, bool[] moveMask, out Direction direction)
        {
            direction = Direction.North;

            Owner enemyOwner = owner == Owner.Player1
                ? Owner.Player2
                : owner == Owner.Player2
                    ? Owner.Player1
                    : Owner.Neutral;
            if (enemyOwner == Owner.Neutral)
            {
                return TryChooseDirection(moveMask, out direction);
            }

            _unitsScratch.Clear();
            _unitsScratch.AddRange(_unitRegistry.GetBuildingsByOwner(enemyOwner));

            GridPosition? nearestEnemyBase = null;
            int bestDistance = int.MaxValue;
            for (int i = 0; i < _unitsScratch.Count; i++)
            {
                UnitRuntime building = _unitsScratch[i];
                if (building == null || !building.IsAlive || building.Type != UnitType.Base)
                {
                    continue;
                }

                int dist = from.ManhattanDistance(building.GridPos);
                if (dist < bestDistance)
                {
                    bestDistance = dist;
                    nearestEnemyBase = building.GridPos;
                }
            }

            if (!nearestEnemyBase.HasValue)
            {
                return TryChooseDirection(moveMask, out direction);
            }

            return TryChooseDirectionTowards(from, nearestEnemyBase.Value, moveMask, out direction);
        }

        private bool TryChooseDirectionTowards(GridPosition from, GridPosition target, bool[] directionMask, out Direction direction)
        {
            direction = Direction.North;
            int bestDistance = int.MaxValue;
            bool found = false;
            int currentDistance = from.ManhattanDistance(target);

            for (int i = 0; i < ActionContract.SIZE_DIRECTION; i++)
            {
                if (directionMask == null || i >= directionMask.Length || !directionMask[i])
                {
                    continue;
                }

                Direction candidateDirection = (Direction)i;
                GridPosition candidateTarget = from.Neighbour(candidateDirection);
                int candidateDistance = candidateTarget.ManhattanDistance(target);

                if (candidateDistance < currentDistance && (!found || candidateDistance < bestDistance))
                {
                    bestDistance = candidateDistance;
                    direction = candidateDirection;
                    found = true;
                }
            }

            return found;
        }

        private bool TryChooseDirection(bool[] directionMask, out Direction direction)
        {
            direction = Direction.North;
            if (directionMask == null)
            {
                return false;
            }

            for (int i = 0; i < ActionContract.SIZE_DIRECTION; i++)
            {
                if (i < directionMask.Length && directionMask[i])
                {
                    direction = (Direction)i;
                    return true;
                }
            }

            return false;
        }

        private bool TryChooseProduceType(bool[] produceTypeMask, out int produceTypeIndex)
        {
            produceTypeIndex = (int)ProducibleUnit.Worker;
            if (produceTypeMask == null || produceTypeMask.Length == 0)
            {
                return false;
            }

            // Prefer Worker for stable economy baseline, then first available.
            if ((int)ProducibleUnit.Worker < produceTypeMask.Length && produceTypeMask[(int)ProducibleUnit.Worker])
            {
                produceTypeIndex = (int)ProducibleUnit.Worker;
                return true;
            }

            for (int i = 0; i < produceTypeMask.Length; i++)
            {
                if (produceTypeMask[i])
                {
                    produceTypeIndex = i;
                    return true;
                }
            }

            return false;
        }

        private bool TryChooseAttackTargetLocal(Owner attackerOwner, GridPosition actorPos, bool[] attackMask, out int attackTargetLocal)
        {
            attackTargetLocal = 4;
            if (attackMask == null || attackMask.Length == 0)
            {
                return false;
            }

            int bestDistance = int.MaxValue;
            bool foundEnemy = false;
            int firstAvailable = -1;

            for (int localIndex = 0; localIndex < attackMask.Length; localIndex++)
            {
                if (!attackMask[localIndex])
                {
                    continue;
                }

                if (firstAvailable < 0)
                {
                    firstAvailable = localIndex;
                }

                GridPosition targetPos = ActionContractMappings.TryGetAttackTargetPosition(actorPos, localIndex, out GridPosition absoluteTarget)
                    ? absoluteTarget
                    : actorPos;
                UnitRuntime targetUnit = _gridManager.GetOccupant(targetPos);
                if (targetUnit == null || !targetUnit.IsAlive)
                {
                    continue;
                }

                if (targetUnit.Owner == attackerOwner || targetUnit.Owner == Owner.Neutral)
                {
                    continue;
                }

                int dist = actorPos.ChebyshevDistance(targetPos);
                if (!foundEnemy || dist < bestDistance)
                {
                    bestDistance = dist;
                    attackTargetLocal = localIndex;
                    foundEnemy = true;
                }
            }

            if (foundEnemy)
            {
                return true;
            }

            return false;
        }

        /// <summary>
        /// Heuristic policy simplification (MVP baseline only).
        /// Returns true when the player already owns at least one living Barracks.
        ///
        /// Used by <see cref="TrySelectWorkerAction"/> to suppress further Barracks-build attempts.
        /// This is NOT an authoritative engine rule — the runtime imposes no cap on Barracks count.
        /// The one-Barracks limit exists solely to keep the heuristic simple during self-play
        /// episodes and to avoid redundant Worker turns that delay combat-unit production.
        /// Relax or remove for multi-Barracks scenarios, curriculum stages, or BC-teacher training.
        /// </summary>
        private bool PlayerHasBarracks(Owner owner)
        {
            List<UnitRuntime> buildings = _unitRegistry?.GetBuildingsByOwner(owner);
            if (buildings == null)
                return false;
            for (int i = 0; i < buildings.Count; i++)
            {
                UnitRuntime b = buildings[i];
                if (b != null && b.IsAlive && b.Type == UnitType.Barracks)
                    return true;
            }
            return false;
        }

        private void EnsurePipeline()
        {
            ResolveReferences();

            if (_policyPipeline == null
                && _gridManager != null
                && _unitRegistry != null
                && _matchManager != null)
            {
                _policyPipeline = new MlPolicyPipelineFacade(
                    _gridManager,
                    _unitRegistry,
                    _resourceManager,
                    _matchManager,
                    _matchBootstrap);
            }
        }

        private void ResolveReferences()
        {
            _gridManager ??= GridManager.Instance;
            _unitRegistry ??= UnitRegistry.Instance;
            _resourceManager ??= ResourceManager.Instance;
            _matchManager ??= MatchManager.Instance;
            _matchBootstrap ??= MatchBootstrap.Instance;
        }

        private bool CanRun()
        {
            return _gridManager != null
                   && _unitRegistry != null
                   && _resourceManager != null
                   && _matchManager != null
                   && _policyPipeline != null;
        }
    }
}
