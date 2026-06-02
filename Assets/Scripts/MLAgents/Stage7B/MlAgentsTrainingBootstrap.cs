using System.Collections.Generic;
using System.Reflection;
using RTS.Core;
using RTS.Gameplay;
using RTS.ML;
using RTS.MLAgents.Stage7B.Diagnostics;
using Unity.MLAgents;
using Unity.MLAgents.Actuators;
using Unity.MLAgents.Policies;
using UnityEngine;

#if UNITY_EDITOR
using UnityEditor;
#endif

namespace RTS.MLAgents.Stage7B
{
    public enum Stage7BRuntimeMode
    {
        HeuristicDryRun = 0,
        TeacherReplayDemoRecording = 1,
        TrainerControlled = 2,
        InferenceOnly = 3,
    }

    [DisallowMultipleComponent]
    public sealed class MlAgentsTrainingBootstrap : MonoBehaviour
    {
        [Header("Stage7B")]
        [SerializeField] private Owner _studentPlayer = Owner.Player1;
        [SerializeField] private Owner _scriptedOpponent = Owner.Player2;
        [SerializeField] private bool _autoConfigureMlAgents = true;
        [SerializeField] private bool _stepScriptedOpponent = true;
        [SerializeField] private bool _ensureWeek6StaticHarvestLayout = true;
        [SerializeField] private GameConfig _fallbackConfig;
        [SerializeField] private int _stage7BMatchMaxSteps = 6000;
        [SerializeField] private BootstrapScenarioPreset _scenarioPreset = BootstrapScenarioPreset.Week6StudentMicroRtsMirror24x24;
        [SerializeField] private int _startResources = 60;
        [SerializeField] private Stage7BRuntimeMode _stage7BRuntimeMode = Stage7BRuntimeMode.HeuristicDryRun;
        [SerializeField] private bool _forceTrainerControlledMode;
        [SerializeField] private ScriptedOpponentTacticProfile _scriptedOpponentTacticProfile = ScriptedOpponentTacticProfile.Legacy;

        [Header("Demo/Interactive Mode")]
        [SerializeField] private bool _autoStartEpisodeOnStart = true;

        public GridManager GridManager { get; private set; }
        public UnitRegistry UnitRegistry { get; private set; }
        public ResourceManager ResourceManager { get; private set; }
        public MatchManager MatchManager { get; private set; }
        public MatchBootstrap MatchBootstrap { get; private set; }
        public HeuristicPolicyAdapter ScriptedOpponentAdapter { get; private set; }
        public StudentMlAgent StudentAgent { get; private set; }
        public Week7ScriptedOpponentPacing ScriptedOpponentPacing { get; private set; }
        public bool StepScriptedOpponent => _stepScriptedOpponent;
        public Owner StudentPlayer => _studentPlayer;
        public Owner ScriptedOpponent => _scriptedOpponent;
        public int ConfiguredStartResources => Mathf.Max(0, _startResources);
        public bool DuplicateSpawnDetected { get; private set; }
        public bool HasRuntimeEpisodeStarted => _hasRuntimeEpisodeStarted;
        public bool IsStartingEpisode => _isStartingEpisode;
        public int StartNewEpisodeInvocationCount => _startNewEpisodeInvocationCount;
        public int StartNewEpisodeSkippedReentrantCount => _startNewEpisodeSkippedReentrantCount;
        public string LastStartNewEpisodeReason => _lastStartNewEpisodeReason;
        public string LastStartNewEpisodeCaller => _lastStartNewEpisodeCaller;
        public string LastStartNewEpisodePath => _lastStartNewEpisodePath;
        public Stage7BRuntimeMode RuntimeMode => _forceTrainerControlledMode
            ? Stage7BRuntimeMode.TrainerControlled
            : _stage7BRuntimeMode;

        private bool _isStartingEpisode;
        private bool _hasRuntimeEpisodeStarted;
        private int _startNewEpisodeInvocationCount;
        private int _startNewEpisodeSkippedReentrantCount;
        private string _lastStartNewEpisodeReason = "none";
        private string _lastStartNewEpisodeCaller = "none";
        private string _lastStartNewEpisodePath = "none";
        private bool _deferredStudentEnableForInference;
        private int _bootstrapFixedTick;
        private int _inferenceReadyAfterFixedTick;
        private bool _inferenceRuntimeReady;
        private GameConfig _runtimeConfigOverride;

        private void Awake()
        {
            Stage7BResetTimeoutTrace.ResetSession();
            Stage7BResetTimeoutTrace.Record("MlAgentsTrainingBootstrap.Awake.enter", StudentAgent, this);
            ResolveRuntimeObjects();
            EnsureWeek6StaticHarvestLayout();
            ConfigureMatchBootstrap();
            EnsureAcademyAutomaticStepping();
            EnsureMlAgentObject();

            if (RuntimeMode == Stage7BRuntimeMode.InferenceOnly
                && Application.isPlaying
                && StudentAgent != null
                && StudentAgent.enabled)
            {
                StudentAgent.enabled = false;
                _deferredStudentEnableForInference = true;
            }

            Stage7BResetTimeoutTrace.Record("MlAgentsTrainingBootstrap.Awake.exit", StudentAgent, this);
        }

        private void Start()
        {
            Stage7BResetTimeoutTrace.Record("MlAgentsTrainingBootstrap.Start.enter", StudentAgent, this);
            if (RuntimeMode == Stage7BRuntimeMode.TrainerControlled)
            {
                PrepareRuntimeForTrainerControlledStart();
            }
            else if (_autoStartEpisodeOnStart)
            {
                StartNewEpisode("bootstrap_start", nameof(MlAgentsTrainingBootstrap) + "." + nameof(Start));
            }

            ApplyRuntimeModeConfiguration();

            if (_deferredStudentEnableForInference
                && StudentAgent != null
                && !StudentAgent.enabled)
            {
                StudentAgent.enabled = true;
                _deferredStudentEnableForInference = false;
            }

            Stage7BResetTimeoutTrace.Record("MlAgentsTrainingBootstrap.Start.exit", StudentAgent, this);
        }

        private void FixedUpdate()
        {
            _bootstrapFixedTick++;
            UpdateInferenceRuntimeReadyState();
        }

        private void OnDestroy()
        {
            CleanupAcademyFixedUpdateStepper();
        }

        public void StartNewEpisode()
        {
            StartNewEpisode("legacy_start_new_episode", "MlAgentsTrainingBootstrap.StartNewEpisode");
        }

        public bool StartNewEpisode(string reason, string caller)
        {
            _startNewEpisodeInvocationCount++;
            _lastStartNewEpisodeReason = string.IsNullOrWhiteSpace(reason) ? "unspecified" : reason;
            _lastStartNewEpisodeCaller = string.IsNullOrWhiteSpace(caller) ? "unspecified" : caller;
            Stage7BResetTimeoutTrace.Record("MlAgentsTrainingBootstrap.StartNewEpisode.enter", StudentAgent, this);

            if (_isStartingEpisode)
            {
                _startNewEpisodeSkippedReentrantCount++;
                _lastStartNewEpisodePath = "skipped_reentrant";
                Stage7BResetTimeoutTrace.Record("MlAgentsTrainingBootstrap.StartNewEpisode.skipped_reentrant", StudentAgent, this);
                return false;
            }

            _isStartingEpisode = true;
            _lastStartNewEpisodePath = RuntimeMode == Stage7BRuntimeMode.TrainerControlled
                ? "trainer_controlled_guarded_full_reset"
                : "runtime_full_reset";

            try
            {
                ResolveRuntimeObjects();
                EnsureWeek6StaticHarvestLayout();
                ConfigureMatchBootstrap();
                EnsureAcademyAutomaticStepping();
                Stage7BResetTimeoutTrace.Record("MlAgentsTrainingBootstrap.CleanupRuntimeObjects.enter", StudentAgent, this);
                CleanupRuntimeObjects();
                Stage7BResetTimeoutTrace.Record("MlAgentsTrainingBootstrap.CleanupRuntimeObjects.exit", StudentAgent, this);
                Stage7BResetTimeoutTrace.Record("MlAgentsTrainingBootstrap.MatchBootstrap.Setup.enter", StudentAgent, this);
                MatchBootstrap.Setup();
                Stage7BResetTimeoutTrace.Record("MlAgentsTrainingBootstrap.MatchBootstrap.Setup.exit", StudentAgent, this);
                ConfigureScriptedOpponent();
                DuplicateSpawnDetected = DetectDuplicateSpawn();
                ScriptedOpponentPacing?.ResetForEpisode(DuplicateSpawnDetected);
                _hasRuntimeEpisodeStarted = true;
                ArmInferenceRuntimeReadyGateAfterEpisodeStart();
                Stage7BResetTimeoutTrace.Record("MlAgentsTrainingBootstrap.StartNewEpisode.exit", StudentAgent, this);
                return true;
            }
            finally
            {
                _isStartingEpisode = false;
            }
        }

        public bool StartNewEpisodeForAgentReset()
        {
            return StartNewEpisode("mlagents_on_episode_begin", "StudentMlAgent.OnEpisodeBegin");
        }

        public void EnsureReadyForDecision()
        {
            Stage7BResetTimeoutTrace.Record("MlAgentsTrainingBootstrap.EnsureReadyForDecision.enter", StudentAgent, this);
            ResolveRuntimeObjects();
            if (MatchManager == null || MatchManager.Phase != MatchPhase.Running)
            {
                Stage7BResetTimeoutTrace.Record("MlAgentsTrainingBootstrap.EnsureReadyForDecision.recover", StudentAgent, this);
                StartNewEpisode("ensure_ready_for_decision_recover", "MlAgentsTrainingBootstrap.EnsureReadyForDecision");
            }
            Stage7BResetTimeoutTrace.Record("MlAgentsTrainingBootstrap.EnsureReadyForDecision.exit", StudentAgent, this);
        }

        private void PrepareRuntimeForTrainerControlledStart()
        {
            _lastStartNewEpisodePath = "trainer_controlled_start_prepare_only";
            Stage7BResetTimeoutTrace.Record("MlAgentsTrainingBootstrap.TrainerControlledStart.prepare_enter", StudentAgent, this);
            ResolveRuntimeObjects();
            EnsureWeek6StaticHarvestLayout();
            ConfigureMatchBootstrap();
            EnsureAcademyAutomaticStepping();
            ApplyRuntimeModeConfiguration();
            Stage7BResetTimeoutTrace.Record("MlAgentsTrainingBootstrap.TrainerControlledStart.prepare_exit", StudentAgent, this);
        }

        private void ResolveRuntimeObjects()
        {
            GridManager = EnsureSceneComponent<GridManager>("GridManager");
            UnitRegistry = EnsureSceneComponent<UnitRegistry>("UnitRegistry");
            ResourceManager = EnsureSceneComponent<ResourceManager>("ResourceManager");
            MatchManager = EnsureSceneComponent<MatchManager>("MatchManager");
            MatchBootstrap = EnsureSceneComponent<MatchBootstrap>("MatchBootstrap");
            EnsureSceneComponent<VictoryResolver>("VictoryResolver");
            ScriptedOpponentAdapter = EnsureSceneComponent<HeuristicPolicyAdapter>("Stage7B_ScriptedOpponent");
            ScriptedOpponentPacing = EnsureSceneComponent<Week7ScriptedOpponentPacing>("Stage7B_ScriptedOpponentPacing");
            EnsureSceneComponent<Stage7BHeuristicDryRunLogger>("Stage7B_HeuristicDryRunLogger");
            EnsureSceneComponent<Stage7BRuntimeContractDumper>("Stage7B_RuntimeContractDumper");
            EnsureSceneComponent<Stage7BTrainingFlowDiagnostics>("Stage7B_TrainingFlowDiagnostics");
        }

        private void EnsureMlAgentObject()
        {
            StudentAgent = FindFirstObjectByType<StudentMlAgent>();
            if (StudentAgent == null)
            {
                var host = new GameObject("Stage7B_StudentMlAgent");
                StudentAgent = host.AddComponent<StudentMlAgent>();
            }

            RemoveUnexpectedAgentComponents(StudentAgent.gameObject);

            StudentAgent.Configure(this, _studentPlayer);

            if (!_autoConfigureMlAgents)
            {
                ApplyRuntimeModeConfiguration();
                return;
            }

            BehaviorParameters behavior = StudentAgent.GetComponent<BehaviorParameters>();
            if (behavior != null)
            {
                behavior.BehaviorName = "Stage7B_RTS_Student";
                behavior.BehaviorType = ResolveBehaviorType(RuntimeMode);
                behavior.TeamId = _studentPlayer == Owner.Player1 ? 0 : 1;
                behavior.BrainParameters.VectorObservationSize = ObservationContract.TotalFloats;
                behavior.BrainParameters.NumStackedVectorObservations = 1;
                behavior.BrainParameters.ActionSpec = ActionSpec.MakeDiscrete(
                    RTS.MLAgents.Stage7B.CandidateActions.MlAgentsCandidateActionList.BranchSize);
            }

            DecisionRequester requester = StudentAgent.GetComponent<DecisionRequester>();
            if (requester != null)
            {
                requester.DecisionPeriod = 1;
                requester.DecisionStep = 0;
                requester.TakeActionsBetweenDecisions = false;
                requester.enabled = ShouldEnableDecisionRequester(RuntimeMode, _hasRuntimeEpisodeStarted);
            }

            StudentAgent.MaxStep = ResolveConfiguredMatchMaxSteps();
            ApplyRuntimeModeConfiguration();

            if (Application.isPlaying && StudentAgent.isActiveAndEnabled)
            {
                StudentAgent.enabled = false;
                StudentAgent.enabled = true;
            }
        }

        private static void EnsureAcademyAutomaticStepping()
        {
            if (!Academy.IsInitialized)
            {
                return;
            }

            Academy academy = Academy.Instance;
            if (academy != null && !academy.AutomaticSteppingEnabled)
            {
                academy.AutomaticSteppingEnabled = true;
            }
        }

        private static void CleanupAcademyFixedUpdateStepper()
        {
            GameObject stepper = GameObject.Find("AcademyFixedUpdateStepper");
            if (stepper != null)
            {
                Destroy(stepper);
            }
        }

        private void ApplyRuntimeModeConfiguration()
        {
            if (StudentAgent == null)
            {
                return;
            }

            BehaviorParameters behavior = StudentAgent.GetComponent<BehaviorParameters>();
            DecisionRequester requester = StudentAgent.GetComponent<DecisionRequester>();
            Stage7BRuntimeMode mode = RuntimeMode;

            if (behavior != null)
            {
                behavior.BehaviorName = "Stage7B_RTS_Student";
                behavior.BehaviorType = ResolveBehaviorType(mode);
            }

            if (requester != null)
            {
                requester.DecisionPeriod = 1;
                requester.DecisionStep = 0;
                requester.TakeActionsBetweenDecisions = false;
                requester.enabled = ShouldEnableDecisionRequester(mode, _hasRuntimeEpisodeStarted);
            }

            if (mode == Stage7BRuntimeMode.TrainerControlled || mode == Stage7BRuntimeMode.InferenceOnly)
            {
                StudentAgent.ConfigureForTrainerControlledMode();
                DisableTeacherReplayOrchestrators();
            }
        }

        private static BehaviorType ResolveBehaviorType(Stage7BRuntimeMode mode)
        {
            return mode switch
            {
                Stage7BRuntimeMode.TrainerControlled => BehaviorType.Default,
                Stage7BRuntimeMode.InferenceOnly => BehaviorType.InferenceOnly,
                _ => BehaviorType.HeuristicOnly,
            };
        }

        private static bool ShouldEnableDecisionRequester(Stage7BRuntimeMode mode, bool runtimeEpisodeStarted)
        {
            if (mode == Stage7BRuntimeMode.TrainerControlled)
            {
                return true;
            }

            if (mode == Stage7BRuntimeMode.InferenceOnly)
            {
                return false;
            }

            return false;
        }

        public bool InferenceRuntimeReady => RuntimeMode != Stage7BRuntimeMode.InferenceOnly || _inferenceRuntimeReady;

        public int BootstrapFixedTick => _bootstrapFixedTick;

        private void ArmInferenceRuntimeReadyGateAfterEpisodeStart()
        {
            if (RuntimeMode != Stage7BRuntimeMode.InferenceOnly)
            {
                _inferenceRuntimeReady = _hasRuntimeEpisodeStarted
                    && MatchManager != null
                    && MatchManager.Phase == MatchPhase.Running;
                _inferenceReadyAfterFixedTick = _bootstrapFixedTick;
                return;
            }

            // Hold first inference decision until at least the next fixed tick after runtime setup.
            _inferenceRuntimeReady = false;
            _inferenceReadyAfterFixedTick = _bootstrapFixedTick + 1;
        }

        private void UpdateInferenceRuntimeReadyState()
        {
            if (RuntimeMode != Stage7BRuntimeMode.InferenceOnly)
            {
                return;
            }

            if (_inferenceRuntimeReady)
            {
                return;
            }

            bool runtimeStable = _hasRuntimeEpisodeStarted
                && !_isStartingEpisode
                && MatchManager != null
                && MatchManager.Phase == MatchPhase.Running;
            if (!runtimeStable)
            {
                return;
            }

            if (_bootstrapFixedTick < _inferenceReadyAfterFixedTick)
            {
                return;
            }

            _inferenceRuntimeReady = true;
        }

        private static void DisableTeacherReplayOrchestrators()
        {
            TeacherReplay.Stage7BTeacherReplayDemoOrchestrator[] orchestrators =
                FindObjectsByType<TeacherReplay.Stage7BTeacherReplayDemoOrchestrator>(
                    FindObjectsInactive.Include,
                    FindObjectsSortMode.None);

            for (int i = 0; i < orchestrators.Length; i++)
            {
                TeacherReplay.Stage7BTeacherReplayDemoOrchestrator orchestrator = orchestrators[i];
                if (orchestrator != null && orchestrator.enabled)
                {
                    orchestrator.enabled = false;
                }
            }
        }

        private static void RemoveUnexpectedAgentComponents(GameObject host)
        {
            if (host == null)
            {
                return;
            }

            Agent[] agents = host.GetComponents<Agent>();
            for (int i = 0; i < agents.Length; i++)
            {
                Agent agent = agents[i];
                if (agent == null || agent is StudentMlAgent)
                {
                    continue;
                }

#if UNITY_EDITOR
                if (!Application.isPlaying)
                {
                    DestroyImmediate(agent);
                }
                else
#endif
                {
                    Destroy(agent);
                }
            }
        }

        private void ConfigureMatchBootstrap()
        {
            if (_fallbackConfig == null)
            {
                _fallbackConfig = LoadDefaultConfig();
            }

            GameConfig configuredGameConfig = ResolveConfiguredGameConfig();

            SetPrivateField(MatchBootstrap, "_config", configuredGameConfig);
            SetPrivateField(MatchBootstrap, "_scenarioPreset", _scenarioPreset);
            SetPrivateField(
                MatchBootstrap,
                "_initializationMode",
                _ensureWeek6StaticHarvestLayout
                    ? BootstrapInitializationMode.StaticSceneRegistration
                    : BootstrapInitializationMode.ProceduralSpawn);
            SetPrivateField(MatchBootstrap, "_day6SanityStartResources", Mathf.Max(0, _startResources));
            SetPrivateField(MatchBootstrap, "_gridManager", GridManager);
            SetPrivateField(MatchBootstrap, "_matchManager", MatchManager);
            SetPrivateField(MatchBootstrap, "_unitRegistry", UnitRegistry);
            SetPrivateField(MatchBootstrap, "_resourceManager", ResourceManager);
        }

        private void ConfigureScriptedOpponent()
        {
            if (ScriptedOpponentAdapter == null)
            {
                return;
            }

            ScriptedOpponentAdapter.Initialize(GridManager, UnitRegistry, ResourceManager, MatchManager, MatchBootstrap);
            ScriptedOpponentAdapter.ResetHeuristicState();
            ScriptedOpponentAdapter.SetScriptedOpponentProfile(_scriptedOpponentTacticProfile);
            ScriptedOpponentAdapter.SetPlayerControlModes(
                _studentPlayer == Owner.Player1 ? HeuristicControlMode.Idle : HeuristicControlMode.Heuristic,
                _studentPlayer == Owner.Player2 ? HeuristicControlMode.Idle : HeuristicControlMode.Heuristic);
            ScriptedOpponentPacing?.AttachAdapter(ScriptedOpponentAdapter, _scriptedOpponent);
        }

        private void CleanupRuntimeObjects()
        {
            if (UnitRegistry != null)
            {
                List<UnitRuntime> units = UnitRegistry.GetAllUnits();
                for (int i = 0; i < units.Count; i++)
                {
                    UnitRuntime unit = units[i];
                    if (unit != null && unit.GetComponent<StaticSceneEntityAuthoring>() == null)
                    {
                        Destroy(unit.gameObject);
                    }
                }

                UnitRegistry.Clear();
            }

            GridManager?.InitGrid(GameConstants.MapWidth, GameConstants.MapHeight);
            ResourceManager?.Clear();
            MatchManager?.ResetMatch();
            Stage7BResetTimeoutTrace.Record("MlAgentsTrainingBootstrap.MatchManager.ResetMatch", StudentAgent, this);
        }

        private void EnsureWeek6StaticHarvestLayout()
        {
            if (!_ensureWeek6StaticHarvestLayout)
            {
                return;
            }

            Transform root = EnsureLayoutRoot();
            EnsureAuthoredEntity(root, "Neutral_Resource_(0, 0)", UnitType.Resource, Owner.Neutral, StaticSceneEntityKind.Resource, new GridPosition(0, 0), GameConstants.MaxResourcesPerPatch);
            EnsureAuthoredEntity(root, "Neutral_Resource_(1, 0)", UnitType.Resource, Owner.Neutral, StaticSceneEntityKind.Resource, new GridPosition(1, 0), GameConstants.MaxResourcesPerPatch);
            EnsureAuthoredEntity(root, "Player1_Worker_(1, 1)", UnitType.Worker, Owner.Player1, StaticSceneEntityKind.Unit, new GridPosition(1, 1), 1);
            EnsureAuthoredEntity(root, "Player1_Base_(2, 2)", UnitType.Base, Owner.Player1, StaticSceneEntityKind.Unit, new GridPosition(2, 2), 1);

            EnsureAuthoredEntity(root, "Neutral_Resource_(23, 23)", UnitType.Resource, Owner.Neutral, StaticSceneEntityKind.Resource, new GridPosition(23, 23), GameConstants.MaxResourcesPerPatch);
            EnsureAuthoredEntity(root, "Neutral_Resource_(22, 23)", UnitType.Resource, Owner.Neutral, StaticSceneEntityKind.Resource, new GridPosition(22, 23), GameConstants.MaxResourcesPerPatch);
            EnsureAuthoredEntity(root, "Player2_Worker_(22, 22)", UnitType.Worker, Owner.Player2, StaticSceneEntityKind.Unit, new GridPosition(22, 22), 1);
            EnsureAuthoredEntity(root, "Player2_Base_(21, 21)", UnitType.Base, Owner.Player2, StaticSceneEntityKind.Unit, new GridPosition(21, 21), 1);
        }

        private static Transform EnsureLayoutRoot()
        {
            GameObject root = GameObject.Find("StaticAuthoredLayout");
            if (root == null)
            {
                root = new GameObject("StaticAuthoredLayout");
            }

            return root.transform;
        }

        private static void EnsureAuthoredEntity(
            Transform root,
            string objectName,
            UnitType unitType,
            Owner owner,
            StaticSceneEntityKind kind,
            GridPosition gridPosition,
            int resourceAmount)
        {
            GameObject go = FindExistingAuthoredEntity(objectName);
            if (go == null)
            {
                GameObject prefab = LoadEntityPrefab(unitType);
                if (prefab != null)
                {
                    go = Instantiate(prefab);
                    go.name = objectName;
                }
                else
                {
                    PrimitiveType primitive = unitType == UnitType.Worker ? PrimitiveType.Capsule : PrimitiveType.Cube;
                    go = GameObject.CreatePrimitive(primitive);
                    go.name = objectName;
                }
            }

            go.transform.SetParent(root, true);
            go.transform.position = gridPosition.ToWorldPosition();
            go.transform.rotation = Quaternion.Euler(0f, 180f, 0f);

            if (unitType == UnitType.Worker)
            {
                go.transform.localScale = new Vector3(0.6f, 1f, 0.6f);
            }
            else if (unitType == UnitType.Resource)
            {
                go.transform.localScale = Vector3.one * 0.6f;
            }
            else
            {
                go.transform.localScale = Vector3.one;
            }

            UnitRuntime runtime = go.GetComponent<UnitRuntime>();
            if (runtime == null)
            {
                runtime = go.AddComponent<UnitRuntime>();
            }

            if ((unitType == UnitType.Base || unitType == UnitType.Barracks)
                && go.GetComponent<BuildingRuntime>() == null)
            {
                go.AddComponent<BuildingRuntime>();
            }

            StaticSceneEntityAuthoring authored = go.GetComponent<StaticSceneEntityAuthoring>();
            if (authored == null)
            {
                authored = go.AddComponent<StaticSceneEntityAuthoring>();
            }

            authored.Configure(kind, unitType, owner, gridPosition, resourceAmount);
        }

        private static GameObject FindExistingAuthoredEntity(string objectName)
        {
            StaticSceneEntityAuthoring[] authored = FindObjectsByType<StaticSceneEntityAuthoring>(
                FindObjectsInactive.Include,
                FindObjectsSortMode.None);

            GameObject first = null;
            for (int i = 0; i < authored.Length; i++)
            {
                StaticSceneEntityAuthoring entry = authored[i];
                if (entry == null || entry.name != objectName)
                {
                    continue;
                }

                if (first == null)
                {
                    first = entry.gameObject;
                }
                else
                {
                    Destroy(entry.gameObject);
                }
            }

            if (first != null)
            {
                return first;
            }

            GameObject byPath = GameObject.Find("StaticAuthoredLayout/" + objectName);
            if (byPath != null)
            {
                return byPath;
            }

            return GameObject.Find(objectName);
        }

        private static GameObject LoadEntityPrefab(UnitType unitType)
        {
#if UNITY_EDITOR
            string path = unitType switch
            {
                UnitType.Resource => "Assets/Prefabs/Resource.prefab",
                UnitType.Base => "Assets/Prefabs/Base.prefab",
                UnitType.Worker => "Assets/Prefabs/Worker.prefab",
                UnitType.Barracks => "Assets/Prefabs/Barracks.prefab",
                UnitType.Light => "Assets/Prefabs/Light.prefab",
                UnitType.Heavy => "Assets/Prefabs/Heavy.prefab",
                UnitType.Ranged => "Assets/Prefabs/Ranged.prefab",
                _ => null
            };

            return string.IsNullOrWhiteSpace(path) ? null : AssetDatabase.LoadAssetAtPath<GameObject>(path);
#else
            return null;
#endif
        }

        private bool DetectDuplicateSpawn()
        {
            if (UnitRegistry == null)
            {
                return false;
            }

            var occupied = new HashSet<GridPosition>();
            List<UnitRuntime> units = UnitRegistry.GetAllUnits();
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit == null || !unit.IsAlive)
                {
                    continue;
                }

                if (!occupied.Add(unit.GridPos))
                {
                    Debug.LogError($"[Stage7B] Duplicate spawn detected at {unit.GridPos}.");
                    return true;
                }
            }

            return false;
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
            return component != null ? component : host.AddComponent<T>();
        }

        private static void SetPrivateField<T>(object target, string fieldName, T value)
        {
            if (target == null)
            {
                return;
            }

            FieldInfo field = target.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            field?.SetValue(target, value);
        }

        private static GameConfig LoadDefaultConfig()
        {
#if UNITY_EDITOR
            return AssetDatabase.LoadAssetAtPath<GameConfig>("Assets/ML/GameConfig_MVP.asset");
#else
            return null;
#endif
        }

        private GameConfig ResolveConfiguredGameConfig()
        {
            if (_fallbackConfig == null)
            {
                return null;
            }

            int configuredMaxSteps = ResolveConfiguredMatchMaxSteps();
            if (_fallbackConfig.maxEpisodeSteps == configuredMaxSteps)
            {
                _runtimeConfigOverride = null;
                return _fallbackConfig;
            }

            if (_runtimeConfigOverride == null)
            {
                _runtimeConfigOverride = Instantiate(_fallbackConfig);
                _runtimeConfigOverride.name = _fallbackConfig.name + "_Stage7B_RuntimeOverride";
            }

            _runtimeConfigOverride.maxEpisodeSteps = configuredMaxSteps;
            return _runtimeConfigOverride;
        }

        private int ResolveConfiguredMatchMaxSteps()
        {
            if (_stage7BMatchMaxSteps > 0)
            {
                return _stage7BMatchMaxSteps;
            }

            if (_fallbackConfig != null && _fallbackConfig.maxEpisodeSteps > 0)
            {
                return _fallbackConfig.maxEpisodeSteps;
            }

            return GameConstants.MaxEpisodeSteps;
        }
    }
}
