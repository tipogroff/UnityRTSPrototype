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
        // ── Stage7B-6H ────────────────────────────────────────────────────────
        private const string MenuPath = "RTS/Week7/Stage7B/Run Unity Replay Sync 6H";
        private const string ScenePath = "Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity";
        private const string ReportPath = "python/stage7b_teacher_replay/stage7b_unity_replay_sync_report.json";
        private const string PendingKey = "RTS.MLAgents.Stage7B.UnityReplaySync6H.Pending";
        private const string StartedAtTicksKey = "RTS.MLAgents.Stage7B.UnityReplaySync6H.StartedAtTicks";
        private const string TriggeredKey = "RTS.MLAgents.Stage7B.UnityReplaySync6H.Triggered";
        private const double TimeoutSeconds = 180d;

        // ── Stage7B-6I ────────────────────────────────────────────────────────
        private const string MenuPath6I = "RTS/Week7/Stage7B/Run Runtime Apply Validation 6I";
        private const string ReportPath6I = "python/stage7b_teacher_replay/stage7b_runtime_apply_validation_report.json";
        private const string PendingKey6I = "RTS.MLAgents.Stage7B.RuntimeApply6I.Pending";
        private const string StartedAtTicksKey6I = "RTS.MLAgents.Stage7B.RuntimeApply6I.StartedAtTicks";
        private const string TriggeredKey6I = "RTS.MLAgents.Stage7B.RuntimeApply6I.Triggered";

    // ── Stage7B-6J ────────────────────────────────────────────────────────
    private const string MenuPath6J = "RTS/Week7/Stage7B/Run Return Direction Mismatch Audit 6J";
    private const string MenuPath6JImmediate = "RTS/Week7/Stage7B/Run Return Direction Mismatch Audit 6J (Immediate In Play Mode)";
    private const string ReportPath6J = "python/stage7b_teacher_replay/stage7b_6j_return_direction_audit_report.json";
    private const string PendingKey6J = "RTS.MLAgents.Stage7B.ReturnDirAudit6J.Pending";
    private const string StartedAtTicksKey6J = "RTS.MLAgents.Stage7B.ReturnDirAudit6J.StartedAtTicks";
    private const string TriggeredKey6J = "RTS.MLAgents.Stage7B.ReturnDirAudit6J.Triggered";

        static Stage7BUnityReplaySyncMenu()
        {
            EditorApplication.update -= PollExecution;
            EditorApplication.update += PollExecution;
            EditorApplication.playModeStateChanged -= OnPlayModeChanged;
            EditorApplication.playModeStateChanged += OnPlayModeChanged;
        }

        // ── 6H Entry Point ────────────────────────────────────────────────────
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

        // ── 6I Entry Point ────────────────────────────────────────────────────
        [MenuItem(MenuPath6I)]
        public static void Run6I()
        {
            if (Application.isPlaying)
            {
                Debug.LogWarning("[Stage7B] Stage7B-6I menu must be started from Edit Mode.");
                return;
            }

            if (EditorSceneManager.GetActiveScene().isDirty)
            {
                Debug.LogError("[Stage7B] Save or revert current scene before Stage7B-6I run.");
                return;
            }

            if (EditorSceneManager.OpenScene(ScenePath) == default)
            {
                Debug.LogError("[Stage7B] Failed to open Week7 scene.");
                return;
            }

            string report6I = GetAbsoluteProjectPath(ReportPath6I);
            if (File.Exists(report6I))
            {
                File.Delete(report6I);
            }

            SessionState.SetBool(PendingKey6I, true);
            SessionState.SetBool(TriggeredKey6I, false);
            SessionState.SetString(StartedAtTicksKey6I, DateTime.UtcNow.Ticks.ToString());
            Debug.Log("[Stage7B] Entering Play Mode for Stage7B-6I runtime apply validation.");
            EditorApplication.isPlaying = true;
        }

        // ── 6J Entry Point ────────────────────────────────────────────────────
        [MenuItem(MenuPath6J)]
        public static void Run6J()
        {
            if (Application.isPlaying)
            {
                Debug.LogWarning("[Stage7B] Stage7B-6J menu must be started from Edit Mode.");
                return;
            }

            if (EditorSceneManager.GetActiveScene().isDirty)
            {
                Debug.LogWarning("[Stage7B] Active scene is dirty; proceeding by reopening Week7 scene for 6J automation.");
            }

            if (EditorSceneManager.OpenScene(ScenePath) == default)
            {
                Debug.LogError("[Stage7B] Failed to open Week7 scene.");
                return;
            }

            string report6J = GetAbsoluteProjectPath(ReportPath6J);
            if (File.Exists(report6J))
            {
                File.Delete(report6J);
            }

            SessionState.SetBool(PendingKey6J, true);
            SessionState.SetBool(TriggeredKey6J, false);
            SessionState.SetString(StartedAtTicksKey6J, DateTime.UtcNow.Ticks.ToString());
            Debug.Log("[Stage7B] Entering Play Mode for Stage7B-6J return direction mismatch audit.");
            EditorApplication.isPlaying = true;
        }

        [MenuItem(MenuPath6JImmediate)]
        public static void Run6JImmediateInPlayMode()
        {
            if (!Application.isPlaying)
            {
                Debug.LogError("[Stage7B] Stage7B-6J immediate menu requires Play Mode.");
                return;
            }

            Stage7BTeacherTrajectoryReplayRunner runner = UnityEngine.Object.FindFirstObjectByType<Stage7BTeacherTrajectoryReplayRunner>();
            if (runner == null)
            {
                var go = new GameObject("Stage7BTeacherReplayRunner");
                runner = go.AddComponent<Stage7BTeacherTrajectoryReplayRunner>();
            }

            runner.RunStage7B6JReturnDirectionAudit();
            Debug.Log("[Stage7B] Stage7B-6J immediate run invoked in Play Mode.");
        }

        [MenuItem("RTS/Week7/Stage7B/Open Week7 Scene")]
        public static void OpenWeek7Scene()
        {
            if (Application.isPlaying)
            {
                Debug.LogError("[Stage7B] Open Week7 Scene menu must be called from Edit Mode.");
                return;
            }

            EditorSceneManager.OpenScene(ScenePath);
            Debug.Log("[Stage7B] Week7 scene opened.");
        }

        private static void PollExecution()
        {
            // ── 6H poll ──────────────────────────────────────────────────────
            if (SessionState.GetBool(PendingKey, false))
            {
                if (HasTimedOut(StartedAtTicksKey))
                {
                    Debug.LogError("[Stage7B] Stage7B-6H timed out.");
                    EditorApplication.isPlaying = false;
                }
                else if (Application.isPlaying)
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

            // ── 6I poll ──────────────────────────────────────────────────────
            if (SessionState.GetBool(PendingKey6I, false))
            {
                if (HasTimedOut(StartedAtTicksKey6I))
                {
                    Debug.LogError("[Stage7B] Stage7B-6I timed out.");
                    EditorApplication.isPlaying = false;
                }
                else if (Application.isPlaying)
                {
                    if (!SessionState.GetBool(TriggeredKey6I, false))
                    {
                        Stage7BTeacherTrajectoryReplayRunner runner = UnityEngine.Object.FindFirstObjectByType<Stage7BTeacherTrajectoryReplayRunner>();
                        if (runner == null)
                        {
                            var go = new GameObject("Stage7BTeacherReplayRunner");
                            runner = go.AddComponent<Stage7BTeacherTrajectoryReplayRunner>();
                        }

                        runner.RunStage7B6IUnityRuntimeApplyValidation();
                        SessionState.SetBool(TriggeredKey6I, true);
                        return;
                    }

                    string report6I = GetAbsoluteProjectPath(ReportPath6I);
                    if (File.Exists(report6I))
                    {
                        Debug.Log("[Stage7B] Stage7B-6I report detected. Exiting Play Mode.");
                        EditorApplication.isPlaying = false;
                    }
                }
            }

            // ── 6J poll ──────────────────────────────────────────────────────
            if (SessionState.GetBool(PendingKey6J, false))
            {
                if (HasTimedOut(StartedAtTicksKey6J))
                {
                    Debug.LogError("[Stage7B] Stage7B-6J timed out.");
                    EditorApplication.isPlaying = false;
                }
                else if (Application.isPlaying)
                {
                    if (!SessionState.GetBool(TriggeredKey6J, false))
                    {
                        Stage7BTeacherTrajectoryReplayRunner runner = UnityEngine.Object.FindFirstObjectByType<Stage7BTeacherTrajectoryReplayRunner>();
                        if (runner == null)
                        {
                            var go = new GameObject("Stage7BTeacherReplayRunner");
                            runner = go.AddComponent<Stage7BTeacherTrajectoryReplayRunner>();
                        }

                        runner.RunStage7B6JReturnDirectionAudit();
                        SessionState.SetBool(TriggeredKey6J, true);
                        return;
                    }

                    string report6J = GetAbsoluteProjectPath(ReportPath6J);
                    if (File.Exists(report6J))
                    {
                        Debug.Log("[Stage7B] Stage7B-6J report detected. Exiting Play Mode.");
                        EditorApplication.isPlaying = false;
                    }
                }
            }
        }

        private static void OnPlayModeChanged(PlayModeStateChange state)
        {
            if (state != PlayModeStateChange.EnteredEditMode)
            {
                return;
            }

            if (SessionState.GetBool(PendingKey, false))
            {
                SessionState.SetBool(PendingKey, false);
                SessionState.SetBool(TriggeredKey, false);
                Validate6HReport();
            }

            if (SessionState.GetBool(PendingKey6I, false))
            {
                SessionState.SetBool(PendingKey6I, false);
                SessionState.SetBool(TriggeredKey6I, false);
                Validate6IReport();
            }

            if (SessionState.GetBool(PendingKey6J, false))
            {
                SessionState.SetBool(PendingKey6J, false);
                SessionState.SetBool(TriggeredKey6J, false);
                Validate6JReport();
            }
        }

        private static void ValidateReport() => Validate6HReport();

        private static void Validate6HReport()
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

        private static void Validate6IReport()
        {
            string report = GetAbsoluteProjectPath(ReportPath6I);
            if (!File.Exists(report))
            {
                Debug.LogError("[Stage7B] Stage7B-6I report was not created: " + report);
                return;
            }

            string json = File.ReadAllText(report);
            TryReadString(json, "status", out string status);
            TryReadInt(json, "stateSyncSuccessCount", out int syncOk);
            TryReadInt(json, "runtimeApplyAttemptedCount", out int applyAttempted);
            TryReadInt(json, "runtimeApplyAcceptedCount", out int applyAccepted);
            TryReadInt(json, "runtimeApplyRejectedCount", out int applyRejected);
            Debug.Log("[Stage7B] Stage7B-6I finished: status=" + status
                + ", stateSyncSuccessCount=" + syncOk
                + ", runtimeApplyAttemptedCount=" + applyAttempted
                + ", runtimeApplyAcceptedCount=" + applyAccepted
                + ", runtimeApplyRejectedCount=" + applyRejected);
        }

        private static void Validate6JReport()
        {
            string report = GetAbsoluteProjectPath(ReportPath6J);
            if (!File.Exists(report))
            {
                Debug.LogError("[Stage7B] Stage7B-6J report was not created: " + report);
                return;
            }

            string json = File.ReadAllText(report);
            TryReadString(json, "status", out string status);
            TryReadInt(json, "stateSyncSuccessCount", out int syncOk);
            TryReadInt(json, "returnCommandsTotal", out int returnTotal);
            TryReadInt(json, "returnCommandsMatched", out int returnMatched);
            TryReadInt(json, "returnDirectionMismatchCount", out int dirMismatch);
            Debug.Log("[Stage7B] Stage7B-6J finished: status=" + status
                + ", stateSyncSuccessCount=" + syncOk
                + ", returnCommandsTotal=" + returnTotal
                + ", returnCommandsMatched=" + returnMatched
                + ", returnDirectionMismatchCount=" + dirMismatch);
        }

        private static bool HasTimedOut(string ticksKey)
        {
            string startedAtTicks = SessionState.GetString(ticksKey, string.Empty);
            if (!long.TryParse(startedAtTicks, out long ticks))
            {
                return false;
            }

            return (DateTime.UtcNow - new DateTime(ticks, DateTimeKind.Utc)).TotalSeconds > TimeoutSeconds;
        }

        private static bool HasTimedOut()
        {
            return HasTimedOut(StartedAtTicksKey);
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
