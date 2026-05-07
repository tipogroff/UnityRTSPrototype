#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Reflection;
using System.Text;
using RTS.Core;
using RTS.Gameplay;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RTS.ML.Editor
{
    [InitializeOnLoad]
    public static class Week6Stage6B3SemanticObservationFixVisualInferenceMenu
    {
        private const string MenuPath = "RTS/Week6/Stage6B3/Run Semantic Observation Fix Visual Inference";
        private const string MaskedMenuPath = "RTS/Week6/Stage6B3/Run Action Parameter Mask Visual Inference";
        private const string MaskedLifecycleMenuPath = "RTS/Week6/Stage6B3/Run Masked Lifecycle Validation";
        private const string PendingKey = "RTS.Week6.Stage6B3SemanticObservationFix.Pending";
        private const string PollCountKey = "RTS.Week6.Stage6B3SemanticObservationFix.PollCount";
        private const string BatchExitKey = "RTS.Week6.Stage6B3SemanticObservationFix.BatchExit";
        private const string LegalMaskKey = "RTS.Week6.Stage6B3SemanticObservationFix.EnableLegalMask";
        private const string TargetStepsKey = "RTS.Week6.Stage6B3SemanticObservationFix.TargetSteps";
        private const string OutputDirKey = "RTS.Week6.Stage6B3SemanticObservationFix.OutputDir";
        private const string SnapshotPrefixKey = "RTS.Week6.Stage6B3SemanticObservationFix.SnapshotPrefix";
        private const string ArtifactPrefixKey = "RTS.Week6.Stage6B3SemanticObservationFix.ArtifactPrefix";
        private const string CaptureModeKey = "RTS.Week6.Stage6B3SemanticObservationFix.CaptureMode";
        private const int MaxPolls = 300;
        private const int DefaultTargetSteps = 12;
        private const int LifecycleTargetSteps = 100;

        private const string TargetScenePath = "Assets/Scenes/Week6_StudentVisualInspection.unity";
        private const string OutputRelativeDir = "python/week6_student/tmp/stage6b3_semantic_obs_fix_visual_inference";
        private const string MaskedOutputRelativeDir = "python/week6_student/tmp/stage6b3_action_parameter_mask_visual_inference";
        private const string MaskedLifecycleOutputRelativeDir = "python/week6_student/tmp/stage6b3_masked_lifecycle_validation";
        private const string SnapshotPrefix = "stage6b3_semantic_obs_fix_snapshot_step";
        private const string MaskedSnapshotPrefix = "stage6b3_action_parameter_mask_snapshot_step";
        private const string MaskedLifecycleSnapshotPrefix = "stage6b3_masked_lifecycle_snapshot_step";
        private const string ArtifactPrefix = "stage6b3_semantic_obs_fix";
        private const string MaskedArtifactPrefix = "stage6b3_action_parameter_mask";
        private const string MaskedLifecycleArtifactPrefix = "stage6b3_masked_lifecycle";
        private const string TargetCheckpointRelativePath =
            "python/week6_student/checkpoints/Stage6B3_SemanticObservationFix/legacy032_v2_bc_source_valid_semantic_obs_fix_final.pt";

        static Week6Stage6B3SemanticObservationFixVisualInferenceMenu()
        {
            EditorApplication.playModeStateChanged -= HandlePlayModeStateChanged;
            EditorApplication.playModeStateChanged += HandlePlayModeStateChanged;
            EditorApplication.update -= PollPendingRun;
            EditorApplication.update += PollPendingRun;
        }

        [MenuItem(MenuPath)]
        public static void Run()
        {
            RunInternal(exitEditorOnComplete: false, enableLegalMask: false, targetSteps: DefaultTargetSteps);
        }

        [MenuItem(MaskedMenuPath)]
        public static void RunMasked()
        {
            RunInternal(exitEditorOnComplete: false, enableLegalMask: true, targetSteps: DefaultTargetSteps);
        }

        [MenuItem(MaskedLifecycleMenuPath)]
        public static void RunMaskedLifecycle()
        {
            RunInternal(
                exitEditorOnComplete: false,
                enableLegalMask: true,
                targetSteps: LifecycleTargetSteps,
                outputRelativeDirOverride: MaskedLifecycleOutputRelativeDir,
                snapshotPrefixOverride: MaskedLifecycleSnapshotPrefix,
                artifactPrefixOverride: MaskedLifecycleArtifactPrefix,
                captureModeOverride: "stage6b3_masked_lifecycle_validation");
        }

        public static void RunBatchmode()
        {
            RunInternal(exitEditorOnComplete: true, enableLegalMask: false, targetSteps: DefaultTargetSteps);
        }

        public static void RunMaskedBatchmode()
        {
            RunInternal(exitEditorOnComplete: true, enableLegalMask: true, targetSteps: DefaultTargetSteps);
        }

        public static void RunMaskedLifecycleBatchmode()
        {
            RunInternal(
                exitEditorOnComplete: true,
                enableLegalMask: true,
                targetSteps: LifecycleTargetSteps,
                outputRelativeDirOverride: MaskedLifecycleOutputRelativeDir,
                snapshotPrefixOverride: MaskedLifecycleSnapshotPrefix,
                artifactPrefixOverride: MaskedLifecycleArtifactPrefix,
                captureModeOverride: "stage6b3_masked_lifecycle_validation");
        }

        private static void RunInternal(
            bool exitEditorOnComplete,
            bool enableLegalMask,
            int targetSteps,
            string outputRelativeDirOverride = "",
            string snapshotPrefixOverride = "",
            string artifactPrefixOverride = "",
            string captureModeOverride = "")
        {
            EnsureTargetSceneLoaded();

            SessionState.SetBool(PendingKey, true);
            SessionState.SetInt(PollCountKey, 0);
            SessionState.SetBool(BatchExitKey, exitEditorOnComplete);
            SessionState.SetBool(LegalMaskKey, enableLegalMask);
            SessionState.SetInt(TargetStepsKey, Mathf.Max(1, targetSteps));
            SessionState.SetString(OutputDirKey, outputRelativeDirOverride ?? string.Empty);
            SessionState.SetString(SnapshotPrefixKey, snapshotPrefixOverride ?? string.Empty);
            SessionState.SetString(ArtifactPrefixKey, artifactPrefixOverride ?? string.Empty);
            SessionState.SetString(CaptureModeKey, captureModeOverride ?? string.Empty);

            if (Application.isPlaying)
            {
                ExecutePendingRun();
                return;
            }

            Debug.Log("[Stage6B3SemanticObservationFix] Entering Play Mode for visual inference verification...");
            EditorApplication.isPlaying = true;
        }

        private static void HandlePlayModeStateChanged(PlayModeStateChange change)
        {
            if (SessionState.GetBool(PendingKey, false) && change == PlayModeStateChange.EnteredPlayMode)
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

            if (UnityEngine.Object.FindFirstObjectByType<Week6VisualInspectionRunner>() == null
                || UnityEngine.Object.FindFirstObjectByType<EpisodeController>() == null
                || UnityEngine.Object.FindFirstObjectByType<MatchManager>() == null
                || UnityEngine.Object.FindFirstObjectByType<Week6StudentPolicyAdapter>() == null)
            {
                if (polls < MaxPolls)
                {
                    return;
                }

                WriteFailureReport("runtime_references_not_ready", "Required runtime components were not found in Play Mode.");
                CompleteRun(1);
                return;
            }

            ExecutePendingRun();
        }

        private static void ExecutePendingRun()
        {
            bool exitOnComplete = SessionState.GetBool(BatchExitKey, false);
            bool enableLegalMask = SessionState.GetBool(LegalMaskKey, false);
            int targetSteps = SessionState.GetInt(TargetStepsKey, DefaultTargetSteps);
            string outputDirOverride = SessionState.GetString(OutputDirKey, string.Empty);
            string snapshotPrefixOverride = SessionState.GetString(SnapshotPrefixKey, string.Empty);
            string artifactPrefixOverride = SessionState.GetString(ArtifactPrefixKey, string.Empty);
            string captureModeOverride = SessionState.GetString(CaptureModeKey, string.Empty);
            SessionState.EraseBool(PendingKey);
            SessionState.EraseInt(PollCountKey);
            SessionState.EraseBool(BatchExitKey);
            SessionState.EraseBool(LegalMaskKey);
            SessionState.EraseInt(TargetStepsKey);
            SessionState.EraseString(OutputDirKey);
            SessionState.EraseString(SnapshotPrefixKey);
            SessionState.EraseString(ArtifactPrefixKey);
            SessionState.EraseString(CaptureModeKey);

            int exitCode = 0;
            try
            {
                RunControlledCapture(
                    enableLegalMask,
                    Mathf.Max(1, targetSteps),
                    outputDirOverride,
                    snapshotPrefixOverride,
                    artifactPrefixOverride,
                    captureModeOverride);
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

        private static void RunControlledCapture(
            bool enableLegalMask,
            int targetSteps,
            string outputRelativeDirOverride,
            string snapshotPrefixOverride,
            string artifactPrefixOverride,
            string captureModeOverride)
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
            string outputRelativeDir = !string.IsNullOrWhiteSpace(outputRelativeDirOverride)
                ? outputRelativeDirOverride
                : (enableLegalMask ? MaskedOutputRelativeDir : OutputRelativeDir);
            string snapshotPrefix = !string.IsNullOrWhiteSpace(snapshotPrefixOverride)
                ? snapshotPrefixOverride
                : (enableLegalMask ? MaskedSnapshotPrefix : SnapshotPrefix);
            string artifactPrefix = !string.IsNullOrWhiteSpace(artifactPrefixOverride)
                ? artifactPrefixOverride
                : (enableLegalMask ? MaskedArtifactPrefix : ArtifactPrefix);
            string outputDir = Path.GetFullPath(Path.Combine(projectRoot, outputRelativeDir));
            Directory.CreateDirectory(outputDir);

            string checkpointAbs = Path.GetFullPath(Path.Combine(projectRoot, TargetCheckpointRelativePath));
            bool checkpointExists = File.Exists(checkpointAbs);
            bool legalMaskPreserved = GetPrivateBool(adapter, "_enableLegalActionMaskForSelection", false);

            if (!checkpointExists)
            {
                throw new FileNotFoundException("Stage6B3 final checkpoint not found; refusing to fall back.", checkpointAbs);
            }

            SetPrivateString(adapter, "_checkpointRelativePath", TargetCheckpointRelativePath);
            SetPrivateBool(adapter, "_enableLegalActionMaskForSelection", enableLegalMask);
            SetPrivateString(adapter, "_artifactDirectoryRelativePath", outputRelativeDir);
            SetPrivateString(adapter, "_artifactFilePrefix", artifactPrefix);
            SetPrivateString(runner, "_stepSnapshotOutputDirectoryRelativePath", outputRelativeDir);
            SetPrivateString(runner, "_stepSnapshotFilePrefix", snapshotPrefix);
            runner.SetCurrentCaptureModeContext(
                !string.IsNullOrWhiteSpace(captureModeOverride)
                    ? captureModeOverride
                    : enableLegalMask
                    ? "stage6b3_action_parameter_mask_visual_inference"
                    : "stage6b3_semantic_obs_fix_visual_inference",
                Week6PlayerControlMode.StudentInference,
                Week6PlayerControlMode.HeuristicBaseline);

            runner.StartVisualInspectionMatch(true);
            DumpCoordinateTruth(outputDir, "step0000", 0);

            int stepsCompleted = 0;
            for (int i = 0; i < targetSteps; i++)
            {
                if (!controller.IsRunning)
                {
                    break;
                }

                runner.StepManualOnce();
                runner.DumpCurrentStepDiagnostics();
                stepsCompleted++;
                if (stepsCompleted == 1)
                {
                    DumpCoordinateTruth(outputDir, "step0001", 1);
                }

                if (!controller.IsRunning)
                {
                    break;
                }
            }

            if (stepsCompleted > 1)
            {
                DumpCoordinateTruth(outputDir, "step" + stepsCompleted.ToString("D4", CultureInfo.InvariantCulture), stepsCompleted);
            }

            EpisodeEndReport terminal = controller.LastTerminalReport;
            string manifestPath = Path.Combine(outputDir, "stage6b3_semantic_obs_fix_run_manifest.json");
            string manifestJson = "{\n"
                + "  \"generated_at_utc\": \"" + DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture) + "\",\n"
                + "  \"scene\": \"" + SceneManager.GetActiveScene().path.Replace("\\", "/") + "\",\n"
                + "  \"scene_name\": \"" + SceneManager.GetActiveScene().name + "\",\n"
                + "  \"output_relative_dir\": \"" + outputRelativeDir + "\",\n"
                + "  \"snapshot_prefix\": \"" + snapshotPrefix + "\",\n"
                + "  \"artifact_prefix\": \"" + artifactPrefix + "\",\n"
                + "  \"target_steps\": " + targetSteps + ",\n"
                + "  \"steps_completed\": " + stepsCompleted + ",\n"
                + "  \"final_match_step\": " + matchManager.Step + ",\n"
                + "  \"terminal\": " + (terminal.IsTerminal ? "true" : "false") + ",\n"
                + "  \"terminal_reason\": \"" + (terminal.IsTerminal ? terminal.TerminalReason.ToString() : "none") + "\",\n"
                + "  \"configured_checkpoint_relative_path\": \"" + TargetCheckpointRelativePath + "\",\n"
                + "  \"configured_checkpoint_absolute_path\": \"" + EscapeJson(checkpointAbs) + "\",\n"
                + "  \"checkpoint_exists\": " + (checkpointExists ? "true" : "false") + ",\n"
                + "  \"legal_action_mask_enabled_preserved\": " + (legalMaskPreserved ? "true" : "false") + ",\n"
                + "  \"legal_action_mask_enabled_requested\": " + (enableLegalMask ? "true" : "false") + "\n"
                + "}\n";

            File.WriteAllText(manifestPath, manifestJson);
            Debug.Log("[Stage6B3SemanticObservationFix] Visual inference capture complete. Manifest: " + manifestPath);
        }

        private static void DumpCoordinateTruth(string outputDir, string suffix, int stepIndex)
        {
            GridManager grid = GridManager.Instance;
            UnitRegistry registry = UnitRegistry.Instance;
            ResourceManager resources = ResourceManager.Instance;
            if (grid == null || registry == null || resources == null)
            {
                return;
            }

            var observationBuilder = new ObservationBuilder(grid, registry, resources);
            float[] obs = observationBuilder.BuildObservation(Owner.Player1, ObservationMode.UnityMvpTransfer);
            var sb = new StringBuilder(8192);
            sb.AppendLine("{");
            JsonProp(sb, "generated_at_utc", DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture), comma: true, indent: 2);
            JsonProp(sb, "step_index", stepIndex, comma: true, indent: 2);
            JsonProp(sb, "flat_formula", "flat = y * 24 + x", comma: true, indent: 2);
            JsonProp(sb, "visual_label_semantics", "letters are x/columns, numbers are y+1 rows; A1 means x=0,y=0", comma: true, indent: 2);
            JsonProp(sb, "direction_semantics", "0=North(+Y),1=East(+X),2=South(-Y),3=West(-X)", comma: true, indent: 2);

            sb.AppendLine("  \"resource_manager_nodes\": [");
            List<ResourceNode> nodes = new List<ResourceNode>(resources.GetAllResourceNodes());
            nodes.Sort((a, b) => a.GridPosition.ToFlatIndex().CompareTo(b.GridPosition.ToFlatIndex()));
            for (int i = 0; i < nodes.Count; i++)
            {
                ResourceNode node = nodes[i];
                GridPosition p = node.GridPosition;
                sb.Append("    {");
                InlineJsonProp(sb, "x", p.X, comma: true);
                InlineJsonProp(sb, "y", p.Y, comma: true);
                InlineJsonProp(sb, "flat", p.ToFlatIndex(), comma: true);
                InlineJsonProp(sb, "visual_label", ToVisualLabel(p), comma: true);
                InlineJsonProp(sb, "current_resources", node.CurrentResources, comma: true);
                InlineJsonProp(sb, "is_exhausted", node.IsExhausted, comma: false);
                sb.Append(i + 1 < nodes.Count ? "},\n" : "}\n");
            }
            sb.AppendLine("  ],");

            sb.AppendLine("  \"unit_registry_units\": [");
            List<UnitRuntime> units = registry.GetAllUnits();
            units.Sort((a, b) => a.GridPos.ToFlatIndex().CompareTo(b.GridPos.ToFlatIndex()));
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                GridPosition p = unit.GridPos;
                sb.Append("    {");
                InlineJsonProp(sb, "x", p.X, comma: true);
                InlineJsonProp(sb, "y", p.Y, comma: true);
                InlineJsonProp(sb, "flat", p.ToFlatIndex(), comma: true);
                InlineJsonProp(sb, "visual_label", ToVisualLabel(p), comma: true);
                InlineJsonProp(sb, "owner", unit.Owner.ToString(), comma: true);
                InlineJsonProp(sb, "unit_type", unit.Type.ToString(), comma: true);
                InlineJsonProp(sb, "hp", unit.HP, comma: true);
                InlineJsonProp(sb, "carried_resources", unit.CarriedResources, comma: false);
                sb.Append(i + 1 < units.Count ? "},\n" : "}\n");
            }
            sb.AppendLine("  ],");

            GridPosition b2 = new GridPosition(1, 1);
            sb.AppendLine("  \"b2_worker_neighbors\": [");
            Direction[] dirs = { Direction.North, Direction.East, Direction.South, Direction.West };
            for (int i = 0; i < dirs.Length; i++)
            {
                Direction dir = dirs[i];
                GridPosition target = b2.Neighbour(dir);
                bool inside = grid.IsInside(target);
                ResourceNode node = inside ? resources.GetResourceNode(target) : null;
                UnitRuntime occupant = inside ? grid.GetOccupant(target) : null;
                bool obsResource = inside && ObsChannel(obs, target, ObservationContract.CH_UNIT_TYPE_BASE) > 0.5f;
                sb.Append("    {");
                InlineJsonProp(sb, "direction_index", (int)dir, comma: true);
                InlineJsonProp(sb, "direction", dir.ToString(), comma: true);
                InlineJsonProp(sb, "x", target.X, comma: true);
                InlineJsonProp(sb, "y", target.Y, comma: true);
                InlineJsonProp(sb, "flat", inside ? target.ToFlatIndex() : -1, comma: true);
                InlineJsonProp(sb, "visual_label", inside ? ToVisualLabel(target) : "out_of_bounds", comma: true);
                InlineJsonProp(sb, "resource_manager_active_resource", node != null && !node.IsExhausted, comma: true);
                InlineJsonProp(sb, "observation_unit_resource", obsResource, comma: true);
                InlineJsonProp(sb, "grid_occupied", occupant != null, comma: true);
                InlineJsonProp(sb, "occupant", occupant != null ? occupant.Type.ToString() : "empty", comma: false);
                sb.Append(i + 1 < dirs.Length ? "},\n" : "}\n");
            }
            sb.AppendLine("  ]");
            sb.AppendLine("}");

            File.WriteAllText(Path.Combine(outputDir, $"stage6b3_authoritative_coordinate_truth_{suffix}.json"), sb.ToString());
        }

        private static float ObsChannel(float[] obs, GridPosition p, int channel)
        {
            int baseIndex = ObservationContract.FlatIndex(p.Y, p.X, 0);
            return baseIndex >= 0 && baseIndex + channel < obs.Length ? obs[baseIndex + channel] : 0f;
        }

        private static string ToVisualLabel(GridPosition p)
        {
            char col = (char)('A' + Mathf.Clamp(p.X, 0, 25));
            return col.ToString() + (p.Y + 1).ToString(CultureInfo.InvariantCulture);
        }

        private static void JsonProp(StringBuilder sb, string name, string value, bool comma, int indent)
        {
            sb.Append(' ', indent).Append('"').Append(EscapeJson(name)).Append("\": \"").Append(EscapeJson(value)).Append('"');
            sb.AppendLine(comma ? "," : string.Empty);
        }

        private static void JsonProp(StringBuilder sb, string name, int value, bool comma, int indent)
        {
            sb.Append(' ', indent).Append('"').Append(EscapeJson(name)).Append("\": ").Append(value.ToString(CultureInfo.InvariantCulture));
            sb.AppendLine(comma ? "," : string.Empty);
        }

        private static void InlineJsonProp(StringBuilder sb, string name, string value, bool comma)
        {
            sb.Append('"').Append(EscapeJson(name)).Append("\": \"").Append(EscapeJson(value)).Append('"');
            if (comma) sb.Append(", ");
        }

        private static void InlineJsonProp(StringBuilder sb, string name, int value, bool comma)
        {
            sb.Append('"').Append(EscapeJson(name)).Append("\": ").Append(value.ToString(CultureInfo.InvariantCulture));
            if (comma) sb.Append(", ");
        }

        private static void InlineJsonProp(StringBuilder sb, string name, bool value, bool comma)
        {
            sb.Append('"').Append(EscapeJson(name)).Append("\": ").Append(value ? "true" : "false");
            if (comma) sb.Append(", ");
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

        private static void WriteFailureReport(string status, string error)
        {
            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? string.Empty;
            string outputDir = Path.GetFullPath(Path.Combine(projectRoot, OutputRelativeDir));
            Directory.CreateDirectory(outputDir);
            string path = Path.Combine(outputDir, "stage6b3_semantic_obs_fix_run_manifest.json");
            string json = "{\n"
                + "  \"generated_at_utc\": \"" + DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture) + "\",\n"
                + "  \"status\": \"" + EscapeJson(status) + "\",\n"
                + "  \"error\": \"" + EscapeJson(error) + "\",\n"
                + "  \"scene\": \"" + TargetScenePath + "\",\n"
                + "  \"configured_checkpoint_relative_path\": \"" + TargetCheckpointRelativePath + "\"\n"
                + "}\n";
            File.WriteAllText(path, json);
            Debug.LogError("[Stage6B3SemanticObservationFix] Failure report written: " + path);
        }

        private static void CompleteRun(int exitCode)
        {
            SessionState.EraseBool(PendingKey);
            SessionState.EraseInt(PollCountKey);
            SessionState.EraseBool(BatchExitKey);
            SessionState.EraseBool(LegalMaskKey);

            if (Application.isPlaying)
            {
                EditorApplication.isPlaying = false;
            }

            if (Application.isBatchMode)
            {
                EditorApplication.delayCall += () => EditorApplication.Exit(exitCode);
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

        private static bool GetPrivateBool(object target, string fieldName, bool fallback)
        {
            FieldInfo field = target.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            return field != null && field.FieldType == typeof(bool) ? (bool)field.GetValue(target) : fallback;
        }

        private static string EscapeJson(string value)
        {
            return (value ?? string.Empty)
                .Replace("\\", "\\\\")
                .Replace("\"", "\\\"")
                .Replace("\r", "\\r")
                .Replace("\n", "\\n");
        }
    }
}
#endif
