using RTS.Core;
using RTS.ML;
using RTS.MLAgents.Stage7B.CandidateActions;

namespace RTS.MLAgents.Stage7B.TeacherConversion
{
    public sealed class Stage7BCandidateMatcher
    {
        public bool TryMatch(
            AgentAction target,
            MlAgentsCandidateActionList candidates,
            out int candidateActionIndex,
            out Stage7BDropReason dropReason)
        {
            candidateActionIndex = MlAgentsCandidateActionList.NoOpCandidateIndex;
            dropReason = Stage7BDropReason.NoMatchingActor;

            if (candidates == null)
            {
                dropReason = Stage7BDropReason.StateReconstructionFailed;
                return false;
            }

            if (target.ActionType == UnitActionType.NoOp)
            {
                candidateActionIndex = MlAgentsCandidateActionList.NoOpCandidateIndex;
                dropReason = Stage7BDropReason.None;
                return true;
            }

            var all = candidates.AvailableCandidates;
            for (int i = 0; i < all.Count; i++)
            {
                MlAgentsCandidateAction c = all[i];
                if (c.IsNoOp)
                {
                    continue;
                }

                if (c.Action.ActorPosition != target.ActorPosition)
                {
                    continue;
                }

                if (c.Action.ActionType != target.ActionType)
                {
                    continue;
                }

                if (target.ActionType == UnitActionType.Move
                    || target.ActionType == UnitActionType.Harvest
                    || target.ActionType == UnitActionType.Return
                    || target.ActionType == UnitActionType.Produce)
                {
                    if (c.Action.Direction != target.Direction)
                    {
                        continue;
                    }
                }

                if (target.ActionType == UnitActionType.Attack
                    && c.Action.AttackTargetPosition != target.AttackTargetPosition)
                {
                    continue;
                }

                candidateActionIndex = c.CandidateIndex;
                dropReason = Stage7BDropReason.None;
                return true;
            }

            dropReason = Stage7BDropReason.NoMatchingActor;
            return false;
        }
    }
}
