using RTS.Core;
using RTS.Gameplay;
using RTS.ML;
using RTS.MLAgents.Stage7B.CandidateActions;
using RTS.MLAgents.Stage7B.Diagnostics;
using RTS.MLAgents.Stage7B.TeacherReplay;
using RTS.Presentation;
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Stopwatch = System.Diagnostics.Stopwatch;
using Unity.MLAgents;
using Unity.MLAgents.Actuators;
using Unity.MLAgents.Policies;
using Unity.MLAgents.Sensors;
using UnityEngine;

namespace RTS.MLAgents.Stage7B
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(BehaviorParameters))]
    [RequireComponent(typeof(DecisionRequester))]
    public sealed class StudentMlAgent : Agent
    {
        private const string DecisionSourceDecisionRequester = "decision_requester";
        private const string DecisionSourceManualFixedUpdate = "manual_fixed_update";
        private const string DecisionSourceDecisionRequesterAndManualDebug = "decision_requester+manual_fixed_update_debug";
        private const string DecisionSourceDecisionRequesterWatchdogManualFallback = "decision_requester_watchdog_manual_fallback";
        private const string DecisionSourceNone = "none";
        private const int DecisionRequesterWatchdogFixedUpdateThreshold = 8;

        [Header("Stage7B")]
        [SerializeField] private Owner _playerPerspective = Owner.Player1;
        [SerializeField] private bool _autoResolveBootstrap = true;
        [SerializeField] private bool _manualFixedUpdateDecisionRequests;
        [SerializeField] private bool _allowConcurrentDecisionSourcesForDebug;
        [SerializeField] private bool _enableDecisionRequesterWatchdogFallback = true;
        [SerializeField] private string _actualCollectTraceRelativePath = "python/stage7b_teacher_replay/stage7b_8c2_actual_collect_observations_trace.jsonl";
        [SerializeField] private string _actionTraceRelativePath = "python/stage7b_teacher_replay/stage7b_8d1_action_trace.jsonl";
        [SerializeField] private string _runtimeApplyTraceRelativePath = "python/stage7b_teacher_replay/stage7b_8d1_runtime_apply_trace.jsonl";
        [SerializeField] private string _decisionSchedulerTraceRelativePath = "python/stage7b_teacher_replay/stage7b_8d1_decision_scheduler_trace.jsonl";
        [SerializeField] private int _stage7BMaxDecisionsPerEpisode = 256;
        [SerializeField] private bool _logRejectedActions;

        private MlAgentsTrainingBootstrap _bootstrap;
        private ObservationBuilder _observationBuilder;
        private MlAgentsCandidateActionBuilder _candidateBuilder;
        private readonly MlAgentsMaskAdapter _maskAdapter = new MlAgentsMaskAdapter();
        private readonly MlAgentsActionAdapter _actionAdapter = new MlAgentsActionAdapter();
        private MlAgentsCandidateActionList _currentCandidates;
        private ActionApplier _actionApplier;
        private RuntimeRewardCollector _rewardCollector;
        private int _episodeDecisionCount;
        private string _currentDecisionSource = DecisionSourceDecisionRequester;
        private bool _loggedDecisionSourceGuard;
        private bool _decisionRequesterWatchdogFallbackActive;
        private int _fixedUpdatesWithoutDecisionWhileUsingDecisionRequester;
        private static bool _applicationIsQuitting;
        private int _onEnableCount;
        private int _initializeCount;
        private int _onEpisodeBeginCount;
        private int _heuristicCallCount;
        private int _manualRequestDecisionCount;
        private int _manualRequestActionCount;
        private int _lastObservationLength;
        private int _lastObservationNanCount;
        private int _lastActionCandidateIndex = -1;
        private bool _lastActionAccepted;
        private int _terminalCount;
        private int _firstCollectObservationsFrame = -1;
        private int _firstWriteMaskFrame = -1;
        private int _firstOnActionReceivedFrame = -1;
        private float _firstCollectObservationsTime = -1f;
        private float _firstWriteMaskTime = -1f;
        private float _firstOnActionReceivedTime = -1f;
        private double _firstResetDurationMs = -1d;
        private double _firstObservationDurationMs = -1d;
        private double _firstWriteMaskDurationMs = -1d;
        private double _firstOnActionReceivedDurationMs = -1d;
        private int _awakeCount;
        private int _startCount;
        private int _endEpisodeCount;
        private bool _onEpisodeBeginStartNewEpisodeCalled;
        private bool _onEpisodeBeginStartNewEpisodeResult;
        private bool _onEpisodeBeginUsedTrainerControlledEpisodeResetPath;
        private string _onEpisodeBeginStartNewEpisodePath = "none";
        private bool _pendingTrainerControlledKickDecision;
        private int _trainerControlledKickDecisionRequestCount;
        private int _candidateBuildCallCount;
        private int _candidateBuilderSuccessCount;
        private int _actionAdapterResolveCount;
        private int _actionAdapterSuccessCount;
        private bool _lastCandidateIndexInRange;
        private int _runtimeApplyAttemptedCount;
        private int _runtimeApplyAcceptedCount;
        private int _runtimeApplyRejectedCount;
        private int _requestDecisionCount;
        private int _inferenceContinuousRequestDecisionCount;
        private float _lastPauseGateLogRealtime = -100f;
        private int _observationBuilderUsedCount;
        private int _observationFallbackCount;
        private int _selectedNoOpActionCount;
        private int _selectedMoveActionCount;
        private int _selectedHarvestActionCount;
        private int _selectedReturnActionCount;
        private int _selectedProduceActionCount;
        private int _selectedAttackActionCount;
        private int _inferenceKickDecisionRequestCount;
        private bool _inferenceDecisionRequesterActivated;
        private int _actualCollectCallIndex;
        private int _actionTraceCallIndex;
        private int _decisionSchedulerTraceIndex;
        private bool _pendingInferenceContinuousRequest;
        private int _fixedUpdatesSinceLastOnActionReceived;
        private int _lastContinuousRequestFixedTick = -1;
        private readonly Dictionary<string, int> _runtimeRejectReasonHistogram = new Dictionary<string, int>();
        private readonly Dictionary<string, int> _schedulerSkipReasonHistogram = new Dictionary<string, int>();
        private readonly Dictionary<int, int> _candidateActionIndexHistogram = new Dictionary<int, int>();
        private int _candidateActionIndexOutOfRangeCount;
        private int _runtimeApplyAttemptedNoOpCount;
        private int _runtimeApplyAttemptedMoveCount;
        private int _runtimeApplyAttemptedHarvestCount;
        private int _runtimeApplyAttemptedReturnCount;
        private int _runtimeApplyAttemptedProduceCount;
        private int _runtimeApplyAttemptedAttackCount;
        private int _runtimeApplyAcceptedNoOpCount;
        private int _runtimeApplyAcceptedMoveCount;
        private int _runtimeApplyAcceptedHarvestCount;
        private int _runtimeApplyAcceptedReturnCount;
        private int _runtimeApplyAcceptedProduceCount;
        private int _runtimeApplyAcceptedAttackCount;
        private int _firstAcceptedCommandFrame = -1;
        private int _lastAcceptedCommandFrame = -1;
        private long _firstAcceptedCommandAcademyStep = -1;
        private long _lastAcceptedCommandAcademyStep = -1;
        private bool _inferenceRuntimeReadyObserved;
        private int _firstInferenceReadyFrame = -1;
        private int _firstInferenceReadyFixedTick = -1;
        private bool _collectObservedSinceLastEnable;
        private bool _collectObservedSinceLastStart;
        private bool _collectObservedSinceLastEpisodeBegin;
        private int _defensivePreReadyObservationCount;
        private bool _defensivePreReadyObservationUsedAfterRuntimeReady;

        public Stage7BActionTrace Trace { get; } = new Stage7BActionTrace();
        public MlAgentsCandidateActionList CurrentCandidates => _currentCandidates;
        public string CurrentDecisionSource => _currentDecisionSource;
        public bool ManualFixedUpdateDecisionRequestsEnabled => _manualFixedUpdateDecisionRequests;
        public bool DecisionRequesterWatchdogFallbackEnabled => _enableDecisionRequesterWatchdogFallback;
        public bool DecisionRequesterWatchdogFallbackActive => _decisionRequesterWatchdogFallbackActive;
        public int OnEnableCount => _onEnableCount;
        public int AwakeCount => _awakeCount;
        public int StartCount => _startCount;
        public int InitializeCount => _initializeCount;
        public int OnEpisodeBeginCount => _onEpisodeBeginCount;
        public int HeuristicCallCount => _heuristicCallCount;
        public int ManualRequestDecisionCount => _manualRequestDecisionCount;
        public int ManualRequestActionCount => _manualRequestActionCount;
        public int LastObservationLength => _lastObservationLength;
        public int LastObservationNanCount => _lastObservationNanCount;
        public int LastActionCandidateIndex => _lastActionCandidateIndex;
        public bool LastActionAccepted => _lastActionAccepted;
        public int TerminalCount => _terminalCount;
        public int EndEpisodeCount => _endEpisodeCount;
        public float FirstCollectObservationsTime => _firstCollectObservationsTime;
        public float FirstWriteMaskTime => _firstWriteMaskTime;
        public float FirstOnActionReceivedTime => _firstOnActionReceivedTime;
        public int FirstCollectObservationsFrame => _firstCollectObservationsFrame;
        public int FirstWriteMaskFrame => _firstWriteMaskFrame;
        public int FirstOnActionReceivedFrame => _firstOnActionReceivedFrame;
        public double FirstResetDurationMs => _firstResetDurationMs;
        public double FirstObservationDurationMs => _firstObservationDurationMs;
        public double FirstWriteMaskDurationMs => _firstWriteMaskDurationMs;
        public double FirstOnActionReceivedDurationMs => _firstOnActionReceivedDurationMs;
        public bool OnEpisodeBeginStartNewEpisodeCalled => _onEpisodeBeginStartNewEpisodeCalled;
        public bool OnEpisodeBeginStartNewEpisodeResult => _onEpisodeBeginStartNewEpisodeResult;
        public bool OnEpisodeBeginUsedTrainerControlledEpisodeResetPath => _onEpisodeBeginUsedTrainerControlledEpisodeResetPath;
        public string OnEpisodeBeginStartNewEpisodePath => _onEpisodeBeginStartNewEpisodePath;
        public int TrainerControlledKickDecisionRequestCount => _trainerControlledKickDecisionRequestCount;
        public int CandidateBuildCallCount => _candidateBuildCallCount;
        public int CandidateBuilderSuccessCount => _candidateBuilderSuccessCount;
        public int ActionAdapterResolveCount => _actionAdapterResolveCount;
        public int ActionAdapterSuccessCount => _actionAdapterSuccessCount;
        public bool LastCandidateIndexInRange => _lastCandidateIndexInRange;
        public int RuntimeApplyAttemptedCount => _runtimeApplyAttemptedCount;
        public int RuntimeApplyAcceptedCount => _runtimeApplyAcceptedCount;
        public int RuntimeApplyRejectedCount => _runtimeApplyRejectedCount;
        public int RequestDecisionCount => _requestDecisionCount;
        public int InferenceContinuousRequestDecisionCount => _inferenceContinuousRequestDecisionCount;
        public bool PendingInferenceContinuousRequest => _pendingInferenceContinuousRequest;
        public int ObservationBuilderUsedCount => _observationBuilderUsedCount;
        public int ObservationFallbackCount => _observationFallbackCount;
        public int SelectedNoOpActionCount => _selectedNoOpActionCount;
        public int SelectedMoveActionCount => _selectedMoveActionCount;
        public int SelectedHarvestActionCount => _selectedHarvestActionCount;
        public int SelectedReturnActionCount => _selectedReturnActionCount;
        public int SelectedProduceActionCount => _selectedProduceActionCount;
        public int SelectedAttackActionCount => _selectedAttackActionCount;
        public int InferenceKickDecisionRequestCount => _inferenceKickDecisionRequestCount;
        public bool InferenceDecisionRequesterActivated => _inferenceDecisionRequesterActivated;
        public IReadOnlyDictionary<string, int> RuntimeRejectReasonHistogram => _runtimeRejectReasonHistogram;
        public IReadOnlyDictionary<string, int> SchedulerSkipReasonHistogram => _schedulerSkipReasonHistogram;
        public IReadOnlyDictionary<int, int> CandidateActionIndexHistogram => _candidateActionIndexHistogram;
        public int CandidateActionIndexOutOfRangeCount => _candidateActionIndexOutOfRangeCount;
        public int CandidateBuilderFailureCount => Mathf.Max(0, _candidateBuildCallCount - _candidateBuilderSuccessCount);
        public int ActionAdapterFailureCount => Mathf.Max(0, _actionAdapterResolveCount - _actionAdapterSuccessCount);
        public int RuntimeApplyAttemptedNoOpCount => _runtimeApplyAttemptedNoOpCount;
        public int RuntimeApplyAttemptedMoveCount => _runtimeApplyAttemptedMoveCount;
        public int RuntimeApplyAttemptedHarvestCount => _runtimeApplyAttemptedHarvestCount;
        public int RuntimeApplyAttemptedReturnCount => _runtimeApplyAttemptedReturnCount;
        public int RuntimeApplyAttemptedProduceCount => _runtimeApplyAttemptedProduceCount;
        public int RuntimeApplyAttemptedAttackCount => _runtimeApplyAttemptedAttackCount;
        public int RuntimeApplyAcceptedNoOpCount => _runtimeApplyAcceptedNoOpCount;
        public int RuntimeApplyAcceptedMoveCount => _runtimeApplyAcceptedMoveCount;
        public int RuntimeApplyAcceptedHarvestCount => _runtimeApplyAcceptedHarvestCount;
        public int RuntimeApplyAcceptedReturnCount => _runtimeApplyAcceptedReturnCount;
        public int RuntimeApplyAcceptedProduceCount => _runtimeApplyAcceptedProduceCount;
        public int RuntimeApplyAcceptedAttackCount => _runtimeApplyAcceptedAttackCount;
        public int FirstAcceptedCommandFrame => _firstAcceptedCommandFrame;
        public int LastAcceptedCommandFrame => _lastAcceptedCommandFrame;
        public long FirstAcceptedCommandAcademyStep => _firstAcceptedCommandAcademyStep;
        public long LastAcceptedCommandAcademyStep => _lastAcceptedCommandAcademyStep;
        public int DefensivePreReadyObservationCount => _defensivePreReadyObservationCount;
        public bool DefensivePreReadyObservationUsedAfterRuntimeReady => _defensivePreReadyObservationUsedAfterRuntimeReady;
        public bool InferenceRuntimeReadyObserved => _inferenceRuntimeReadyObserved;
        public int FirstInferenceReadyFrame => _firstInferenceReadyFrame;
        public int FirstInferenceReadyFixedTick => _firstInferenceReadyFixedTick;

        /// <summary>
        /// Stage7B-7: Set by Stage7BTeacherReplayDemoOrchestrator to enable teacher-replay-demo
        /// mode.  When non-null and active, Heuristic() returns the orchestrator's queued
        /// candidate index and OnActionReceived() skips reward / episode-end evaluation.
        /// </summary>
        internal Stage7BTeacherReplayDemoOrchestrator TeacherReplayOrchestrator { get; set; }

        private void Awake()
        {
            _awakeCount++;
            Stage7BResetTimeoutTrace.Record("StudentMlAgent.Awake", this, _bootstrap);
        }

        protected override void OnEnable()
        {
            _onEnableCount++;
            _collectObservedSinceLastEnable = false;
            ConfigureBehaviorParameters();
            ApplyDecisionSourcePolicy();
            Stage7BResetTimeoutTrace.Record("StudentMlAgent.OnEnable.enter", this, _bootstrap);
            base.OnEnable();
            Stage7BResetTimeoutTrace.Record("StudentMlAgent.OnEnable.exit", this, _bootstrap);
        }

        private void Start()
        {
            _startCount++;
            _actualCollectCallIndex = 0;
            _actionTraceCallIndex = 0;
            _decisionSchedulerTraceIndex = 0;
            _collectObservedSinceLastStart = false;
            _pendingInferenceContinuousRequest = false;
            _fixedUpdatesSinceLastOnActionReceived = 0;
            _lastContinuousRequestFixedTick = -1;
            _schedulerSkipReasonHistogram.Clear();
            ClearActualCollectTraceFile();
            ClearTraceFile(_actionTraceRelativePath);
            ClearTraceFile(_runtimeApplyTraceRelativePath);
            ClearTraceFile(_decisionSchedulerTraceRelativePath);
            Stage7BResetTimeoutTrace.Record("StudentMlAgent.Start", this, _bootstrap);
        }

        public void Configure(MlAgentsTrainingBootstrap bootstrap, Owner playerPerspective)
        {
            _bootstrap = bootstrap;
            _playerPerspective = playerPerspective;
            ResolveDependencies();
        }

        public override void Initialize()
        {
            _initializeCount++;
            Stage7BResetTimeoutTrace.Record("StudentMlAgent.Initialize.enter", this, _bootstrap);
            ResolveDependencies();
            ConfigureBehaviorParameters();
            ApplyDecisionSourcePolicy();
            Stage7BResetTimeoutTrace.Record("StudentMlAgent.Initialize.exit", this, _bootstrap);
        }

        public void ConfigureForTrainerControlledMode()
        {
            _manualFixedUpdateDecisionRequests = false;
            _allowConcurrentDecisionSourcesForDebug = false;
            _enableDecisionRequesterWatchdogFallback = false;
            _decisionRequesterWatchdogFallbackActive = false;
            _inferenceDecisionRequesterActivated = false;
            _inferenceRuntimeReadyObserved = false;
            _firstInferenceReadyFrame = -1;
            _firstInferenceReadyFixedTick = -1;
            _defensivePreReadyObservationCount = 0;
            _defensivePreReadyObservationUsedAfterRuntimeReady = false;
            _fixedUpdatesWithoutDecisionWhileUsingDecisionRequester = 0;
            _loggedDecisionSourceGuard = false;
            TeacherReplayOrchestrator = null;
            ApplyDecisionSourcePolicy();
        }

        private void OnApplicationQuit()
        {
            _applicationIsQuitting = true;
        }

        public override void OnEpisodeBegin()
        {
            _onEpisodeBeginCount++;
            Stage7BResetTimeoutTrace.Record("StudentMlAgent.OnEpisodeBegin.enter", this, _bootstrap);
            Stopwatch timer = Stopwatch.StartNew();
            ResolveDependencies();
            _observationBuilder = null;
            _candidateBuilder = null;
            _actionApplier = null;

            _onEpisodeBeginStartNewEpisodeCalled = _bootstrap != null;
            _onEpisodeBeginStartNewEpisodeResult = false;
            _onEpisodeBeginUsedTrainerControlledEpisodeResetPath =
                _bootstrap != null && _bootstrap.RuntimeMode == Stage7BRuntimeMode.TrainerControlled;
            _onEpisodeBeginStartNewEpisodePath = "none";

            if (_bootstrap != null)
            {
                _onEpisodeBeginStartNewEpisodeResult = _onEpisodeBeginUsedTrainerControlledEpisodeResetPath
                    ? _bootstrap.StartNewEpisodeForAgentReset()
                    : _bootstrap.StartNewEpisode("agent_on_episode_begin", "StudentMlAgent.OnEpisodeBegin");
                _onEpisodeBeginStartNewEpisodePath = _bootstrap.LastStartNewEpisodePath;
            }

            ResolveDependencies();
            _rewardCollector?.ResetEpisode();
            _episodeDecisionCount = 0;
            _fixedUpdatesWithoutDecisionWhileUsingDecisionRequester = 0;
            _inferenceDecisionRequesterActivated = false;
            _pendingInferenceContinuousRequest = false;
            _fixedUpdatesSinceLastOnActionReceived = 0;
            _lastContinuousRequestFixedTick = -1;
            _collectObservedSinceLastEpisodeBegin = false;
            Trace.RecordReset(_bootstrap != null && _bootstrap.DuplicateSpawnDetected);
            _currentCandidates = null;
            _pendingTrainerControlledKickDecision =
                _onEpisodeBeginUsedTrainerControlledEpisodeResetPath && _onEpisodeBeginStartNewEpisodeResult;
            timer.Stop();
            if (_firstResetDurationMs < 0d)
            {
                _firstResetDurationMs = timer.Elapsed.TotalMilliseconds;
            }
            Stage7BResetTimeoutTrace.Record("StudentMlAgent.OnEpisodeBegin.exit", this, _bootstrap);
        }

        private void FixedUpdate()
        {
            ApplyDecisionSourcePolicy();
            UpdateDecisionRequesterWatchdog();
            _fixedUpdatesSinceLastOnActionReceived++;

            if (TryActivateInferenceDecisionKick())
            {
                return;
            }

            if (TryRequestTrainerControlledKickDecision())
            {
                return;
            }

            if (TryRequestInferenceContinuousDecision())
            {
                return;
            }

            if (!ShouldUseManualFixedUpdateDecisionRequests())
            {
                return;
            }

            ResolveDependencies();
            if (_bootstrap == null || _bootstrap.MatchManager == null)
            {
                return;
            }

            if (_bootstrap.MatchManager.Phase == MatchPhase.Running)
            {
                _manualRequestDecisionCount++;
                Stage7BResetTimeoutTrace.Record("StudentMlAgent.RequestDecision.manual", this, _bootstrap);
                RequestDecisionWithTracking("manual_fixedupdate", false);
            }
        }

        private bool TryRequestTrainerControlledKickDecision()
        {
            if (!_pendingTrainerControlledKickDecision)
            {
                return false;
            }

            ResolveDependencies();
            if (_bootstrap == null
                || _bootstrap.MatchManager == null
                || _bootstrap.MatchManager.Phase != MatchPhase.Running)
            {
                return false;
            }

            _pendingTrainerControlledKickDecision = false;
            _trainerControlledKickDecisionRequestCount++;
            Stage7BResetTimeoutTrace.Record("StudentMlAgent.RequestDecision.trainer_controlled_kick", this, _bootstrap);
            RequestDecisionWithTracking("trainer_controlled_kick", false);
            return true;
        }

        public override void CollectObservations(VectorSensor sensor)
        {
            Stage7BResetTimeoutTrace.Record("StudentMlAgent.CollectObservations.enter", this, _bootstrap);
            Stopwatch timer = Stopwatch.StartNew();
            ResolveDependencies();

            _actualCollectCallIndex++;
            bool observationBuilderCalled = _observationBuilder != null;
            bool runtimeServicesReady = AreInferenceRuntimeServicesReady();
            string earlyExitReason = ResolveCollectEarlyExitReason(runtimeServicesReady, observationBuilderCalled);
            bool firstCallAfterEnable = !_collectObservedSinceLastEnable;
            bool firstCallAfterStart = !_collectObservedSinceLastStart;
            bool firstCallAfterEpisodeBegin = !_collectObservedSinceLastEpisodeBegin;
            bool defensivePreReadyObservation = !runtimeServicesReady;

            float[] observation = _observationBuilder != null
                ? _observationBuilder.BuildObservation(_playerPerspective, ObservationMode.UnityMvpTransfer)
                : new float[ObservationContract.TotalFloats];

            if (_observationBuilder != null)
            {
                _observationBuilderUsedCount++;
            }
            else
            {
                _observationFallbackCount++;
            }

            ValidateObservation(observation);
            Trace.RecordObservation(observation);
            _lastObservationLength = observation != null ? observation.Length : 0;
            _lastObservationNanCount = Trace.ObservationNanCount;
            sensor.AddObservation(observation);

            if (defensivePreReadyObservation)
            {
                _defensivePreReadyObservationCount++;
                if (_inferenceRuntimeReadyObserved)
                {
                    _defensivePreReadyObservationUsedAfterRuntimeReady = true;
                }
            }

            _collectObservedSinceLastEnable = true;
            _collectObservedSinceLastStart = true;
            _collectObservedSinceLastEpisodeBegin = true;

            AppendActualCollectObservationTrace(
                _actualCollectCallIndex,
                runtimeServicesReady,
                observationBuilderCalled,
                _lastObservationLength,
                _observationBuilder == null,
                earlyExitReason,
                defensivePreReadyObservation,
                firstCallAfterEnable,
                firstCallAfterStart,
                firstCallAfterEpisodeBegin);

            timer.Stop();
            if (_firstCollectObservationsTime < 0f)
            {
                _firstCollectObservationsTime = Time.realtimeSinceStartup;
                _firstCollectObservationsFrame = Time.frameCount;
            }

            if (_firstObservationDurationMs < 0d)
            {
                _firstObservationDurationMs = timer.Elapsed.TotalMilliseconds;
            }
            Stage7BResetTimeoutTrace.Record(
                "StudentMlAgent.CollectObservations.exit",
                this,
                _bootstrap,
                observationLength: _lastObservationLength,
                observationNanCount: _lastObservationNanCount);
        }

        public override void WriteDiscreteActionMask(IDiscreteActionMask actionMask)
        {
            Stage7BResetTimeoutTrace.Record("StudentMlAgent.WriteDiscreteActionMask.enter", this, _bootstrap);
            Stopwatch timer = Stopwatch.StartNew();
            ResolveDependencies();
            BuildCandidates();
            _maskAdapter.WriteDiscreteActionMask(actionMask, _currentCandidates);
            Trace.RecordMask(
                _currentCandidates != null ? _currentCandidates.CandidateCount : 0,
                _maskAdapter.LastMaskedEmptySlots,
                _currentCandidates != null ? _currentCandidates.OverflowCount : 0);
            timer.Stop();
            if (_firstWriteMaskTime < 0f)
            {
                _firstWriteMaskTime = Time.realtimeSinceStartup;
                _firstWriteMaskFrame = Time.frameCount;
            }

            if (_firstWriteMaskDurationMs < 0d)
            {
                _firstWriteMaskDurationMs = timer.Elapsed.TotalMilliseconds;
            }
            Stage7BResetTimeoutTrace.Record(
                "StudentMlAgent.WriteDiscreteActionMask.exit",
                this,
                _bootstrap,
                candidateCount: _currentCandidates != null ? _currentCandidates.CandidateCount : -1,
                maskedSlots: _maskAdapter.LastMaskedEmptySlots);
        }

        public override void OnActionReceived(ActionBuffers actions)
        {
            Stage7BResetTimeoutTrace.Record("StudentMlAgent.OnActionReceived.enter", this, _bootstrap);
            Stopwatch timer = Stopwatch.StartNew();
            ResolveDependencies();
            ApplyDecisionSourcePolicy();
            if (IsSimulationPauseActive("on_action_received_enter"))
            {
                _currentCandidates = null;
                timer.Stop();
                Stage7BResetTimeoutTrace.Record("StudentMlAgent.OnActionReceived.paused", this, _bootstrap);
                AppendDecisionSchedulerTrace(
                    "on_action_received_paused",
                    "simulation_paused",
                    accepted: false,
                    requestedDecisionNow: false,
                    scheduledNextDecision: false,
                    decisionRequesterExpectedToDrive: ShouldDecisionRequesterDriveInference());
                return;
            }

            _bootstrap?.EnsureReadyForDecision();
            BuildCandidates();

            RuntimeRewardCollector collector = _rewardCollector;
            RewardRuntimeSnapshot pre = collector != null
                ? collector.CaptureSnapshot(_bootstrap.MatchManager, _bootstrap.UnitRegistry)
                : default;

            int selectedIndex = actions.DiscreteActions.Length > 0 ? actions.DiscreteActions[0] : 0;
            _lastActionCandidateIndex = selectedIndex;
            _lastCandidateIndexInRange = selectedIndex >= 0 && selectedIndex < MlAgentsCandidateActionList.BranchSize;
            if (!_lastCandidateIndexInRange)
            {
                _candidateActionIndexOutOfRangeCount++;
            }
            if (_candidateActionIndexHistogram.TryGetValue(selectedIndex, out int actionIndexCount))
            {
                _candidateActionIndexHistogram[selectedIndex] = actionIndexCount + 1;
            }
            else
            {
                _candidateActionIndexHistogram[selectedIndex] = 1;
            }

            _episodeDecisionCount++;
            _fixedUpdatesWithoutDecisionWhileUsingDecisionRequester = 0;
            _fixedUpdatesSinceLastOnActionReceived = 0;
            _bootstrap?.ScriptedOpponentPacing?.RecordStudentActionAttempt();
            AgentAction selectedAction = _actionAdapter.Resolve(_currentCandidates, selectedIndex, out MlAgentsCandidateAction candidate);
            _actionAdapterResolveCount++;
            if (!_actionAdapter.LastFallbackToNoOp)
            {
                _actionAdapterSuccessCount++;
            }
            RecordSelectedActionType(selectedAction.ActionType);

            // Stage7B-7: teacher-replay-demo mode — apply action, notify orchestrator, skip
            // reward evaluation and episode-end so the recording loop is not interrupted.
            Stage7BTeacherReplayDemoOrchestrator replayOrchestrator = TeacherReplayOrchestrator;
            if (replayOrchestrator != null && replayOrchestrator.IsActive)
            {
                bool demoAccepted = false;
                if (_actionApplier != null)
                {
                    _runtimeApplyAttemptedCount++;
                    _actionApplier.ResetDiagnostics();
                    demoAccepted = _actionApplier.ApplyAction(
                        selectedAction, _playerPerspective, _currentCandidates?.SourceMask,
                        "stage7b-demo-replay");
                    if (demoAccepted)
                    {
                        _runtimeApplyAcceptedCount++;
                    }
                    else
                    {
                        _runtimeApplyRejectedCount++;
                    }
                    RecordRuntimeRejectReasons(_actionApplier.RejectionReasonsLastStep);
                }

                if (_bootstrap != null
                    && _bootstrap.MatchManager != null
                    && _bootstrap.MatchManager.Phase == MatchPhase.Running
                    && CanAdvanceMatchFromStudentAgent("demo_replay_stepmatch"))
                {
                    _bootstrap.MatchManager.StepMatch();
                }

                string demoSummary = "actor=" + selectedAction.ActorPosition
                    + ",type=" + selectedAction.ActionType
                    + ",dir=" + selectedAction.Direction;
                replayOrchestrator.NotifyActionApplied(demoAccepted, selectedIndex, demoSummary);
                _lastActionAccepted = demoAccepted;
                UpdateInferenceContinuousScheduleAfterAction(demoAccepted);

                _currentCandidates = null;
                timer.Stop();
                if (_firstOnActionReceivedTime < 0f)
                {
                    _firstOnActionReceivedTime = Time.realtimeSinceStartup;
                    _firstOnActionReceivedFrame = Time.frameCount;
                }

                if (_firstOnActionReceivedDurationMs < 0d)
                {
                    _firstOnActionReceivedDurationMs = timer.Elapsed.TotalMilliseconds;
                }
                Stage7BResetTimeoutTrace.Record(
                    "StudentMlAgent.OnActionReceived.exit.demo",
                    this,
                    _bootstrap,
                    lastActionIndex: _lastActionCandidateIndex);
                AppendDecisionSchedulerTrace(
                    "on_action_received_exit_demo",
                    "none",
                    demoAccepted,
                    requestedDecisionNow: false,
                    scheduledNextDecision: _pendingInferenceContinuousRequest,
                    decisionRequesterExpectedToDrive: ShouldDecisionRequesterDriveInference());
                return;
            }
            Trace.RecordCandidateFallback(
                _actionAdapter.LastInvalidCandidateIndexSelected,
                _actionAdapter.LastEmptyCandidateSelected,
                _actionAdapter.LastOutOfRangeCandidateSelected,
                _actionAdapter.LastFallbackToNoOp);
            bool selectedNoOp = candidate.IsEmpty || candidate.IsNoOp || selectedAction.ActionType == UnitActionType.NoOp;
            Trace.RecordActionSelected(selectedNoOp);

            bool accepted = false;
            if (_actionApplier != null)
            {
                _runtimeApplyAttemptedCount++;
                RecordRuntimeAttemptedActionType(selectedAction.ActionType);
                _actionApplier.ResetDiagnostics();
                accepted = _actionApplier.ApplyAction(
                    selectedAction,
                    _playerPerspective,
                    _currentCandidates?.SourceMask,
                    "stage7b-candidate-action-index");
                _lastActionAccepted = accepted;

                if (accepted)
                {
                    _runtimeApplyAcceptedCount++;
                    RecordRuntimeAcceptedActionType(selectedAction.ActionType);
                    RecordAcceptedCommandPosition();
                }
                else
                {
                    _runtimeApplyRejectedCount++;
                }
                RecordRuntimeRejectReasons(_actionApplier.RejectionReasonsLastStep);

                Trace.RecordApplyResult(
                    accepted ? 1 : 0,
                    accepted ? 0 : _actionApplier.RejectedActionsLastStep,
                    _actionApplier.RejectionReasonsLastStep);

                if (_logRejectedActions && !accepted && _actionApplier.RejectionReasonsLastStep.Count > 0)
                {
                    Debug.LogWarning("[Stage7B] Rejected candidate action: " + _actionApplier.RejectionReasonsLastStep[0]);
                }

                AppendRuntimeApplyTrace(
                    _runtimeApplyAttemptedCount,
                    selectedIndex,
                    selectedAction.ActionType,
                    accepted,
                    _actionApplier.RejectionReasonsLastStep,
                    candidate.IsEmpty,
                    candidate.IsNoOp);
            }

            AppendActionTrace(
                _episodeDecisionCount,
                selectedIndex,
                _lastCandidateIndexInRange,
                selectedAction.ActionType,
                candidate.IsEmpty,
                candidate.IsNoOp,
                _actionAdapter.LastFallbackToNoOp,
                _currentCandidates != null ? _currentCandidates.CandidateCount : 0,
                _actionApplier != null,
                accepted);

            UpdateInferenceContinuousScheduleAfterAction(accepted);

            if (_bootstrap != null
                && _bootstrap.StepScriptedOpponent
                && _bootstrap.ScriptedOpponentAdapter != null
                && _bootstrap.MatchManager != null
                && _bootstrap.MatchManager.Phase == MatchPhase.Running
                && CanAdvanceMatchFromStudentAgent("scripted_opponent_decision"))
            {
                bool shouldRunScriptedOpponent = _bootstrap.ScriptedOpponentPacing == null
                    || _bootstrap.ScriptedOpponentPacing.ShouldExecuteBotDecisionStep(Time.time);
                if (shouldRunScriptedOpponent)
                {
                    using (HumanPlayCommandSourceDiagnostics.PushSource("Stage7B.ScriptedOpponentViaStudentMlAgent"))
                    {
                        (int acceptedTotal, int rejectedTotal) = _bootstrap.ScriptedOpponentAdapter.ExecuteDecisionStepWithCounts();
                        _bootstrap.ScriptedOpponentPacing?.RecordBotDecisionOutcome(acceptedTotal, rejectedTotal);
                    }
                }
            }

            bool stillRunning = _bootstrap != null
                                && _bootstrap.MatchManager != null
                                && CanAdvanceMatchFromStudentAgent("student_on_action_stepmatch")
                                && _bootstrap.MatchManager.StepMatch();

            if (collector != null && _bootstrap != null)
            {
                RewardRuntimeSnapshot post = collector.CaptureSnapshot(_bootstrap.MatchManager, _bootstrap.UnitRegistry);
                RewardStepTrace rewardTrace = collector.EvaluateStep(pre, post, _playerPerspective);
                float reward = rewardTrace.Breakdown.Total;
                AddReward(reward);
                Trace.RecordReward(reward);

                bool stage7BLimitReached = _stage7BMaxDecisionsPerEpisode > 0
                                           && _episodeDecisionCount >= _stage7BMaxDecisionsPerEpisode;

                if (rewardTrace.Breakdown.IsTerminalStep || !stillRunning || stage7BLimitReached)
                {
                    string terminalReason = stage7BLimitReached
                        ? "stage7b_decision_limit"
                        : rewardTrace.Breakdown.TerminalReason.ToString();
                    if (_bootstrap.MatchManager != null && _bootstrap.MatchManager.Phase == MatchPhase.Ended)
                    {
                        terminalReason = _bootstrap.MatchManager.EndReason.ToString();
                    }

                    Trace.RecordTerminal(terminalReason);
                    _terminalCount++;
                    _bootstrap?.ScriptedOpponentPacing?.FinalizeEpisodeAndWriteReport(terminalReason);
                    _endEpisodeCount++;
                    Stage7BResetTimeoutTrace.Record("StudentMlAgent.EndEpisode", this, _bootstrap, terminalReason);
                    EndEpisode();
                }
            }
            else if (!stillRunning)
            {
                Trace.RecordTerminal("runtime-ended");
                _terminalCount++;
                _bootstrap?.ScriptedOpponentPacing?.FinalizeEpisodeAndWriteReport("runtime-ended");
                _endEpisodeCount++;
                Stage7BResetTimeoutTrace.Record("StudentMlAgent.EndEpisode", this, _bootstrap, "runtime-ended");
                EndEpisode();
            }

            _currentCandidates = null;
            timer.Stop();
            if (_firstOnActionReceivedTime < 0f)
            {
                _firstOnActionReceivedTime = Time.realtimeSinceStartup;
                _firstOnActionReceivedFrame = Time.frameCount;
            }

            if (_firstOnActionReceivedDurationMs < 0d)
            {
                _firstOnActionReceivedDurationMs = timer.Elapsed.TotalMilliseconds;
            }
            Stage7BResetTimeoutTrace.Record(
                "StudentMlAgent.OnActionReceived.exit",
                this,
                _bootstrap,
                lastActionIndex: _lastActionCandidateIndex);
            AppendDecisionSchedulerTrace(
                "on_action_received_exit",
                "none",
                accepted,
                requestedDecisionNow: false,
                scheduledNextDecision: _pendingInferenceContinuousRequest,
                decisionRequesterExpectedToDrive: ShouldDecisionRequesterDriveInference());
        }

        private bool CanAdvanceMatchFromStudentAgent(string source)
        {
            return !IsSimulationPauseActive(source);
        }

        private bool IsSimulationPauseActive(string source)
        {
            EpisodeController episodeController = EpisodeController.Instance;
            if (episodeController == null)
            {
                episodeController = FindFirstObjectByType<EpisodeController>();
            }

            if (episodeController == null || !episodeController.IsAutomaticSteppingPaused)
            {
                return false;
            }

            if (Time.unscaledTime - _lastPauseGateLogRealtime >= 1f)
            {
                _lastPauseGateLogRealtime = Time.unscaledTime;
                int step = _bootstrap != null && _bootstrap.MatchManager != null ? _bootstrap.MatchManager.Step : -1;
                Debug.Log(
                    $"[PauseGate] Blocked StudentMlAgent source={source} step={step} "
                    + $"episodeController={episodeController.GetInstanceID()} "
                    + $"isAutomaticSteppingPaused={episodeController.IsAutomaticSteppingPaused}");
            }

            return true;
        }

        public override void Heuristic(in ActionBuffers actionsOut)
        {
            _heuristicCallCount++;
            Stage7BResetTimeoutTrace.Record("StudentMlAgent.Heuristic.enter", this, _bootstrap);
            ResolveDependencies();
            BuildCandidates();
            ActionSegment<int> discrete = actionsOut.DiscreteActions;
            if (discrete.Length == 0)
            {
                return;
            }

            // Stage7B-7: teacher-replay-demo mode — use orchestrator's matched candidate index.
            Stage7BTeacherReplayDemoOrchestrator orchestrator = TeacherReplayOrchestrator;
            if (orchestrator != null && orchestrator.IsActive)
            {
                if (orchestrator.TryConsumePendingCandidateIndex(out int replayIndex))
                {
                    discrete[0] = replayIndex;
                    Stage7BResetTimeoutTrace.Record("StudentMlAgent.Heuristic.exit", this, _bootstrap, "demo_index");
                    return;
                }
                // No pending index this tick — emit NoOp so we don't record unintended actions.
                discrete[0] = MlAgentsCandidateActionList.NoOpCandidateIndex;
                Stage7BResetTimeoutTrace.Record("StudentMlAgent.Heuristic.exit", this, _bootstrap, "demo_noop");
                return;
            }

            discrete[0] = SelectHeuristicCandidateIndex();
            Stage7BResetTimeoutTrace.Record("StudentMlAgent.Heuristic.exit", this, _bootstrap);
        }

        private void ResolveDependencies()
        {
            if (_applicationIsQuitting
                || !Application.isPlaying
                || !isActiveAndEnabled
                || !gameObject.activeInHierarchy)
            {
                return;
            }

            if (_bootstrap == null && _autoResolveBootstrap)
            {
                _bootstrap = FindFirstObjectByType<MlAgentsTrainingBootstrap>(FindObjectsInactive.Exclude);
            }

            GridManager grid = _bootstrap != null ? _bootstrap.GridManager : GridManager.Instance;
            UnitRegistry registry = _bootstrap != null ? _bootstrap.UnitRegistry : UnitRegistry.Instance;
            ResourceManager resources = _bootstrap != null ? _bootstrap.ResourceManager : ResourceManager.Instance;
            MatchManager match = _bootstrap != null ? _bootstrap.MatchManager : MatchManager.Instance;
            MatchBootstrap matchBootstrap = _bootstrap != null ? _bootstrap.MatchBootstrap : MatchBootstrap.Instance;

            if (grid == null || registry == null || match == null || matchBootstrap == null || matchBootstrap.GetConfig() == null)
            {
                return;
            }

            _observationBuilder ??= new ObservationBuilder(grid, registry, resources);
            if (_candidateBuilder == null)
            {
                var maskBuilder = new ActionMaskBuilder(match, grid, resources, registry, matchBootstrap);
                _candidateBuilder = new MlAgentsCandidateActionBuilder(maskBuilder);
            }

            _actionApplier = new ActionApplier(grid, registry, match, resources);
            _rewardCollector ??= new RuntimeRewardCollector(RewardConfig.CreateV1Defaults(), RewardCollectorOptions.CreateDefaults());
        }

        private void ConfigureBehaviorParameters()
        {
            BehaviorParameters behavior = GetComponent<BehaviorParameters>();
            if (behavior == null)
            {
                return;
            }

            behavior.BrainParameters.VectorObservationSize = ObservationContract.TotalFloats;
            behavior.BrainParameters.NumStackedVectorObservations = 1;
            behavior.BrainParameters.ActionSpec = ActionSpec.MakeDiscrete(MlAgentsCandidateActionList.BranchSize);
            Trace.RecordBehaviorSpec(behavior.BehaviorName, discreteBranchCount: 1, MlAgentsCandidateActionList.BranchSize);
            Trace.RecordActionContract(MlAgentsCandidateActionList.AttackTargetSize, MlAgentsCandidateActionList.AttackTargetCenterIndex);
        }

        private void ApplyDecisionSourcePolicy()
        {
            DecisionRequester requester = GetComponent<DecisionRequester>();
            bool hasRequester = requester != null;

            if (ShouldSuppressDecisionRequesterForInference())
            {
                if (hasRequester && requester.enabled)
                {
                    requester.enabled = false;
                }

                _currentDecisionSource = DecisionSourceNone;
                Trace.RecordDecisionSource(_currentDecisionSource);
                return;
            }

            if (_decisionRequesterWatchdogFallbackActive)
            {
                if (hasRequester && requester.enabled)
                {
                    requester.enabled = false;
                }

                _currentDecisionSource = DecisionSourceDecisionRequesterWatchdogManualFallback;
                Trace.RecordDecisionSource(_currentDecisionSource);
                return;
            }

            if (_manualFixedUpdateDecisionRequests)
            {
                if (hasRequester && !_allowConcurrentDecisionSourcesForDebug)
                {
                    if (requester.enabled)
                    {
                        requester.enabled = false;
                    }

                    if (!_loggedDecisionSourceGuard)
                    {
                        Debug.LogWarning("[Stage7B] Disabled DecisionRequester because manual FixedUpdate decision requests are enabled without the explicit debug override.");
                        _loggedDecisionSourceGuard = true;
                    }

                    _currentDecisionSource = DecisionSourceManualFixedUpdate;
                }
                else if (hasRequester && requester.enabled)
                {
                    _currentDecisionSource = DecisionSourceDecisionRequesterAndManualDebug;
                }
                else
                {
                    _currentDecisionSource = DecisionSourceManualFixedUpdate;
                }
            }
            else if (hasRequester)
            {
                bool requesterShouldBeEnabled = _bootstrap == null
                    || _bootstrap.RuntimeMode != Stage7BRuntimeMode.InferenceOnly
                    || AreInferenceRuntimeServicesReady();
                if (requesterShouldBeEnabled && !requester.enabled)
                {
                    requester.enabled = true;
                }
                else if (!requesterShouldBeEnabled && requester.enabled)
                {
                    requester.enabled = false;
                }

                _currentDecisionSource = DecisionSourceDecisionRequester;
                _loggedDecisionSourceGuard = false;
            }
            else
            {
                _currentDecisionSource = DecisionSourceNone;
            }

            Trace.RecordDecisionSource(_currentDecisionSource);
        }

        private bool TryActivateInferenceDecisionKick()
        {
            if (_bootstrap == null || _bootstrap.RuntimeMode != Stage7BRuntimeMode.InferenceOnly)
            {
                return false;
            }

            ResolveDependencies();
            bool ready = AreInferenceRuntimeServicesReady();
            if (!ready)
            {
                return false;
            }

            if (_inferenceDecisionRequesterActivated)
            {
                return false;
            }

            _inferenceDecisionRequesterActivated = true;
            _inferenceKickDecisionRequestCount++;
            Stage7BResetTimeoutTrace.Record("StudentMlAgent.RequestDecision.inference_kick", this, _bootstrap);
            RequestDecisionWithTracking("inference_kick", false);
            AppendDecisionSchedulerTrace(
                "inference_kick_consumed",
                "none",
                accepted: true,
                requestedDecisionNow: true,
                scheduledNextDecision: _pendingInferenceContinuousRequest,
                decisionRequesterExpectedToDrive: ShouldDecisionRequesterDriveInference());
            return true;
        }

        private bool TryRequestInferenceContinuousDecision()
        {
            if (!_pendingInferenceContinuousRequest)
            {
                return false;
            }

            if (_bootstrap == null || _bootstrap.RuntimeMode != Stage7BRuntimeMode.InferenceOnly)
            {
                RecordSchedulerSkip("not_inference_mode", false);
                _pendingInferenceContinuousRequest = false;
                return false;
            }

            if (_bootstrap.MatchManager == null || _bootstrap.MatchManager.Phase != MatchPhase.Running)
            {
                RecordSchedulerSkip("match_not_running", false);
                _pendingInferenceContinuousRequest = false;
                return false;
            }

            if (!isActiveAndEnabled || !gameObject.activeInHierarchy)
            {
                RecordSchedulerSkip("agent_inactive", false);
                _pendingInferenceContinuousRequest = false;
                return false;
            }

            if (_terminalCount > 0)
            {
                RecordSchedulerSkip("terminal_already_reached", false);
                _pendingInferenceContinuousRequest = false;
                return false;
            }

            if (TeacherReplayOrchestrator != null && TeacherReplayOrchestrator.IsActive)
            {
                RecordSchedulerSkip("teacher_replay_active", false);
                _pendingInferenceContinuousRequest = false;
                return false;
            }

            if (_manualFixedUpdateDecisionRequests || _decisionRequesterWatchdogFallbackActive)
            {
                RecordSchedulerSkip("manual_or_watchdog_path_active", false);
                _pendingInferenceContinuousRequest = false;
                return false;
            }

            ResolveDependencies();
            if (!AreInferenceRuntimeServicesReady())
            {
                RecordSchedulerSkip("runtime_not_ready", false);
                return false;
            }

            if (_fixedUpdatesSinceLastOnActionReceived < 2)
            {
                RecordSchedulerSkip("waiting_next_fixedupdate", false);
                return false;
            }

            int fixedTick = _bootstrap != null ? _bootstrap.BootstrapFixedTick : -1;
            if (fixedTick >= 0 && fixedTick == _lastContinuousRequestFixedTick)
            {
                RecordSchedulerSkip("already_requested_this_fixedtick", false);
                return false;
            }

            _pendingInferenceContinuousRequest = false;
            _lastContinuousRequestFixedTick = fixedTick;
            _inferenceContinuousRequestDecisionCount++;
            Stage7BResetTimeoutTrace.Record("StudentMlAgent.RequestDecision.inference_continuous", this, _bootstrap);
            RequestDecisionWithTracking("inference_continuous", true);
            AppendDecisionSchedulerTrace(
                "inference_continuous_request",
                "none",
                accepted: true,
                requestedDecisionNow: true,
                scheduledNextDecision: _pendingInferenceContinuousRequest,
                decisionRequesterExpectedToDrive: ShouldDecisionRequesterDriveInference());
            return true;
        }

        private void UpdateInferenceContinuousScheduleAfterAction(bool accepted)
        {
            if (_bootstrap == null || _bootstrap.RuntimeMode != Stage7BRuntimeMode.InferenceOnly)
            {
                _pendingInferenceContinuousRequest = false;
                return;
            }

            bool canSchedule = _bootstrap.MatchManager != null
                && _bootstrap.MatchManager.Phase == MatchPhase.Running
                && _terminalCount == 0
                && !(TeacherReplayOrchestrator != null && TeacherReplayOrchestrator.IsActive)
                && !_manualFixedUpdateDecisionRequests
                && !_decisionRequesterWatchdogFallbackActive;

            _pendingInferenceContinuousRequest = canSchedule;
            AppendDecisionSchedulerTrace(
                "post_action_schedule_update",
                canSchedule ? "none" : "post_action_not_schedulable",
                accepted,
                requestedDecisionNow: false,
                scheduledNextDecision: _pendingInferenceContinuousRequest,
                decisionRequesterExpectedToDrive: ShouldDecisionRequesterDriveInference());
        }

        private bool ShouldDecisionRequesterDriveInference()
        {
            if (_bootstrap == null || _bootstrap.RuntimeMode != Stage7BRuntimeMode.InferenceOnly)
            {
                return true;
            }

            return false;
        }

        private void RequestDecisionWithTracking(string reason, bool schedulerRequest)
        {
            _requestDecisionCount++;
            AppendDecisionSchedulerTrace(
                "request_decision_called",
                string.IsNullOrWhiteSpace(reason) ? "none" : reason,
                accepted: _lastActionAccepted,
                requestedDecisionNow: true,
                scheduledNextDecision: _pendingInferenceContinuousRequest,
                decisionRequesterExpectedToDrive: ShouldDecisionRequesterDriveInference());
            RequestDecision();
        }

        private void RecordSchedulerSkip(string reason, bool accepted)
        {
            string key = string.IsNullOrWhiteSpace(reason) ? "unknown" : reason;
            if (_schedulerSkipReasonHistogram.TryGetValue(key, out int count))
            {
                _schedulerSkipReasonHistogram[key] = count + 1;
            }
            else
            {
                _schedulerSkipReasonHistogram[key] = 1;
            }

            AppendDecisionSchedulerTrace(
                "scheduler_skip",
                key,
                accepted,
                requestedDecisionNow: false,
                scheduledNextDecision: _pendingInferenceContinuousRequest,
                decisionRequesterExpectedToDrive: ShouldDecisionRequesterDriveInference());
        }

        private void AppendDecisionSchedulerTrace(
            string eventName,
            string skipReason,
            bool accepted,
            bool requestedDecisionNow,
            bool scheduledNextDecision,
            bool decisionRequesterExpectedToDrive)
        {
            AppendJsonTraceLine(_decisionSchedulerTraceRelativePath, () =>
            {
                _decisionSchedulerTraceIndex++;
                Academy academy = Academy.IsInitialized ? Academy.Instance : null;
                DecisionRequester requester = GetComponent<DecisionRequester>();
                string matchState = _bootstrap != null && _bootstrap.MatchManager != null
                    ? _bootstrap.MatchManager.Phase.ToString()
                    : "missing";

                var sb = new StringBuilder(768);
                sb.Append('{');
                sb.Append("\"timestamp_utc\":\"").Append(DateTime.UtcNow.ToString("o")).Append("\",");
                sb.Append("\"trace_index\":").Append(_decisionSchedulerTraceIndex).Append(',');
                sb.Append("\"event\":\"").Append(EscapeJson(eventName)).Append("\",");
                sb.Append("\"skip_reason\":\"").Append(EscapeJson(skipReason)).Append("\",");
                sb.Append("\"on_action_received_index\":").Append(Trace != null ? Trace.OnActionReceivedCalls : 0).Append(',');
                sb.Append("\"frame\":").Append(Time.frameCount).Append(',');
                sb.Append("\"fixed_time\":").Append(Time.fixedTime.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',');
                sb.Append("\"bootstrap_fixed_tick\":").Append(_bootstrap != null ? _bootstrap.BootstrapFixedTick : -1).Append(',');
                sb.Append("\"academy_step\":").Append(academy != null ? academy.StepCount : -1L).Append(',');
                sb.Append("\"decision_requester_enabled\":").Append(requester != null && requester.enabled ? "true" : "false").Append(',');
                sb.Append("\"decision_requester_expected_to_drive\":").Append(decisionRequesterExpectedToDrive ? "true" : "false").Append(',');
                sb.Append("\"inference_runtime_ready\":").Append(AreInferenceRuntimeServicesReady() ? "true" : "false").Append(',');
                sb.Append("\"inference_kick_consumed\":").Append(_inferenceDecisionRequesterActivated ? "true" : "false").Append(',');
                sb.Append("\"pending_next_request\":").Append(_pendingInferenceContinuousRequest ? "true" : "false").Append(',');
                sb.Append("\"requested_decision_now\":").Append(requestedDecisionNow ? "true" : "false").Append(',');
                sb.Append("\"scheduled_next_request\":").Append(scheduledNextDecision ? "true" : "false").Append(',');
                sb.Append("\"agent_is_active_and_enabled\":").Append(isActiveAndEnabled ? "true" : "false").Append(',');
                sb.Append("\"agent_gameobject_active\":").Append(gameObject.activeInHierarchy ? "true" : "false").Append(',');
                sb.Append("\"match_state\":\"").Append(EscapeJson(matchState)).Append("\",");
                sb.Append("\"action_accepted\":").Append(accepted ? "true" : "false").Append(',');
                sb.Append("\"end_episode_count\":").Append(_endEpisodeCount).Append(',');
                sb.Append("\"terminal_count\":").Append(_terminalCount).Append(',');
                sb.Append("\"on_episode_begin_count\":").Append(_onEpisodeBeginCount).Append(',');
                sb.Append("\"request_decision_count\":").Append(_requestDecisionCount).Append(',');
                sb.Append("\"inference_continuous_request_count\":").Append(_inferenceContinuousRequestDecisionCount);
                sb.Append('}');
                return sb.ToString();
            }, "decision scheduler trace");
        }

        private bool ShouldSuppressDecisionRequesterForInference()
        {
            if (_bootstrap == null || _bootstrap.RuntimeMode != Stage7BRuntimeMode.InferenceOnly)
            {
                return false;
            }

            return !_bootstrap.HasRuntimeEpisodeStarted
                   || _bootstrap.MatchManager == null
                   || _bootstrap.MatchManager.Phase != MatchPhase.Running
                   || _observationBuilder == null
                   || _candidateBuilder == null
                   || _actionApplier == null;
        }

        private bool AreInferenceRuntimeServicesReady()
        {
            if (_bootstrap == null)
            {
                return false;
            }

            if (_bootstrap.RuntimeMode != Stage7BRuntimeMode.InferenceOnly)
            {
                return _bootstrap.MatchManager != null && _bootstrap.MatchManager.Phase == MatchPhase.Running;
            }

            bool ready = _bootstrap.HasRuntimeEpisodeStarted
                   && _bootstrap.InferenceRuntimeReady
                   && _bootstrap.MatchManager != null
                   && _bootstrap.MatchManager.Phase == MatchPhase.Running
                   && _observationBuilder != null
                   && _candidateBuilder != null
                   && _actionApplier != null;

            if (ready && !_inferenceRuntimeReadyObserved)
            {
                _inferenceRuntimeReadyObserved = true;
                _firstInferenceReadyFrame = Time.frameCount;
                _firstInferenceReadyFixedTick = _bootstrap.BootstrapFixedTick;
            }

            return ready;
        }

        private string ResolveCollectEarlyExitReason(bool runtimeServicesReady, bool observationBuilderCalled)
        {
            if (runtimeServicesReady)
            {
                return "none";
            }

            if (_bootstrap == null)
            {
                return "bootstrap_missing";
            }

            if (!_bootstrap.HasRuntimeEpisodeStarted)
            {
                return "runtime_episode_not_started";
            }

            if (_bootstrap.MatchManager == null)
            {
                return "match_manager_missing";
            }

            if (_bootstrap.MatchManager.Phase != MatchPhase.Running)
            {
                return "match_not_running";
            }

            if (!observationBuilderCalled)
            {
                return "observation_builder_missing";
            }

            return "runtime_services_not_ready";
        }

        private void AppendActualCollectObservationTrace(
            int callIndex,
            bool runtimeServicesReady,
            bool observationBuilderCalled,
            int valuesAddedToSensor,
            bool zeroFallbackUsed,
            string earlyExitReason,
            bool defensivePreReadyObservation,
            bool firstCallAfterEnable,
            bool firstCallAfterStart,
            bool firstCallAfterEpisodeBegin)
        {
            if (!Application.isPlaying)
            {
                return;
            }

            try
            {
                string path = ResolveProjectPath(_actualCollectTraceRelativePath);
                if (string.IsNullOrWhiteSpace(path))
                {
                    return;
                }

                BehaviorParameters behavior = GetComponent<BehaviorParameters>();
                string behaviorName = behavior != null ? behavior.BehaviorName : "missing";
                string behaviorType = behavior != null ? behavior.BehaviorType.ToString() : "missing";
                string matchState = _bootstrap != null && _bootstrap.MatchManager != null
                    ? _bootstrap.MatchManager.Phase.ToString()
                    : "missing";
                Academy academy = Academy.IsInitialized ? Academy.Instance : null;

                var sb = new StringBuilder(512);
                sb.Append('{');
                sb.Append("\"timestamp_utc\":\"").Append(DateTime.UtcNow.ToString("o")).Append("\",");
                sb.Append("\"call_index\":").Append(callIndex).Append(',');
                sb.Append("\"frame\":").Append(Time.frameCount).Append(',');
                sb.Append("\"fixed_time\":").Append(Time.fixedTime.ToString("R", System.Globalization.CultureInfo.InvariantCulture)).Append(',');
                sb.Append("\"academy_step\":").Append(academy != null ? academy.StepCount : -1L).Append(',');
                sb.Append("\"bootstrap_fixed_tick\":").Append(_bootstrap != null ? _bootstrap.BootstrapFixedTick : -1).Append(',');
                sb.Append("\"match_state\":\"").Append(matchState).Append("\",");
                sb.Append("\"runtime_services_ready\":").Append(runtimeServicesReady ? "true" : "false").Append(',');
                sb.Append("\"inference_runtime_ready_observed\":").Append(_inferenceRuntimeReadyObserved ? "true" : "false").Append(',');
                sb.Append("\"observation_builder_called\":").Append(observationBuilderCalled ? "true" : "false").Append(',');
                sb.Append("\"values_added_to_sensor\":").Append(valuesAddedToSensor).Append(',');
                sb.Append("\"expected_values\":").Append(ObservationContract.TotalFloats).Append(',');
                sb.Append("\"zero_fallback_used\":").Append(zeroFallbackUsed ? "true" : "false").Append(',');
                sb.Append("\"defensive_pre_ready_observation\":").Append(defensivePreReadyObservation ? "true" : "false").Append(',');
                sb.Append("\"first_call_after_enable\":").Append(firstCallAfterEnable ? "true" : "false").Append(',');
                sb.Append("\"first_call_after_start\":").Append(firstCallAfterStart ? "true" : "false").Append(',');
                sb.Append("\"first_call_after_on_episode_begin\":").Append(firstCallAfterEpisodeBegin ? "true" : "false").Append(',');
                sb.Append("\"early_exit_reason\":\"").Append(EscapeJson(earlyExitReason)).Append("\",");
                sb.Append("\"agent_gameobject_path\":\"").Append(EscapeJson(GetTransformPath(transform))).Append("\",");
                sb.Append("\"agent_instance_id\":").Append(GetInstanceID()).Append(',');
                sb.Append("\"behavior_name\":\"").Append(EscapeJson(behaviorName)).Append("\",");
                sb.Append("\"behavior_type\":\"").Append(EscapeJson(behaviorType)).Append("\"");
                sb.Append('}');

                File.AppendAllText(path, sb.ToString() + Environment.NewLine, Encoding.UTF8);
            }
            catch (Exception ex)
            {
                Debug.LogWarning("[Stage7B][8C.2] Failed to append actual collect trace: " + ex.Message);
            }
        }

        private void ClearActualCollectTraceFile()
        {
            try
            {
                string path = ResolveProjectPath(_actualCollectTraceRelativePath);
                if (string.IsNullOrWhiteSpace(path))
                {
                    return;
                }

                string directory = Path.GetDirectoryName(path);
                if (!string.IsNullOrWhiteSpace(directory))
                {
                    Directory.CreateDirectory(directory);
                }

                File.WriteAllText(path, string.Empty, Encoding.UTF8);
            }
            catch (Exception ex)
            {
                Debug.LogWarning("[Stage7B][8C.2] Failed to clear actual collect trace: " + ex.Message);
            }
        }

        private void AppendActionTrace(
            int decisionIndex,
            int selectedIndex,
            bool selectedIndexInRange,
            UnitActionType actionType,
            bool candidateIsEmpty,
            bool candidateIsNoOp,
            bool actionAdapterFallbackToNoOp,
            int candidateCount,
            bool runtimeApplyAttempted,
            bool runtimeApplyAccepted)
        {
            AppendJsonTraceLine(_actionTraceRelativePath, () =>
            {
                _actionTraceCallIndex++;
                Academy academy = Academy.IsInitialized ? Academy.Instance : null;
                string matchState = _bootstrap != null && _bootstrap.MatchManager != null
                    ? _bootstrap.MatchManager.Phase.ToString()
                    : "missing";
                int matchStep = _bootstrap != null && _bootstrap.MatchManager != null
                    ? _bootstrap.MatchManager.Step
                    : -1;

                var sb = new StringBuilder(640);
                sb.Append('{');
                sb.Append("\"timestamp_utc\":\"").Append(DateTime.UtcNow.ToString("o")).Append("\",");
                sb.Append("\"trace_index\":").Append(_actionTraceCallIndex).Append(',');
                sb.Append("\"decision_index\":").Append(decisionIndex).Append(',');
                sb.Append("\"frame\":").Append(Time.frameCount).Append(',');
                sb.Append("\"academy_step\":").Append(academy != null ? academy.StepCount : -1L).Append(',');
                sb.Append("\"match_step\":").Append(matchStep).Append(',');
                sb.Append("\"match_state\":\"").Append(EscapeJson(matchState)).Append("\",");
                sb.Append("\"candidate_count\":").Append(candidateCount).Append(',');
                sb.Append("\"selected_index\":").Append(selectedIndex).Append(',');
                sb.Append("\"selected_index_in_range\":").Append(selectedIndexInRange ? "true" : "false").Append(',');
                sb.Append("\"candidate_is_empty\":").Append(candidateIsEmpty ? "true" : "false").Append(',');
                sb.Append("\"candidate_is_noop\":").Append(candidateIsNoOp ? "true" : "false").Append(',');
                sb.Append("\"action_adapter_fallback_to_noop\":").Append(actionAdapterFallbackToNoOp ? "true" : "false").Append(',');
                sb.Append("\"selected_action_type\":\"").Append(actionType).Append("\",");
                sb.Append("\"runtime_apply_attempted\":").Append(runtimeApplyAttempted ? "true" : "false").Append(',');
                sb.Append("\"runtime_apply_accepted\":").Append(runtimeApplyAccepted ? "true" : "false");
                sb.Append('}');
                return sb.ToString();
            }, "action trace");
        }

        private void AppendRuntimeApplyTrace(
            int applyAttemptIndex,
            int selectedIndex,
            UnitActionType actionType,
            bool accepted,
            IReadOnlyList<string> rejectReasons,
            bool candidateIsEmpty,
            bool candidateIsNoOp)
        {
            AppendJsonTraceLine(_runtimeApplyTraceRelativePath, () =>
            {
                Academy academy = Academy.IsInitialized ? Academy.Instance : null;
                string primaryRejectReason = rejectReasons != null && rejectReasons.Count > 0
                    ? rejectReasons[0]
                    : "none";
                string matchState = _bootstrap != null && _bootstrap.MatchManager != null
                    ? _bootstrap.MatchManager.Phase.ToString()
                    : "missing";

                var sb = new StringBuilder(512);
                sb.Append('{');
                sb.Append("\"timestamp_utc\":\"").Append(DateTime.UtcNow.ToString("o")).Append("\",");
                sb.Append("\"apply_attempt_index\":").Append(applyAttemptIndex).Append(',');
                sb.Append("\"frame\":").Append(Time.frameCount).Append(',');
                sb.Append("\"academy_step\":").Append(academy != null ? academy.StepCount : -1L).Append(',');
                sb.Append("\"match_state\":\"").Append(EscapeJson(matchState)).Append("\",");
                sb.Append("\"selected_index\":").Append(selectedIndex).Append(',');
                sb.Append("\"action_type\":\"").Append(actionType).Append("\",");
                sb.Append("\"candidate_is_empty\":").Append(candidateIsEmpty ? "true" : "false").Append(',');
                sb.Append("\"candidate_is_noop\":").Append(candidateIsNoOp ? "true" : "false").Append(',');
                sb.Append("\"accepted\":").Append(accepted ? "true" : "false").Append(',');
                sb.Append("\"rejected\":").Append(accepted ? "false" : "true").Append(',');
                sb.Append("\"primary_reject_reason\":\"").Append(EscapeJson(primaryRejectReason)).Append("\"");
                sb.Append('}');
                return sb.ToString();
            }, "runtime apply trace");
        }

        private void AppendJsonTraceLine(string relativePath, Func<string> buildLine, string traceName)
        {
            if (!Application.isPlaying || string.IsNullOrWhiteSpace(relativePath) || buildLine == null)
            {
                return;
            }

            try
            {
                string path = ResolveProjectPath(relativePath);
                if (string.IsNullOrWhiteSpace(path))
                {
                    return;
                }

                string directory = Path.GetDirectoryName(path);
                if (!string.IsNullOrWhiteSpace(directory))
                {
                    Directory.CreateDirectory(directory);
                }

                string line = buildLine();
                if (!string.IsNullOrWhiteSpace(line))
                {
                    File.AppendAllText(path, line + Environment.NewLine, Encoding.UTF8);
                }
            }
            catch (Exception ex)
            {
                Debug.LogWarning("[Stage7B] Failed to append " + traceName + ": " + ex.Message);
            }
        }

        private void ClearTraceFile(string relativePath)
        {
            if (string.IsNullOrWhiteSpace(relativePath))
            {
                return;
            }

            try
            {
                string path = ResolveProjectPath(relativePath);
                if (string.IsNullOrWhiteSpace(path))
                {
                    return;
                }

                string directory = Path.GetDirectoryName(path);
                if (!string.IsNullOrWhiteSpace(directory))
                {
                    Directory.CreateDirectory(directory);
                }

                File.WriteAllText(path, string.Empty, Encoding.UTF8);
            }
            catch (Exception ex)
            {
                Debug.LogWarning("[Stage7B] Failed to clear trace file: " + ex.Message);
            }
        }

        private static string ResolveProjectPath(string relativePath)
        {
            if (string.IsNullOrWhiteSpace(relativePath))
            {
                return string.Empty;
            }

            string normalized = relativePath.Replace('\\', '/');
            if (Path.IsPathRooted(normalized))
            {
                return normalized;
            }

            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            return Path.Combine(projectRoot, normalized.Replace('/', Path.DirectorySeparatorChar));
        }

        private static string GetTransformPath(Transform value)
        {
            if (value == null)
            {
                return "missing";
            }

            string path = value.name;
            Transform current = value.parent;
            while (current != null)
            {
                path = current.name + "/" + path;
                current = current.parent;
            }

            return path;
        }

        private static string EscapeJson(string value)
        {
            if (string.IsNullOrEmpty(value))
            {
                return string.Empty;
            }

            return value
                .Replace("\\", "\\\\")
                .Replace("\"", "\\\"")
                .Replace("\r", "\\r")
                .Replace("\n", "\\n");
        }

        private bool ShouldUseManualFixedUpdateDecisionRequests()
        {
            return _currentDecisionSource == DecisionSourceManualFixedUpdate
                   || _currentDecisionSource == DecisionSourceDecisionRequesterAndManualDebug
                   || _currentDecisionSource == DecisionSourceDecisionRequesterWatchdogManualFallback;
        }

        private void UpdateDecisionRequesterWatchdog()
        {
            if (!_enableDecisionRequesterWatchdogFallback
                || _decisionRequesterWatchdogFallbackActive
                || _currentDecisionSource != DecisionSourceDecisionRequester)
            {
                return;
            }

            if (_bootstrap == null || _bootstrap.MatchManager == null || _bootstrap.MatchManager.Phase != MatchPhase.Running)
            {
                _fixedUpdatesWithoutDecisionWhileUsingDecisionRequester = 0;
                return;
            }

            _fixedUpdatesWithoutDecisionWhileUsingDecisionRequester++;
            if (_fixedUpdatesWithoutDecisionWhileUsingDecisionRequester < DecisionRequesterWatchdogFixedUpdateThreshold)
            {
                return;
            }

            _decisionRequesterWatchdogFallbackActive = true;
            _fixedUpdatesWithoutDecisionWhileUsingDecisionRequester = 0;
            ApplyDecisionSourcePolicy();
            Debug.LogWarning("[Stage7B] DecisionRequester stalled before producing actions. Switched to manual FixedUpdate decision requests via watchdog fallback.");
        }

        private void BuildCandidates()
        {
            _candidateBuildCallCount++;
            if (_candidateBuilder == null)
            {
                return;
            }

            _currentCandidates = _candidateBuilder.Build(_playerPerspective);
            if (_currentCandidates != null && _currentCandidates.CandidateCount > 0)
            {
                _candidateBuilderSuccessCount++;
            }
        }

        private void RecordSelectedActionType(UnitActionType actionType)
        {
            switch (actionType)
            {
                case UnitActionType.NoOp:
                    _selectedNoOpActionCount++;
                    break;
                case UnitActionType.Move:
                    _selectedMoveActionCount++;
                    break;
                case UnitActionType.Harvest:
                    _selectedHarvestActionCount++;
                    break;
                case UnitActionType.Return:
                    _selectedReturnActionCount++;
                    break;
                case UnitActionType.Produce:
                    _selectedProduceActionCount++;
                    break;
                case UnitActionType.Attack:
                    _selectedAttackActionCount++;
                    break;
            }
        }

        private void RecordRuntimeAttemptedActionType(UnitActionType actionType)
        {
            switch (actionType)
            {
                case UnitActionType.NoOp:
                    _runtimeApplyAttemptedNoOpCount++;
                    break;
                case UnitActionType.Move:
                    _runtimeApplyAttemptedMoveCount++;
                    break;
                case UnitActionType.Harvest:
                    _runtimeApplyAttemptedHarvestCount++;
                    break;
                case UnitActionType.Return:
                    _runtimeApplyAttemptedReturnCount++;
                    break;
                case UnitActionType.Produce:
                    _runtimeApplyAttemptedProduceCount++;
                    break;
                case UnitActionType.Attack:
                    _runtimeApplyAttemptedAttackCount++;
                    break;
            }
        }

        private void RecordRuntimeAcceptedActionType(UnitActionType actionType)
        {
            switch (actionType)
            {
                case UnitActionType.NoOp:
                    _runtimeApplyAcceptedNoOpCount++;
                    break;
                case UnitActionType.Move:
                    _runtimeApplyAcceptedMoveCount++;
                    break;
                case UnitActionType.Harvest:
                    _runtimeApplyAcceptedHarvestCount++;
                    break;
                case UnitActionType.Return:
                    _runtimeApplyAcceptedReturnCount++;
                    break;
                case UnitActionType.Produce:
                    _runtimeApplyAcceptedProduceCount++;
                    break;
                case UnitActionType.Attack:
                    _runtimeApplyAcceptedAttackCount++;
                    break;
            }
        }

        private void RecordAcceptedCommandPosition()
        {
            Academy academy = Academy.IsInitialized ? Academy.Instance : null;
            long academyStep = academy != null ? academy.StepCount : -1L;

            if (_firstAcceptedCommandFrame < 0)
            {
                _firstAcceptedCommandFrame = Time.frameCount;
                _firstAcceptedCommandAcademyStep = academyStep;
            }

            _lastAcceptedCommandFrame = Time.frameCount;
            _lastAcceptedCommandAcademyStep = academyStep;
        }

        private void RecordRuntimeRejectReasons(IReadOnlyList<string> reasons)
        {
            if (reasons == null)
            {
                return;
            }

            for (int i = 0; i < reasons.Count; i++)
            {
                string reason = string.IsNullOrWhiteSpace(reasons[i]) ? "unknown" : reasons[i];
                if (_runtimeRejectReasonHistogram.TryGetValue(reason, out int count))
                {
                    _runtimeRejectReasonHistogram[reason] = count + 1;
                }
                else
                {
                    _runtimeRejectReasonHistogram.Add(reason, 1);
                }
            }
        }

        private int SelectHeuristicCandidateIndex()
        {
            int index = FindPreferredCandidate(UnitActionType.Return, requireCarryingWorker: true);
            if (index > 0) return index;

            index = FindPreferredCandidate(UnitActionType.Harvest, requireCarryingWorker: false);
            if (index > 0) return index;

            index = FindPreferredCandidate(UnitActionType.Produce, requireCarryingWorker: false);
            if (index > 0) return index;

            index = FindPreferredCandidate(UnitActionType.Attack, requireCarryingWorker: false);
            if (index > 0) return index;

            index = FindPreferredCandidate(UnitActionType.Move, requireCarryingWorker: false);
            return index > 0 ? index : MlAgentsCandidateActionList.NoOpCandidateIndex;
        }

        private int FindPreferredCandidate(UnitActionType actionType, bool requireCarryingWorker)
        {
            if (_currentCandidates == null)
            {
                return -1;
            }

            for (int i = 0; i < _currentCandidates.AvailableCandidates.Count; i++)
            {
                MlAgentsCandidateAction candidate = _currentCandidates.AvailableCandidates[i];
                if (candidate.IsNoOp || candidate.Action.ActionType != actionType)
                {
                    continue;
                }

                if (requireCarryingWorker)
                {
                    UnitRuntime actor = _bootstrap?.GridManager != null
                        ? _bootstrap.GridManager.GetOccupant(candidate.Action.ActorPosition)
                        : null;
                    if (actor == null || actor.Type != UnitType.Worker || actor.CarriedResources <= 0)
                    {
                        continue;
                    }
                }

                return candidate.CandidateIndex;
            }

            return -1;
        }

        private void ValidateObservation(float[] observation)
        {
            if (observation == null || observation.Length != ObservationContract.TotalFloats)
            {
                Debug.LogError(
                    $"[Stage7B] Observation length mismatch: {observation?.Length ?? 0} != {ObservationContract.TotalFloats}");
                return;
            }

            int badCount = 0;
            for (int i = 0; i < observation.Length; i++)
            {
                float value = observation[i];
                if (float.IsNaN(value) || float.IsInfinity(value) || value < 0f || value > 1f)
                {
                    badCount++;
                }
            }

            if (badCount > 0)
            {
                Debug.LogError($"[Stage7B] Observation contains {badCount} NaN/Inf/out-of-range values.");
            }
        }
    }
}
