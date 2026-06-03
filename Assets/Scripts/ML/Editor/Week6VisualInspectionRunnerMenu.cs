using RTS.ML;
using UnityEditor;
using UnityEngine;

namespace RTS.ML.Editor
{
    public static class Week6VisualInspectionRunnerMenu
    {
        [MenuItem("RTS/Week6/Visual Inspection/Start Or Restart")]
        private static void StartOrRestart()
        {
            if (!EditorApplication.isPlaying)
            {
                Debug.LogWarning("[Week6VisualInspectionRunnerMenu] Enter Play Mode first.");
                return;
            }

            Week6VisualInspectionRunner runner = Object.FindFirstObjectByType<Week6VisualInspectionRunner>();
            if (runner == null)
            {
                Debug.LogWarning("[Week6VisualInspectionRunnerMenu] Week6VisualInspectionRunner not found in scene.");
                return;
            }

            runner.RestartVisualInspectionMatch();
        }

        [MenuItem("RTS/Week6/Visual Inspection/Step Once")]
        private static void StepOnce()
        {
            if (!EditorApplication.isPlaying)
            {
                Debug.LogWarning("[Week6VisualInspectionRunnerMenu] Enter Play Mode first.");
                return;
            }

            Week6VisualInspectionRunner runner = Object.FindFirstObjectByType<Week6VisualInspectionRunner>();
            if (runner == null)
            {
                Debug.LogWarning("[Week6VisualInspectionRunnerMenu] Week6VisualInspectionRunner not found in scene.");
                return;
            }

            runner.StepManualOnce();
        }

        [MenuItem("RTS/Week6/Visual Inspection/Toggle Pause")]
        private static void TogglePause()
        {
            if (!EditorApplication.isPlaying)
            {
                Debug.LogWarning("[Week6VisualInspectionRunnerMenu] Enter Play Mode first.");
                return;
            }

            Week6VisualInspectionRunner runner = Object.FindFirstObjectByType<Week6VisualInspectionRunner>();
            if (runner == null)
            {
                Debug.LogWarning("[Week6VisualInspectionRunnerMenu] Week6VisualInspectionRunner not found in scene.");
                return;
            }

            runner.TogglePauseResume();
        }

        [MenuItem("RTS/Week6/Visual Inspection/Dump Snapshot")]
        private static void DumpSnapshot()
        {
            if (!EditorApplication.isPlaying)
            {
                Debug.LogWarning("[Week6VisualInspectionRunnerMenu] Enter Play Mode first.");
                return;
            }

            Week6VisualInspectionRunner runner = Object.FindFirstObjectByType<Week6VisualInspectionRunner>();
            if (runner == null)
            {
                Debug.LogWarning("[Week6VisualInspectionRunnerMenu] Week6VisualInspectionRunner not found in scene.");
                return;
            }

            runner.DumpCurrentStepDiagnostics();
        }

        [MenuItem("RTS/Week6/Visual Inspection/Enable Auto Visual Playback")]
        private static void EnableAutoVisualPlayback()
        {
            if (!EditorApplication.isPlaying)
            {
                Debug.LogWarning("[Week6VisualInspectionRunnerMenu] Enter Play Mode first.");
                return;
            }

            Week6VisualInspectionRunner runner = Object.FindFirstObjectByType<Week6VisualInspectionRunner>();
            if (runner == null)
            {
                Debug.LogWarning("[Week6VisualInspectionRunnerMenu] Week6VisualInspectionRunner not found in scene.");
                return;
            }

            runner.SetAutoVisualPlaybackEnabled(true);
            Debug.Log("[Week6VisualInspectionRunnerMenu] Auto visual playback enabled.");
        }

        [MenuItem("RTS/Week6/Visual Inspection/Disable Auto Visual Playback")]
        private static void DisableAutoVisualPlayback()
        {
            if (!EditorApplication.isPlaying)
            {
                Debug.LogWarning("[Week6VisualInspectionRunnerMenu] Enter Play Mode first.");
                return;
            }

            Week6VisualInspectionRunner runner = Object.FindFirstObjectByType<Week6VisualInspectionRunner>();
            if (runner == null)
            {
                Debug.LogWarning("[Week6VisualInspectionRunnerMenu] Week6VisualInspectionRunner not found in scene.");
                return;
            }

            runner.SetAutoVisualPlaybackEnabled(false);
            Debug.Log("[Week6VisualInspectionRunnerMenu] Auto visual playback disabled.");
        }

        [MenuItem("RTS/Week6/Visual Inspection/Run 10 Visual Steps")]
        private static void RunTenVisualSteps()
        {
            if (!EditorApplication.isPlaying)
            {
                Debug.LogWarning("[Week6VisualInspectionRunnerMenu] Enter Play Mode first.");
                return;
            }

            Week6VisualInspectionRunner runner = Object.FindFirstObjectByType<Week6VisualInspectionRunner>();
            if (runner == null)
            {
                Debug.LogWarning("[Week6VisualInspectionRunnerMenu] Week6VisualInspectionRunner not found in scene.");
                return;
            }

            runner.RunVisualPlaybackSteps(10);
        }

        [MenuItem("RTS/Week6/Visual Inspection/Run Until Terminal Or 100 Steps")]
        private static void RunUntilTerminalOrHundredSteps()
        {
            if (!EditorApplication.isPlaying)
            {
                Debug.LogWarning("[Week6VisualInspectionRunnerMenu] Enter Play Mode first.");
                return;
            }

            Week6VisualInspectionRunner runner = Object.FindFirstObjectByType<Week6VisualInspectionRunner>();
            if (runner == null)
            {
                Debug.LogWarning("[Week6VisualInspectionRunnerMenu] Week6VisualInspectionRunner not found in scene.");
                return;
            }

            runner.RunVisualPlaybackUntilTerminalOrLimit(100);
        }
    }
}
