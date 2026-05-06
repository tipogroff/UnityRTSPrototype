using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using RTS.Gameplay;
using UnityEngine;
using UnityEngine.SceneManagement;

#if UNITY_EDITOR
using UnityEditor;
#endif

namespace RTS.ML
{
    [DisallowMultipleComponent]
    public sealed class Stage6B3SPlayModeValidator : MonoBehaviour
    {
        private const string TargetSceneName = "Week6_StudentStaticHarvestLayout";
        private const string OutputRelativePath = "python/week6_student/reports/stage6b3s_static_scene_playmode_validation.json";

        [SerializeField]
        private bool _exitPlayModeAfterValidation;

        private IEnumerator Start()
        {
            if (!string.Equals(SceneManager.GetActiveScene().name, TargetSceneName, StringComparison.Ordinal))
            {
                yield break;
            }

            yield return null;

            var grid = GridManager.Instance;
            var registry = UnitRegistry.Instance;
            var resources = ResourceManager.Instance;
            var authored = FindObjectsByType<StaticSceneEntityAuthoring>(FindObjectsSortMode.None);

            int authoredCount = authored != null ? authored.Length : 0;
            int occupancyCount = grid != null && grid.Occupancy != null ? grid.Occupancy.Count : 0;
            int unitCount = registry != null ? registry.GetAllUnits().Count : 0;

            int resourceNodeCount = 0;
            if (resources != null)
            {
                foreach (var _ in resources.GetAllResourceNodes())
                {
                    resourceNodeCount++;
                }
            }

            var uniqueCells = new HashSet<GridPosition>();
            if (grid != null && grid.Occupancy != null)
            {
                foreach (var kv in grid.Occupancy)
                {
                    uniqueCells.Add(kv.Key);
                }
            }

            bool noDuplicateSpawn = authoredCount == 8
                && occupancyCount == 8
                && unitCount == 8
                && uniqueCells.Count == 8
                && resourceNodeCount == 4;

            string json = "{" +
                "\n  \"scene\": \"" + TargetSceneName + "\"," +
                "\n  \"captured_at_utc\": \"" + DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture) + "\"," +
                "\n  \"authored_entity_count\": " + authoredCount + "," +
                "\n  \"grid_occupancy_count\": " + occupancyCount + "," +
                "\n  \"unit_registry_count\": " + unitCount + "," +
                "\n  \"resource_node_count\": " + resourceNodeCount + "," +
                "\n  \"unique_occupancy_cells\": " + uniqueCells.Count + "," +
                "\n  \"no_duplicate_spawn_after_play_start\": " + (noDuplicateSpawn ? "true" : "false") +
                "\n}";

            string outputPath = Path.GetFullPath(Path.Combine(Application.dataPath, "..", OutputRelativePath));
            string outputDir = Path.GetDirectoryName(outputPath);
            if (!string.IsNullOrEmpty(outputDir))
            {
                Directory.CreateDirectory(outputDir);
            }

            File.WriteAllText(outputPath, json);
            Debug.Log("[Stage6B3S] PlayMode validation saved: " + outputPath);

#if UNITY_EDITOR
            if (_exitPlayModeAfterValidation)
            {
                EditorApplication.delayCall += () => { EditorApplication.isPlaying = false; };
            }
#endif
        }
    }
}
