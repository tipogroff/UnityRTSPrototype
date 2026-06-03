#if UNITY_EDITOR
using System.Collections;
using System.Collections.Generic;
using System.IO;
using RTS.Core;
using RTS.Gameplay;
using RTS.Presentation.UI;
using UnityEditor;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RTS.Presentation.DebugTools
{
    public sealed class DebugPauseValidationRunner : MonoBehaviour
    {
        public const string EnabledKey = "RTS.DebugPauseValidation.Enabled";
        public const string SceneNameKey = "RTS.DebugPauseValidation.SceneName";
        public const string ReportPathKey = "RTS.DebugPauseValidation.ReportPath";

        private const string DefaultSceneName = "HumanPlay_Demo_PlayerVsAI";
        private const string DefaultReportPath = "GAME_SPEED_PAUSE_VALIDATION_RUNTIME_REPORT.md";

        private readonly List<string> _lines = new List<string>();
        private bool _lastModePassed;
        private bool _lastStepGrowthResult;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.BeforeSceneLoad)]
        private static void ConfigureLaunchOptions()
        {
            if (!EditorPrefs.GetBool(EnabledKey, false))
            {
                return;
            }

            DemoLaunchOptions.SetMode(DemoLaunchMode.AIvsPlayer);
        }

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void CreateRunner()
        {
            if (!EditorPrefs.GetBool(EnabledKey, false))
            {
                return;
            }

            if (FindFirstObjectByType<DebugPauseValidationRunner>() != null)
            {
                return;
            }

            GameObject host = new GameObject("DebugPauseValidationRunner");
            DontDestroyOnLoad(host);
            host.AddComponent<DebugPauseValidationRunner>();
        }

        private void Start()
        {
            StartCoroutine(Run());
        }

        private IEnumerator Run()
        {
            Log("# Game Speed Pause Runtime Validation");
            Log($"Started at realtime={Time.realtimeSinceStartup:0.00}");

            string sceneName = EditorPrefs.GetString(SceneNameKey, DefaultSceneName);
            if (SceneManager.GetActiveScene().name != sceneName)
            {
                Log($"Loading scene {sceneName}");
                DemoLaunchOptions.SetMode(DemoLaunchMode.AIvsPlayer);
                SceneManager.LoadScene(sceneName);
                yield return WaitForScene(sceneName, 10f);
            }

            yield return WaitForSecondsRealtime(0.25f);

            bool allPassed = true;
            yield return RunMode("AIvsPlayer", controller => controller.StartAIvsPlayer2());
            allPassed &= _lastModePassed;
            yield return RunMode("AIvsBot", controller => controller.StartAIvsBot());
            allPassed &= _lastModePassed;
            yield return RunMode("AIvsAI", controller => controller.StartAIvsAI());
            allPassed &= _lastModePassed;

            Log(allPassed ? "RESULT: PASS" : "RESULT: FAIL");
            WriteReport();
            Debug.Log("[PauseValidation] Completed. Result=" + (allPassed ? "PASS" : "FAIL"));
            EditorPrefs.SetBool(EnabledKey, false);
        }

        private IEnumerator RunMode(string modeName, System.Action<HumanPlayModeController> startMode)
        {
            _lastModePassed = false;
            Log($"## Mode={modeName}");

            HumanPlayModeController modeController = null;
            GameSpeedController speedController = null;
            EpisodeController episodeController = null;
            MatchManager matchManager = null;

            yield return WaitForControllers(
                10f,
                value => modeController = value,
                value => speedController = value,
                value => episodeController = value,
                value => matchManager = value);

            if (modeController == null || speedController == null || episodeController == null || matchManager == null)
            {
                Log($"[PauseValidation] Mode={modeName} FAIL missing controller mode={modeController != null} speed={speedController != null} episode={episodeController != null} match={matchManager != null}");
                yield break;
            }

            speedController.ClearAllPauseReasons("DebugPauseValidationRunner." + modeName + ".start");
            startMode(modeController);
            yield return WaitForMatchRunning(matchManager, 5f);
            yield return WaitForSecondsRealtime(0.25f);
            TryResolveControllers(out modeController, out speedController, out episodeController, out matchManager);

            int startStep = matchManager.Step;
            yield return WaitForStepGrowth(matchManager, startStep, 4f);
            bool grewBeforePause = _lastStepGrowthResult;
            int growingStep = matchManager.Step;
            Log($"[PauseValidation] Mode={modeName} Step counter growing: {startStep} -> {growingStep} {(grewBeforePause ? "PASS" : "FAIL")}");
            if (!grewBeforePause)
            {
                yield break;
            }

            speedController.RequestPause(SimulationPauseReason.External);
            yield return WaitForSecondsRealtime(0.1f);
            TryResolveControllers(out modeController, out speedController, out episodeController, out matchManager);
            int pausedStep = matchManager.Step;
            bool pauseFlagApplied = episodeController.IsAutomaticSteppingPaused;
            Log($"[PauseValidation] Mode={modeName} RequestPause External pausedStep={pausedStep} activeReasons={speedController.ActiveReasons} episodePaused={pauseFlagApplied}");

            yield return WaitForSecondsRealtime(2f);
            int afterPauseWait = matchManager.Step;
            bool stopped = afterPauseWait == pausedStep;
            Log($"[PauseValidation] Mode={modeName} After 2.0s step={afterPauseWait} {(stopped ? "PASS stopped" : "FAIL still stepping")}");

            bool stepped = speedController.StepOnce();
            yield return WaitForSecondsRealtime(0.1f);
            TryResolveControllers(out modeController, out speedController, out episodeController, out matchManager);
            int afterStepOnce = matchManager.Step;
            bool singleStep = stepped && afterStepOnce == pausedStep + 1;
            Log($"[PauseValidation] Mode={modeName} StepOnce returned={stepped} step {pausedStep} -> {afterStepOnce} {(singleStep ? "PASS single step" : "FAIL")}");

            yield return WaitForSecondsRealtime(2f);
            int afterStepWait = matchManager.Step;
            bool stillPaused = afterStepWait == afterStepOnce;
            Log($"[PauseValidation] Mode={modeName} After Step wait 2.0s step={afterStepWait} {(stillPaused ? "PASS still paused" : "FAIL resumed unexpectedly")}");

            speedController.ReleasePause(SimulationPauseReason.External);
            yield return WaitForSecondsRealtime(0.1f);
            TryResolveControllers(out modeController, out speedController, out episodeController, out matchManager);
            int resumeStart = matchManager.Step;
            yield return WaitForStepGrowth(matchManager, resumeStart, 4f);
            bool resumed = _lastStepGrowthResult;
            Log($"[PauseValidation] Mode={modeName} After resume step={matchManager.Step} {(resumed ? "PASS resumed" : "FAIL did not resume")}");

            speedController.ClearAllPauseReasons("DebugPauseValidationRunner." + modeName + ".cleanup");
            _lastModePassed = stopped && singleStep && stillPaused && resumed && pauseFlagApplied;
        }

        private IEnumerator WaitForControllers(
            float timeoutSeconds,
            System.Action<HumanPlayModeController> mode,
            System.Action<GameSpeedController> speed,
            System.Action<EpisodeController> episode,
            System.Action<MatchManager> match)
        {
            float deadline = Time.realtimeSinceStartup + timeoutSeconds;
            while (Time.realtimeSinceStartup < deadline)
            {
                HumanPlayModeController modeController = FindFirstObjectByType<HumanPlayModeController>();
                GameSpeedController speedController = FindFirstObjectByType<GameSpeedController>();
                EpisodeController episodeController = EpisodeController.Instance != null
                    ? EpisodeController.Instance
                    : FindFirstObjectByType<EpisodeController>();
                MatchManager matchManager = MatchManager.Instance != null
                    ? MatchManager.Instance
                    : FindFirstObjectByType<MatchManager>();

                if (modeController != null && speedController != null && episodeController != null && matchManager != null)
                {
                    mode(modeController);
                    speed(speedController);
                    episode(episodeController);
                    match(matchManager);
                    yield break;
                }

                yield return null;
            }
        }

        private static bool TryResolveControllers(
            out HumanPlayModeController modeController,
            out GameSpeedController speedController,
            out EpisodeController episodeController,
            out MatchManager matchManager)
        {
            modeController = FindFirstObjectByType<HumanPlayModeController>();
            speedController = FindFirstObjectByType<GameSpeedController>();
            episodeController = EpisodeController.Instance != null
                ? EpisodeController.Instance
                : FindFirstObjectByType<EpisodeController>();
            matchManager = MatchManager.Instance != null
                ? MatchManager.Instance
                : FindFirstObjectByType<MatchManager>();

            return modeController != null && speedController != null && episodeController != null && matchManager != null;
        }

        private static IEnumerator WaitForScene(string sceneName, float timeoutSeconds)
        {
            float deadline = Time.realtimeSinceStartup + timeoutSeconds;
            while (Time.realtimeSinceStartup < deadline && SceneManager.GetActiveScene().name != sceneName)
            {
                yield return null;
            }
        }

        private static IEnumerator WaitForMatchRunning(MatchManager matchManager, float timeoutSeconds)
        {
            float deadline = Time.realtimeSinceStartup + timeoutSeconds;
            while (Time.realtimeSinceStartup < deadline && matchManager != null && matchManager.Phase != MatchPhase.Running)
            {
                yield return null;
            }
        }

        private IEnumerator WaitForStepGrowth(MatchManager matchManager, int startStep, float timeoutSeconds)
        {
            _lastStepGrowthResult = false;
            float deadline = Time.realtimeSinceStartup + timeoutSeconds;
            while (Time.realtimeSinceStartup < deadline)
            {
                if (matchManager != null && matchManager.Step > startStep)
                {
                    _lastStepGrowthResult = true;
                    yield break;
                }

                yield return null;
            }
        }

        private static IEnumerator WaitForSecondsRealtime(float seconds)
        {
            float deadline = Time.realtimeSinceStartup + seconds;
            while (Time.realtimeSinceStartup < deadline)
            {
                yield return null;
            }
        }

        private void Log(string line)
        {
            _lines.Add(line);
            Debug.Log("[PauseValidation] " + line);
        }

        private void WriteReport()
        {
            string relativePath = EditorPrefs.GetString(ReportPathKey, DefaultReportPath);
            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            string fullPath = Path.Combine(projectRoot, relativePath);
            File.WriteAllLines(fullPath, _lines);
            Log("Report written: " + fullPath);
        }
    }
}
#endif
