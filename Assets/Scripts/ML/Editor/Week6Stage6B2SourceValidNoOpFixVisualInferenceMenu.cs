#if UNITY_EDITOR
using System;
using System.Globalization;
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
    public static class Week6Stage6B2SourceValidNoOpFixVisualInferenceMenu
    {
        private const string MenuPath = "RTS/Week6/Stage6B2/Run Source-Valid NoOpFix Visual Inference";
        private const string PendingKey = "RTS.Week6.Stage6B2SourceValidNoOpFix.Pending";
        private const string PollCountKey = "RTS.Week6.Stage6B2SourceValidNoOpFix.PollCount";
        private const string BatchExitKey = "RTS.Week6.Stage6B2SourceValidNoOpFix.BatchExit";
        private const int MaxPolls = 300;
        private const int TargetSteps = 12;

        private const string TargetScenePath = "Assets/Scenes/Week6_StudentVisualInspection.unity";
        private const string OutputRelativeDir = "python/week6_student/tmp/stage6b2_source_valid_noopfix_visual_inference";
        private const string SnapshotPrefix = "stage6b2_source_valid_noopfix_snapshot_step";
        private const string ArtifactPrefix = "stage6b2_source_valid_noopfix";
        private const string TargetCheckpointRelativePath =
            "python/week6_student/runs/Stage6B2_SourceValidNoOpFix/legacy032_v2_bc_source_valid_noop_fix_best.pt";

        static Week6Stage6B2SourceValidNoOpFixVisualInferenceMenu()
        {
            EditorApplication.playModeStateChanged -= HandlePlayModeStateChanged;
            EditorApplication.playModeStateChanged += HandlePlayModeStateChanged;
            EditorApplication.update -= PollPendingRun;
            EditorApplication.update += PollPendingRun;
        }

        [MenuItem(MenuPath)]
        public static void Run()
        {
            RunInternal(exitEditorOnComplete: false);
        }

        public static void RunBatchmode()
        {
            RunInternal(exitEditorOnComplete: true);
        }

        private static void RunInternal(bool exitEditorOnComplete)
        {
            EnsureTargetSceneLoaded();

            SessionState.SetBool(PendingKey, true);
            SessionState.SetInt(PollCountKey, 0);
            SessionState.SetBool(BatchExitKey, exitEditorOnComplete);

            if (Application.isPlaying)
            {
                ExecutePendingRun();
                return;
            }

            Debug.Log("[Stage6B2SourceValidNoOpFix] Entering Play Mode for visual inference verification...");
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

                WriteFailureReport("runtime_references_not_ready", "Required runtime components were not found in Play Mode.");
                CompleteRun(exitCode: 1);
                return;
            }

            ExecutePendingRun();
        }

        private static void ExecutePendingRun()
        {
            bool exitOnComplete = SessionState.GetBool(BatchExitKey, false);
            SessionState.EraseBool(PendingKey);
            SessionState.EraseInt(PollCountKey);
            SessionState.EraseBool(BatchExitKey);

            int exitCode = 0;
            try
            {
                RunControlledCapture();
            }
            catch (Exception ex)
            {
                Debug.LogException(ex);
                WriteFailureReport("exception", ex.ToString());
                exitCode = 1;
            }
            finally
            {
                if (Application.isPlaying)
                {
                    EditorApplication.isPlaying = false;
                }

                if (exitOnComplete || Application.isBatchMode)
                {
                    int capturedExitCode = exitCode;
                    EditorApplication.delayCall += () => EditorApplication.Exit(capturedExitCode);
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
                WriteFailureReport("runtime_components_missing", "Missing runner/controller/matchManager/adapter.");
                return;
            }

            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? string.Empty;
            string outputDir = Path.GetFullPath(Path.Combine(projectRoot, OutputRelativeDir));
            Directory.CreateDirectory(outputDir);

            string checkpointAbs = Path.GetFullPath(Path.Combine(projectRoot, TargetCheckpointRelativePath));
            bool checkpointExists = File.Exists(checkpointAbs);
            bool legalMaskPreserved = GetPrivateBool(adapter, "_enableLegalActionMaskForSelection", false);

            SetPrivateString(adapter, "_checkpointRelativePath", TargetCheckpointRelativePath);
            SetPrivateString(adapter, "_artifactDirectoryRelativePath", OutputRelativeDir);
            SetPrivateString(adapter, "_artifactFilePrefix", ArtifactPrefix);
            SetPrivateString(runner, "_stepSnapshotOutputDirectoryRelativePath", OutputRelativeDir);
            SetPrivateString(runner, "_stepSnapshotFilePrefix", SnapshotPrefix);
            runner.SetCurrentCaptureModeContext(
                "stage6b2_source_valid_noopfix_visual_inference",
                Week6PlayerControlMode.StudentInference,
                Week6PlayerControlMode.HeuristicBaseline);

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
            string manifestPath = Path.Combine(outputDir, "stage6b2_source_valid_noopfix_run_manifest.json");
            string manifestJson = "{\n"
                + "  \"generated_at_utc\": \"" + DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture) + "\",\n"
                + "  \"scene\": \"" + SceneManager.GetActiveScene().path.Replace("\\", "/") + "\",\n"
                + "  \"scene_name\": \"" + SceneManager.GetActiveScene().name + "\",\n"
                + "  \"output_relative_dir\": \"" + OutputRelativeDir + "\",\n"
                + "  \"snapshot_prefix\": \"" + SnapshotPrefix + "\",\n"
                + "  \"artifact_prefix\": \"" + ArtifactPrefix + "\",\n"
                + "  \"target_steps\": " + TargetSteps + ",\n"
                + "  \"steps_completed\": " + stepsCompleted + ",\n"
                + "  \"final_match_step\": " + matchManager.Step + ",\n"
                + "  \"terminal\": " + (terminal.IsTerminal ? "true" : "false") + ",\n"
                + "  \"terminal_reason\": \"" + (terminal.IsTerminal ? terminal.TerminalReason.ToString() : "none") + "\",\n"
                + "  \"configured_checkpoint_relative_path\": \"" + TargetCheckpointRelativePath + "\",\n"
                + "  \"configured_checkpoint_absolute_path\": \"" + EscapeJson(checkpointAbs) + "\",\n"
                + "  \"checkpoint_exists\": " + (checkpointExists ? "true" : "false") + ",\n"
                + "  \"legal_action_mask_enabled_preserved\": " + (legalMaskPreserved ? "true" : "false") + "\n"
                + "}\n";

            File.WriteAllText(manifestPath, manifestJson);
            Debug.Log("[Stage6B2SourceValidNoOpFix] Visual inference capture complete. Manifest: " + manifestPath);
        }

        private static void WriteFailureReport(string status, string error)
        {
            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? string.Empty;
            string outputDir = Path.GetFullPath(Path.Combine(projectRoot, OutputRelativeDir));
            Directory.CreateDirectory(outputDir);
            string path = Path.Combine(outputDir, "stage6b2_source_valid_noopfix_run_manifest.json");
            string json = "{\n"
                + "  \"generated_at_utc\": \"" + DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture) + "\",\n"
                + "  \"status\": \"" + EscapeJson(status) + "\",\n"
                + "  \"error\": \"" + EscapeJson(error) + "\",\n"
                + "  \"scene\": \"" + TargetScenePath + "\",\n"
                + "  \"configured_checkpoint_relative_path\": \"" + TargetCheckpointRelativePath + "\"\n"
                + "}\n";
            File.WriteAllText(path, json);
            Debug.LogError("[Stage6B2SourceValidNoOpFix] Failure report written: " + path);
        }

        private static void CompleteRun(int exitCode)
        {
            SessionState.EraseBool(PendingKey);
            SessionState.EraseInt(PollCountKey);
            bool exitOnComplete = SessionState.GetBool(BatchExitKey, false);
            SessionState.EraseBool(BatchExitKey);

            if (Application.isPlaying)
            {
                EditorApplication.isPlaying = false;
            }

            if (exitOnComplete || Application.isBatchMode)
            {
                EditorApplication.delayCall += () => EditorApplication.Exit(exitCode);
            }
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

            EditorSceneManager.OpenScene(TargetScenePath, OpenSceneMode.Single);
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

        private static bool GetPrivateBool(object target, string fieldName, bool fallback)
        {
            FieldInfo field = target.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            if (field == null || field.FieldType != typeof(bool))
            {
                return fallback;
            }

            object value = field.GetValue(target);
            return value is bool cast ? cast : fallback;
        }

        private static string EscapeJson(string value)
        {
            return (value ?? string.Empty).Replace("\\", "\\\\").Replace("\"", "\\\"");
        }
    }
}
#endif
