// AgentAction.cs — unified intermediate action representation
// Week 3, Day 3: Unified action contract between policy and MatchManager
//
// Both v1_transfer_compatible_action_space and v1_debug_action_space
// are decoded into AgentAction, which then flows through ActionApplier -> MatchManager.
//
// Design principle:
// - AgentAction decouples external action format (policy output) from internal game logic.
// - Two input formats (transfer-compatible per-cell, debug single-actor) map to the same AgentAction model.
// - One downstream pipeline (ActionApplier) applies all AgentActions uniformly.

using UnityEngine;
using RTS.Core;
using RTS.Gameplay;

namespace RTS.ML
{
    /// <summary>
    /// Unified intermediate representation of one decoded action intent.
    ///
    /// AgentAction bridges semantic layers without erasing their differences:
    /// - transfer-compatible decoding uses it as the production-facing Week 3 policy contract;
    /// - debug decoding uses the same shape for smoke and diagnostics only.
    ///
    /// Runtime authority still does not live here. Even a structurally valid AgentAction may be
    /// rejected later by ActionApplier or MatchManager.
    /// </summary>
    public readonly struct AgentAction
    {
        /// <summary>
        /// Actor position on grid (who is executing this action).
        /// If position is invalid (all zeros), action is considered NoOp for no-actor case.
        /// </summary>
        public GridPosition ActorPosition { get; }

        /// <summary>
        /// Type of action: NoOp, Move, Harvest, Return, Produce, Attack.
        /// </summary>
        public UnitActionType ActionType { get; }

        /// <summary>
        /// Primary direction parameter (used for Move, Harvest, Return, Produce).
        /// Default value: Direction.North if not applicable to action type.
        /// </summary>
        public Direction Direction { get; }

        /// <summary>
        /// Type of unit to produce (Worker, Light, Heavy, Ranged).
        /// Only meaningful if ActionType == UnitActionType.Produce.
        /// Default value: ProducibleUnit.Worker if not applicable.
        /// </summary>
        public ProducibleUnit ProduceUnitType { get; }

        /// <summary>
        /// Attack target position relative to actor.
        /// Only meaningful if ActionType == UnitActionType.Attack.
        /// For MVP, this is a local 3x3 neighborhood indexing (0..8, where 4 = center/self).
        /// </summary>
        public GridPosition AttackTargetPosition { get; }

        /// <summary>
        /// Decoder-side diagnostic metadata only.
        /// Indicates whether ActionDecoder was able to produce a structurally valid action
        /// (e.g. actor index in range, branches parseable).
        ///
        /// IMPORTANT: IsValid == true does NOT guarantee the action will be accepted by ActionApplier.
        /// Authoritative action validity is determined exclusively inside ActionApplier,
        /// which performs server-side validation against live game state (phase, ownership,
        /// unit type capability, resource availability, queue status, etc.).
        /// </summary>
        public bool IsValid { get; }

        /// <summary>
        /// Debug/diagnostic: reason why action is invalid (if IsValid == false).
        /// </summary>
        public string InvalidationReason { get; }

        /// <summary>
        /// Source of this action: TransferCompatible (per-cell multi-discrete) or Debug (single-actor).
        /// Used for diagnostics and fallback logic.
        /// </summary>
        public ActionSourceType SourceType { get; }

        public AgentAction(
            GridPosition actorPosition,
            UnitActionType actionType,
            Direction direction = Direction.North,
            ProducibleUnit produceUnitType = ProducibleUnit.Worker,
            GridPosition attackTargetPosition = default,
            bool isValid = true,
            string invalidationReason = "",
            ActionSourceType sourceType = ActionSourceType.TransferCompatible)
        {
            ActorPosition = actorPosition;
            ActionType = actionType;
            Direction = direction;
            ProduceUnitType = produceUnitType;
            AttackTargetPosition = attackTargetPosition;
            IsValid = isValid;
            InvalidationReason = invalidationReason;
            SourceType = sourceType;
        }

        /// <summary>
        /// Create a NoOp action (no operation).
        /// Used when actor position is invalid or action type is NoOp.
        /// </summary>
        public static AgentAction CreateNoOp(ActionSourceType sourceType = ActionSourceType.Debug)
        {
            return new AgentAction(
                actorPosition: GridPosition.Zero,
                actionType: UnitActionType.NoOp,
                isValid: true,
                sourceType: sourceType);
        }

        /// <summary>
        /// Create invalid action with reason.
        /// Used when action decode or validation detects an invalid choice.
        /// </summary>
        public static AgentAction CreateInvalid(
            GridPosition actorPosition,
            string reason,
            ActionSourceType sourceType = ActionSourceType.Debug)
        {
            return new AgentAction(
                actorPosition: actorPosition,
                actionType: UnitActionType.NoOp,
                isValid: false,
                invalidationReason: reason,
                sourceType: sourceType);
        }

        /// <summary>
        /// Debug string representation.
        /// </summary>
        public override string ToString()
        {
            var sb = new System.Text.StringBuilder();
            sb.Append($"[AgentAction] actor={ActorPosition} type={ActionType}");

            if (ActionType == UnitActionType.Move || 
                ActionType == UnitActionType.Harvest || 
                ActionType == UnitActionType.Return || 
                ActionType == UnitActionType.Produce)
            {
                sb.Append($" dir={Direction}");
            }

            if (ActionType == UnitActionType.Produce)
            {
                sb.Append($" produce={ProduceUnitType}");
            }

            if (ActionType == UnitActionType.Attack)
            {
                sb.Append($" target={AttackTargetPosition}");
            }

            if (!IsValid)
            {
                sb.Append($" ✗ ({InvalidationReason})");
            }

            sb.Append($" source={SourceType}");

            return sb.ToString();
        }
    }

    /// <summary>
    /// Action source type for diagnostics and fallback handling.
    /// </summary>
    public enum ActionSourceType
    {
        /// <summary>
        /// From v1_transfer_compatible_action_space (per-cell multi-discrete).
        /// This is the primary input format for ML-Agents policy.
        /// </summary>
        TransferCompatible,

        /// <summary>
        /// From v1_debug_action_space (single-actor, simplified).
        /// Used for smoke/debug testing and heuristic policies.
        /// </summary>
        Debug
    }
}
