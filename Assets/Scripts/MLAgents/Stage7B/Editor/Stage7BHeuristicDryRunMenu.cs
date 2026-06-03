#if UNITY_EDITOR
using System;
using System.IO;
using System.Text.RegularExpressions;
using RTS.MLAgents.Stage7B.Diagnostics;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.Editor
{
    [InitializeOnLoad]
    public static class Stage7BHeuristicDryRunMenu
    {
        private const string MenuPath = "RTS/Week7/Stage7B/Run Heuristic Dry Run";
        private const string ScenePath = "Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity";
        private const string ArtifactFileName = "stage7b_mlagents_heuristic_dryrun.json";
        private const string PendingKey = "RTS.MLAgents.Stage7B.HeuristicDryRun.Pending";
        private const string StartedAtTicksKey = "RTS.MLAgents.Stage7B.HeuristicDryRun.StartedAtTicks";
        private const double TimeoutSeconds = 90d;

        static Stage7BHeuristicDryRunMenu()
        {
            EditorApplication.update -= PollPlayModeArtifact;
            EditorApplication.update += PollPlayModeArtifact;
            EditorApplication.playModeStateChanged -= HandlePlayModeStateChanged;
            EditorApplication.playModeStateChanged += HandlePlayModeStateChanged;
        }

        [MenuItem(MenuPath)]
        public static void Run()
        {
            if (Application.isPlaying)
            {
                Debug.LogWarning("[Stage7B] Heuristic dry run menu must be started from Edit Mode.");
                return;
            }

            if (EditorSceneManager.GetActiveScene().isDirty)
            {
                Debug.LogError("[Stage7B] Save or revert the current scene before running the Week7 heuristic dry run.");
                return;
            }

            if (EditorSceneManager.OpenScene(ScenePath) == default)
            {
                Debug.LogError("[Stage7B] Failed to open Week7 ML-Agents scene.");
                return;
            }

            EnableDryRunLoggerForExplicitRun();

            string artifactPath = GetArtifactPath();
            if (File.Exists(artifactPath))
            {
                File.Delete(artifactPath);
            }

            SessionState.SetBool(PendingKey, true);
            SessionState.SetString(StartedAtTicksKey, DateTime.UtcNow.Ticks.ToString());
            Debug.Log("[Stage7B] Opening Week7 scene and entering Play Mode for heuristic dry run.");
            EditorApplication.isPlaying = true;
        }

        private static void PollPlayModeArtifact()
        {
            if (!Application.isPlaying || !SessionState.GetBool(PendingKey, false))
            {
                return;
            }

            if (HasTimedOut())
            {
                Debug.LogError("[Stage7B] Heuristic dry run timed out before a terminal artifact was produced.");
                EditorApplication.isPlaying = false;
                return;
            }

            string artifactPath = GetArtifactPath();
            if (!File.Exists(artifactPath))
            {
                return;
            }

            string json = File.ReadAllText(artifactPath);
            if (!TryReadInt(json, "collect_observations_calls", out int observations)
                || !TryReadInt(json, "write_mask_calls", out int maskCalls)
                || !TryReadInt(json, "on_action_received_calls", out int actionCalls)
                || !TryReadString(json, "terminal_reason", out string terminalReason))
            {
                return;
            }

            if (observations > 0 && maskCalls > 0 && actionCalls > 0 && !string.Equals(terminalReason, "none", StringComparison.OrdinalIgnoreCase))
            {
                Debug.Log("[Stage7B] Heuristic dry run produced terminal artifact state. Exiting Play Mode.");
                EditorApplication.isPlaying = false;
            }
        }

        private static void HandlePlayModeStateChanged(PlayModeStateChange state)
        {
            if (state != PlayModeStateChange.EnteredEditMode || !SessionState.GetBool(PendingKey, false))
            {
                return;
            }

            SessionState.SetBool(PendingKey, false);
            ValidateArtifactAfterRun();
        }

        private static void ValidateArtifactAfterRun()
        {
            string artifactPath = GetArtifactPath();
            if (!File.Exists(artifactPath))
            {
                Debug.LogError("[Stage7B] Heuristic dry run did not produce stage7b_mlagents_heuristic_dryrun.json.");
                return;
            }

            string json = File.ReadAllText(artifactPath);
            bool ok = TryReadInt(json, "collect_observations_calls", out int observations);
            ok &= TryReadInt(json, "write_mask_calls", out int maskCalls);
            ok &= TryReadInt(json, "on_action_received_calls", out int actionCalls);
            ok &= TryReadInt(json, "accepted_commands", out int acceptedCommands);
            ok &= TryReadInt(json, "rejected_commands", out int rejectedCommands);
            ok &= TryReadString(json, "terminal_reason", out string terminalReason);

            if (!ok)
            {
                Debug.LogError("[Stage7B] Heuristic dry run artifact is missing required counters.");
                return;
            }

            Debug.Log(
                "[Stage7B] Heuristic dry run finished: " +
                $"collect={observations}, mask={maskCalls}, actions={actionCalls}, accepted={acceptedCommands}, rejected={rejectedCommands}, terminal={terminalReason}");
        }

        private static bool HasTimedOut()
        {
            string startedAtTicks = SessionState.GetString(StartedAtTicksKey, string.Empty);
            if (!long.TryParse(startedAtTicks, out long ticks))
            {
                return false;
            }

            return (DateTime.UtcNow - new DateTime(ticks, DateTimeKind.Utc)).TotalSeconds > TimeoutSeconds;
        }

        private static string GetArtifactPath()
        {
            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            return Path.Combine(projectRoot, ArtifactFileName);
        }

        private static bool TryReadInt(string json, string key, out int value)
        {
            Match match = Regex.Match(json, $"\"{Regex.Escape(key)}\"\\s*:\\s*(-?\\d+)");
            if (match.Success && int.TryParse(match.Groups[1].Value, out value))
            {
                return true;
            }

            value = 0;
            return false;
        }

        private static bool TryReadString(string json, string key, out string value)
        {
            Match match = Regex.Match(json, $"\"{Regex.Escape(key)}\"\\s*:\\s*\"([^\"]*)\"");
            if (match.Success)
            {
                value = match.Groups[1].Value;
                return true;
            }

            value = string.Empty;
            return false;
        }
    

private static void EnableDryRunLoggerForExplicitRun()
        {
            Stage7BHeuristicDryRunLogger logger = UnityEngine.Object.FindFirstObjectByType<Stage7BHeuristicDryRunLogger>(FindObjectsInactive.Include);
            if (logger == null)
            {
                var host = new GameObject("Stage7B_HeuristicDryRunLogger");
                logger = host.AddComponent<Stage7BHeuristicDryRunLogger>();
            }

            logger.enabled = true;
            SerializedObject serialized = new SerializedObject(logger);
            SerializedProperty writes = serialized.FindProperty("_enableRuntimeArtifactWrites");
            if (writes != null)
            {
                writes.boolValue = true;
                serialized.ApplyModifiedPropertiesWithoutUndo();
            }
        }
}
}
#endif