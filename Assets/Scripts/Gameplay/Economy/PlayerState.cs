// PlayerState.cs — централизованное состояние игрока.
// Этап 3: Экономика. Неделя 2.

using System;
using RTS.Core;

namespace RTS.Gameplay
{
    /// <summary>
    /// Чистая модель состояния одного игрока.
    /// Централизует управление ресурсами и счётчиками.
    /// </summary>
    [Serializable]
    public class PlayerState
    {
        // ── Идентификация ──────────────────────────────────────────────────────
        public Owner Owner { get; private set; }

        // ── Ресурсы ────────────────────────────────────────────────────────────
        public int CurrentResources { get; private set; }

        // ── Счётчики ───────────────────────────────────────────────────────────
        /// <summary>Количество построенных зданий (включая стартовую базу).</summary>
        public int BuildingCount { get; private set; }

        /// <summary>Количество произведённых волевых юнитов (workers, light, heavy, ranged).</summary>
        public int UnitCount { get; private set; }

        /// <summary>Количество уничтоженных юнитов противника.</summary>
        public int EnemyUnitsKilled { get; private set; }

        /// <summary>Количество потерянных своих юнитов.</summary>
        public int OwnUnitsLost { get; private set; }

        // ── События ────────────────────────────────────────────────────────────

        /// <summary>Вызывается, когда изменяется запас ресурсов (newAmount).</summary>
        public System.Action<int> OnResourcesChanged;

        /// <summary>Вызывается при попытке потратить больше ресурсов, чем есть (требуемая сумма).</summary>
        public System.Action<int> OnInsufficientResources;

        // ── Инициализация ──────────────────────────────────────────────────────

        public PlayerState(Owner owner, int startingResources = 0)
        {
            Owner = owner;
            CurrentResources = startingResources >= 0 ? startingResources : 0;
            BuildingCount = 0;
            UnitCount = 0;
            EnemyUnitsKilled = 0;
            OwnUnitsLost = 0;
        }

        // ── Ресурсы ────────────────────────────────────────────────────────────

        /// <summary>
        /// Проверяет, может ли игрок позволить себе стоимость.
        /// </summary>
        public bool CanAfford(int cost)
        {
            if (cost <= 0) return true;
            return CurrentResources >= cost;
        }

        /// <summary>
        /// Пытается потратить ресурсы. Возвращает true, если успешно.
        /// Если ресурсов недостаточно, вызывает OnInsufficientResources и возвращает false.
        /// </summary>
        public bool SpendResources(int cost)
        {
            if (cost <= 0) return true;

            if (!CanAfford(cost))
            {
                OnInsufficientResources?.Invoke(cost);
                return false;
            }

            CurrentResources -= cost;
            OnResourcesChanged?.Invoke(CurrentResources);
            return true;
        }

        /// <summary>
        /// Добавляет ресурсы игроку.
        /// </summary>
        public void AddResources(int amount)
        {
            if (amount <= 0) return;

            CurrentResources += amount;
            OnResourcesChanged?.Invoke(CurrentResources);
        }

        // ── Счётчики ───────────────────────────────────────────────────────────

        /// <summary>
        /// Регистрирует построение здания.
        /// </summary>
        public void RegisterBuilding()
        {
            BuildingCount++;
        }

        /// <summary>
        /// Регистрирует производство волевого юнита.
        /// </summary>
        public void RegisterUnit()
        {
            UnitCount++;
        }

        /// <summary>
        /// Регистрирует уничтожение враждебного юнита.
        /// </summary>
        public void RegisterEnemyKill()
        {
            EnemyUnitsKilled++;
        }

        /// <summary>
        /// Регистрирует потерю собственного юнита.
        /// </summary>
        public void RegisterOwnLoss()
        {
            OwnUnitsLost++;
        }

        // ── Reset ──────────────────────────────────────────────────────────────

        /// <summary>
        /// Сбрасывает состояние к исходному (для reset эпизода).
        /// </summary>
        public void ResetForEpisode(int startingResources = 0)
        {
            CurrentResources = startingResources >= 0 ? startingResources : 0;
            BuildingCount = 0;
            UnitCount = 0;
            EnemyUnitsKilled = 0;
            OwnUnitsLost = 0;
            OnResourcesChanged?.Invoke(CurrentResources);
        }
    }
}
