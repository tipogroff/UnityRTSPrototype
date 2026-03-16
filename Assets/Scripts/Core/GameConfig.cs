// GameConfig.cs — главный ScriptableObject конфигурации матча (эталонный сценарий)
// Технический контракт MVP. Неделя 1.
// Создать экземпляр: Assets > Create > RTS > Game Config

using UnityEngine;

namespace RTS.Core
{
    /// <summary>
    /// Эталонный сценарий матча. Один ассет = один сравниваемый вариант.
    /// Фиксирует параметры карты, стартовые условия и ссылки на UnitDefinition.
    /// </summary>
    [CreateAssetMenu(fileName = "GameConfig", menuName = "RTS/Game Config")]
    public class GameConfig : ScriptableObject
    {
        // ── Описание сценария ─────────────────────────────────────────────────
        [Header("Описание сценария")]
        [Tooltip("Человекочитаемое имя — появляется в логах и заголовках CSV")]
        public string scenarioName = "MVP_24x24_Symmetric";
        [TextArea] public string scenarioNotes =
            "Эталонный сценарий для сравнения transfer vs from-scratch-lite.\n" +
            "24x24-карта, симметричный старт, по 2 рабочих и 1 базе у каждой стороны.";

        // ── Параметры карты ───────────────────────────────────────────────────
        [Header("Карта")]
        public int mapWidth  = GameConstants.MapWidth;
        public int mapHeight = GameConstants.MapHeight;
        [Tooltip("Начальные ресурсы каждого игрока")]
        public int startResources = GameConstants.InitialResources;

        // ── Лимит эпизода ─────────────────────────────────────────────────────
        [Header("Лимит эпизода")]
        public int maxEpisodeSteps = GameConstants.MaxEpisodeSteps;

        // ── Библиотека юнитов ─────────────────────────────────────────────────
        [Header("Библиотека юнитов")]
        [Tooltip("Все UnitDefinition, доступные в этом сценарии. " +
                 "Порядок должен совпадать с UnitType enum (индекс = int-значение enum).")]
        public UnitDefinition[] unitDefinitions = new UnitDefinition[7];

        // ── Утилиты ───────────────────────────────────────────────────────────
        /// <summary>
        /// Вернуть UnitDefinition по типу, null если не назначен.
        /// </summary>
        public UnitDefinition GetDefinition(UnitType type)
        {
            int idx = (int)type;
            if (idx < 0 || idx >= unitDefinitions.Length) return null;
            return unitDefinitions[idx];
        }

        void OnValidate()
        {
            if (unitDefinitions.Length != 7)
            {
                Debug.LogWarning(
                    $"[GameConfig] unitDefinitions.Length должен быть 7 " +
                    $"(по одному на каждый UnitType). Текущий: {unitDefinitions.Length}");
            }
        }
    }
}
