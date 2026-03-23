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

        // Diagnostics tracking
        public int AcceptedActionsLastStep { get; private set; }
        public int RejectedActionsLastStep { get; private set; }
        public List<string> RejectionReasonsLastStep { get; private set; }

        public ActionApplier(GridManager gridManager, UnitRegistry unitRegistry, MatchManager matchManager, ResourceManager resourceManager = null)
        {
            _gridManager = gridManager ?? throw new System.ArgumentNullException(nameof(gridManager));
            _unitRegistry = unitRegistry ?? throw new System.ArgumentNullException(nameof(unitRegistry));
            _matchManager = matchManager ?? throw new System.ArgumentNullException(nameof(matchManager));
            _resourceManager = resourceManager ?? ResourceManager.Instance;

            RejectionReasonsLastStep = new List<string>();
            ResetDiagnostics();
        }

        /// <summary>
        /// Apply a single AgentAction.
        /// 
        /// Returns:
        ///   true  - action was accepted and applied
        ///   false - action was rejected (check RejectionReasonsLastStep for reason)
        /// </summary>
        public bool ApplyAction(AgentAction action, Owner playerPerspective)
        {
            // Early exit for NoOp
            if (action.ActionType == UnitActionType.NoOp)
            {
                return true;
            }

            // Authoritative phase validation: reject if match is not in Running state.
            // This check runs for every action regardless of source (single or batch).
            if (_matchManager.Phase != MatchPhase.Running)
            {
                RecordRejection($"Match is not in Running phase (current: {_matchManager.Phase})");
                return false;
            }

            // Validate actor exists
            var unit = _gridManager.GetOccupant(action.ActorPosition);
            if (unit == null)
            {
                var reason = $"Actor does not exist at {action.ActorPosition}";
                RecordRejection(reason);
                return false;
            }

            // Validate actor belongs to correct player
            if (unit.Owner != playerPerspective)
            {
                var reason = $"Actor at {action.ActorPosition} belongs to {unit.Owner}, not {playerPerspective}";
                RecordRejection(reason);
                return false;
            }

            // Validate actor is alive
            if (!unit.IsAlive)
            {
                var reason = $"Actor at {action.ActorPosition} is dead";
                RecordRejection(reason);
                return false;
            }

            // Validate action type is supported by actor type
            if (!IsActionSupportedByUnitType(unit.Type, action.ActionType))
            {
                var reason = $"Unit type {unit.Type} does not support action {action.ActionType}";
                RecordRejection(reason);
                return false;
            }

            // Action-specific validation
            switch (action.ActionType)
            {
                case UnitActionType.Move:
                    if (!ValidateMoveAction(unit, action, out var moveReason))
                    {
                        RecordRejection(moveReason);
                        return false;
                    }
                    break;

                case UnitActionType.Harvest:
                    if (!ValidateHarvestAction(unit, action, out var harvestReason))
                    {
                        RecordRejection(harvestReason);
                        return false;
                    }
                    break;

                case UnitActionType.Return:
                    if (!ValidateReturnAction(unit, action, out var returnReason))
                    {
                        RecordRejection(returnReason);
                        return false;
                    }
                    break;

                case UnitActionType.Produce:
                    if (!ValidateProduceAction(unit, action, out var produceReason))
                    {
                        RecordRejection(produceReason);
                        return false;
                    }
                    break;

                case UnitActionType.Attack:
                    if (!ValidateAttackAction(unit, action, out var attackReason))
                    {
                        RecordRejection(attackReason);
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
                produceUnitType: action.ProduceUnitType,
                attackTarget: action.AttackTargetPosition,
                hasAttackTarget: action.ActionType == UnitActionType.Attack);

            bool applied = _matchManager.ApplyCommand(command);
            if (applied)
            {
                AcceptedActionsLastStep++;
            }
            else
            {
                RecordRejection("MatchManager rejected command");
            }

            return applied;
        }

        /// <summary>
        /// Apply a batch of AgentActions from DecodeTransferCompatibleBatch() in one step.
        ///
        /// Conflict resolution (first-wins per actor):
        /// - Each actor (GridPosition) may receive at most ONE command per step.
        /// - If multiple commands reference the same actor position, only the first
        ///   (by list order, which equals flat-index scan order 0..TotalCells-1) is applied.
        /// - Subsequent commands for the same actor are rejected with reason:
        ///   "Duplicate command for actor at {pos}: already processed (first-wins policy)"
        ///
        /// Actions are applied sequentially by calling ApplyAction() for each validated command.
        /// MatchManager.ApplyCommand() is the authoritative last gate.
        ///
        /// Returns: count of accepted actions this step.
        /// </summary>
        public int ApplyActions(IReadOnlyList<AgentAction> actions, Owner playerPerspective)
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

                ApplyAction(action, playerPerspective);
            }

            return AcceptedActionsLastStep;
        }

        /// <summary>
        /// Reset per-step diagnostics.
        /// </summary>
        public void ResetDiagnostics()
        {
            AcceptedActionsLastStep = 0;
            RejectedActionsLastStep = 0;
            RejectionReasonsLastStep.Clear();
        }

        // ── Private Helpers ────────────────────────────────────────────────

        private bool IsActionSupportedByUnitType(UnitType unitType, UnitActionType actionType)
        {
            // Check what actions each unit type supports
            return actionType switch
            {
                UnitActionType.NoOp => true,  // All units

                UnitActionType.Move => true,  // All combat units and workers
                
                UnitActionType.Harvest => unitType == UnitType.Worker,  // Only workers
                
                UnitActionType.Return => unitType == UnitType.Worker,  // Only workers
                
                UnitActionType.Produce => unitType == UnitType.Base || unitType == UnitType.Barracks,  // Only buildings
                
                UnitActionType.Attack => unitType != UnitType.Resource,  // All units except resources
                
                _ => false
            };
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

        private bool ValidateProduceAction(UnitRuntime unit, AgentAction action, out string reason)
        {
            reason = "";

            // Only buildings produce
            if (unit.Type != UnitType.Base && unit.Type != UnitType.Barracks)
            {
                reason = $"Unit type {unit.Type} cannot produce";
                return false;
            }

            // Get resources for player
            var playerResources = _matchManager.GetResources(unit.Owner);
            // For MVP, assume fixed production costs (50 per unit)
            int unitCost = 50;

            // Validate enough resources
            if (playerResources < unitCost)
            {
                reason = $"Not enough resources ({playerResources} < {unitCost} for {action.ProduceUnitType})";
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

        private bool ValidateAttackAction(UnitRuntime unit, AgentAction action, out string reason)
        {
            reason = "";

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

            // Validate target within attack range (3x3 neighborhood for MVP)
            int dX = Mathf.Abs(action.AttackTargetPosition.X - unit.GridPos.X);
            int dY = Mathf.Abs(action.AttackTargetPosition.Y - unit.GridPos.Y);
            if (dX > 1 || dY > 1)
            {
                reason = $"Attack target {action.AttackTargetPosition} is out of range from {unit.GridPos}";
                return false;
            }

            // Validate there's an enemy unit at target
            var targetUnit = _gridManager.GetOccupant(action.AttackTargetPosition);
            if (targetUnit == null || targetUnit.Owner == unit.Owner)
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
            RejectionReasonsLastStep.Add(reason);
        }
    }
}
