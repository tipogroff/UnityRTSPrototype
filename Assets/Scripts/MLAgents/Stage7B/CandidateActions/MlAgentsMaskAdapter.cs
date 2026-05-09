using Unity.MLAgents.Actuators;

namespace RTS.MLAgents.Stage7B.CandidateActions
{
    public sealed class MlAgentsMaskAdapter
    {
        public int LastMaskedEmptySlots { get; private set; }

        public void WriteDiscreteActionMask(IDiscreteActionMask actionMask, MlAgentsCandidateActionList candidates)
        {
            LastMaskedEmptySlots = 0;
            if (actionMask == null)
            {
                return;
            }

            for (int i = 1; i < MlAgentsCandidateActionList.BranchSize; i++)
            {
                bool enabled = candidates != null && candidates.IsIndexAvailable(i);
                if (!enabled)
                {
                    LastMaskedEmptySlots++;
                }

                actionMask.SetActionEnabled(0, i, enabled);
            }

            actionMask.SetActionEnabled(0, MlAgentsCandidateActionList.NoOpCandidateIndex, true);
        }
    }
}
