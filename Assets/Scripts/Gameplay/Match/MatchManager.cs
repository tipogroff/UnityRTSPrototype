// MatchManager.cs — central step-based coordinator of a single match.

using System.Collections.Generic;
using UnityEngine;
using RTS.Core;

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

        public MatchPhase Phase { get; private set; } = MatchPhase.Idle;
        public int Step { get; private set; }
        public int MaxSteps { get; private set; }
        public Owner Winner { get; private set; } = Owner.Neutral;
        public MatchEndReason EndReason { get; private set; } = MatchEndReason.None;
        public string EndReasonDetails { get; private set; } = string.Empty;

        public int AcceptedCommandsLastStep => _acceptedCommandsThisStep;
        public int InvalidCommandsLastStep => _invalidCommandsThisStep;
        public int TotalAcceptedCommands { get; private set; }
        public int TotalInvalidCommands { get; private set; }

        private PlayerState[] _playerStates;
        private readonly int[] _resources = new int[2];

        private readonly List<MatchCommand> _pendingCommands = new List<MatchCommand>(256);
        private readonly List<ResolvedCommand> _movementCommands = new List<ResolvedCommand>(128);
        private readonly List<ResolvedCommand> _harvestDepositCommands = new List<ResolvedCommand>(128);
        private readonly List<ResolvedCommand> _productionCommands = new List<ResolvedCommand>(64);
        private readonly List<ResolvedCommand> _combatCommands = new List<ResolvedCommand>(64);
        private readonly Dictionary<UnitRuntime, MatchCommand> _lastAppliedCommandByUnit = new Dictionary<UnitRuntime, MatchCommand>(128);

        private int _acceptedCommandsThisStep;
        private int _invalidCommandsThisStep;
        private CombatResolver _combatResolver;

        public System.Action<Owner> OnMatchEnded;
        public System.Action<MatchResolution> OnMatchResolved;
        public System.Action<int> OnStepAdvanced;
        public System.Action<MatchStateSnapshot> OnStepCompleted;
        public System.Action<MatchCommand> OnCommandAccepted;
        public System.Action<MatchCommand, string> OnCommandRejected;

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

            ResolveReferences();

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
            return true;
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

            Debug.Log($"[MatchManager] Match ended. Winner={winner}, Reason={reason}, Step={Step}");
            OnMatchResolved?.Invoke(resolution);
            OnMatchEnded?.Invoke(winner);
        }

        private void ProcessCommandPhase()
        {
            ClearPhaseCommandBuffers();

            if (_pendingCommands.Count == 0)
            {
                return;
            }

            var assignedUnits = new HashSet<UnitRuntime>();

            for (int i = 0; i < _pendingCommands.Count; i++)
            {
                MatchCommand command = _pendingCommands[i];
                if (!TryResolveCommandUnit(command, out UnitRuntime unit, out string error))
                {
                    RejectCommand(command, error);
                    continue;
                }

                if (!assignedUnits.Add(unit))
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

        private void ExecuteMovementPhase()
        {
            if (_gridManager == null || _movementCommands.Count == 0)
            {
                return;
            }

            for (int i = 0; i < _movementCommands.Count; i++)
            {
                ResolvedCommand command = _movementCommands[i];
                if (!TryExecuteMove(command))
                {
                    RejectCommand(command.Command, "Move command cannot be executed.");
                }
            }
        }

        private bool TryExecuteMove(ResolvedCommand command)
        {
            UnitRuntime unit = command.Unit;
            if (unit == null || !unit.IsAlive || unit.IsBuilding)
            {
                return false;
            }

            GridPosition target = unit.GridPos.Neighbour(command.Command.Direction);
            if (!_gridManager.IsInside(target) || _gridManager.IsCellOccupied(target))
            {
                return false;
            }

            return unit.MoveTo(target, _gridManager);
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

            return worker.AddCarriedResources(harvested) > 0;
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

            List<UnitRuntime> allUnits = _unitRegistry.GetAllUnits();
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
                Debug.LogWarning($"[MatchManager] {buildingUnit.Type} cannot produce {command.Command.ProduceUnitType} " +
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

            if (!_gridManager.IsInside(targetCell))
            {
                Debug.LogWarning($"[MatchManager] Worker build Barracks: target {targetCell} out of bounds");
                return false;
            }

            if (_gridManager.IsCellOccupied(targetCell))
            {
                Debug.LogWarning($"[MatchManager] Worker build Barracks: target {targetCell} is occupied");
                return false;
            }

            var barracksDefinition = config.GetDefinition(UnitType.Barracks);
            if (barracksDefinition == null)
            {
                Debug.LogWarning("[MatchManager] Worker build Barracks: UnitDef_Barracks not configured in GameConfig");
                return false;
            }

            int cost = barracksDefinition.productionCost;
            if (!CanAfford(worker.Owner, cost))
            {
                Debug.LogWarning($"[MatchManager] Worker build Barracks: insufficient resources (need {cost})");
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
                Debug.LogWarning($"[MatchManager] Worker build Barracks: UnitFactory spawn failed at {targetCell}");
                return false;
            }

            Debug.Log($"[MatchManager] {worker.Owner} Worker built Barracks at {targetCell} (cost: {cost})");
            return true;
        }

        private void ExecuteCombatPhase()
        {
            if (!EnsureCombatResolverReady())
            {
                return;
            }

            HashSet<UnitRuntime> commandedAttackers = null;
            if (_combatCommands.Count > 0)
            {
                commandedAttackers = new HashSet<UnitRuntime>(_combatCommands.Count);
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

        private void RejectCommand(MatchCommand command, string reason)
        {
            _invalidCommandsThisStep++;
            TotalInvalidCommands++;

            if (_logStepEvents)
            {
                Debug.LogWarning($"[MatchManager] Command rejected: {reason}");
            }

            OnCommandRejected?.Invoke(command, reason);
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

            List<UnitRuntime> units = _unitRegistry.GetUnitsByOwner(owner);
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

            List<UnitRuntime> units = _unitRegistry.GetUnitsByOwner(owner);
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

            List<UnitRuntime> units = _unitRegistry.GetUnitsByOwner(owner);
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
