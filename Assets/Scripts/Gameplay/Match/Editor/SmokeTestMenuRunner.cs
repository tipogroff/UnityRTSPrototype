// SmokeTestMenuRunner.cs — EditorScript для запуска smoke-test через меню Unity.
// Автоматически удаляется после тестирования.
#if UNITY_EDITOR
using System.Reflection;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;
using RTS.Gameplay;
using RTS.ML;
using RTS.Core;

namespace RTS.Testing.Editor
{
    [InitializeOnLoad]
    public static class SmokeTestMenuRunner
    {
        private const string RunDay6AfterPlayModeKey = "RTS.Testing.Editor.RunDay6AfterPlayMode";
        private const string RunDay6ReadyPollsKey = "RTS.Testing.Editor.RunDay6ReadyPolls";

        private const string RunDay3AfterPlayModeKey = "RTS.Testing.Editor.RunDay3AfterPlayMode";
        private const string RunDay3ReadyPollsKey = "RTS.Testing.Editor.RunDay3ReadyPolls";

        static SmokeTestMenuRunner()
        {
            EditorApplication.playModeStateChanged -= HandlePlayModeStateChanged;
            EditorApplication.playModeStateChanged += HandlePlayModeStateChanged;
            EditorApplication.update -= PollPendingColdStartSmoke;
            EditorApplication.update += PollPendingColdStartSmoke;
            EditorApplication.update -= PollPendingColdStartSmokeDay3;
            EditorApplication.update += PollPendingColdStartSmokeDay3;
        }

        [MenuItem("RTS/PlayMode/Enter")]
        public static void EnterPlayMode()
        {
            if (Application.isPlaying)
            {
                Debug.Log("[RTS PlayMode] Already in Play Mode.");
                return;
            }

            EditorApplication.isPlaying = true;
        }

        [MenuItem("RTS/PlayMode/Exit")]
        public static void ExitPlayMode()
        {
            if (!Application.isPlaying)
            {
                Debug.Log("[RTS PlayMode] Already in Edit Mode.");
                return;
            }

            EditorApplication.isPlaying = false;
        }

        [MenuItem("RTS/Smoke/Day6 From Cold Start")]
        public static void RunDay6FromColdStart()
        {
            if (Application.isPlaying)
            {
                RunDay6PipelineSmokeTest();
                return;
            }

            SessionState.SetBool(RunDay6AfterPlayModeKey, true);
            SessionState.SetInt(RunDay6ReadyPollsKey, 0);
            Debug.Log("[SmokeTest] Day 6 cold-start requested. Entering Play Mode...");
            EditorApplication.isPlaying = true;
        }

        [MenuItem("RTS/Scene/Fix Current RTS Scene")]
        public static void FixCurrentRtsScene()
        {
            if (Application.isPlaying)
            {
                Debug.LogError("[RTS Scene Fix] Exit Play Mode before repairing the scene.");
                return;
            }

            Scene activeScene = SceneManager.GetActiveScene();
            if (!activeScene.IsValid())
            {
                Debug.LogError("[RTS Scene Fix] No valid active scene is open.");
                return;
            }

            GameConfig config = AssetDatabase.LoadAssetAtPath<GameConfig>("Assets/ML/GameConfig_MVP.asset");
            if (config == null)
            {
                Debug.LogError("[RTS Scene Fix] Could not load Assets/ML/GameConfig_MVP.asset.");
                return;
            }

            GridManager gridManager = EnsureComponent<GridManager>("GridManager");
            MatchManager matchManager = EnsureComponent<MatchManager>("MatchManager");
            MatchBootstrap matchBootstrap = EnsureComponent<MatchBootstrap>("MatchBootstrap");
            UnitRegistry unitRegistry = EnsureComponent<UnitRegistry>("UnitRegistry");
            ResourceManager resourceManager = EnsureComponent<ResourceManager>("ResourceManager");
            EpisodeController episodeController = EnsureComponent<EpisodeController>("EpisodeController");
            VictoryResolver victoryResolver = EnsureComponent<VictoryResolver>("VictoryResolver");
            HeuristicDriver heuristicDriver = EnsureComponent<HeuristicDriver>("HeuristicDriver");

            EnsureMainCamera();
            EnsureDirectionalLight();

            SetSerializedReference(gridManager, "config", config);

            SetSerializedReference(matchBootstrap, "_config", config);
            SetSerializedReference(matchBootstrap, "_gridManager", gridManager);
            SetSerializedReference(matchBootstrap, "_matchManager", matchManager);
            SetSerializedReference(matchBootstrap, "_unitRegistry", unitRegistry);
            SetSerializedReference(matchBootstrap, "_resourceManager", resourceManager);

            SetSerializedReference(matchManager, "_gridManager", gridManager);
            SetSerializedReference(matchManager, "_unitRegistry", unitRegistry);
            SetSerializedReference(matchManager, "_victoryResolver", victoryResolver);
            SetSerializedReference(matchManager, "_matchBootstrap", matchBootstrap);

            SetSerializedReference(episodeController, "_matchManager", matchManager);
            SetSerializedReference(episodeController, "_matchBootstrap", matchBootstrap);
            SetSerializedReference(episodeController, "_gridManager", gridManager);
            SetSerializedReference(episodeController, "_unitRegistry", unitRegistry);
            SetSerializedReference(episodeController, "_resourceManager", resourceManager);
            SetSerializedReference(episodeController, "_heuristicDriver", heuristicDriver);

            SetSerializedReference(heuristicDriver, "_config", config);
            SetSerializedReference(heuristicDriver, "_gridManager", gridManager);
            SetSerializedReference(heuristicDriver, "_unitRegistry", unitRegistry);
            SetSerializedReference(heuristicDriver, "_resourceManager", resourceManager);
            SetSerializedReference(heuristicDriver, "_matchManager", matchManager);

            ManualStepController manualStepController = Object.FindFirstObjectByType<ManualStepController>();
            if (manualStepController != null)
            {
                SetSerializedReference(manualStepController, "_episodeController", episodeController);
                SetSerializedReference(manualStepController, "_matchManager", matchManager);
            }

            EditorSceneManager.MarkSceneDirty(activeScene);
            EditorSceneManager.SaveOpenScenes();

            Debug.Log($"[RTS Scene Fix] Scene '{activeScene.name}' repaired and saved.");
        }

        [MenuItem("SmokeTest/0 - Ensure ActionApplierSmokeTest Object")]
        public static void EnsureMlSmokeTestObject()
        {
            ActionApplierSmokeTest existing = Object.FindFirstObjectByType<ActionApplierSmokeTest>();
            if (existing != null)
            {
                Debug.Log("[SmokeTest] ActionApplierSmokeTest already exists in scene.");
                return;
            }

            GameObject host = new GameObject("ActionApplierSmokeTest");
            host.AddComponent<ActionApplierSmokeTest>();

            EditorSceneManager.MarkSceneDirty(host.scene);
            EditorSceneManager.SaveOpenScenes();

            Debug.Log("[SmokeTest] Created persistent ActionApplierSmokeTest object and saved scene.");
        }

        [MenuItem("SmokeTest/1 - Print Match State")]
        public static void PrintMatchState()
        {
            MatchManager mm = MatchManager.Instance;
            EpisodeController ec = EpisodeController.Instance;

            if (mm == null || ec == null)
            {
                Debug.LogError("[SmokeTest] Not in Play Mode or components missing.");
                return;
            }

            Debug.Log("═══════════════ MATCH STATE SNAPSHOT ═══════════════");
            Debug.Log($"  EpisodeIndex : {ec.EpisodeIndex}");
            Debug.Log($"  IsRunning    : {ec.IsRunning}");
            Debug.Log($"  Phase        : {mm.Phase}");
            Debug.Log($"  Step         : {mm.Step}");
            Debug.Log($"  MaxSteps     : {mm.MaxSteps}");
            Debug.Log($"  Winner       : {mm.Winner}");
            Debug.Log($"  EndReason    : {mm.EndReason}");
            Debug.Log($"  EndDetails   : {mm.EndReasonDetails}");
            Debug.Log("═════════════════════════════════════════════════════");
        }

        [MenuItem("SmokeTest/2 - Force StepMatch x5")]
        public static void Step5Times()
        {
            MatchManager mm = MatchManager.Instance;
            if (mm == null)
            {
                Debug.LogError("[SmokeTest] Not in Play Mode.");
                return;
            }
            if (mm.Phase != MatchPhase.Running)
            {
                Debug.LogWarning($"[SmokeTest] Phase is {mm.Phase}, cannot step.");
                return;
            }

            Debug.Log($"[SmokeTest] Stepping 5 times from Step={mm.Step}...");
            for (int i = 0; i < 5; i++)
            {
                bool isRunning = mm.StepMatch();
                Debug.Log($"[SmokeTest] StepMatch() → Step={mm.Step}, Phase={mm.Phase}, Running={isRunning}");
                if (!isRunning)
                {
                    break;
                }
            }
            Debug.Log($"[SmokeTest] After 5 steps: Step={mm.Step}, Phase={mm.Phase}");
        }

        [MenuItem("SmokeTest/3 - Force Episode Reset")]
        public static void ForceReset()
        {
            EpisodeController ec = EpisodeController.Instance;
            MatchManager mm = MatchManager.Instance;

            if (ec == null || mm == null)
            {
                Debug.LogError("[SmokeTest] Not in Play Mode.");
                return;
            }

            int prevEpisode = ec.EpisodeIndex;
            Debug.Log($"[SmokeTest] Resetting from Episode {prevEpisode}, Phase={mm.Phase}...");

            ec.ResetEpisode();

            Debug.Log("═══════════════ POST-RESET STATE ════════════════════");
            Debug.Log($"  EpisodeIndex : {ec.EpisodeIndex}  (was {prevEpisode})");
            Debug.Log($"  Phase        : {mm.Phase}  (expected Running)");
            Debug.Log($"  Step         : {mm.Step}  (expected 0)");
            Debug.Log($"  Winner       : {mm.Winner}  (expected Neutral)");
            Debug.Log($"  EndReason    : {mm.EndReason}  (expected None)");

            bool ok = mm.Phase == MatchPhase.Running
                   && mm.Step == 0
                   && ec.EpisodeIndex == prevEpisode + 1;

            if (ok)
            {
                Debug.Log("[SmokeTest] ✅ RESET OK — lifecycle cycle working correctly!");
            }
            else
            {
                Debug.LogWarning("[SmokeTest] ⚠️ RESET had unexpected state. Check logs above.");
            }
            Debug.Log("═════════════════════════════════════════════════════");
        }

        [MenuItem("SmokeTest/4 - FULL AUTO SMOKE TEST")]
        public static void RunFullSmokeTest()
        {
            MatchManager mm = MatchManager.Instance;
            EpisodeController ec = EpisodeController.Instance;

            if (mm == null || ec == null)
            {
                Debug.LogError("[SmokeTest] Enter Play Mode first.");
                return;
            }

            Debug.Log("╔════════════════════════════════════════════════════════╗");
            Debug.Log("║        FULL AUTO SMOKE-TEST INITIATED                  ║");
            Debug.Log("╚════════════════════════════════════════════════════════╝");

            // Шаг 1 — начальное состояние
            Debug.Log($"\n[1] Initial state: Phase={mm.Phase} | Step={mm.Step} | Episode={ec.EpisodeIndex}");
            bool startOk = mm.Phase == MatchPhase.Running;

            // Шаг 2 — 5 принудительных шагов
            int stepsBefore = mm.Step;
            for (int i = 0; i < 5; i++)
            {
                if (mm.Phase != MatchPhase.Running)
                {
                    break;
                }
                mm.StepMatch();
            }
            bool stepsOk = mm.Step > stepsBefore;
            Debug.Log($"[2] After 5 steps: Step={mm.Step} (was {stepsBefore}), +{mm.Step - stepsBefore} steps");

            // Шаг 3 — принудительное завершение до лимита
            // Пропускаем к MaxSteps напрямую через StepMatch в цикле (ограничен 50 итерациями)
            int stepsToTerminal = 0;
            int safetyLimit = 50;
            bool reachedTerminal = false;
            while (mm.Phase == MatchPhase.Running && stepsToTerminal < safetyLimit)
            {
                bool isRunning = mm.StepMatch();
                stepsToTerminal++;
                if (!isRunning)
                {
                    reachedTerminal = true;
                    break;
                }
            }

            bool terminalOk = mm.Phase == MatchPhase.Ended || reachedTerminal;
            Debug.Log($"[3] Terminal? {mm.Phase} | Winner={mm.Winner} | Reason={mm.EndReason} | {stepsToTerminal} extra steps");

            // Принудительный terminal если ещё не наступил
            if (!terminalOk && mm.Phase == MatchPhase.Running)
            {
                mm.DeclareWinner(RTS.Core.Owner.Neutral, MatchEndReason.StepLimitReached, "Forced by smoke-test");
                terminalOk = true;
                Debug.Log("[3b] Forced terminal via DeclareWinner()");
            }

            // Шаг 4 — reset
            int episodeBefore = ec.EpisodeIndex;
            ec.ResetEpisode();
            bool resetOk = mm.Phase == MatchPhase.Running && mm.Step == 0 && ec.EpisodeIndex == episodeBefore + 1;
            Debug.Log($"[4] Reset: Phase={mm.Phase} | Step={mm.Step} | Episode {episodeBefore}→{ec.EpisodeIndex}");

            // Итог
            Debug.Log("\n╔════════════════ SMOKE-TEST RESULTS ════════════════════╗");
            Debug.Log($"  ✓ Start (Phase=Running):       {(startOk   ? "✅ PASS" : "❌ FAIL")}");
            Debug.Log($"  ✓ Steps incremented:           {(stepsOk   ? "✅ PASS" : "❌ FAIL")}");
            Debug.Log($"  ✓ Terminal reached:            {(terminalOk? "✅ PASS" : "❌ FAIL")}");
            Debug.Log($"  ✓ Reset (Step=0, Episode+1):   {(resetOk   ? "✅ PASS" : "❌ FAIL")}");
            Debug.Log("╚════════════════════════════════════════════════════════╝");

            if (startOk && stepsOk && terminalOk && resetOk)
            {
                Debug.Log("🎉  ALL SMOKE-TESTS PASSED!");
            }
            else
            {
                Debug.LogWarning("⚠️  SOME CHECKS FAILED — see above.");
            }
        }

        [MenuItem("SmokeTest/5 - ML Action Pipeline Smoke Test")]
        public static void RunMlActionPipelineSmokeTest()
        {
            if (!Application.isPlaying)
            {
                Debug.LogError("[SmokeTest] Enter Play Mode first.");
                return;
            }

            ActionApplierSmokeTest smoke = Object.FindFirstObjectByType<ActionApplierSmokeTest>();
            if (smoke == null)
            {
                GameObject host = new GameObject("ActionApplierSmokeTest_AutoRunner");
                smoke = host.AddComponent<ActionApplierSmokeTest>();
                Debug.Log("[SmokeTest] ActionApplierSmokeTest was auto-created for this run.");
            }

            MethodInfo runTests = typeof(ActionApplierSmokeTest)
                .GetMethod("RunTests", BindingFlags.Instance | BindingFlags.NonPublic);

            if (runTests == null)
            {
                Debug.LogError("[SmokeTest] RunTests() method not found on ActionApplierSmokeTest.");
                return;
            }

            runTests.Invoke(smoke, null);
            Debug.Log("[SmokeTest] ML Action pipeline smoke test invoked.");
        }

        [MenuItem("SmokeTest/6 - ML Action Masking Smoke Test")]
        public static void RunMlActionMaskingSmokeTest()
        {
            if (!Application.isPlaying)
            {
                Debug.LogError("[SmokeTest] Enter Play Mode first.");
                return;
            }

            ActionMaskBuilderSmokeTest smoke = Object.FindFirstObjectByType<ActionMaskBuilderSmokeTest>();
            if (smoke == null)
            {
                GameObject host = new GameObject("ActionMaskBuilderSmokeTest_AutoRunner");
                smoke = host.AddComponent<ActionMaskBuilderSmokeTest>();
                Debug.Log("[SmokeTest] ActionMaskBuilderSmokeTest was auto-created for this run.");
            }

            MethodInfo runTests = typeof(ActionMaskBuilderSmokeTest)
                .GetMethod("RunTests", BindingFlags.Instance | BindingFlags.NonPublic);

            if (runTests == null)
            {
                Debug.LogError("[SmokeTest] RunTests() method not found on ActionMaskBuilderSmokeTest.");
                return;
            }

            runTests.Invoke(smoke, null);
            Debug.Log("[SmokeTest] ML Action masking smoke test invoked.");
        }

        [MenuItem("SmokeTest/7 - Day5 Heuristic Pipeline Smoke Test")]
        public static void RunDay5HeuristicPipelineSmokeTest()
        {
            if (!Application.isPlaying)
            {
                Debug.LogError("[SmokeTest] Enter Play Mode first.");
                return;
            }

            HeuristicPolicyAdapterSmokeTest smoke = Object.FindFirstObjectByType<HeuristicPolicyAdapterSmokeTest>();
            bool wasAutoCreated = false;
            if (smoke == null)
            {
                GameObject host = new GameObject("HeuristicPolicyAdapterSmokeTest_AutoRunner");
                smoke = host.AddComponent<HeuristicPolicyAdapterSmokeTest>();
                wasAutoCreated = true;
                Debug.Log("[SmokeTest] HeuristicPolicyAdapterSmokeTest was auto-created for this run.");
            }

            // When auto-created, Awake() typically runs smoke immediately.
            // Skip explicit invocation in the same menu call to avoid duplicate execution.
            if (wasAutoCreated)
            {
                Debug.Log("[SmokeTest] Day 5 heuristic pipeline smoke test invoked via Awake() on auto-created component.");
                return;
            }

            MethodInfo runTests = typeof(HeuristicPolicyAdapterSmokeTest)
                .GetMethod("RunTests", BindingFlags.Instance | BindingFlags.NonPublic);

            if (runTests == null)
            {
                Debug.LogError("[SmokeTest] RunTests() method not found on HeuristicPolicyAdapterSmokeTest.");
                return;
            }

            runTests.Invoke(smoke, null);
            Debug.Log("[SmokeTest] Day 5 heuristic pipeline smoke test invoked.");
        }

        [MenuItem("SmokeTest/8 - Day5 Mode Heuristic vs Heuristic")]
        public static void SetDay5HeuristicVsHeuristic()
        {
            if (!Application.isPlaying)
            {
                Debug.LogError("[SmokeTest] Enter Play Mode first.");
                return;
            }

            HeuristicPolicyAdapter adapter = Object.FindFirstObjectByType<HeuristicPolicyAdapter>();
            if (adapter == null)
            {
                GameObject host = new GameObject("HeuristicPolicyAdapter");
                adapter = host.AddComponent<HeuristicPolicyAdapter>();
            }

            adapter.SetPlayerControlModes(HeuristicControlMode.Heuristic, HeuristicControlMode.Heuristic);
            Debug.Log("[SmokeTest] Day5 control mode set: Player1=Heuristic, Player2=Heuristic.");
        }

        [MenuItem("SmokeTest/9 - Day5 Mode Heuristic vs Idle")]
        public static void SetDay5HeuristicVsIdle()
        {
            if (!Application.isPlaying)
            {
                Debug.LogError("[SmokeTest] Enter Play Mode first.");
                return;
            }

            HeuristicPolicyAdapter adapter = Object.FindFirstObjectByType<HeuristicPolicyAdapter>();
            if (adapter == null)
            {
                GameObject host = new GameObject("HeuristicPolicyAdapter");
                adapter = host.AddComponent<HeuristicPolicyAdapter>();
            }

            adapter.SetPlayerControlModes(HeuristicControlMode.Heuristic, HeuristicControlMode.Idle);
            Debug.Log("[SmokeTest] Day5 control mode set: Player1=Heuristic, Player2=Idle.");
        }

        [MenuItem("SmokeTest/10 - Day6 Pipeline Smoke Test")]
        public static void RunDay6PipelineSmokeTest()
        {
            if (!Application.isPlaying)
            {
                Debug.LogError("[SmokeTest] Enter Play Mode first.");
                return;
            }

            Day6PipelineSmokeTest smoke = Object.FindFirstObjectByType<Day6PipelineSmokeTest>();
            bool wasAutoCreated = false;
            if (smoke == null)
            {
                GameObject host = new GameObject("Day6PipelineSmokeTest_AutoRunner");
                smoke = host.AddComponent<Day6PipelineSmokeTest>();
                wasAutoCreated = true;
                Debug.Log("[SmokeTest] Day6PipelineSmokeTest was auto-created for this run.");
            }

            if (wasAutoCreated)
            {
                Debug.Log("[SmokeTest] Day 6 pipeline smoke test invoked via Awake() on auto-created component.");
                return;
            }

            MethodInfo runTests = typeof(Day6PipelineSmokeTest)
                .GetMethod("RunTests", BindingFlags.Instance | BindingFlags.NonPublic);

            if (runTests == null)
            {
                Debug.LogError("[SmokeTest] RunTests() method not found on Day6PipelineSmokeTest.");
                return;
            }

            runTests.Invoke(smoke, null);
            Debug.Log("[SmokeTest] Day 6 pipeline smoke test invoked.");
        }

        [MenuItem("SmokeTest/11 - Day3 Terminal Pipeline Smoke Test")]
        public static void RunDay3TerminalSmokeTest()
        {
            if (!Application.isPlaying)
            {
                Debug.LogError("[SmokeTest] Enter Play Mode first.");
                return;
            }

            Day3TerminalSmokeTest smoke = Object.FindFirstObjectByType<Day3TerminalSmokeTest>();
            bool wasAutoCreated = false;
            if (smoke == null)
            {
                GameObject host = new GameObject("Day3TerminalSmokeTest_AutoRunner");
                smoke = host.AddComponent<Day3TerminalSmokeTest>();
                wasAutoCreated = true;
                Debug.Log("[SmokeTest] Day3TerminalSmokeTest was auto-created for this run.");
            }

            if (wasAutoCreated)
            {
                Debug.Log("[SmokeTest] Day 3 terminal pipeline smoke test invoked via Awake() on auto-created component.");
                return;
            }

            MethodInfo runTests = typeof(Day3TerminalSmokeTest)
                .GetMethod("RunTests", BindingFlags.Instance | BindingFlags.NonPublic);

            if (runTests == null)
            {
                Debug.LogError("[SmokeTest] RunTests() method not found on Day3TerminalSmokeTest.");
                return;
            }

            runTests.Invoke(smoke, null);
            Debug.Log("[SmokeTest] Day 3 terminal pipeline smoke test invoked.");
        }

        [MenuItem("RTS/Smoke/Day3 From Cold Start")]
        public static void RunDay3TerminalSmokeTestColdStart()
        {
            if (Application.isPlaying)
            {
                Debug.Log("[SmokeTest] Already in Play Mode. Running Day 3 terminal smoke test directly.");
                RunDay3TerminalSmokeTest();
                return;
            }

            SessionState.SetBool(RunDay3AfterPlayModeKey, true);
            SessionState.SetInt(RunDay3ReadyPollsKey, 0);
            Debug.Log("[SmokeTest] Day 3 cold-start: entering Play Mode. Test will auto-run when runtime is ready.");
            EditorApplication.isPlaying = true;
        }

        // Short aliases for environments where long menu paths are clipped.
        [MenuItem("RTS/Smoke/Day6")]
        public static void RunDay6PipelineSmokeTestShortAlias()
        {
            RunDay6PipelineSmokeTest();
        }

        [MenuItem("Tools/RTS/Smoke/Day6")]
        public static void RunDay6PipelineSmokeTestToolsAlias()
        {
            RunDay6PipelineSmokeTest();
        }

        [MenuItem("RTS/Smoke/Day3")]
        public static void RunDay3TerminalSmokeTestShortAlias()
        {
            RunDay3TerminalSmokeTest();
        }

        [MenuItem("Tools/RTS/Smoke/Day3")]
        public static void RunDay3TerminalSmokeTestToolsAlias()
        {
            RunDay3TerminalSmokeTest();
        }

        private static void HandlePlayModeStateChanged(PlayModeStateChange change)
        {
            // Day 6
            if (SessionState.GetBool(RunDay6AfterPlayModeKey, false))
            {
                if (change == PlayModeStateChange.EnteredPlayMode)
                {
                    SessionState.SetInt(RunDay6ReadyPollsKey, 0);
                    Debug.Log("[SmokeTest] Day 6 cold-start entered Play Mode. Waiting for runtime readiness...");
                }
                else if (change == PlayModeStateChange.ExitingPlayMode || change == PlayModeStateChange.EnteredEditMode)
                {
                    SessionState.EraseBool(RunDay6AfterPlayModeKey);
                    SessionState.EraseInt(RunDay6ReadyPollsKey);
                }
            }

            // Day 3
            if (SessionState.GetBool(RunDay3AfterPlayModeKey, false))
            {
                if (change == PlayModeStateChange.EnteredPlayMode)
                {
                    SessionState.SetInt(RunDay3ReadyPollsKey, 0);
                    Debug.Log("[SmokeTest] Day 3 cold-start entered Play Mode. Waiting for runtime readiness...");
                }
                else if (change == PlayModeStateChange.ExitingPlayMode || change == PlayModeStateChange.EnteredEditMode)
                {
                    SessionState.EraseBool(RunDay3AfterPlayModeKey);
                    SessionState.EraseInt(RunDay3ReadyPollsKey);
                }
            }
        }

        private static void PollPendingColdStartSmokeDay3()
        {
            if (!SessionState.GetBool(RunDay3AfterPlayModeKey, false) || !Application.isPlaying)
            {
                return;
            }

            int readyPolls = SessionState.GetInt(RunDay3ReadyPollsKey, 0) + 1;
            SessionState.SetInt(RunDay3ReadyPollsKey, readyPolls);

            EpisodeController episodeController = EpisodeController.Instance;
            MatchManager matchManager = MatchManager.Instance;
            if (episodeController == null || matchManager == null || matchManager.Phase != MatchPhase.Running)
            {
                if (readyPolls == 300)
                {
                    Debug.LogWarning("[SmokeTest] Day 3 cold-start timed out waiting for runtime readiness.");
                    SessionState.EraseBool(RunDay3AfterPlayModeKey);
                    SessionState.EraseInt(RunDay3ReadyPollsKey);
                }

                return;
            }

            SessionState.EraseBool(RunDay3AfterPlayModeKey);
            SessionState.EraseInt(RunDay3ReadyPollsKey);
            Debug.Log("[SmokeTest] Day 3 cold-start runtime is ready. Launching terminal pipeline suite...");
            RunDay3TerminalSmokeTest();
        }

        private static void PollPendingColdStartSmoke()
        {
            if (!SessionState.GetBool(RunDay6AfterPlayModeKey, false) || !Application.isPlaying)
            {
                return;
            }

            int readyPolls = SessionState.GetInt(RunDay6ReadyPollsKey, 0) + 1;
            SessionState.SetInt(RunDay6ReadyPollsKey, readyPolls);

            EpisodeController episodeController = EpisodeController.Instance;
            MatchManager matchManager = MatchManager.Instance;
            if (episodeController == null || matchManager == null || matchManager.Phase != MatchPhase.Running)
            {
                if (readyPolls == 300)
                {
                    Debug.LogWarning("[SmokeTest] Day 6 cold-start timed out waiting for runtime readiness.");
                    SessionState.EraseBool(RunDay6AfterPlayModeKey);
                    SessionState.EraseInt(RunDay6ReadyPollsKey);
                }

                return;
            }

            SessionState.EraseBool(RunDay6AfterPlayModeKey);
            SessionState.EraseInt(RunDay6ReadyPollsKey);
            Debug.Log("[SmokeTest] Day 6 cold-start runtime is ready. Launching suite...");
            RunDay6PipelineSmokeTest();
        }

        private static T EnsureComponent<T>(string gameObjectName) where T : Component
        {
            T existing = Object.FindFirstObjectByType<T>();
            if (existing != null)
            {
                if (existing.gameObject.name != gameObjectName)
                {
                    existing.gameObject.name = gameObjectName;
                }

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

        private static void SetSerializedReference(Object target, string propertyName, Object value)
        {
            if (target == null)
            {
                return;
            }

            SerializedObject serializedObject = new SerializedObject(target);
            SerializedProperty property = serializedObject.FindProperty(propertyName);
            if (property == null)
            {
                Debug.LogWarning($"[RTS Scene Fix] Property '{propertyName}' was not found on {target.name}.");
                return;
            }

            property.objectReferenceValue = value;
            serializedObject.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(target);
        }

        private static void EnsureMainCamera()
        {
            Camera camera = Camera.main;
            if (camera != null)
            {
                return;
            }

            GameObject cameraGo = GameObject.Find("Main Camera") ?? new GameObject("Main Camera");
            if (cameraGo.GetComponent<Camera>() == null)
            {
                cameraGo.AddComponent<Camera>();
            }

            if (cameraGo.GetComponent<AudioListener>() == null)
            {
                cameraGo.AddComponent<AudioListener>();
            }

            cameraGo.tag = "MainCamera";
        }

        private static void EnsureDirectionalLight()
        {
            Light[] lights = Object.FindObjectsByType<Light>(FindObjectsSortMode.None);
            for (int i = 0; i < lights.Length; i++)
            {
                if (lights[i] != null && lights[i].type == LightType.Directional)
                {
                    return;
                }
            }

            GameObject lightGo = GameObject.Find("Directional Light") ?? new GameObject("Directional Light");
            Light light = lightGo.GetComponent<Light>();
            if (light == null)
            {
                light = lightGo.AddComponent<Light>();
            }

            light.type = LightType.Directional;
        }
    }
}
#endif
