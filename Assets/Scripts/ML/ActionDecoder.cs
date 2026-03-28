// ActionDecoder.cs — decode policy output into unified AgentAction
// Week 3, Day 3: Decode discrete branches from v1_transfer_compatible and v1_debug action spaces
//
// Both action formats are decoded into AgentAction through separate paths:
// - TransferCompatible: per-cell multi-discrete -> decode all 576 cells -> collect ALL non-NoOp actions
//   -> DecodeTransferCompatibleBatch() returns List<AgentAction> (multi-command per step)
//   -> DecodeTransferCompatible() is a single-action wrapper for backward compatibility
// - Debug: single-actor simplified -> direct actor index + action -> one AgentAction per step
//
// Conflict resolution (duplicate actor in batch) is handled downstream by ActionApplier (first-wins).

using System;
using System.Collections.Generic;
using UnityEngine;
using RTS.Core;
using RTS.Gameplay;

namespace RTS.ML
{
    /// <summary>
    /// Decodes policy output into unified AgentAction values.
    ///
    /// Transfer-compatible decoding is the production-facing Week 3 contract. Debug decoding is
    /// intentionally assembly-local and exists for smoke tests, heuristics, and diagnostics.
    /// Conflict resolution for duplicate actors is handled later by ActionApplier.
    /// </summary>
    public class ActionDecoder
    {
        private readonly GridManager _gridManager;
        private readonly UnitRegistry _unitRegistry;

        public ActionDecoder(GridManager gridManager, UnitRegistry unitRegistry)
        {
            _gridManager = gridManager ?? throw new ArgumentNullException(nameof(gridManager));
            _unitRegistry = unitRegistry ?? throw new ArgumentNullException(nameof(unitRegistry));
        }

        /// <summary>
        /// [PRIMARY] Decode ALL non-NoOp actions from v1_transfer_compatible_action_space.
        ///
        /// Multi-command decoding: scans all TotalCells cells and collects every
        /// cell where action_type != NoOp into the result list.
        ///
        /// Input:  flat action array of size [TotalCells * ActionFlatSize]
        /// Output: List of AgentActions (empty if all cells are NoOp).
        ///
        /// Conflict resolution (multiple commands for the same actor) is NOT done here.
        /// ActionApplier.ApplyActions() applies first-wins policy on duplicates.
        /// </summary>
        public List<AgentAction> DecodeTransferCompatibleBatch(int[] actionFlat, Owner playerPerspective)
        {
            var results = new List<AgentAction>();

            if (actionFlat == null)
            {
                Debug.LogWarning("[ActionDecoder] DecodeTransferCompatibleBatch: actionFlat is null");
                return results;
            }

            int expectedLength = ActionContract.TotalActionFlatSize;
            if (actionFlat.Length != expectedLength)
            {
                Debug.LogWarning($"[ActionDecoder] DecodeTransferCompatibleBatch: array length {actionFlat.Length} != expected {expectedLength}");
                return results;
            }

            for (int cellIndex = 0; cellIndex < ActionContract.TotalCells; cellIndex++)
            {
                if (!TryDecodeCell(actionFlat, cellIndex, playerPerspective, out var action))
                    continue;

                if (action.ActionType != UnitActionType.NoOp)
                {
                    results.Add(action);
                }
            }

            return results;
        }

        /// <summary>
        /// [COMPAT] Decode action from v1_transfer_compatible_action_space — returns first non-NoOp action.
        ///
        /// Wrapper around DecodeTransferCompatibleBatch() for backward compatibility.
        /// Prefer DecodeTransferCompatibleBatch() for full multi-command support.
        ///
        /// Input:  flat action array of size [TotalCells * ActionFlatSize]
        /// Output: First valid non-NoOp AgentAction, or NoOp if all cells are NoOp.
        /// </summary>
        public AgentAction DecodeTransferCompatible(int[] actionFlat, Owner playerPerspective)
        {
            if (actionFlat == null)
                return AgentAction.CreateInvalid(GridPosition.Zero, "Action array is null", ActionSourceType.TransferCompatible);

            var batch = DecodeTransferCompatibleBatch(actionFlat, playerPerspective);
            return batch.Count > 0 ? batch[0] : AgentAction.CreateNoOp(ActionSourceType.TransferCompatible);
        }

        /// <summary>
        /// Decodes the assembly-local debug action format used by smoke and heuristic tooling.
        ///
        /// This path intentionally stays separate from the transfer-compatible contract and should
        /// not be treated as a claim of semantic parity with the reference action surface.
        /// </summary>
        internal AgentAction DecodeDebug(int actorIndexFlat, int actionType, int direction, int produceUnitType, int attackTargetLocal)
        {
            // Check for NoActor marker
            if (actorIndexFlat >= ActionContract.TotalCells)
            {
                return AgentAction.CreateNoOp(ActionSourceType.Debug);
            }

            // Validate actor index range
            if (actorIndexFlat < 0)
            {
                return AgentAction.CreateInvalid(
                    GridPosition.Zero,
                    $"Actor index {actorIndexFlat} < 0",
                    ActionSourceType.Debug);
            }

            // Decode flat index to grid position
            var actorPos = GridPosition.FromFlatIndex(actorIndexFlat);
            if (!actorPos.IsInsideMap())
            {
                return AgentAction.CreateInvalid(
                    GridPosition.Zero,
                    $"Cannot decode flat index {actorIndexFlat} to valid position",
                    ActionSourceType.Debug);
            }

            // Validate actor type
            if (!TryValidateActionType(actionType, out var unitActionType, out string actionTypeError))
            {
                return AgentAction.CreateInvalid(actorPos, actionTypeError, ActionSourceType.Debug);
            }

            // Validate direction
            if (!TryValidateDirection(direction, out var dirEnum, out string dirError))
            {
                return AgentAction.CreateInvalid(actorPos, dirError, ActionSourceType.Debug);
            }

            // Validate produce unit type
            if (!TryValidateProduceUnitType(produceUnitType, out var produceEnum, out string produceError))
            {
                return AgentAction.CreateInvalid(actorPos, produceError, ActionSourceType.Debug);
            }

            // Decode attack target from local 3x3 index
            GridPosition attackTarget = default;
            if (unitActionType == UnitActionType.Attack)
            {
                if (!ActionContractMappings.TryGetAttackTargetPosition(actorPos, attackTargetLocal, out attackTarget))
                {
                    return AgentAction.CreateInvalid(
                        actorPos,
                        $"Invalid attack target local index {attackTargetLocal}",
                        ActionSourceType.Debug);
                }
            }

            // Validate actor exists and belongs to correct player (will be done by ActionApplier)
            return new AgentAction(
                actorPosition: actorPos,
                actionType: unitActionType,
                direction: dirEnum,
                produceUnitType: produceEnum,
                attackTargetPosition: attackTarget,
                isValid: true,
                sourceType: ActionSourceType.Debug);
        }

        // ── Private Helpers ────────────────────────────────────────────────

        /// <summary>
        /// Try to decode a single cell (GridPosition) with 7 branches.
        /// </summary>
        private bool TryDecodeCell(int[] actionFlat, int cellIndex, Owner playerPerspective, out AgentAction action)
        {
            action = default;

            if (cellIndex < 0 || cellIndex >= ActionContract.TotalCells)
                return false;

            // Extract branches for this cell
            int cellBaseOffset = cellIndex * ActionContract.ActionFlatSize;

            // b0: action_type
            int branchActionTypeOffset = ActionContract.BranchOffset(ActionContract.BRANCH_ACTION_TYPE);
            int actionTypeValue = ExtractBranchValue(actionFlat, cellBaseOffset + branchActionTypeOffset,
                ActionContract.SIZE_ACTION_TYPE);

            if (actionTypeValue < 0 || actionTypeValue >= ActionContract.SIZE_ACTION_TYPE)
            {
                action = AgentAction.CreateInvalid(
                    GridPosition.Zero,
                    $"Invalid action type value {actionTypeValue}",
                    ActionSourceType.TransferCompatible);
                return false;
            }

            if (!TryValidateActionType(actionTypeValue, out var unitActionType, out _))
            {
                action = AgentAction.CreateInvalid(
                    GridPosition.Zero,
                    $"Cannot decode action type {actionTypeValue}",
                    ActionSourceType.TransferCompatible);
                return false;
            }

            // Decode position
            var cellPos = GridPosition.FromFlatIndex(cellIndex);

            // Check actor exists at this cell before decoding full action
            var unit = _gridManager.GetOccupant(cellPos);
            if (unit == null)
            {
                // Cell has no unit, skip
                return false;
            }

            // b1: move_dir
            int branchMoveDirOffset = ActionContract.BranchOffset(ActionContract.BRANCH_MOVE_DIR);
            int moveDirValue = ExtractBranchValue(actionFlat, cellBaseOffset + branchMoveDirOffset,
                ActionContract.SIZE_DIRECTION);

            // b2: harvest_dir
            int branchHarvestDirOffset = ActionContract.BranchOffset(ActionContract.BRANCH_HARVEST_DIR);
            int harvestDirValue = ExtractBranchValue(actionFlat, cellBaseOffset + branchHarvestDirOffset,
                ActionContract.SIZE_DIRECTION);

            // b3: return_dir
            int branchReturnDirOffset = ActionContract.BranchOffset(ActionContract.BRANCH_RETURN_DIR);
            int returnDirValue = ExtractBranchValue(actionFlat, cellBaseOffset + branchReturnDirOffset,
                ActionContract.SIZE_DIRECTION);

            // b4: produce_dir
            int branchProduceDirOffset = ActionContract.BranchOffset(ActionContract.BRANCH_PRODUCE_DIR);
            int produceDirValue = ExtractBranchValue(actionFlat, cellBaseOffset + branchProduceDirOffset,
                ActionContract.SIZE_DIRECTION);

            // b5: produce_unit_type
            int branchProduceTypeOffset = ActionContract.BranchOffset(ActionContract.BRANCH_PRODUCE_UNIT_TYPE);
            int produceTypeValue = ExtractBranchValue(actionFlat, cellBaseOffset + branchProduceTypeOffset,
                ActionContract.SIZE_PRODUCE_UNIT_TYPE);

            // b6: attack_target_local
            int branchAttackTargetOffset = ActionContract.BranchOffset(ActionContract.BRANCH_ATTACK_TARGET);
            int attackTargetValue = ExtractBranchValue(actionFlat, cellBaseOffset + branchAttackTargetOffset,
                ActionContract.SIZE_ATTACK_TARGET);

            // Determine which direction to use based on action type
            Direction primaryDir = GetPrimaryDirection(unitActionType, moveDirValue, harvestDirValue, returnDirValue, produceDirValue);

            // Validate produce type
            if (!TryValidateProduceUnitType(produceTypeValue, out var produceEnum, out _))
            {
                produceEnum = ProducibleUnit.Worker;
            }

            // Decode attack target if needed
            GridPosition attackTargetPos = GridPosition.Zero;
            if (unitActionType == UnitActionType.Attack)
            {
                ActionContractMappings.TryGetAttackTargetPosition(cellPos, attackTargetValue, out attackTargetPos);
            }

            action = new AgentAction(
                actorPosition: cellPos,
                actionType: unitActionType,
                direction: primaryDir,
                produceUnitType: produceEnum,
                attackTargetPosition: attackTargetPos,
                isValid: true,
                sourceType: ActionSourceType.TransferCompatible);

            return true;
        }

        /// <summary>
        /// Extract single branch value from flat action array.
        /// Each branch is a one-hot or discrete value at index cellBaseOffset + branchOffset.
        /// </summary>
        private int ExtractBranchValue(int[] actionFlat, int offset, int branchSize)
        {
            if (offset < 0 || offset >= actionFlat.Length)
                return -1;

            // For now, assume actionFlat contains discrete indices (0..branchSize-1)
            int value = actionFlat[offset];
            if (value < 0 || value >= branchSize)
                return -1;

            return value;
        }

        /// <summary>
        /// Map index to direction enum.
        /// </summary>
        private Direction GetPrimaryDirection(UnitActionType actionType, int moveDir, int harvestDir, int returnDir, int produceDir)
        {
            int dirValue = actionType switch
            {
                UnitActionType.Move => moveDir,
                UnitActionType.Harvest => harvestDir,
                UnitActionType.Return => returnDir,
                UnitActionType.Produce => produceDir,
                _ => 0
            };

            return ActionContractMappings.TryDirectionFromIndex(dirValue, out var direction)
                ? direction
                : Direction.North;
        }

        /// <summary>
        /// Convert action type index to enum.
        /// </summary>
        private bool TryValidateActionType(int value, out UnitActionType actionType, out string error)
        {
            error = "";
            if (value < 0 || value >= ActionContract.SIZE_ACTION_TYPE)
            {
                error = $"Action type {value} out of range [0..{ActionContract.SIZE_ACTION_TYPE - 1}]";
                actionType = UnitActionType.NoOp;
                return false;
            }

            actionType = (UnitActionType)value;
            return true;
        }

        /// <summary>
        /// Convert direction index to enum.
        /// </summary>
        private bool TryValidateDirection(int value, out Direction direction, out string error)
        {
            error = "";
            if (value < 0 || value >= ActionContract.SIZE_DIRECTION)
            {
                error = $"Direction {value} out of range [0..{ActionContract.SIZE_DIRECTION - 1}]";
                direction = Direction.North;
                return false;
            }

            return ActionContractMappings.TryDirectionFromIndex(value, out direction);
        }

        /// <summary>
        /// Convert produce unit type index to enum.
        /// </summary>
        private bool TryValidateProduceUnitType(int value, out ProducibleUnit produceType, out string error)
        {
            error = "";
            if (value < 0 || value >= ActionContract.SIZE_PRODUCE_UNIT_TYPE)
            {
                error = $"Produce unit type {value} out of range [0..{ActionContract.SIZE_PRODUCE_UNIT_TYPE - 1}]";
                produceType = ProducibleUnit.Worker;
                return false;
            }

            produceType = (ProducibleUnit)value;
            return true;
        }

    }
}
