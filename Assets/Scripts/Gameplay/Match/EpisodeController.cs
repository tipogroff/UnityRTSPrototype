// EpisodeController.cs — episode lifecycle and reset orchestration.
//
// Week 4 Day 4: StepMatchWithHeuristics now delegates to RlLoopCoordinator,
// which enforces a canonical 9-phase RL loop order:
//   Phase 1: PreStepCapture → Phase 2: Observation → Phase 3: Mask
//   Phase 4: ActionSubmit   → Phase 5: RuntimeStep  → Phase 6: PostStepCapture
//   Phase 7: RewardEval     → Phase 8: TerminalEval → Phase 9: StepReport

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
        [SerializeField] private Week6StudentPolicyAdapter _week6StudentPolicyAdapter;

        [Header("Week 4 Day 2 Reward")]
        [Tooltip("Gates reward breakdown log output. Reward computation is always-on in the Day 4 canonical loop — this flag no longer enables/disables computation.")]
        [SerializeField] private bool _rewardLoggingEnabled = true;
        [SerializeField] private Owner _rewardPerspective = Owner.Player1;
        [SerializeField] private bool _logRewardBreakdown;
        [SerializeField] private bool _enableSelfLossPenalty;
        [SerializeField] private bool _enableInvalidCommandPenalty;
        [SerializeField] private float _invalidPenaltyPerStepCap = 0.05f;

        [Header("Week 4 Day 4 RL Loop")]
        [Tooltip("Log the per-step RlLoopStepReport diagnostic line to the console.")]
        [SerializeField] private bool _logRlLoopDiagnostics = false;

        [Header("Runtime")]
        [SerializeField] private bool _autoStartOnPlay = true;
        [SerializeField] private bool _autoStepInFixedUpdate = true;
        [SerializeField] private bool _useHeuristicAI = true;
        [SerializeField] private HeuristicExecutionPath _heuristicExecutionPath = HeuristicExecutionPath.Day5PolicyPipeline;
        [SerializeField] private bool _logLifecycleEvents;
        [SerializeField] private bool _logTerminalDiagnostics = true;

        [Header("Week 6 Day 5 Student Match Control")]
        [SerializeField] private bool _enableWeek6StudentMatchControl;
        [SerializeField] private Week6PlayerControlMode _player1DecisionMode = Week6PlayerControlMode.StudentInference;
        [SerializeField] private Week6PlayerControlMode _player2DecisionMode = Week6PlayerControlMode.HeuristicBaseline;

        [Header("Auto loop")]
        [Tooltip("Автоматически запускать следующий эпизод после завершения текущего.")]
        [SerializeField] private bool _autoRestartEpisodes = false;
        [Tooltip("Максимальное число эпизодов для авторестарта. 0 = бесконечно.")]
        [SerializeField] private int _maxEpisodes = 0;

        private bool _episodeRunning;
        private bool _episodeFinalized;
        private RuntimeRewardCollector _runtimeRewardCollector;
        private MlPolicyPipelineFacade _policyPipelineFacade;
        private RlLoopCoordinator _rlLoopCoordinator;

        public RewardStepTrace LastRewardStepTrace { get; private set; }
        public RewardBreakdown LastRewardBreakdown { get; private set; }
        public EpisodeEndReport LastTerminalReport { get; private set; }

        /// <summary>Per-step RL loop report from the last RlLoopCoordinator.ExecuteFullStep call.</summary>
        public RlLoopStepReport LastRlLoopStepReport { get; private set; }

        public int EpisodeIndex { get; private set; }
        public bool IsRunning => _episodeRunning && _matchManager != null && _matchManager.Phase == MatchPhase.Running;
        public bool AutoStepInFixedUpdate
        {
            get => _autoStepInFixedUpdate;
            set => _autoStepInFixedUpdate = value;
        }
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
                if (!ValidateWeek6ControlConfiguration(out string week6ConfigError))
                {
                    Debug.LogError("[EpisodeController] Week6 control configuration is invalid: " + week6ConfigError);
                    _episodeRunning = false;
                    return;
                }

                EpisodeIndex++;
                _experimentLogger?.BeginEpisode();
                _runtimeRewardCollector?.ResetEpisode();
                LastRewardStepTrace = default;
                LastRewardBreakdown = default;
                LastTerminalReport = default;

                // Reset RL loop coordinator for the new episode.
                _rlLoopCoordinator?.ResetLoop();
                LastRlLoopStepReport = default;

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

                if (_enableWeek6StudentMatchControl && _week6StudentPolicyAdapter != null)
                {
                    _week6StudentPolicyAdapter.Initialize(
                        _gridManager,
                        _unitRegistry,
                        _resourceManager,
                        _matchManager,
                        _matchBootstrap);
                    _week6StudentPolicyAdapter.ResetEpisodeState();
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
        /// Executes one match step via the canonical RL loop (Week 4 Day 4).
        ///
        /// Delegates to RlLoopCoordinator.ExecuteFullStep(), which enforces:
        ///   Phase 1: PreStepCapture  → Phase 2: Observation  → Phase 3: Mask
        ///   Phase 4: ActionSubmit    → Phase 5: RuntimeStep   → Phase 6: PostStepCapture
        ///   Phase 7: RewardEval      → Phase 8: TerminalEval  → Phase 9: StepReport
        ///
        /// Guarantees:
        ///   - obs and mask built before StepMatch on the same pre-step state;
        ///   - reward and terminal read only after StepMatch;
        ///   - double-step guard blocks any second StepMatch in one cycle;
        ///   - baseline path and future RL path share identical phase logic.
        /// </summary>
        private bool StepMatchWithHeuristics()
        {
            if (_matchManager == null)
            {
                return false;
            }

            if (!ValidateWeek6ControlConfiguration(out string week6ConfigError))
            {
                Debug.LogError("[EpisodeController] Week6 control configuration is invalid during step: " + week6ConfigError);
                _episodeRunning = false;
                return false;
            }

            // Select action source based on current heuristic settings.
            // All sources satisfy IDecisionSource contract (no StepMatch calls).
            IDecisionSource decisionSource = BuildDecisionSource();

            // Delegate to the canonical RL loop coordinator.
            RlLoopStepReport report = _rlLoopCoordinator.ExecuteFullStep(_rewardPerspective, decisionSource);

            // ── Propagate results to EpisodeController public surface ─────────────
            LastRlLoopStepReport = report;

            // Reward traces forwarded unconditionally: coordinator always computes them.
            // _enableRuntimeRewardCollector controls only the breakdown log, not computation.
            LastRewardStepTrace = report.RewardTrace;
            LastRewardBreakdown = report.RewardTrace.Breakdown;
            float rewardDelta = report.RewardTotal;

            if (_rewardLoggingEnabled && _logRewardBreakdown)
            {
                RewardBreakdown bd = report.RewardTrace.Breakdown;
                Debug.Log(
                    $"[EpisodeController][Reward] Step={report.RewardTrace.Step}, Total={bd.Total:F4}, " +
                    $"Economy={bd.Economy:F4}, Combat={bd.Combat:F4}, " +
                    $"Terminal={bd.Terminal:F4}, Shaping={bd.Shaping:F4}, " +
                    $"Events={bd.EventCount}, TerminalStep={bd.IsTerminalStep}, " +
                    $"TerminalReason={bd.TerminalReason}");
            }

            if (_logRlLoopDiagnostics)
            {
                Debug.Log(report.BuildDiagnosticLine());
            }

            // ── Experiment logger (step metrics) ──────────────────────────────────
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

            // Match is still running when the coordinator found no terminal state post-step.
            return !report.IsTerminal;
        }

        /// <summary>
        /// Builds the IDecisionSource for the current step.
        ///
        /// All returned sources satisfy the IDecisionSource phase contract:
        /// they submit actions through the production path and never call StepMatch.
        /// </summary>
        private IDecisionSource BuildDecisionSource()
        {
            if (_enableWeek6StudentMatchControl)
            {
                return new Week6ConfiguredDecisionSource(
                    _heuristicPolicyAdapter,
                    _week6StudentPolicyAdapter,
                    _player1DecisionMode,
                    _player2DecisionMode);
            }

            if (!_useHeuristicAI)
            {
                return IdleDecisionSource.Instance;
            }

            switch (_heuristicExecutionPath)
            {
                case HeuristicExecutionPath.Day5PolicyPipeline:
                    if (_heuristicPolicyAdapter != null)
                    {
                        return new BaselineDecisionSource(_heuristicPolicyAdapter);
                    }
                    // Fallback: adapter not wired, use legacy driver to keep Play Mode usable.
                    return _heuristicDriver != null
                        ? (IDecisionSource)new LegacyDecisionSource(_heuristicDriver)
                        : IdleDecisionSource.Instance;

                default:
                    return _heuristicDriver != null
                        ? (IDecisionSource)new LegacyDecisionSource(_heuristicDriver)
                        : IdleDecisionSource.Instance;
            }
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

        public void ConfigureWeek6PlayerControlModes(
            bool enableStudentMatchControl,
            Week6PlayerControlMode player1Mode,
            Week6PlayerControlMode player2Mode)
        {
            _enableWeek6StudentMatchControl = enableStudentMatchControl;
            _player1DecisionMode = player1Mode;
            _player2DecisionMode = player2Mode;

            if (!ValidateWeek6ControlConfiguration(out string week6ConfigError))
            {
                Debug.LogError("[EpisodeController] Rejected invalid Week6 control mode switch: " + week6ConfigError);
            }
        }

        private bool ValidateWeek6ControlConfiguration(out string error)
        {
            error = string.Empty;

            if (!_enableWeek6StudentMatchControl)
            {
                return true;
            }

            if (!IsValidWeek6Mode(_player1DecisionMode) || !IsValidWeek6Mode(_player2DecisionMode))
            {
                error = $"Unsupported control mode pair: p1={_player1DecisionMode}, p2={_player2DecisionMode}";
                return false;
            }

            if (_player1DecisionMode == Week6PlayerControlMode.StudentInference
                && _player2DecisionMode == Week6PlayerControlMode.StudentInference)
            {
                error = "Safe Day5 sanity mode requires exactly one student-controlled side.";
                return false;
            }

            if (_player1DecisionMode == Week6PlayerControlMode.HeuristicBaseline
                && _player2DecisionMode == Week6PlayerControlMode.HeuristicBaseline)
            {
                error = "Week6 student match control is enabled, but both sides are still heuristic baseline.";
                return false;
            }

            if ((_player1DecisionMode == Week6PlayerControlMode.StudentInference
                 || _player2DecisionMode == Week6PlayerControlMode.StudentInference)
                && _week6StudentPolicyAdapter == null)
            {
                error = "StudentInference mode is selected, but Week6StudentPolicyAdapter is missing.";
                return false;
            }

            if ((_player1DecisionMode == Week6PlayerControlMode.HeuristicBaseline
                 || _player2DecisionMode == Week6PlayerControlMode.HeuristicBaseline)
                && _heuristicPolicyAdapter == null)
            {
                error = "HeuristicBaseline mode is selected, but HeuristicPolicyAdapter is missing.";
                return false;
            }

            return true;
        }

        private static bool IsValidWeek6Mode(Week6PlayerControlMode mode)
        {
            return mode == Week6PlayerControlMode.Idle
                || mode == Week6PlayerControlMode.HeuristicBaseline
                || mode == Week6PlayerControlMode.StudentInference;
        }

        public bool TryGetWeek6StudentExecutionReport(Owner playerId, out StudentPolicyExecutionReport report)
        {
            ResolveReferences();
            if (_week6StudentPolicyAdapter != null)
            {
                return _week6StudentPolicyAdapter.TryGetLastExecutionReport(playerId, out report);
            }

            report = default;
            return false;
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
                        if (unit.GetComponent<StaticSceneEntityAuthoring>() != null)
                        {
                            continue;
                        }

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

            if (_week6StudentPolicyAdapter == null)
            {
                _week6StudentPolicyAdapter = FindFirstObjectByType<Week6StudentPolicyAdapter>();
                if (_week6StudentPolicyAdapter == null && _enableWeek6StudentMatchControl)
                {
                    _week6StudentPolicyAdapter = EnsureSceneComponent<Week6StudentPolicyAdapter>("Week6StudentPolicyAdapter");
                    Debug.Log("[EpisodeController] Week6StudentPolicyAdapter created automatically.");
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

            // Build MlPolicyPipelineFacade for RlLoopCoordinator (obs/mask phases).
            // This facade is separate from the one inside HeuristicPolicyAdapter:
            // both are stateless wrappers over the same scene objects and produce
            // equivalent obs/mask from the same pre-step state.
            if (_policyPipelineFacade == null && _gridManager != null && _unitRegistry != null && _matchManager != null)
            {
                _policyPipelineFacade = new MlPolicyPipelineFacade(
                    _gridManager,
                    _unitRegistry,
                    _resourceManager,
                    _matchManager,
                    _matchBootstrap);
            }

            // Build RlLoopCoordinator once all dependencies are available.
            if (_rlLoopCoordinator == null && _policyPipelineFacade != null && _runtimeRewardCollector != null && _matchManager != null)
            {
                _rlLoopCoordinator = new RlLoopCoordinator(
                    _policyPipelineFacade,
                    _runtimeRewardCollector,
                    _matchManager,
                    _unitRegistry);
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
