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

        [Header("Week 4 Day 2 Reward")]
        [SerializeField] private bool _enableRuntimeRewardCollector = true;
        [SerializeField] private Owner _rewardPerspective = Owner.Player1;
        [SerializeField] private bool _logRewardBreakdown;
        [SerializeField] private bool _enableSelfLossPenalty;
        [SerializeField] private bool _enableInvalidCommandPenalty;
        [SerializeField] private float _invalidPenaltyPerStepCap = 0.05f;

        [Header("Runtime")]
        [SerializeField] private bool _autoStartOnPlay = true;
        [SerializeField] private bool _autoStepInFixedUpdate = true;
        [SerializeField] private bool _useHeuristicAI = true;
        [SerializeField] private HeuristicExecutionPath _heuristicExecutionPath = HeuristicExecutionPath.Day5PolicyPipeline;
        [SerializeField] private bool _logLifecycleEvents;
        [SerializeField] private bool _logTerminalDiagnostics = true;

        [Header("Auto loop")]
        [Tooltip("Автоматически запускать следующий эпизод после завершения текущего.")]
        [SerializeField] private bool _autoRestartEpisodes = false;
        [Tooltip("Максимальное число эпизодов для авторестарта. 0 = бесконечно.")]
        [SerializeField] private int _maxEpisodes = 0;

        private bool _episodeRunning;
        private bool _episodeFinalized;
        private RuntimeRewardCollector _runtimeRewardCollector;

        public RewardStepTrace LastRewardStepTrace { get; private set; }
        public RewardBreakdown LastRewardBreakdown { get; private set; }
        public EpisodeEndReport LastTerminalReport { get; private set; }

        public int EpisodeIndex { get; private set; }
        public bool IsRunning => _episodeRunning && _matchManager != null && _matchManager.Phase == MatchPhase.Running;
        public RewardEpisodeSummary CurrentRewardEpisodeSummary =>
            _runtimeRewardCollector != null ? _runtimeRewardCollector.CurrentEpisodeSummary : default;

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
                _runtimeRewardCollector?.ResetEpisode();
                LastRewardStepTrace = default;
                LastRewardBreakdown = default;
                LastTerminalReport = default;
                
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
            if (_episodeRunning && !_episodeFinalized)
            {
                MatchStateSnapshot snapshot = _matchManager != null ? _matchManager.GetMatchState() : default;
                TerminalEvaluationResult terminalEvaluation = snapshot.Phase == MatchPhase.Ended
                    ? EpisodeTerminalEvaluator.Evaluate(snapshot, _rewardPerspective)
                    : EpisodeTerminalEvaluator.CreateGuardedStop("Episode reset was requested while runtime match was still running.");

                FinalizeEpisodeWithTerminalReport(terminalEvaluation, snapshot.Step);

                if (snapshot.Phase != MatchPhase.Ended)
                {
                    Debug.LogWarning("[EpisodeController][Terminal] Guarded stop: episode reset before runtime terminal transition.");
                }
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
            RewardRuntimeSnapshot preSnapshot = null;
            if (_enableRuntimeRewardCollector && _runtimeRewardCollector != null)
            {
                preSnapshot = _runtimeRewardCollector.CaptureSnapshot(_matchManager, _unitRegistry);
            }

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

            float rewardDelta = 0f;
            if (_enableRuntimeRewardCollector && _runtimeRewardCollector != null && preSnapshot != null)
            {
                RewardRuntimeSnapshot postSnapshot = _runtimeRewardCollector.CaptureSnapshot(_matchManager, _unitRegistry);
                LastRewardStepTrace = _runtimeRewardCollector.EvaluateStep(preSnapshot, postSnapshot, _rewardPerspective);
                LastRewardBreakdown = LastRewardStepTrace.Breakdown;
                rewardDelta = LastRewardBreakdown.Total;

                if (_logRewardBreakdown)
                {
                    Debug.Log(
                        $"[EpisodeController][Reward] Step={LastRewardStepTrace.Step}, Total={LastRewardBreakdown.Total:F4}, " +
                        $"Economy={LastRewardBreakdown.Economy:F4}, Combat={LastRewardBreakdown.Combat:F4}, " +
                        $"Terminal={LastRewardBreakdown.Terminal:F4}, Shaping={LastRewardBreakdown.Shaping:F4}, " +
                        $"Events={LastRewardBreakdown.EventCount}, TerminalStep={LastRewardBreakdown.IsTerminalStep}, " +
                        $"TerminalReason={LastRewardBreakdown.TerminalReason}");
                }
            }
            else
            {
                LastRewardStepTrace = default;
                LastRewardBreakdown = default;
            }

            // 3) Пишем метрики шага в логгер.
            if (_experimentLogger != null)
            {
                MatchStateSnapshot snapshot = _matchManager.GetMatchState();
                bool hasInvalidCommand = _matchManager.InvalidCommandsLastStep > 0;
                _experimentLogger.OnStep(
                    rewardDelta: rewardDelta,
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
            if (_episodeFinalized)
            {
                return;
            }

            MatchStateSnapshot snapshot = _matchManager != null ? _matchManager.GetMatchState() : default;
            TerminalEvaluationResult terminalEvaluation = EpisodeTerminalEvaluator.Evaluate(snapshot, _rewardPerspective);
            FinalizeEpisodeWithTerminalReport(terminalEvaluation, snapshot.Step);

            if (_autoRestartEpisodes && (_maxEpisodes <= 0 || EpisodeIndex < _maxEpisodes))
            {
                StartCoroutine(StartNextEpisodeNextFrame());
            }
        }

        private void FinalizeEpisodeWithTerminalReport(TerminalEvaluationResult terminalEvaluation, int episodeStep)
        {
            if (_episodeFinalized)
            {
                return;
            }

            _episodeRunning = false;
            _episodeFinalized = true;

            RewardEpisodeSummary summary = _runtimeRewardCollector != null
                ? _runtimeRewardCollector.CurrentEpisodeSummary
                : default;

            // TerminalEventProcessed: evaluator recognised and ran the terminal path.
            // True even when terminal reward magnitude is zero (e.g. neutral Draw/Timeout defaults).
            bool terminalEventProcessed = terminalEvaluation.IsTerminal && terminalEvaluation.TerminalReason != TerminalReason.None;
            // TerminalRewardNonZero: something was actually accumulated in the terminal reward bucket.
            bool terminalRewardNonZero = !Mathf.Approximately(summary.Breakdown.Terminal, 0f);

            LastTerminalReport = new EpisodeEndReport(
                terminalEvaluation.IsTerminal,
                terminalEvaluation.TerminalReason,
                terminalEvaluation.Winner,
                terminalEvaluation.RuntimeEndReason,
                terminalEvaluation.RuntimeWasTerminal,
                terminalEventProcessed,
                terminalRewardNonZero,
                episodeStep,
                summary.Breakdown,
                terminalEvaluation.DiagnosticDescription);

            if (summary.TerminalReached
                && summary.TerminalReason != TerminalReason.None
                && summary.TerminalReason != terminalEvaluation.TerminalReason)
            {
                // Mismatch between the reward layer and the controller evaluator.
                // Both read from the same EpisodeTerminalEvaluator, so this should not occur under normal
                // operation. It may indicate a guarded reset, a mid-episode evaluation order issue, or a
                // future divergence introduced by a refactor. This is a diagnostic warning, not a hard stop.
                Debug.LogWarning(
                    $"[EpisodeController][Terminal][Mismatch] TerminalReason divergence detected. " +
                    $"RewardLayer={summary.TerminalReason}, Controller={terminalEvaluation.TerminalReason}, " +
                    $"RuntimeEndReason={terminalEvaluation.RuntimeEndReason}, Winner={terminalEvaluation.Winner}, " +
                    $"Step={episodeStep}, TerminalRewardBucket={summary.Breakdown.Terminal:F4}, " +
                    $"RuntimeWasTerminal={terminalEvaluation.RuntimeWasTerminal}, " +
                    $"Diagnostic={terminalEvaluation.DiagnosticDescription}");
            }

            _experimentLogger?.EndEpisode(terminalEvaluation.Winner == Owner.Player1);

            if (_logLifecycleEvents || _logTerminalDiagnostics)
            {
                Debug.Log(
                    $"[EpisodeController][Terminal] Episode={EpisodeIndex}, Step={LastTerminalReport.EpisodeStep}, " +
                    $"Reason={LastTerminalReport.TerminalReason}, RuntimeReason={LastTerminalReport.RuntimeEndReason}, " +
                    $"Winner={LastTerminalReport.Winner}, RuntimeTerminal={LastTerminalReport.RuntimeWasTerminal}, " +
                    $"TerminalEventProcessed={LastTerminalReport.TerminalEventProcessed}, TerminalRewardNonZero={LastTerminalReport.TerminalRewardNonZero}, " +
                    $"RewardSummary(Total={LastTerminalReport.RewardBreakdown.Total:F4}, Economy={LastTerminalReport.RewardBreakdown.Economy:F4}, " +
                    $"Combat={LastTerminalReport.RewardBreakdown.Combat:F4}, Terminal={LastTerminalReport.RewardBreakdown.Terminal:F4}, " +
                    $"Shaping={LastTerminalReport.RewardBreakdown.Shaping:F4}, Events={LastTerminalReport.RewardBreakdown.EventCount}), " +
                    $"Details={LastTerminalReport.DiagnosticDescription}");
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
            EnsureCoreRuntimeObjects();

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
                if (_heuristicDriver == null && _useHeuristicAI)
                {
                    _heuristicDriver = EnsureSceneComponent<HeuristicDriver>("HeuristicDriver");
                    Debug.Log("[EpisodeController] HeuristicDriver created automatically.");
                }
            }

            if (_heuristicPolicyAdapter == null)
            {
                _heuristicPolicyAdapter = FindFirstObjectByType<HeuristicPolicyAdapter>();
                if (_heuristicPolicyAdapter == null && _useHeuristicAI && _heuristicExecutionPath == HeuristicExecutionPath.Day5PolicyPipeline)
                {
                    _heuristicPolicyAdapter = EnsureSceneComponent<HeuristicPolicyAdapter>("HeuristicPolicyAdapter");
                    Debug.Log("[EpisodeController] HeuristicPolicyAdapter created automatically.");
                }
            }

            if (_runtimeRewardCollector == null)
            {
                var config = RewardConfig.CreateV1Defaults();
                var options = RewardCollectorOptions.CreateDefaults();
                options.EnableSelfLossPenalty = _enableSelfLossPenalty;
                options.EnableInvalidCommandPenalty = _enableInvalidCommandPenalty;
                options.InvalidPenaltyPerStepCap = Mathf.Max(0f, _invalidPenaltyPerStepCap);
                _runtimeRewardCollector = new RuntimeRewardCollector(config, options);
            }
        }

        private void EnsureCoreRuntimeObjects()
        {
            _gridManager ??= EnsureSceneComponent<GridManager>("GridManager");
            _unitRegistry ??= EnsureSceneComponent<UnitRegistry>("UnitRegistry");
            _resourceManager ??= EnsureSceneComponent<ResourceManager>("ResourceManager");
            _matchBootstrap ??= EnsureSceneComponent<MatchBootstrap>("MatchBootstrap");
            _matchManager ??= EnsureSceneComponent<MatchManager>("MatchManager");

            // VictoryResolver is consumed transitively by MatchManager.ResolveReferences().
            EnsureSceneComponent<VictoryResolver>("VictoryResolver");
        }

        private static T EnsureSceneComponent<T>(string gameObjectName) where T : Component
        {
            T existing = FindFirstObjectByType<T>();
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
