// GameConstants.cs — глобальные константы проекта
// Технический контракт MVP. Неделя 1.

namespace RTS.Core
{
    /// <summary>
    /// Глобальные константы игровой логики.
    /// Изменение любого значения здесь автоматически затрагивает все модули.
    /// </summary>
    public static class GameConstants
    {
        // ── Сетка карты ──────────────────────────────────────────────────────
        public const int MapWidth  = 24;
        public const int MapHeight = 24;
        public const float CellSize = 1f;           // Unity-единицы на клетку

        // ── Временные параметры ──────────────────────────────────────────────
        public const int MaxEpisodeSteps  = 2000;   // шаги до принудительного сброса
        public const float DecisionPeriod = 0.1f;   // с, интервал принятия решений агентом

        // ── Ресурсы ──────────────────────────────────────────────────────────
        public const int InitialResources      = 5;
        public const int MaxResourcesPerPatch  = 20;
        public const int HarvestAmount         = 1;  // ресурсов за операцию харвеста
        public const int MaxCarryCapacity      = 5;  // максимум в руках рабочего

        // ── Здоровье (используется для нормализации наблюдений) ──────────────
        public const int MaxHitPoints = 10;

        // ── Теги (должны совпадать со значениями в Inspector) ────────────────
        public const string TeamPlayerTag = "Player";
        public const string TeamEnemyTag  = "Enemy";
        public const string ResourceTag   = "Resource";
    }
}
