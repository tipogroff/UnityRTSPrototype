// ActionApplier.cs — convert AgentAction to MatchCommand and apply through MatchManager
// Week 3, Day 3: Apply decoded action(s) to game engine
//
// Responsibilities:
// - Validate AgentAction against game state (server-side validation, not just masks)
// - Conflict resolution for multi-command batches (first-wins per actor per step)
// - Convert AgentAction → MatchCommand
// - Submit command to MatchManager.ApplyCommand()
// - Track acceptance/rejection for diagnostics
//
// Multi-command semantics (transfer-compatible batch):
// - ApplyActions() processes a List<AgentAction> from DecodeTransferCompatibleBatch()
// - Policy: at most ONE command per actor per step (first-wins on duplicates)
// - All validations are deterministic and logged
// - Debug single-action format flows through the same ApplyAction() method
//
// Conflict resolution policy:
// - Duplicate actor positions: first command in list wins, rest rejected with explicit reason
// - Empty cell (no unit at ActorPosition): rejected
// - Wrong owner: rejected
// - Dead unit: rejected
// - MatchManager rejection: counted and logged

using System.Collections.Generic;
using UnityEngine;
using RTS.Core;
using RTS.Gameplay;

namespace RTS.ML
{
    /// <summary>
    /// Classification of why an action was rejected or surfaced as invalid.
    ///
    /// These categories are diagnostic only. They do not alter authoritative runtime behavior.
    /// </summary>
    public enum InvalidAttemptCategory
    {
        ObservationMismatch,
        MaskMismatch,
        RuntimeOnlyConstraint,
        InvalidInput,
        ExpectedFallback
    }

    /// <summary>
    /// Structured record emitted when ActionApplier rejects or classifies an invalid attempt.
    ///
    /// The log captures decoder-side metadata, mask state at selection time, and the final
    /// authoritative rejection reason. It should not be interpreted as proof that masks replace
    /// runtime validation.
    /// </summary>
    public readonly struct InvalidActionAttemptLog
    {
        public InvalidActionAttemptLog(
            Owner player,
            GridPosition actorPosition,
            int actorFlatIndex,
            string sourceActionFormat,
            UnitActionType requestedActionType,
            Direction direction,
            ProducibleUnit produceType,
            GridPosition attackTarget,
            bool decoderIsValid,
            string decoderReason,
            string maskState,
            bool accepted,
            string rejectionReason,
            InvalidAttemptCategory category)
        {
            Player = player;
            ActorPosition = actorPosition;
            ActorFlatIndex = actorFlatIndex;
            SourceActionFormat = sourceActionFormat;
            RequestedActionType = requestedActionType;
            Direction = direction;
            ProduceType = produceType;
            AttackTarget = attackTarget;
            DecoderIsValid = decoderIsValid;
            DecoderReason = decoderReason;
            MaskState = maskState;
            Accepted = accepted;
            RejectionReason = rejectionReason;
            Category = category;
        }

        public Owner Player { get; }
        public GridPosition ActorPosition { get; }
        public int ActorFlatIndex { get; }
        public string SourceActionFormat { get; }
        public UnitActionType RequestedActionType { get; }
        public Direction Direction { get; }
        public ProducibleUnit ProduceType { get; }
        public GridPosition AttackTarget { get; }
        public bool DecoderIsValid { get; }
        public string DecoderReason { get; }
        public string MaskState { get; }
        public bool Accepted { get; }
        public string RejectionReason { get; }
        public InvalidAttemptCategory Category { get; }

        public string ToCompactString()
        {
            return
                $"player={Player}, actor={ActorPosition}#{ActorFlatIndex}, source={SourceActionFormat}, " +
                $"type={RequestedActionType}, dir={Direction}, produce={ProduceType}, target={AttackTarget}, " +
                $"decoderValid={DecoderIsValid}, accepted={Accepted}, category={Category}, " +
                $"reason={RejectionReason}, decoderReason={DecoderReason}, mask={MaskState}";
        }
    }

    /// <summary>
    /// Applies AgentAction to the game engine.
    /// 
    /// Validates action against current game state and converts to MatchCommand.
    /// This is the authoritative server-side validation layer that always runs regardless of mask.
    /// </summary>
    public class ActionApplier
    {
        private readonly GridManager _gridManager;
        private readonly UnitRegistry _unitRegistry;
        private readonly MatchManager _matchManager;
        private readonly ResourceManager _resourceManager;
        private readonly MatchBootstrap _matchBootstrap;
        private readonly List<string> _rejectionReasonsLastStep;

        // Diagnostics tracking
        public int AcceptedActionsLastStep { get; private set; }
        public int RejectedActionsLastStep { get; private set; }
        public IReadOnlyList<string> RejectionReasonsLastStep => _rejectionReasonsLastStep;
        public InvalidActionAttemptLog? LastInvalidAttempt { get; private set; }

        public event System.Action<InvalidActionAttemptLog> OnInvalidActionAttempt;

        public ActionApplier(GridManager gridManager, UnitRegistry unitRegistry, MatchManager matchManager, ResourceManager resourceManager = null)
        {
            _gridManager = gridManager ?? throw new System.ArgumentNullException(nameof(gridManager));
            _unitRegistry = unitRegistry ?? throw new System.ArgumentNullException(nameof(unitRegistry));
            _matchManager = matchManager ?? throw new System.ArgumentNullException(nameof(matchManager));
            _resourceManager = resourceManager ?? ResourceManager.Instance;
            _matchBootstrap = MatchBootstrap.Instance;

            _rejectionReasonsLastStep = new List<string>();
            ResetDiagnostics();
        }

        /// <summary>
        /// Applies one decoded action through the authoritative runtime validation path.
        ///
        /// Masks are not consulted here. This is the production contract surface that always
        /// defers final truth to ActionApplier and MatchManager.
        /// </summary>
        public bool ApplyAction(AgentAction action, Owner playerPerspective)
        {
            return ApplyAction(action, playerPerspective, null, null);
        }

        /// <summary>
        /// Applies one decoded action with optional diagnostic context.
        ///
        /// This overload is assembly-local so smoke tests, heuristics, and the policy facade can
        /// preserve selection-time mask/source context without expanding the public production API.
        /// </summary>
        internal bool ApplyAction(AgentAction action, Owner playerPerspective, ActionMaskSet maskAtSelection, string sourceActionFormat)
        {
            string sourceFormat = ResolveSourceFormat(action, sourceActionFormat);
            string maskState = BuildMaskStateForAction(maskAtSelection, action);

            if (!action.IsValid)
            {
                string reason = string.IsNullOrWhiteSpace(action.InvalidationReason)
                    ? "Decoder marked action invalid"
                    : $"Decoder marked action invalid: {action.InvalidationReason}";
                RecordRejectionDetailed(action, playerPerspective, reason, maskState, sourceFormat, InvalidAttemptCategory.InvalidInput);
                return false;
            }

            // Early exit for NoOp
            if (action.ActionType == UnitActionType.NoOp)
            {
                return true;
            }

            // Authoritative phase validation: reject if match is not in Running state.
            // This check runs for every action regardless of source (single or batch).
            if (_matchManager.Phase != MatchPhase.Running)
            {
                RecordRejectionDetailed(
                    action,
                    playerPerspective,
                    $"Match is not in Running phase (current: {_matchManager.Phase})",
                    maskState,
                    sourceFormat,
                    InvalidAttemptCategory.RuntimeOnlyConstraint);
                return false;
            }

            // Validate actor exists
            var unit = _gridManager.GetOccupant(action.ActorPosition);
            if (unit == null)
            {
                var reason = $"Actor does not exist at {action.ActorPosition}";
                RecordRejectionDetailed(action, playerPerspective, reason, maskState, sourceFormat, InferCategoryFromMask(maskAtSelection, action, InvalidAttemptCategory.InvalidInput));
                return false;
            }

            // Validate actor belongs to correct player
            if (unit.Owner != playerPerspective)
            {
                var reason = $"Actor at {action.ActorPosition} belongs to {unit.Owner}, not {playerPerspective}";
                RecordRejectionDetailed(action, playerPerspective, reason, maskState, sourceFormat, InferCategoryFromMask(maskAtSelection, action, InvalidAttemptCategory.InvalidInput));
                return false;
            }

            // Validate actor is alive
            if (!unit.IsAlive)
            {
                var reason = $"Actor at {action.ActorPosition} is dead";
                RecordRejectionDetailed(action, playerPerspective, reason, maskState, sourceFormat, InferCategoryFromMask(maskAtSelection, action, InvalidAttemptCategory.InvalidInput));
                return false;
            }

            // Coarse gate: cheap unit-type constraints before deeper runtime checks.
            if (!IsActionTypeCoarseSupportedByUnitType(unit.Type, action.ActionType))
            {
                var reason = $"Unit type {unit.Type} does not support action {action.ActionType}";
                RecordRejectionDetailed(action, playerPerspective, reason, maskState, sourceFormat, InferCategoryFromMask(maskAtSelection, action, InvalidAttemptCategory.RuntimeOnlyConstraint));
                return false;
            }

            // Runtime-authoritative capability gate for action semantics that depend
            // on current Unity runtime definitions (for example attack capability).
            if (!ValidateRuntimeCapabilityGate(unit, action.ActionType, out var runtimeGateReason))
            {
                RecordRejectionDetailed(action, playerPerspective, runtimeGateReason, maskState, sourceFormat, InferCategoryFromMask(maskAtSelection, action, InvalidAttemptCategory.RuntimeOnlyConstraint));
                return false;
            }

            // Action-specific validation
            ProducibleUnit commandProduceType = action.ProduceUnitType;
            switch (action.ActionType)
            {
                case UnitActionType.Move:
                    if (!ValidateMoveAction(unit, action, out var moveReason))
                    {
                        RecordRejectionDetailed(action, playerPerspective, moveReason, maskState, sourceFormat, InferCategoryFromMask(maskAtSelection, action, InvalidAttemptCategory.RuntimeOnlyConstraint));
                        return false;
                    }
                    break;

                case UnitActionType.Harvest:
                    if (!ValidateHarvestAction(unit, action, out var harvestReason))
                    {
                        RecordRejectionDetailed(action, playerPerspective, harvestReason, maskState, sourceFormat, InferCategoryFromMask(maskAtSelection, action, InvalidAttemptCategory.RuntimeOnlyConstraint));
                        return false;
                    }
                    break;

                case UnitActionType.Return:
                    if (!ValidateReturnAction(unit, action, out var returnReason))
                    {
                        RecordRejectionDetailed(action, playerPerspective, returnReason, maskState, sourceFormat, InferCategoryFromMask(maskAtSelection, action, InvalidAttemptCategory.RuntimeOnlyConstraint));
                        return false;
                    }
                    break;

                case UnitActionType.Produce:
                    if (!ValidateProduceAction(unit, action, out commandProduceType, out var produceReason))
                    {
                        RecordRejectionDetailed(action, playerPerspective, produceReason, maskState, sourceFormat, InferCategoryFromMask(maskAtSelection, action, InvalidAttemptCategory.RuntimeOnlyConstraint));
                        return false;
                    }
                    break;

                case UnitActionType.Attack:
                    if (!ValidateAttackAction(unit, action, out var attackReason))
                    {
                        RecordRejectionDetailed(action, playerPerspective, attackReason, maskState, sourceFormat, InferCategoryFromMask(maskAtSelection, action, InvalidAttemptCategory.RuntimeOnlyConstraint));
                        return false;
                    }
                    break;
            }

            // All validations passed, construct and apply command
            var command = new MatchCommand(
                owner: playerPerspective,
                unitPosition: action.ActorPosition,
                actionType: action.ActionType,
                direction: action.Direction,
                // IMPORTANT: v2 produce branch index (0..6) is carried in AgentAction for
                // authoritative validation only. MatchCommand still expects runtime produce enum.
                produceUnitType: commandProduceType,
                attackTarget: action.AttackTargetPosition,
                hasAttackTarget: action.ActionType == UnitActionType.Attack);

            bool applied = _matchManager.ApplyCommand(command);
            if (applied)
            {
                AcceptedActionsLastStep++;
            }
            else
            {
                RecordRejectionDetailed(
                    action,
                    playerPerspective,
                    "MatchManager rejected command",
                    maskState,
                    sourceFormat,
                    InferCategoryFromMask(maskAtSelection, action, InvalidAttemptCategory.RuntimeOnlyConstraint));
            }

            return applied;
        }

        /// <summary>
        /// Applies a transfer-compatible batch in flat-index order.
        ///
        /// Duplicate actor commands follow the current first-wins policy. Even when the batch came
        /// from a mask-aware policy, authoritative validation still happens for every action here.
        /// </summary>
        public int ApplyActions(IReadOnlyList<AgentAction> actions, Owner playerPerspective)
        {
            return ApplyActions(actions, playerPerspective, null, null);
        }

        /// <summary>
        /// Applies a batch with optional diagnostic context for assembly-local tooling.
        /// </summary>
        internal int ApplyActions(IReadOnlyList<AgentAction> actions, Owner playerPerspective, ActionMaskSet maskAtSelection, string sourceActionFormat)
        {
            ResetDiagnostics();

            if (actions == null || actions.Count == 0)
                return 0;

            // First-wins conflict resolution: track actor positions commanded this step.
            var processedActors = new System.Collections.Generic.HashSet<GridPosition>();

            foreach (var action in actions)
            {
                // NoOp actions do not consume an actor slot
                if (action.ActionType == UnitActionType.NoOp)
                    continue;

                // Conflict check: reject duplicate commands for the same actor
                if (!processedActors.Add(action.ActorPosition))
                {
                    RecordRejection($"Duplicate command for actor at {action.ActorPosition}: already processed this step (first-wins policy)");
                    continue;
                }

                ApplyAction(action, playerPerspective, maskAtSelection, sourceActionFormat);
            }

            return AcceptedActionsLastStep;
        }

        /// <summary>
        /// Resets per-step diagnostics for assembly-local smoke and integration tooling.
        /// </summary>
        internal void ResetDiagnostics()
        {
            AcceptedActionsLastStep = 0;
            RejectedActionsLastStep = 0;
            _rejectionReasonsLastStep.Clear();
            LastInvalidAttempt = null;
        }

        // ── Private Helpers ────────────────────────────────────────────────

        private bool IsActionTypeCoarseSupportedByUnitType(UnitType unitType, UnitActionType actionType)
        {
            // Coarse static gate by unit type. Keep this broad and cheap.
            // Runtime-specific capability checks are handled in ValidateRuntimeCapabilityGate().
            return actionType switch
            {
                UnitActionType.NoOp => true,  // All units

                UnitActionType.Move => unitType != UnitType.Resource && unitType != UnitType.Base && unitType != UnitType.Barracks,
                
                UnitActionType.Harvest => unitType == UnitType.Worker,  // Only workers
                
                UnitActionType.Return => unitType == UnitType.Worker,  // Only workers
                
                UnitActionType.Produce => unitType == UnitType.Base || unitType == UnitType.Barracks || unitType == UnitType.Worker,  // Buildings produce; Workers build Barracks
                
                UnitActionType.Attack => unitType != UnitType.Resource,
                
                _ => false
            };
        }

        private bool ValidateRuntimeCapabilityGate(UnitRuntime unit, UnitActionType actionType, out string reason)
        {
            reason = string.Empty;

            switch (actionType)
            {
                case UnitActionType.Move:
                    if (unit.IsBuilding)
                    {
                        reason = $"Unit type {unit.Type} cannot move in runtime (building)";
                        return false;
                    }
                    break;

                case UnitActionType.Attack:
                    if (!CanAttackByRuntimeDefinition(unit))
                    {
                        reason = $"Unit type {unit.Type} has no runtime attack capability";
                        return false;
                    }
                    break;
            }

            return true;
        }

        private bool ValidateMoveAction(UnitRuntime unit, AgentAction action, out string reason)
        {
            reason = "";

            // Decode target position from direction
            var targetPos = GetPositionInDirection(unit.GridPos, action.Direction);

            // Validate target is in bounds
            if (!targetPos.IsInsideMap())
            {
                reason = $"Move target {targetPos} is out of bounds";
                return false;
            }

            // Validate target is not occupied
            var targetUnit = _gridManager.GetOccupant(targetPos);
            if (targetUnit != null)
            {
                reason = $"Move target {targetPos} is occupied by {targetUnit.Type}";
                return false;
            }

            return true;
        }

        private bool ValidateHarvestAction(UnitRuntime unit, AgentAction action, out string reason)
        {
            reason = "";

            // Only workers harvest
            if (unit.Type != UnitType.Worker)
            {
                reason = "Only workers can harvest";
                return false;
            }

            // Decode target position
            var targetPos = GetPositionInDirection(unit.GridPos, action.Direction);

            // Validate target is valid
            if (!targetPos.IsInsideMap())
            {
                reason = $"Harvest target {targetPos} is out of bounds";
                return false;
            }

            // Validate there's a resource at target
            var resource = _resourceManager?.GetResourceNode(targetPos);
            if (resource == null || resource.IsExhausted)
            {
                reason = $"No active resource at harvest target {targetPos}";
                return false;
            }

            // Validate worker has free carry capacity (max 100)
            if (unit.CarriedResources >= 100)
            {
                reason = $"Worker already carrying {unit.CarriedResources} resources (max 100)";
                return false;
            }

            return true;
        }

        private bool ValidateReturnAction(UnitRuntime unit, AgentAction action, out string reason)
        {
            reason = "";

            // Only workers return
            if (unit.Type != UnitType.Worker)
            {
                reason = "Only workers can return resources";
                return false;
            }

            // Validate worker is carrying resources
            if (unit.CarriedResources <= 0)
            {
                reason = "Worker is not carrying any resources";
                return false;
            }

            // Decode target position
            var targetPos = GetPositionInDirection(unit.GridPos, action.Direction);

            // Validate target is valid
            if (!targetPos.IsInsideMap())
            {
                reason = $"Return target {targetPos} is out of bounds";
                return false;
            }

            // Validate there's a base at target belonging to player
            var targetUnit = _gridManager.GetOccupant(targetPos);
            if (targetUnit == null || targetUnit.Type != UnitType.Base || targetUnit.Owner != unit.Owner)
            {
                reason = $"No friendly base at return target {targetPos}";
                return false;
            }

            return true;
        }

        private bool ValidateProduceAction(UnitRuntime unit, AgentAction action, out ProducibleUnit runtimeProduceType, out string reason)
        {
            reason = "";
            runtimeProduceType = ProducibleUnit.Worker;

            // v2 contract note:
            // - produce branch index follows UnitType/Gym order [0..6]
            // - branch-bound decode does NOT imply runtime validity
            // - ActionApplier remains authoritative runtime truth
            int produceBranchIndex = (int)action.ProduceUnitType;
            if (!ActionContractMappings.TryMapV2ProduceIndexToUnitType(produceBranchIndex, out UnitType producedUnitType))
            {
                reason = $"Produce index {produceBranchIndex} is out of v2 range [0..{ActionContract.SIZE_PRODUCE_UNIT_TYPE - 1}]";
                return false;
            }

            // MVP encoding: Worker + Produce = build Barracks on adjacent cell.
            // In v2 ordering this is index 2 (Barracks).
            if (ActionContractMappings.IsWorkerBuildBarracksAction(unit.Type))
            {
                if (produceBranchIndex != 2)
                {
                    reason = $"Worker Produce accepts only v2 index 2 (Barracks build), got {produceBranchIndex} ({producedUnitType})";
                    return false;
                }

                runtimeProduceType = ProducibleUnit.Worker; // placeholder; MatchManager worker-produce path ignores produce type
                return ValidateWorkerBuildBarracks(unit, action, out reason);
            }

            // Only Base and Barracks can produce units
            if (unit.Type != UnitType.Base && unit.Type != UnitType.Barracks)
            {
                reason = $"Unit type {unit.Type} cannot produce";
                return false;
            }

            // Validate v2 branch index is allowed for this building type.
            if (!IsProduceIndexAllowedForBuilding(unit.Type, produceBranchIndex))
            {
                reason = $"{unit.Type} cannot produce v2 index {produceBranchIndex} ({producedUnitType}) (rule: Worker-build->2, Base->3, Barracks->4/5/6)";
                return false;
            }

            if (!TryMapProducedUnitTypeToRuntimeProduceType(producedUnitType, out runtimeProduceType))
            {
                reason = $"Produced UnitType {producedUnitType} is not a runtime producible unit";
                return false;
            }

            // Resolve production cost from UnitDefinition — aligned with BuildingRuntime.StartProducingUnit,
            // which is the authoritative cost deduction path. Falls back to 50 if definition is missing.
            GameConfig produceConfig = _matchBootstrap?.GetConfig();
            UnitDefinition producedDef = produceConfig?.GetDefinition(producedUnitType);
            int unitCost = producedDef != null && producedDef.productionCost > 0 ? producedDef.productionCost : 50;
            int playerResources = _matchManager.GetResources(unit.Owner);

            // Validate enough resources
            if (playerResources < unitCost)
            {
                reason = $"Not enough resources ({playerResources} < {unitCost} for {producedUnitType})";
                return false;
            }

            // Validate production queue is not busy
            var buildingRuntime = unit.GetComponent<BuildingRuntime>();
            if (buildingRuntime != null)
            {
                var queue = buildingRuntime.GetProductionQueue();
                if (queue != null && queue.IsProducing)
                {
                    reason = $"Production queue is busy (already producing {queue.CurrentProducingType})";
                    return false;
                }
            }

            return true;
        }

        private bool ValidateWorkerBuildBarracks(UnitRuntime unit, AgentAction action, out string reason)
        {
            reason = "";

            if (HasAliveBarracks(unit.Owner))
            {
                reason = "Cannot build Barracks: owner already has one alive Barracks";
                return false;
            }

            var config = _matchBootstrap?.GetConfig();
            var barracksDefinition = config?.GetDefinition(UnitType.Barracks);
            if (barracksDefinition == null)
            {
                reason = "Barracks UnitDefinition is not configured in GameConfig";
                return false;
            }

            var targetPos = GetPositionInDirection(unit.GridPos, action.Direction);

            if (!targetPos.IsInsideMap())
            {
                reason = $"Build target {targetPos} is out of bounds";
                return false;
            }

            if (_gridManager.IsCellOccupied(targetPos))
            {
                reason = $"Build target {targetPos} is occupied";
                return false;
            }

            int cost = barracksDefinition.productionCost;
            int playerResources = _matchManager.GetResources(unit.Owner);
            if (playerResources < cost)
            {
                reason = $"Not enough resources to build Barracks ({playerResources} < {cost})";
                return false;
            }

            return true;
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

        private static bool IsProduceIndexAllowedForBuilding(UnitType buildingType, int produceBranchIndex)
        {
            // v2 UnitType/Gym order indices:
            // 0 Resource (reject), 1 Base (reject), 2 Barracks (worker-build only),
            // 3 Worker, 4 Light, 5 Heavy, 6 Ranged.
            return buildingType switch
            {
                UnitType.Base     => produceBranchIndex == 3,
                UnitType.Barracks => produceBranchIndex == 4
                                  || produceBranchIndex == 5
                                  || produceBranchIndex == 6,
                _                 => false
            };
        }

        private static bool TryMapProducedUnitTypeToRuntimeProduceType(UnitType producedUnitType, out ProducibleUnit runtimeProduceType)
        {
            runtimeProduceType = producedUnitType switch
            {
                UnitType.Worker => ProducibleUnit.Worker,
                UnitType.Light => ProducibleUnit.Light,
                UnitType.Heavy => ProducibleUnit.Heavy,
                UnitType.Ranged => ProducibleUnit.Ranged,
                _ => ProducibleUnit.Worker
            };

            return producedUnitType == UnitType.Worker
                   || producedUnitType == UnitType.Light
                   || producedUnitType == UnitType.Heavy
                   || producedUnitType == UnitType.Ranged;
        }

        private bool ValidateAttackAction(UnitRuntime unit, AgentAction action, out string reason)
        {
            reason = "";

            // Runtime authority note:
            // v2 branch expansion (7x7 / 49) only makes more local targets representable.
            // It does NOT weaken runtime validation. ActionApplier remains authoritative truth:
            // self-target, out-of-bounds, empty/friendly targets, and range violations are rejected safely.

            // Can all non-resource units attack?
            if (unit.Type == UnitType.Resource)
            {
                reason = "Resources cannot attack";
                return false;
            }

            // Validate target is in bounds
            if (!action.AttackTargetPosition.IsInsideMap())
            {
                reason = $"Attack target {action.AttackTargetPosition} is out of bounds";
                return false;
            }

            // Validate target is not self
            if (action.AttackTargetPosition == unit.GridPos)
            {
                reason = "Cannot attack self";
                return false;
            }

            // Validate target within unit's definition-driven attack range.
            // NOTE: with v2 action contract, commanded targets come from local 7x7 offsets.
            // This guard is therefore active and can reject out-of-range targets depending on
            // actor definition (attackRange) and selected local index.
            var unitDef = _matchBootstrap?.GetConfig()?.GetDefinition(unit.Type);
            int maxRange = unitDef != null ? unitDef.attackRange : 1;
            int chebyshev = unit.GridPos.ChebyshevDistance(action.AttackTargetPosition);
            if (chebyshev > maxRange)
            {
                reason = $"Attack target {action.AttackTargetPosition} is out of range for {unit.Type} (range={maxRange}, distance={chebyshev})";
                return false;
            }

            // Validate there's an enemy unit at target
            var targetUnit = _gridManager.GetOccupant(action.AttackTargetPosition);
            if (targetUnit == null || targetUnit.Owner == unit.Owner || targetUnit.Owner == Owner.Neutral)
            {
                reason = $"No enemy unit at attack target {action.AttackTargetPosition}";
                return false;
            }

            return true;
        }

        // Coordinate convention: North=+Y, South=-Y, East=+X, West=-X.
        // Matches GridPosition.Neighbour(Direction) — delegate to avoid duplication.
        private GridPosition GetPositionInDirection(GridPosition from, Direction direction)
            => from.Neighbour(direction);

        private void RecordRejection(string reason)
        {
            RejectedActionsLastStep++;
            _rejectionReasonsLastStep.Add(reason);
        }

        private void RecordRejectionDetailed(
            AgentAction action,
            Owner playerPerspective,
            string reason,
            string maskState,
            string sourceActionFormat,
            InvalidAttemptCategory category)
        {
            RecordRejection(reason);

            var logEntry = new InvalidActionAttemptLog(
                player: playerPerspective,
                actorPosition: action.ActorPosition,
                actorFlatIndex: action.ActorPosition.IsInsideMap() ? action.ActorPosition.ToFlatIndex() : -1,
                sourceActionFormat: sourceActionFormat,
                requestedActionType: action.ActionType,
                direction: action.Direction,
                produceType: action.ProduceUnitType,
                attackTarget: action.AttackTargetPosition,
                decoderIsValid: action.IsValid,
                decoderReason: action.InvalidationReason,
                maskState: maskState,
                accepted: false,
                rejectionReason: reason,
                category: category);

            LastInvalidAttempt = logEntry;
            OnInvalidActionAttempt?.Invoke(logEntry);
            Debug.LogWarning($"[ActionApplier][InvalidAttempt] {logEntry.ToCompactString()}");
        }

        private string ResolveSourceFormat(AgentAction action, string sourceActionFormat)
        {
            if (!string.IsNullOrWhiteSpace(sourceActionFormat))
                return sourceActionFormat;

            return action.SourceType switch
            {
                ActionSourceType.TransferCompatible => "transfer",
                ActionSourceType.Debug => "debug",
                _ => "unknown"
            };
        }

        private InvalidAttemptCategory InferCategoryFromMask(ActionMaskSet maskAtSelection, AgentAction action, InvalidAttemptCategory fallback)
        {
            if (action.ActionType == UnitActionType.NoOp && !action.IsValid)
                return InvalidAttemptCategory.ExpectedFallback;

            if (maskAtSelection == null)
                return fallback;

            if (!action.ActorPosition.IsInsideMap())
                return InvalidAttemptCategory.InvalidInput;

            int actorIndex = action.ActorPosition.ToFlatIndex();
            if (actorIndex < 0 || actorIndex >= ActionContract.TotalCells)
                return InvalidAttemptCategory.InvalidInput;

            if (!maskAtSelection.ActorCellMask[actorIndex])
                return InvalidAttemptCategory.MaskMismatch;

            ActorActionMask actorMask = maskAtSelection.GetActorMaskByFlatIndex(actorIndex);
            if (actorMask != null && !actorMask.IsActionTypeEnabled(action.ActionType))
                return InvalidAttemptCategory.MaskMismatch;

            return fallback;
        }

        private string BuildMaskStateForAction(ActionMaskSet maskAtSelection, AgentAction action)
        {
            if (maskAtSelection == null)
                return "mask:none";

            if (!action.ActorPosition.IsInsideMap())
                return $"mask:actor-out-of-bounds pos={action.ActorPosition}";

            int actorIndex = action.ActorPosition.ToFlatIndex();
            if (actorIndex < 0 || actorIndex >= ActionContract.TotalCells)
                return $"mask:actor-index-invalid index={actorIndex}";

            bool actorEnabled = maskAtSelection.ActorCellMask[actorIndex];
            ActorActionMask actorMask = maskAtSelection.GetActorMaskByFlatIndex(actorIndex);
            string actionEnabled = actorMask != null
                ? actorMask.IsActionTypeEnabled(action.ActionType).ToString()
                : "false";
            string availableActions = actorMask != null ? actorMask.ActionTypeMaskToString() : "<none>";

            return
                $"mask:actorEnabled={actorEnabled}, actionEnabled={actionEnabled}, " +
                $"availableActions={availableActions}, matchRunning={maskAtSelection.IsMatchRunning}";
        }

        private bool CanAttackByRuntimeDefinition(UnitRuntime unit)
        {
            MatchBootstrap bootstrap = _matchBootstrap ?? MatchBootstrap.Instance;
            GameConfig config = bootstrap != null ? bootstrap.GetConfig() : null;
            UnitDefinition definition = config != null ? config.GetDefinition(unit.Type) : null;

            if (definition == null)
            {
                // Fallback: preserve previous broad behavior if definitions are unavailable.
                return unit.Type != UnitType.Resource;
            }

            return definition.attackDamage > 0 && definition.attackRange > 0;
        }
    }
}
