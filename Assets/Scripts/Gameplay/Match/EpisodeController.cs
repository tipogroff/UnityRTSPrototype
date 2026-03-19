// EpisodeController.cs — управляет игровым циклом эпизода (тики, reset).
// Этап 3: Экономика + Этап 4: Боевая механика. Неделя 2.

using UnityEngine;
using RTS.Core;

namespace RTS.Gameplay
{
    /// <summary>
    /// MonoBehaviour, который управляет основным игровым циклом:
    /// — вызывает TickProduction() для всех зданий;
    /// — продвигает счётчик шагов в MatchManager;
    /// — проверяет условия завершения эпизода;
    /// — управляет ResetEpisode() для ML-Agents.
    /// </summary>
    public class EpisodeController : MonoBehaviour
    {
        // ── Singleton ─────────────────────────────────────────────────────────

        public static EpisodeController Instance { get; private set; }

        // ── State ──────────────────────────────────────────────────────────────

        private bool _isRunning = false;
        private CombatResolver _combatResolver;

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
            // Ждём инициализации MatchManager и MatchBootstrap
            _isRunning = true;
        }

        private void FixedUpdate()
        {
            if (!_isRunning) return;

            var matchMgr = MatchManager.Instance;
            if (matchMgr == null || matchMgr.Phase != MatchPhase.Running) return;

            // Главный игровой тик:
            TickProductions();
            TickCombatSystems(); // Боевая фаза тика
            
            // Продвигаем счётчик шагов
            matchMgr.AdvanceStep();

            // Проверяем условия завершения
            CheckEndConditions();
        }

        // ── Game ticks ────────────────────────────────────────────────────────

        /// <summary>
        /// Продвигает производство всех зданий на один тик.
        /// </summary>
        private void TickProductions()
        {
            var unitRegistry = UnitRegistry.Instance;
            if (unitRegistry == null) return;

            // Получаем все здания (базы, казармы и т.д.)
            var allUnits = unitRegistry.GetAllUnits();
            foreach (var unit in allUnits)
            {
                if (!unit.IsBuilding) continue;

                var buildingRuntime = unit.GetComponent<BuildingRuntime>();
                if (buildingRuntime != null)
                {
                    buildingRuntime.TickProduction();
                }
            }
        }

        /// <summary>
        /// Боевая система (Неделя 2):
        /// мгновенные атаки, 1 удар на юнит за тик.
        /// </summary>
        private void TickCombatSystems()
        {
            if (!EnsureCombatResolverReady()) return;
            _combatResolver.ResolveCombatTick();
        }

        private bool EnsureCombatResolverReady()
        {
            if (_combatResolver != null) return true;

            var bootstrap = MatchBootstrap.Instance;
            var config = bootstrap != null ? bootstrap.GetConfig() : null;
            var unitRegistry = UnitRegistry.Instance;
            var gridManager = GridManager.Instance;
            var matchManager = MatchManager.Instance;

            if (config == null || unitRegistry == null || gridManager == null || matchManager == null)
                return false;

            _combatResolver = new CombatResolver(config, unitRegistry, gridManager, matchManager);
            return true;
        }

        // ── End conditions ────────────────────────────────────────────────────

        /// <summary>
        /// Проверяет условия завершения эпизода.
        /// </summary>
        private void CheckEndConditions()
        {
            var matchMgr = MatchManager.Instance;
            if (matchMgr == null || matchMgr.Phase != MatchPhase.Running) return;

            // Условие 1: Один из противников потеряет все базы → ему проиграл
            var victoryResolver = VictoryResolver.Instance;
            if (victoryResolver != null)
            {
                victoryResolver.CheckVictoryConditions();
            }

            // Условие 2: Лимит шагов достигнут
            if (matchMgr.Step >= matchMgr.MaxSteps)
            {
                Debug.Log($"[EpisodeController] Достигнут лимит шагов ({matchMgr.MaxSteps}). Ничья.");
                matchMgr.DeclareWinner(Owner.Neutral); // Ничья
            }
        }

        // ── Episode reset ──────────────────────────────────────────────────────

        /// <summary>
        /// Сбросить эпизод (вызывается из ML-Agents или UI).
        /// </summary>
        public void ResetEpisode()
        {
            var matchMgr = MatchManager.Instance;
            var gridMgr = GridManager.Instance;
            var registry = UnitRegistry.Instance;
            var resourceMgr = ResourceManager.Instance;

            _combatResolver = null;

            // Очищаем все юниты со сцены
            if (registry != null)
            {
                var allUnits = registry.GetAllUnits();
                foreach (var unit in allUnits)
                {
                    Destroy(unit.gameObject);
                }
                registry.Clear();
            }

            // Сбрасываем состояние каждой системы
            if (gridMgr != null) gridMgr.InitGrid(gridMgr.Width, gridMgr.Height);
            if (matchMgr != null) matchMgr.ResetMatch();
            if (resourceMgr != null) resourceMgr.Clear();

            // Перезапускаем сцену через MatchBootstrap
            var bootstrap = MatchBootstrap.Instance;
            if (bootstrap != null)
            {
                bootstrap.Setup();
            }

            _isRunning = true;
        }

        // ── Public API ────────────────────────────────────────────────────────

        /// <summary>
        /// Паузировать/возобновить симуляцию.
        /// </summary>
        public void SetRunning(bool running)
        {
            _isRunning = running;
        }

        /// <summary>
        /// Проверить, работает ли эпизод.
        /// </summary>
        public bool IsRunning => _isRunning && MatchManager.Instance?.Phase == MatchPhase.Running;
    }
}
