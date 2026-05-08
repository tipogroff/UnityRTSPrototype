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
        public readonly struct MaskAwareCellTelemetry
        {
            public MaskAwareCellTelemetry(
                int cellIndex,
                UnitActionType rawActionTypeTop1,
                int rawMoveDirTop1,
                UnitActionType maskedActionType,
                int maskedMoveDir,
                bool[] legalActionTypeMask,
                bool[] legalMoveDirMask,
                bool maskedMoveDirLegal,
                bool branchMaskAppliedForMove,
                string moveDirMaskFallbackReason,
                UnitActionType decoderReceivedActionType,
                int decoderReceivedMoveDir,
                bool decoderReceivedMoveDirLegal,
                int rawHarvestDirTop1 = 0,
                int rawReturnDirTop1 = 0,
                int rawProduceDirTop1 = 0,
                int rawProduceUnitTypeTop1 = 0,
                int rawAttackTargetLocalTop1 = 0,
                int maskedHarvestDir = 0,
                int maskedReturnDir = 0,
                int maskedProduceDir = 0,
                int maskedProduceUnitType = 0,
                int maskedAttackTargetLocal = 0,
                bool branchParameterMaskApplied = false,
                string branchParameterMaskReason = "")
            {
                CellIndex = cellIndex;
                RawActionTypeTop1 = rawActionTypeTop1;
                RawMoveDirTop1 = rawMoveDirTop1;
                RawHarvestDirTop1 = rawHarvestDirTop1;
                RawReturnDirTop1 = rawReturnDirTop1;
                RawProduceDirTop1 = rawProduceDirTop1;
                RawProduceUnitTypeTop1 = rawProduceUnitTypeTop1;
                RawAttackTargetLocalTop1 = rawAttackTargetLocalTop1;
                MaskedActionType = maskedActionType;
                MaskedMoveDir = maskedMoveDir;
                MaskedHarvestDir = maskedHarvestDir;
                MaskedReturnDir = maskedReturnDir;
                MaskedProduceDir = maskedProduceDir;
                MaskedProduceUnitType = maskedProduceUnitType;
                MaskedAttackTargetLocal = maskedAttackTargetLocal;
                LegalActionTypeMask = legalActionTypeMask ?? Array.Empty<bool>();
                LegalMoveDirMask = legalMoveDirMask ?? Array.Empty<bool>();
                MaskedMoveDirLegal = maskedMoveDirLegal;
                BranchMaskAppliedForMove = branchMaskAppliedForMove;
                MoveDirMaskFallbackReason = moveDirMaskFallbackReason ?? string.Empty;
                DecoderReceivedActionType = decoderReceivedActionType;
                DecoderReceivedMoveDir = decoderReceivedMoveDir;
                DecoderReceivedMoveDirLegal = decoderReceivedMoveDirLegal;
                BranchParameterMaskApplied = branchParameterMaskApplied;
                BranchParameterMaskReason = branchParameterMaskReason ?? string.Empty;
            }

            public int CellIndex { get; }
            public UnitActionType RawActionTypeTop1 { get; }
            public int RawMoveDirTop1 { get; }
            public int RawHarvestDirTop1 { get; }
            public int RawReturnDirTop1 { get; }
            public int RawProduceDirTop1 { get; }
            public int RawProduceUnitTypeTop1 { get; }
            public int RawAttackTargetLocalTop1 { get; }
            public UnitActionType MaskedActionType { get; }
            public int MaskedMoveDir { get; }
            public int MaskedHarvestDir { get; }
            public int MaskedReturnDir { get; }
            public int MaskedProduceDir { get; }
            public int MaskedProduceUnitType { get; }
            public int MaskedAttackTargetLocal { get; }
            public bool[] LegalActionTypeMask { get; }
            public bool[] LegalMoveDirMask { get; }
            public bool MaskedMoveDirLegal { get; }
            public bool BranchMaskAppliedForMove { get; }
            public string MoveDirMaskFallbackReason { get; }
            public UnitActionType DecoderReceivedActionType { get; }
            public int DecoderReceivedMoveDir { get; }
            public bool DecoderReceivedMoveDirLegal { get; }
            public bool BranchParameterMaskApplied { get; }
            public string BranchParameterMaskReason { get; }
        }

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
            long perfStart = Stage6B3PerformanceCounters.Begin(Stage6B3PerfMetric.ActionDecode);
            var results = new List<AgentAction>();

            if (actionFlat == null)
            {
                Debug.LogWarning("[ActionDecoder] DecodeTransferCompatibleBatch: actionFlat is null");
                Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.ActionDecode, perfStart);
                return results;
            }

            int expectedLength = ActionContract.TotalActionFlatSize;
            if (actionFlat.Length != expectedLength)
            {
                Debug.LogWarning($"[ActionDecoder] DecodeTransferCompatibleBatch: array length {actionFlat.Length} != expected {expectedLength}");
                Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.ActionDecode, perfStart);
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

            Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.ActionDecode, perfStart);
            return results;
        }

        /// <summary>
        /// Decode transfer-compatible output only for the provided actor cell subset.
        ///
        /// This is used by the Week 6 live student path to enforce explicit pre-submit
        /// ownership/control gating before actions reach ActionApplier.
        /// </summary>
        public List<AgentAction> DecodeTransferCompatibleBatchFiltered(
            int[] actionFlat,
            Owner playerPerspective,
            IReadOnlyList<int> eligibleCellIndices)
        {
            long perfStart = Stage6B3PerformanceCounters.Begin(Stage6B3PerfMetric.ActionDecode);
            var results = new List<AgentAction>();

            if (actionFlat == null)
            {
                Debug.LogWarning("[ActionDecoder] DecodeTransferCompatibleBatchFiltered: actionFlat is null");
                Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.ActionDecode, perfStart);
                return results;
            }

            if (eligibleCellIndices == null || eligibleCellIndices.Count == 0)
            {
                Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.ActionDecode, perfStart);
                return results;
            }

            int expectedLength = ActionContract.TotalActionFlatSize;
            if (actionFlat.Length != expectedLength)
            {
                Debug.LogWarning($"[ActionDecoder] DecodeTransferCompatibleBatchFiltered: array length {actionFlat.Length} != expected {expectedLength}");
                Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.ActionDecode, perfStart);
                return results;
            }

            for (int i = 0; i < eligibleCellIndices.Count; i++)
            {
                int cellIndex = eligibleCellIndices[i];
                if (!TryDecodeCell(actionFlat, cellIndex, playerPerspective, out var action))
                    continue;

                if (action.ActionType != UnitActionType.NoOp)
                {
                    results.Add(action);
                }
            }

            Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.ActionDecode, perfStart);
            return results;
        }

        /// <summary>
        /// Mask-aware decode for the Week 6 live student path.
        ///
        /// For each eligible actor cell: decode the model's chosen action_type, then consult the
        /// runtime ActionMaskSet to verify the action is permitted for this actor right now.
        /// If the model chose a masked-out action type, the cell is silently treated as NoOp
        /// (safe fallback). Branch parameters (direction, produce type, attack target) are
        /// decoded by the normal path only after the action_type clears the mask check.
        ///
        /// Important: this does NOT replace runtime validation — ActionApplier remains the
        /// authoritative gate. This is only a pre-submit live policy helper that prevents
        /// submitting obviously disallowed action types before they reach the runtime.
        ///
        /// Out params carry diagnostics for the compact episode report.
        /// </summary>
        public List<AgentAction> DecodeTransferCompatibleBatchMaskAware(
            int[] actionFlat,
            Owner playerPerspective,
            IReadOnlyList<int> eligibleCellIndices,
            ActionMaskSet maskSet,
            out int maskedOutChoicesCount,
            out int fallbackToNoopCount,
            out Dictionary<UnitActionType, int> preMaskHistogram,
            out Dictionary<UnitActionType, int> postMaskHistogram,
            out Dictionary<int, MaskAwareCellTelemetry> cellTelemetryByFlat)
        {
            long perfStart = Stage6B3PerformanceCounters.Begin(Stage6B3PerfMetric.ActionDecode);
            maskedOutChoicesCount = 0;
            fallbackToNoopCount = 0;
            preMaskHistogram = new Dictionary<UnitActionType, int>();
            postMaskHistogram = new Dictionary<UnitActionType, int>();
            cellTelemetryByFlat = new Dictionary<int, MaskAwareCellTelemetry>();
            var results = new List<AgentAction>();
            var reservedMoveTargetsThisDecode = new HashSet<int>();

            if (actionFlat == null || eligibleCellIndices == null || eligibleCellIndices.Count == 0)
            {
                Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.ActionDecode, perfStart);
                return results;
            }

            int expectedLength = ActionContract.TotalActionFlatSize;
            if (actionFlat.Length != expectedLength)
            {
                Debug.LogWarning($"[ActionDecoder] DecodeTransferCompatibleBatchMaskAware: array length {actionFlat.Length} != expected {expectedLength}");
                Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.ActionDecode, perfStart);
                return results;
            }

            for (int i = 0; i < eligibleCellIndices.Count; i++)
            {
                int cellIndex = eligibleCellIndices[i];

                // Decode the full action first (validates unit existence, branches, etc.)
                if (!TryDecodeCell(actionFlat, cellIndex, playerPerspective, out AgentAction action))
                    continue;

                int cellBaseOffset = cellIndex * ActionContract.ActionFlatSize;
                int rawMoveDir = ExtractBranchValue(
                    actionFlat,
                    cellBaseOffset + ActionContract.BranchOffset(ActionContract.BRANCH_MOVE_DIR),
                    ActionContract.SIZE_DIRECTION);
                int rawHarvestDir = ExtractBranchValue(
                    actionFlat,
                    cellBaseOffset + ActionContract.BranchOffset(ActionContract.BRANCH_HARVEST_DIR),
                    ActionContract.SIZE_DIRECTION);
                int rawReturnDir = ExtractBranchValue(
                    actionFlat,
                    cellBaseOffset + ActionContract.BranchOffset(ActionContract.BRANCH_RETURN_DIR),
                    ActionContract.SIZE_DIRECTION);
                int rawProduceDir = ExtractBranchValue(
                    actionFlat,
                    cellBaseOffset + ActionContract.BranchOffset(ActionContract.BRANCH_PRODUCE_DIR),
                    ActionContract.SIZE_DIRECTION);
                int rawProduceUnitType = ExtractBranchValue(
                    actionFlat,
                    cellBaseOffset + ActionContract.BranchOffset(ActionContract.BRANCH_PRODUCE_UNIT_TYPE),
                    ActionContract.SIZE_PRODUCE_UNIT_TYPE);
                int rawAttackTargetLocal = ExtractBranchValue(
                    actionFlat,
                    cellBaseOffset + ActionContract.BranchOffset(ActionContract.BRANCH_ATTACK_TARGET),
                    ActionContract.SIZE_ATTACK_TARGET);
                bool[] legalActionTypeMask = BuildLegalActionTypeMask(maskSet, cellIndex);
                bool[] legalMoveDirMask = BuildLegalMoveDirectionMask(maskSet, cellIndex);
                UnitActionType rawActionTypeTop1 = action.ActionType;
                UnitActionType maskedActionType = action.ActionType;
                int maskedMoveDir = rawMoveDir;
                int maskedHarvestDir = rawHarvestDir;
                int maskedReturnDir = rawReturnDir;
                int maskedProduceDir = rawProduceDir;
                int maskedProduceUnitType = rawProduceUnitType;
                int maskedAttackTargetLocal = rawAttackTargetLocal;
                bool branchMaskAppliedForMove = false;
                bool maskedMoveDirLegal = true;
                string moveDirFallbackReason = string.Empty;
                bool branchParameterMaskApplied = false;
                string branchParameterMaskReason = string.Empty;

                // Track what the model chose before mask constraint
                IncrementActionDict(preMaskHistogram, action.ActionType);

                // Check runtime mask for this actor: if the chosen action type is explicitly
                // masked out, fall back to NoOp. maskSet may be null (e.g. baseline path or
                // if mask build failed) — in that case treat all actions as permitted.
                if (maskSet != null)
                {
                    ActorActionMask actorMask = maskSet.GetActorMaskByFlatIndex(cellIndex);
                    if (action.ActionType == UnitActionType.Move && actorMask != null)
                    {
                        branchMaskAppliedForMove = true;
                        if (!TrySelectMaskedBranchValue(
                                actorMask.MoveDirectionMask,
                                rawMoveDir,
                                out int selectedMoveDir,
                                out bool moveDirReplaced,
                                out string moveDirReason))
                        {
                            maskedOutChoicesCount++;
                            fallbackToNoopCount++;
                            maskedActionType = UnitActionType.NoOp;
                            moveDirFallbackReason = moveDirReason;
                            maskedMoveDirLegal = false;
                            cellTelemetryByFlat[cellIndex] = new MaskAwareCellTelemetry(
                                cellIndex,
                                rawActionTypeTop1,
                                rawMoveDir,
                                maskedActionType,
                                maskedMoveDir,
                                legalActionTypeMask,
                                legalMoveDirMask,
                                false,
                                branchMaskAppliedForMove,
                                moveDirFallbackReason,
                                UnitActionType.NoOp,
                                0,
                                true);
                            continue;
                        }

                        maskedMoveDir = selectedMoveDir;
                        if (moveDirReplaced)
                        {
                            moveDirFallbackReason = "masked_to_sole_legal_move_dir";
                            action = RebuildActionWithDirection(action, (Direction)selectedMoveDir);
                        }

                        if (TryGetMoveTargetFlat(actorMask, selectedMoveDir, out int selectedMoveTargetFlat)
                            && reservedMoveTargetsThisDecode.Contains(selectedMoveTargetFlat))
                        {
                            // Same execution window safety gate: do not submit another Move into an
                            // already-reserved target cell from a previously selected Move this tick.
                            maskedOutChoicesCount++;
                            fallbackToNoopCount++;
                            maskedActionType = UnitActionType.NoOp;
                            maskedMoveDirLegal = false;
                            moveDirFallbackReason = "target_reserved_by_friendly_command_same_tick";
                            cellTelemetryByFlat[cellIndex] = new MaskAwareCellTelemetry(
                                cellIndex,
                                rawActionTypeTop1,
                                rawMoveDir,
                                maskedActionType,
                                maskedMoveDir,
                                legalActionTypeMask,
                                legalMoveDirMask,
                                false,
                                branchMaskAppliedForMove,
                                moveDirFallbackReason,
                                UnitActionType.NoOp,
                                0,
                                true);
                            continue;
                        }

                        maskedMoveDirLegal = true;
                    }
                    else if (actorMask != null && action.ActionType != UnitActionType.NoOp)
                    {
                        if (!TryApplyParameterMask(
                                action,
                                actorMask,
                                rawHarvestDir,
                                rawReturnDir,
                                rawProduceDir,
                                rawProduceUnitType,
                                rawAttackTargetLocal,
                                out AgentAction parameterMaskedAction,
                                out string parameterMaskReason))
                        {
                            maskedOutChoicesCount++;
                            fallbackToNoopCount++;
                            maskedActionType = UnitActionType.NoOp;
                            moveDirFallbackReason = parameterMaskReason;
                            cellTelemetryByFlat[cellIndex] = new MaskAwareCellTelemetry(
                                cellIndex,
                                rawActionTypeTop1,
                                rawMoveDir,
                                maskedActionType,
                                maskedMoveDir,
                                legalActionTypeMask,
                                legalMoveDirMask,
                                true,
                                branchMaskAppliedForMove,
                                moveDirFallbackReason,
                                UnitActionType.NoOp,
                                0,
                                true);
                            continue;
                        }

                        action = parameterMaskedAction;
                        if (!string.IsNullOrWhiteSpace(parameterMaskReason))
                        {
                            moveDirFallbackReason = parameterMaskReason;
                            branchParameterMaskApplied = true;
                            branchParameterMaskReason = parameterMaskReason;
                            switch (action.ActionType)
                            {
                                case UnitActionType.Harvest:
                                    maskedHarvestDir = (int)action.Direction;
                                    break;
                                case UnitActionType.Return:
                                    maskedReturnDir = (int)action.Direction;
                                    break;
                                case UnitActionType.Produce:
                                    maskedProduceDir = (int)action.Direction;
                                    maskedProduceUnitType = (int)action.ProduceUnitType;
                                    break;
                                case UnitActionType.Attack:
                                    if (TryGetAttackTargetLocalIndex(action.ActorPosition, action.AttackTargetPosition, out int maskedAttackLocal))
                                    {
                                        maskedAttackTargetLocal = maskedAttackLocal;
                                    }
                                    break;
                            }
                        }
                    }
                }

                if (action.ActionType == UnitActionType.NoOp)
                {
                    cellTelemetryByFlat[cellIndex] = new MaskAwareCellTelemetry(
                        cellIndex,
                        rawActionTypeTop1,
                        rawMoveDir,
                        maskedActionType,
                        maskedMoveDir,
                        legalActionTypeMask,
                        legalMoveDirMask,
                        maskedMoveDirLegal,
                        branchMaskAppliedForMove,
                        moveDirFallbackReason,
                        UnitActionType.NoOp,
                        0,
                        true);
                    continue;
                }

                // Action type passes the mask — include it in the submission
                results.Add(action);
                if (action.ActionType == UnitActionType.Move
                    && maskSet != null
                    && maskSet.GetActorMaskByFlatIndex(cellIndex) is ActorActionMask selectedActorMask
                    && TryGetMoveTargetFlat(selectedActorMask, maskedMoveDir, out int selectedTargetFlat))
                {
                    reservedMoveTargetsThisDecode.Add(selectedTargetFlat);
                }
                IncrementActionDict(postMaskHistogram, action.ActionType);
                cellTelemetryByFlat[cellIndex] = new MaskAwareCellTelemetry(
                    cellIndex,
                    rawActionTypeTop1,
                    rawMoveDir,
                    maskedActionType,
                    maskedMoveDir,
                    legalActionTypeMask,
                    legalMoveDirMask,
                    maskedMoveDirLegal,
                    branchMaskAppliedForMove,
                    moveDirFallbackReason,
                    action.ActionType,
                    action.ActionType == UnitActionType.Move ? maskedMoveDir : 0,
                    action.ActionType != UnitActionType.Move || maskedMoveDirLegal,
                    rawHarvestDir,
                    rawReturnDir,
                    rawProduceDir,
                    rawProduceUnitType,
                    rawAttackTargetLocal,
                    maskedHarvestDir,
                    maskedReturnDir,
                    maskedProduceDir,
                    maskedProduceUnitType,
                    maskedAttackTargetLocal,
                    branchParameterMaskApplied,
                    branchParameterMaskReason);
            }

            Stage6B3PerformanceCounters.End(Stage6B3PerfMetric.ActionDecode, perfStart);
            return results;
        }

        private static bool TryApplyParameterMask(
            AgentAction action,
            ActorActionMask actorMask,
            int rawHarvestDir,
            int rawReturnDir,
            int rawProduceDir,
            int rawProduceUnitType,
            int rawAttackTargetLocal,
            out AgentAction maskedAction,
            out string reason)
        {
            maskedAction = action;
            reason = string.Empty;

            switch (action.ActionType)
            {
                case UnitActionType.Harvest:
                    if (!TrySelectMaskedBranchValue(actorMask.HarvestDirectionMask, rawHarvestDir, out int harvestDir, out bool harvestReplaced, out reason))
                        return false;
                    if (harvestReplaced)
                    {
                        maskedAction = RebuildActionWithDirection(action, (Direction)harvestDir);
                        reason = "masked_to_sole_legal_harvest_dir";
                    }
                    return true;

                case UnitActionType.Return:
                    if (!TrySelectMaskedBranchValue(actorMask.ReturnDirectionMask, rawReturnDir, out int returnDir, out bool returnReplaced, out reason))
                        return false;
                    if (returnReplaced)
                    {
                        maskedAction = RebuildActionWithDirection(action, (Direction)returnDir);
                        reason = "masked_to_sole_legal_return_dir";
                    }
                    return true;

                case UnitActionType.Produce:
                    if (!TrySelectMaskedBranchValue(actorMask.ProduceDirectionMask, rawProduceDir, out int produceDir, out bool produceDirReplaced, out reason))
                        return false;
                    if (!TrySelectMaskedBranchValue(actorMask.ProduceUnitTypeMask, rawProduceUnitType, out int produceType, out bool produceTypeReplaced, out reason))
                        return false;
                    if (produceDirReplaced || produceTypeReplaced)
                    {
                        maskedAction = new AgentAction(
                            action.ActorPosition,
                            action.ActionType,
                            (Direction)produceDir,
                            (ProducibleUnit)produceType,
                            action.AttackTargetPosition,
                            action.IsValid,
                            action.InvalidationReason,
                            action.SourceType);
                        reason = produceDirReplaced && produceTypeReplaced
                            ? "masked_to_sole_legal_produce_dir_and_type"
                            : produceDirReplaced
                                ? "masked_to_sole_legal_produce_dir"
                                : "masked_to_sole_legal_produce_unit_type";
                    }
                    return true;

                case UnitActionType.Attack:
                    if (!TrySelectMaskedBranchValue(actorMask.AttackTargetLocalMask, rawAttackTargetLocal, out int attackTargetLocal, out bool attackReplaced, out reason))
                        return false;
                    if (attackReplaced
                        && ActionContractMappings.TryGetAttackTargetPosition(action.ActorPosition, attackTargetLocal, out GridPosition targetPosition))
                    {
                        maskedAction = new AgentAction(
                            action.ActorPosition,
                            action.ActionType,
                            action.Direction,
                            action.ProduceUnitType,
                            targetPosition,
                            action.IsValid,
                            action.InvalidationReason,
                            action.SourceType);
                        reason = "masked_to_sole_legal_attack_target";
                    }
                    return true;

                default:
                    return true;
            }
        }

        private static bool TrySelectMaskedBranchValue(bool[] mask, int rawValue, out int selectedValue, out bool replaced, out string reason)
        {
            selectedValue = rawValue;
            replaced = false;
            reason = string.Empty;

            if (mask == null || mask.Length == 0)
                return true;

            if (rawValue >= 0 && rawValue < mask.Length && mask[rawValue])
                return true;

            int legalCount = 0;
            int onlyLegal = -1;
            for (int i = 0; i < mask.Length; i++)
            {
                if (!mask[i])
                    continue;

                legalCount++;
                onlyLegal = i;
            }

            if (legalCount == 1)
            {
                selectedValue = onlyLegal;
                replaced = true;
                return true;
            }

            reason = legalCount == 0
                ? "no_legal_parameter_value"
                : "illegal_parameter_value_with_multiple_legal_values";
            return false;
        }

        private static AgentAction RebuildActionWithDirection(AgentAction action, Direction direction)
        {
            return new AgentAction(
                action.ActorPosition,
                action.ActionType,
                direction,
                action.ProduceUnitType,
                action.AttackTargetPosition,
                action.IsValid,
                action.InvalidationReason,
                action.SourceType);
        }

        private static bool TryGetMoveTargetFlat(ActorActionMask actorMask, int rawMoveDir, out int targetFlat)
        {
            targetFlat = -1;
            if (actorMask == null || rawMoveDir < 0 || rawMoveDir >= ActionContract.SIZE_DIRECTION)
            {
                return false;
            }

            GridPosition target = actorMask.ActorPosition.Neighbour((Direction)rawMoveDir);
            if (!target.IsInsideMap())
            {
                return false;
            }

            targetFlat = target.ToFlatIndex();
            return targetFlat >= 0 && targetFlat < ActionContract.TotalCells;
        }

        private static bool TryGetAttackTargetLocalIndex(GridPosition actorPosition, GridPosition targetPosition, out int localIndex)
        {
            for (int i = 0; i < ActionContract.SIZE_ATTACK_TARGET; i++)
            {
                if (ActionContractMappings.TryGetAttackTargetPosition(actorPosition, i, out GridPosition candidate)
                    && candidate.Equals(targetPosition))
                {
                    localIndex = i;
                    return true;
                }
            }

            localIndex = 24;
            return false;
        }

        private static bool[] BuildLegalActionTypeMask(ActionMaskSet maskSet, int cellIndex)
        {
            var mask = new bool[ActionContract.SIZE_ACTION_TYPE];
            if (maskSet == null)
            {
                for (int i = 0; i < mask.Length; i++)
                    mask[i] = true;
                return mask;
            }

            ActorActionMask actorMask = maskSet.GetActorMaskByFlatIndex(cellIndex);
            if (actorMask == null || actorMask.ActionTypeMask == null)
            {
                mask[(int)UnitActionType.NoOp] = true;
                return mask;
            }

            for (int i = 0; i < mask.Length && i < actorMask.ActionTypeMask.Length; i++)
                mask[i] = actorMask.ActionTypeMask[i];
            return mask;
        }

        private static bool[] BuildLegalMoveDirectionMask(ActionMaskSet maskSet, int cellIndex)
        {
            var mask = new bool[ActionContract.SIZE_DIRECTION];
            if (maskSet == null)
            {
                for (int i = 0; i < mask.Length; i++)
                    mask[i] = true;
                return mask;
            }

            ActorActionMask actorMask = maskSet.GetActorMaskByFlatIndex(cellIndex);
            if (actorMask == null || actorMask.MoveDirectionMask == null)
                return mask;

            for (int i = 0; i < mask.Length && i < actorMask.MoveDirectionMask.Length; i++)
                mask[i] = actorMask.MoveDirectionMask[i];
            return mask;
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

            // Decode attack target from local 7x7 index (49 entries)
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
        /// Convert v2 produce branch index to runtime produce enum.
        ///
        /// v2 produce_unit_type branch index follows Gym/Gridnet UnitType order:
        /// 0 Resource, 1 Base, 2 Barracks, 3 Worker, 4 Light, 5 Heavy, 6 Ranged.
        ///
        /// IMPORTANT:
        /// - Branch-bound decode validity does NOT imply runtime Produce validity.
        /// - Runtime/context validation remains authoritative in ActionMaskBuilder + ActionApplier.
        /// - AgentAction currently carries ProducibleUnit (4-value runtime enum), so non-producible
        ///   v2 values (Resource/Base/Barracks) are represented via placeholder mapping here.
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

            if (!ActionContractMappings.TryMapV2ProduceIndexToUnitType(value, out UnitType v2UnitType))
            {
                error = $"Cannot map v2 produce branch index {value}";
                produceType = ProducibleUnit.Worker;
                return false;
            }

            // Preserve raw v2 index in AgentAction.ProduceUnitType (underlying int), so
            // ActionApplier can apply authoritative v2 runtime semantics by index.
            // Runtime producible enum normalization happens in ActionApplier right before
            // MatchCommand submission.
            produceType = (ProducibleUnit)value;

            return true;
        }

        private static void IncrementActionDict(Dictionary<UnitActionType, int> dict, UnitActionType key)
        {
            if (!dict.TryGetValue(key, out int current))
                current = 0;
            dict[key] = current + 1;
        }

    }
}
