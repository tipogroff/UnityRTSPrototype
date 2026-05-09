using RTS.Core;
using RTS.Gameplay;
using RTS.ML;
using RTS.MLAgents.Stage7B.CandidateActions;
using RTS.MLAgents.Stage7B.Diagnostics;
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
        [Header("Stage7B")]
        [SerializeField] private Owner _playerPerspective = Owner.Player1;
        [SerializeField] private bool _autoResolveBootstrap = true;
        [SerializeField] private bool _requestDecisionInFixedUpdate = true;
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

        public Stage7BActionTrace Trace { get; } = new Stage7BActionTrace();
        public MlAgentsCandidateActionList CurrentCandidates => _currentCandidates;

        protected override void OnEnable()
        {
            ConfigureBehaviorParameters();
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
            Trace.RecordReset(_bootstrap != null && _bootstrap.DuplicateSpawnDetected);
            _currentCandidates = null;
        }

        private void FixedUpdate()
        {
            if (!_requestDecisionInFixedUpdate)
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
            _bootstrap?.EnsureReadyForDecision();
            BuildCandidates();

            RuntimeRewardCollector collector = _rewardCollector;
            RewardRuntimeSnapshot pre = collector != null
                ? collector.CaptureSnapshot(_bootstrap.MatchManager, _bootstrap.UnitRegistry)
                : default;

            int selectedIndex = actions.DiscreteActions.Length > 0 ? actions.DiscreteActions[0] : 0;
            _episodeDecisionCount++;
            AgentAction selectedAction = _actionAdapter.Resolve(_currentCandidates, selectedIndex, out MlAgentsCandidateAction candidate);
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
                _bootstrap.ScriptedOpponentAdapter.ExecuteDecisionStep();
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
                    EndEpisode();
                }
            }
            else if (!stillRunning)
            {
                Trace.RecordTerminal("runtime-ended");
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
