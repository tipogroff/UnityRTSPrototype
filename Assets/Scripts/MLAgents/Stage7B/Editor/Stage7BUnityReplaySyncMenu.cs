#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.RegularExpressions;
using RTS.Core;
using RTS.Gameplay;
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

        // ── Stage7B-7 Demo Recording Smoke ────────────────────────────────────
        private const string MenuPath7 = "RTS/Week7/Stage7B/Run Demo Recording Smoke 7";
        private const string MenuPath7Immediate = "RTS/Week7/Stage7B/Run Demo Recording Smoke 7 (Immediate In Play Mode)";
        private const string ReportPath7 = "python/stage7b_teacher_replay/stage7b_demo_recording_smoke_report.json";
        private const string PendingKey7 = "RTS.MLAgents.Stage7B.DemoSmoke7.Pending";
        private const string StartedAtTicksKey7 = "RTS.MLAgents.Stage7B.DemoSmoke7.StartedAtTicks";
        private const string TriggeredKey7 = "RTS.MLAgents.Stage7B.DemoSmoke7.Triggered";
        private const string StartedFromEditModeKey7 = "RTS.MLAgents.Stage7B.DemoSmoke7.StartedFromEditMode";
        private const double TimeoutSeconds7 = 300d;  // pre-processing up to 4096 steps + recording frames
        private const string DemoTempDirectory = "Library/Stage7B_DemoRecordingTemp";

        // Stage7B-7A Move/Harvest/Produce mismatch audit
        private const string MenuPath7A = "RTS/Week7/Stage7B/Run MHP Mismatch Audit 7A";
        private const string MenuPath7AImmediate = "RTS/Week7/Stage7B/Run MHP Mismatch Audit 7A (Immediate In Play Mode)";
        private const string ReportPath7A = "python/stage7b_teacher_replay/stage7b_7a_mhp_mismatch_audit_report.json";
        private const string PendingKey7A = "RTS.MLAgents.Stage7B.MhpMismatchAudit7A.Pending";
        private const string StartedAtTicksKey7A = "RTS.MLAgents.Stage7B.MhpMismatchAudit7A.StartedAtTicks";
        private const string TriggeredKey7A = "RTS.MLAgents.Stage7B.MhpMismatchAudit7A.Triggered";
        private const double TimeoutSeconds7A = 300d;

        // Stage7B-7B Move/Harvest/Produce direction mapping fix
        private const string MenuPath7B = "RTS/Week7/Stage7B/Run MHP Direction Fix 7B";
        private const string MenuPath7BImmediate = "RTS/Week7/Stage7B/Run MHP Direction Fix 7B (Immediate In Play Mode)";
        private const string ReportPath7B = "python/stage7b_teacher_replay/stage7b_7b_mhp_direction_fix_report.json";
        private const string PendingKey7B = "RTS.MLAgents.Stage7B.MhpDirectionFix7B.Pending";
        private const string StartedAtTicksKey7B = "RTS.MLAgents.Stage7B.MhpDirectionFix7B.StartedAtTicks";
        private const string TriggeredKey7B = "RTS.MLAgents.Stage7B.MhpDirectionFix7B.Triggered";
        private const double TimeoutSeconds7B = 300d;

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

        // ── 7 Entry Point ─────────────────────────────────────────────────────
        [MenuItem(MenuPath7)]
        public static void Run7()
        {
            if (Application.isPlaying)
            {
                Debug.LogWarning("[Stage7B] Stage7B-7 menu must be started from Edit Mode.");
                return;
            }

            if (EditorSceneManager.GetActiveScene().isDirty)
            {
                Debug.LogWarning("[Stage7B] Active scene is dirty; reopening Week7 scene for Stage7B-7 automation.");
            }

            if (EditorSceneManager.OpenScene(ScenePath) == default)
            {
                Debug.LogError("[Stage7B] Failed to open Week7 scene.");
                return;
            }

            // Delete stale report so polling detects a fresh write.
            string report7 = GetAbsoluteProjectPath(ReportPath7);
            if (File.Exists(report7)) File.Delete(report7);

            SessionState.SetBool(PendingKey7, true);
            SessionState.SetBool(TriggeredKey7, false);
            SessionState.SetBool(StartedFromEditModeKey7, true);
            SessionState.SetString(StartedAtTicksKey7, DateTime.UtcNow.Ticks.ToString());
            Debug.Log("[Stage7B] Entering Play Mode for Stage7B-7 demo recording smoke.");
            EditorApplication.isPlaying = true;
        }

        [MenuItem(MenuPath7Immediate)]
        public static void Run7ImmediateInPlayMode()
        {
            if (!Application.isPlaying)
            {
                Debug.LogError("[Stage7B] Stage7B-7 immediate menu requires Play Mode.");
                return;
            }

            SessionState.SetBool(StartedFromEditModeKey7, false);

            EnsureDemonstrationRecorderOnStudentAgent();

            RTS.MLAgents.Stage7B.TeacherReplay.Stage7BTeacherReplayDemoOrchestrator orchestrator =
                UnityEngine.Object.FindFirstObjectByType<RTS.MLAgents.Stage7B.TeacherReplay.Stage7BTeacherReplayDemoOrchestrator>();
            if (orchestrator == null)
            {
                var go = new GameObject("Stage7BDemoOrchestrator_7");
                orchestrator = go.AddComponent<RTS.MLAgents.Stage7B.TeacherReplay.Stage7BTeacherReplayDemoOrchestrator>();
            }

            orchestrator.ConfigureStartupContext(startedFromEditMode: false, enteredPlayMode: false, playModeReady: true);
            orchestrator.RunStage7B7DemoRecordingSmoke();
            Debug.Log("[Stage7B] Stage7B-7 immediate demo recording smoke invoked in Play Mode.");
        }

        [MenuItem(MenuPath7A)]
        public static void Run7A()
        {
            if (Application.isPlaying)
            {
                Debug.LogWarning("[Stage7B] Stage7B-7A menu must be started from Edit Mode.");
                return;
            }

            if (EditorSceneManager.GetActiveScene().isDirty)
            {
                Debug.LogWarning("[Stage7B] Active scene is dirty; reopening Week7 scene for Stage7B-7A automation.");
            }

            if (EditorSceneManager.OpenScene(ScenePath) == default)
            {
                Debug.LogError("[Stage7B] Failed to open Week7 scene.");
                return;
            }

            string report7A = GetAbsoluteProjectPath(ReportPath7A);
            if (File.Exists(report7A)) File.Delete(report7A);

            SessionState.SetBool(PendingKey7A, true);
            SessionState.SetBool(TriggeredKey7A, false);
            SessionState.SetString(StartedAtTicksKey7A, DateTime.UtcNow.Ticks.ToString());
            Debug.Log("[Stage7B] Entering Play Mode for Stage7B-7A M/H/P mismatch audit.");
            EditorApplication.isPlaying = true;
        }

        [MenuItem(MenuPath7AImmediate)]
        public static void Run7AImmediateInPlayMode()
        {
            if (!Application.isPlaying)
            {
                Debug.LogError("[Stage7B] Stage7B-7A immediate menu requires Play Mode.");
                return;
            }

            Stage7B7AMhpMismatchAuditRunner runner =
                UnityEngine.Object.FindFirstObjectByType<Stage7B7AMhpMismatchAuditRunner>();
            if (runner == null)
            {
                var go = new GameObject("Stage7B7A_MhpMismatchAuditRunner");
                runner = go.AddComponent<Stage7B7AMhpMismatchAuditRunner>();
            }

            runner.RunStage7B7AMhpMismatchAudit();
            Debug.Log("[Stage7B] Stage7B-7A immediate M/H/P mismatch audit invoked in Play Mode.");
        }

        [MenuItem(MenuPath7B)]
        public static void Run7B()
        {
            if (Application.isPlaying)
            {
                Debug.LogWarning("[Stage7B] Stage7B-7B menu must be started from Edit Mode.");
                return;
            }

            if (EditorSceneManager.GetActiveScene().isDirty)
            {
                Debug.LogWarning("[Stage7B] Active scene is dirty; reopening Week7 scene for Stage7B-7B automation.");
            }

            if (EditorSceneManager.OpenScene(ScenePath) == default)
            {
                Debug.LogError("[Stage7B] Failed to open Week7 scene.");
                return;
            }

            string report7B = GetAbsoluteProjectPath(ReportPath7B);
            if (File.Exists(report7B)) File.Delete(report7B);

            SessionState.SetBool(PendingKey7B, true);
            SessionState.SetBool(TriggeredKey7B, false);
            SessionState.SetString(StartedAtTicksKey7B, DateTime.UtcNow.Ticks.ToString());
            Debug.Log("[Stage7B] Entering Play Mode for Stage7B-7B M/H/P direction fix validation.");
            EditorApplication.isPlaying = true;
        }

        [MenuItem(MenuPath7BImmediate)]
        public static void Run7BImmediateInPlayMode()
        {
            if (!Application.isPlaying)
            {
                Debug.LogError("[Stage7B] Stage7B-7B immediate menu requires Play Mode.");
                return;
            }

            Stage7B7BMhpDirectionFixRunner runner =
                UnityEngine.Object.FindFirstObjectByType<Stage7B7BMhpDirectionFixRunner>();
            if (runner == null)
            {
                var go = new GameObject("Stage7B7B_MhpDirectionFixRunner");
                runner = go.AddComponent<Stage7B7BMhpDirectionFixRunner>();
            }

            runner.RunStage7B7BMhpDirectionFix();
            Debug.Log("[Stage7B] Stage7B-7B immediate M/H/P direction fix validation invoked in Play Mode.");
        }

        /// <summary>
        /// Adds and configures a DemonstrationRecorder on the StudentMlAgent GameObject if not present.
        /// Must be called in Play Mode (Edit Mode equivalent not needed — recorder requires runtime).
        /// </summary>
        private static void EnsureDemonstrationRecorderOnStudentAgent()
        {
            var student = UnityEngine.Object.FindFirstObjectByType<RTS.MLAgents.Stage7B.StudentMlAgent>();
            if (student == null)
            {
                Debug.LogWarning("[Stage7B] StudentMlAgent not found — cannot configure DemonstrationRecorder.");
                return;
            }

            var recorderType = System.Type.GetType(
                "Unity.MLAgents.Demonstrations.DemonstrationRecorder, Unity.ML-Agents");
            if (recorderType == null)
            {
                Debug.LogWarning("[Stage7B] DemonstrationRecorder type not found in loaded assemblies.");
                return;
            }

            UnityEngine.Component recorder = student.GetComponent(recorderType)
                ?? student.gameObject.AddComponent(recorderType);

            var nameField = recorderType.GetField("DemonstrationName",
                System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance);
            var dirField = recorderType.GetField("DemonstrationDirectory",
                System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance);
            var recordField = recorderType.GetField("Record",
                System.Reflection.BindingFlags.Public | System.Reflection.BindingFlags.Instance);

            nameField?.SetValue(recorder, "stage7b_teacher_replay_smoke");
            dirField?.SetValue(recorder, DemoTempDirectory);
            recordField?.SetValue(recorder, true);

            Debug.Log("[Stage7B] DemonstrationRecorder configured: name=stage7b_teacher_replay_smoke " +
                      "dir=" + DemoTempDirectory + " Record=true");
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

            // ── 7 poll (demo recording smoke) ─────────────────────────────────
            if (SessionState.GetBool(PendingKey7, false))
            {
                if (HasTimedOut(StartedAtTicksKey7, TimeoutSeconds7))
                {
                    Debug.LogError("[Stage7B] Stage7B-7 demo recording smoke timed out.");
                    EditorApplication.isPlaying = false;
                }
                else if (Application.isPlaying)
                {
                    if (!SessionState.GetBool(TriggeredKey7, false))
                    {
                        if (!AreRuntimeServicesReady())
                        {
                            return;
                        }

                        // Configure DemonstrationRecorder before starting orchestrator
                        EnsureDemonstrationRecorderOnStudentAgent();

                        RTS.MLAgents.Stage7B.TeacherReplay.Stage7BTeacherReplayDemoOrchestrator orchestrator =
                            UnityEngine.Object.FindFirstObjectByType<RTS.MLAgents.Stage7B.TeacherReplay.Stage7BTeacherReplayDemoOrchestrator>();
                        if (orchestrator == null)
                        {
                            var go = new GameObject("Stage7BDemoOrchestrator_7");
                            orchestrator = go.AddComponent<RTS.MLAgents.Stage7B.TeacherReplay.Stage7BTeacherReplayDemoOrchestrator>();
                        }

                        bool startedFromEditMode = SessionState.GetBool(StartedFromEditModeKey7, true);
                        orchestrator.ConfigureStartupContext(startedFromEditMode, enteredPlayMode: startedFromEditMode, playModeReady: true);
                        orchestrator.RunStage7B7DemoRecordingSmoke();
                        SessionState.SetBool(TriggeredKey7, true);
                        return;
                    }

                    string report7 = GetAbsoluteProjectPath(ReportPath7);
                    if (File.Exists(report7))
                    {
                        Debug.Log("[Stage7B] Stage7B-7 demo recording smoke report detected. Exiting Play Mode.");
                        EditorApplication.isPlaying = false;
                    }
                }
            }

            // Stage7B-7A poll (M/H/P mismatch audit)
            if (SessionState.GetBool(PendingKey7A, false))
            {
                if (HasTimedOut(StartedAtTicksKey7A, TimeoutSeconds7A))
                {
                    Debug.LogError("[Stage7B] Stage7B-7A M/H/P mismatch audit timed out.");
                    EditorApplication.isPlaying = false;
                }
                else if (Application.isPlaying)
                {
                    if (!SessionState.GetBool(TriggeredKey7A, false))
                    {
                        if (!AreRuntimeServicesReady())
                        {
                            return;
                        }

                        Stage7B7AMhpMismatchAuditRunner runner =
                            UnityEngine.Object.FindFirstObjectByType<Stage7B7AMhpMismatchAuditRunner>();
                        if (runner == null)
                        {
                            var go = new GameObject("Stage7B7A_MhpMismatchAuditRunner");
                            runner = go.AddComponent<Stage7B7AMhpMismatchAuditRunner>();
                        }

                        runner.RunStage7B7AMhpMismatchAudit();
                        SessionState.SetBool(TriggeredKey7A, true);
                        return;
                    }

                    string report7A = GetAbsoluteProjectPath(ReportPath7A);
                    if (File.Exists(report7A))
                    {
                        Debug.Log("[Stage7B] Stage7B-7A report detected. Exiting Play Mode.");
                        EditorApplication.isPlaying = false;
                    }
                }
            }

            // Stage7B-7B poll (M/H/P direction mapping fix)
            if (SessionState.GetBool(PendingKey7B, false))
            {
                if (HasTimedOut(StartedAtTicksKey7B, TimeoutSeconds7B))
                {
                    Debug.LogError("[Stage7B] Stage7B-7B M/H/P direction fix validation timed out.");
                    EditorApplication.isPlaying = false;
                }
                else if (Application.isPlaying)
                {
                    if (!SessionState.GetBool(TriggeredKey7B, false))
                    {
                        if (!AreRuntimeServicesReady())
                        {
                            return;
                        }

                        Stage7B7BMhpDirectionFixRunner runner =
                            UnityEngine.Object.FindFirstObjectByType<Stage7B7BMhpDirectionFixRunner>();
                        if (runner == null)
                        {
                            var go = new GameObject("Stage7B7B_MhpDirectionFixRunner");
                            runner = go.AddComponent<Stage7B7BMhpDirectionFixRunner>();
                        }

                        runner.RunStage7B7BMhpDirectionFix();
                        SessionState.SetBool(TriggeredKey7B, true);
                        return;
                    }

                    string report7B = GetAbsoluteProjectPath(ReportPath7B);
                    if (File.Exists(report7B))
                    {
                        Debug.Log("[Stage7B] Stage7B-7B report detected. Exiting Play Mode.");
                        EditorApplication.isPlaying = false;
                    }
                }
            }
        }

        private static bool AreRuntimeServicesReady()
        {
            if (MatchManager.Instance == null
                || GridManager.Instance == null
                || UnitRegistry.Instance == null
                || MatchBootstrap.Instance == null
                || ResourceManager.Instance == null)
            {
                return false;
            }

            return UnityEngine.Object.FindFirstObjectByType<RTS.MLAgents.Stage7B.StudentMlAgent>() != null;
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

            if (SessionState.GetBool(PendingKey7, false))
            {
                SessionState.SetBool(PendingKey7, false);
                SessionState.SetBool(TriggeredKey7, false);
                Validate7Report();
            }

            if (SessionState.GetBool(PendingKey7A, false))
            {
                SessionState.SetBool(PendingKey7A, false);
                SessionState.SetBool(TriggeredKey7A, false);
                Validate7AReport();
            }

            if (SessionState.GetBool(PendingKey7B, false))
            {
                SessionState.SetBool(PendingKey7B, false);
                SessionState.SetBool(TriggeredKey7B, false);
                Validate7BReport();
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

        private static void Validate7Report()
        {
            string report = GetAbsoluteProjectPath(ReportPath7);
            if (!File.Exists(report))
            {
                Debug.LogError("[Stage7B] Stage7B-7 smoke report was not created: " + report);
                return;
            }

            string json = File.ReadAllText(report);
            Stage7BDemoRecordingSmokeReport parsed = JsonUtility.FromJson<Stage7BDemoRecordingSmokeReport>(json);
            if (parsed == null)
            {
                Debug.LogError("[Stage7B] Stage7B-7 smoke report parsing failed: " + report);
                return;
            }

            // In Play Mode the temp demo file can stay locked. Finalize copy in Edit Mode.
            if (TryCopyLatestTempDemoToExpected(out string copiedPath, out long copiedSize, out string copyDiag))
            {
                parsed.demo_file_path = copiedPath;
                parsed.demo_file_exists = true;
                parsed.demo_file_size_bytes = copiedSize;
                parsed.notes.Add("EditMode finalize: copied temp demo to expected path.");
            }
            else
            {
                parsed.notes.Add("EditMode finalize copy not completed: " + copyDiag);
            }

            bool go = parsed.demo_file_exists
                && parsed.demo_file_size_bytes > 0
                && parsed.recorded_decisions > 0
                && parsed.runtime_apply_rejected_count == 0
                && !parsed.stage6b3_baseline_touched;

            parsed.status = go ? "GO" : "NO_GO";
            parsed.demo_recording_ready_for_imitation_smoke = go;
            parsed.generated_at_utc = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ");

            File.WriteAllText(report, JsonUtility.ToJson(parsed, true));

            string mdPath = GetAbsoluteProjectPath("python/stage7b_teacher_replay/stage7b_demo_recording_smoke_report.md");
            File.WriteAllText(mdPath, BuildStage7BSmokeMarkdown(parsed));

            Debug.Log("[Stage7B] Stage7B-7 demo recording smoke finished: status=" + parsed.status
                + ", recorded_decisions=" + parsed.recorded_decisions
                + ", runtime_apply_rejected=" + parsed.runtime_apply_rejected_count
                + ", demo_file_exists=" + parsed.demo_file_exists
                + ", demo_file_size_bytes=" + parsed.demo_file_size_bytes);

            if (parsed.status == "GO")
                Debug.Log("[Stage7B] Stage7B-7 GO. IMPORTANT: Run Stage7B-7A Move/Harvest/Produce mismatch audit before large dataset export.");
            else
                Debug.LogWarning("[Stage7B] Stage7B-7 NO-GO. Check smoke report for details.");
        }

        private static void Validate7AReport()
        {
            string report = GetAbsoluteProjectPath(ReportPath7A);
            if (!File.Exists(report))
            {
                Debug.LogError("[Stage7B] Stage7B-7A report was not created: " + report);
                return;
            }

            string json = File.ReadAllText(report);
            TryReadString(json, "status", out string status);
            TryReadString(json, "decision", out string decision);
            TryReadInt(json, "state_sync_failed_count", out int syncFailed);
            TryReadInt(json, "runtime_apply_rejected_count", out int applyRejected);
            TryReadInt(json, "mhp_y_axis_flip_count", out int yFlip);
            TryReadInt(json, "mhp_x_axis_flip_count", out int xFlip);
            Debug.Log("[Stage7B] Stage7B-7A finished: status=" + status
                + ", decision=" + decision
                + ", state_sync_failed_count=" + syncFailed
                + ", runtime_apply_rejected_count=" + applyRejected
                + ", y_axis_flip_count=" + yFlip
                + ", x_axis_flip_count=" + xFlip);
        }

        private static void Validate7BReport()
        {
            string report = GetAbsoluteProjectPath(ReportPath7B);
            if (!File.Exists(report))
            {
                Debug.LogError("[Stage7B] Stage7B-7B report was not created: " + report);
                return;
            }

            string json = File.ReadAllText(report);
            TryReadString(json, "status", out string status);
            TryReadString(json, "decision", out string decision);
            TryReadInt(json, "state_sync_failed_count", out int syncFailed);
            TryReadInt(json, "runtime_apply_rejected_count", out int applyRejected);
            TryReadInt(json, "candidate_match_count_after_7b", out int matchCount);
            TryReadInt(json, "return_direction_mismatch_count_after_7b", out int returnMismatch);
            Debug.Log("[Stage7B] Stage7B-7B finished: status=" + status
                + ", decision=" + decision
                + ", candidate_match_count_after_7b=" + matchCount
                + ", state_sync_failed_count=" + syncFailed
                + ", runtime_apply_rejected_count=" + applyRejected
                + ", return_direction_mismatch_count_after_7b=" + returnMismatch);
        }

        private static bool TryCopyLatestTempDemoToExpected(out string copiedPath, out long copiedSize, out string diagnostics)
        {
            copiedPath = string.Empty;
            copiedSize = 0;
            diagnostics = string.Empty;

            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            string tempDir = Path.GetFullPath(Path.Combine(projectRoot, DemoTempDirectory));
            if (!Directory.Exists(tempDir))
            {
                diagnostics = "temp demo directory not found: " + tempDir;
                return false;
            }

            string[] demoFiles = Directory.GetFiles(tempDir, "*.demo", SearchOption.TopDirectoryOnly);
            if (demoFiles == null || demoFiles.Length == 0)
            {
                diagnostics = "no temp demo files found in: " + tempDir;
                return false;
            }

            string latest = demoFiles[0];
            DateTime latestWrite = File.GetLastWriteTimeUtc(latest);
            for (int i = 1; i < demoFiles.Length; i++)
            {
                DateTime candidateWrite = File.GetLastWriteTimeUtc(demoFiles[i]);
                if (candidateWrite > latestWrite)
                {
                    latest = demoFiles[i];
                    latestWrite = candidateWrite;
                }
            }

            string expectedRelative = "Assets/Demonstrations/stage7b_teacher_replay_smoke.demo";
            string expected = Path.GetFullPath(Path.Combine(projectRoot, expectedRelative));
            string expectedDir = Path.GetDirectoryName(expected);
            if (!string.IsNullOrWhiteSpace(expectedDir)) Directory.CreateDirectory(expectedDir);

            File.Copy(latest, expected, true);

            copiedPath = expected;
            copiedSize = new FileInfo(expected).Length;
            diagnostics = "copied from " + latest;
            return true;
        }

        private static string BuildStage7BSmokeMarkdown(Stage7BDemoRecordingSmokeReport r)
        {
            var sb = new StringBuilder(2048);
            sb.AppendLine("# Stage7B-7 Demo Recording Smoke Report");
            sb.AppendLine();
            sb.AppendLine("- status: " + r.status);
            sb.AppendLine("- generated_at_utc: " + r.generated_at_utc);
            sb.AppendLine("- demo_file_path: " + r.demo_file_path);
            sb.AppendLine("- demo_file_exists: " + r.demo_file_exists.ToString().ToLowerInvariant());
            sb.AppendLine("- demo_file_size_bytes: " + r.demo_file_size_bytes);
            sb.AppendLine("- behavior_name: " + r.behavior_name);
            sb.AppendLine("- observation_size: " + r.observation_size);
            sb.AppendLine("- discrete_branch_count: " + r.discrete_branch_count);
            sb.AppendLine("- candidate_branch_size: " + r.candidate_branch_size);
            sb.AppendLine("- source_path: " + r.source_path);
            sb.AppendLine("- source_replay_ready: " + r.source_replay_ready.ToString().ToLowerInvariant());
            sb.AppendLine("- runtime_services_ready: " + r.runtime_services_ready.ToString().ToLowerInvariant());
            sb.AppendLine("- runtime_services_wait_seconds: " + r.runtime_services_wait_seconds.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture));
            sb.AppendLine("- runtime_apply_attempted_count: " + r.runtime_apply_attempted_count);
            sb.AppendLine("- runtime_apply_accepted_count: " + r.runtime_apply_accepted_count);
            sb.AppendLine("- runtime_apply_rejected_count: " + r.runtime_apply_rejected_count);
            sb.AppendLine("- runtime_apply_accept_rate: " + r.runtime_apply_accept_rate.ToString("0.######", System.Globalization.CultureInfo.InvariantCulture));
            sb.AppendLine("- recorded_decisions: " + r.recorded_decisions);
            sb.AppendLine("- stage6b3_baseline_touched: " + r.stage6b3_baseline_touched.ToString().ToLowerInvariant());
            return sb.ToString();
        }

        private static bool HasTimedOut(string ticksKey, double timeoutSec = TimeoutSeconds)
        {
            string startedAtTicks = SessionState.GetString(ticksKey, string.Empty);
            if (!long.TryParse(startedAtTicks, out long ticks))
            {
                return false;
            }

            return (DateTime.UtcNow - new DateTime(ticks, DateTimeKind.Utc)).TotalSeconds > timeoutSec;
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
