using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using RTS.ML;

namespace RTS.MLAgents.Stage7B.CandidateActions
{
    public sealed class MlAgentsCandidateActionBuilder
    {
        private const int AttackCenterLocalIndex = 24;

        private readonly ActionMaskBuilder _maskBuilder;
        private readonly List<MlAgentsCandidateAction> _scratch = new List<MlAgentsCandidateAction>(256);

        public MlAgentsCandidateActionBuilder(ActionMaskBuilder maskBuilder)
        {
            _maskBuilder = maskBuilder ?? throw new System.ArgumentNullException(nameof(maskBuilder));
        }

        public MlAgentsCandidateActionList Build(Owner player)
        {
            ActionMaskSet mask = _maskBuilder.BuildTransferCompatibleMask(player, noOpOnlyWhenNotRunning: true);
            var result = new MlAgentsCandidateActionList();
            result.SetSourceMask(mask);
            result.AddNoOp(AgentAction.CreateNoOp(ActionSourceType.Debug));

            _scratch.Clear();
            if (mask == null || !mask.IsMatchRunning)
            {
                return result;
            }

            for (int actorFlatIndex = 0; actorFlatIndex < ActionContract.TotalCells; actorFlatIndex++)
            {
                if (!mask.ActorCellMask[actorFlatIndex])
                {
                    continue;
                }

                ActorActionMask actorMask = mask.GetActorMaskByFlatIndex(actorFlatIndex);
                if (actorMask == null)
                {
                    continue;
                }

                GridPosition actorPosition = GridPosition.FromFlatIndex(actorFlatIndex);
                AddDirectionalCandidates(actorFlatIndex, actorPosition, actorMask, UnitActionType.Move, actorMask.MoveDirectionMask);
                AddDirectionalCandidates(actorFlatIndex, actorPosition, actorMask, UnitActionType.Harvest, actorMask.HarvestDirectionMask);
                AddDirectionalCandidates(actorFlatIndex, actorPosition, actorMask, UnitActionType.Return, actorMask.ReturnDirectionMask);
                AddProduceCandidates(actorFlatIndex, actorPosition, actorMask);
                AddAttackCandidates(actorFlatIndex, actorPosition, actorMask);
            }

            _scratch.Sort((a, b) => a.SortKey.CompareTo(b.SortKey));
            result.AddLegalCandidates(_scratch);
            return result;
        }

        private void AddDirectionalCandidates(
            int actorFlatIndex,
            GridPosition actorPosition,
            ActorActionMask actorMask,
            UnitActionType actionType,
            bool[] directionMask)
        {
            if (!actorMask.IsActionTypeEnabled(actionType) || directionMask == null)
            {
                return;
            }

            for (int direction = 0; direction < directionMask.Length; direction++)
            {
                if (!directionMask[direction])
                {
                    continue;
                }

                var key = new CandidateActionSortKey(actorFlatIndex, actionType, direction, 3, AttackCenterLocalIndex);
                var action = new AgentAction(
                    actorPosition,
                    actionType,
                    (Direction)direction,
                    (ProducibleUnit)3,
                    GridPosition.Zero,
                    isValid: true,
                    sourceType: ActionSourceType.Debug);
                _scratch.Add(new MlAgentsCandidateAction(-1, action, key, AttackCenterLocalIndex, isNoOp: false));
            }
        }

        private void AddProduceCandidates(int actorFlatIndex, GridPosition actorPosition, ActorActionMask actorMask)
        {
            if (!actorMask.IsActionTypeEnabled(UnitActionType.Produce))
            {
                return;
            }

            for (int direction = 0; direction < actorMask.ProduceDirectionMask.Length; direction++)
            {
                if (!actorMask.ProduceDirectionMask[direction])
                {
                    continue;
                }

                for (int produceType = 0; produceType < actorMask.ProduceUnitTypeMask.Length; produceType++)
                {
                    if (!actorMask.ProduceUnitTypeMask[produceType])
                    {
                        continue;
                    }

                    var key = new CandidateActionSortKey(actorFlatIndex, UnitActionType.Produce, direction, produceType, AttackCenterLocalIndex);
                    var action = new AgentAction(
                        actorPosition,
                        UnitActionType.Produce,
                        (Direction)direction,
                        (ProducibleUnit)produceType,
                        GridPosition.Zero,
                        isValid: true,
                        sourceType: ActionSourceType.Debug);
                    _scratch.Add(new MlAgentsCandidateAction(-1, action, key, AttackCenterLocalIndex, isNoOp: false));
                }
            }
        }

        private void AddAttackCandidates(int actorFlatIndex, GridPosition actorPosition, ActorActionMask actorMask)
        {
            if (!actorMask.IsActionTypeEnabled(UnitActionType.Attack))
            {
                return;
            }

            for (int attackLocal = 0; attackLocal < actorMask.AttackTargetLocalMask.Length; attackLocal++)
            {
                if (!actorMask.AttackTargetLocalMask[attackLocal])
                {
                    continue;
                }

                if (!ActionContractMappings.TryGetAttackTargetPosition(actorPosition, attackLocal, out GridPosition target))
                {
                    continue;
                }

                var key = new CandidateActionSortKey(actorFlatIndex, UnitActionType.Attack, 0, 3, attackLocal);
                var action = new AgentAction(
                    actorPosition,
                    UnitActionType.Attack,
                    Direction.North,
                    (ProducibleUnit)3,
                    target,
                    isValid: true,
                    sourceType: ActionSourceType.Debug);
                _scratch.Add(new MlAgentsCandidateAction(-1, action, key, attackLocal, isNoOp: false));
            }
        }
    }
}
