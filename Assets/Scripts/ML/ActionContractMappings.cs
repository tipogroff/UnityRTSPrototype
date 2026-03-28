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