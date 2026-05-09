using System;
using System.Collections.Generic;
using RTS.ML;

namespace RTS.MLAgents.Stage7B.CandidateActions
{
    public sealed class MlAgentsCandidateActionList
    {
        public const int BranchSize = 128;
        public const int NoOpCandidateIndex = 0;

        private readonly MlAgentsCandidateAction[] _slots = new MlAgentsCandidateAction[BranchSize];
        private readonly List<MlAgentsCandidateAction> _available = new List<MlAgentsCandidateAction>(BranchSize);

        public MlAgentsCandidateActionList()
        {
            Clear();
        }

        public IReadOnlyList<MlAgentsCandidateAction> AvailableCandidates => _available;
        public int CandidateCount => _available.Count;
        public int LegalNonNoOpCount { get; private set; }
        public int OverflowCount { get; private set; }
        public bool Overflowed => OverflowCount > 0;
        public int EmptySlotCount => BranchSize - CandidateCount;
        public ActionMaskSet SourceMask { get; private set; }

        public void Clear()
        {
            for (int i = 0; i < _slots.Length; i++)
            {
                _slots[i] = MlAgentsCandidateAction.Empty;
            }

            _available.Clear();
            LegalNonNoOpCount = 0;
            OverflowCount = 0;
            SourceMask = null;
        }

        public void SetSourceMask(ActionMaskSet sourceMask)
        {
            SourceMask = sourceMask;
        }

        public void AddNoOp(AgentAction noOp)
        {
            var candidate = new MlAgentsCandidateAction(
                NoOpCandidateIndex,
                noOp,
                new CandidateActionSortKey(-1, RTS.Core.UnitActionType.NoOp, 0, 0, 24),
                24,
                isNoOp: true);
            _slots[NoOpCandidateIndex] = candidate;
            _available.Add(candidate);
        }

        public void AddLegalCandidates(IReadOnlyList<MlAgentsCandidateAction> sortedLegalCandidates)
        {
            LegalNonNoOpCount = sortedLegalCandidates != null ? sortedLegalCandidates.Count : 0;
            if (sortedLegalCandidates == null)
            {
                return;
            }

            int writable = Math.Min(BranchSize - 1, sortedLegalCandidates.Count);
            for (int i = 0; i < writable; i++)
            {
                MlAgentsCandidateAction source = sortedLegalCandidates[i];
                int candidateIndex = i + 1;
                var candidate = new MlAgentsCandidateAction(
                    candidateIndex,
                    source.Action,
                    source.SortKey,
                    source.AttackTargetLocalIndex,
                    isNoOp: false);
                _slots[candidateIndex] = candidate;
                _available.Add(candidate);
            }

            OverflowCount = Math.Max(0, sortedLegalCandidates.Count - writable);
        }

        public bool IsIndexAvailable(int candidateIndex)
        {
            return candidateIndex >= 0
                   && candidateIndex < BranchSize
                   && !_slots[candidateIndex].IsEmpty;
        }

        public MlAgentsCandidateAction GetOrEmpty(int candidateIndex)
        {
            if (candidateIndex < 0 || candidateIndex >= BranchSize)
            {
                return MlAgentsCandidateAction.Empty;
            }

            return _slots[candidateIndex];
        }
    }
}
