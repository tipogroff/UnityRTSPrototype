// ResourceNode.cs — чистая модель ресурсного патча (клетки с ресурсами).
// Этап 3: Экономика. Неделя 2.

using System;
using RTS.Core;

namespace RTS.Gameplay
{
    /// <summary>
    /// Чистая модель ресурсного узла (патча ресурсов).
    /// Отделена от scene-object логики, удобна для reset и наблюдений.
    /// </summary>
    [Serializable]
    public class ResourceNode
    {
        // ── Позиция ────────────────────────────────────────────────────────────
        public GridPosition GridPosition { get; private set; }

        // ── Текущее состояние ──────────────────────────────────────────────────
        public int MaxResources { get; private set; }
        public int CurrentResources { get; private set; }

        /// <summary>
        /// Ресурс исчерпан и не может быть больше добыт.
        /// </summary>
        public bool IsExhausted => CurrentResources <= 0;

        // ── События ────────────────────────────────────────────────────────────

        /// <summary>
        /// Вызывается, когда ресурс полностью исчерпан (CurrentResources == 0).
        /// Передаёт GridPosition исчерпанного узла.
        /// </summary>
        public System.Action<GridPosition> OnResourceExhausted;

        // ── Инициализация ──────────────────────────────────────────────────────

        public ResourceNode(GridPosition position, int maxResources = 0)
        {
            GridPosition = position;
            // Если maxResources == 0, используется значение по умолчанию из констант
            MaxResources = maxResources > 0 ? maxResources : GameConstants.MaxResourcesPerPatch;
            CurrentResources = MaxResources;
        }

        // ── Операции ───────────────────────────────────────────────────────────

        public void SetGridPosition(GridPosition newPos)
        {
            GridPosition = newPos;
        }

        /// <summary>
        /// Добывает ресурс из этого узла.
        /// Возвращает фактически добытое количество (может быть меньше requested, если ресурс почти исчерпан).
        /// Если ресурс полностью исчерпан, вызывает OnResourceExhausted.
        /// </summary>
        /// <param name="amount">Желаемое количество для добычи.</param>
        /// <returns>Фактически добытое количество.</returns>
        public int Harvest(int amount)
        {
            if (amount <= 0) return 0;
            if (IsExhausted) return 0;

            int harvested = Math.Min(amount, CurrentResources);
            CurrentResources -= harvested;

            // Если только что стал исчерпан, вызываем событие
            if (IsExhausted && OnResourceExhausted != null)
            {
                OnResourceExhausted.Invoke(GridPosition);
            }

            return harvested;
        }

        /// <summary>
        /// Сбрасывает ресурс в исходное состояние (для reset эпизода).
        /// </summary>
        public void ResetForEpisode()
        {
            CurrentResources = MaxResources;
        }
    }
}
