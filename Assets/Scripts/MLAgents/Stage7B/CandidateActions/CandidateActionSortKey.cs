using System;
using RTS.Core;

namespace RTS.MLAgents.Stage7B.CandidateActions
{
    public readonly struct CandidateActionSortKey : IComparable<CandidateActionSortKey>
    {
        public CandidateActionSortKey(
            int actorFlatIndex,
            UnitActionType actionType,
            int direction,
            int produceUnitType,
            int attackTargetLocal)
        {
            ActorFlatIndex = actorFlatIndex;
            ActionType = actionType;
            Direction = direction;
            ProduceUnitType = produceUnitType;
            AttackTargetLocal = attackTargetLocal;
        }

        public int ActorFlatIndex { get; }
        public UnitActionType ActionType { get; }
        public int Direction { get; }
        public int ProduceUnitType { get; }
        public int AttackTargetLocal { get; }

        public int CompareTo(CandidateActionSortKey other)
        {
            int cmp = ActorFlatIndex.CompareTo(other.ActorFlatIndex);
            if (cmp != 0) return cmp;

            cmp = ((int)ActionType).CompareTo((int)other.ActionType);
            if (cmp != 0) return cmp;

            cmp = Direction.CompareTo(other.Direction);
            if (cmp != 0) return cmp;

            cmp = ProduceUnitType.CompareTo(other.ProduceUnitType);
            if (cmp != 0) return cmp;

            return AttackTargetLocal.CompareTo(other.AttackTargetLocal);
        }
    }
}
