#if UNITY_EDITOR
using System;
using RTS.MLAgents.Stage7B.Diagnostics;
using RTS.MLAgents.Stage7B.TeacherReplay;
using Unity.MLAgents.Policies;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.Editor
{
    public static class Stage7BPpoFineTuneSmokeMenu
    {
        private const string MenuPath = "RTS/Week7/Stage7B/Prepare PPO FineTune Smoke 9";
        private const string ScenePath = "Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity";

        private const string ActualCollectTracePath = "python/stage7b_teacher_replay/stage7b_9_actual_collect_observations_trace.jsonl";
        private const string ActionTracePath = "python/stage7b_teacher_replay/stage7b_9_action_trace.jsonl";
        private const string RuntimeApplyTracePath = "python/stage7b_teacher_replay/stage7b_9_runtime_apply_trace.jsonl";
        private const string DecisionSchedulerTracePath = "python/stage7b_teacher_replay/stage7b_9_decision_scheduler_trace.jsonl";
        private const string TrainingDiagnosticJsonPath = "python/stage7b_teacher_replay/stage7b_9_training_flow_diagnostic_report.json";
        private const string TrainingDiagnosticMdPath = "python/stage7b_teacher_replay/stage7b_9_training_flow_diagnostic_report.md";

        [MenuItem(MenuPath)]
        public static void PreparePpoFineTuneSmoke9()
        {
            if (Application.isPlaying)
            {
                Debug.LogError("[Stage7B] Prepare PPO FineTune Smoke 9 must run from Edit Mode.");
                return;
            }

            if (EditorSceneManager.GetActiveScene().isDirty)
            {
                EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo();
            }

            if (EditorSceneManager.OpenScene(ScenePath) == default)
            {
                Debug.LogError("[Stage7B] Failed to open Week7 scene for PPO smoke preparation.");
                return;
            }

            StudentMlAgent student = UnityEngine.Object.FindFirstObjectByType<StudentMlAgent>(FindObjectsInactive.Include);
            MlAgentsTrainingBootstrap bootstrap = UnityEngine.Object.FindFirstObjectByType<MlAgentsTrainingBootstrap>(FindObjectsInactive.Include);
            BehaviorParameters behavior = student != null ? student.GetComponent<BehaviorParameters>() : null;
            Unity.MLAgents.DecisionRequester requester = student != null ? student.GetComponent<Unity.MLAgents.DecisionRequester>() : null;
            Stage7BTrainingFlowDiagnostics diagnostics = UnityEngine.Object.FindFirstObjectByType<Stage7BTrainingFlowDiagnostics>(FindObjectsInactive.Include);
            Stage7BTeacherReplayDemoOrchestrator[] orchestrators =
                UnityEngine.Object.FindObjectsByType<Stage7BTeacherReplayDemoOrchestrator>(
                    FindObjectsInactive.Include,
                    FindObjectsSortMode.None);

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
                studentSerialized.FindProperty("_actualCollectTraceRelativePath")?.SetValue(ActualCollectTracePath);
                studentSerialized.FindProperty("_actionTraceRelativePath")?.SetValue(ActionTracePath);
                studentSerialized.FindProperty("_runtimeApplyTraceRelativePath")?.SetValue(RuntimeApplyTracePath);
                studentSerialized.FindProperty("_decisionSchedulerTraceRelativePath")?.SetValue(DecisionSchedulerTracePath);
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

            if (diagnostics != null)
            {
                SerializedObject diagnosticsSerialized = new SerializedObject(diagnostics);
                diagnosticsSerialized.FindProperty("_diagnosticJsonRelativePath")?.SetValue(TrainingDiagnosticJsonPath);
                diagnosticsSerialized.FindProperty("_diagnosticMdRelativePath")?.SetValue(TrainingDiagnosticMdPath);
                diagnosticsSerialized.FindProperty("_enableRuntimeTrainingFlowDiagnostics")?.SetValue(true);
                diagnosticsSerialized.ApplyModifiedPropertiesWithoutUndo();
                diagnostics.enabled = true;
                EditorUtility.SetDirty(diagnostics);
            }

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
                }
            }

            EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
            EditorSceneManager.SaveOpenScenes();
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            Debug.Log("[Stage7B] PPO FineTune Smoke 9 preparation finished. behavior_type=Default action_trace=" + ActionTracePath);
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

        private static void SetValue(this SerializedProperty property, string value)
        {
            if (property != null)
            {
                property.stringValue = value;
            }
        }
    }
}
#endif