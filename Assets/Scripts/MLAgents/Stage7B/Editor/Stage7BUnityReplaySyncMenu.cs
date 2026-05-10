#if UNITY_EDITOR
using System;
using System.IO;
using System.Text.RegularExpressions;
using RTS.MLAgents.Stage7B.TeacherReplay;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.Editor
{
    [InitializeOnLoad]
    public static class Stage7BUnityReplaySyncMenu
    {
        private const string MenuPath = "RTS/Week7/Stage7B/Run Unity Replay Sync 6H";
        private const string ScenePath = "Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity";
        private const string ReportPath = "python/stage7b_teacher_replay/stage7b_unity_replay_sync_report.json";
        private const string PendingKey = "RTS.MLAgents.Stage7B.UnityReplaySync6H.Pending";
        private const string StartedAtTicksKey = "RTS.MLAgents.Stage7B.UnityReplaySync6H.StartedAtTicks";
        private const string TriggeredKey = "RTS.MLAgents.Stage7B.UnityReplaySync6H.Triggered";
        private const double TimeoutSeconds = 180d;

        static Stage7BUnityReplaySyncMenu()
        {
            EditorApplication.update -= PollExecution;
            EditorApplication.update += PollExecution;
            EditorApplication.playModeStateChanged -= OnPlayModeChanged;
            EditorApplication.playModeStateChanged += OnPlayModeChanged;
        }

        [MenuItem(MenuPath)]
        public static void Run()
        {
            if (Application.isPlaying)
            {
                Debug.LogWarning("[Stage7B] Stage7B-6H menu must be started from Edit Mode.");
                return;
            }

            if (EditorSceneManager.GetActiveScene().isDirty)
            {
                Debug.LogError("[Stage7B] Save or revert current scene before Stage7B-6H run.");
                return;
            }

            if (EditorSceneManager.OpenScene(ScenePath) == default)
            {
                Debug.LogError("[Stage7B] Failed to open Week7 scene.");
                return;
            }

            string report = GetAbsoluteProjectPath(ReportPath);
            if (File.Exists(report))
            {
                File.Delete(report);
            }

            SessionState.SetBool(PendingKey, true);
            SessionState.SetBool(TriggeredKey, false);
            SessionState.SetString(StartedAtTicksKey, DateTime.UtcNow.Ticks.ToString());
            Debug.Log("[Stage7B] Entering Play Mode for Stage7B-6H Unity replay sync.");
            EditorApplication.isPlaying = true;
        }

        private static void PollExecution()
        {
            if (!SessionState.GetBool(PendingKey, false))
            {
                return;
            }

            if (HasTimedOut())
            {
                Debug.LogError("[Stage7B] Stage7B-6H timed out.");
                EditorApplication.isPlaying = false;
                return;
            }

            if (Application.isPlaying)
            {
                if (!SessionState.GetBool(TriggeredKey, false))
                {
                    Stage7BTeacherTrajectoryReplayRunner runner = UnityEngine.Object.FindFirstObjectByType<Stage7BTeacherTrajectoryReplayRunner>();
                    if (runner == null)
                    {
                        var go = new GameObject("Stage7BTeacherReplayRunner");
                        runner = go.AddComponent<Stage7BTeacherTrajectoryReplayRunner>();
                    }

                    runner.RunStage7B6HUnityReplaySync();
                    SessionState.SetBool(TriggeredKey, true);
                    return;
                }

                string report = GetAbsoluteProjectPath(ReportPath);
                if (File.Exists(report))
                {
                    Debug.Log("[Stage7B] Stage7B-6H report detected. Exiting Play Mode.");
                    EditorApplication.isPlaying = false;
                }
            }
        }

        private static void OnPlayModeChanged(PlayModeStateChange state)
        {
            if (state != PlayModeStateChange.EnteredEditMode || !SessionState.GetBool(PendingKey, false))
            {
                return;
            }

            SessionState.SetBool(PendingKey, false);
            SessionState.SetBool(TriggeredKey, false);
            ValidateReport();
        }

        private static void ValidateReport()
        {
            string report = GetAbsoluteProjectPath(ReportPath);
            if (!File.Exists(report))
            {
                Debug.LogError("[Stage7B] Stage7B-6H report was not created: " + report);
                return;
            }

            string json = File.ReadAllText(report);
            if (!TryReadString(json, "status", out string status)
                || !TryReadInt(json, "teacherCommandsTotal", out int commands)
                || !TryReadInt(json, "stateSyncSuccessCount", out int syncOk))
            {
                Debug.LogError("[Stage7B] Stage7B-6H report is missing required fields.");
                return;
            }

            Debug.Log("[Stage7B] Stage7B-6H finished: status=" + status + ", teacherCommandsTotal=" + commands + ", stateSyncSuccessCount=" + syncOk);
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

        private static string GetAbsoluteProjectPath(string relativePath)
        {
            string root = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            string normalized = relativePath.Replace('/', Path.DirectorySeparatorChar);
            return Path.Combine(root, normalized);
        }

        private static bool TryReadInt(string json, string key, out int value)
        {
            Match match = Regex.Match(json, "\"" + Regex.Escape(key) + "\"\\s*:\\s*(-?\\d+)");
            if (match.Success && int.TryParse(match.Groups[1].Value, out value))
            {
                return true;
            }

            value = 0;
            return false;
        }

        private static bool TryReadString(string json, string key, out string value)
        {
            Match match = Regex.Match(json, "\"" + Regex.Escape(key) + "\"\\s*:\\s*\"([^\"]*)\"");
            if (match.Success)
            {
                value = match.Groups[1].Value;
                return true;
            }

            value = string.Empty;
            return false;
        }
    }
}
#endif
