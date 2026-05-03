#if UNITY_EDITOR
using System;
using System.IO;
using System.Reflection;
using RTS.Gameplay;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RTS.ML.Editor
{
    [InitializeOnLoad]
    public static class Week6Stage10D20UnityMaskedValidMoveRerunMenu
    {
        private const string MenuPath = "RTS/Week6/Stage10D20/Run Unity Masked Valid-Move Rerun";
        private const string PendingKey = "RTS.Week6.Stage10D20.Pending";
        private const string PollCountKey = "RTS.Week6.Stage10D20.PollCount";
        private const int MaxPolls = 300;
        private const int TargetSteps = 200;

        private const string TargetScenePath = "Assets/Scenes/Week6_StudentVisualInspection.unity";
        private const string OutputRelativeDir = "python/week6_student/tmp/stage10d20_masked_runtime_rerun";
        private const string SnapshotPrefix = "stage10d20_snapshot_step";
        private const string ArtifactPrefix = "stage10d20_masked_runtime";
        private const string TargetCheckpointRelativePath = "python/week6_student/runs/legacy032_v2_stage10d19b_valid_move_augmented_bc_20260503T192454Z/student_bc_stage10d19b_valid_move_best.pt";

        static Week6Stage10D20UnityMaskedValidMoveRerunMenu()
        {
            EditorApplication.playModeStateChanged -= HandlePlayModeStateChanged;
            EditorApplication.playModeStateChanged += HandlePlayModeStateChanged;
            EditorApplication.update -= PollPendingRun;
            EditorApplication.update += PollPendingRun;
        }

        [MenuItem(MenuPath)]
        public static void Run()
        {
            EnsureTargetSceneLoaded();

            SessionState.SetBool(PendingKey, true);
            SessionState.SetInt(PollCountKey, 0);

            if (Application.isPlaying)
            {
                ExecutePendingRun();
                return;
            }

            Debug.Log("[Stage10D20] Entering Play Mode for Unity masked valid-Move rerun...");
            EditorApplication.isPlaying = true;
        }

        private static void HandlePlayModeStateChanged(PlayModeStateChange change)
        {
            if (!SessionState.GetBool(PendingKey, false))
            {
                return;
            }

            if (change == PlayModeStateChange.EnteredPlayMode)
            {
                SessionState.SetInt(PollCountKey, 0);
            }

            if (change == PlayModeStateChange.ExitingPlayMode || change == PlayModeStateChange.EnteredEditMode)
            {
                SessionState.EraseBool(PendingKey);
                SessionState.EraseInt(PollCountKey);
            }
        }

        private static void PollPendingRun()
        {
            if (!SessionState.GetBool(PendingKey, false) || !Application.isPlaying)
            {
                return;
            }

            int polls = SessionState.GetInt(PollCountKey, 0) + 1;
            SessionState.SetInt(PollCountKey, polls);

            Week6VisualInspectionRunner runner = UnityEngine.Object.FindFirstObjectByType<Week6VisualInspectionRunner>();
            EpisodeController controller = UnityEngine.Object.FindFirstObjectByType<EpisodeController>();
            MatchManager matchManager = UnityEngine.Object.FindFirstObjectByType<MatchManager>();
            Week6StudentPolicyAdapter adapter = UnityEngine.Object.FindFirstObjectByType<Week6StudentPolicyAdapter>();

            if (runner == null || controller == null || matchManager == null || adapter == null)
            {
                if (polls < MaxPolls)
                {
                    return;
                }

                SessionState.EraseBool(PendingKey);
                SessionState.EraseInt(PollCountKey);
                Debug.LogError("[Stage10D20] Runtime references not ready in Play Mode.");
                EditorApplication.isPlaying = false;
                return;
            }

            ExecutePendingRun();
        }

        private static void ExecutePendingRun()
        {
            SessionState.EraseBool(PendingKey);
            SessionState.EraseInt(PollCountKey);

            bool shouldExitPlayMode = Application.isPlaying;
            try
            {
                RunControlledCapture();
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
            }
            finally
            {
                if (shouldExitPlayMode && Application.isPlaying)
                {
                    EditorApplication.isPlaying = false;
                }
            }
        }

        private static void RunControlledCapture()
        {
            Week6VisualInspectionRunner runner = UnityEngine.Object.FindFirstObjectByType<Week6VisualInspectionRunner>();
            EpisodeController controller = UnityEngine.Object.FindFirstObjectByType<EpisodeController>();
            MatchManager matchManager = UnityEngine.Object.FindFirstObjectByType<MatchManager>();
            Week6StudentPolicyAdapter adapter = UnityEngine.Object.FindFirstObjectByType<Week6StudentPolicyAdapter>();

            if (runner == null || controller == null || matchManager == null || adapter == null)
            {
                Debug.LogError("[Stage10D20] Missing runtime components.");
                return;
            }

            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? string.Empty;
            string outputDir = Path.GetFullPath(Path.Combine(projectRoot, OutputRelativeDir));
            Directory.CreateDirectory(outputDir);

            SetPrivateString(adapter, "_checkpointRelativePath", TargetCheckpointRelativePath);
            SetPrivateString(adapter, "_artifactDirectoryRelativePath", OutputRelativeDir);
            SetPrivateString(adapter, "_artifactFilePrefix", ArtifactPrefix);
            SetPrivateBool(adapter, "_enableLegalActionMaskForSelection", true);

            SetPrivateString(runner, "_stepSnapshotOutputDirectoryRelativePath", OutputRelativeDir);
            SetPrivateString(runner, "_stepSnapshotFilePrefix", SnapshotPrefix);

            runner.StartVisualInspectionMatch(true);

            int stepsCompleted = 0;
            for (int i = 0; i < TargetSteps; i++)
            {
                if (!controller.IsRunning)
                {
                    break;
                }

                runner.StepManualOnce();
                runner.DumpCurrentStepDiagnostics();
                stepsCompleted++;

                if (!controller.IsRunning)
                {
                    break;
                }
            }

            EpisodeEndReport terminal = controller.LastTerminalReport;
            string terminalReason = terminal.IsTerminal ? terminal.TerminalReason.ToString() : "none";
            string manifestPath = Path.Combine(outputDir, "stage10d20_run_manifest.json");
            string manifestJson = "{\n"
                + "  \"generated_at_utc\": \"" + DateTime.UtcNow.ToString("O") + "\",\n"
                + "  \"scene\": \"" + SceneManager.GetActiveScene().path.Replace("\\", "/") + "\",\n"
                + "  \"output_relative_dir\": \"" + OutputRelativeDir.Replace("\\", "/") + "\",\n"
                + "  \"snapshot_prefix\": \"" + SnapshotPrefix + "\",\n"
                + "  \"target_steps\": " + TargetSteps + ",\n"
                + "  \"steps_completed\": " + stepsCompleted + ",\n"
                + "  \"final_match_step\": " + matchManager.Step + ",\n"
                + "  \"terminal\": " + (terminal.IsTerminal ? "true" : "false") + ",\n"
                + "  \"terminal_reason\": \"" + terminalReason + "\",\n"
                + "  \"configured_checkpoint_relative_path\": \"" + TargetCheckpointRelativePath.Replace("\\", "/") + "\",\n"
                + "  \"configured_legal_mask_enabled\": true\n"
                + "}\n";

            File.WriteAllText(manifestPath, manifestJson);
            Debug.Log("[Stage10D20] Unity masked valid-Move rerun capture complete. Manifest: " + manifestPath);
        }

        private static void EnsureTargetSceneLoaded()
        {
            Scene scene = SceneManager.GetActiveScene();
            if (scene.IsValid() && string.Equals(scene.path, TargetScenePath, StringComparison.Ordinal))
            {
                return;
            }

            if (Application.isPlaying)
            {
                throw new InvalidOperationException("Cannot switch scene while in Play Mode.");
            }

            if (EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo())
            {
                EditorSceneManager.OpenScene(TargetScenePath, OpenSceneMode.Single);
            }
            else
            {
                throw new InvalidOperationException("Scene switch canceled by user.");
            }
        }

        private static void SetPrivateString(object target, string fieldName, string value)
        {
            FieldInfo field = target.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            if (field == null || field.FieldType != typeof(string))
            {
                throw new MissingFieldException(target.GetType().Name, fieldName);
            }

            field.SetValue(target, value ?? string.Empty);
        }

        private static void SetPrivateBool(object target, string fieldName, bool value)
        {
            FieldInfo field = target.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            if (field == null || field.FieldType != typeof(bool))
            {
                throw new MissingFieldException(target.GetType().Name, fieldName);
            }

            field.SetValue(target, value);
        }
    }
}
#endif
