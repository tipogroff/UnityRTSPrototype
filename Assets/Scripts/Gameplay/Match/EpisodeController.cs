// EpisodeController.cs — episode lifecycle and reset orchestration.

using System.Collections.Generic;
using UnityEngine;
using RTS.Core;
using RTS.Logging;
using RTS.ML;

namespace RTS.Gameplay
{
    public enum HeuristicExecutionPath
    {
        LegacyDirectDriver = 0,
        Day5PolicyPipeline = 1
    }

    [DisallowMultipleComponent]
    public class EpisodeController : MonoBehaviour
    {
        public static EpisodeController Instance { get; private set; }

        [Header("Scene references")]
        [SerializeField] private MatchManager _matchManager;
        [SerializeField] private MatchBootstrap _matchBootstrap;
        [SerializeField] private GridManager _gridManager;
        [SerializeField] private UnitRegistry _unitRegistry;
        [SerializeField] private ResourceManager _resourceManager;
        [SerializeField] private ExperimentLogger _experimentLogger;
        [SerializeField] private HeuristicDriver _heuristicDriver;
        [SerializeField] private HeuristicPolicyAdapter _heuristicPolicyAdapter;

        [Header("Runtime")]
        [SerializeField] private bool _autoStartOnPlay = true;
        [SerializeField] private bool _autoStepInFixedUpdate = true;
        [SerializeField] private bool _useHeuristicAI = true;
        [SerializeField] private HeuristicExecutionPath _heuristicExecutionPath = HeuristicExecutionPath.Day5PolicyPipeline;
        [SerializeField] private bool _logLifecycleEvents;

        [Header("Auto loop")]
        [Tooltip("Автоматически запускать следующий эпизод после завершения текущего.")]
        [SerializeField] private bool _autoRestartEpisodes = false;
        [Tooltip("Максимальное число эпизодов для авторестарта. 0 = бесконечно.")]
        [SerializeField] private int _maxEpisodes = 0;

        private bool _episodeRunning;
        private bool _episodeFinalized;

        public int EpisodeIndex { get; private set; }
        public bool IsRunning => _episodeRunning && _matchManager != null && _matchManager.Phase == MatchPhase.Running;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }

            Instance = this;
            ResolveReferences();
        }

        private void OnEnable()
        {
            ResolveReferences();
            SubscribeMatchEvents();
        }

        private void OnDisable()
        {
            UnsubscribeMatchEvents();
        }

        private void OnDestroy()
        {
            UnsubscribeMatchEvents();

            if (Instance == this)
            {
                Instance = null;
            }
        }

        private void Start()
        {
            if (_autoStartOnPlay)
            {
                StartNewEpisode();
            }
        }

        private void FixedUpdate()
        {
            if (!_autoStepInFixedUpdate || !_episodeRunning)
            {
                return;
            }

            if (_matchManager == null || _matchManager.Phase != MatchPhase.Running)
            {
                return;
            }

            StepMatchWithHeuristics();
        }

        public void StartNewEpisode()
        {
            ResolveReferences();

            if (_matchManager == null || _matchBootstrap == null)
            {
                Debug.LogError("[EpisodeController] MatchManager or MatchBootstrap is missing.");
                _episodeRunning = false;
                return;
            }

            CleanupRuntimeObjects();

            _matchBootstrap.Setup();

            _episodeRunning = _matchManager.Phase == MatchPhase.Running;
            _episodeFinalized = false;

            if (_episodeRunning)
            {
                EpisodeIndex++;
                _experimentLogger?.BeginEpisode();
                
                // Инициализируем HeuristicDriver
                if (_useHeuristicAI && _heuristicDriver != null)
                {
                    GameConfig config = _matchBootstrap != null ? _matchBootstrap.GetConfig() : null;
                    _heuristicDriver.Initialize(config, _gridManager, _unitRegistry, _resourceManager, _matchManager);
                    _heuristicDriver.ResetHeuristics();
                }

                if (_useHeuristicAI && _heuristicPolicyAdapter != null)
                {
                    _heuristicPolicyAdapter.Initialize(
                        _gridManager,
                        _unitRegistry,
                        _resourceManager,
                        _matchManager,
                        _matchBootstrap);
                    _heuristicPolicyAdapter.ResetHeuristicState();
                }
            }

            if (_logLifecycleEvents)
            {
                Debug.Log($"[EpisodeController] Episode {EpisodeIndex} started. Running={_episodeRunning}");
            }
        }

        public void ResetEpisode()
        {
            // Safety net: если ресет был вызван до получения OnMatchEnded,
            // всё равно закрываем текущий эпизод в логгере.
            if (_episodeRunning && !_episodeFinalized)
            {
                _episodeFinalized = true;
                _episodeRunning = false;
                _experimentLogger?.EndEpisode(false);
            }

            StartNewEpisode();
        }

        public bool StepEpisodeOnce()
        {
            ResolveReferences();

            if (_matchManager == null || _matchManager.Phase != MatchPhase.Running)
            {
                return false;
            }

            return StepMatchWithHeuristics();
        }

        /// <summary>
        /// Выполняет один шаг матча с применением эвристик.
        /// </summary>
        private bool StepMatchWithHeuristics()
        {
            // 1) Применяем эвристические решения для всех юнитов
            if (_useHeuristicAI)
            {
                switch (_heuristicExecutionPath)
                {
                    case HeuristicExecutionPath.Day5PolicyPipeline:
                        if (_heuristicPolicyAdapter != null)
                        {
                            _heuristicPolicyAdapter.ExecuteDecisionStep();
                        }
                        else if (_heuristicDriver != null)
                        {
                            // Fallback keeps Play Mode usable if adapter is not wired in scene yet.
                            _heuristicDriver.MakeAllDecisions();
                        }
                        break;

                    default:
                        if (_heuristicDriver != null)
                        {
                            _heuristicDriver.MakeAllDecisions();
                        }
                        break;
                }
            }

            // 2) Выполняем шаг матча
            if (_matchManager == null)
            {
                return false;
            }

            bool isRunningAfterStep = _matchManager.StepMatch();

            // 3) Пишем метрики шага в логгер (MVP: reward=0, метрики берём по Player1)
            if (_experimentLogger != null)
            {
                MatchStateSnapshot snapshot = _matchManager.GetMatchState();
                bool hasInvalidCommand = _matchManager.InvalidCommandsLastStep > 0;
                _experimentLogger.OnStep(
                    rewardDelta: 0f,
                    wasActionInvalid: hasInvalidCommand,
                    currentResourcesP1: snapshot.Player1Resources,
                    currentResourcesP2: snapshot.Player2Resources,
                    currentBuildsP1: snapshot.Player1BaseCount,
                    currentBuildsP2: snapshot.Player2BaseCount);
            }

            return isRunningAfterStep;
        }

        public bool ApplyCommand(MatchCommand command)
        {
            ResolveReferences();
            return _matchManager != null && _matchManager.ApplyCommand(command);
        }

        public int ApplyCommands(IReadOnlyList<MatchCommand> commands)
        {
            ResolveReferences();
            return _matchManager != null ? _matchManager.ApplyCommands(commands) : 0;
        }

        public MatchStateSnapshot GetMatchState()
        {
            ResolveReferences();
            return _matchManager != null ? _matchManager.GetMatchState() : default;
        }

        public void SetRunning(bool running)
        {
            _episodeRunning = running;
        }

        private void HandleMatchEnded(Owner winner)
        {
            _episodeRunning = false;

            if (_episodeFinalized)
            {
                return;
            }

            _episodeFinalized = true;
            bool player1Win = winner == Owner.Player1;
            _experimentLogger?.EndEpisode(player1Win);

            if (_logLifecycleEvents)
            {
                Debug.Log($"[EpisodeController] Episode {EpisodeIndex} ended. Winner={winner}");
            }

            if (_autoRestartEpisodes && (_maxEpisodes <= 0 || EpisodeIndex < _maxEpisodes))
            {
                StartCoroutine(StartNextEpisodeNextFrame());
            }
        }

        private System.Collections.IEnumerator StartNextEpisodeNextFrame()
        {
            yield return null;
            StartNewEpisode();
        }

        private void CleanupRuntimeObjects()
        {
            if (_unitRegistry != null)
            {
                List<UnitRuntime> units = _unitRegistry.GetAllUnits();
                for (int i = 0; i < units.Count; i++)
                {
                    UnitRuntime unit = units[i];
                    if (unit != null)
                    {
                        Destroy(unit.gameObject);
                    }
                }

                _unitRegistry.Clear();
            }

            if (_gridManager != null)
            {
                int width = _gridManager.Width > 0 ? _gridManager.Width : GameConstants.MapWidth;
                int height = _gridManager.Height > 0 ? _gridManager.Height : GameConstants.MapHeight;
                _gridManager.InitGrid(width, height);
            }

            _resourceManager?.Clear();
            _matchManager?.ResetMatch();
        }

        private void ResolveReferences()
        {
            if (_matchManager == null)
            {
                _matchManager = MatchManager.Instance;
            }

            if (_matchBootstrap == null)
            {
                _matchBootstrap = MatchBootstrap.Instance;
            }

            if (_gridManager == null)
            {
                _gridManager = GridManager.Instance;
            }

            if (_unitRegistry == null)
            {
                _unitRegistry = UnitRegistry.Instance;
            }

            if (_resourceManager == null)
            {
                _resourceManager = ResourceManager.Instance;
            }

            if (_experimentLogger == null)
            {
                _experimentLogger = FindFirstObjectByType<ExperimentLogger>();
                if (_experimentLogger == null)
                {
                    var loggerGo = new GameObject("ExperimentLogger");
                    _experimentLogger = loggerGo.AddComponent<ExperimentLogger>();
                    Debug.Log("[EpisodeController] ExperimentLogger создан автоматически.");
                }
            }

            if (_heuristicDriver == null)
            {
                _heuristicDriver = FindFirstObjectByType<HeuristicDriver>();
            }

            if (_heuristicPolicyAdapter == null)
            {
                _heuristicPolicyAdapter = FindFirstObjectByType<HeuristicPolicyAdapter>();
            }
        }

        private void SubscribeMatchEvents()
        {
            if (_matchManager == null)
            {
                return;
            }

            _matchManager.OnMatchEnded -= HandleMatchEnded;
            _matchManager.OnMatchEnded += HandleMatchEnded;
        }

        private void UnsubscribeMatchEvents()
        {
            if (_matchManager == null)
            {
                return;
            }

            _matchManager.OnMatchEnded -= HandleMatchEnded;
        }
    }
}
