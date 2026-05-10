using RTS.Core;
using RTS.Gameplay;
using RTS.ML;

namespace RTS.MLAgents.Stage7B.TeacherReplay
{
    public sealed class Stage7BTeacherReplayActionResolver
    {
        public const string ReturnDirectionMappingModeNone = "none";
        public const string ReturnDirectionMappingModeInvertYForLegacy032Teacher = "invert_y_for_legacy032_teacher";

        public string returnDirectionMappingMode = ReturnDirectionMappingModeInvertYForLegacy032Teacher;

        public int LastRawTeacherReturnDir { get; private set; } = -1;
        public int LastMappedUnityReturnDir { get; private set; } = -1;
        public string LastReturnDirectionMappingMode { get; private set; } = ReturnDirectionMappingModeInvertYForLegacy032Teacher;
        public bool LastReturnDirectionMappingApplied { get; private set; }

        public bool TryResolveTeacherCommand(
            Stage7BTeacherReplayTeacherCommand command,
            Owner playerPerspective,
            out AgentAction action,
            out Stage7BTeacherReplayDropReason dropReason)
        {
            action = AgentAction.CreateNoOp(ActionSourceType.Debug);
            dropReason = Stage7BTeacherReplayDropReason.Unknown;
            ResetLastReturnMappingDiagnostics();

            if (command == null)
            {
                dropReason = Stage7BTeacherReplayDropReason.MissingTeacherCommands;
                return false;
            }

            GridManager grid = GridManager.Instance;
            if (grid == null)
            {
                dropReason = Stage7BTeacherReplayDropReason.UnityStateApiMissing;
                return false;
            }

            GridPosition actorPos = ResolveActorPosition(command);
            if (!actorPos.IsInsideMap())
            {
                dropReason = Stage7BTeacherReplayDropReason.ActorNotFound;
                return false;
            }

            if (!grid.TryGetOccupant(actorPos, out UnitRuntime actor) || actor == null)
            {
                dropReason = Stage7BTeacherReplayDropReason.ActorNotFound;
                return false;
            }

            if (actor.Owner != playerPerspective)
            {
                dropReason = Stage7BTeacherReplayDropReason.ActorOwnerMismatch;
                return false;
            }

            if (command.action_type < ActionContract.ACTION_NOOP || command.action_type >= ActionContract.SIZE_ACTION_TYPE)
            {
                dropReason = Stage7BTeacherReplayDropReason.ActionTypeUnsupported;
                return false;
            }

            UnitActionType actionType = (UnitActionType)command.action_type;
            switch (actionType)
            {
                case UnitActionType.NoOp:
                    action = AgentAction.CreateNoOp(ActionSourceType.Debug);
                    dropReason = Stage7BTeacherReplayDropReason.None;
                    return true;

                case UnitActionType.Move:
                    if (!ActionContractMappings.TryDirectionFromIndex(command.move_dir, out Direction moveDir))
                    {
                        dropReason = Stage7BTeacherReplayDropReason.DirectionMismatch;
                        return false;
                    }

                    action = new AgentAction(actorPos, UnitActionType.Move, moveDir, sourceType: ActionSourceType.Debug);
                    dropReason = Stage7BTeacherReplayDropReason.None;
                    return true;

                case UnitActionType.Harvest:
                    if (!ActionContractMappings.TryDirectionFromIndex(command.harvest_dir, out Direction harvestDir))
                    {
                        dropReason = Stage7BTeacherReplayDropReason.DirectionMismatch;
                        return false;
                    }

                    if (actor.Type != UnitType.Worker)
                    {
                        dropReason = Stage7BTeacherReplayDropReason.ActorTypeMismatch;
                        return false;
                    }

                    action = new AgentAction(actorPos, UnitActionType.Harvest, harvestDir, sourceType: ActionSourceType.Debug);
                    dropReason = Stage7BTeacherReplayDropReason.None;
                    return true;

                case UnitActionType.Return:
                    LastRawTeacherReturnDir = command.return_dir;
                    LastReturnDirectionMappingMode = GetEffectiveReturnDirectionMappingMode();

                    if (command.return_dir < 0 || command.return_dir >= ActionContract.SIZE_DIRECTION)
                    {
                        dropReason = Stage7BTeacherReplayDropReason.DirectionMismatch;
                        return false;
                    }

                    Direction returnDir;
                    if (LastReturnDirectionMappingMode == ReturnDirectionMappingModeInvertYForLegacy032Teacher)
                    {
                        returnDir = ConvertLegacy032ReturnDirectionToUnity(command.return_dir);
                        LastReturnDirectionMappingApplied = true;
                    }
                    else
                    {
                        returnDir = (Direction)command.return_dir;
                        LastReturnDirectionMappingApplied = false;
                    }

                    LastMappedUnityReturnDir = (int)returnDir;

                    if (actor.Type != UnitType.Worker)
                    {
                        dropReason = Stage7BTeacherReplayDropReason.ActorTypeMismatch;
                        return false;
                    }

                    action = new AgentAction(actorPos, UnitActionType.Return, returnDir, sourceType: ActionSourceType.Debug);
                    dropReason = Stage7BTeacherReplayDropReason.None;
                    return true;

                case UnitActionType.Produce:
                    if (!ActionContractMappings.TryDirectionFromIndex(command.produce_dir, out Direction produceDir))
                    {
                        dropReason = Stage7BTeacherReplayDropReason.DirectionMismatch;
                        return false;
                    }

                    if (command.produce_unit_type < 0 || command.produce_unit_type >= ActionContract.SIZE_PRODUCE_UNIT_TYPE)
                    {
                        dropReason = Stage7BTeacherReplayDropReason.ProduceTypeMismatch;
                        return false;
                    }

                    action = new AgentAction(
                        actorPos,
                        UnitActionType.Produce,
                        produceDir,
                        (ProducibleUnit)command.produce_unit_type,
                        sourceType: ActionSourceType.Debug);
                    dropReason = Stage7BTeacherReplayDropReason.None;
                    return true;

                case UnitActionType.Attack:
                    if (command.attack_target_local < 0 || command.attack_target_local >= ActionContract.SIZE_ATTACK_TARGET)
                    {
                        dropReason = Stage7BTeacherReplayDropReason.AttackTargetMismatch;
                        return false;
                    }

                    if (!ActionContractMappings.TryGetAttackTargetPosition(actorPos, command.attack_target_local, out GridPosition attackTarget))
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

        private static GridPosition ResolveActorPosition(Stage7BTeacherReplayTeacherCommand command)
        {
            if (command.actor_flat >= 0 && command.actor_flat < ActionContract.TotalCells)
            {
                return GridPosition.FromFlatIndex(command.actor_flat);
            }

            return new GridPosition(command.actor_x, command.actor_y);
        }

        public static Direction ConvertLegacy032ReturnDirectionToUnity(int rawReturnDir)
        {
            switch (rawReturnDir)
            {
                case 0: return Direction.South;
                case 1: return Direction.East;
                case 2: return Direction.North;
                case 3: return Direction.West;
                default: return Direction.North;
            }
        }

        private string GetEffectiveReturnDirectionMappingMode()
        {
            if (returnDirectionMappingMode == ReturnDirectionMappingModeNone)
            {
                return ReturnDirectionMappingModeNone;
            }

            if (returnDirectionMappingMode == ReturnDirectionMappingModeInvertYForLegacy032Teacher)
            {
                return ReturnDirectionMappingModeInvertYForLegacy032Teacher;
            }

            return ReturnDirectionMappingModeInvertYForLegacy032Teacher;
        }

        private void ResetLastReturnMappingDiagnostics()
        {
            LastRawTeacherReturnDir = -1;
            LastMappedUnityReturnDir = -1;
            LastReturnDirectionMappingMode = GetEffectiveReturnDirectionMappingMode();
            LastReturnDirectionMappingApplied = false;
        }

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
