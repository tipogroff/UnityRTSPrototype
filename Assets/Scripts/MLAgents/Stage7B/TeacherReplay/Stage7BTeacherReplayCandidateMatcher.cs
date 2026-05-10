using RTS.Core;
using RTS.ML;
using RTS.MLAgents.Stage7B.CandidateActions;

namespace RTS.MLAgents.Stage7B.TeacherReplay
{
    public sealed class Stage7BTeacherReplayCandidateMatcher
    {
        public bool TryMatch(
            AgentAction teacherAction,
            MlAgentsCandidateActionList candidates,
            out int candidateIndex,
            out Stage7BTeacherReplayDropReason dropReason)
        {
            candidateIndex = -1;
            dropReason = Stage7BTeacherReplayDropReason.Unknown;

            if (candidates == null)
            {
                dropReason = Stage7BTeacherReplayDropReason.MissingRuntimeState;
                return false;
            }

            if (teacherAction.ActionType == UnitActionType.NoOp)
            {
                candidateIndex = MlAgentsCandidateActionList.NoOpCandidateIndex;
                dropReason = Stage7BTeacherReplayDropReason.None;
                return true;
            }

            for (int i = 0; i < candidates.AvailableCandidates.Count; i++)
            {
                MlAgentsCandidateAction candidate = candidates.AvailableCandidates[i];
                if (candidate.IsEmpty)
                {
                    continue;
                }

                if (ActionsEqual(teacherAction, candidate.Action))
                {
                    candidateIndex = candidate.CandidateIndex;
                    dropReason = Stage7BTeacherReplayDropReason.None;
                    return true;
                }
            }

            dropReason = Stage7BTeacherReplayDropReason.NoMatchingActor;
            return false;
        }

        private static bool ActionsEqual(AgentAction a, AgentAction b)
        {
            if (a.ActionType != b.ActionType)
            {
                return false;
            }

            if (a.ActionType == UnitActionType.NoOp)
            {
                return true;
            }

            if (a.ActorPosition != b.ActorPosition)
            {
                return false;
            }

            switch (a.ActionType)
            {
                case UnitActionType.Move:
                case UnitActionType.Harvest:
                case UnitActionType.Return:
                    return a.Direction == b.Direction;
                case UnitActionType.Produce:
                    return a.Direction == b.Direction && (int)a.ProduceUnitType == (int)b.ProduceUnitType;
                case UnitActionType.Attack:
                    return a.AttackTargetPosition == b.AttackTargetPosition;
                default:
                    return false;
            }
        }
    }
}
