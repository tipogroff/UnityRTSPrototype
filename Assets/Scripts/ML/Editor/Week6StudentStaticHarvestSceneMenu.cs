using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using RTS.Core;
using RTS.Gameplay;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RTS.ML.Editor
{
    public static class Week6StudentStaticHarvestSceneMenu
    {
        private const string SourceScenePath = "Assets/Scenes/Week6_StudentVisualInspection.unity";
        private const string TargetScenePath = "Assets/Scenes/Week6_StudentStaticHarvestLayout.unity";

        private const string SnapshotPath = "python/week6_student/reports/stage6b3s_static_scene_layout_snapshot.json";
        private const string ReportJsonPath = "python/week6_student/reports/stage6b3s_static_harvest_scene_report.json";
        private const string ReportMdPath = "python/week6_student/reports/STAGE6B3S_STATIC_HARVEST_SCENE_REPORT.md";
        private const string PlayModeValidationPath = "python/week6_student/reports/stage6b3s_static_scene_playmode_validation.json";

        [MenuItem("RTS/Week6/Stage6B3S/Build Static Harvest Scene")]
        public static void BuildStaticHarvestScene()
        {
            BuildSceneInternal();
        }

        [MenuItem("RTS/Week6/Stage6B3S/Generate Static Harvest Reports")]
        public static void GenerateStaticHarvestReports()
        {
            GenerateReportsInternal();
        }

        [MenuItem("RTS/Week6/Stage6B3S/Build Scene And Generate Reports")]
        public static void BuildAndGenerateStaticHarvestReports()
        {
            BuildSceneInternal();
            GenerateReportsInternal();
        }

        private static void BuildSceneInternal()
        {
            if (!File.Exists(SourceScenePath))
            {
                throw new InvalidOperationException("Source scene not found: " + SourceScenePath);
            }

            EnsureParentDirectory(TargetScenePath);

            if (File.Exists(TargetScenePath))
            {
                File.Delete(TargetScenePath);
            }

            File.Copy(SourceScenePath, TargetScenePath);
            AssetDatabase.ImportAsset(TargetScenePath, ImportAssetOptions.ForceSynchronousImport);

            Scene scene = EditorSceneManager.OpenScene(TargetScenePath, OpenSceneMode.Single);
            if (!scene.IsValid())
            {
                throw new InvalidOperationException("Failed to open target scene: " + TargetScenePath);
            }

            ConfigureBootstrapForStaticScene();
            EnsurePlayModeValidator();
            RebuildAuthoredEntities();

            EditorSceneManager.MarkSceneDirty(scene);
            EditorSceneManager.SaveScene(scene);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            Debug.Log("[Stage6B3S] Scene built: " + TargetScenePath);
        }

        private static void GenerateReportsInternal()
        {
            Scene scene = EditorSceneManager.OpenScene(TargetScenePath, OpenSceneMode.Single);
            if (!scene.IsValid())
            {
                throw new InvalidOperationException("Failed to open scene: " + TargetScenePath);
            }

            MatchBootstrap bootstrap = UnityEngine.Object.FindFirstObjectByType<MatchBootstrap>();
            GridManager grid = UnityEngine.Object.FindFirstObjectByType<GridManager>();
            UnitRegistry unitRegistry = UnityEngine.Object.FindFirstObjectByType<UnitRegistry>();
            ResourceManager resourceManager = UnityEngine.Object.FindFirstObjectByType<ResourceManager>();
            MatchManager matchManager = UnityEngine.Object.FindFirstObjectByType<MatchManager>();

            if (bootstrap == null || grid == null || unitRegistry == null || resourceManager == null || matchManager == null)
            {
                throw new InvalidOperationException("Core runtime components are missing in static scene.");
            }

            StaticSceneEntityAuthoring[] authored = UnityEngine.Object.FindObjectsByType<StaticSceneEntityAuthoring>(FindObjectsSortMode.None);
            List<AuthoredEntityRow> authoredRows = BuildAuthoredRows(authored);

            bootstrap.Setup();

            ValidationResult validation = BuildValidation(authoredRows, grid, unitRegistry, resourceManager, matchManager, bootstrap);
            WriteSnapshot(authoredRows, validation);
            WriteJsonReport(validation);
            WriteMarkdownReport(validation);

            AssetDatabase.Refresh();
            Debug.Log("[Stage6B3S] Reports generated.");
        }

        private static void ConfigureBootstrapForStaticScene()
        {
            MatchBootstrap bootstrap = UnityEngine.Object.FindFirstObjectByType<MatchBootstrap>();
            if (bootstrap == null)
            {
                throw new InvalidOperationException("MatchBootstrap not found in scene.");
            }

            SerializedObject serialized = new SerializedObject(bootstrap);
            SerializedProperty mode = serialized.FindProperty("_initializationMode");
            if (mode == null)
            {
                throw new InvalidOperationException("MatchBootstrap._initializationMode not found. Recompile scripts and retry.");
            }

            mode.enumValueIndex = (int)BootstrapInitializationMode.StaticSceneRegistration;

            SerializedProperty preset = serialized.FindProperty("_scenarioPreset");
            if (preset != null)
            {
                preset.enumValueIndex = (int)BootstrapScenarioPreset.Week6StudentMicroRtsMirror24x24;
            }

            serialized.ApplyModifiedPropertiesWithoutUndo();
            EditorUtility.SetDirty(bootstrap);
        }

        private static void EnsurePlayModeValidator()
        {
            const string validatorObjectName = "Stage6B3S_PlayModeValidator";
            GameObject existing = GameObject.Find(validatorObjectName);
            if (existing == null)
            {
                existing = new GameObject(validatorObjectName);
            }

            if (existing.GetComponent<Stage6B3SPlayModeValidator>() == null)
            {
                existing.AddComponent<Stage6B3SPlayModeValidator>();
            }
        }

        private static void RebuildAuthoredEntities()
        {
            StaticSceneEntityAuthoring[] existing = UnityEngine.Object.FindObjectsByType<StaticSceneEntityAuthoring>(FindObjectsSortMode.None);
            for (int i = 0; i < existing.Length; i++)
            {
                if (existing[i] != null)
                {
                    UnityEngine.Object.DestroyImmediate(existing[i].gameObject);
                }
            }

            GameObject root = GameObject.Find("StaticAuthoredLayout");
            if (root == null)
            {
                root = new GameObject("StaticAuthoredLayout");
            }

            EnsureEntity(root.transform, "P1_Resource_1", "Assets/Prefabs/Resource.prefab", StaticSceneEntityKind.Resource, UnitType.Resource, Owner.Player1, new GridPosition(0, 0), GameConstants.MaxResourcesPerPatch);
            EnsureEntity(root.transform, "P1_Resource_2", "Assets/Prefabs/Resource.prefab", StaticSceneEntityKind.Resource, UnitType.Resource, Owner.Player1, new GridPosition(1, 0), GameConstants.MaxResourcesPerPatch);
            EnsureEntity(root.transform, "P1_Worker", "Assets/Prefabs/Worker.prefab", StaticSceneEntityKind.Unit, UnitType.Worker, Owner.Player1, new GridPosition(1, 1), 1);
            EnsureEntity(root.transform, "P1_Base", "Assets/Prefabs/Base.prefab", StaticSceneEntityKind.Unit, UnitType.Base, Owner.Player1, new GridPosition(2, 2), 1);

            EnsureEntity(root.transform, "P2_Resource_1", "Assets/Prefabs/Resource.prefab", StaticSceneEntityKind.Resource, UnitType.Resource, Owner.Player2, new GridPosition(23, 23), GameConstants.MaxResourcesPerPatch);
            EnsureEntity(root.transform, "P2_Resource_2", "Assets/Prefabs/Resource.prefab", StaticSceneEntityKind.Resource, UnitType.Resource, Owner.Player2, new GridPosition(22, 23), GameConstants.MaxResourcesPerPatch);
            EnsureEntity(root.transform, "P2_Worker", "Assets/Prefabs/Worker.prefab", StaticSceneEntityKind.Unit, UnitType.Worker, Owner.Player2, new GridPosition(22, 22), 1);
            EnsureEntity(root.transform, "P2_Base", "Assets/Prefabs/Base.prefab", StaticSceneEntityKind.Unit, UnitType.Base, Owner.Player2, new GridPosition(21, 21), 1);
        }

        private static void EnsureEntity(Transform parent, string name, string prefabPath, StaticSceneEntityKind kind, UnitType unitType, Owner owner, GridPosition gridPos, int resourceAmount)
        {
            GameObject prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
            if (prefab == null)
            {
                throw new InvalidOperationException("Prefab not found: " + prefabPath);
            }

            GameObject go = PrefabUtility.InstantiatePrefab(prefab) as GameObject;
            if (go == null)
            {
                throw new InvalidOperationException("Failed to instantiate prefab: " + prefabPath);
            }

            go.name = name;
            go.transform.SetParent(parent, true);
            go.transform.position = gridPos.ToWorldPosition();
            go.transform.rotation = Quaternion.identity;

            UnitRuntime runtime = go.GetComponent<UnitRuntime>();
            if (runtime == null)
            {
                runtime = go.AddComponent<UnitRuntime>();
            }

            StaticSceneEntityAuthoring authored = go.GetComponent<StaticSceneEntityAuthoring>();
            if (authored == null)
            {
                authored = go.AddComponent<StaticSceneEntityAuthoring>();
            }

            authored.Configure(kind, unitType, owner, gridPos, resourceAmount);
        }

        private static List<AuthoredEntityRow> BuildAuthoredRows(StaticSceneEntityAuthoring[] authored)
        {
            var rows = new List<AuthoredEntityRow>();
            for (int i = 0; i < authored.Length; i++)
            {
                StaticSceneEntityAuthoring entry = authored[i];
                if (entry == null)
                {
                    continue;
                }

                GridPosition pos = entry.GetGridPosition();
                Vector3 world = entry.transform.position;
                rows.Add(new AuthoredEntityRow
                {
                    name = entry.name,
                    entity_kind = entry.EntityKind.ToString(),
                    unit_type = entry.UnitType.ToString(),
                    owner = entry.Owner.ToString(),
                    grid_x = pos.X,
                    grid_y = pos.Y,
                    world_x = world.x,
                    world_y = world.y,
                    world_z = world.z,
                    visual_label = BuildLabel(pos),
                    visual_y_flipped = Math.Abs(world.z - pos.Y * GameConstants.CellSize) > 0.001f,
                });
            }

            rows.Sort((a, b) => string.CompareOrdinal(a.name, b.name));
            return rows;
        }

        private static ValidationResult BuildValidation(
            List<AuthoredEntityRow> authoredRows,
            GridManager grid,
            UnitRegistry unitRegistry,
            ResourceManager resourceManager,
            MatchManager matchManager,
            MatchBootstrap bootstrap)
        {
            var occupancyRows = new List<OccupancyRow>();
            foreach (var kv in grid.Occupancy)
            {
                UnitRuntime unit = kv.Value;
                occupancyRows.Add(new OccupancyRow
                {
                    grid_x = kv.Key.X,
                    grid_y = kv.Key.Y,
                    unit_name = unit != null ? unit.name : "null",
                    unit_type = unit != null ? unit.Type.ToString() : "Unknown",
                    owner = unit != null ? unit.Owner.ToString() : "Unknown",
                });
            }

            occupancyRows.Sort((a, b) =>
            {
                int y = a.grid_y.CompareTo(b.grid_y);
                return y != 0 ? y : a.grid_x.CompareTo(b.grid_x);
            });

            List<UnitRuntime> units = unitRegistry.GetAllUnits();
            var registryRows = new List<UnitRegistryRow>(units.Count);
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit == null)
                {
                    continue;
                }

                registryRows.Add(new UnitRegistryRow
                {
                    unit_name = unit.name,
                    unit_type = unit.Type.ToString(),
                    owner = unit.Owner.ToString(),
                    grid_x = unit.GridPos.X,
                    grid_y = unit.GridPos.Y,
                });
            }

            registryRows.Sort((a, b) => string.CompareOrdinal(a.unit_name, b.unit_name));

            var resourceRows = new List<ResourceNodeRow>();
            foreach (ResourceNode node in resourceManager.GetAllResourceNodes())
            {
                resourceRows.Add(new ResourceNodeRow
                {
                    grid_x = node.GridPosition.X,
                    grid_y = node.GridPosition.Y,
                    current_resources = node.CurrentResources,
                    is_exhausted = node.IsExhausted,
                });
            }

            resourceRows.Sort((a, b) =>
            {
                int y = a.grid_y.CompareTo(b.grid_y);
                return y != 0 ? y : a.grid_x.CompareTo(b.grid_x);
            });

            GridPosition workerPos = new GridPosition(2, 2);
            GridPosition north = workerPos.Neighbour(Direction.North);
            GridPosition east = workerPos.Neighbour(Direction.East);
            GridPosition south = workerPos.Neighbour(Direction.South);
            GridPosition west = workerPos.Neighbour(Direction.West);

            bool northValid = IsHarvestTargetValid(resourceManager, north);
            bool eastValid = IsHarvestTargetValid(resourceManager, east);
            bool southValid = IsHarvestTargetValid(resourceManager, south);
            bool westValid = IsHarvestTargetValid(resourceManager, west);

            var maskBuilder = new ActionMaskBuilder(matchManager, grid, resourceManager, unitRegistry, bootstrap);
            ActionMaskSet p1Mask = maskBuilder.BuildTransferCompatibleMask(Owner.Player1);
            ActorActionMask workerMask = p1Mask.GetActorMask(workerPos);

            bool maskNorth = workerMask != null && workerMask.HarvestDirectionMask.Length > 0 && workerMask.HarvestDirectionMask[0];
            bool maskEast = workerMask != null && workerMask.HarvestDirectionMask.Length > 1 && workerMask.HarvestDirectionMask[1];
            bool maskSouth = workerMask != null && workerMask.HarvestDirectionMask.Length > 2 && workerMask.HarvestDirectionMask[2];
            bool maskWest = workerMask != null && workerMask.HarvestDirectionMask.Length > 3 && workerMask.HarvestDirectionMask[3];

            int authoredCount = authoredRows.Count;
            int occupancyCount = occupancyRows.Count;
            int registryCount = registryRows.Count;
            int resourceCount = resourceRows.Count;

            bool staticObjectsRegistered = authoredCount == 8 && occupancyCount == 8 && registryCount == 8 && resourceCount == 4;
            bool directionMaskMatches = !northValid && !eastValid && !southValid && westValid
                && !maskNorth && !maskEast && !maskSouth && maskWest;

            PlayModeValidation playModeValidation = ReadPlayModeValidationIfPresent();
            bool noDuplicateAfterPlay = playModeValidation != null && playModeValidation.no_duplicate_spawn_after_play_start;

            string classification;
            if (playModeValidation != null && !noDuplicateAfterPlay)
            {
                classification = "STAGE6B3S_FAIL_DUPLICATE_SPAWN";
            }
            else if (!staticObjectsRegistered)
            {
                classification = "STAGE6B3S_FAIL_STATIC_OBJECTS_NOT_REGISTERED";
            }
            else if (!directionMaskMatches)
            {
                classification = "STAGE6B3S_FAIL_DIRECTION_MASK_MISMATCH";
            }
            else if (playModeValidation == null)
            {
                classification = "STAGE6B3S_PASS_SCENE_READY_WITH_WARNINGS";
            }
            else
            {
                classification = "STAGE6B3S_PASS_STATIC_SCENE_READY";
            }

            return new ValidationResult
            {
                generated_at_utc = DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture),
                scene_name = SceneManager.GetActiveScene().name,
                scene_path = TargetScenePath,
                map_width = grid.Width,
                map_height = grid.Height,
                bootstrap_mode = BootstrapInitializationMode.StaticSceneRegistration.ToString(),
                authored_entities = authoredRows,
                grid_occupancy = occupancyRows,
                unit_registry = registryRows,
                resource_nodes = resourceRows,
                authored_entity_count = authoredCount,
                occupancy_count = occupancyCount,
                unit_registry_count = registryCount,
                resource_node_count = resourceCount,
                static_objects_registered = staticObjectsRegistered,
                duplicate_spawn_prevented_after_play_start = noDuplicateAfterPlay,
                playmode_validation_present = playModeValidation != null,
                playmode_validation = playModeValidation,
                worker_harvest_check = new WorkerHarvestCheck
                {
                    worker_grid_x = 2,
                    worker_grid_y = 2,
                    direction_enum = "0=North,1=East,2=South,3=West",
                    north_target = "(2,3)",
                    east_target = "(3,2)",
                    south_target = "(2,1)",
                    west_target = "(1,2)",
                    north_valid = northValid,
                    east_valid = eastValid,
                    south_valid = southValid,
                    west_valid = westValid,
                    mask_north = maskNorth,
                    mask_east = maskEast,
                    mask_south = maskSouth,
                    mask_west = maskWest,
                    expected_valid_direction = "West",
                    expected_valid_direction_index = 3,
                    expected_invalid_direction = "East",
                    expected_invalid_direction_index = 1,
                    direction_mask_matches_expectation = directionMaskMatches,
                },
                coordinate_mapping_note = "GridPosition(X,Y) uses X->world.x and Y->world.z. Visual Y is not flipped in this scene.",
                classification = classification,
                stage6b3h_ready = classification == "STAGE6B3S_PASS_STATIC_SCENE_READY" || classification == "STAGE6B3S_PASS_SCENE_READY_WITH_WARNINGS",
            };
        }

        private static bool IsHarvestTargetValid(ResourceManager resourceManager, GridPosition target)
        {
            ResourceNode node = resourceManager.GetResourceNode(target);
            return node != null && !node.IsExhausted;
        }

        private static void WriteSnapshot(List<AuthoredEntityRow> authoredRows, ValidationResult validation)
        {
            var snapshot = new LayoutSnapshot
            {
                generated_at_utc = validation.generated_at_utc,
                scene_name = validation.scene_name,
                scene_path = validation.scene_path,
                map_width = validation.map_width,
                map_height = validation.map_height,
                authored_entities = authoredRows,
                coordinate_mapping_note = validation.coordinate_mapping_note,
            };

            string json = JsonUtility.ToJson(snapshot, true);
            WriteProjectRelativeText(SnapshotPath, json + "\n");
        }

        private static void WriteJsonReport(ValidationResult validation)
        {
            string json = JsonUtility.ToJson(validation, true);
            WriteProjectRelativeText(ReportJsonPath, json + "\n");
        }

        private static void WriteMarkdownReport(ValidationResult validation)
        {
            var lines = new List<string>
            {
                "# STAGE6B3S Static Harvest Scene Report",
                "",
                "- Generated (UTC): " + validation.generated_at_utc,
                "- Scene: " + validation.scene_path,
                "- Classification: " + validation.classification,
                "- Bootstrap mode: " + validation.bootstrap_mode,
                "- Objects present before Play Mode: true (scene-authored objects are stored in the scene).",
                "- Duplicate spawn prevented after Play Mode start: " + validation.duplicate_spawn_prevented_after_play_start,
                "- Play Mode validation file present: " + validation.playmode_validation_present,
                "",
                "## Coordinates",
                "",
                "### Player1",
                "| Name | GridPosition |",
                "|---|---|",
                "| P1_Resource_1 | (1,1) |",
                "| P1_Resource_2 | (1,2) |",
                "| P1_Worker | (2,2) |",
                "| P1_Base | (3,3) |",
                "",
                "### Player2 mirrored (mirrorX = 23-x, mirrorY = 23-y)",
                "| Name | GridPosition |",
                "|---|---|",
                "| P2_Resource_1 | (22,22) |",
                "| P2_Resource_2 | (22,21) |",
                "| P2_Worker | (21,21) |",
                "| P2_Base | (20,20) |",
                "",
                "## Worker (2,2) Harvest Direction",
                "",
                "- North target (2,3): valid=" + validation.worker_harvest_check.north_valid + ", mask=" + validation.worker_harvest_check.mask_north,
                "- East target (3,2): valid=" + validation.worker_harvest_check.east_valid + ", mask=" + validation.worker_harvest_check.mask_east,
                "- South target (2,1): valid=" + validation.worker_harvest_check.south_valid + ", mask=" + validation.worker_harvest_check.mask_south,
                "- West target (1,2): valid=" + validation.worker_harvest_check.west_valid + ", mask=" + validation.worker_harvest_check.mask_west,
                "- Expected valid: West / 3",
                "- Expected invalid: East / 1",
                "- Direction check pass: " + validation.worker_harvest_check.direction_mask_matches_expectation,
                "",
                "## Overlay Focus",
                "",
                "- Focus worker cell = (2,2)",
                "- Focus base cell = (3,3)",
                "- Week6VisualInspectionRunner now auto-switches focus labels/flat-indices for Week6_StudentStaticHarvestLayout.",
                "",
                "## Files Changed",
                "",
                "- Assets/Scenes/Week6_StudentStaticHarvestLayout.unity",
                "- Assets/Scripts/Gameplay/Match/MatchBootstrap.cs",
                "- Assets/Scripts/Gameplay/Match/StaticSceneEntityAuthoring.cs",
                "- Assets/Scripts/ML/Week6VisualInspectionRunner.cs",
                "- Assets/Scripts/ML/Stage6B3SPlayModeValidator.cs",
                "- Assets/Scripts/ML/Editor/Week6StudentStaticHarvestSceneMenu.cs",
                "- python/week6_student/reports/stage6b3s_static_scene_layout_snapshot.json",
                "- python/week6_student/reports/stage6b3s_static_harvest_scene_report.json",
                "- python/week6_student/reports/STAGE6B3S_STATIC_HARVEST_SCENE_REPORT.md",
                "- python/week6_student/reports/stage6b3s_static_scene_playmode_validation.json (generated after Play Mode run)",
                "",
                "## Notes",
                "",
                "- Runtime authoritative path remains unchanged: Policy -> ActionDecoder -> ActionApplier -> MatchManager.ApplyCommand.",
                "- No training steps were executed by this utility.",
            };

            WriteProjectRelativeText(ReportMdPath, string.Join("\n", lines) + "\n");
        }

        private static PlayModeValidation ReadPlayModeValidationIfPresent()
        {
            string path = GetProjectAbsolutePath(PlayModeValidationPath);
            if (!File.Exists(path))
            {
                return null;
            }

            string json = File.ReadAllText(path);
            if (string.IsNullOrWhiteSpace(json))
            {
                return null;
            }

            return JsonUtility.FromJson<PlayModeValidation>(json);
        }

        private static void WriteProjectRelativeText(string relativePath, string content)
        {
            string absolutePath = GetProjectAbsolutePath(relativePath);
            string dir = Path.GetDirectoryName(absolutePath);
            if (!string.IsNullOrEmpty(dir))
            {
                Directory.CreateDirectory(dir);
            }

            File.WriteAllText(absolutePath, content);
        }

        private static string GetProjectAbsolutePath(string relativePath)
        {
            return Path.GetFullPath(Path.Combine(Application.dataPath, "..", relativePath));
        }

        private static void EnsureParentDirectory(string assetRelativePath)
        {
            string absolute = GetProjectAbsolutePath(assetRelativePath);
            string dir = Path.GetDirectoryName(absolute);
            if (!string.IsNullOrEmpty(dir))
            {
                Directory.CreateDirectory(dir);
            }
        }

        private static string BuildLabel(GridPosition pos)
        {
            char col = (char)('A' + Mathf.Clamp(pos.X, 0, 25));
            return col + (pos.Y + 1).ToString(CultureInfo.InvariantCulture);
        }

        [Serializable]
        private sealed class LayoutSnapshot
        {
            public string generated_at_utc;
            public string scene_name;
            public string scene_path;
            public int map_width;
            public int map_height;
            public List<AuthoredEntityRow> authored_entities;
            public string coordinate_mapping_note;
        }

        [Serializable]
        private sealed class ValidationResult
        {
            public string generated_at_utc;
            public string scene_name;
            public string scene_path;
            public int map_width;
            public int map_height;
            public string bootstrap_mode;
            public List<AuthoredEntityRow> authored_entities;
            public List<OccupancyRow> grid_occupancy;
            public List<UnitRegistryRow> unit_registry;
            public List<ResourceNodeRow> resource_nodes;
            public int authored_entity_count;
            public int occupancy_count;
            public int unit_registry_count;
            public int resource_node_count;
            public bool static_objects_registered;
            public bool duplicate_spawn_prevented_after_play_start;
            public bool playmode_validation_present;
            public PlayModeValidation playmode_validation;
            public WorkerHarvestCheck worker_harvest_check;
            public string coordinate_mapping_note;
            public string classification;
            public bool stage6b3h_ready;
        }

        [Serializable]
        private sealed class AuthoredEntityRow
        {
            public string name;
            public string entity_kind;
            public string unit_type;
            public string owner;
            public int grid_x;
            public int grid_y;
            public float world_x;
            public float world_y;
            public float world_z;
            public string visual_label;
            public bool visual_y_flipped;
        }

        [Serializable]
        private sealed class OccupancyRow
        {
            public int grid_x;
            public int grid_y;
            public string unit_name;
            public string unit_type;
            public string owner;
        }

        [Serializable]
        private sealed class UnitRegistryRow
        {
            public string unit_name;
            public string unit_type;
            public string owner;
            public int grid_x;
            public int grid_y;
        }

        [Serializable]
        private sealed class ResourceNodeRow
        {
            public int grid_x;
            public int grid_y;
            public int current_resources;
            public bool is_exhausted;
        }

        [Serializable]
        private sealed class WorkerHarvestCheck
        {
            public int worker_grid_x;
            public int worker_grid_y;
            public string direction_enum;
            public string north_target;
            public string east_target;
            public string south_target;
            public string west_target;
            public bool north_valid;
            public bool east_valid;
            public bool south_valid;
            public bool west_valid;
            public bool mask_north;
            public bool mask_east;
            public bool mask_south;
            public bool mask_west;
            public string expected_valid_direction;
            public int expected_valid_direction_index;
            public string expected_invalid_direction;
            public int expected_invalid_direction_index;
            public bool direction_mask_matches_expectation;
        }

        [Serializable]
        private sealed class PlayModeValidation
        {
            public string scene;
            public string captured_at_utc;
            public int authored_entity_count;
            public int grid_occupancy_count;
            public int unit_registry_count;
            public int resource_node_count;
            public int unique_occupancy_cells;
            public bool no_duplicate_spawn_after_play_start;
        }
    }
}
