// MatchBootstrap.cs — стартовый компонент, собирающий матч из GameConfig.
// Неделя 2, Этап Match.
//
// Ответственность:
//   1. Прочитать GameConfig (единственный источник параметров сценария).
//   2. Инициализировать GridManager с размерами карты из конфига.
//   3. Создать стартовые юниты симметричного сценария MVP_24x24_Symmetric.
//   4. Передать управление MatchManager.BeginMatch().
//
// Все позиции спавна вычисляются программно через симметрию 180°
// (mirrorX = W-1-x, mirrorY = H-1-y), чтобы не хардкодить
// конкретные координаты — при смене GameConfig.mapWidth/Height
// расстановка масштабируется автоматически.

using System.Collections.Generic;
using UnityEngine;
using RTS.Core;

namespace RTS.Gameplay
{
    /// <summary>
    /// MonoBehaviour, прикреплённый к единственному GameObject "Bootstrap" в сцене.
    /// Запускается из Start(), до того как любой агент запрашивает наблюдения.
    /// </summary>
    public class MatchBootstrap : MonoBehaviour
    {
        // ── Inspector ─────────────────────────────────────────────────────────

        [Header("Конфигурация сценария")]
        [Tooltip("Эталонный ассет GameConfig. ОБЯЗАТЕЛЬНО.")]
        [SerializeField] private GameConfig _config;

        [Header("Зависимости сцены")]
        [Tooltip("GridManager в сцене. Если не задан — ищется через Instance.")]
        [SerializeField] private GridManager _gridManager;

        [Tooltip("MatchManager в сцене. Если не задан — ищется через Instance.")]
        [SerializeField] private MatchManager _matchManager;

        [Tooltip("UnitRegistry в сцене. Если не задан — ищется через Instance.")]
        [SerializeField] private UnitRegistry _unitRegistry;

        private UnitFactory _unitFactory;

        // ── Public API ────────────────────────────────────────────────────────

        /// <summary>
        /// Вызывается автоматически из Start().
        /// Может быть вызван повторно из EpisodeController.ResetEpisode(),
        /// если нужен полный рестарт сцены без перезагрузки.
        /// </summary>
        public void Setup()
        {
            if (!ValidateConfig()) return;

            ResolveReferences();
            if (_gridManager == null || _matchManager == null) return;

            InitGrid();
            _unitFactory = new UnitFactory(_config, _gridManager, transform, _unitRegistry);
            SpawnStartingUnits();
            _matchManager.BeginMatch(_config.startResources, _config.maxEpisodeSteps);

            Debug.Log($"[MatchBootstrap] Матч '{_config.scenarioName}' начат. " +
                      $"Карта {_config.mapWidth}×{_config.mapHeight}.");
        }

        // ── Unity lifecycle ───────────────────────────────────────────────────

        private void Start() => Setup();

        // ── Шаг 1: валидация ─────────────────────────────────────────────────

        private bool ValidateConfig()
        {
            if (_config == null)
            {
                Debug.LogError("[MatchBootstrap] GameConfig не назначен! " +
                               "Перетащите ассет GameConfig в поле _config.");
                return false;
            }
            if (_config.unitDefinitions == null || _config.unitDefinitions.Length < 7)
            {
                Debug.LogError("[MatchBootstrap] GameConfig.unitDefinitions должен " +
                               "содержать 7 элементов (по одному на каждый UnitType).");
                return false;
            }
            return true;
        }

        // ── Шаг 2: поиск зависимостей ────────────────────────────────────────

        private void ResolveReferences()
        {
            if (_gridManager == null) _gridManager = GridManager.Instance;
            if (_matchManager == null) _matchManager = MatchManager.Instance;
            if (_unitRegistry == null) _unitRegistry = UnitRegistry.Instance;

            if (_gridManager == null)
                Debug.LogError("[MatchBootstrap] GridManager не найден в сцене!");
            if (_matchManager == null)
                Debug.LogError("[MatchBootstrap] MatchManager не найден в сцене!");
            if (_unitRegistry == null)
                Debug.LogWarning("[MatchBootstrap] UnitRegistry не найден. Спавн продолжится без реестра.");
        }

        // ── Шаг 3: инициализация сетки ───────────────────────────────────────

        private void InitGrid()
        {
            _gridManager.InitGrid(_config.mapWidth, _config.mapHeight);
        }

        // ── Шаг 4: спавн юнитов ──────────────────────────────────────────────

        private void SpawnStartingUnits()
        {
            int W = _config.mapWidth;
            int H = _config.mapHeight;

            // ── Стартовая расстановка Player1 ─────────────────────────────────
            // База у левого нижнего угла, рабочие рядом.
            // Отступ 3 клетки от края — гарантирует место вокруг базы.
            var p1Spawns = new List<(UnitType type, GridPosition pos)>
            {
                (UnitType.Base,   new GridPosition(3,     H / 2)),
                (UnitType.Worker, new GridPosition(4,     H / 2)),
                (UnitType.Worker, new GridPosition(3,     H / 2 - 1)),
            };

            foreach (var (type, pos) in p1Spawns)
                _unitFactory.Spawn(type, Owner.Player1, pos);

            // ── Стартовая расстановка Player2 (180° симметрия) ────────────────
            // mirrorX = W-1-x, mirrorY = H-1-y
            foreach (var (type, pos) in p1Spawns)
            {
                var mirrorPos = new GridPosition(W - 1 - pos.X, H - 1 - pos.Y);
                _unitFactory.Spawn(type, Owner.Player2, mirrorPos);
            }

            // ── Ресурсные патчи (симметричные пары + опц. центральный) ────────
            SpawnResourcePatches(W, H);
        }

        /// <summary>
        /// Размещает ресурсные патчи симметрично относительно центра карты.
        /// Количество определено в GameConfig.startResources (число патчей на сторону).
        /// По умолчанию для MVP: 2 пары + 1 у левого нижнего края.
        /// </summary>
        private void SpawnResourcePatches(int W, int H)
        {
            // Позиции для Player1-половины (около базы и в центре)
            var p1ResourcePositions = new List<GridPosition>
            {
                new GridPosition(6,      H / 2),       // у базы P1
                new GridPosition(3,      H / 2 + 3),   // чуть выше базы P1
                new GridPosition(W / 2 - 1, H / 2),    // ближе к центру
            };

            foreach (var pos in p1ResourcePositions)
            {
                var mirrorPos = new GridPosition(W - 1 - pos.X, H - 1 - pos.Y);
                _unitFactory.Spawn(UnitType.Resource, Owner.Neutral, pos);
                _unitFactory.Spawn(UnitType.Resource, Owner.Neutral, mirrorPos);
            }
        }
    }
}
