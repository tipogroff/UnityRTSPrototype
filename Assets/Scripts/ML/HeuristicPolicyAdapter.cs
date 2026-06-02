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

    public readonly struct HeuristicDecisionCycleEvaluation
    {
        public HeuristicDecisionCycleEvaluation(
            Owner playerId,
            bool controlEnabled,
            bool heuristicCalled,
            string controllerReason,
            string skipReason,
            int actorCandidates,
            int legalNonNoOpAvailableCount,
            int emittedNonNoOpCount,
            int acceptedCount,
            int rejectedCount,
            int canHarvestCount,
            int canReturnCount,
            int canProduceCount,
            int canMoveCount,
            int canAttackCount,
            int moveSelectedCount,
            int reverseMoveCount,
            bool oscillationDetected,
            int sameTwoCellLoopCount,
            int detourUsedCount,
            string detourReason,
            string goalType,
            string goalCell,
            int selectedMoveDirection,
            string selectedTargetCell,
            bool goalLocked = false,
            int goalLockTicksRemaining = 0,
            int reverseBlockedCount = 0,
            int recentCellPenaltyCount = 0,
            int reservedTargetConflictCount = 0,
            int bfsDetourUsedCount = 0,
            int bfsDetourFailedCount = 0,
            float moveScoreSelected = 0f,
            float moveScoreSecondBest = 0f,
            string moveSelectionReason = "none")
        {
            PlayerId = playerId;
            ControlEnabled = controlEnabled;
            HeuristicCalled = heuristicCalled;
            ControllerReason = controllerReason ?? string.Empty;
            SkipReason = skipReason ?? string.Empty;
            ActorCandidates = actorCandidates;
            LegalNonNoOpAvailableCount = legalNonNoOpAvailableCount;
            EmittedNonNoOpCount = emittedNonNoOpCount;
            AcceptedCount = acceptedCount;
            RejectedCount = rejectedCount;
            CanHarvestCount = canHarvestCount;
            CanReturnCount = canReturnCount;
            CanProduceCount = canProduceCount;
            CanMoveCount = canMoveCount;
            CanAttackCount = canAttackCount;
            MoveSelectedCount = moveSelectedCount;
            ReverseMoveCount = reverseMoveCount;
            OscillationDetected = oscillationDetected;
            SameTwoCellLoopCount = sameTwoCellLoopCount;
            DetourUsedCount = detourUsedCount;
            DetourReason = detourReason ?? string.Empty;
            GoalType = goalType ?? string.Empty;
            GoalCell = goalCell ?? string.Empty;
            SelectedMoveDirection = selectedMoveDirection;
            SelectedTargetCell = selectedTargetCell ?? string.Empty;
            GoalLocked = goalLocked;
            GoalLockTicksRemaining = goalLockTicksRemaining;
            ReverseBlockedCount = reverseBlockedCount;
            RecentCellPenaltyCount = recentCellPenaltyCount;
            ReservedTargetConflictCount = reservedTargetConflictCount;
            BfsDetourUsedCount = bfsDetourUsedCount;
            BfsDetourFailedCount = bfsDetourFailedCount;
            MoveScoreSelected = moveScoreSelected;
            MoveScoreSecondBest = moveScoreSecondBest;
            MoveSelectionReason = moveSelectionReason ?? string.Empty;
        }

        public Owner PlayerId { get; }
        public bool ControlEnabled { get; }
        public bool HeuristicCalled { get; }
        public string ControllerReason { get; }
        public string SkipReason { get; }
        public int ActorCandidates { get; }
        public int LegalNonNoOpAvailableCount { get; }
        public int EmittedNonNoOpCount { get; }
        public int AcceptedCount { get; }
        public int RejectedCount { get; }
        public int CanHarvestCount { get; }
        public int CanReturnCount { get; }
        public int CanProduceCount { get; }
        public int CanMoveCount { get; }
        public int CanAttackCount { get; }
        public int MoveSelectedCount { get; }
        public int ReverseMoveCount { get; }
        public bool OscillationDetected { get; }
        public int SameTwoCellLoopCount { get; }
        public int DetourUsedCount { get; }
        public string DetourReason { get; }
        public string GoalType { get; }
        public string GoalCell { get; }
        public int SelectedMoveDirection { get; }
        public string SelectedTargetCell { get; }
        public bool GoalLocked { get; }
        public int GoalLockTicksRemaining { get; }
        public int ReverseBlockedCount { get; }
        public int RecentCellPenaltyCount { get; }
        public int ReservedTargetConflictCount { get; }
        public int BfsDetourUsedCount { get; }
        public int BfsDetourFailedCount { get; }
        public float MoveScoreSelected { get; }
        public float MoveScoreSecondBest { get; }
        public string MoveSelectionReason { get; }
    }

    internal enum ScriptedGoalType
    {
        None = 0,
        Resource = 1,
        Base = 2,
        Enemy = 3,
        EnemyBase = 4
    }

    internal struct ScriptedUnitMoveMemory
    {
        public int LastStep;
        public GridPosition PreviousPosition;
        public GridPosition LastPosition;
        public Direction? LastMoveDirection;
        public GridPosition? CurrentGoal;
        public int SameGoalTicks;
        public int StuckTicks;
        public int GoalLockTicksRemaining;
        public int GoalUnreachableTicks;
        public int ReverseCooldownTicks;
        public int RecentHead;
        public int RecentCount;
        public GridPosition Recent0;
        public GridPosition Recent1;
        public GridPosition Recent2;
        public GridPosition Recent3;
        public GridPosition Recent4;
    }

    internal struct WorkerMoveSelectionTelemetry
    {
        public bool MoveSelected;
        public bool ReverseMove;
        public bool OscillationDetected;
        public bool DetourUsed;
        public string DetourReason;
        public ScriptedGoalType GoalType;
        public GridPosition? GoalCell;
        public Direction SelectedMoveDirection;
        public GridPosition? SelectedTargetCell;
        public bool GoalLocked;
        public int GoalLockTicksRemaining;
        public int ReverseBlockedCount;
        public int RecentCellPenaltyCount;
        public int ReservedTargetConflictCount;
        public bool BfsDetourUsed;
        public bool BfsDetourFailed;
        public float MoveScoreSelected;
        public float MoveScoreSecondBest;
        public string MoveSelectionReason;
    }

    internal struct Player2MoveCandidate
    {
        public Direction Direction;
        public GridPosition Target;
        public float Score;
        public bool Reverse;
        public bool Detour;
        public string Reason;
        public bool ReducesDistance;
        public int DistanceAfterMove;
    }

    internal struct Player2BfsNode
    {
        public GridPosition Position;
        public Direction FirstDirection;
        public GridPosition FirstTarget;
        public int Depth;
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
        [SerializeField] private bool _enablePlayer2DetourMoveFallback = true;
        [SerializeField] private int _player2AntiOscillationStuckThreshold = 2;
        [SerializeField] private int _player2GoalLockTicks = 8;
        [SerializeField] private int _player2ReverseCooldownTicks = 3;
        [SerializeField] private int _player2GoalUnreachableResetThreshold = 3;
        [SerializeField] private int _player2StuckGoalResetThreshold = 6;
        [SerializeField] private int _player2RecentCellMemorySize = 5;
        [SerializeField] private bool _enablePlayer2BfsDetour = true;
        [SerializeField] private int _player2BfsMaxDepth = 4;

        private MlPolicyPipelineFacade _policyPipeline;
        private readonly Dictionary<Owner, int> _decisionCycleByPlayer = new Dictionary<Owner, int>(2);

        private readonly List<UnitRuntime> _unitsScratch = new List<UnitRuntime>(64);
        private readonly StringBuilder _logBuilder = new StringBuilder(256);
        private readonly Dictionary<int, ScriptedUnitMoveMemory> _player2MoveMemoryByUnitKey =
            new Dictionary<int, ScriptedUnitMoveMemory>();
        private readonly HashSet<int> _activePlayer2UnitKeysScratch = new HashSet<int>();
        private readonly HashSet<GridPosition> _player2ReservedTargetsScratch = new HashSet<GridPosition>();
        private readonly Queue<Player2BfsNode> _player2BfsQueueScratch = new Queue<Player2BfsNode>();
        private readonly HashSet<GridPosition> _player2BfsVisitedScratch = new HashSet<GridPosition>();

        public event Action<HeuristicActionEvaluation> OnActionEvaluated;
        public event Action<HeuristicDecisionCycleEvaluation> OnDecisionCycleEvaluated;
        public Func<Owner, UnitActionType, bool> ActionSelectionFilter { get; set; }

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
            _player2MoveMemoryByUnitKey.Clear();
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
                EmitDecisionCycleEvaluation(new HeuristicDecisionCycleEvaluation(
                    Owner.Player1,
                    _player1Control == HeuristicControlMode.Heuristic,
                    heuristicCalled: false,
                    controllerReason: "pipeline-unavailable",
                    skipReason: "pipeline-unavailable",
                    actorCandidates: 0,
                    legalNonNoOpAvailableCount: 0,
                    emittedNonNoOpCount: 0,
                    acceptedCount: 0,
                    rejectedCount: 0,
                    canHarvestCount: 0,
                    canReturnCount: 0,
                    canProduceCount: 0,
                    canMoveCount: 0,
                    canAttackCount: 0,
                    moveSelectedCount: 0,
                    reverseMoveCount: 0,
                    oscillationDetected: false,
                    sameTwoCellLoopCount: 0,
                    detourUsedCount: 0,
                    detourReason: "none",
                    goalType: "None",
                    goalCell: "none",
                    selectedMoveDirection: -1,
                    selectedTargetCell: "none"));
                EmitDecisionCycleEvaluation(new HeuristicDecisionCycleEvaluation(
                    Owner.Player2,
                    _player2Control == HeuristicControlMode.Heuristic,
                    heuristicCalled: false,
                    controllerReason: "pipeline-unavailable",
                    skipReason: "pipeline-unavailable",
                    actorCandidates: 0,
                    legalNonNoOpAvailableCount: 0,
                    emittedNonNoOpCount: 0,
                    acceptedCount: 0,
                    rejectedCount: 0,
                    canHarvestCount: 0,
                    canReturnCount: 0,
                    canProduceCount: 0,
                    canMoveCount: 0,
                    canAttackCount: 0,
                    moveSelectedCount: 0,
                    reverseMoveCount: 0,
                    oscillationDetected: false,
                    sameTwoCellLoopCount: 0,
                    detourUsedCount: 0,
                    detourReason: "none",
                    goalType: "None",
                    goalCell: "none",
                    selectedMoveDirection: -1,
                    selectedTargetCell: "none"));
                Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.HeuristicDecision, perfStart);
                return (0, 0);
            }

            PrunePlayer2MoveMemory();

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
                EmitDecisionCycleEvaluation(new HeuristicDecisionCycleEvaluation(
                    Owner.Player1,
                    controlEnabled: true,
                    heuristicCalled: true,
                    controllerReason: "enabled",
                    skipReason: p1Result.skipReason,
                    actorCandidates: p1Result.actorCandidates,
                    legalNonNoOpAvailableCount: p1Result.legalNonNoOpAvailable,
                    emittedNonNoOpCount: p1Result.emittedNonNoOp,
                    acceptedCount: p1Result.accepted,
                    rejectedCount: p1Result.rejected,
                    canHarvestCount: p1Result.canHarvest,
                    canReturnCount: p1Result.canReturn,
                    canProduceCount: p1Result.canProduce,
                    canMoveCount: p1Result.canMove,
                    canAttackCount: p1Result.canAttack,
                    moveSelectedCount: p1Result.moveSelectedCount,
                    reverseMoveCount: p1Result.reverseMoveCount,
                    oscillationDetected: p1Result.oscillationDetected,
                    sameTwoCellLoopCount: p1Result.sameTwoCellLoopCount,
                    detourUsedCount: p1Result.detourUsedCount,
                    detourReason: p1Result.detourReason,
                    goalType: p1Result.goalType,
                    goalCell: p1Result.goalCell,
                    selectedMoveDirection: p1Result.selectedMoveDirection,
                    selectedTargetCell: p1Result.selectedTargetCell,
                    goalLocked: p1Result.goalLocked,
                    goalLockTicksRemaining: p1Result.goalLockTicksRemaining,
                    reverseBlockedCount: p1Result.reverseBlockedCount,
                    recentCellPenaltyCount: p1Result.recentCellPenaltyCount,
                    reservedTargetConflictCount: p1Result.reservedTargetConflictCount,
                    bfsDetourUsedCount: p1Result.bfsDetourUsedCount,
                    bfsDetourFailedCount: p1Result.bfsDetourFailedCount,
                    moveScoreSelected: p1Result.moveScoreSelected,
                    moveScoreSecondBest: p1Result.moveScoreSecondBest,
                    moveSelectionReason: p1Result.moveSelectionReason));
            }
            else
            {
                EmitDecisionCycleEvaluation(new HeuristicDecisionCycleEvaluation(
                    Owner.Player1,
                    controlEnabled: false,
                    heuristicCalled: false,
                    controllerReason: "control-mode-idle",
                    skipReason: "control-mode-idle",
                    actorCandidates: 0,
                    legalNonNoOpAvailableCount: 0,
                    emittedNonNoOpCount: 0,
                    acceptedCount: 0,
                    rejectedCount: 0,
                    canHarvestCount: 0,
                    canReturnCount: 0,
                    canProduceCount: 0,
                    canMoveCount: 0,
                        canAttackCount: 0,
                        moveSelectedCount: 0,
                        reverseMoveCount: 0,
                        oscillationDetected: false,
                        sameTwoCellLoopCount: 0,
                        detourUsedCount: 0,
                        detourReason: "none",
                        goalType: "None",
                        goalCell: "none",
                        selectedMoveDirection: -1,
                        selectedTargetCell: "none"));
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
                EmitDecisionCycleEvaluation(new HeuristicDecisionCycleEvaluation(
                    Owner.Player2,
                    controlEnabled: true,
                    heuristicCalled: true,
                    controllerReason: "enabled",
                    skipReason: p2Result.skipReason,
                    actorCandidates: p2Result.actorCandidates,
                    legalNonNoOpAvailableCount: p2Result.legalNonNoOpAvailable,
                    emittedNonNoOpCount: p2Result.emittedNonNoOp,
                    acceptedCount: p2Result.accepted,
                    rejectedCount: p2Result.rejected,
                    canHarvestCount: p2Result.canHarvest,
                    canReturnCount: p2Result.canReturn,
                    canProduceCount: p2Result.canProduce,
                    canMoveCount: p2Result.canMove,
                    canAttackCount: p2Result.canAttack,
                    moveSelectedCount: p2Result.moveSelectedCount,
                    reverseMoveCount: p2Result.reverseMoveCount,
                    oscillationDetected: p2Result.oscillationDetected,
                    sameTwoCellLoopCount: p2Result.sameTwoCellLoopCount,
                    detourUsedCount: p2Result.detourUsedCount,
                    detourReason: p2Result.detourReason,
                    goalType: p2Result.goalType,
                    goalCell: p2Result.goalCell,
                    selectedMoveDirection: p2Result.selectedMoveDirection,
                    selectedTargetCell: p2Result.selectedTargetCell,
                    goalLocked: p2Result.goalLocked,
                    goalLockTicksRemaining: p2Result.goalLockTicksRemaining,
                    reverseBlockedCount: p2Result.reverseBlockedCount,
                    recentCellPenaltyCount: p2Result.recentCellPenaltyCount,
                    reservedTargetConflictCount: p2Result.reservedTargetConflictCount,
                    bfsDetourUsedCount: p2Result.bfsDetourUsedCount,
                    bfsDetourFailedCount: p2Result.bfsDetourFailedCount,
                    moveScoreSelected: p2Result.moveScoreSelected,
                    moveScoreSecondBest: p2Result.moveScoreSecondBest,
                    moveSelectionReason: p2Result.moveSelectionReason));
            }
            else
            {
                EmitDecisionCycleEvaluation(new HeuristicDecisionCycleEvaluation(
                    Owner.Player2,
                    controlEnabled: false,
                    heuristicCalled: false,
                    controllerReason: "control-mode-idle",
                    skipReason: "control-mode-idle",
                    actorCandidates: 0,
                    legalNonNoOpAvailableCount: 0,
                    emittedNonNoOpCount: 0,
                    acceptedCount: 0,
                    rejectedCount: 0,
                    canHarvestCount: 0,
                    canReturnCount: 0,
                    canProduceCount: 0,
                    canMoveCount: 0,
                        canAttackCount: 0,
                        moveSelectedCount: 0,
                        reverseMoveCount: 0,
                        oscillationDetected: false,
                        sameTwoCellLoopCount: 0,
                        detourUsedCount: 0,
                        detourReason: "none",
                        goalType: "None",
                        goalCell: "none",
                        selectedMoveDirection: -1,
                        selectedTargetCell: "none"));
            }

            Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.HeuristicDecision, perfStart);
            return (accepted, rejected);
        }

        private (int accepted, int rejected, int actorCandidates, int legalNonNoOpAvailable, int emittedNonNoOp, int canHarvest, int canReturn, int canProduce, int canMove, int canAttack, int moveSelectedCount, int reverseMoveCount, bool oscillationDetected, int sameTwoCellLoopCount, int detourUsedCount, string detourReason, string goalType, string goalCell, int selectedMoveDirection, string selectedTargetCell, bool goalLocked, int goalLockTicksRemaining, int reverseBlockedCount, int recentCellPenaltyCount, int reservedTargetConflictCount, int bfsDetourUsedCount, int bfsDetourFailedCount, float moveScoreSelected, float moveScoreSecondBest, string moveSelectionReason, string skipReason) ExecutePlayerDecisionBatch(Owner playerId, bool canUseCanonical, in RlLoopStepInput stepInput)
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
            int actorCandidates = 0;
            int legalNonNoOpAvailable = 0;
            int emittedNonNoOp = 0;
            int canHarvest = 0;
            int canReturn = 0;
            int canProduce = 0;
            int canMove = 0;
            int canAttack = 0;
            int moveSelectedCount = 0;
            int reverseMoveCount = 0;
            bool oscillationDetected = false;
            int sameTwoCellLoopCount = 0;
            int detourUsedCount = 0;
            string detourReason = "none";
            string goalType = "None";
            string goalCell = "none";
            int selectedMoveDirection = -1;
            string selectedTargetCell = "none";
            bool goalLocked = false;
            int goalLockTicksRemaining = 0;
            int reverseBlockedCount = 0;
            int recentCellPenaltyCount = 0;
            int reservedTargetConflictCount = 0;
            int bfsDetourUsedCount = 0;
            int bfsDetourFailedCount = 0;
            float moveScoreSelected = 0f;
            float moveScoreSecondBest = 0f;
            string moveSelectionReason = "none";

            if (playerId == Owner.Player2)
            {
                _player2ReservedTargetsScratch.Clear();
            }

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

                actorCandidates++;
                if (HasAnyLegalNonNoOp(actorMask))
                {
                    legalNonNoOpAvailable++;
                }

                if (actorMask.IsActionTypeEnabled(UnitActionType.Harvest)) canHarvest++;
                if (actorMask.IsActionTypeEnabled(UnitActionType.Return)) canReturn++;
                if (actorMask.IsActionTypeEnabled(UnitActionType.Produce)) canProduce++;
                if (actorMask.IsActionTypeEnabled(UnitActionType.Move)) canMove++;
                if (actorMask.IsActionTypeEnabled(UnitActionType.Attack)) canAttack++;

                if (!TrySelectSingleActor(playerId, debugMask, actorIndex, out DebugActionSelection selection, out string reason, out WorkerMoveSelectionTelemetry moveTelemetry))
                {
                    continue;
                }

                if (selection.ActionType == ActionContract.ACTION_NOOP)
                {
                    continue;
                }

                emittedNonNoOp++;

                if (playerId == Owner.Player2 && moveTelemetry.MoveSelected)
                {
                    moveSelectedCount++;
                    if (moveTelemetry.ReverseMove)
                    {
                        reverseMoveCount++;
                    }

                    if (moveTelemetry.OscillationDetected)
                    {
                        oscillationDetected = true;
                        sameTwoCellLoopCount++;
                    }

                    if (moveTelemetry.DetourUsed)
                    {
                        detourUsedCount++;
                        detourReason = string.IsNullOrWhiteSpace(moveTelemetry.DetourReason)
                            ? "detour"
                            : moveTelemetry.DetourReason;
                    }

                    goalType = moveTelemetry.GoalType.ToString();
                    goalCell = moveTelemetry.GoalCell.HasValue ? moveTelemetry.GoalCell.Value.ToString() : "none";
                    selectedMoveDirection = (int)moveTelemetry.SelectedMoveDirection;
                    selectedTargetCell = moveTelemetry.SelectedTargetCell.HasValue
                        ? moveTelemetry.SelectedTargetCell.Value.ToString()
                        : "none";
                    goalLocked = moveTelemetry.GoalLocked;
                    goalLockTicksRemaining = moveTelemetry.GoalLockTicksRemaining;
                    reverseBlockedCount += moveTelemetry.ReverseBlockedCount;
                    recentCellPenaltyCount += moveTelemetry.RecentCellPenaltyCount;
                    reservedTargetConflictCount += moveTelemetry.ReservedTargetConflictCount;
                    if (moveTelemetry.BfsDetourUsed)
                    {
                        bfsDetourUsedCount++;
                    }

                    if (moveTelemetry.BfsDetourFailed)
                    {
                        bfsDetourFailedCount++;
                    }

                    moveScoreSelected = moveTelemetry.MoveScoreSelected;
                    moveScoreSecondBest = moveTelemetry.MoveScoreSecondBest;
                    moveSelectionReason = string.IsNullOrWhiteSpace(moveTelemetry.MoveSelectionReason)
                        ? "none"
                        : moveTelemetry.MoveSelectionReason;

                    if (moveTelemetry.SelectedTargetCell.HasValue)
                    {
                        _player2ReservedTargetsScratch.Add(moveTelemetry.SelectedTargetCell.Value);
                    }
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

            string skipReason = emittedNonNoOp > 0
                ? "action-emitted"
                : actorCandidates <= 0
                    ? "no-owned-actors"
                    : legalNonNoOpAvailable <= 0
                        ? "no-legal-non-noop"
                        : "heuristic-selected-noop-or-none";

            return (accepted, rejected, actorCandidates, legalNonNoOpAvailable, emittedNonNoOp, canHarvest, canReturn, canProduce, canMove, canAttack, moveSelectedCount, reverseMoveCount, oscillationDetected, sameTwoCellLoopCount, detourUsedCount, detourReason, goalType, goalCell, selectedMoveDirection, selectedTargetCell, goalLocked, goalLockTicksRemaining, reverseBlockedCount, recentCellPenaltyCount, reservedTargetConflictCount, bfsDetourUsedCount, bfsDetourFailedCount, moveScoreSelected, moveScoreSecondBest, moveSelectionReason, skipReason);
        }

        private static bool HasAnyLegalNonNoOp(ActorActionMask actorMask)
        {
            if (actorMask == null)
            {
                return false;
            }

            return actorMask.IsActionTypeEnabled(UnitActionType.Move)
                   || actorMask.IsActionTypeEnabled(UnitActionType.Harvest)
                   || actorMask.IsActionTypeEnabled(UnitActionType.Return)
                   || actorMask.IsActionTypeEnabled(UnitActionType.Produce)
                   || actorMask.IsActionTypeEnabled(UnitActionType.Attack);
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
                if (TrySelectSingleActor(playerId, debugMask, preferredActorIndexFlat.Value, out DebugActionSelection forcedSelection, out reason, out _))
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

                    if (pass == 0 && TrySelectWorkerAction(actorIndex, actor, actorMask, out DebugActionSelection workerSelection, out reason, out _))
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
            out string reason,
            out WorkerMoveSelectionTelemetry moveTelemetry)
        {
            selection = DebugActionSelection.NoActorNoOp;
            reason = "fallback:no-actor";
            moveTelemetry = default;

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

            if (TrySelectWorkerAction(actorIndex, actor, actorMask, out DebugActionSelection workerSelection, out reason, out moveTelemetry))
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
            out string reason,
            out WorkerMoveSelectionTelemetry moveTelemetry)
        {
            selection = DebugActionSelection.NoActorNoOp;
            reason = string.Empty;
            moveTelemetry = default;

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
                    ClearPlayer2MoveMemory(worker);
                    return true;
                }

                if (actorMask.IsActionTypeEnabled(UnitActionType.Move) &&
                    TryChooseMoveDirection(worker, actorMask.MoveDirectionMask, ScriptedGoalType.Base, out Direction moveToBase, out moveTelemetry))
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
                ClearPlayer2MoveMemory(worker);
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
                ClearPlayer2MoveMemory(worker);
                return true;
            }

            if (actorMask.IsActionTypeEnabled(UnitActionType.Move) &&
                TryChooseMoveDirection(worker, actorMask.MoveDirectionMask, ScriptedGoalType.Resource, out Direction moveToResource, out moveTelemetry))
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

        private bool TryChooseMoveDirection(
            UnitRuntime unit,
            bool[] moveMask,
            ScriptedGoalType goalType,
            out Direction direction,
            out WorkerMoveSelectionTelemetry telemetry)
        {
            telemetry = default;

            if (unit == null)
            {
                direction = Direction.North;
                return false;
            }

            if (unit.Owner != Owner.Player2)
            {
                switch (goalType)
                {
                    case ScriptedGoalType.Base:
                        return TryChooseMoveDirectionToNearestBase(unit.Owner, unit.GridPos, moveMask, out direction);
                    case ScriptedGoalType.Resource:
                        return TryChooseMoveDirectionToNearestResource(unit.GridPos, moveMask, out direction);
                    case ScriptedGoalType.Enemy:
                        return TryChooseMoveDirectionToNearestEnemy(unit.Owner, unit.GridPos, moveMask, out direction);
                    case ScriptedGoalType.EnemyBase:
                        return TryChooseMoveDirectionToEnemyBase(unit.Owner, unit.GridPos, moveMask, out direction);
                    default:
                        return TryChooseDirection(moveMask, out direction);
                }
            }

            GridPosition resolvedGoal = TryResolveGoalCell(unit.Owner, unit.GridPos, goalType, out bool hasGoal);
            GridPosition? goalCell = hasGoal ? resolvedGoal : (GridPosition?)null;
            if (!hasGoal && goalType != ScriptedGoalType.None)
            {
                goalType = ScriptedGoalType.None;
            }

            return TryChoosePlayer2MoveWithMemory(unit, moveMask, goalType, goalCell, out direction, out telemetry);
        }

        private GridPosition TryResolveGoalCell(Owner owner, GridPosition from, ScriptedGoalType goalType, out bool hasGoal)
        {
            hasGoal = false;
            switch (goalType)
            {
                case ScriptedGoalType.Base:
                    return TryGetNearestBasePosition(owner, from, out hasGoal);
                case ScriptedGoalType.Resource:
                    return TryGetNearestResourcePosition(from, out hasGoal);
                case ScriptedGoalType.Enemy:
                    return TryGetNearestEnemyPosition(owner, from, out hasGoal);
                case ScriptedGoalType.EnemyBase:
                    return TryGetNearestEnemyBasePosition(owner, from, out hasGoal);
                default:
                    return GridPosition.Zero;
            }
        }

        private bool TryChoosePlayer2MoveWithMemory(
            UnitRuntime unit,
            bool[] moveMask,
            ScriptedGoalType goalType,
            GridPosition? goalCell,
            out Direction direction,
            out WorkerMoveSelectionTelemetry telemetry)
        {
            direction = Direction.North;
            telemetry = default;

            if (moveMask == null)
            {
                return false;
            }

            int unitKey = GetScriptedUnitKey(unit);
            _player2MoveMemoryByUnitKey.TryGetValue(unitKey, out ScriptedUnitMoveMemory memory);
            InitializeRecentCells(ref memory, unit.GridPos);

            ScriptedGoalType effectiveGoalType = goalType;
            GridPosition? effectiveGoalCell = goalCell;
            bool goalLocked = false;
            ResolveGoalLock(unit, ref memory, ref effectiveGoalType, ref effectiveGoalCell, out goalLocked);

            int legalCount = 0;
            int reverseBlockedCount = 0;
            int recentCellPenaltyCount = 0;
            int reservedConflictCount = 0;
            bool hasStrictReducer = false;
            float bestScore = float.MinValue;
            float secondBestScore = float.MinValue;
            Player2MoveCandidate best = default;
            bool found = false;
            int currentDistance = effectiveGoalCell.HasValue
                ? unit.GridPos.ManhattanDistance(effectiveGoalCell.Value)
                : int.MaxValue;

            int reverseCooldown = Mathf.Max(0, memory.ReverseCooldownTicks);

            for (int i = 0; i < ActionContract.SIZE_DIRECTION; i++)
            {
                if (i >= moveMask.Length || !moveMask[i])
                {
                    continue;
                }

                legalCount++;
                Direction candidateDirection = (Direction)i;
                GridPosition candidateTarget = unit.GridPos.Neighbour(candidateDirection);

                bool isReverse = memory.LastMoveDirection.HasValue
                    && candidateDirection == Opposite(memory.LastMoveDirection.Value);
                bool reverseAllowed = !isReverse || ShouldAllowReverseMove(unit, memory, candidateTarget, legalCount);

                float score = 0f;
                string selectionReason = "scored-detour";
                bool reducesDistance = false;
                bool detour = true;
                int distanceAfterMove = int.MaxValue;

                if (effectiveGoalCell.HasValue)
                {
                    distanceAfterMove = candidateTarget.ManhattanDistance(effectiveGoalCell.Value);
                    if (distanceAfterMove < currentDistance)
                    {
                        score += 120f;
                        selectionReason = "strict-goal-progress";
                        reducesDistance = true;
                        detour = false;
                        hasStrictReducer = true;
                    }
                    else if (distanceAfterMove == currentDistance)
                    {
                        score += 20f;
                        selectionReason = "goal-equal-distance";
                    }
                    else
                    {
                        score -= 50f;
                        selectionReason = "goal-distance-increase";
                    }
                }
                else
                {
                    score += 5f;
                    selectionReason = "no-goal-detour";
                }

                if (candidateTarget == memory.PreviousPosition)
                {
                    score -= 260f;
                    recentCellPenaltyCount++;
                }

                int recentAge = GetRecentVisitAge(memory, candidateTarget);
                if (recentAge >= 0)
                {
                    if (recentAge <= 1)
                    {
                        score -= 140f;
                    }
                    else if (recentAge == 2)
                    {
                        score -= 80f;
                    }
                    else
                    {
                        score -= 45f;
                    }

                    recentCellPenaltyCount++;
                }
                else
                {
                    score += 15f;
                }

                if (_player2ReservedTargetsScratch.Contains(candidateTarget))
                {
                    score -= 180f;
                    reservedConflictCount++;
                    selectionReason = "reserved-target-conflict";
                }

                score -= ComputeReservedNeighbourPenalty(candidateTarget);

                if (isReverse)
                {
                    bool reverseCooldownActive = reverseCooldown > 0;
                    if (reverseCooldownActive && !reverseAllowed)
                    {
                        score -= 400f;
                        reverseBlockedCount++;
                        selectionReason = "reverse-blocked-cooldown";
                    }
                    else
                    {
                        score -= reverseCooldownActive ? 220f : 120f;
                        if (reverseAllowed)
                        {
                            selectionReason = "reverse-escape";
                        }
                    }
                }

                score += (ActionContract.SIZE_DIRECTION - i) * 0.01f;

                var candidate = new Player2MoveCandidate
                {
                    Direction = candidateDirection,
                    Target = candidateTarget,
                    Score = score,
                    Reverse = isReverse,
                    Detour = detour,
                    Reason = selectionReason,
                    ReducesDistance = reducesDistance,
                    DistanceAfterMove = distanceAfterMove,
                };

                if (!found || candidate.Score > bestScore)
                {
                    secondBestScore = bestScore;
                    bestScore = candidate.Score;
                    best = candidate;
                    found = true;
                }
                else if (candidate.Score > secondBestScore)
                {
                    secondBestScore = candidate.Score;
                }
            }

            bool bfsDetourUsed = false;
            bool bfsDetourFailed = false;
            if (found && !hasStrictReducer && effectiveGoalCell.HasValue && _enablePlayer2BfsDetour)
            {
                if (TryFindBfsDetour(unit, moveMask, effectiveGoalCell.Value, out Direction bfsDirection, out GridPosition bfsTarget))
                {
                    best = new Player2MoveCandidate
                    {
                        Direction = bfsDirection,
                        Target = bfsTarget,
                        Score = best.Score + 40f,
                        Reverse = memory.LastMoveDirection.HasValue && bfsDirection == Opposite(memory.LastMoveDirection.Value),
                        Detour = true,
                        Reason = "bfs-detour",
                        ReducesDistance = bfsTarget.ManhattanDistance(effectiveGoalCell.Value) < currentDistance,
                        DistanceAfterMove = bfsTarget.ManhattanDistance(effectiveGoalCell.Value),
                    };
                    bestScore = best.Score;
                    bfsDetourUsed = true;
                }
                else
                {
                    bfsDetourFailed = true;
                }
            }

            if (!found)
            {
                return false;
            }

            direction = best.Direction;
            telemetry.MoveSelected = true;
            telemetry.ReverseMove = best.Reverse;
            telemetry.OscillationDetected = best.Target == memory.PreviousPosition && memory.LastPosition == unit.GridPos;
            telemetry.DetourUsed = best.Detour;
            telemetry.DetourReason = string.IsNullOrWhiteSpace(best.Reason) ? "none" : best.Reason;
            telemetry.GoalType = effectiveGoalType;
            telemetry.GoalCell = effectiveGoalCell;
            telemetry.SelectedMoveDirection = best.Direction;
            telemetry.SelectedTargetCell = best.Target;
            telemetry.GoalLocked = goalLocked;
            telemetry.GoalLockTicksRemaining = memory.GoalLockTicksRemaining;
            telemetry.ReverseBlockedCount = reverseBlockedCount;
            telemetry.RecentCellPenaltyCount = recentCellPenaltyCount;
            telemetry.ReservedTargetConflictCount = reservedConflictCount;
            telemetry.BfsDetourUsed = bfsDetourUsed;
            telemetry.BfsDetourFailed = bfsDetourFailed;
            telemetry.MoveScoreSelected = bestScore;
            telemetry.MoveScoreSecondBest = secondBestScore > float.MinValue ? secondBestScore : bestScore;
            telemetry.MoveSelectionReason = best.Reason;

            int currentStep = _matchManager != null ? _matchManager.Step : -1;
            ScriptedUnitMoveMemory updated = memory;
            updated.LastStep = currentStep;
            updated.PreviousPosition = unit.GridPos;
            updated.LastPosition = best.Target;
            updated.LastMoveDirection = best.Direction;
            updated.ReverseCooldownTicks = Mathf.Max(0, _player2ReverseCooldownTicks);

            if (effectiveGoalCell.HasValue)
            {
                if (updated.CurrentGoal.HasValue && updated.CurrentGoal.Value == effectiveGoalCell.Value)
                {
                    updated.SameGoalTicks = memory.SameGoalTicks + 1;
                }
                else
                {
                    updated.SameGoalTicks = 0;
                }

                updated.CurrentGoal = effectiveGoalCell;
                if (best.ReducesDistance)
                {
                    updated.GoalUnreachableTicks = 0;
                }
                else
                {
                    updated.GoalUnreachableTicks = memory.GoalUnreachableTicks + 1;
                }
            }
            else
            {
                updated.CurrentGoal = null;
                updated.SameGoalTicks = 0;
                updated.GoalUnreachableTicks = 0;
                updated.GoalLockTicksRemaining = 0;
            }

            updated.StuckTicks = telemetry.OscillationDetected || telemetry.DetourUsed
                ? memory.StuckTicks + 1
                : 0;

            if (updated.GoalLockTicksRemaining > 0)
            {
                updated.GoalLockTicksRemaining--;
            }

            if (updated.GoalUnreachableTicks >= Mathf.Max(1, _player2GoalUnreachableResetThreshold)
                || updated.StuckTicks >= Mathf.Max(2, _player2StuckGoalResetThreshold)
                || !IsGoalStillValid(unit.Owner, effectiveGoalType, updated.CurrentGoal))
            {
                updated.CurrentGoal = null;
                updated.GoalLockTicksRemaining = 0;
                updated.GoalUnreachableTicks = 0;
                updated.SameGoalTicks = 0;
            }

            if (updated.ReverseCooldownTicks > 0)
            {
                updated.ReverseCooldownTicks--;
            }

            AddRecentCell(ref updated, best.Target);
            _player2MoveMemoryByUnitKey[unitKey] = updated;
            return true;
        }

        private void ResolveGoalLock(
            UnitRuntime unit,
            ref ScriptedUnitMoveMemory memory,
            ref ScriptedGoalType requestedGoalType,
            ref GridPosition? requestedGoalCell,
            out bool goalLocked)
        {
            goalLocked = false;

            if (memory.CurrentGoal.HasValue && IsGoalStillValid(unit.Owner, requestedGoalType, memory.CurrentGoal))
            {
                if (memory.GoalLockTicksRemaining > 0 || memory.SameGoalTicks > 0)
                {
                    requestedGoalCell = memory.CurrentGoal;
                    goalLocked = true;
                    return;
                }
            }

            if (requestedGoalCell.HasValue && IsGoalStillValid(unit.Owner, requestedGoalType, requestedGoalCell))
            {
                if (!memory.CurrentGoal.HasValue || memory.CurrentGoal.Value != requestedGoalCell.Value)
                {
                    memory.GoalLockTicksRemaining = Mathf.Clamp(_player2GoalLockTicks, 5, 10);
                    memory.GoalUnreachableTicks = 0;
                    memory.SameGoalTicks = 0;
                }

                memory.CurrentGoal = requestedGoalCell;
                return;
            }

            requestedGoalType = ScriptedGoalType.None;
            requestedGoalCell = null;
            memory.CurrentGoal = null;
            memory.GoalLockTicksRemaining = 0;
            memory.GoalUnreachableTicks = 0;
            memory.SameGoalTicks = 0;
        }

        private bool IsGoalStillValid(Owner owner, ScriptedGoalType goalType, GridPosition? goalCell)
        {
            if (!goalCell.HasValue)
            {
                return false;
            }

            GridPosition goal = goalCell.Value;
            if (!_gridManager.IsInside(goal))
            {
                return false;
            }

            switch (goalType)
            {
                case ScriptedGoalType.Base:
                    {
                        UnitRuntime occupant = _gridManager.GetOccupant(goal);
                        return occupant != null && occupant.IsAlive && occupant.Owner == owner && occupant.Type == UnitType.Base;
                    }
                case ScriptedGoalType.Resource:
                    {
                        ResourceNode node = _resourceManager?.GetResourceNode(goal);
                        return node != null && !node.IsExhausted;
                    }
                case ScriptedGoalType.Enemy:
                case ScriptedGoalType.EnemyBase:
                    {
                        UnitRuntime occupant = _gridManager.GetOccupant(goal);
                        return occupant != null && occupant.IsAlive && occupant.Owner != owner && occupant.Owner != Owner.Neutral;
                    }
                default:
                    return true;
            }
        }

        private bool ShouldAllowReverseMove(UnitRuntime unit, ScriptedUnitMoveMemory memory, GridPosition reverseTarget, int legalCount)
        {
            if (legalCount <= 1)
            {
                return true;
            }

            if (memory.StuckTicks >= Mathf.Max(1, _player2AntiOscillationStuckThreshold))
            {
                return true;
            }

            return HasImmediateUsefulActionAtTarget(unit, reverseTarget);
        }

        private bool HasImmediateUsefulActionAtTarget(UnitRuntime unit, GridPosition target)
        {
            if (unit == null)
            {
                return false;
            }

            for (int i = 0; i < ActionContract.SIZE_DIRECTION; i++)
            {
                Direction dir = (Direction)i;
                GridPosition adjacent = target.Neighbour(dir);

                UnitRuntime adjacentUnit = _gridManager.GetOccupant(adjacent);
                if (adjacentUnit != null && adjacentUnit.IsAlive && adjacentUnit.Owner != unit.Owner && adjacentUnit.Owner != Owner.Neutral)
                {
                    return true;
                }

                if (unit.Type == UnitType.Worker)
                {
                    if (unit.CarriedResources > 0 && adjacentUnit != null && adjacentUnit.Owner == unit.Owner && adjacentUnit.Type == UnitType.Base)
                    {
                        return true;
                    }

                    if (unit.CarriedResources <= 0)
                    {
                        ResourceNode node = _resourceManager?.GetResourceNode(adjacent);
                        if (node != null && !node.IsExhausted)
                        {
                            return true;
                        }
                    }
                }
            }

            return false;
        }

        private float ComputeReservedNeighbourPenalty(GridPosition target)
        {
            float penalty = 0f;
            foreach (GridPosition reserved in _player2ReservedTargetsScratch)
            {
                int chebyshev = target.ChebyshevDistance(reserved);
                if (chebyshev == 0)
                {
                    continue;
                }

                if (chebyshev == 1)
                {
                    penalty += 30f;
                }
            }

            return penalty;
        }

        private int GetRecentVisitAge(ScriptedUnitMoveMemory memory, GridPosition target)
        {
            int recentWindow = Mathf.Clamp(_player2RecentCellMemorySize, 3, 5);
            int count = Mathf.Min(memory.RecentCount, 5);
            int maxToCheck = Mathf.Min(count, recentWindow);
            for (int age = 0; age < maxToCheck; age++)
            {
                int index = (memory.RecentHead - 1 - age + 5) % 5;
                if (GetRecentCellByIndex(memory, index) == target)
                {
                    return age;
                }
            }

            return -1;
        }

        private void InitializeRecentCells(ref ScriptedUnitMoveMemory memory, GridPosition currentPos)
        {
            if (memory.RecentCount > 0)
            {
                return;
            }

            AddRecentCell(ref memory, currentPos);
        }

        private void AddRecentCell(ref ScriptedUnitMoveMemory memory, GridPosition pos)
        {
            int index = memory.RecentHead;
            SetRecentCellByIndex(ref memory, index, pos);
            memory.RecentHead = (index + 1) % 5;
            if (memory.RecentCount < 5)
            {
                memory.RecentCount++;
            }
        }

        private static GridPosition GetRecentCellByIndex(ScriptedUnitMoveMemory memory, int index)
        {
            switch (index)
            {
                case 0: return memory.Recent0;
                case 1: return memory.Recent1;
                case 2: return memory.Recent2;
                case 3: return memory.Recent3;
                default: return memory.Recent4;
            }
        }

        private static void SetRecentCellByIndex(ref ScriptedUnitMoveMemory memory, int index, GridPosition value)
        {
            switch (index)
            {
                case 0: memory.Recent0 = value; break;
                case 1: memory.Recent1 = value; break;
                case 2: memory.Recent2 = value; break;
                case 3: memory.Recent3 = value; break;
                default: memory.Recent4 = value; break;
            }
        }

        private bool TryFindBfsDetour(UnitRuntime unit, bool[] moveMask, GridPosition goal, out Direction direction, out GridPosition target)
        {
            direction = Direction.North;
            target = unit.GridPos;

            int currentDistance = unit.GridPos.ManhattanDistance(goal);
            int maxDepth = Mathf.Clamp(_player2BfsMaxDepth, 3, 5);

            _player2BfsQueueScratch.Clear();
            _player2BfsVisitedScratch.Clear();

            for (int i = 0; i < ActionContract.SIZE_DIRECTION; i++)
            {
                if (i >= moveMask.Length || !moveMask[i])
                {
                    continue;
                }

                Direction firstDirection = (Direction)i;
                GridPosition firstTarget = unit.GridPos.Neighbour(firstDirection);
                if (!IsTraversableForBfs(firstTarget, unit.GridPos))
                {
                    continue;
                }

                if (_player2ReservedTargetsScratch.Contains(firstTarget))
                {
                    continue;
                }

                _player2BfsQueueScratch.Enqueue(new Player2BfsNode
                {
                    Position = firstTarget,
                    FirstDirection = firstDirection,
                    FirstTarget = firstTarget,
                    Depth = 1,
                });
                _player2BfsVisitedScratch.Add(firstTarget);
            }

            while (_player2BfsQueueScratch.Count > 0)
            {
                Player2BfsNode node = _player2BfsQueueScratch.Dequeue();
                if (node.Position.ManhattanDistance(goal) < currentDistance)
                {
                    direction = node.FirstDirection;
                    target = node.FirstTarget;
                    return true;
                }

                if (node.Depth >= maxDepth)
                {
                    continue;
                }

                for (int i = 0; i < ActionContract.SIZE_DIRECTION; i++)
                {
                    GridPosition next = node.Position.Neighbour((Direction)i);
                    if (!_player2BfsVisitedScratch.Add(next))
                    {
                        continue;
                    }

                    if (!IsTraversableForBfs(next, unit.GridPos))
                    {
                        continue;
                    }

                    if (_player2ReservedTargetsScratch.Contains(next))
                    {
                        continue;
                    }

                    _player2BfsQueueScratch.Enqueue(new Player2BfsNode
                    {
                        Position = next,
                        FirstDirection = node.FirstDirection,
                        FirstTarget = node.FirstTarget,
                        Depth = node.Depth + 1,
                    });
                }
            }

            return false;
        }

        private bool IsTraversableForBfs(GridPosition pos, GridPosition origin)
        {
            if (!_gridManager.IsInside(pos))
            {
                return false;
            }

            UnitRuntime occupant = _gridManager.GetOccupant(pos);
            return occupant == null || pos == origin;
        }

        private void PrunePlayer2MoveMemory()
        {
            _activePlayer2UnitKeysScratch.Clear();

            if (_unitRegistry != null)
            {
                IReadOnlyList<UnitRuntime> units = _unitRegistry.GetUnitsByOwner(Owner.Player2);
                if (units != null)
                {
                    for (int i = 0; i < units.Count; i++)
                    {
                        UnitRuntime unit = units[i];
                        if (unit == null || !unit.IsAlive)
                        {
                            continue;
                        }

                        _activePlayer2UnitKeysScratch.Add(GetScriptedUnitKey(unit));
                    }
                }
            }

            if (_player2MoveMemoryByUnitKey.Count == 0)
            {
                return;
            }

            _unitsScratch.Clear();
            var keys = new List<int>(_player2MoveMemoryByUnitKey.Keys);
            for (int i = 0; i < keys.Count; i++)
            {
                int key = keys[i];
                if (!_activePlayer2UnitKeysScratch.Contains(key))
                {
                    _player2MoveMemoryByUnitKey.Remove(key);
                }
            }
        }

        private static int GetScriptedUnitKey(UnitRuntime unit)
        {
            return unit != null ? unit.GetInstanceID() : 0;
        }

        private void ClearPlayer2MoveMemory(UnitRuntime unit)
        {
            if (unit == null || unit.Owner != Owner.Player2)
            {
                return;
            }

            _player2MoveMemoryByUnitKey.Remove(GetScriptedUnitKey(unit));
        }

        private static Direction Opposite(Direction direction)
        {
            switch (direction)
            {
                case Direction.North:
                    return Direction.South;
                case Direction.South:
                    return Direction.North;
                case Direction.East:
                    return Direction.West;
                case Direction.West:
                    return Direction.East;
                default:
                    return Direction.North;
            }
        }

        private GridPosition TryGetNearestBasePosition(Owner owner, GridPosition from, out bool hasGoal)
        {
            hasGoal = false;
            _unitsScratch.Clear();
            _unitsScratch.AddRange(_unitRegistry.GetBuildingsByOwner(owner));

            GridPosition nearestBasePos = from;
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
                    nearestBasePos = building.GridPos;
                    hasGoal = true;
                }
            }

            return nearestBasePos;
        }

        private GridPosition TryGetNearestResourcePosition(GridPosition from, out bool hasGoal)
        {
            hasGoal = false;
            GridPosition nearestResourcePos = from;
            IEnumerable<ResourceNode> resources = _resourceManager?.GetAllResourceNodes();
            if (resources == null)
            {
                return nearestResourcePos;
            }

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
                    hasGoal = true;
                }
            }

            return nearestResourcePos;
        }

        private GridPosition TryGetNearestEnemyPosition(Owner owner, GridPosition from, out bool hasGoal)
        {
            hasGoal = false;
            GridPosition nearestEnemyPos = from;
            IReadOnlyList<UnitRuntime> allUnits = _unitRegistry.GetAllUnits();
            if (allUnits == null || allUnits.Count == 0)
            {
                return nearestEnemyPos;
            }

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
                    hasGoal = true;
                }
            }

            return nearestEnemyPos;
        }

        private GridPosition TryGetNearestEnemyBasePosition(Owner owner, GridPosition from, out bool hasGoal)
        {
            hasGoal = false;
            GridPosition nearestEnemyBase = from;

            Owner enemyOwner = owner == Owner.Player1
                ? Owner.Player2
                : owner == Owner.Player2
                    ? Owner.Player1
                    : Owner.Neutral;

            if (enemyOwner == Owner.Neutral)
            {
                return nearestEnemyBase;
            }

            _unitsScratch.Clear();
            _unitsScratch.AddRange(_unitRegistry.GetBuildingsByOwner(enemyOwner));

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
                    hasGoal = true;
                }
            }

            return nearestEnemyBase;
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
            ClearPlayer2MoveMemory(building);
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

            if (actorMask.IsActionTypeEnabled(UnitActionType.Attack)
                && IsActionAllowed(playerId, UnitActionType.Attack)
                &&
                TryChooseAttackTargetLocal(playerId, combatUnit.GridPos, actorMask.AttackTargetLocalMask, out int attackLocal))
            {
                selection = new DebugActionSelection(
                    actorIndex,
                    ActionContract.ACTION_ATTACK,
                    ActionContract.DIR_NORTH,
                    HeuristicV2ActionDefaults.WorkerProduceIndex,
                    attackLocal);
                reason = $"combat:attack local={attackLocal}";
                ClearPlayer2MoveMemory(combatUnit);
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

        private bool IsActionAllowed(Owner owner, UnitActionType actionType)
        {
            Func<Owner, UnitActionType, bool> filter = ActionSelectionFilter;
            if (filter == null)
            {
                return true;
            }

            try
            {
                return filter(owner, actionType);
            }
            catch (Exception ex)
            {
                Debug.LogWarning("[HeuristicPolicyAdapter] ActionSelectionFilter failed: " + ex.Message);
                return true;
            }
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

        private bool TryChooseFallbackDirection(bool[] directionMask, out Direction direction)
        {
            // Keep fallback deterministic and cheap: first legal move in mask order.
            return TryChooseDirection(directionMask, out direction);
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

        private void EmitDecisionCycleEvaluation(HeuristicDecisionCycleEvaluation evaluation)
        {
            OnDecisionCycleEvaluated?.Invoke(evaluation);
        }
    }
}
