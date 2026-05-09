using RTS.Core;
using RTS.Gameplay;
using RTS.ML;

namespace RTS.MLAgents.Stage7B.TeacherConversion
{
    public sealed class Stage7BTeacherActionConverter
    {
        public bool TryConvertSingleActorAction(
            short[] perCellBranchesFlat,
            out AgentAction action,
            out Stage7BDropReason dropReason)
        {
            action = AgentAction.CreateNoOp(ActionSourceType.Debug);
            dropReason = Stage7BDropReason.Unknown;

            if (perCellBranchesFlat == null || perCellBranchesFlat.Length != ActionContract.TotalCells * ActionContract.ActionBranchCount)
            {
                dropReason = Stage7BDropReason.BranchContractMismatch;
                return false;
            }

            int actorFlat = -1;
            int nonNoOpCount = 0;
            for (int i = 0; i < ActionContract.TotalCells; i++)
            {
                int actionType = perCellBranchesFlat[i * ActionContract.ActionBranchCount + 0];
                if (actionType != ActionContract.ACTION_NOOP)
                {
                    actorFlat = i;
                    nonNoOpCount++;
                }
            }

            if (nonNoOpCount == 0)
            {
                action = AgentAction.CreateNoOp(ActionSourceType.Debug);
                dropReason = Stage7BDropReason.TeacherNoOp;
                return true;
            }

            if (nonNoOpCount > 1)
            {
                dropReason = Stage7BDropReason.MultipleNonNoOpActors;
                return false;
            }

            int baseOffset = actorFlat * ActionContract.ActionBranchCount;
            int actionTypeIndex = perCellBranchesFlat[baseOffset + 0];
            var actorPos = GridPosition.FromFlatIndex(actorFlat);

            if (actionTypeIndex < 0 || actionTypeIndex >= ActionContract.SIZE_ACTION_TYPE)
            {
                dropReason = Stage7BDropReason.ActionTypeUnsupported;
                return false;
            }

            UnitActionType actionType = (UnitActionType)actionTypeIndex;
            switch (actionType)
            {
                case UnitActionType.Move:
                    action = new AgentAction(
                        actorPos,
                        actionType,
                        (Direction)perCellBranchesFlat[baseOffset + 1],
                        sourceType: ActionSourceType.Debug);
                    break;
                case UnitActionType.Harvest:
                    action = new AgentAction(
                        actorPos,
                        actionType,
                        (Direction)perCellBranchesFlat[baseOffset + 2],
                        sourceType: ActionSourceType.Debug);
                    break;
                case UnitActionType.Return:
                    action = new AgentAction(
                        actorPos,
                        actionType,
                        (Direction)perCellBranchesFlat[baseOffset + 3],
                        sourceType: ActionSourceType.Debug);
                    break;
                case UnitActionType.Produce:
                    int unitTypeIndex = perCellBranchesFlat[baseOffset + 5];
                    if (unitTypeIndex < 0 || unitTypeIndex >= ActionContract.SIZE_PRODUCE_UNIT_TYPE)
                    {
                        dropReason = Stage7BDropReason.ProduceTypeMismatch;
                        return false;
                    }

                    action = new AgentAction(
                        actorPos,
                        actionType,
                        (Direction)perCellBranchesFlat[baseOffset + 4],
                        (ProducibleUnit)0,
                        sourceType: ActionSourceType.Debug);
                    break;
                case UnitActionType.Attack:
                    int localAttackIndex = perCellBranchesFlat[baseOffset + 6];
                    if (!ActionContractMappings.TryGetAttackTargetPosition(actorPos, localAttackIndex, out GridPosition targetPos))
                    {
                        dropReason = Stage7BDropReason.AttackTargetMismatch;
                        return false;
                    }

                    action = new AgentAction(
                        actorPos,
                        actionType,
                        Direction.North,
                        ProducibleUnit.Worker,
                        targetPos,
                        sourceType: ActionSourceType.Debug);
                    break;
                default:
                    action = AgentAction.CreateNoOp(ActionSourceType.Debug);
                    break;
            }

            dropReason = Stage7BDropReason.None;
            return true;
        }
    }
}
