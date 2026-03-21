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
        // ── Singleton ─────────────────────────────────────────────────────────

        public static MatchBootstrap Instance { get; private set; }

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

        [Tooltip("ResourceManager в сцене. Если не задан — ищется через Instance.")]
        [SerializeField] private ResourceManager _resourceManager;

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

        /// <summary>
        /// Получить текущий GameConfig (для других компонентов).
        /// </summary>
        public GameConfig GetConfig() => _config;

        // ── Unity lifecycle ───────────────────────────────────────────────────

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
        }

        private void Start()
        {
            // EpisodeController управляет жизненным циклом и вызывает Setup() через StartNewEpisode().
            // Автозапуск только если EpisodeController отсутствует в сцене.
            if (EpisodeController.Instance == null)
                Setup();
        }

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
            if (_resourceManager == null) _resourceManager = ResourceManager.Instance;

            if (_gridManager == null)
                Debug.LogError("[MatchBootstrap] GridManager не найден в сцене!");
            if (_matchManager == null)
                Debug.LogError("[MatchBootstrap] MatchManager не найден в сцене!");
            if (_unitRegistry == null)
                Debug.LogWarning("[MatchBootstrap] UnitRegistry не найден. Спавн продолжится без реестра.");
            if (_resourceManager == null)
                Debug.LogWarning("[MatchBootstrap] ResourceManager не найден. Ресурсные узлы не будут отслеживаться.");
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
                (UnitType.Base,   new GridPosition(3,  H / 2 - 1)),
                (UnitType.Worker, new GridPosition(5,  H / 2 - 1)),
                (UnitType.Light,  new GridPosition(W / 2 - 1, H / 2 - 1)),
            };

            var p2Spawns = new List<(UnitType type, GridPosition pos)>
            {
                (UnitType.Base,   new GridPosition(W - 4, H / 2)),
                (UnitType.Worker, new GridPosition(W - 6, H / 2)),
                (UnitType.Light,  new GridPosition(W / 2, H / 2 - 1)),
            };

            foreach (var (type, pos) in p1Spawns)
                _unitFactory.Spawn(type, Owner.Player1, pos);

            foreach (var (type, pos) in p2Spawns)
                _unitFactory.Spawn(type, Owner.Player2, pos);

            // ── Ресурсные патчи (симметричные пары + опц. центральный) ────────
            SpawnResourcePatches(W, H);
        }

        /// <summary>
        /// Размещает ресурсные патчи симметрично относительно центра карты.
        /// Количество определено в GameConfig.startResources (число патчей на сторону).
        /// По умолчанию для MVP: 2 пары + 1 у левого нижнего края.
        /// Создаёт ResourceNode модели и регистрирует их в ResourceManager.
        /// </summary>
        private void SpawnResourcePatches(int W, int H)
        {
            // Позиции для Player1-половины (около базы и в центре)
            var p1ResourcePositions = new List<GridPosition>
            {
                new GridPosition(6, H / 2 - 2),
                new GridPosition(6, H / 2 + 2),
            };

            foreach (var pos in p1ResourcePositions)
            {
                var mirrorPos = new GridPosition(W - 1 - pos.X, H - 1 - pos.Y);

                // Спавним UnitRuntime для визуальной представления
                _unitFactory.Spawn(UnitType.Resource, Owner.Neutral, pos);
                _unitFactory.Spawn(UnitType.Resource, Owner.Neutral, mirrorPos);

                // Создаём модели ResourceNode и регистрируем в ResourceManager
                if (_resourceManager != null)
                {
                    var resourceNodeP1 = new ResourceNode(pos, GameConstants.MaxResourcesPerPatch);
                    var resourceNodeP2 = new ResourceNode(mirrorPos, GameConstants.MaxResourcesPerPatch);

                    _resourceManager.RegisterResourceNode(resourceNodeP1);
                    _resourceManager.RegisterResourceNode(resourceNodeP2);
                }
            }
        }
    }
}
