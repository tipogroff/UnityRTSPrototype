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
    public enum BootstrapScenarioPreset
    {
        LegacyMvpSymmetric = 0,
        Day6Sanity24x24 = 1,
        /// <summary>
        /// Week 4 сценарий: 2 Worker + 2 Resource-патча на каждую сторону, без базы и боевых юнитов.
        /// Минимальный сетап для тестирования Worker-механик (сбор, возврат, постройка Казармы).
        /// </summary>
        Week4TwoWorkersSymmetric = 2,
        /// <summary>
        /// Week 6 visual/sanity preset: тот же процедурный путь (Base + 2 Worker + 2 Resource),
        /// но с более разнесённым стартом, чтобы снизить ранние искажения opening-поведения.
        /// </summary>
        Week6VisualSanitySpread24x24 = 3,
        /// <summary>
        /// Week 6 student visual inspection preset: microRTS-like 24x24 mirrored opening.
        /// P1: Resource A1/B1, Worker B2, Base C3.
        /// P2: Resource X24/W24, Worker W23, Base V22.
        /// </summary>
        Week6StudentMicroRtsMirror24x24 = 4,
    }

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

        [Header("Scenario preset")]
        [Tooltip("LegacyMvpSymmetric = исторический Week 1 старт. Day6Sanity24x24 = sanity-friendly opening для Day 6 rollout. Week4TwoWorkersSymmetric = 2 Worker + 2 ресурса на каждую сторону. Week6VisualSanitySpread24x24 = тот же состав, но с большей стартовой дистанцией.")]
        [SerializeField] private BootstrapScenarioPreset _scenarioPreset = BootstrapScenarioPreset.Week4TwoWorkersSymmetric;
        [Tooltip("Стартовые ресурсы для Day6Sanity24x24. Нужны, чтобы production был practically reachable в sanity-rollout.")]
        [Min(0)]
        [SerializeField] private int _day6SanityStartResources = 60;

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
            ResolveReferences();
            if (!ValidateConfig()) return;

            if (_gridManager == null || _matchManager == null) return;

            InitGrid();
            _unitFactory = new UnitFactory(_config, _gridManager, transform, _unitRegistry);
            SpawnStartingUnits();
            int scenarioStartResources = ResolveScenarioStartResources();
            _matchManager.BeginMatch(scenarioStartResources, _config.maxEpisodeSteps);

            Debug.Log($"[MatchBootstrap] Матч '{_config.scenarioName}' начат. " +
                      $"Карта {_config.mapWidth}×{_config.mapHeight}, " +
                      $"Preset={_scenarioPreset}, StartResources={scenarioStartResources}.");
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
                MatchBootstrap bootstrap = Instance;
                if (bootstrap != null && bootstrap != this)
                {
                    _config = bootstrap.GetConfig();
                }
            }

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
            if (_gridManager == null) _gridManager = GridManager.Instance ?? EnsureSceneComponent<GridManager>("GridManager");
            if (_matchManager == null) _matchManager = MatchManager.Instance ?? EnsureSceneComponent<MatchManager>("MatchManager");
            if (_unitRegistry == null) _unitRegistry = UnitRegistry.Instance ?? EnsureSceneComponent<UnitRegistry>("UnitRegistry");
            if (_resourceManager == null) _resourceManager = ResourceManager.Instance ?? EnsureSceneComponent<ResourceManager>("ResourceManager");

            EnsureSceneComponent<VictoryResolver>("VictoryResolver");

            if (_gridManager == null)
                Debug.LogError("[MatchBootstrap] GridManager не найден в сцене!");
            if (_matchManager == null)
                Debug.LogError("[MatchBootstrap] MatchManager не найден в сцене!");
            if (_unitRegistry == null)
                Debug.LogWarning("[MatchBootstrap] UnitRegistry не найден. Спавн продолжится без реестра.");
            if (_resourceManager == null)
                Debug.LogWarning("[MatchBootstrap] ResourceManager не найден. Ресурсные узлы не будут отслеживаться.");
        }

        private static T EnsureSceneComponent<T>(string gameObjectName) where T : Component
        {
            T existing = Object.FindFirstObjectByType<T>();
            if (existing != null)
            {
                return existing;
            }

            GameObject host = GameObject.Find(gameObjectName);
            if (host == null)
            {
                host = new GameObject(gameObjectName);
            }

            T component = host.GetComponent<T>();
            if (component == null)
            {
                component = host.AddComponent<T>();
            }

            return component;
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

            List<(UnitType type, GridPosition pos)> p1Spawns;
            List<(UnitType type, GridPosition pos)> p2Spawns;

            if (_scenarioPreset == BootstrapScenarioPreset.Week4TwoWorkersSymmetric)
            {
                // Week 4: база + 2 рабочих на каждую сторону.
                // Расстановка разнесена по Y чтобы юниты не мешали друг другу:
                //   Base  (2, H/2)       — левый край своей зоны
                //   Worker (5, H/2 - 2) и (5, H/2 + 2) — дальше по X, разнесены по Y
                //   Resources (8, H/2 - 2) и (8, H/2 + 2) — ещё дальше
                p1Spawns = new List<(UnitType type, GridPosition pos)>
                {
                    (UnitType.Base,   new GridPosition(2,     H / 2)),
                    (UnitType.Worker, new GridPosition(5,     H / 2 - 2)),
                    (UnitType.Worker, new GridPosition(5,     H / 2 + 2)),
                };

                p2Spawns = new List<(UnitType type, GridPosition pos)>
                {
                    (UnitType.Base,   new GridPosition(W - 3, H / 2)),
                    (UnitType.Worker, new GridPosition(W - 6, H / 2 - 2)),
                    (UnitType.Worker, new GridPosition(W - 6, H / 2 + 2)),
                };
            }
            else if (_scenarioPreset == BootstrapScenarioPreset.Week6VisualSanitySpread24x24)
            {
                // Week 6 visual/sanity: тот же процедурный состав, но стороны разнесены сильнее.
                // Это уменьшает ранние искажения opening (ранние блокировки/контакты),
                // сохраняя симметрию и весь существующий runtime bootstrap path.
                p1Spawns = new List<(UnitType type, GridPosition pos)>
                {
                    (UnitType.Base,   new GridPosition(2,     H / 2 - 4)),
                    (UnitType.Worker, new GridPosition(4,     H / 2 - 5)),
                    (UnitType.Worker, new GridPosition(4,     H / 2 - 3)),
                };

                p2Spawns = new List<(UnitType type, GridPosition pos)>
                {
                    (UnitType.Base,   new GridPosition(W - 3, H / 2 + 3)),
                    (UnitType.Worker, new GridPosition(W - 5, H / 2 + 2)),
                    (UnitType.Worker, new GridPosition(W - 5, H / 2 + 4)),
                };
            }
            else if (_scenarioPreset == BootstrapScenarioPreset.Day6Sanity24x24)
            {
                // Day 6 follow-up rationale:
                // - убираем мгновенный Light-vs-Light размен в центре;
                // - даём 2 workers на сторону для стабильного harvest/return цикла;
                // - сохраняем 24x24 observation contract и тот же runtime path.
                p1Spawns = new List<(UnitType type, GridPosition pos)>
                {
                    (UnitType.Base,   new GridPosition(3,  H / 2 - 1)),
                    (UnitType.Worker, new GridPosition(5,  H / 2 - 2)),
                    (UnitType.Worker, new GridPosition(5,  H / 2)),
                    (UnitType.Light,  new GridPosition(W / 2 - 3, H / 2 - 1)),
                };

                p2Spawns = new List<(UnitType type, GridPosition pos)>
                {
                    (UnitType.Base,   new GridPosition(W - 4, H / 2)),
                    (UnitType.Worker, new GridPosition(W - 6, H / 2 + 1)),
                    (UnitType.Worker, new GridPosition(W - 6, H / 2 - 1)),
                    (UnitType.Light,  new GridPosition(W / 2 + 2, H / 2)),
                };
            }
            else if (_scenarioPreset == BootstrapScenarioPreset.Week6StudentMicroRtsMirror24x24)
            {
                p1Spawns = new List<(UnitType type, GridPosition pos)>
                {
                    (UnitType.Worker, new GridPosition(1, 1)),
                    (UnitType.Base,   new GridPosition(2, 2)),
                };

                p2Spawns = new List<(UnitType type, GridPosition pos)>
                {
                    (UnitType.Worker, new GridPosition(W - 2, H - 2)),
                    (UnitType.Base,   new GridPosition(W - 3, H - 3)),
                };
            }
            else
            {
                p1Spawns = new List<(UnitType type, GridPosition pos)>
                {
                    (UnitType.Base,   new GridPosition(3,  H / 2 - 1)),
                    (UnitType.Worker, new GridPosition(5,  H / 2 - 1)),
                    (UnitType.Light,  new GridPosition(W / 2 - 1, H / 2 - 1)),
                };

                p2Spawns = new List<(UnitType type, GridPosition pos)>
                {
                    (UnitType.Base,   new GridPosition(W - 4, H / 2)),
                    (UnitType.Worker, new GridPosition(W - 6, H / 2)),
                    (UnitType.Light,  new GridPosition(W / 2, H / 2 - 1)),
                };
            }

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
            List<GridPosition> p1ResourcePositions;

            if (_scenarioPreset == BootstrapScenarioPreset.Week4TwoWorkersSymmetric)
            {
                // Ресурсы в одну строку с рабочими, на 3 клетки правее.
                p1ResourcePositions = new List<GridPosition>
                {
                    new GridPosition(8, H / 2 - 2),
                    new GridPosition(8, H / 2 + 2),
                };
            }
            else if (_scenarioPreset == BootstrapScenarioPreset.Week6VisualSanitySpread24x24)
            {
                // Ресурсы остаются ближе к своей стороне, чтобы opening был нейтральнее
                // и без раннего центр-конфликта при визуальной диагностике.
                p1ResourcePositions = new List<GridPosition>
                {
                    new GridPosition(7, H / 2 - 5),
                    new GridPosition(7, H / 2 - 3),
                };
            }
            else if (_scenarioPreset == BootstrapScenarioPreset.Day6Sanity24x24)
            {
                // Для sanity-сценария ресурсы чуть ближе к workers, чтобы ускорить
                // вход в economy progression и снизить долю "пустых" шагов.
                p1ResourcePositions = new List<GridPosition>
                {
                    new GridPosition(6, H / 2 - 2),
                    new GridPosition(6, H / 2),
                };
            }
            else if (_scenarioPreset == BootstrapScenarioPreset.Week6StudentMicroRtsMirror24x24)
            {
                p1ResourcePositions = new List<GridPosition>
                {
                    new GridPosition(0, 0),
                    new GridPosition(1, 0),
                };
            }
            else
            {
                p1ResourcePositions = new List<GridPosition>
                {
                    new GridPosition(6, H / 2 - 2),
                    new GridPosition(6, H / 2 + 2),
                };
            }

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

        private int ResolveScenarioStartResources()
        {
            if (_scenarioPreset == BootstrapScenarioPreset.Week4TwoWorkersSymmetric)
            {
                // Стартовые ресурсы — достаточно для первой постройки Казармы.
                return Mathf.Max(_day6SanityStartResources, 0);
            }

            if (_scenarioPreset == BootstrapScenarioPreset.Week6VisualSanitySpread24x24)
            {
                return Mathf.Max(_day6SanityStartResources, 0);
            }

            if (_scenarioPreset == BootstrapScenarioPreset.Day6Sanity24x24)
            {
                return Mathf.Max(_day6SanityStartResources, 0);
            }

            if (_scenarioPreset == BootstrapScenarioPreset.Week6StudentMicroRtsMirror24x24)
            {
                return Mathf.Max(_day6SanityStartResources, 0);
            }

            return _config.startResources;
        }
    }
}
