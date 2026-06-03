#if UNITY_EDITOR
using System.IO;
using RTS.Presentation.Diagnostics;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RTS.Presentation.Diagnostics.Editor
{
    [InitializeOnLoad]
    public static class RuntimePerformanceValidationMenu
    {
        private const string PendingRunKey = "RTS.PerformanceValidation.PendingRun";
        private const string QuitAfterRunKey = "RTS.PerformanceValidation.QuitAfterRun";
        private const string ExternalTriggerFileName = "RUN_PERFORMANCE_VALIDATION.trigger";
        private const string ValidationScenePath = "Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity";

        static RuntimePerformanceValidationMenu()
        {
            EditorApplication.playModeStateChanged -= HandlePlayModeStateChanged;
            EditorApplication.playModeStateChanged += HandlePlayModeStateChanged;
            EditorApplication.delayCall += TryConsumeExternalTrigger;
        }

        [MenuItem("RTS/Debug/Performance/Run FPS Validation")]
        public static void RunFpsValidation()
        {
            if (EditorApplication.isPlaying)
            {
                StartRunner(quitAfterRun: false);
                return;
            }

            if (!EnsureValidationSceneOpen())
            {
                return;
            }

            EditorPrefs.SetBool(PendingRunKey, true);
            EditorPrefs.SetBool(QuitAfterRunKey, false);
            EditorApplication.EnterPlaymode();
        }

        public static void RunFpsValidationBatchMode()
        {
            if (EditorApplication.isPlaying)
            {
                StartRunner(quitAfterRun: true);
                return;
            }

            if (!EnsureValidationSceneOpen())
            {
                EditorApplication.Exit(1);
                return;
            }

            EditorPrefs.SetBool(PendingRunKey, true);
            EditorPrefs.SetBool(QuitAfterRunKey, true);
            EditorApplication.EnterPlaymode();
        }

        [MenuItem("RTS/Debug/Performance/Show Runtime Monitor")]
        public static void ShowRuntimeMonitor()
        {
            if (!EditorApplication.isPlaying)
            {
                Debug.LogWarning("[Perf] Runtime monitor can be created only in Play Mode.");
                return;
            }

            RuntimePerformanceMonitor.EnsureInScene();
        }

        private static void HandlePlayModeStateChanged(PlayModeStateChange state)
        {
            if (state != PlayModeStateChange.EnteredPlayMode || !EditorPrefs.GetBool(PendingRunKey, false))
            {
                return;
            }

            EditorPrefs.SetBool(PendingRunKey, false);
            bool quitAfterRun = EditorPrefs.GetBool(QuitAfterRunKey, false);
            EditorPrefs.SetBool(QuitAfterRunKey, false);
            EditorApplication.delayCall += () => StartRunner(quitAfterRun);
        }

        private static void TryConsumeExternalTrigger()
        {
            string triggerPath = Path.Combine(Directory.GetCurrentDirectory(), ExternalTriggerFileName);
            if (!File.Exists(triggerPath))
            {
                return;
            }

            try
            {
                File.Delete(triggerPath);
            }
            catch (IOException ex)
            {
                Debug.LogWarning("[Perf] Could not delete validation trigger: " + ex.Message);
            }

            Debug.Log("[Perf] External validation trigger consumed.");
            RunFpsValidation();
        }

        private static bool EnsureValidationSceneOpen()
        {
            Scene activeScene = SceneManager.GetActiveScene();
            string activePath = activeScene.path;
            if (string.Equals(activePath, ValidationScenePath, System.StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            if (activeScene.isDirty)
            {
                Debug.LogWarning(
                    "[Perf] FPS validation was not started because the active scene has unsaved changes. " +
                    "Save or discard the scene, open " + ValidationScenePath + ", then run RTS/Debug/Performance/Run FPS Validation again.");
                return false;
            }

            EditorSceneManager.OpenScene(ValidationScenePath, OpenSceneMode.Single);
            return true;
        }

        private static void StartRunner(bool quitAfterRun)
        {
            RuntimePerformanceMonitor.EnsureInScene().Configure(showOverlay: false, logSpikes: false);
            RuntimePerformanceValidationRunner.EnsureInScene().Run(() =>
            {
                if (!quitAfterRun)
                {
                    return;
                }

                EditorApplication.ExitPlaymode();
                EditorApplication.delayCall += () => EditorApplication.Exit(0);
            });
            Debug.Log("[Perf] FPS validation started.");
        }
    }
}
#endif
