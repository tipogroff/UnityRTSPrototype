// UnitType.cs — перечисление типов юнитов (единственный источник истины)
// Технический контракт MVP. Неделя 1.
// ВАЖНО: порядок enum-значений соответствует индексам one-hot каналов
// в ObservationContract (каналы 5-11). Не менять порядок без обновления
// ObservationContract и Python-стороны.

namespace RTS.Core
{
    /// <summary>
    /// Тип юнита. Совпадает с Gym-µRTS unit-type order (Resource=0..Ranged=6).
    /// </summary>
    public enum UnitType
    {
        Resource  = 0,
        Base      = 1,
        Barracks  = 2,
        Worker    = 3,
        Light     = 4,
        Heavy     = 5,
        Ranged    = 6
    }

    /// <summary>
    /// Принадлежность клетки / юнита.
    /// Совпадает с one-hot каналами owner в ObservationContract (каналы 2-4).
    /// </summary>
    public enum Owner
    {
        Neutral = 0,
        Player1 = 1,
        Player2 = 2
    }

    /// <summary>
    /// Тип действия, которое юнит выполняет в текущий тик.
    /// Совпадает с one-hot каналами current_action в ObservationContract (каналы 12-17).
    /// </summary>
    public enum UnitActionType
    {
        NoOp     = 0,
        Move     = 1,
        Harvest  = 2,
        Return   = 3,
        Produce  = 4,
        Attack   = 5
    }

    /// <summary>
    /// Направление: NESW. Используется как параметр Move, Harvest, Return, Produce.
    /// Совпадает с one-hot каналами action_dir в ObservationContract (каналы 18-21)
    /// и ветвью ActionContract.BranchDirection.
    /// </summary>
    public enum Direction
    {
        North = 0,
        East  = 1,
        South = 2,
        West  = 3
    }

    /// <summary>
    /// Типы юнитов, которые можно произвести. Параметр действия Produce.
    /// Совпадает с one-hot каналами produce_type в ObservationContract (каналы 22-25)
    /// и ветвью ActionContract.BranchProduceType.
    /// </summary>
    public enum ProducibleUnit
    {
        Worker = 0,
        Light  = 1,
        Heavy  = 2,
        Ranged = 3
    }
}
