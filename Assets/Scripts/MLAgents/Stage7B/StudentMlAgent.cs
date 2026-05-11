using RTS.Core;
using RTS.Gameplay;
using RTS.ML;
using RTS.MLAgents.Stage7B.CandidateActions;
using RTS.MLAgents.Stage7B.Diagnostics;
using RTS.MLAgents.Stage7B.TeacherReplay;
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
        private readonly Dictionary<string, int> _runtimeRejectReasonHistogram = new Dictionary<string, int>();
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
            _collectObservedSinceLastStart = false;
            ClearActualCollectTraceFile();
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

            if (TryActivateInferenceDecisionKick())
            {
                return;
            }

            if (TryRequestTrainerControlledKickDecision())
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
                RequestDecision();
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
            RequestDecision();
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
            _bootstrap?.EnsureReadyForDecision();
            BuildCandidates();

            RuntimeRewardCollector collector = _rewardCollector;
            RewardRuntimeSnapshot pre = collector != null
                ? collector.CaptureSnapshot(_bootstrap.MatchManager, _bootstrap.UnitRegistry)
                : default;

            int selectedIndex = actions.DiscreteActions.Length > 0 ? actions.DiscreteActions[0] : 0;
            _lastActionCandidateIndex = selectedIndex;
            _lastCandidateIndexInRange = selectedIndex >= 0 && selectedIndex < MlAgentsCandidateActionList.BranchSize;
            _episodeDecisionCount++;
            _fixedUpdatesWithoutDecisionWhileUsingDecisionRequester = 0;
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
                    && _bootstrap.MatchManager.Phase == MatchPhase.Running)
                {
                    _bootstrap.MatchManager.StepMatch();
                }

                string demoSummary = "actor=" + selectedAction.ActorPosition
                    + ",type=" + selectedAction.ActionType
                    + ",dir=" + selectedAction.Direction;
                replayOrchestrator.NotifyActionApplied(demoAccepted, selectedIndex, demoSummary);
                _lastActionAccepted = demoAccepted;

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
            }

            if (_bootstrap != null
                && _bootstrap.StepScriptedOpponent
                && _bootstrap.ScriptedOpponentAdapter != null
                && _bootstrap.MatchManager != null
                && _bootstrap.MatchManager.Phase == MatchPhase.Running)
            {
                bool shouldRunScriptedOpponent = _bootstrap.ScriptedOpponentPacing == null
                    || _bootstrap.ScriptedOpponentPacing.ShouldExecuteBotDecisionStep(Time.time);
                if (shouldRunScriptedOpponent)
                {
                    (int acceptedTotal, int rejectedTotal) = _bootstrap.ScriptedOpponentAdapter.ExecuteDecisionStepWithCounts();
                    _bootstrap.ScriptedOpponentPacing?.RecordBotDecisionOutcome(acceptedTotal, rejectedTotal);
                }
            }

            bool stillRunning = _bootstrap != null
                                && _bootstrap.MatchManager != null
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
                if (!requester.enabled)
                {
                    requester.enabled = true;
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

            DecisionRequester requester = GetComponent<DecisionRequester>();
            if (requester == null)
            {
                return false;
            }

            ResolveDependencies();
            bool ready = AreInferenceRuntimeServicesReady();
            if (!ready)
            {
                if (requester.enabled)
                {
                    requester.enabled = false;
                }

                return false;
            }

            if (!requester.enabled)
            {
                requester.enabled = true;
            }

            if (_inferenceDecisionRequesterActivated)
            {
                return false;
            }

            _inferenceDecisionRequesterActivated = true;
            _inferenceKickDecisionRequestCount++;
            Stage7BResetTimeoutTrace.Record("StudentMlAgent.RequestDecision.inference_kick", this, _bootstrap);
            RequestDecision();
            return true;
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
