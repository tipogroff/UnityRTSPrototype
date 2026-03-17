// ProductionQueue.cs — простая очередь производства для здания.
// Этап 3: Экономика. Неделя 2 (упрощённая версия).

using System;
using System.Collections.Generic;
using RTS.Core;

namespace RTS.Gameplay
{
    /// <summary>
    /// Простая очередь производства для здания (обычно базы).
    /// Неделя 2 версия: одно производство за раз, одна очередь.
    /// </summary>
    [Serializable]
    public class ProductionQueue
    {
        // ── Владелец ───────────────────────────────────────────────────────────
        public Owner Owner { get; private set; }
        public GridPosition BuildingPosition { get; private set; }

        // ── Текущее производство ───────────────────────────────────────────────
        /// <summary>Тип юнита, который сейчас производится (null если ничего).</summary>
        public UnitType? CurrentProducingType { get; private set; } = null;

        /// <summary>Сколько тиков осталось до завершения производства.</summary>
        public int ProductionTimeRemaining { get; private set; } = 0;

        /// <summary>Общее время производства текущего юнита (для прогрессбара).</summary>
        public int ProductionTimeFull { get; private set; } = 0;

        // ── События ────────────────────────────────────────────────────────────

        /// <summary>Вызывается, когда производство юнита завершено и готов spawn.</summary>
        public System.Action<UnitType, GridPosition> OnProductionComplete;

        // ── Инициализация ──────────────────────────────────────────────────────

        public ProductionQueue(Owner owner, GridPosition buildingPosition)
        {
            Owner = owner;
            BuildingPosition = buildingPosition;
        }

        // ── Статус ───────────────────────────────────────────────────────────────

        /// <summary>
        /// true, если сейчас идёт производство какого-то юнита.
        /// </summary>
        public bool IsProducing => CurrentProducingType.HasValue && ProductionTimeRemaining > 0;

        /// <summary>
        /// Возвращает прогресс производства в диапазоне [0, 1].
        /// </summary>
        public float ProductionProgress
        {
            get
            {
                if (ProductionTimeFull <= 0) return 0f;
                return 1f - (ProductionTimeRemaining / (float)ProductionTimeFull);
            }
        }

        // ── Команды ────────────────────────────────────────────────────────────

        /// <summary>
        /// Начать производство юнита определённого типа.
        /// Если сейчас что-то производится, это будет заменено (упрощённо для Недели 2).
        /// </summary>
        /// <param name="unitType">Тип юнита для производства.</param>
        /// <param name="definition">UnitDefinition этого типа (содержит productionTime и productionCost).</param>
        public void StartProduction(UnitType unitType, UnitDefinition definition)
        {
            if (definition == null)
                throw new ArgumentNullException(nameof(definition));

            CurrentProducingType = unitType;
            ProductionTimeFull = definition.productionTime;
            ProductionTimeRemaining = definition.productionTime;
        }

        /// <summary>
        /// Продвигает производство на один тик.
        /// Возвращает true, если производство только что завершилось.
        /// </summary>
        public bool AdvanceProduction()
        {
            if (!IsProducing) return false;

            ProductionTimeRemaining--;

            if (ProductionTimeRemaining <= 0)
            {
                var completedType = CurrentProducingType.Value;
                OnProductionComplete?.Invoke(completedType, BuildingPosition);
                CurrentProducingType = null;
                ProductionTimeRemaining = 0;
                ProductionTimeFull = 0;
                return true;
            }

            return false;
        }

        /// <summary>
        /// Отменяет текущее производство.
        /// </summary>
        public void CancelProduction()
        {
            CurrentProducingType = null;
            ProductionTimeRemaining = 0;
            ProductionTimeFull = 0;
        }

        // ── Reset ──────────────────────────────────────────────────────────────

        /// <summary>
        /// Сбрасывает очередь (для reset эпизода).
        /// </summary>
        public void ResetForEpisode()
        {
            CancelProduction();
        }
    }
}
