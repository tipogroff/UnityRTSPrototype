using RTS.Core;
using RTS.Gameplay;
using RTS.ML;

namespace RTS.MLAgents.Stage7B.TeacherReplay
{
    public sealed class Stage7BTeacherReplayActionResolver
    {
        public bool TryResolveSingleActorAction(
            int[] perCellBranchesFlat,
            out AgentAction action,
            out Stage7BTeacherReplayDropReason dropReason)
        {
            action = AgentAction.CreateNoOp(ActionSourceType.Debug);
            dropReason = Stage7BTeacherReplayDropReason.Unknown;

            if (perCellBranchesFlat == null || perCellBranchesFlat.Length != ActionContract.TotalCells * ActionContract.ActionBranchCount)
            {
                dropReason = Stage7BTeacherReplayDropReason.BranchContractMismatch;
                return false;
            }

            int actorFlat = -1;
            int nonNoOpCount = 0;
            for (int i = 0; i < ActionContract.TotalCells; i++)
            {
                int cellActionType = perCellBranchesFlat[i * ActionContract.ActionBranchCount + ActionContract.BRANCH_ACTION_TYPE];
                if (cellActionType != ActionContract.ACTION_NOOP)
                {
                    actorFlat = i;
                    nonNoOpCount++;
                }
            }

            if (nonNoOpCount == 0)
            {
                action = AgentAction.CreateNoOp(ActionSourceType.Debug);
                dropReason = Stage7BTeacherReplayDropReason.TeacherNoOp;
                return true;
            }

            if (nonNoOpCount > 1)
            {
                dropReason = Stage7BTeacherReplayDropReason.MultipleNonNoOpActors;
                return false;
            }

            int baseOffset = actorFlat * ActionContract.ActionBranchCount;
            int actionTypeIndex = perCellBranchesFlat[baseOffset + ActionContract.BRANCH_ACTION_TYPE];
            if (actionTypeIndex < 0 || actionTypeIndex >= ActionContract.SIZE_ACTION_TYPE)
            {
                dropReason = Stage7BTeacherReplayDropReason.ActionTypeUnsupported;
                return false;
            }

            GridPosition actorPos = GridPosition.FromFlatIndex(actorFlat);
            UnitActionType actionType = (UnitActionType)actionTypeIndex;

            switch (actionType)
            {
                case UnitActionType.Move:
                    action = new AgentAction(
                        actorPos,
                        UnitActionType.Move,
                        (Direction)perCellBranchesFlat[baseOffset + ActionContract.BRANCH_MOVE_DIR],
                        sourceType: ActionSourceType.Debug);
                    dropReason = Stage7BTeacherReplayDropReason.None;
                    return true;

                case UnitActionType.Harvest:
                    action = new AgentAction(
                        actorPos,
                        UnitActionType.Harvest,
                        (Direction)perCellBranchesFlat[baseOffset + ActionContract.BRANCH_HARVEST_DIR],
                        sourceType: ActionSourceType.Debug);
                    dropReason = Stage7BTeacherReplayDropReason.None;
                    return true;

                case UnitActionType.Return:
                    action = new AgentAction(
                        actorPos,
                        UnitActionType.Return,
                        (Direction)perCellBranchesFlat[baseOffset + ActionContract.BRANCH_RETURN_DIR],
                        sourceType: ActionSourceType.Debug);
                    dropReason = Stage7BTeacherReplayDropReason.None;
                    return true;

                case UnitActionType.Produce:
                    int produceType = perCellBranchesFlat[baseOffset + ActionContract.BRANCH_PRODUCE_UNIT_TYPE];
                    if (produceType < 0 || produceType >= ActionContract.SIZE_PRODUCE_UNIT_TYPE)
                    {
                        dropReason = Stage7BTeacherReplayDropReason.ProduceTypeMismatch;
                        return false;
                    }

                    action = new AgentAction(
                        actorPos,
                        UnitActionType.Produce,
                        (Direction)perCellBranchesFlat[baseOffset + ActionContract.BRANCH_PRODUCE_DIR],
                        (ProducibleUnit)produceType,
                        sourceType: ActionSourceType.Debug);
                    dropReason = Stage7BTeacherReplayDropReason.None;
                    return true;

                case UnitActionType.Attack:
                    int localTarget = perCellBranchesFlat[baseOffset + ActionContract.BRANCH_ATTACK_TARGET];
                    if (localTarget < 0 || localTarget >= ActionContract.SIZE_ATTACK_TARGET)
                    {
                        dropReason = Stage7BTeacherReplayDropReason.AttackTargetContractMismatch;
                        return false;
                    }

                    if (!ActionContractMappings.TryGetAttackTargetPosition(actorPos, localTarget, out GridPosition attackTarget))
                    {
                        dropReason = Stage7BTeacherReplayDropReason.AttackTargetMismatch;
                        return false;
                    }

                    action = new AgentAction(
                        actorPos,
                        UnitActionType.Attack,
                        Direction.North,
                        ProducibleUnit.Worker,
                        attackTarget,
                        sourceType: ActionSourceType.Debug);
                    dropReason = Stage7BTeacherReplayDropReason.None;
                    return true;

                default:
                    dropReason = Stage7BTeacherReplayDropReason.ActionTypeUnsupported;
                    return false;
            }
        }
    }
}
