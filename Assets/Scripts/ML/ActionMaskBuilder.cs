using System;
using System.Collections.Generic;
using System.Text;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.ML
{
    /// <summary>
    /// Transfer-compatible mask snapshot for one player perspective.
    ///
    /// This object exposes pre-sampling availability only. It does not guarantee that an action
    /// will be accepted, because authoritative validation remains downstream in ActionApplier.
    /// </summary>
    public sealed class ActionMaskSet
    {
        private readonly ActorActionMask[] _actorMasksByCell;
        private readonly List<string> _validationMismatches;

        public ActionMaskSet(Owner playerId)
        {
            PlayerId = playerId;
            ActorCellMask = new bool[ActionContract.TotalCells];
            _actorMasksByCell = new ActorActionMask[ActionContract.TotalCells];
            _validationMismatches = new List<string>();
        }

        public Owner PlayerId { get; }
        public bool IsMatchRunning { get; internal set; }
        public bool NoOpOnlyDueToPhaseGate { get; internal set; }
        public bool[] ActorCellMask { get; }
        public int AvailableActorCount { get; internal set; }
        public int EmptyActionTypeMaskCount { get; internal set; }
        public IReadOnlyList<string> ValidationMismatches => _validationMismatches;

        public ActorActionMask GetActorMask(GridPosition position)
        {
            if (!position.IsInsideMap())
                return null;

            return GetActorMaskByFlatIndex(position.ToFlatIndex());
        }

        public ActorActionMask GetActorMaskByFlatIndex(int flatIndex)
        {
            if (flatIndex < 0 || flatIndex >= _actorMasksByCell.Length)
                return null;

            return _actorMasksByCell[flatIndex];
        }

        internal void RecordValidationMismatch(string mismatch)
        {
            if (!string.IsNullOrWhiteSpace(mismatch))
            {
                _validationMismatches.Add(mismatch);
            }
        }

        internal void SetActorMask(int flatIndex, ActorActionMask actorMask)
        {
            ActorCellMask[flatIndex] = true;
            _actorMasksByCell[flatIndex] = actorMask;
            AvailableActorCount++;

            if (actorMask != null && !actorMask.HasAnyActionTypeEnabled)
            {
                EmptyActionTypeMaskCount++;
            }
        }

        internal string BuildSummaryDump(int maxActorsToPrint = 12)
        {
            var sb = new StringBuilder(512);
            sb.AppendLine("[ActionMaskSet] Summary");
            sb.AppendLine($"  player={PlayerId}");
            sb.AppendLine($"  matchRunning={IsMatchRunning}");
            sb.AppendLine($"  noOpOnlyPhaseGate={NoOpOnlyDueToPhaseGate}");
            sb.AppendLine($"  availableActors={AvailableActorCount}/{ActionContract.TotalCells}");
            sb.AppendLine($"  emptyActionTypeMasks={EmptyActionTypeMaskCount}");
            sb.AppendLine($"  validationMismatches={ValidationMismatches.Count}");

            int printed = 0;
            for (int i = 0; i < ActionContract.TotalCells && printed < maxActorsToPrint; i++)
            {
                if (!ActorCellMask[i])
                    continue;

                var actorMask = _actorMasksByCell[i];
                if (actorMask == null)
                    continue;

                sb.AppendLine($"  actor[{i}] pos={actorMask.ActorPosition} type={actorMask.ActorType} actions={actorMask.ActionTypeMaskToString()}");
                sb.AppendLine(
                    $"    move={actorMask.DirectionMaskToString(actorMask.MoveDirectionMask)} " +
                    $"harvest={actorMask.DirectionMaskToString(actorMask.HarvestDirectionMask)} " +
                    $"return={actorMask.DirectionMaskToString(actorMask.ReturnDirectionMask)}");
                sb.AppendLine(
                    $"    produceDir={actorMask.DirectionMaskToString(actorMask.ProduceDirectionMask)} " +
                    $"produceType={actorMask.ProduceTypeMaskToString()} " +
                    $"attackLocal={actorMask.AttackTargetMaskToString()}");
                printed++;
            }

            if (ValidationMismatches.Count > 0)
            {
                int maxMismatch = Mathf.Min(ValidationMismatches.Count, 8);
                for (int i = 0; i < maxMismatch; i++)
                {
                    sb.AppendLine($"  mismatch[{i}] {ValidationMismatches[i]}");
                }
            }

            return sb.ToString();
        }
    }

    /// <summary>
    /// Parameterized mask snapshot for one transfer-compatible actor slot.
    ///
    /// The contained branch masks describe what may be sampled, not what the runtime must accept.
    /// </summary>
    public sealed class ActorActionMask
    {
        public ActorActionMask(GridPosition actorPosition, UnitType actorType)
        {
            ActorPosition = actorPosition;
            ActorType = actorType;

            ActionTypeMask = new bool[ActionContract.SIZE_ACTION_TYPE];
            MoveDirectionMask = new bool[ActionContract.SIZE_DIRECTION];
            HarvestDirectionMask = new bool[ActionContract.SIZE_DIRECTION];
            ReturnDirectionMask = new bool[ActionContract.SIZE_DIRECTION];
            ProduceDirectionMask = new bool[ActionContract.SIZE_DIRECTION];
            ProduceUnitTypeMask = new bool[ActionContract.SIZE_PRODUCE_UNIT_TYPE];
            AttackTargetLocalMask = new bool[ActionContract.SIZE_ATTACK_TARGET];
        }

        public GridPosition ActorPosition { get; }
        public UnitType ActorType { get; }

        public bool[] ActionTypeMask { get; }
        public bool[] MoveDirectionMask { get; }
        public bool[] HarvestDirectionMask { get; }
        public bool[] ReturnDirectionMask { get; }
        public bool[] ProduceDirectionMask { get; }
        public bool[] ProduceUnitTypeMask { get; }
        public bool[] AttackTargetLocalMask { get; }

        public bool HasAnyActionTypeEnabled
        {
            get
            {
                for (int i = 0; i < ActionTypeMask.Length; i++)
                {
                    if (ActionTypeMask[i])
                        return true;
                }

                return false;
            }
        }

        public bool IsActionTypeEnabled(UnitActionType actionType)
        {
            int index = (int)actionType;
            return index >= 0 && index < ActionTypeMask.Length && ActionTypeMask[index];
        }

        internal string ActionTypeMaskToString()
        {
            string value = ActionContractMappings.FormatEnabledValues(
                ActionTypeMask,
                i => ((UnitActionType)i).ToString(),
                "<none>");
            return value.Replace("|", ",");
        }

        internal string DirectionMaskToString(bool[] directionMask)
        {
            return ActionContractMappings.FormatEnabledValues(
                directionMask,
                i => ((Direction)i).ToString(),
                "-");
        }

        internal string ProduceTypeMaskToString()
        {
            return ActionContractMappings.FormatEnabledValues(
                ProduceUnitTypeMask,
                i => ActionContractMappings.TryMapV2ProduceIndexToUnitType(i, out UnitType mapped)
                    ? mapped.ToString()
                    : $"idx{i}",
                "-");
        }

        internal string AttackTargetMaskToString()
        {
            return ActionContractMappings.FormatEnabledValues(
                AttackTargetLocalMask,
                i => i.ToString(),
                "-");
        }
    }

    /// <summary>
    /// Adapted mask view for debug action format.
    ///
    /// Debug format has actor_index_flat in [0..TotalCells] where TotalCells means NoActor.
    /// </summary>
    internal sealed class DebugActionMaskSet
    {
        private readonly ActorActionMask[] _actorMasksByIndex;

        public DebugActionMaskSet(ActionMaskSet transferMask)
        {
            TransferMask = transferMask;
            _actorMasksByIndex = new ActorActionMask[ActionContract.TotalCells + 1];
            ActorIndexMask = new bool[ActionContract.TotalCells + 1];

            for (int i = 0; i < ActionContract.TotalCells; i++)
            {
                if (!transferMask.ActorCellMask[i])
                    continue;

                ActorIndexMask[i] = true;
                _actorMasksByIndex[i] = transferMask.GetActorMaskByFlatIndex(i);
            }

            // NoActor marker is always allowed as a safe debug fallback.
            ActorIndexMask[ActionContract.TotalCells] = true;
        }

        public ActionMaskSet TransferMask { get; }
        public bool[] ActorIndexMask { get; }

        internal ActorActionMask GetActorMask(int actorIndexFlat)
        {
            if (actorIndexFlat < 0 || actorIndexFlat >= _actorMasksByIndex.Length)
                return null;

            return _actorMasksByIndex[actorIndexFlat];
        }
    }

    /// <summary>
    /// Builds action masks from current Unity state.
    ///
    /// This class is a pre-sampling decision-space filter only. Authoritative runtime truth
    /// remains in ActionApplier, so any mask-allowed action may still be rejected later.
    /// </summary>
    public sealed class ActionMaskBuilder
    {
        private const int WorkerCarryCapacity = GameConstants.MaxCarryCapacity;
        private const int ProduceCostFallback = 50;

        private readonly MatchManager _matchManager;
        private readonly GridManager _gridManager;
        private readonly ResourceManager _resourceManager;
        private readonly UnitRegistry _unitRegistry;
        private readonly MatchBootstrap _matchBootstrap;

        public ActionMaskBuilder(
            MatchManager matchManager,
            GridManager gridManager,
            ResourceManager resourceManager,
            UnitRegistry unitRegistry,
            MatchBootstrap matchBootstrap = null)
        {
            _matchManager = matchManager ?? throw new ArgumentNullException(nameof(matchManager));
            _gridManager = gridManager ?? throw new ArgumentNullException(nameof(gridManager));
            _resourceManager = resourceManager;
            _unitRegistry = unitRegistry ?? throw new ArgumentNullException(nameof(unitRegistry));
            _matchBootstrap = matchBootstrap ?? MatchBootstrap.Instance;
        }

        /// <summary>
        /// When true, emits Debug.Log for each mask-method early exit due to missing definitions,
        /// insufficient resources, production rule blocks, or no valid targets.
        /// Useful for smoke-testing mask correctness without a full editor debug session.
        /// </summary>
        public bool DiagnosticLogging { get; set; }

        /// <summary>
        /// Builds the transfer-compatible action mask for one player perspective.
        ///
        /// The mask intentionally stops at pre-sampling semantics. Runtime-only constraints such
        /// as phase timing, queue state races, and apply-time contention still belong downstream.
        /// </summary>
        public ActionMaskSet BuildTransferCompatibleMask(Owner playerId, bool noOpOnlyWhenNotRunning = true)
        {
            long perfStart = Stage6B3PerformanceCounters.Begin(Stage6B3PerfMetric.LegalMaskBuild);
            var maskSet = new ActionMaskSet(playerId)
            {
                IsMatchRunning = _matchManager.Phase == MatchPhase.Running,
                NoOpOnlyDueToPhaseGate = _matchManager.Phase != MatchPhase.Running && noOpOnlyWhenNotRunning
            };

            // Unity-only runtime rule: if the match is not running, actors are masked out.
            if (_matchManager.Phase != MatchPhase.Running)
            {
                Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.LegalMaskBuild, perfStart);
                return maskSet;
            }

            for (int cellIndex = 0; cellIndex < ActionContract.TotalCells; cellIndex++)
            {
                GridPosition position = GridPosition.FromFlatIndex(cellIndex);
                UnitRuntime unit = _gridManager.GetOccupant(position);

                // Gym-semantics-compatible actor checks.
                if (!IsActorValidGym(unit, playerId))
                    continue;

                // Unity-only actor checks.
                if (!CanReceiveCommandsUnity(unit))
                    continue;

                ActorActionMask actorMask = BuildActorMask(unit);
                maskSet.SetActorMask(cellIndex, actorMask);
            }

            Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.LegalMaskBuild, perfStart);
            return maskSet;
        }

        internal DebugActionMaskSet BuildDebugMask(Owner playerId, bool noOpOnlyWhenNotRunning = true)
        {
            ActionMaskSet transferMask = BuildTransferCompatibleMask(playerId, noOpOnlyWhenNotRunning);
            return new DebugActionMaskSet(transferMask);
        }

        private ActorActionMask BuildActorMask(UnitRuntime unit)
        {
            var actorMask = new ActorActionMask(unit.GridPos, unit.Type);

            // NoOp is always available for a valid actor.
            actorMask.ActionTypeMask[(int)UnitActionType.NoOp] = true;

            BuildMoveMask(unit, actorMask);
            BuildHarvestMask(unit, actorMask);
            BuildReturnMask(unit, actorMask);
            BuildProduceMask(unit, actorMask);
            BuildAttackMask(unit, actorMask);

            return actorMask;
        }

        private void BuildMoveMask(UnitRuntime unit, ActorActionMask actorMask)
        {
            // MatchManager.TryExecuteMove() rejects building units.
            if (unit.IsBuilding)
                return;

            if (!IsActionSupportedByUnitType(unit.Type, UnitActionType.Move))
                return;

            bool anyDirection = false;
            for (int i = 0; i < ActionContract.SIZE_DIRECTION; i++)
            {
                var direction = (Direction)i;
                GridPosition target = unit.GridPos.Neighbour(direction);

                // Gym-compatible checks.
                if (!_gridManager.IsInside(target))
                    continue;

                if (_gridManager.IsCellOccupied(target))
                    continue;

                actorMask.MoveDirectionMask[i] = true;
                anyDirection = true;
            }

            if (anyDirection)
            {
                actorMask.ActionTypeMask[(int)UnitActionType.Move] = true;
            }
        }

        private void BuildHarvestMask(UnitRuntime unit, ActorActionMask actorMask)
        {
            if (!IsActionSupportedByUnitType(unit.Type, UnitActionType.Harvest))
                return;

            // Unity-only check.
            if (unit.CarriedResources >= WorkerCarryCapacity)
                return;

            bool anyDirection = false;
            for (int i = 0; i < ActionContract.SIZE_DIRECTION; i++)
            {
                var direction = (Direction)i;
                GridPosition target = unit.GridPos.Neighbour(direction);

                // Gym-compatible checks.
                if (!_gridManager.IsInside(target))
                    continue;

                ResourceNode resource = _resourceManager?.GetResourceNode(target);
                if (resource == null || resource.IsExhausted)
                    continue;

                actorMask.HarvestDirectionMask[i] = true;
                anyDirection = true;
            }

            if (anyDirection)
            {
                actorMask.ActionTypeMask[(int)UnitActionType.Harvest] = true;
            }
        }

        private void BuildReturnMask(UnitRuntime unit, ActorActionMask actorMask)
        {
            if (!IsActionSupportedByUnitType(unit.Type, UnitActionType.Return))
                return;

            // Gym-compatible check.
            if (unit.CarriedResources <= 0)
                return;

            bool anyDirection = false;
            for (int i = 0; i < ActionContract.SIZE_DIRECTION; i++)
            {
                var direction = (Direction)i;
                GridPosition target = unit.GridPos.Neighbour(direction);

                // Gym-compatible checks.
                if (!_gridManager.IsInside(target))
                    continue;

                UnitRuntime targetUnit = _gridManager.GetOccupant(target);
                if (targetUnit == null || targetUnit.Type != UnitType.Base || targetUnit.Owner != unit.Owner)
                    continue;

                actorMask.ReturnDirectionMask[i] = true;
                anyDirection = true;
            }

            if (anyDirection)
            {
                actorMask.ActionTypeMask[(int)UnitActionType.Return] = true;
            }
        }

        private void BuildProduceMask(UnitRuntime unit, ActorActionMask actorMask)
        {
            if (!IsActionSupportedByUnitType(unit.Type, UnitActionType.Produce))
                return;

            // MVP encoding: Worker + Produce = build Barracks on adjacent cell.
            // See ActionContractMappings.IsWorkerBuildBarracksAction for the full rule.
            if (ActionContractMappings.IsWorkerBuildBarracksAction(unit.Type))
            {
                BuildWorkerBuildMask(unit, actorMask);
                return;
            }

            // MatchManager.TryExecuteProduce() requires BuildingRuntime to exist.
            BuildingRuntime buildingRuntime = unit.GetComponent<BuildingRuntime>();
            if (buildingRuntime == null)
                return;

            // Unity-only check: queue status.
            if (IsProductionQueueBusy(buildingRuntime))
                return;

            bool anyDirection = false;
            for (int i = 0; i < ActionContract.SIZE_DIRECTION; i++)
            {
                var direction = (Direction)i;
                GridPosition target = unit.GridPos.Neighbour(direction);

                // Gym-compatible checks for produce direction.
                if (!_gridManager.IsInside(target))
                    continue;

                if (_gridManager.IsCellOccupied(target))
                    continue;

                actorMask.ProduceDirectionMask[i] = true;
                anyDirection = true;
            }

            bool anyUnitType = false;
            int playerResources = _matchManager.GetResources(unit.Owner);
            for (int v2ProduceIndex = 0; v2ProduceIndex < ActionContract.SIZE_PRODUCE_UNIT_TYPE; v2ProduceIndex++)
            {
                if (!ActionContractMappings.TryMapV2ProduceIndexToUnitType(v2ProduceIndex, out UnitType producedUnitType))
                    continue;

                // Runtime-aligned gate: BuildingRuntime.StartProducingUnit() fails when definition is missing.
                UnitDefinition producedDefinition = GetUnitDefinition(producedUnitType);
                if (producedDefinition == null)
                    continue;

                // Current runtime has no explicit Base/Barracks produce-type split;
                // both rely on the same BuildingRuntime.StartProducingUnit path.
                if (!CanBuildingProduceUnitType(unit.Type, producedUnitType))
                {
                    if (DiagnosticLogging) Debug.Log($"[ActionMaskBuilder] {unit.Owner} building@{unit.GridPos} ({unit.Type}): produce {producedUnitType} blocked by production rule");
                    continue;
                }

                // Gym-compatible check: affordability.
                int cost = GetProduceCost(producedDefinition);
                if (playerResources < cost)
                    continue;

                actorMask.ProduceUnitTypeMask[v2ProduceIndex] = true;
                anyUnitType = true;
            }

            if (anyDirection && anyUnitType)
            {
                actorMask.ActionTypeMask[(int)UnitActionType.Produce] = true;
            }
        }

        private void BuildWorkerBuildMask(UnitRuntime unit, ActorActionMask actorMask)
        {
            // Worker builds Barracks on an adjacent free cell.
            // v2 produce branch uses UnitType order, so Barracks build intent is slot 2.
            // MatchManager routes Worker-Produce to TryWorkerBuildBarracks.
            if (HasAliveBarracks(unit.Owner))
            {
                if (DiagnosticLogging) Debug.Log($"[ActionMaskBuilder] {unit.Owner} worker@{unit.GridPos}: build-barracks masked — owner already has a Barracks");
                return;
            }

            UnitDefinition barracksDefinition = GetUnitDefinition(UnitType.Barracks);
            if (barracksDefinition == null)
            {
                if (DiagnosticLogging) Debug.Log($"[ActionMaskBuilder] {unit.Owner} worker@{unit.GridPos}: build-barracks masked — Barracks definition missing in GameConfig");
                return;
            }

            int playerResources = _matchManager.GetResources(unit.Owner);
            int cost = GetProduceCost(barracksDefinition);
            if (playerResources < cost)
            {
                if (DiagnosticLogging) Debug.Log($"[ActionMaskBuilder] {unit.Owner} worker@{unit.GridPos}: build-barracks masked — insufficient resources ({playerResources} < {cost})");
                return;
            }

            bool anyDirection = false;
            for (int i = 0; i < ActionContract.SIZE_DIRECTION; i++)
            {
                GridPosition target = unit.GridPos.Neighbour((Direction)i);
                if (!_gridManager.IsInside(target))
                    continue;
                if (_gridManager.IsCellOccupied(target))
                    continue;

                actorMask.ProduceDirectionMask[i] = true;
                anyDirection = true;
            }

            if (!anyDirection)
            {
                if (DiagnosticLogging) Debug.Log($"[ActionMaskBuilder] {unit.Owner} worker@{unit.GridPos}: build-barracks masked — no free adjacent cell");
                return;
            }

            // v2 produce branch uses Gym/Gridnet UnitType order: Barracks is index 2.
            // Runtime ignores ProduceUnitType value for Worker actors — command means "build Barracks".
            // See ActionContractMappings.IsWorkerBuildBarracksAction for the canonical rule.
            actorMask.ProduceUnitTypeMask[2] = true;
            actorMask.ActionTypeMask[(int)UnitActionType.Produce] = true;
        }

        private bool HasAliveBarracks(Owner owner)
        {
            var units = _unitRegistry.GetUnitsByOwner(owner);
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit != null && unit.IsAlive && unit.Type == UnitType.Barracks)
                {
                    return true;
                }
            }

            return false;
        }

        private void BuildAttackMask(UnitRuntime unit, ActorActionMask actorMask)
        {
            if (!IsActionSupportedByUnitType(unit.Type, UnitActionType.Attack))
                return;

            // Runtime-aligned gate from CombatResolver semantics.
            if (!CanAttackByRuntimeDefinition(unit))
            {
                if (DiagnosticLogging) Debug.Log($"[ActionMaskBuilder] {unit.Owner} {unit.Type}@{unit.GridPos}: attack masked — no attack capability in definition (attackDamage/attackRange=0)");
                return;
            }

            bool anyTarget = false;
            UnitDefinition actorDef = GetUnitDefinition(unit.Type);
            int attackRange = actorDef != null ? actorDef.attackRange : 1;
            for (int i = 0; i < ActionContract.SIZE_ATTACK_TARGET; i++)
            {
                // v2 center slot (idx=24) is a self-target placeholder and must remain masked out.
                if (i == 24)
                    continue;

                if (!TryGetAttackTargetPosition(unit.GridPos, i, out GridPosition target))
                    continue;

                // Gym-compatible checks.
                if (target == unit.GridPos)
                    continue;

                // Per-definition range gate for v2 local 7x7 attack offsets.
                // This is not a no-op check: depending on attackRange, part of the 7x7 window
                // can be masked out as runtime-invalid for the current actor.
                int distance = unit.GridPos.ChebyshevDistance(target);
                if (distance > attackRange)
                    continue;

                UnitRuntime targetUnit = _gridManager.GetOccupant(target);
                if (targetUnit == null
                    || !targetUnit.IsAlive
                    || targetUnit.Owner == unit.Owner
                    || targetUnit.Owner == Owner.Neutral)
                    continue;

                actorMask.AttackTargetLocalMask[i] = true;
                anyTarget = true;
            }

            if (anyTarget)
            {
                actorMask.ActionTypeMask[(int)UnitActionType.Attack] = true;
            }
        }

        private bool IsActorValidGym(UnitRuntime unit, Owner playerId)
        {
            if (unit == null)
                return false;

            if (unit.Owner != playerId)
                return false;

            if (!unit.IsAlive)
                return false;

            return true;
        }

        private bool CanReceiveCommandsUnity(UnitRuntime unit)
        {
            // Unity-only gate for commandable actors on this step.
            return unit.Type != UnitType.Resource;
        }

        private bool IsActionSupportedByUnitType(UnitType unitType, UnitActionType actionType)
        {
            // Keep this aligned with ActionApplier, then tighten with runtime-only gates
            // in specific builders (Move/Attack/Produce) to reduce semantic drift.
            return actionType switch
            {
                UnitActionType.NoOp => true,
                UnitActionType.Move => unitType != UnitType.Resource,
                UnitActionType.Harvest => unitType == UnitType.Worker,
                UnitActionType.Return => unitType == UnitType.Worker,
                UnitActionType.Produce => unitType == UnitType.Base || unitType == UnitType.Barracks || unitType == UnitType.Worker,
                UnitActionType.Attack => unitType != UnitType.Resource,
                _ => false
            };
        }

        private bool IsProductionQueueBusy(BuildingRuntime buildingRuntime)
        {
            ProductionQueue queue = buildingRuntime.GetProductionQueue();
            return queue != null && queue.IsProducing;
        }

        private int GetProduceCost(UnitDefinition definition)
        {
            if (definition != null && definition.productionCost > 0)
            {
                return definition.productionCost;
            }

            return ProduceCostFallback;
        }

        private bool CanAttackByRuntimeDefinition(UnitRuntime unit)
        {
            UnitDefinition definition = GetUnitDefinition(unit.Type);
            if (definition == null)
            {
                // Fallback to ActionApplier-compatible behavior when definition is missing.
                return unit.Type != UnitType.Resource;
            }

            return definition.attackDamage > 0 && definition.attackRange > 0;
        }

        private bool CanBuildingProduceUnitType(UnitType buildingType, UnitType producedUnitType)
        {
            // Production rules aligned with Gym-µRTS / microRTS:
            //   Base     → Worker only
            //   Barracks → Light, Heavy, Ranged only
            return buildingType switch
            {
                UnitType.Base     => producedUnitType == UnitType.Worker,
                UnitType.Barracks => producedUnitType == UnitType.Light
                                  || producedUnitType == UnitType.Heavy
                                  || producedUnitType == UnitType.Ranged,
                _                 => false
            };
        }

        private UnitDefinition GetUnitDefinition(UnitType unitType)
        {
            GameConfig config = _matchBootstrap != null ? _matchBootstrap.GetConfig() : null;
            return config != null ? config.GetDefinition(unitType) : null;
        }

        private bool TryGetAttackTargetPosition(GridPosition actorPosition, int localIndex, out GridPosition target)
        {
            target = GridPosition.Zero;

            return ActionContractMappings.TryGetAttackTargetPosition(actorPosition, localIndex, out target)
                   && _gridManager.IsInside(target);
        }
    }
}
