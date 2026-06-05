// MatchManager.cs — central step-based coordinator of a single match.

using System;
using System.Collections.Generic;
using UnityEngine;
using RTS.Core;
using RTS.Presentation;
using Unity.Profiling;

namespace RTS.Gameplay
{
    public enum MatchPhase
    {
        Idle,
        Running,
        Ended
    }

    public readonly struct MatchCommand
    {
        public MatchCommand(
            Owner owner,
            GridPosition unitPosition,
            UnitActionType actionType,
            Direction direction = Direction.North,
            ProducibleUnit produceUnitType = ProducibleUnit.Worker,
            GridPosition attackTarget = default,
            bool hasAttackTarget = false)
        {
            Owner = owner;
            UnitPosition = unitPosition;
            ActionType = actionType;
            Direction = direction;
            ProduceUnitType = produceUnitType;
            AttackTarget = attackTarget;
            HasAttackTarget = hasAttackTarget;
        }

        public Owner Owner { get; }
        public GridPosition UnitPosition { get; }
        public UnitActionType ActionType { get; }
        public Direction Direction { get; }
        public ProducibleUnit ProduceUnitType { get; }
        public GridPosition AttackTarget { get; }
        public bool HasAttackTarget { get; }
    }

    public readonly struct MatchStateSnapshot
    {
        public MatchStateSnapshot(
            MatchPhase phase,
            int step,
            int maxSteps,
            Owner winner,
            MatchEndReason endReason,
            int player1Resources,
            int player2Resources,
            int player1UnitCount,
            int player2UnitCount,
            int player1BaseCount,
            int player2BaseCount,
            int pendingCommands)
        {
            Phase = phase;
            Step = step;
            MaxSteps = maxSteps;
            Winner = winner;
            EndReason = endReason;
            Player1Resources = player1Resources;
            Player2Resources = player2Resources;
            Player1UnitCount = player1UnitCount;
            Player2UnitCount = player2UnitCount;
            Player1BaseCount = player1BaseCount;
            Player2BaseCount = player2BaseCount;
            PendingCommands = pendingCommands;
        }

        public MatchPhase Phase { get; }
        public int Step { get; }
        public int MaxSteps { get; }
        public Owner Winner { get; }
        public MatchEndReason EndReason { get; }
        public int Player1Resources { get; }
        public int Player2Resources { get; }
        public int Player1UnitCount { get; }
        public int Player2UnitCount { get; }
        public int Player1BaseCount { get; }
        public int Player2BaseCount { get; }
        public int PendingCommands { get; }
    }

    public readonly struct PendingMoveReservation
    {
        public PendingMoveReservation(Owner owner, GridPosition source, GridPosition target, Direction direction, string sourceType)
        {
            Owner = owner;
            Source = source;
            Target = target;
            Direction = direction;
            SourceType = sourceType ?? string.Empty;
        }

        public Owner Owner { get; }
        public GridPosition Source { get; }
        public GridPosition Target { get; }
        public Direction Direction { get; }
        public string SourceType { get; }
    }

    public readonly struct MatchCommandRejectionDiagnostics
    {
        public MatchCommandRejectionDiagnostics(
            bool hasDiagnostics,
            string rejectCallsite,
            string rejectReasonRaw,
            string rejectReasonNormalized,
            UnitActionType actionType,
            Direction moveDir,
            int sourceCellFromCommand,
            int sourceXFromCommand,
            int sourceYFromCommand,
            int targetCellFromCommand,
            int targetXFromCommand,
            int targetYFromCommand,
            string unitId,
            string unitOwner,
            string unitType,
            int unitPositionXAtReject,
            int unitPositionYAtReject,
            int unitCellAtReject,
            bool occupantExistsAtTarget,
            string occupantIdAtTarget,
            string occupantOwnerAtTarget,
            string occupantTypeAtTarget,
            int occupantXAtTarget,
            int occupantYAtTarget,
            int occupantCellAtTarget,
            int occupancyLookupKeyCell,
            int occupancyLookupKeyX,
            int occupancyLookupKeyY,
            bool tryGetOccupantResult,
            bool occupantRefExists,
            int occupantInstanceId,
            string occupantName,
            int occupantLogicalX,
            int occupantLogicalY,
            int occupantLogicalCell,
            bool occupantLogicalCellRoundtripOk,
            bool occupantLogicalCellMatchesLookupKey,
            bool occupantLogicalCellMatchesTargetCell,
            float occupantTransformX,
            float occupantTransformY,
            int occupantVisualGridX,
            int occupantVisualGridY,
            int occupantVisualCell,
            bool occupantVisualCellMatchesLogicalCell,
            bool gridLookupByTargetReturnsOccupant,
            bool gridLookupByOccupantLogicalCellReturnsSameOccupant,
            bool gridLookupByOccupantVisualCellReturnsSameOccupant,
            bool occupancyMapKeyMatchesOccupantLogicalPosition,
            int occupantCellReportedPrevious,
            string occupancyLookupMethod,
            string occupancyLookupSource,
            bool targetInBoundsAtReject,
            bool targetPassableAtReject,
            bool targetOccupiedAtReject,
            bool targetOccupiedByRuntimeLookup,
            bool directRuntimeTargetMatchesReconstructedTarget)
        {
            HasDiagnostics = hasDiagnostics;
            RejectCallsite = rejectCallsite ?? string.Empty;
            RejectReasonRaw = rejectReasonRaw ?? string.Empty;
            RejectReasonNormalized = rejectReasonNormalized ?? string.Empty;
            ActionType = actionType;
            MoveDir = moveDir;
            SourceCellFromCommand = sourceCellFromCommand;
            SourceXFromCommand = sourceXFromCommand;
            SourceYFromCommand = sourceYFromCommand;
            TargetCellFromCommand = targetCellFromCommand;
            TargetXFromCommand = targetXFromCommand;
            TargetYFromCommand = targetYFromCommand;
            UnitId = unitId ?? "NOT_EXPOSED";
            UnitOwner = unitOwner ?? "NOT_EXPOSED";
            UnitType = unitType ?? "NOT_EXPOSED";
            UnitPositionXAtReject = unitPositionXAtReject;
            UnitPositionYAtReject = unitPositionYAtReject;
            UnitCellAtReject = unitCellAtReject;
            OccupantExistsAtTarget = occupantExistsAtTarget;
            OccupantIdAtTarget = occupantIdAtTarget ?? "NOT_EXPOSED";
            OccupantOwnerAtTarget = occupantOwnerAtTarget ?? "NOT_EXPOSED";
            OccupantTypeAtTarget = occupantTypeAtTarget ?? "NOT_EXPOSED";
            OccupantXAtTarget = occupantXAtTarget;
            OccupantYAtTarget = occupantYAtTarget;
            OccupantCellAtTarget = occupantCellAtTarget;
            OccupancyLookupKeyCell = occupancyLookupKeyCell;
            OccupancyLookupKeyX = occupancyLookupKeyX;
            OccupancyLookupKeyY = occupancyLookupKeyY;
            TryGetOccupantResult = tryGetOccupantResult;
            OccupantRefExists = occupantRefExists;
            OccupantInstanceId = occupantInstanceId;
            OccupantName = occupantName ?? "NOT_EXPOSED";
            OccupantLogicalX = occupantLogicalX;
            OccupantLogicalY = occupantLogicalY;
            OccupantLogicalCell = occupantLogicalCell;
            OccupantLogicalCellRoundtripOk = occupantLogicalCellRoundtripOk;
            OccupantLogicalCellMatchesLookupKey = occupantLogicalCellMatchesLookupKey;
            OccupantLogicalCellMatchesTargetCell = occupantLogicalCellMatchesTargetCell;
            OccupantTransformX = occupantTransformX;
            OccupantTransformY = occupantTransformY;
            OccupantVisualGridX = occupantVisualGridX;
            OccupantVisualGridY = occupantVisualGridY;
            OccupantVisualCell = occupantVisualCell;
            OccupantVisualCellMatchesLogicalCell = occupantVisualCellMatchesLogicalCell;
            GridLookupByTargetReturnsOccupant = gridLookupByTargetReturnsOccupant;
            GridLookupByOccupantLogicalCellReturnsSameOccupant = gridLookupByOccupantLogicalCellReturnsSameOccupant;
            GridLookupByOccupantVisualCellReturnsSameOccupant = gridLookupByOccupantVisualCellReturnsSameOccupant;
            OccupancyMapKeyMatchesOccupantLogicalPosition = occupancyMapKeyMatchesOccupantLogicalPosition;
            OccupantCellReportedPrevious = occupantCellReportedPrevious;
            OccupancyLookupMethod = occupancyLookupMethod ?? string.Empty;
            OccupancyLookupSource = occupancyLookupSource ?? string.Empty;
            TargetInBoundsAtReject = targetInBoundsAtReject;
            TargetPassableAtReject = targetPassableAtReject;
            TargetOccupiedAtReject = targetOccupiedAtReject;
            TargetOccupiedByRuntimeLookup = targetOccupiedByRuntimeLookup;
            DirectRuntimeTargetMatchesReconstructedTarget = directRuntimeTargetMatchesReconstructedTarget;
        }

        public static MatchCommandRejectionDiagnostics None => new MatchCommandRejectionDiagnostics(
            false,
            string.Empty,
            string.Empty,
            string.Empty,
            UnitActionType.NoOp,
            Direction.North,
            -1,
            -1,
            -1,
            -1,
            -1,
            -1,
            "NOT_EXPOSED",
            "NOT_EXPOSED",
            "NOT_EXPOSED",
            -1,
            -1,
            -1,
            false,
            "NOT_EXPOSED",
            "NOT_EXPOSED",
            "NOT_EXPOSED",
            -1,
            -1,
            -1,
            -1,
            -1,
            -1,
            false,
            false,
            0,
            "NOT_EXPOSED",
            -1,
            -1,
            -1,
            false,
            false,
            false,
            float.NaN,
            float.NaN,
            -1,
            -1,
            -1,
            false,
            false,
            false,
            false,
            false,
            -1,
            string.Empty,
            string.Empty,
            false,
            false,
            false,
            false,
            false);

        public bool HasDiagnostics { get; }
        public string RejectCallsite { get; }
        public string RejectReasonRaw { get; }
        public string RejectReasonNormalized { get; }
        public UnitActionType ActionType { get; }
        public Direction MoveDir { get; }
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

    [DisallowMultipleComponent]
    public class MatchManager : MonoBehaviour
    {
        public static MatchManager Instance { get; private set; }

        [Header("Scene references")]
        [SerializeField] private GridManager _gridManager;
        [SerializeField] private UnitRegistry _unitRegistry;
        [SerializeField] private VictoryResolver _victoryResolver;
        [SerializeField] private MatchBootstrap _matchBootstrap;

        [Header("Debug")]
        [SerializeField] private bool _logStepEvents;
        [SerializeField] private bool _logHumanMoveDiagnostics;
        [SerializeField] private bool _logProductionDiagnostics;
        [SerializeField] private bool _logLifecycleDiagnostics;

        public MatchPhase Phase { get; private set; } = MatchPhase.Idle;
        public int Step { get; private set; }
        public int MaxSteps { get; private set; }
        public Owner Winner { get; private set; } = Owner.Neutral;
        public MatchEndReason EndReason { get; private set; } = MatchEndReason.None;
        public string EndReasonDetails { get; private set; } = string.Empty;

        public int AcceptedCommandsLastStep => _acceptedCommandsThisStep;
        public int InvalidCommandsLastStep => _invalidCommandsThisStep;
        public int TotalAcceptedCommands { get; private set; }
                public int LastCombatAttackersEvaluated => _combatResolver != null ? _combatResolver.LastAttackersEvaluated : 0;
        public int LastCombatTargetCellChecks => _combatResolver != null ? _combatResolver.LastTargetCellChecks : 0;
public int TotalInvalidCommands { get; private set; }

        private PlayerState[] _playerStates;
        private readonly int[] _resources = new int[2];

        private readonly List<MatchCommand> _pendingCommands = new List<MatchCommand>(256);
        private readonly List<ResolvedCommand> _movementCommands = new List<ResolvedCommand>(128);
        private readonly List<ResolvedCommand> _harvestDepositCommands = new List<ResolvedCommand>(128);
        private readonly List<ResolvedCommand> _productionCommands = new List<ResolvedCommand>(64);
        private readonly List<ResolvedCommand> _combatCommands = new List<ResolvedCommand>(64);
        private readonly Dictionary<UnitRuntime, MatchCommand> _lastAppliedCommandByUnit = new Dictionary<UnitRuntime, MatchCommand>(128);
        private readonly HashSet<UnitRuntime> _assignedUnitsScratch = new HashSet<UnitRuntime>();
        private readonly HashSet<UnitRuntime> _commandedAttackersScratch = new HashSet<UnitRuntime>();

        private int _acceptedCommandsThisStep;
        private int _invalidCommandsThisStep;
        private CombatResolver _combatResolver;

        private static readonly ProfilerMarker StepMatchMarker = new ProfilerMarker("MatchManager.StepMatch");
        private static readonly ProfilerMarker ProcessCommandPhaseMarker = new ProfilerMarker("MatchManager.ProcessCommandPhase");
        private static readonly ProfilerMarker MovementPhaseMarker = new ProfilerMarker("MatchManager.ExecuteMovementPhase");
        private static readonly ProfilerMarker ProductionPhaseMarker = new ProfilerMarker("MatchManager.ExecuteProductionPhase");
        private static readonly ProfilerMarker CombatPhaseMarker = new ProfilerMarker("MatchManager.ExecuteCombatPhase");

        public System.Action<Owner> OnMatchEnded;
        public System.Action<MatchResolution> OnMatchResolved;
        public System.Action<int> OnStepAdvanced;
        public System.Action<MatchStateSnapshot> OnStepCompleted;
        public System.Action<MatchStateSnapshot> OnStepCleanupCompleted;
        public System.Action<MatchCommand> OnCommandAccepted;
        public System.Action<MatchCommand, string> OnCommandRejected;
        public System.Action<MatchCommand, string, MatchCommandRejectionDiagnostics> OnCommandRejectedDetailed;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }

            Instance = this;
            ResolveReferences();
        }

        private void OnDestroy()
        {
            if (Instance == this)
            {
                Instance = null;
            }
        }

        public void BeginMatch(int startResourcesPerPlayer, int maxSteps)
        {
            ResolveReferences();

            _playerStates = new PlayerState[2]
            {
                new PlayerState(Owner.Player1, startResourcesPerPlayer),
                new PlayerState(Owner.Player2, startResourcesPerPlayer)
            };

            _resources[0] = startResourcesPerPlayer;
            _resources[1] = startResourcesPerPlayer;

            ResourceManager.Instance?.ResetForEpisode();

            MaxSteps = maxSteps > 0 ? maxSteps : GameConstants.MaxEpisodeSteps;
            Step = 0;
            Winner = Owner.Neutral;
            EndReason = MatchEndReason.None;
            EndReasonDetails = string.Empty;
            Phase = MatchPhase.Running;

            _acceptedCommandsThisStep = 0;
            _invalidCommandsThisStep = 0;
            _combatResolver = null;
            _pendingCommands.Clear();
            ClearPhaseCommandBuffers();
            _lastAppliedCommandByUnit.Clear();

            SeedPlayerCountersFromRegistry();

            if (_logStepEvents)
            {
                Debug.Log($"[MatchManager] BeginMatch. MaxSteps={MaxSteps}, StartResources={startResourcesPerPlayer}");
            }
        }

        public void ResetMatch()
        {
            if (_playerStates != null)
            {
                _playerStates[0]?.ResetForEpisode(0);
                _playerStates[1]?.ResetForEpisode(0);
            }

            _resources[0] = 0;
            _resources[1] = 0;

            _acceptedCommandsThisStep = 0;
            _invalidCommandsThisStep = 0;
            _combatResolver = null;
            _pendingCommands.Clear();
            ClearPhaseCommandBuffers();
            _lastAppliedCommandByUnit.Clear();

            Step = 0;
            MaxSteps = 0;
            Winner = Owner.Neutral;
            EndReason = MatchEndReason.None;
            EndReasonDetails = string.Empty;
            Phase = MatchPhase.Idle;
        }

        public bool StepMatch()
        {
            if (Phase != MatchPhase.Running)
            {
                return false;
            }

            using var stepMarker = StepMatchMarker.Auto();
            ResolveReferences();
            LogPendingHumanMoves("StepMatch begin");

            _acceptedCommandsThisStep = 0;
            _invalidCommandsThisStep = 0;
            _lastAppliedCommandByUnit.Clear();

            // 1) Command processing and bucketing by phase.
            ProcessCommandPhase();

            // 2) Movement.
            ExecuteMovementPhase();

            // 3) Harvest / deposit economy interactions.
            ExecuteHarvestDepositPhase();

            // 4) Production.
            ExecuteProductionPhase();

            // 5) Combat.
            ExecuteCombatPhase();
            LogPendingHumanMoveResults();

            // Step counter is advanced after all gameplay phases.
            Step++;
            OnStepAdvanced?.Invoke(Step);

            // 6) Match completion check.
            MatchResolution resolution = ResolveCompletion();
            if (resolution.IsTerminal)
            {
                DeclareWinner(resolution.Winner, resolution.Reason, resolution.Details);
            }

            MatchStateSnapshot snapshot = GetMatchState();
            OnStepCompleted?.Invoke(snapshot);

            if (_logStepEvents)
            {
                Debug.Log(
                    $"[MatchManager] Step={Step}, Accepted={_acceptedCommandsThisStep}, Invalid={_invalidCommandsThisStep}, " +
                    $"P1Res={snapshot.Player1Resources}, P2Res={snapshot.Player2Resources}");
            }

            _pendingCommands.Clear();
            ClearPhaseCommandBuffers();
            OnStepCleanupCompleted?.Invoke(snapshot);

            return Phase == MatchPhase.Running;
        }

        // Backward-compatible helper for old callers.
        public void AdvanceStep()
        {
            if (Phase != MatchPhase.Running)
            {
                return;
            }

            Step++;
            OnStepAdvanced?.Invoke(Step);
        }

        public bool ApplyCommand(MatchCommand command)
        {
            if (Phase != MatchPhase.Running)
            {
                RejectCommand(command, "Match is not running.");
                return false;
            }

            if (!IsPlayerOwner(command.Owner))
            {
                RejectCommand(command, "Only Player1/Player2 commands are accepted.");
                return false;
            }

            if (command.ActionType == UnitActionType.NoOp)
            {
                return true;
            }

            _pendingCommands.Add(command);
            if (_logHumanMoveDiagnostics && command.Owner == Owner.Player2 && command.ActionType == UnitActionType.Move)
            {
                Debug.Log($"[HumanMove3G1R] MatchManager queued Player2 Move actor={command.UnitPosition} direction={command.Direction} pendingCount={_pendingCommands.Count}");
            }
            return true;
        }

        private void LogPendingHumanMoves(string stage)
        {
            if (!_logHumanMoveDiagnostics)
            {
                return;
            }

            for (int i = 0; i < _pendingCommands.Count; i++)
            {
                MatchCommand command = _pendingCommands[i];
                if (command.Owner != Owner.Player2 || command.ActionType != UnitActionType.Move)
                {
                    continue;
                }

                Debug.Log($"[HumanMove3G1R] MatchManager {stage} Player2 Move actor={command.UnitPosition} direction={command.Direction} pendingCount={_pendingCommands.Count}");
            }
        }

        private void LogPendingHumanMoveResults()
        {
            if (!_logHumanMoveDiagnostics)
            {
                return;
            }

            for (int i = 0; i < _movementCommands.Count; i++)
            {
                ResolvedCommand resolved = _movementCommands[i];
                MatchCommand command = resolved.Command;
                if (command.Owner != Owner.Player2 || command.ActionType != UnitActionType.Move)
                {
                    continue;
                }

                UnitRuntime unit = resolved.Unit;
                Debug.Log($"[HumanMove3G1R] MatchManager movement phase result actorBefore={command.UnitPosition} direction={command.Direction} finalGrid={(unit != null ? unit.GridPos.ToString() : "<null>")} changed={unit != null && unit.GridPos != command.UnitPosition}");
            }
        }

        public int ApplyCommands(IReadOnlyList<MatchCommand> commands)
        {
            if (commands == null)
            {
                return 0;
            }

            int accepted = 0;
            for (int i = 0; i < commands.Count; i++)
            {
                if (ApplyCommand(commands[i]))
                {
                    accepted++;
                }
            }

            return accepted;
        }

        public MatchStateSnapshot GetMatchState()
        {
            int p1Units = CountAliveUnits(Owner.Player1);
            int p2Units = CountAliveUnits(Owner.Player2);
            int p1Bases = CountAliveBases(Owner.Player1);
            int p2Bases = CountAliveBases(Owner.Player2);

            return new MatchStateSnapshot(
                Phase,
                Step,
                MaxSteps,
                Winner,
                EndReason,
                GetResources(Owner.Player1),
                GetResources(Owner.Player2),
                p1Units,
                p2Units,
                p1Bases,
                p2Bases,
                _pendingCommands.Count);
        }

        public PlayerState GetPlayerState(Owner owner)
        {
            if (_playerStates == null)
            {
                return null;
            }

            return owner switch
            {
                Owner.Player1 => _playerStates[0],
                Owner.Player2 => _playerStates[1],
                _ => null
            };
        }

        public int GetResources(Owner owner)
        {
            PlayerState state = GetPlayerState(owner);
            if (state != null)
            {
                return state.CurrentResources;
            }

            return owner == Owner.Player1 ? _resources[0] :
                   owner == Owner.Player2 ? _resources[1] : 0;
        }

        public void AddResources(Owner owner, int amount)
        {
            PlayerState state = GetPlayerState(owner);
            if (state != null)
            {
                if (amount >= 0)
                {
                    state.AddResources(amount);
                }
                else
                {
                    state.SpendResources(-amount);
                }

                SyncLegacyResourceCache(owner, state.CurrentResources);
                return;
            }

            if (owner == Owner.Player1)
            {
                _resources[0] = Mathf.Max(0, _resources[0] + amount);
            }
            else if (owner == Owner.Player2)
            {
                _resources[1] = Mathf.Max(0, _resources[1] + amount);
            }
        }

        public bool CanAfford(Owner owner, int cost)
        {
            PlayerState state = GetPlayerState(owner);
            if (state != null)
            {
                return state.CanAfford(cost);
            }

            return GetResources(owner) >= cost;
        }

        public void DeclareWinner(Owner winner, MatchEndReason reason = MatchEndReason.None, string details = "")
        {
            if (Phase != MatchPhase.Running)
            {
                return;
            }

            Winner = winner;
            EndReason = reason;
            EndReasonDetails = details ?? string.Empty;
            Phase = MatchPhase.Ended;

            MatchResolution resolution = new MatchResolution(true, winner, reason, Step, EndReasonDetails);

            LogLifecycleDiagnostic($"[MatchManager] Match ended. Winner={winner}, Reason={reason}, Step={Step}");
            OnMatchResolved?.Invoke(resolution);
            OnMatchEnded?.Invoke(winner);
        }

        private void ProcessCommandPhase()
        {
            using var marker = ProcessCommandPhaseMarker.Auto();
            ClearPhaseCommandBuffers();

            if (_pendingCommands.Count == 0)
            {
                return;
            }

            _assignedUnitsScratch.Clear();

            for (int i = 0; i < _pendingCommands.Count; i++)
            {
                MatchCommand command = _pendingCommands[i];
                if (!TryResolveCommandUnit(command, out UnitRuntime unit, out string error))
                {
                    RejectCommand(command, error);
                    continue;
                }

                if (!_assignedUnitsScratch.Add(unit))
                {
                    RejectCommand(command, "Unit already has a command this step.");
                    continue;
                }

                var resolved = new ResolvedCommand(unit, command);
                switch (command.ActionType)
                {
                    case UnitActionType.Move:
                        _movementCommands.Add(resolved);
                        break;
                    case UnitActionType.Harvest:
                    case UnitActionType.Return:
                        _harvestDepositCommands.Add(resolved);
                        break;
                    case UnitActionType.Produce:
                        _productionCommands.Add(resolved);
                        break;
                    case UnitActionType.Attack:
                        _combatCommands.Add(resolved);
                        break;
                    default:
                        RejectCommand(command, "Unsupported command action.");
                        continue;
                }

                _acceptedCommandsThisStep++;
                TotalAcceptedCommands++;
                OnCommandAccepted?.Invoke(command);
                _lastAppliedCommandByUnit[unit] = command;
            }
        }

        /// <summary>
        /// Возвращает последнюю принятую команду для юнита в текущем шаге.
        /// Используется ObservationBuilder для заполнения action channels.
        /// </summary>
        public bool TryGetLastAppliedCommand(UnitRuntime unit, out MatchCommand command)
        {
            if (unit != null && _lastAppliedCommandByUnit.TryGetValue(unit, out command))
            {
                return true;
            }

            command = default;
            return false;
        }

        /// <summary>
        /// Returns known Move targets that are already visible in the command ledger for the current step.
        /// This is a read-only diagnostic/introspection helper for pre-submit mask enrichment.
        /// </summary>
        public void GetKnownMoveReservations(List<PendingMoveReservation> output)
        {
            if (output == null)
            {
                return;
            }

            output.Clear();
            var seen = new HashSet<string>();

            for (int i = 0; i < _movementCommands.Count; i++)
            {
                MatchCommand command = _movementCommands[i].Command;
                if (command.ActionType != UnitActionType.Move)
                {
                    continue;
                }

                GridPosition target = command.UnitPosition.Neighbour(command.Direction);
                string key = command.Owner + "|" + command.UnitPosition.ToFlatIndex() + "|" + target.ToFlatIndex() + "|" + (int)command.Direction;
                if (!seen.Add(key))
                {
                    continue;
                }

                output.Add(new PendingMoveReservation(command.Owner, command.UnitPosition, target, command.Direction, "movement_commands"));
            }

            for (int i = 0; i < _pendingCommands.Count; i++)
            {
                MatchCommand command = _pendingCommands[i];
                if (command.ActionType != UnitActionType.Move)
                {
                    continue;
                }

                GridPosition target = command.UnitPosition.Neighbour(command.Direction);
                string key = command.Owner + "|" + command.UnitPosition.ToFlatIndex() + "|" + target.ToFlatIndex() + "|" + (int)command.Direction;
                if (!seen.Add(key))
                {
                    continue;
                }

                output.Add(new PendingMoveReservation(command.Owner, command.UnitPosition, target, command.Direction, "pending_commands"));
            }
        }

        private void ExecuteMovementPhase()
        {
            using var marker = MovementPhaseMarker.Auto();
            if (_gridManager == null || _movementCommands.Count == 0)
            {
                return;
            }

            for (int i = 0; i < _movementCommands.Count; i++)
            {
                ResolvedCommand command = _movementCommands[i];
                if (!TryExecuteMove(command, out MatchCommandRejectionDiagnostics diagnostics))
                {
                    RejectCommand(command.Command, "Move command cannot be executed.", diagnostics);
                }
            }
        }

        private bool TryExecuteMove(ResolvedCommand command, out MatchCommandRejectionDiagnostics diagnostics)
        {
            diagnostics = MatchCommandRejectionDiagnostics.None;

            UnitRuntime unit = command.Unit;
            GridPosition sourceFromCommand = command.Command.UnitPosition;
            GridPosition sourceAtReject = unit != null ? unit.GridPos : sourceFromCommand;
            GridPosition targetFromCommand = sourceFromCommand.Neighbour(command.Command.Direction);
            GridPosition targetFromRuntime = sourceAtReject.Neighbour(command.Command.Direction);
            bool runtimeTargetMatchesCommandTarget = targetFromRuntime == targetFromCommand;

            if (unit == null || !unit.IsAlive || unit.IsBuilding || _gridManager == null)
            {
                diagnostics = BuildMoveRejectionDiagnostics(
                    command,
                    unit,
                    sourceFromCommand,
                    sourceAtReject,
                    targetFromCommand,
                    targetFromRuntime,
                    occupancyLookupAttempted: false,
                    occupancyLookupMethod: "not_executed",
                    occupancyLookupSource: "MatchManager.TryExecuteMove",
                    targetInBounds: false,
                    targetPassable: false,
                    targetOccupied: false,
                    tryGetOccupantResult: false,
                    occupant: null,
                    normalizedReason: "unit_unavailable_or_grid_missing",
                    runtimeTargetMatchesCommandTarget: runtimeTargetMatchesCommandTarget);
                return false;
            }

            bool targetInBounds = _gridManager.IsInside(targetFromRuntime);
            UnitRuntime occupant = null;
            bool targetOccupied = false;
            bool targetPassable = false;
            bool occupancyLookupAttempted = false;
            bool tryGetOccupantResult = false;

            if (targetInBounds)
            {
                occupancyLookupAttempted = true;
                tryGetOccupantResult = _gridManager.TryGetOccupant(targetFromRuntime, out occupant);
                targetOccupied = tryGetOccupantResult && occupant != null;
                targetPassable = !targetOccupied;
            }

            if (!targetInBounds || targetOccupied)
            {
                diagnostics = BuildMoveRejectionDiagnostics(
                    command,
                    unit,
                    sourceFromCommand,
                    sourceAtReject,
                    targetFromCommand,
                    targetFromRuntime,
                    occupancyLookupAttempted,
                    "GridManager.TryGetOccupant",
                    "MatchManager.TryExecuteMove",
                    targetInBounds,
                    targetPassable,
                    targetOccupied,
                    tryGetOccupantResult,
                    occupant,
                    !targetInBounds ? "target_out_of_bounds" : "target_occupied",
                    runtimeTargetMatchesCommandTarget);
                return false;
            }

            bool moved = unit.MoveTo(targetFromRuntime, _gridManager);
            if (!moved)
            {
                diagnostics = BuildMoveRejectionDiagnostics(
                    command,
                    unit,
                    sourceFromCommand,
                    sourceAtReject,
                    targetFromCommand,
                    targetFromRuntime,
                    occupancyLookupAttempted,
                    "GridManager.TryGetOccupant",
                    "MatchManager.TryExecuteMove",
                    targetInBounds,
                    targetPassable,
                    targetOccupied,
                        tryGetOccupantResult,
                    occupant,
                    "move_apply_failed",
                    runtimeTargetMatchesCommandTarget);
            }

            return moved;
        }

        private void ExecuteHarvestDepositPhase()
        {
            if (_harvestDepositCommands.Count == 0)
            {
                return;
            }

            for (int i = 0; i < _harvestDepositCommands.Count; i++)
            {
                ResolvedCommand command = _harvestDepositCommands[i];
                bool success = command.Command.ActionType switch
                {
                    UnitActionType.Harvest => TryExecuteHarvest(command),
                    UnitActionType.Return => TryExecuteDeposit(command),
                    _ => false
                };

                if (!success)
                {
                    RejectCommand(command.Command, "Harvest/deposit command cannot be executed.");
                }
            }
        }

        private bool TryExecuteHarvest(ResolvedCommand command)
        {
            ResourceManager resourceManager = ResourceManager.Instance;
            if (resourceManager == null)
            {
                return false;
            }

            UnitRuntime worker = command.Unit;
            if (worker == null || !worker.IsAlive || worker.IsBuilding || worker.Type != UnitType.Worker)
            {
                return false;
            }

            int freeCapacity = GameConstants.MaxCarryCapacity - worker.CarriedResources;
            if (freeCapacity <= 0)
            {
                return false;
            }

            GridPosition targetCell = worker.GridPos.Neighbour(command.Command.Direction);
            ResourceNode node = resourceManager.GetResourceNode(targetCell);
            if (node == null || node.IsExhausted)
            {
                return false;
            }

            int requestAmount = Mathf.Min(GameConstants.HarvestAmount, freeCapacity);
            int harvested = node.Harvest(requestAmount);
            if (harvested <= 0)
            {
                return false;
            }

            bool carriedAdded = worker.AddCarriedResources(harvested) > 0;
            if (carriedAdded)
            {
                TryGetVisualBridge(worker)?.OnVisualHarvest();
            }

            return carriedAdded;
        }

        private bool TryExecuteDeposit(ResolvedCommand command)
        {
            if (_gridManager == null)
            {
                return false;
            }

            UnitRuntime worker = command.Unit;
            if (worker == null || !worker.IsAlive || worker.Type != UnitType.Worker)
            {
                return false;
            }

            if (worker.CarriedResources <= 0)
            {
                return false;
            }

            GridPosition dropCell = worker.GridPos.Neighbour(command.Command.Direction);
            if (!_gridManager.TryGetOccupant(dropCell, out UnitRuntime targetBase) || targetBase == null)
            {
                return false;
            }

            if (targetBase.Owner != worker.Owner || targetBase.Type != UnitType.Base)
            {
                return false;
            }

            int dropped = worker.DropAllCarriedResources();
            if (dropped <= 0)
            {
                return false;
            }

            AddResources(worker.Owner, dropped);
            return true;
        }

        private void ExecuteProductionPhase()
        {
            using var marker = ProductionPhaseMarker.Auto();
            GameConfig config = GetActiveConfig();

            for (int i = 0; i < _productionCommands.Count; i++)
            {
                ResolvedCommand command = _productionCommands[i];
                if (!TryExecuteProduce(command, config))
                {
                    RejectCommand(command.Command, "Produce command cannot be executed.");
                }
            }

            if (_unitRegistry == null)
            {
                return;
            }

            IReadOnlyList<UnitRuntime> allUnits = _unitRegistry.GetAllUnitsReadOnly();
            for (int i = 0; i < allUnits.Count; i++)
            {
                UnitRuntime unit = allUnits[i];
                if (unit == null || !unit.IsAlive || !unit.IsBuilding)
                {
                    continue;
                }

                BuildingRuntime building = unit.GetComponent<BuildingRuntime>();
                building?.TickProduction();
            }
        }

        private bool TryExecuteProduce(ResolvedCommand command, GameConfig config)
        {
            UnitRuntime buildingUnit = command.Unit;
            if (buildingUnit == null || !buildingUnit.IsAlive)
            {
                return false;
            }

            if (config == null)
            {
                return false;
            }

            // MVP encoding: Worker + Produce = build Barracks on adjacent cell.
            // No dedicated build-structure slot exists in the 4-slot produce contract.
            // ProduceUnitType value is ignored for Worker actors.
            // ML-layer canonical rule: ActionContractMappings.IsWorkerBuildBarracksAction (RTS.ML).
            if (buildingUnit.Type == UnitType.Worker)
            {
                return TryWorkerBuildBarracks(buildingUnit, command.Command.Direction, config);
            }

            if (!buildingUnit.IsBuilding)
            {
                return false;
            }

            BuildingRuntime buildingRuntime = buildingUnit.GetComponent<BuildingRuntime>();
            if (buildingRuntime == null)
            {
                return false;
            }

            // Authoritative production rule: Base→Worker, Barracks→Light/Heavy/Ranged
            if (!IsBuildingAllowedToProduceUnit(buildingUnit.Type, command.Command.ProduceUnitType))
            {
                LogProductionWarning($"[MatchManager] {buildingUnit.Type} cannot produce {command.Command.ProduceUnitType} " +
                                 "(production rule: Base→Worker, Barracks→Light/Heavy/Ranged)");
                return false;
            }

            UnitType producedType = command.Command.ProduceUnitType switch
            {
                ProducibleUnit.Worker => UnitType.Worker,
                ProducibleUnit.Light => UnitType.Light,
                ProducibleUnit.Heavy => UnitType.Heavy,
                ProducibleUnit.Ranged => UnitType.Ranged,
                _ => UnitType.Worker
            };

            return buildingRuntime.StartProducingUnit(producedType, config);
        }

        private static bool IsBuildingAllowedToProduceUnit(UnitType buildingType, ProducibleUnit produceType)
        {
            return buildingType switch
            {
                UnitType.Base     => produceType == ProducibleUnit.Worker,
                UnitType.Barracks => produceType == ProducibleUnit.Light
                                  || produceType == ProducibleUnit.Heavy
                                  || produceType == ProducibleUnit.Ranged,
                _                 => false
            };
        }

        private bool TryWorkerBuildBarracks(UnitRuntime worker, Direction direction, GameConfig config)
        {
            GridPosition targetCell = worker.GridPos.Neighbour(direction);
            LogBarracksBuildConfigDiagnostic("TryWorkerBuildBarracks.enter", config, targetCell, worker);

            if (CountAliveBarracks(worker.Owner) > 0)
            {
                LogProductionWarning($"[MatchManager] Worker build Barracks: {worker.Owner} already has a living Barracks");
                return false;
            }

            if (!_gridManager.IsInside(targetCell))
            {
                LogProductionWarning($"[MatchManager] Worker build Barracks: target {targetCell} out of bounds");
                return false;
            }

            if (_gridManager.IsCellOccupied(targetCell))
            {
                LogProductionWarning($"[MatchManager] Worker build Barracks: target {targetCell} is occupied");
                return false;
            }

            var barracksDefinition = config.GetDefinition(UnitType.Barracks);
            if (barracksDefinition == null)
            {
                LogBarracksBuildConfigDiagnostic("TryWorkerBuildBarracks.barracks_definition_null", config, targetCell, worker);
                LogProductionWarning("[MatchManager] Worker build Barracks: UnitDef_Barracks not configured in GameConfig");
                return false;
            }

            int cost = barracksDefinition.productionCost;
            if (!CanAfford(worker.Owner, cost))
            {
                LogProductionWarning($"[MatchManager] Worker build Barracks: insufficient resources (need {cost})");
                return false;
            }

            // Spend resources first
            AddResources(worker.Owner, -cost);

            var factory = new UnitFactory(config, _gridManager, _gridManager?.transform, _unitRegistry);
            var barracks = factory.Spawn(UnitType.Barracks, worker.Owner, targetCell);
            if (barracks == null)
            {
                // Refund on failed spawn
                AddResources(worker.Owner, cost);
                LogProductionWarning($"[MatchManager] Worker build Barracks: UnitFactory spawn failed at {targetCell}");
                return false;
            }

            LogProductionDiagnostic($"[MatchManager] {worker.Owner} Worker built Barracks at {targetCell} (cost: {cost})");
            return true;
        }

        private void ExecuteCombatPhase()
        {
            using var marker = CombatPhaseMarker.Auto();
            if (!EnsureCombatResolverReady())
            {
                return;
            }

            HashSet<UnitRuntime> commandedAttackers = null;
            if (_combatCommands.Count > 0)
            {
                _commandedAttackersScratch.Clear();
                commandedAttackers = _commandedAttackersScratch;
                for (int i = 0; i < _combatCommands.Count; i++)
                {
                    ResolvedCommand command = _combatCommands[i];
                    if (TryExecuteAttack(command))
                    {
                        commandedAttackers.Add(command.Unit);
                    }
                    else
                    {
                        RejectCommand(command.Command, "Attack command cannot be executed.");
                    }
                }
            }

            _combatResolver.ResolveCombatTick(commandedAttackers);
        }

        private bool TryExecuteAttack(ResolvedCommand command)
        {
            if (_gridManager == null)
            {
                return false;
            }

            UnitRuntime attacker = command.Unit;
            if (attacker == null || !attacker.IsAlive)
            {
                return false;
            }

            if (!command.Command.HasAttackTarget)
            {
                return false;
            }

            GridPosition targetPos = command.Command.AttackTarget;
            if (!_gridManager.IsInside(targetPos))
            {
                return false;
            }

            if (!_gridManager.TryGetOccupant(targetPos, out UnitRuntime target) || target == null || !target.IsAlive)
            {
                return false;
            }

            if (target.Owner == attacker.Owner || target.Owner == Owner.Neutral)
            {
                return false;
            }

            return _combatResolver.TryAttack(attacker, target);
        }

        private static VisualEventBridge TryGetVisualBridge(UnitRuntime unit)
        {
            if (unit == null)
            {
                return null;
            }

            return unit.GetComponent<VisualEventBridge>()
                   ?? unit.GetComponentInParent<VisualEventBridge>(true)
                   ?? unit.GetComponentInChildren<VisualEventBridge>(true);
        }

        private MatchResolution ResolveCompletion()
        {
            if (_victoryResolver == null || _unitRegistry == null)
            {
                if (MaxSteps > 0 && Step >= MaxSteps)
                {
                    return new MatchResolution(
                        true,
                        Owner.Neutral,
                        MatchEndReason.StepLimitReached,
                        Step,
                        $"Step limit reached ({Step}/{MaxSteps}).");
                }

                return MatchResolution.Continue(Step);
            }

            return _victoryResolver.Evaluate(_unitRegistry, Step, MaxSteps);
        }

        private bool TryResolveCommandUnit(MatchCommand command, out UnitRuntime unit, out string error)
        {
            unit = null;
            error = string.Empty;

            if (_gridManager == null)
            {
                error = "GridManager is missing.";
                return false;
            }

            if (!_gridManager.IsInside(command.UnitPosition))
            {
                error = "Command source position is outside the grid.";
                return false;
            }

            if (!_gridManager.TryGetOccupant(command.UnitPosition, out unit) || unit == null)
            {
                error = "No unit found at command source position.";
                return false;
            }

            if (!unit.IsAlive)
            {
                error = "Command source unit is dead.";
                return false;
            }

            if (unit.Owner != command.Owner)
            {
                error = "Command source unit belongs to another owner.";
                return false;
            }

            return true;
        }

        private void LogProductionDiagnostic(string message)
        {
            if (_logProductionDiagnostics)
            {
                Debug.Log(message);
            }
        }

        private void LogProductionWarning(string message)
        {
            if (_logProductionDiagnostics)
            {
                Debug.LogWarning(message);
            }
        }

        private void LogLifecycleDiagnostic(string message)
        {
            if (_logLifecycleDiagnostics)
            {
                Debug.Log(message);
            }
        }

        private void RejectCommand(MatchCommand command, string reason, MatchCommandRejectionDiagnostics diagnostics = default)
        {
            _invalidCommandsThisStep++;
            TotalInvalidCommands++;

            if (_logStepEvents)
            {
                Debug.LogWarning($"[MatchManager] Command rejected: {reason}");
            }

            OnCommandRejected?.Invoke(command, reason);
            MatchCommandRejectionDiagnostics details = diagnostics.HasDiagnostics
                ? diagnostics
                : MatchCommandRejectionDiagnostics.None;
            OnCommandRejectedDetailed?.Invoke(command, reason, details);
        }

        private static MatchCommandRejectionDiagnostics BuildMoveRejectionDiagnostics(
            ResolvedCommand command,
            UnitRuntime unit,
            GridPosition sourceFromCommand,
            GridPosition sourceAtReject,
            GridPosition targetFromCommand,
            GridPosition targetFromRuntime,
            bool occupancyLookupAttempted,
            string occupancyLookupMethod,
            string occupancyLookupSource,
            bool targetInBounds,
            bool targetPassable,
            bool targetOccupied,
            bool tryGetOccupantResult,
            UnitRuntime occupant,
            string normalizedReason,
            bool runtimeTargetMatchesCommandTarget)
        {
            int occupancyLookupKeyCell = ToFlatIndex(targetFromRuntime);
            int occupancyLookupKeyX = targetFromRuntime.X;
            int occupancyLookupKeyY = targetFromRuntime.Y;

            bool occupantRefExists = occupant != null;
            int occupantInstanceId = occupantRefExists ? occupant.GetInstanceID() : 0;
            string occupantName = occupantRefExists ? occupant.name : "NOT_EXPOSED";

            GridPosition occupantLogicalPos = occupantRefExists ? occupant.GridPos : GridPosition.Zero;
            int occupantLogicalX = occupantRefExists ? occupantLogicalPos.X : -1;
            int occupantLogicalY = occupantRefExists ? occupantLogicalPos.Y : -1;
            int occupantLogicalCell = occupantRefExists ? ToFlatIndex(occupantLogicalPos) : -1;
            bool occupantLogicalCellRoundtripOk = occupantRefExists
                && occupantLogicalPos.IsInsideMap()
                && GridPosition.FromFlatIndex(occupantLogicalCell) == occupantLogicalPos;
            bool occupantLogicalCellMatchesLookupKey = occupantRefExists && occupantLogicalCell == occupancyLookupKeyCell;
            bool occupantLogicalCellMatchesTargetCell = occupantRefExists && occupantLogicalCell == ToFlatIndex(targetFromCommand);

            float occupantTransformX = occupantRefExists ? occupant.transform.position.x : float.NaN;
            float occupantTransformY = occupantRefExists ? occupant.transform.position.z : float.NaN;
            int occupantVisualGridX = -1;
            int occupantVisualGridY = -1;
            int occupantVisualCell = -1;
            bool occupantVisualCellMatchesLogicalCell = false;
            GridPosition occupantVisualPos = GridPosition.Zero;
            bool hasVisualCell = false;
            if (occupantRefExists)
            {
                occupantVisualPos = GridPosition.FromWorldPosition(occupant.transform.position);
                hasVisualCell = occupantVisualPos.IsInsideMap();
                if (hasVisualCell)
                {
                    occupantVisualGridX = occupantVisualPos.X;
                    occupantVisualGridY = occupantVisualPos.Y;
                    occupantVisualCell = ToFlatIndex(occupantVisualPos);
                    occupantVisualCellMatchesLogicalCell = occupantVisualCell == occupantLogicalCell;
                }
            }

            bool gridLookupByTargetReturnsOccupant = false;
            bool gridLookupByOccupantLogicalCellReturnsSameOccupant = false;
            bool gridLookupByOccupantVisualCellReturnsSameOccupant = false;
            bool occupancyMapKeyMatchesOccupantLogicalPosition = false;
            if (command.Unit != null && command.Unit.IsAlive && command.Unit.Owner != Owner.Neutral)
            {
                // no-op: keeps method pure wrt gameplay state; diagnostics only below use provided references.
            }

            GridManager grid = GridManager.Instance;
            if (grid != null)
            {
                if (grid.TryGetOccupant(targetFromRuntime, out UnitRuntime atTarget) && atTarget != null && occupantRefExists)
                {
                    gridLookupByTargetReturnsOccupant = ReferenceEquals(atTarget, occupant);
                }

                if (occupantRefExists && occupantLogicalPos.IsInsideMap()
                    && grid.TryGetOccupant(occupantLogicalPos, out UnitRuntime atLogical)
                    && atLogical != null)
                {
                    gridLookupByOccupantLogicalCellReturnsSameOccupant = ReferenceEquals(atLogical, occupant);
                }

                if (occupantRefExists && hasVisualCell
                    && grid.TryGetOccupant(occupantVisualPos, out UnitRuntime atVisual)
                    && atVisual != null)
                {
                    gridLookupByOccupantVisualCellReturnsSameOccupant = ReferenceEquals(atVisual, occupant);
                }

                if (occupantRefExists)
                {
                    foreach (KeyValuePair<GridPosition, UnitRuntime> kv in grid.Occupancy)
                    {
                        if (!ReferenceEquals(kv.Value, occupant))
                        {
                            continue;
                        }

                        occupancyMapKeyMatchesOccupantLogicalPosition = kv.Key == occupantLogicalPos;
                        break;
                    }
                }
            }

            return new MatchCommandRejectionDiagnostics(
                hasDiagnostics: true,
                rejectCallsite: "MatchManager.ExecuteMovementPhase -> TryExecuteMove -> RejectCommand",
                rejectReasonRaw: "Move command cannot be executed.",
                rejectReasonNormalized: normalizedReason,
                actionType: command.Command.ActionType,
                moveDir: command.Command.Direction,
                sourceCellFromCommand: ToFlatIndex(sourceFromCommand),
                sourceXFromCommand: sourceFromCommand.X,
                sourceYFromCommand: sourceFromCommand.Y,
                targetCellFromCommand: ToFlatIndex(targetFromCommand),
                targetXFromCommand: targetFromCommand.X,
                targetYFromCommand: targetFromCommand.Y,
                unitId: GetUnitId(unit),
                unitOwner: unit != null ? unit.Owner.ToString() : "NOT_EXPOSED",
                unitType: unit != null ? unit.Type.ToString() : "NOT_EXPOSED",
                unitPositionXAtReject: sourceAtReject.X,
                unitPositionYAtReject: sourceAtReject.Y,
                unitCellAtReject: ToFlatIndex(sourceAtReject),
                occupantExistsAtTarget: targetOccupied,
                occupantIdAtTarget: GetUnitId(occupant),
                occupantOwnerAtTarget: occupant != null ? occupant.Owner.ToString() : "NOT_EXPOSED",
                occupantTypeAtTarget: occupant != null ? occupant.Type.ToString() : "NOT_EXPOSED",
                occupantXAtTarget: occupant != null ? occupant.GridPos.X : -1,
                occupantYAtTarget: occupant != null ? occupant.GridPos.Y : -1,
                occupantCellAtTarget: occupant != null ? ToFlatIndex(occupant.GridPos) : -1,
                occupancyLookupKeyCell: occupancyLookupKeyCell,
                occupancyLookupKeyX: occupancyLookupKeyX,
                occupancyLookupKeyY: occupancyLookupKeyY,
                tryGetOccupantResult: tryGetOccupantResult,
                occupantRefExists: occupantRefExists,
                occupantInstanceId: occupantInstanceId,
                occupantName: occupantName,
                occupantLogicalX: occupantLogicalX,
                occupantLogicalY: occupantLogicalY,
                occupantLogicalCell: occupantLogicalCell,
                occupantLogicalCellRoundtripOk: occupantLogicalCellRoundtripOk,
                occupantLogicalCellMatchesLookupKey: occupantLogicalCellMatchesLookupKey,
                occupantLogicalCellMatchesTargetCell: occupantLogicalCellMatchesTargetCell,
                occupantTransformX: occupantTransformX,
                occupantTransformY: occupantTransformY,
                occupantVisualGridX: occupantVisualGridX,
                occupantVisualGridY: occupantVisualGridY,
                occupantVisualCell: occupantVisualCell,
                occupantVisualCellMatchesLogicalCell: occupantVisualCellMatchesLogicalCell,
                gridLookupByTargetReturnsOccupant: gridLookupByTargetReturnsOccupant,
                gridLookupByOccupantLogicalCellReturnsSameOccupant: gridLookupByOccupantLogicalCellReturnsSameOccupant,
                gridLookupByOccupantVisualCellReturnsSameOccupant: gridLookupByOccupantVisualCellReturnsSameOccupant,
                occupancyMapKeyMatchesOccupantLogicalPosition: occupancyMapKeyMatchesOccupantLogicalPosition,
                occupantCellReportedPrevious: occupant != null ? ToFlatIndex(occupant.GridPos) : -1,
                occupancyLookupMethod: occupancyLookupAttempted ? occupancyLookupMethod : "not_executed",
                occupancyLookupSource: occupancyLookupSource,
                targetInBoundsAtReject: targetInBounds,
                targetPassableAtReject: targetPassable,
                targetOccupiedAtReject: targetOccupied,
                targetOccupiedByRuntimeLookup: targetOccupied,
                directRuntimeTargetMatchesReconstructedTarget: runtimeTargetMatchesCommandTarget);
        }

        private static int ToFlatIndex(GridPosition pos)
            => pos.Y * GameConstants.MapWidth + pos.X;

        private static string GetUnitId(UnitRuntime unit)
        {
            if (unit == null)
            {
                return "NOT_EXPOSED";
            }

            return unit.name + "#" + unit.GetInstanceID();
        }

        private void ResolveReferences()
        {
            if (_gridManager == null)
            {
                _gridManager = GridManager.Instance;
            }

            if (_unitRegistry == null)
            {
                _unitRegistry = UnitRegistry.Instance;
            }

            if (_victoryResolver == null)
            {
                _victoryResolver = VictoryResolver.Instance;
            }

            if (_matchBootstrap == null)
            {
                _matchBootstrap = MatchBootstrap.Instance;
            }
        }

        private bool EnsureCombatResolverReady()
        {
            if (_combatResolver != null)
            {
                return true;
            }

            GameConfig config = GetActiveConfig();
            if (config == null || _unitRegistry == null || _gridManager == null)
            {
                return false;
            }

            _combatResolver = new CombatResolver(config, _unitRegistry, _gridManager, this);
            return true;
        }

        private GameConfig GetActiveConfig()
        {
            if (_matchBootstrap == null || _matchBootstrap != MatchBootstrap.Instance)
            {
                _matchBootstrap = MatchBootstrap.Instance;
            }

            if (_matchBootstrap != null)
            {
                return _matchBootstrap.GetConfig();
            }

            MatchBootstrap bootstrap = MatchBootstrap.Instance;
            if (bootstrap != null)
            {
                return bootstrap.GetConfig();
            }

            return null;
        }

        private void LogBarracksBuildConfigDiagnostic(string source, GameConfig config, GridPosition targetCell, UnitRuntime worker)
        {
            if (Application.isEditor)
            {
                return;
            }

            UnitDefinition barracksDefinition = config != null ? config.GetDefinition(UnitType.Barracks) : null;
            bool occupied = _gridManager != null && _gridManager.IsInside(targetCell) && _gridManager.IsCellOccupied(targetCell);
            int resources = worker != null ? GetResources(worker.Owner) : -1;
            int length = config != null && config.unitDefinitions != null ? config.unitDefinitions.Length : -1;
            Debug.Log(
                $"[GameConfigBuildDiag] MatchManager.{source} config={(config != null ? config.name : "<null>")} " +
                $"configId={(config != null ? config.GetInstanceID() : 0)} barracksDefinition={(barracksDefinition != null ? barracksDefinition.name : "<null>")} " +
                $"targetCell={targetCell} resources={resources} occupied={occupied} unitDefinitions.Length={length}");

            if (config == null || config.unitDefinitions == null)
            {
                return;
            }

            for (int i = 0; i < config.unitDefinitions.Length; i++)
            {
                UnitDefinition definition = config.unitDefinitions[i];
                string expected = Enum.IsDefined(typeof(UnitType), i) ? ((UnitType)i).ToString() : "<undefined>";
                Debug.Log($"[GameConfigBuildDiag] MatchManager.{source} index={i} expected={expected} asset={(definition != null ? definition.name : "<null>")}");
            }
        }

        private void SeedPlayerCountersFromRegistry()
        {
            if (_unitRegistry == null || _playerStates == null)
            {
                return;
            }

            SeedCountersForOwner(Owner.Player1, _playerStates[0]);
            SeedCountersForOwner(Owner.Player2, _playerStates[1]);
        }

        private void SeedCountersForOwner(Owner owner, PlayerState state)
        {
            if (state == null)
            {
                return;
            }

            IReadOnlyList<UnitRuntime> units = _unitRegistry.GetUnitsByOwnerReadOnly(owner);
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit == null || !unit.IsAlive)
                {
                    continue;
                }

                if (unit.IsBuilding)
                {
                    state.RegisterBuilding();
                }
                else
                {
                    state.RegisterUnit();
                }
            }
        }

        private int CountAliveUnits(Owner owner)
        {
            if (_unitRegistry == null)
            {
                return 0;
            }

            IReadOnlyList<UnitRuntime> units = _unitRegistry.GetUnitsByOwnerReadOnly(owner);
            int aliveCount = 0;
            for (int i = 0; i < units.Count; i++)
            {
                if (units[i] != null && units[i].IsAlive)
                {
                    aliveCount++;
                }
            }

            return aliveCount;
        }

        private int CountAliveBases(Owner owner)
        {
            if (_unitRegistry == null)
            {
                return 0;
            }

            IReadOnlyList<UnitRuntime> units = _unitRegistry.GetUnitsByOwnerReadOnly(owner);
            int baseCount = 0;
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit != null && unit.IsAlive && unit.Type == UnitType.Base)
                {
                    baseCount++;
                }
            }

            return baseCount;
        }

        private int CountAliveBarracks(Owner owner)
        {
            if (_unitRegistry == null)
            {
                return 0;
            }

            IReadOnlyList<UnitRuntime> units = _unitRegistry.GetUnitsByOwnerReadOnly(owner);
            int barracksCount = 0;
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit != null && unit.IsAlive && unit.Type == UnitType.Barracks)
                {
                    barracksCount++;
                }
            }

            return barracksCount;
        }

        private static bool IsPlayerOwner(Owner owner)
            => owner == Owner.Player1 || owner == Owner.Player2;

        private void SyncLegacyResourceCache(Owner owner, int value)
        {
            if (owner == Owner.Player1)
            {
                _resources[0] = value;
            }
            else if (owner == Owner.Player2)
            {
                _resources[1] = value;
            }
        }

        private void ClearPhaseCommandBuffers()
        {
            _movementCommands.Clear();
            _harvestDepositCommands.Clear();
            _productionCommands.Clear();
            _combatCommands.Clear();
        }

        private readonly struct ResolvedCommand
        {
            public ResolvedCommand(UnitRuntime unit, MatchCommand command)
            {
                Unit = unit;
                Command = command;
            }

            public UnitRuntime Unit { get; }
            public MatchCommand Command { get; }
        }
    }
}
