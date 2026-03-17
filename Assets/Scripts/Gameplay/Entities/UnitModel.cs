// UnitModel.cs — чистая модель данных юнита (без MonoBehaviour).
// Неделя 2, Этап 2 (Игровые сущности).

using System;
using RTS.Core;

namespace RTS.Gameplay
{
    /// <summary>
    /// Чистая модель состояния юнита, отделённая от scene-object логики.
    /// Удобна для reset, сериализации, observation builder и BC-пайплайна.
    /// </summary>
    [Serializable]
    public class UnitModel
    {
        public UnitType Type { get; private set; }
        public Owner Owner { get; private set; }
        public bool IsBuilding { get; private set; }

        public int MaxHP { get; private set; }
        public int CurrentHP { get; private set; }

        public GridPosition GridPosition { get; private set; }

        public int CarriedResources { get; private set; }
        public int MaxCarryCapacity { get; private set; }

        public bool IsAlive => CurrentHP > 0;

        public UnitModel(
            UnitType type,
            Owner owner,
            int maxHP,
            GridPosition startPos,
            bool isBuilding = false,
            int startCarriedResources = 0,
            int maxCarryCapacity = GameConstants.MaxCarryCapacity)
        {
            Type = type;
            Owner = owner;
            IsBuilding = isBuilding;
            MaxHP = Math.Max(1, maxHP);
            CurrentHP = MaxHP;
            GridPosition = startPos;
            MaxCarryCapacity = Math.Max(0, maxCarryCapacity);
            CarriedResources = Math.Clamp(startCarriedResources, 0, MaxCarryCapacity);
        }

        public static UnitModel FromDefinition(UnitDefinition definition, Owner owner, GridPosition startPos)
        {
            if (definition == null)
                throw new ArgumentNullException(nameof(definition));

            return new UnitModel(
                definition.unitType,
                owner,
                definition.maxHitPoints,
                startPos,
                definition.isBuilding,
                0,
                GameConstants.MaxCarryCapacity);
        }

        public void SetGridPosition(GridPosition newPos)
        {
            GridPosition = newPos;
        }

        /// <summary>
        /// Применяет урон. Возвращает true, если юнит погиб после удара.
        /// </summary>
        public bool TakeDamage(int amount)
        {
            if (amount <= 0) return !IsAlive;

            CurrentHP = Math.Max(0, CurrentHP - amount);
            return !IsAlive;
        }

        public void Heal(int amount)
        {
            if (amount <= 0 || !IsAlive) return;
            CurrentHP = Math.Min(MaxHP, CurrentHP + amount);
        }

        /// <summary>
        /// Пытается добавить переносимые ресурсы в пределах capacity.
        /// Возвращает реально добавленное количество.
        /// </summary>
        public int AddCarriedResources(int amount)
        {
            if (amount <= 0 || MaxCarryCapacity <= 0) return 0;

            int free = MaxCarryCapacity - CarriedResources;
            int added = Math.Min(free, amount);
            CarriedResources += added;
            return added;
        }

        /// <summary>
        /// Сбрасывает переносимые ресурсы и возвращает количество, которое было в руках.
        /// </summary>
        public int DropAllCarriedResources()
        {
            int dropped = CarriedResources;
            CarriedResources = 0;
            return dropped;
        }

        /// <summary>
        /// Сброс состояния в начало эпизода: full HP, новая позиция, пустые руки.
        /// </summary>
        public void ResetForEpisode(GridPosition spawnPos)
        {
            GridPosition = spawnPos;
            CurrentHP = MaxHP;
            CarriedResources = 0;
        }
    }
}
