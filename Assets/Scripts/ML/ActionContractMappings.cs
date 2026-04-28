using System;
using RTS.Core;
using RTS.Gameplay;

namespace RTS.ML
{
    internal static class ActionContractMappings
    {
        internal static bool TryDirectionFromIndex(int value, out Direction direction)
        {
            if (value >= 0 && value < ActionContract.SIZE_DIRECTION)
            {
                direction = (Direction)value;
                return true;
            }

            direction = Direction.North;
            return false;
        }

        internal static int UnitTypeToObservationIndex(UnitType type)
        {
            return type switch
            {
                UnitType.Resource => 0,
                UnitType.Base => 1,
                UnitType.Barracks => 2,
                UnitType.Worker => 3,
                UnitType.Light => 4,
                UnitType.Heavy => 5,
                UnitType.Ranged => 6,
                _ => -1
            };
        }

        internal static int DirectionToObservationIndex(Direction direction)
        {
            return direction switch
            {
                Direction.North => 0,
                Direction.East => 1,
                Direction.South => 2,
                Direction.West => 3,
                _ => -1
            };
        }

        internal static int ProducibleUnitToObservationIndex(ProducibleUnit unit)
        {
            return unit switch
            {
                ProducibleUnit.Worker => 0,
                ProducibleUnit.Light => 1,
                ProducibleUnit.Heavy => 2,
                ProducibleUnit.Ranged => 3,
                _ => -1
            };
        }

        internal static int UnitActionTypeToObservationIndex(UnitActionType actionType)
        {
            return actionType switch
            {
                UnitActionType.NoOp => 0,
                UnitActionType.Move => 1,
                UnitActionType.Harvest => 2,
                UnitActionType.Return => 3,
                UnitActionType.Produce => 4,
                UnitActionType.Attack => 5,
                _ => 0
            };
        }

        internal static int UnitTypeToProducibleUnitObservationIndex(UnitType unitType)
        {
            return unitType switch
            {
                UnitType.Worker => 0,
                UnitType.Light => 1,
                UnitType.Heavy => 2,
                UnitType.Ranged => 3,
                _ => -1
            };
        }

        internal static bool TryMapProducibleUnitType(ProducibleUnit produceType, out UnitType unitType)
        {
            unitType = produceType switch
            {
                ProducibleUnit.Worker => UnitType.Worker,
                ProducibleUnit.Light => UnitType.Light,
                ProducibleUnit.Heavy => UnitType.Heavy,
                ProducibleUnit.Ranged => UnitType.Ranged,
                _ => UnitType.Worker
            };

            return produceType == ProducibleUnit.Worker
                   || produceType == ProducibleUnit.Light
                   || produceType == ProducibleUnit.Heavy
                   || produceType == ProducibleUnit.Ranged;
        }

        /// <summary>
        /// Maps v2 contract-level produce branch index to UnitType using Gym/Gridnet order:
        /// 0=Resource, 1=Base, 2=Barracks, 3=Worker, 4=Light, 5=Heavy, 6=Ranged.
        ///
        /// IMPORTANT: successful mapping to UnitType does not mean the Produce action is valid
        /// in the current runtime context. Context-validity (actor type, game rules, queue, etc.)
        /// is determined by mask/runtime validation layers.
        /// </summary>
        internal static bool TryMapV2ProduceIndexToUnitType(int index, out UnitType unitType)
        {
            unitType = index switch
            {
                0 => UnitType.Resource,
                1 => UnitType.Base,
                2 => UnitType.Barracks,
                3 => UnitType.Worker,
                4 => UnitType.Light,
                5 => UnitType.Heavy,
                6 => UnitType.Ranged,
                _ => UnitType.Worker
            };

            return index >= 0 && index < ActionContract.SIZE_PRODUCE_UNIT_TYPE;
        }

        /// <summary>
        /// MVP ENCODING RULE (tech-debt, temporary): Worker + Produce action = "build Barracks".
        ///
        /// The 4-slot BRANCH_PRODUCE_UNIT_TYPE contract has no dedicated build-structure slot.
        /// A Produce command issued by a Worker actor is unconditionally treated as
        /// "build Barracks at the adjacent cell indicated by the Produce direction branch".
        /// The ProduceUnitType slot value (Worker=0) is set only as a structurally valid
        /// placeholder; it is IGNORED at all downstream dispatch points when actor is Worker.
        ///
        /// All three dispatch layers share this rule by checking actor type first:
        ///   • ActionMaskBuilder.BuildProduceMask → BuildWorkerBuildMask
        ///   • ActionApplier.ValidateProduceAction → ValidateWorkerBuildBarracks
        ///   • MatchManager.TryExecuteProduce → TryWorkerBuildBarracks (game-logic layer,
        ///     performs the same type check independently to avoid cross-layer coupling)
        ///
        /// Future work: replace with a dedicated produce-slot or separate action-type branch
        /// if this encoding causes BC/teacher-pipeline confusion or policy gradient ambiguity.
        /// </summary>
        internal static bool IsWorkerBuildBarracksAction(UnitType actorType)
            => actorType == UnitType.Worker;

        internal static bool TryGetAttackTargetPosition(GridPosition actorPosition, int localIndex, out GridPosition targetPosition)
        {
            targetPosition = GridPosition.Zero;
            if (localIndex < 0 || localIndex >= ActionContract.AttackOffsets.Length)
            {
                return false;
            }

            var (offsetX, offsetY) = ActionContract.AttackOffsets[localIndex];
            targetPosition = new GridPosition(actorPosition.X + offsetX, actorPosition.Y + offsetY);
            return targetPosition.IsInsideMap();
        }

        internal static string FormatEnabledValues(bool[] mask, Func<int, string> labelProvider, string emptyValue)
        {
            if (mask == null || labelProvider == null)
            {
                return emptyValue;
            }

            var labels = new System.Collections.Generic.List<string>(mask.Length);
            for (int i = 0; i < mask.Length; i++)
            {
                if (mask[i])
                {
                    labels.Add(labelProvider(i));
                }
            }

            return labels.Count == 0 ? emptyValue : string.Join("|", labels);
        }
    }
}