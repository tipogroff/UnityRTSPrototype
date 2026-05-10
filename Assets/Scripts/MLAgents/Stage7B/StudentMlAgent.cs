using RTS.Core;
using RTS.Gameplay;
using RTS.ML;
using RTS.MLAgents.Stage7B.CandidateActions;
using RTS.MLAgents.Stage7B.Diagnostics;
using RTS.MLAgents.Stage7B.TeacherReplay;
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

        public Stage7BActionTrace Trace { get; } = new Stage7BActionTrace();
        public MlAgentsCandidateActionList CurrentCandidates => _currentCandidates;
        public string CurrentDecisionSource => _currentDecisionSource;

        /// <summary>
        /// Stage7B-7: Set by Stage7BTeacherReplayDemoOrchestrator to enable teacher-replay-demo
        /// mode.  When non-null and active, Heuristic() returns the orchestrator's queued
        /// candidate index and OnActionReceived() skips reward / episode-end evaluation.
        /// </summary>
        internal Stage7BTeacherReplayDemoOrchestrator TeacherReplayOrchestrator { get; set; }

        protected override void OnEnable()
        {
            ConfigureBehaviorParameters();
            ApplyDecisionSourcePolicy();
            base.OnEnable();
        }

        public void Configure(MlAgentsTrainingBootstrap bootstrap, Owner playerPerspective)
        {
            _bootstrap = bootstrap;
            _playerPerspective = playerPerspective;
            ResolveDependencies();
        }

        public override void Initialize()
        {
            ResolveDependencies();
            ConfigureBehaviorParameters();
            ApplyDecisionSourcePolicy();
        }

        public override void OnEpisodeBegin()
        {
            ResolveDependencies();
            _bootstrap?.StartNewEpisode();
            _observationBuilder = null;
            _candidateBuilder = null;
            _actionApplier = null;
            ResolveDependencies();
            _rewardCollector?.ResetEpisode();
            _episodeDecisionCount = 0;
            _fixedUpdatesWithoutDecisionWhileUsingDecisionRequester = 0;
            Trace.RecordReset(_bootstrap != null && _bootstrap.DuplicateSpawnDetected);
            _currentCandidates = null;
        }

        private void FixedUpdate()
        {
            ApplyDecisionSourcePolicy();
            UpdateDecisionRequesterWatchdog();

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
                RequestDecision();
            }
        }

        public override void CollectObservations(VectorSensor sensor)
        {
            ResolveDependencies();
            float[] observation = _observationBuilder != null
                ? _observationBuilder.BuildObservation(_playerPerspective, ObservationMode.UnityMvpTransfer)
                : new float[ObservationContract.TotalFloats];

            ValidateObservation(observation);
            Trace.RecordObservation(observation);
            sensor.AddObservation(observation);
        }

        public override void WriteDiscreteActionMask(IDiscreteActionMask actionMask)
        {
            ResolveDependencies();
            BuildCandidates();
            _maskAdapter.WriteDiscreteActionMask(actionMask, _currentCandidates);
            Trace.RecordMask(
                _currentCandidates != null ? _currentCandidates.CandidateCount : 0,
                _maskAdapter.LastMaskedEmptySlots,
                _currentCandidates != null ? _currentCandidates.OverflowCount : 0);
        }

        public override void OnActionReceived(ActionBuffers actions)
        {
            ResolveDependencies();
            ApplyDecisionSourcePolicy();
            _bootstrap?.EnsureReadyForDecision();
            BuildCandidates();

            RuntimeRewardCollector collector = _rewardCollector;
            RewardRuntimeSnapshot pre = collector != null
                ? collector.CaptureSnapshot(_bootstrap.MatchManager, _bootstrap.UnitRegistry)
                : default;

            int selectedIndex = actions.DiscreteActions.Length > 0 ? actions.DiscreteActions[0] : 0;
            _episodeDecisionCount++;
            _fixedUpdatesWithoutDecisionWhileUsingDecisionRequester = 0;
            _bootstrap?.ScriptedOpponentPacing?.RecordStudentActionAttempt();
            AgentAction selectedAction = _actionAdapter.Resolve(_currentCandidates, selectedIndex, out MlAgentsCandidateAction candidate);

            // Stage7B-7: teacher-replay-demo mode — apply action, notify orchestrator, skip
            // reward evaluation and episode-end so the recording loop is not interrupted.
            Stage7BTeacherReplayDemoOrchestrator replayOrchestrator = TeacherReplayOrchestrator;
            if (replayOrchestrator != null && replayOrchestrator.IsActive)
            {
                bool demoAccepted = false;
                if (_actionApplier != null)
                {
                    _actionApplier.ResetDiagnostics();
                    demoAccepted = _actionApplier.ApplyAction(
                        selectedAction, _playerPerspective, _currentCandidates?.SourceMask,
                        "stage7b-demo-replay");
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

                _currentCandidates = null;
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
                _actionApplier.ResetDiagnostics();
                accepted = _actionApplier.ApplyAction(
                    selectedAction,
                    _playerPerspective,
                    _currentCandidates?.SourceMask,
                    "stage7b-candidate-action-index");

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
                    _bootstrap?.ScriptedOpponentPacing?.FinalizeEpisodeAndWriteReport(terminalReason);
                    EndEpisode();
                }
            }
            else if (!stillRunning)
            {
                Trace.RecordTerminal("runtime-ended");
                _bootstrap?.ScriptedOpponentPacing?.FinalizeEpisodeAndWriteReport("runtime-ended");
                EndEpisode();
            }

            _currentCandidates = null;
        }

        public override void Heuristic(in ActionBuffers actionsOut)
        {
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
                    return;
                }
                // No pending index this tick — emit NoOp so we don't record unintended actions.
                discrete[0] = MlAgentsCandidateActionList.NoOpCandidateIndex;
                return;
            }

            discrete[0] = SelectHeuristicCandidateIndex();
        }

        private void ResolveDependencies()
        {
            if (_bootstrap == null && _autoResolveBootstrap)
            {
                _bootstrap = FindFirstObjectByType<MlAgentsTrainingBootstrap>();
                if (_bootstrap == null)
                {
                    _bootstrap = new GameObject("Stage7B_MLAgentsTrainingBootstrap").AddComponent<MlAgentsTrainingBootstrap>();
                }
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
            if (_candidateBuilder == null)
            {
                return;
            }

            _currentCandidates = _candidateBuilder.Build(_playerPerspective);
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
