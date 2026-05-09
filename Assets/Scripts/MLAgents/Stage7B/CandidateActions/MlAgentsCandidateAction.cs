using RTS.ML;

namespace RTS.MLAgents.Stage7B.CandidateActions
{
    public readonly struct MlAgentsCandidateAction
    {
        public MlAgentsCandidateAction(
            int candidateIndex,
            AgentAction action,
            CandidateActionSortKey sortKey,
            int attackTargetLocalIndex,
            bool isNoOp)
        {
            CandidateIndex = candidateIndex;
            Action = action;
            SortKey = sortKey;
            AttackTargetLocalIndex = attackTargetLocalIndex;
            IsNoOp = isNoOp;
        }

        public int CandidateIndex { get; }
        public AgentAction Action { get; }
        public CandidateActionSortKey SortKey { get; }
        public int AttackTargetLocalIndex { get; }
        public bool IsNoOp { get; }
        public bool IsEmpty => CandidateIndex < 0;

        public static MlAgentsCandidateAction Empty => new MlAgentsCandidateAction(
            -1,
            AgentAction.CreateNoOp(ActionSourceType.Debug),
            new CandidateActionSortKey(int.MaxValue, RTS.Core.UnitActionType.NoOp, int.MaxValue, int.MaxValue, int.MaxValue),
            -1,
            false);
    }
}
