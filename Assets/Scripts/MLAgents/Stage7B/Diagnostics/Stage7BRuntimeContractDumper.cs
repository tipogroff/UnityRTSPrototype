using RTS.ML;
using RTS.MLAgents.Stage7B.CandidateActions;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.Diagnostics
{
    [DisallowMultipleComponent]
    public sealed class Stage7BRuntimeContractDumper : MonoBehaviour
    {
        [SerializeField] private bool _dumpOnStart = true;

        private void Start()
        {
            if (_dumpOnStart)
            {
                Dump();
            }
        }

        public void Dump()
        {
            Debug.Log(
                "[Stage7B][Contract] observation=vector " + ObservationContract.TotalFloats +
                ", action=discrete[0]=candidate_action_index branchSize=" + MlAgentsCandidateActionList.BranchSize +
                ", candidate[0]=NoOp, candidates[1..127]=runtime-mask-derived AgentAction, " +
                "ActionApplier/MatchManager remain authoritative.");
        }
    }
}
