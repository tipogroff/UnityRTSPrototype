using RTS.Core;
using RTS.Gameplay;
using RTS.ML;

namespace RTS.Presentation.Orders
{
    public static class ProductionCommandHelper
    {
        public static bool TryCreateAction(
            UnitRuntime producer,
            UnitType producedType,
            out AgentAction action,
            out string reason)
        {
            action = default;
            reason = string.Empty;

            if (producer == null)
            {
                reason = "No selected producer.";
                return false;
            }

            if (!TryGetRawV2ProduceIndex(producer.Type, producedType, out int rawV2Index))
            {
                reason = $"{producer.Type} cannot produce {producedType}.";
                return false;
            }

            action = new AgentAction(
                actorPosition: producer.GridPos,
                actionType: UnitActionType.Produce,
                direction: Direction.North,
                produceUnitType: (ProducibleUnit)rawV2Index,
                attackTargetPosition: default,
                isValid: true,
                invalidationReason: string.Empty,
                sourceType: ActionSourceType.Debug);
            return true;
        }

        public static bool TryGetRawV2ProduceIndex(UnitType producerType, UnitType producedType, out int rawV2Index)
        {
            rawV2Index = (producerType, producedType) switch
            {
                (UnitType.Base, UnitType.Worker) => 3,
                (UnitType.Barracks, UnitType.Light) => 4,
                (UnitType.Barracks, UnitType.Heavy) => 5,
                (UnitType.Barracks, UnitType.Ranged) => 6,
                _ => -1
            };

            return rawV2Index >= 0;
        }

        public static bool TryCreateBuildBarracksAction(
            UnitRuntime worker,
            Direction buildDirection,
            out AgentAction action,
            out string reason)
        {
            action = default;
            reason = string.Empty;

            if (worker == null)
            {
                reason = "Build Barracks worker is missing.";
                return false;
            }

            if (worker.Owner != Owner.Player2 || worker.Type != UnitType.Worker)
            {
                reason = "Build Barracks requires a Player2 Worker.";
                return false;
            }

            action = new AgentAction(
                actorPosition: worker.GridPos,
                actionType: UnitActionType.Produce,
                direction: buildDirection,
                produceUnitType: (ProducibleUnit)2,
                attackTargetPosition: default,
                isValid: true,
                invalidationReason: string.Empty,
                sourceType: ActionSourceType.Debug);
            return true;
        }
    }
}
