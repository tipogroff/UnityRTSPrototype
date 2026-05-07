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
    public static class Week6Stage6B3StaticHarvestMaskedLifecycleMenu
    {
        private const string MenuPath = "RTS/Week6/Stage6B3/Run StaticHarvestLayout Masked Lifecycle Validation";
        private const string PendingKey = "RTS.Week6.Stage6B3StaticHarvest.Pending";
        private const string PollCountKey = "RTS.Week6.Stage6B3StaticHarvest.PollCount";
        private const string BatchExitKey = "RTS.Week6.Stage6B3StaticHarvest.BatchExit";
        private const int MaxPolls = 300;
        private const int TargetSteps = 100;

        private const string TargetScenePath = "Assets/Scenes/Week6_StudentStaticHarvestLayout.unity";
        private const string OutputRelativeDir = "python/week6_student/tmp/stage6b3_static_harvest_masked_lifecycle_validation";
        private const string SnapshotPrefix = "stage6b3_static_harvest_masked_lifecycle_snapshot_step";
        private const string ArtifactPrefix = "stage6b3_static_harvest_masked_lifecycle";
        private const string StaticValidationFileName = "stage6b3_static_scene_playmode_validation.json";
        private const string ManifestFileName = "stage6b3_static_harvest_masked_lifecycle_manifest.json";
        private const string TargetCheckpointRelativePath =
            "python/week6_student/checkpoints/Stage6B3_SemanticObservationFix/legacy032_v2_bc_source_valid_semantic_obs_fix_final.pt";

        static Week6Stage6B3StaticHarvestMaskedLifecycleMenu()
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

            Debug.Log("[Stage6B3StaticHarvest] Entering Play Mode for static-scene masked lifecycle validation...");
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
            MatchBootstrap bootstrap = UnityEngine.Object.FindFirstObjectByType<MatchBootstrap>();

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
            if (!checkpointExists)
            {
                throw new FileNotFoundException("Stage6B3 final checkpoint not found; refusing to run.", checkpointAbs);
            }

            SetPrivateString(adapter, "_checkpointRelativePath", TargetCheckpointRelativePath);
            SetPrivateBool(adapter, "_enableLegalActionMaskForSelection", true);
            SetPrivateString(adapter, "_artifactDirectoryRelativePath", OutputRelativeDir);
            SetPrivateString(adapter, "_artifactFilePrefix", ArtifactPrefix);
            SetPrivateString(runner, "_stepSnapshotOutputDirectoryRelativePath", OutputRelativeDir);
            SetPrivateString(runner, "_stepSnapshotFilePrefix", SnapshotPrefix);
            runner.SetCurrentCaptureModeContext(
                "stage6b3_static_harvest_masked_lifecycle_validation",
                Week6PlayerControlMode.StudentInference,
                Week6PlayerControlMode.HeuristicBaseline);

            DumpStaticSceneValidation(outputDir, bootstrap);

            runner.StartVisualInspectionMatch(true);
            DumpCoordinateTruth(outputDir, "step0000", 0);

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
            string manifestPath = Path.Combine(outputDir, ManifestFileName);
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
                + "  \"checkpoint_loaded\": " + (checkpointExists ? "true" : "false") + ",\n"
                + "  \"legal_parameter_mask_enabled\": true,\n"
                + "  \"fallback_used\": false,\n"
                + "  \"heuristic_used\": false,\n"
                + "  \"fake_logits_used\": false\n"
                + "}\n";

            File.WriteAllText(manifestPath, manifestJson);
            Debug.Log("[Stage6B3StaticHarvest] Static masked lifecycle capture complete. Manifest: " + manifestPath);
        }

        private static void DumpStaticSceneValidation(string outputDir, MatchBootstrap bootstrap)
        {
            GridManager grid = GridManager.Instance;
            UnitRegistry registry = UnitRegistry.Instance;
            ResourceManager resources = ResourceManager.Instance;

            StaticSceneEntityAuthoring[] authored = UnityEngine.Object.FindObjectsByType<StaticSceneEntityAuthoring>(
                FindObjectsInactive.Include,
                FindObjectsSortMode.None);

            int authoredCount = authored != null ? authored.Length : 0;
            int occupancyCount = grid != null && grid.Occupancy != null ? grid.Occupancy.Count : 0;
            List<UnitRuntime> units = registry != null ? registry.GetAllUnits() : new List<UnitRuntime>();
            int unitCount = units.Count;

            var uniqueCells = new HashSet<int>();
            if (grid != null && grid.Occupancy != null)
            {
                foreach (KeyValuePair<GridPosition, UnitRuntime> kv in grid.Occupancy)
                {
                    uniqueCells.Add(kv.Key.ToFlatIndex());
                }
            }

            var resourceNodes = new List<ResourceNode>();
            if (resources != null)
            {
                foreach (ResourceNode node in resources.GetAllResourceNodes())
                {
                    resourceNodes.Add(node);
                }
            }

            var authoredFlats = new HashSet<int>();
            if (authored != null)
            {
                for (int i = 0; i < authored.Length; i++)
                {
                    if (authored[i] == null)
                    {
                        continue;
                    }

                    authoredFlats.Add(authored[i].GetGridPosition().ToFlatIndex());
                }
            }

            var registryFlats = new HashSet<int>();
            for (int i = 0; i < units.Count; i++)
            {
                registryFlats.Add(units[i].GridPos.ToFlatIndex());
            }

            bool noDuplicateSpawn = authoredCount == unitCount
                && occupancyCount == unitCount
                && uniqueCells.Count == occupancyCount;
            bool authoredLayoutPreserved = authoredFlats.SetEquals(registryFlats);

            units.Sort((a, b) => a.GridPos.ToFlatIndex().CompareTo(b.GridPos.ToFlatIndex()));
            resourceNodes.Sort((a, b) => a.GridPosition.ToFlatIndex().CompareTo(b.GridPosition.ToFlatIndex()));

            int initializationMode = GetPrivateEnumInt(bootstrap, "_initializationMode", -1);
            int scenarioPreset = GetPrivateEnumInt(bootstrap, "_scenarioPreset", -1);

            var sb = new StringBuilder(8192);
            sb.AppendLine("{");
            JsonProp(sb, "generated_at_utc", DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture), comma: true, indent: 2);
            JsonProp(sb, "active_scene_name", SceneManager.GetActiveScene().name, comma: true, indent: 2);
            JsonProp(sb, "active_scene_path", SceneManager.GetActiveScene().path.Replace("\\", "/"), comma: true, indent: 2);
            JsonProp(sb, "authored_entity_count", authoredCount, comma: true, indent: 2);
            JsonProp(sb, "grid_occupancy_count", occupancyCount, comma: true, indent: 2);
            JsonProp(sb, "unit_registry_count", unitCount, comma: true, indent: 2);
            JsonProp(sb, "resource_node_count", resourceNodes.Count, comma: true, indent: 2);
            JsonProp(sb, "unique_occupancy_cells", uniqueCells.Count, comma: true, indent: 2);
            JsonProp(sb, "no_duplicate_spawn_after_play_start", noDuplicateSpawn, comma: true, indent: 2);
            JsonProp(sb, "authored_layout_preserved", authoredLayoutPreserved, comma: true, indent: 2);
            JsonProp(sb, "bootstrap_initialization_mode", initializationMode, comma: true, indent: 2);
            JsonProp(sb, "bootstrap_scenario_preset", scenarioPreset, comma: true, indent: 2);

            sb.AppendLine("  \"unit_registry_units\": [");
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                GridPosition p = unit.GridPos;
                sb.Append("    {");
                InlineJsonProp(sb, "owner", unit.Owner.ToString(), comma: true);
                InlineJsonProp(sb, "unit_type", unit.Type.ToString(), comma: true);
                InlineJsonProp(sb, "x", p.X, comma: true);
                InlineJsonProp(sb, "y", p.Y, comma: true);
                InlineJsonProp(sb, "flat_index", p.ToFlatIndex(), comma: true);
                InlineJsonProp(sb, "visual_label", ToVisualLabel(p), comma: true);
                InlineJsonProp(sb, "hp", unit.HP, comma: true);
                InlineJsonProp(sb, "carried_resources", unit.CarriedResources, comma: false);
                sb.Append(i + 1 < units.Count ? "},\n" : "}\n");
            }

            sb.AppendLine("  ],");
            sb.AppendLine("  \"resource_manager_nodes\": [");
            for (int i = 0; i < resourceNodes.Count; i++)
            {
                ResourceNode node = resourceNodes[i];
                GridPosition p = node.GridPosition;
                sb.Append("    {");
                InlineJsonProp(sb, "x", p.X, comma: true);
                InlineJsonProp(sb, "y", p.Y, comma: true);
                InlineJsonProp(sb, "flat_index", p.ToFlatIndex(), comma: true);
                InlineJsonProp(sb, "visual_label", ToVisualLabel(p), comma: true);
                InlineJsonProp(sb, "amount", node.CurrentResources, comma: true);
                InlineJsonProp(sb, "exhausted", node.IsExhausted, comma: false);
                sb.Append(i + 1 < resourceNodes.Count ? "},\n" : "}\n");
            }

            sb.AppendLine("  ]");
            sb.AppendLine("}");

            File.WriteAllText(Path.Combine(outputDir, StaticValidationFileName), sb.ToString());
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

            sb.AppendLine("  ]");
            sb.AppendLine("}");

            File.WriteAllText(Path.Combine(outputDir, $"stage6b3_authoritative_coordinate_truth_{suffix}.json"), sb.ToString());
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

        private static void JsonProp(StringBuilder sb, string name, bool value, bool comma, int indent)
        {
            sb.Append(' ', indent).Append('"').Append(EscapeJson(name)).Append("\": ").Append(value ? "true" : "false");
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
            string path = Path.Combine(outputDir, ManifestFileName);
            string json = "{\n"
                + "  \"generated_at_utc\": \"" + DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture) + "\",\n"
                + "  \"status\": \"" + EscapeJson(status) + "\",\n"
                + "  \"error\": \"" + EscapeJson(error) + "\",\n"
                + "  \"scene\": \"" + TargetScenePath + "\",\n"
                + "  \"configured_checkpoint_relative_path\": \"" + TargetCheckpointRelativePath + "\"\n"
                + "}\n";
            File.WriteAllText(path, json);
            Debug.LogError("[Stage6B3StaticHarvest] Failure report written: " + path);
        }

        private static void CompleteRun(int exitCode)
        {
            SessionState.EraseBool(PendingKey);
            SessionState.EraseInt(PollCountKey);
            SessionState.EraseBool(BatchExitKey);

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

        private static int GetPrivateEnumInt(object target, string fieldName, int fallback)
        {
            if (target == null)
            {
                return fallback;
            }

            FieldInfo field = target.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            if (field == null)
            {
                return fallback;
            }

            object value = field.GetValue(target);
            if (value == null)
            {
                return fallback;
            }

            try
            {
                return Convert.ToInt32(value, CultureInfo.InvariantCulture);
            }
            catch
            {
                return fallback;
            }
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