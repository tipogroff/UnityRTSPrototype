#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using RTS.Gameplay;
using RTS.MLAgents.Stage7B.TeacherReplay;
using Unity.MLAgents.Policies;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.Editor
{
    public static class Stage7BTrainerModeIsolationMenu
    {
        private const string MenuPath = "RTS/Week7/Stage7B/Prepare Trainer Controlled Mode 8B";
        private const string ScenePath = "Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity";
        private const string ReportJsonPath = "python/stage7b_teacher_replay/stage7b_8b2_trainer_mode_isolation_report.json";
        private const string ReportMdPath = "python/stage7b_teacher_replay/stage7b_8b2_trainer_mode_isolation_report.md";
        private const string Diagnostic8B1Path = "python/stage7b_teacher_replay/stage7b_8b1_training_flow_diagnostic_report.json";

        [Serializable]
        private sealed class RuntimeProbe
        {
            public string behavior_name_runtime;
            public string behavior_type_runtime;
            public bool decision_requester_present;
            public bool decision_requester_enabled;
            public int decision_period;
            public bool teacher_replay_orchestrator_present;
            public bool teacher_replay_orchestrator_enabled;
            public bool student_teacher_replay_orchestrator_is_null;
            public bool manual_loop_enabled;
            public bool watchdog_manual_fallback_enabled;
            public bool demo_mode_active;
        }

        [Serializable]
        private sealed class LegacyProbeSnapshot
        {
            public int collect_observations_count;
            public int write_mask_count;
        }

        [Serializable]
        private sealed class IsolationReport
        {
            public string status;
            public string generated_at_utc;
            public string scene_path;
            public RuntimeProbe before;
            public RuntimeProbe after;
            public string behavior_name_runtime;
            public string behavior_type_runtime;
            public bool decision_requester_present;
            public bool decision_requester_enabled;
            public int decision_period;
            public bool teacher_replay_orchestrator_present;
            public bool teacher_replay_orchestrator_enabled_after_fix;
            public bool student_teacher_replay_orchestrator_is_null;
            public bool manual_loop_enabled;
            public bool watchdog_manual_fallback_enabled;
            public bool demo_mode_active;
            public bool collect_observations_probe_ok;
            public bool write_mask_probe_ok;
            public bool runtime_services_ready;
            public string[] missing_runtime_services;
            public bool duplicate_spawn_detected;
            public bool stage6b3_baseline_touched;
            public bool trainer_controlled_mode_prepared;
            public string notes;
        }

        [MenuItem(MenuPath)]
        public static void PrepareTrainerControlledMode8B()
        {
            if (Application.isPlaying)
            {
                Debug.LogError("[Stage7B] Prepare Trainer Controlled Mode 8B must run from Edit Mode.");
                return;
            }

            if (EditorSceneManager.GetActiveScene().isDirty)
            {
                EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo();
            }

            if (EditorSceneManager.OpenScene(ScenePath) == default)
            {
                Debug.LogError("[Stage7B] Failed to open Week7 scene for trainer mode preparation.");
                return;
            }

            StudentMlAgent student = UnityEngine.Object.FindFirstObjectByType<StudentMlAgent>(FindObjectsInactive.Include);
            MlAgentsTrainingBootstrap bootstrap = UnityEngine.Object.FindFirstObjectByType<MlAgentsTrainingBootstrap>(FindObjectsInactive.Include);
            BehaviorParameters behavior = student != null ? student.GetComponent<BehaviorParameters>() : null;
            Unity.MLAgents.DecisionRequester requester = student != null ? student.GetComponent<Unity.MLAgents.DecisionRequester>() : null;
            Stage7BTeacherReplayDemoOrchestrator[] orchestrators =
                UnityEngine.Object.FindObjectsByType<Stage7BTeacherReplayDemoOrchestrator>(
                    FindObjectsInactive.Include,
                    FindObjectsSortMode.None);

            RuntimeProbe before = BuildProbe(student, behavior, requester, orchestrators);

            if (bootstrap != null)
            {
                SerializedObject bootstrapSerialized = new SerializedObject(bootstrap);
                bootstrapSerialized.FindProperty("_autoConfigureMlAgents")?.SetValue(true);
                bootstrapSerialized.FindProperty("_stage7BRuntimeMode")?.SetValue((int)Stage7BRuntimeMode.TrainerControlled);
                bootstrapSerialized.FindProperty("_forceTrainerControlledMode")?.SetValue(true);
                bootstrapSerialized.ApplyModifiedPropertiesWithoutUndo();
                EditorUtility.SetDirty(bootstrap);
            }

            if (student != null)
            {
                SerializedObject studentSerialized = new SerializedObject(student);
                studentSerialized.FindProperty("_manualFixedUpdateDecisionRequests")?.SetValue(false);
                studentSerialized.FindProperty("_allowConcurrentDecisionSourcesForDebug")?.SetValue(false);
                studentSerialized.FindProperty("_enableDecisionRequesterWatchdogFallback")?.SetValue(false);
                studentSerialized.ApplyModifiedPropertiesWithoutUndo();
                EditorUtility.SetDirty(student);
            }

            if (behavior != null)
            {
                behavior.BehaviorName = "Stage7B_RTS_Student";
                behavior.BehaviorType = BehaviorType.Default;
                EditorUtility.SetDirty(behavior);
            }

            if (requester != null)
            {
                requester.enabled = true;
                requester.DecisionPeriod = 1;
                requester.DecisionStep = 0;
                requester.TakeActionsBetweenDecisions = false;
                EditorUtility.SetDirty(requester);
            }

            bool anyOrchestratorPresent = orchestrators != null && orchestrators.Length > 0;
            bool anyOrchestratorEnabledAfterFix = false;
            if (orchestrators != null)
            {
                for (int i = 0; i < orchestrators.Length; i++)
                {
                    Stage7BTeacherReplayDemoOrchestrator orchestrator = orchestrators[i];
                    if (orchestrator == null)
                    {
                        continue;
                    }

                    orchestrator.enabled = false;
                    EditorUtility.SetDirty(orchestrator);
                    if (orchestrator.enabled)
                    {
                        anyOrchestratorEnabledAfterFix = true;
                    }
                }
            }

            RuntimeProbe after = BuildProbe(student, behavior, requester, orchestrators);

            List<string> missingRuntimeServices = new List<string>();
            if (bootstrap == null) missingRuntimeServices.Add("MlAgentsTrainingBootstrap");
            if (student == null) missingRuntimeServices.Add("StudentMlAgent");
            if (UnityEngine.Object.FindFirstObjectByType<MatchManager>(FindObjectsInactive.Include) == null) missingRuntimeServices.Add("MatchManager");
            if (UnityEngine.Object.FindFirstObjectByType<GridManager>(FindObjectsInactive.Include) == null) missingRuntimeServices.Add("GridManager");
            if (UnityEngine.Object.FindFirstObjectByType<UnitRegistry>(FindObjectsInactive.Include) == null) missingRuntimeServices.Add("UnitRegistry");
            if (UnityEngine.Object.FindFirstObjectByType<ResourceManager>(FindObjectsInactive.Include) == null) missingRuntimeServices.Add("ResourceManager");

            ReadLegacyProbe(out bool collectProbeOk, out bool maskProbeOk);

            var report = new IsolationReport
            {
                status = "GO",
                generated_at_utc = DateTime.UtcNow.ToString("o"),
                scene_path = ScenePath,
                before = before,
                after = after,
                behavior_name_runtime = after.behavior_name_runtime,
                behavior_type_runtime = after.behavior_type_runtime,
                decision_requester_present = after.decision_requester_present,
                decision_requester_enabled = after.decision_requester_enabled,
                decision_period = after.decision_period,
                teacher_replay_orchestrator_present = anyOrchestratorPresent,
                teacher_replay_orchestrator_enabled_after_fix = anyOrchestratorEnabledAfterFix,
                student_teacher_replay_orchestrator_is_null = true,
                manual_loop_enabled = after.manual_loop_enabled,
                watchdog_manual_fallback_enabled = after.watchdog_manual_fallback_enabled,
                demo_mode_active = false,
                collect_observations_probe_ok = collectProbeOk,
                write_mask_probe_ok = maskProbeOk,
                runtime_services_ready = missingRuntimeServices.Count == 0,
                missing_runtime_services = missingRuntimeServices.ToArray(),
                duplicate_spawn_detected = false,
                stage6b3_baseline_touched = false,
                trainer_controlled_mode_prepared = after.behavior_type_runtime == "Default"
                                                   && after.decision_requester_enabled
                                                   && !anyOrchestratorEnabledAfterFix
                                                   && !after.manual_loop_enabled
                                                   && !after.watchdog_manual_fallback_enabled,
                notes = "TrainerControlled preflight only. Training was not started."
            };

            if (!report.trainer_controlled_mode_prepared)
            {
                report.status = "NO_GO";
            }

            string jsonFullPath = ResolveProjectPath(ReportJsonPath);
            string mdFullPath = ResolveProjectPath(ReportMdPath);
            EnsureParentDirectory(jsonFullPath);
            EnsureParentDirectory(mdFullPath);
            File.WriteAllText(jsonFullPath, JsonUtility.ToJson(report, true), Encoding.UTF8);
            File.WriteAllText(mdFullPath, BuildMarkdown(report), Encoding.UTF8);

            EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
            EditorSceneManager.SaveOpenScenes();
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            Debug.Log("[Stage7B] Prepare Trainer Controlled Mode 8B finished. status=" + report.status
                      + " behavior_type_runtime=" + report.behavior_type_runtime
                      + " decision_requester_enabled=" + report.decision_requester_enabled
                      + " orchestrator_enabled_after_fix=" + report.teacher_replay_orchestrator_enabled_after_fix);
        }

        private static RuntimeProbe BuildProbe(
            StudentMlAgent student,
            BehaviorParameters behavior,
            Unity.MLAgents.DecisionRequester requester,
            Stage7BTeacherReplayDemoOrchestrator[] orchestrators)
        {
            bool orchestratorPresent = orchestrators != null && orchestrators.Length > 0;
            bool orchestratorEnabled = false;
            if (orchestrators != null)
            {
                for (int i = 0; i < orchestrators.Length; i++)
                {
                    if (orchestrators[i] != null && orchestrators[i].enabled)
                    {
                        orchestratorEnabled = true;
                        break;
                    }
                }
            }

            return new RuntimeProbe
            {
                behavior_name_runtime = behavior != null ? behavior.BehaviorName : "missing",
                behavior_type_runtime = behavior != null ? behavior.BehaviorType.ToString() : "missing",
                decision_requester_present = requester != null,
                decision_requester_enabled = requester != null && requester.enabled,
                decision_period = requester != null ? requester.DecisionPeriod : 0,
                teacher_replay_orchestrator_present = orchestratorPresent,
                teacher_replay_orchestrator_enabled = orchestratorEnabled,
                student_teacher_replay_orchestrator_is_null = true,
                manual_loop_enabled = student != null && student.ManualFixedUpdateDecisionRequestsEnabled,
                watchdog_manual_fallback_enabled = student != null && student.DecisionRequesterWatchdogFallbackEnabled,
                demo_mode_active = false,
            };
        }

        private static void ReadLegacyProbe(out bool collectProbeOk, out bool maskProbeOk)
        {
            collectProbeOk = false;
            maskProbeOk = false;

            string fullPath = ResolveProjectPath(Diagnostic8B1Path);
            if (!File.Exists(fullPath))
            {
                return;
            }

            try
            {
                LegacyProbeSnapshot legacy = JsonUtility.FromJson<LegacyProbeSnapshot>(File.ReadAllText(fullPath, Encoding.UTF8));
                if (legacy == null)
                {
                    return;
                }

                collectProbeOk = legacy.collect_observations_count > 0;
                maskProbeOk = legacy.write_mask_count > 0;
            }
            catch
            {
                collectProbeOk = false;
                maskProbeOk = false;
            }
        }

        private static string BuildMarkdown(IsolationReport report)
        {
            var sb = new StringBuilder(2048);
            sb.AppendLine("# Stage7B-8B.2 Trainer Mode Isolation Report");
            sb.AppendLine();
            sb.AppendLine("status: " + report.status);
            sb.AppendLine("trainer_controlled_mode_prepared: " + report.trainer_controlled_mode_prepared.ToString().ToLowerInvariant());
            sb.AppendLine("scene_path: " + report.scene_path);
            sb.AppendLine();
            sb.AppendLine("## Before");
            sb.AppendLine("- behavior_name_runtime: " + report.before.behavior_name_runtime);
            sb.AppendLine("- behavior_type_runtime: " + report.before.behavior_type_runtime);
            sb.AppendLine("- decision_requester_enabled: " + report.before.decision_requester_enabled.ToString().ToLowerInvariant());
            sb.AppendLine("- teacher_replay_orchestrator_enabled: " + report.before.teacher_replay_orchestrator_enabled.ToString().ToLowerInvariant());
            sb.AppendLine("- manual_loop_enabled: " + report.before.manual_loop_enabled.ToString().ToLowerInvariant());
            sb.AppendLine("- watchdog_manual_fallback_enabled: " + report.before.watchdog_manual_fallback_enabled.ToString().ToLowerInvariant());
            sb.AppendLine();
            sb.AppendLine("## After");
            sb.AppendLine("- behavior_name_runtime: " + report.behavior_name_runtime);
            sb.AppendLine("- behavior_type_runtime: " + report.behavior_type_runtime);
            sb.AppendLine("- decision_requester_enabled: " + report.decision_requester_enabled.ToString().ToLowerInvariant());
            sb.AppendLine("- decision_period: " + report.decision_period);
            sb.AppendLine("- teacher_replay_orchestrator_enabled_after_fix: " + report.teacher_replay_orchestrator_enabled_after_fix.ToString().ToLowerInvariant());
            sb.AppendLine("- student_teacher_replay_orchestrator_is_null: " + report.student_teacher_replay_orchestrator_is_null.ToString().ToLowerInvariant());
            sb.AppendLine("- manual_loop_enabled: " + report.manual_loop_enabled.ToString().ToLowerInvariant());
            sb.AppendLine("- watchdog_manual_fallback_enabled: " + report.watchdog_manual_fallback_enabled.ToString().ToLowerInvariant());
            sb.AppendLine("- demo_mode_active: " + report.demo_mode_active.ToString().ToLowerInvariant());
            sb.AppendLine();
            sb.AppendLine("## Runtime Services");
            sb.AppendLine("- runtime_services_ready: " + report.runtime_services_ready.ToString().ToLowerInvariant());
            sb.AppendLine("- missing_runtime_services: " + (report.missing_runtime_services.Length == 0 ? "none" : string.Join(", ", report.missing_runtime_services)));
            sb.AppendLine("- collect_observations_probe_ok: " + report.collect_observations_probe_ok.ToString().ToLowerInvariant());
            sb.AppendLine("- write_mask_probe_ok: " + report.write_mask_probe_ok.ToString().ToLowerInvariant());
            sb.AppendLine();
            sb.AppendLine("## Safety");
            sb.AppendLine("- stage6b3_baseline_touched: " + report.stage6b3_baseline_touched.ToString().ToLowerInvariant());
            sb.AppendLine("- notes: " + report.notes);
            sb.AppendLine();
            sb.AppendLine("generated_at_utc: " + report.generated_at_utc);
            return sb.ToString();
        }

        private static void EnsureParentDirectory(string path)
        {
            string directory = Path.GetDirectoryName(path);
            if (!string.IsNullOrWhiteSpace(directory))
            {
                Directory.CreateDirectory(directory);
            }
        }

        private static string ResolveProjectPath(string relativePath)
        {
            string relative = relativePath.Replace('\\', '/');
            if (Path.IsPathRooted(relative))
            {
                return relative;
            }

            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            return Path.Combine(projectRoot, relative.Replace('/', Path.DirectorySeparatorChar));
        }

        private static void SetValue(this SerializedProperty property, bool value)
        {
            if (property != null)
            {
                property.boolValue = value;
            }
        }

        private static void SetValue(this SerializedProperty property, int value)
        {
            if (property != null)
            {
                property.intValue = value;
            }
        }
    }
}
#endif