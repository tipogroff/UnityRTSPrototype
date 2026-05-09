using RTS.Core;
using RTS.Gameplay;
using RTS.ML;

namespace RTS.MLAgents.Stage7B.CandidateActions
{
    public sealed class MlAgentsActionAdapter
    {
        public AgentAction Resolve(MlAgentsCandidateActionList candidates, int candidateIndex, out MlAgentsCandidateAction candidate)
        {
            candidate = candidates != null
                ? candidates.GetOrEmpty(candidateIndex)
                : MlAgentsCandidateAction.Empty;

            if (candidate.IsEmpty)
            {
                return AgentAction.CreateInvalid(
                    GridPosition.Zero,
                    $"candidate_action_index {candidateIndex} is empty or outside branch size",
                    ActionSourceType.Debug);
            }

            return candidate.Action;
        }
    }
}
