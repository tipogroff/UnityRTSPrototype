#if UNITY_EDITOR
using System;
using System.IO;
using RTS.ML;
using RTS.MLAgents.Stage7B.Diagnostics;
using RTS.MLAgents.Stage7B.TeacherReplay;
using Unity.MLAgents;
using Unity.MLAgents.Actuators;
using Unity.MLAgents.Policies;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.Editor
{
    [InitializeOnLoad]
    public static class Stage7BInferenceMode8CMenu
    {
        private const string PrepareMenuPath = "RTS/Week7/Stage7B/Prepare ONNX Inference Mode 8C";
        private const string RunMenuPath = "RTS/Week7/Stage7B/Run Unity Inference Smoke 8C";
        private const string RunExtended8DMenuPath = "RTS/Week7/Stage7B/Run Extended ONNX Inference Smoke 8D.1";
        private const string OpenSceneMenuPath = "RTS/Week7/Stage7B/Open Week7 Scene 8C";

        private const string ScenePath = "Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity";
        private const string OnnxSourceRelativePath = "results/Stage7B_ImitationSmoke_010_PostKickConfirm/Stage7B_RTS_Student.onnx";
        private const string OnnxAssetTargetPath = "Assets/MLAgents/Models/Stage7B_RTS_Student_ImitationSmoke_010.onnx";

        private const string ReportJsonPath = "python/stage7b_teacher_replay/stage7b_8c2_padding_warning_fix_report.json";
        private const string ReportMdPath = "python/stage7b_teacher_replay/stage7b_8c2_padding_warning_fix_report.md";
        private const string TraceJsonlPath = "python/stage7b_teacher_replay/stage7b_8c2_inference_lifecycle_trace.jsonl";
        private const string CollectTraceJsonlPath = "python/stage7b_teacher_replay/stage7b_8c2_actual_collect_observations_trace.jsonl";
        private const string AgentInventoryJsonPath = "python/stage7b_teacher_replay/stage7b_8c2_agent_inventory.json";
        private const string SourceTraceJsonlPath = "python/stage7b_teacher_replay/stage7b_8b6_lifecycle_trace.jsonl";
        private const string Report8DJsonPath = "python/stage7b_teacher_replay/stage7b_8d1_decision_scheduling_fix_report.json";
        private const string Report8DMdPath = "python/stage7b_teacher_replay/stage7b_8d1_decision_scheduling_fix_report.md";
        private const string Trace8DJsonlPath = "python/stage7b_teacher_replay/stage7b_8d1_inference_lifecycle_trace.jsonl";
        private const string Collect8DTraceJsonlPath = "python/stage7b_teacher_replay/stage7b_8d1_actual_collect_observations_trace.jsonl";
        private const string Action8DTraceJsonlPath = "python/stage7b_teacher_replay/stage7b_8d1_action_trace.jsonl";
        private const string RuntimeApply8DTraceJsonlPath = "python/stage7b_teacher_replay/stage7b_8d1_runtime_apply_trace.jsonl";
        private const string DecisionScheduler8DTraceJsonlPath = "python/stage7b_teacher_replay/stage7b_8d1_decision_scheduler_trace.jsonl";
        private const string AgentInventory8DJsonPath = "python/stage7b_teacher_replay/stage7b_8d1_agent_inventory.json";
        private const string ConsoleExport8DJsonPath = "python/stage7b_teacher_replay/stage7b_8d1_unity_console_export.json";
        private const string PendingRunKey = "RTS.MLAgents.Stage7B.Inference8C.Pending";
        private const string TriggeredRunKey = "RTS.MLAgents.Stage7B.Inference8C.Triggered";
        private const string StartedAtTicksKey = "RTS.MLAgents.Stage7B.Inference8C.StartedAtTicks";
        private const string TimeoutHandledKey = "RTS.MLAgents.Stage7B.Inference8C.TimeoutHandled";
        private const string PendingRun8DKey = "RTS.MLAgents.Stage7B.Inference8D.Pending";
        private const string TriggeredRun8DKey = "RTS.MLAgents.Stage7B.Inference8D.Triggered";
        private const string StartedAtTicks8DKey = "RTS.MLAgents.Stage7B.Inference8D.StartedAtTicks";
        private const string TimeoutHandled8DKey = "RTS.MLAgents.Stage7B.Inference8D.TimeoutHandled";
        private const string DecisionsTarget8DKey = "RTS.MLAgents.Stage7B.Inference8D.DecisionsTarget";
        private const double MinPlayDurationSecondsBeforeExit = 10d;
        private const double TimeoutSeconds = 300d;
        private const double Timeout8DSeconds = 1800d;
        private const int DefaultDecisionsTarget8D = 3000;
        private const int FullHorizonDecisionsTarget8D = 6000;

        static Stage7BInferenceMode8CMenu()
        {
            EditorApplication.update -= PollExecution;
            EditorApplication.update += PollExecution;
        }

        [MenuItem(PrepareMenuPath)]
        public static void PrepareInferenceMode8C()
        {
            if (Application.isPlaying)
            {
                Debug.LogError("[Stage7B][8C] Preparation must run from Edit Mode.");
                return;
            }

            if (EditorSceneManager.GetActiveScene().isDirty)
            {
                EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo();
            }

            if (EditorSceneManager.OpenScene(ScenePath) == default)
            {
                Debug.LogError("[Stage7B][8C] Failed to open Week7 scene.");
                return;
            }

            bool copied = TryCopyOnnxToAssets(out bool importSucceeded, out string copyError);

            StudentMlAgent student = UnityEngine.Object.FindFirstObjectByType<StudentMlAgent>(FindObjectsInactive.Include);
            MlAgentsTrainingBootstrap bootstrap = UnityEngine.Object.FindFirstObjectByType<MlAgentsTrainingBootstrap>(FindObjectsInactive.Include);
            BehaviorParameters behavior = student != null ? student.GetComponent<BehaviorParameters>() : null;
            DecisionRequester requester = student != null ? student.GetComponent<DecisionRequester>() : null;

            if (bootstrap != null)
            {
                SerializedObject bootstrapSerialized = new SerializedObject(bootstrap);
                bootstrapSerialized.FindProperty("_autoConfigureMlAgents")?.SetValue(true);
                bootstrapSerialized.FindProperty("_forceTrainerControlledMode")?.SetValue(false);
                bootstrapSerialized.FindProperty("_stage7BRuntimeMode")?.SetValue((int)Stage7BRuntimeMode.InferenceOnly);
                bootstrapSerialized.ApplyModifiedPropertiesWithoutUndo();
                EditorUtility.SetDirty(bootstrap);
            }

            if (student != null)
            {
                SerializedObject studentSerialized = new SerializedObject(student);
                studentSerialized.FindProperty("_manualFixedUpdateDecisionRequests")?.SetValue(false);
                studentSerialized.FindProperty("_allowConcurrentDecisionSourcesForDebug")?.SetValue(false);
                studentSerialized.FindProperty("_enableDecisionRequesterWatchdogFallback")?.SetValue(false);
                studentSerialized.FindProperty("_actualCollectTraceRelativePath")?.SetValue(CollectTraceJsonlPath);
                studentSerialized.ApplyModifiedPropertiesWithoutUndo();
                EditorUtility.SetDirty(student);
                ClearTeacherReplayOrchestratorReference(student);
            }

            if (behavior != null)
            {
                behavior.BehaviorName = "Stage7B_RTS_Student";
                behavior.BehaviorType = BehaviorType.InferenceOnly;
                behavior.BrainParameters.VectorObservationSize = ObservationContract.TotalFloats;
                behavior.BrainParameters.NumStackedVectorObservations = 1;
                behavior.BrainParameters.ActionSpec = ActionSpec.MakeDiscrete(RTS.MLAgents.Stage7B.CandidateActions.MlAgentsCandidateActionList.BranchSize);
                AssignModelAsset(behavior, OnnxAssetTargetPath);
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

            Stage7BTeacherReplayDemoOrchestrator[] orchestrators =
                UnityEngine.Object.FindObjectsByType<Stage7BTeacherReplayDemoOrchestrator>(
                    FindObjectsInactive.Include,
                    FindObjectsSortMode.None);
            if (orchestrators != null)
            {
                for (int i = 0; i < orchestrators.Length; i++)
                {
                    if (orchestrators[i] == null)
                    {
                        continue;
                    }

                    orchestrators[i].enabled = false;
                    EditorUtility.SetDirty(orchestrators[i]);
                }
            }

            Stage7BInferenceSmokeDiagnostics diagnostics = EnsureDiagnosticsComponent(bootstrap, student);
            if (diagnostics != null)
            {
                SerializedObject diagnosticsSerialized = new SerializedObject(diagnostics);
                diagnosticsSerialized.FindProperty("_reportJsonRelativePath")?.SetValue(ReportJsonPath);
                diagnosticsSerialized.FindProperty("_reportMdRelativePath")?.SetValue(ReportMdPath);
                diagnosticsSerialized.FindProperty("_traceJsonlRelativePath")?.SetValue(TraceJsonlPath);
                diagnosticsSerialized.FindProperty("_sourceTraceRelativePath")?.SetValue(SourceTraceJsonlPath);
                diagnosticsSerialized.FindProperty("_actualCollectTraceRelativePath")?.SetValue(CollectTraceJsonlPath);
                diagnosticsSerialized.ApplyModifiedPropertiesWithoutUndo();
                diagnostics.SetPreparationContext(OnnxSourceRelativePath, OnnxAssetTargetPath, copied, importSucceeded);
                EditorUtility.SetDirty(diagnostics);
            }

            EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
            EditorSceneManager.SaveOpenScenes();
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            if (!string.IsNullOrWhiteSpace(copyError))
            {
                Debug.LogWarning("[Stage7B][8C] ONNX copy/import warning: " + copyError);
            }

            Debug.Log("[Stage7B][8C] Prepare ONNX Inference Mode completed. copied=" + copied
                      + " import_succeeded=" + importSucceeded
                      + " behavior_type=" + (behavior != null ? behavior.BehaviorType.ToString() : "missing")
                      + " model_assigned=" + (behavior != null && behavior.Model != null));
        }

        [MenuItem(RunMenuPath)]
        public static void RunInferenceSmoke8C()
        {
            if (Application.isPlaying)
            {
                Debug.LogWarning("[Stage7B][8C] Run menu must be started from Edit Mode.");
                return;
            }

            PrepareInferenceMode8C();
            string reportFullPath = GetAbsoluteProjectPath(ReportJsonPath);
            if (File.Exists(reportFullPath))
            {
                File.Delete(reportFullPath);
            }
            string reportMdFullPath = GetAbsoluteProjectPath(ReportMdPath);
            if (File.Exists(reportMdFullPath))
            {
                File.Delete(reportMdFullPath);
            }
            string traceFullPath = GetAbsoluteProjectPath(TraceJsonlPath);
            if (File.Exists(traceFullPath))
            {
                File.Delete(traceFullPath);
            }
            string collectTraceFullPath = GetAbsoluteProjectPath(CollectTraceJsonlPath);
            if (File.Exists(collectTraceFullPath))
            {
                File.Delete(collectTraceFullPath);
            }
            string agentInventoryFullPath = GetAbsoluteProjectPath(AgentInventoryJsonPath);
            if (File.Exists(agentInventoryFullPath))
            {
                File.Delete(agentInventoryFullPath);
            }

            SessionState.SetBool(PendingRunKey, true);
            SessionState.SetBool(TriggeredRunKey, false);
            SessionState.SetBool(TimeoutHandledKey, false);
            SessionState.SetString(StartedAtTicksKey, DateTime.UtcNow.Ticks.ToString());
            Debug.Log("[Stage7B][8C] Entering Play Mode for inference smoke run.");
            EditorApplication.isPlaying = true;
        }

        [MenuItem(RunExtended8DMenuPath)]
        public static void RunExtendedInferenceSmoke8D()
        {
            if (Application.isPlaying)
            {
                Debug.LogWarning("[Stage7B][8D] Run menu must be started from Edit Mode.");
                return;
            }

            PrepareInferenceMode8C();
            ConfigureForExtended8DArtifacts();
            DeleteIfExists(Report8DJsonPath);
            DeleteIfExists(Report8DMdPath);
            DeleteIfExists(Trace8DJsonlPath);
            DeleteIfExists(Collect8DTraceJsonlPath);
            DeleteIfExists(Action8DTraceJsonlPath);
            DeleteIfExists(RuntimeApply8DTraceJsonlPath);
            DeleteIfExists(DecisionScheduler8DTraceJsonlPath);
            DeleteIfExists(AgentInventory8DJsonPath);
            DeleteIfExists(ConsoleExport8DJsonPath);

            SessionState.SetBool(PendingRun8DKey, true);
            SessionState.SetBool(TriggeredRun8DKey, false);
            SessionState.SetBool(TimeoutHandled8DKey, false);
            SessionState.SetInt(DecisionsTarget8DKey, DefaultDecisionsTarget8D);
            SessionState.SetString(StartedAtTicks8DKey, DateTime.UtcNow.Ticks.ToString());
            Debug.Log("[Stage7B][8D] Entering Play Mode for extended inference smoke run.");
            EditorApplication.isPlaying = true;
        }

        [MenuItem("RTS/Week7/Stage7B/Run Full Horizon ONNX Inference Smoke 8D.2")]
        public static void RunFullHorizonInferenceSmoke8D()
        {
            if (Application.isPlaying)
            {
                Debug.LogWarning("[Stage7B][8D2] Run menu must be started from Edit Mode.");
                return;
            }

            PrepareInferenceMode8C();
            ConfigureForExtended8DArtifacts();
            DeleteIfExists(Report8DJsonPath);
            DeleteIfExists(Report8DMdPath);
            DeleteIfExists(Trace8DJsonlPath);
            DeleteIfExists(Collect8DTraceJsonlPath);
            DeleteIfExists(Action8DTraceJsonlPath);
            DeleteIfExists(RuntimeApply8DTraceJsonlPath);
            DeleteIfExists(DecisionScheduler8DTraceJsonlPath);
            DeleteIfExists(AgentInventory8DJsonPath);
            DeleteIfExists(ConsoleExport8DJsonPath);

            SessionState.SetBool(PendingRun8DKey, true);
            SessionState.SetBool(TriggeredRun8DKey, false);
            SessionState.SetBool(TimeoutHandled8DKey, false);
            SessionState.SetInt(DecisionsTarget8DKey, FullHorizonDecisionsTarget8D);
            SessionState.SetString(StartedAtTicks8DKey, DateTime.UtcNow.Ticks.ToString());
            Debug.Log("[Stage7B][8D2] Entering Play Mode for full-horizon inference run.");
            EditorApplication.isPlaying = true;
        }

        [MenuItem(OpenSceneMenuPath)]
        public static void OpenScene8C()
        {
            if (Application.isPlaying)
            {
                Debug.LogError("[Stage7B][8C] Open scene must be called from Edit Mode.");
                return;
            }

            EditorSceneManager.OpenScene(ScenePath);
            Debug.Log("[Stage7B][8C] Week7 scene opened.");
        }

        private static void PollExecution()
        {
            if (SessionState.GetBool(PendingRun8DKey, false))
            {
                PollExecution8D();
                return;
            }

            if (!SessionState.GetBool(PendingRunKey, false))
            {
                return;
            }

            if (HasTimedOut())
            {
                HandleTimeoutOnce();
                return;
            }

            if (!Application.isPlaying)
            {
                return;
            }

            if (!SessionState.GetBool(TriggeredRunKey, false))
            {
                SessionState.SetBool(TriggeredRunKey, true);
                return;
            }

            string reportFullPath = GetAbsoluteProjectPath(ReportJsonPath);
            if (File.Exists(reportFullPath))
            {
                if (!HasReachedMinimumRunDuration())
                {
                    return;
                }

                Debug.Log("[Stage7B][8C] Inference smoke report detected. Exiting Play Mode.");
                SessionState.SetBool(PendingRunKey, false);
                SessionState.SetBool(TriggeredRunKey, false);
                SessionState.SetBool(TimeoutHandledKey, false);
                SessionState.SetString(StartedAtTicksKey, string.Empty);
                EditorApplication.isPlaying = false;
            }
        }

        private static void PollExecution8D()
        {
            if (!SessionState.GetBool(PendingRun8DKey, false))
            {
                return;
            }

            if (HasTimedOut(StartedAtTicks8DKey, Timeout8DSeconds))
            {
                HandleTimeoutOnce8D();
                return;
            }

            if (!Application.isPlaying)
            {
                return;
            }

            if (!SessionState.GetBool(TriggeredRun8DKey, false))
            {
                SessionState.SetBool(TriggeredRun8DKey, true);
                return;
            }

            StudentMlAgent student = UnityEngine.Object.FindFirstObjectByType<StudentMlAgent>(FindObjectsInactive.Exclude);
            if (student == null)
            {
                return;
            }

            int decisionsTarget = Math.Max(1, SessionState.GetInt(DecisionsTarget8DKey, DefaultDecisionsTarget8D));
            int decisionsCompleted = student.Trace != null ? student.Trace.OnActionReceivedCalls : 0;
            bool terminalReached = student.TerminalCount > 0;
            bool reachedTarget = decisionsCompleted >= decisionsTarget;

            if (!reachedTarget && !terminalReached)
            {
                return;
            }

            Stage7BInferenceSmokeDiagnostics diagnostics = UnityEngine.Object.FindFirstObjectByType<Stage7BInferenceSmokeDiagnostics>();
            diagnostics?.ForceWriteSnapshot();

            string reportFullPath = GetAbsoluteProjectPath(Report8DJsonPath);
            if (!File.Exists(reportFullPath))
            {
                return;
            }

            if (!HasReachedMinimumRunDuration(StartedAtTicks8DKey, 5d))
            {
                return;
            }

            Debug.Log("[Stage7B][8D] Extended inference report detected (target/terminal reached). Exiting Play Mode.");
            SessionState.SetBool(PendingRun8DKey, false);
            SessionState.SetBool(TriggeredRun8DKey, false);
            SessionState.SetBool(TimeoutHandled8DKey, false);
            SessionState.SetString(StartedAtTicks8DKey, string.Empty);
            EditorApplication.isPlaying = false;
        }

        private static void HandleTimeoutOnce()
        {
            if (SessionState.GetBool(TimeoutHandledKey, false))
            {
                return;
            }

            SessionState.SetBool(TimeoutHandledKey, true);
            SessionState.SetBool(PendingRunKey, false);
            SessionState.SetBool(TriggeredRunKey, false);
            SessionState.SetString(StartedAtTicksKey, string.Empty);

            Stage7BInferenceSmokeDiagnostics diagnostics = UnityEngine.Object.FindFirstObjectByType<Stage7BInferenceSmokeDiagnostics>();
            if (diagnostics != null)
            {
                diagnostics.ForceWriteSnapshot();
            }

            Debug.LogError("[Stage7B][8C] Inference smoke timed out.");
            if (Application.isPlaying)
            {
                EditorApplication.isPlaying = false;
            }
        }

        private static void HandleTimeoutOnce8D()
        {
            if (SessionState.GetBool(TimeoutHandled8DKey, false))
            {
                return;
            }

            SessionState.SetBool(TimeoutHandled8DKey, true);
            SessionState.SetBool(PendingRun8DKey, false);
            SessionState.SetBool(TriggeredRun8DKey, false);
            SessionState.SetString(StartedAtTicks8DKey, string.Empty);

            Stage7BInferenceSmokeDiagnostics diagnostics = UnityEngine.Object.FindFirstObjectByType<Stage7BInferenceSmokeDiagnostics>();
            if (diagnostics != null)
            {
                diagnostics.ForceWriteSnapshot();
            }

            Debug.LogError("[Stage7B][8D] Extended inference smoke timed out.");
            if (Application.isPlaying)
            {
                EditorApplication.isPlaying = false;
            }
        }

        private static bool HasReachedMinimumRunDuration()
        {
            return HasReachedMinimumRunDuration(StartedAtTicksKey, MinPlayDurationSecondsBeforeExit);
        }

        private static bool HasReachedMinimumRunDuration(string startedAtKey, double minSeconds)
        {
            string ticksString = SessionState.GetString(startedAtKey, string.Empty);
            if (!long.TryParse(ticksString, out long ticks) || ticks <= 0)
            {
                return false;
            }

            DateTime started = new DateTime(ticks, DateTimeKind.Utc);
            return (DateTime.UtcNow - started).TotalSeconds >= minSeconds;
        }

        private static Stage7BInferenceSmokeDiagnostics EnsureDiagnosticsComponent(
            MlAgentsTrainingBootstrap bootstrap,
            StudentMlAgent student)
        {
            if (bootstrap != null)
            {
                Stage7BInferenceSmokeDiagnostics onBootstrap = bootstrap.GetComponent<Stage7BInferenceSmokeDiagnostics>();
                if (onBootstrap != null)
                {
                    return onBootstrap;
                }

                return bootstrap.gameObject.AddComponent<Stage7BInferenceSmokeDiagnostics>();
            }

            if (student != null)
            {
                Stage7BInferenceSmokeDiagnostics onStudent = student.GetComponent<Stage7BInferenceSmokeDiagnostics>();
                if (onStudent != null)
                {
                    return onStudent;
                }

                return student.gameObject.AddComponent<Stage7BInferenceSmokeDiagnostics>();
            }

            var host = new GameObject("Stage7B_InferenceSmokeDiagnostics");
            return host.AddComponent<Stage7BInferenceSmokeDiagnostics>();
        }

        private static void AssignModelAsset(BehaviorParameters behavior, string assetPath)
        {
            if (behavior == null || string.IsNullOrWhiteSpace(assetPath))
            {
                return;
            }

            UnityEngine.Object modelAsset = AssetDatabase.LoadMainAssetAtPath(assetPath);
            if (modelAsset == null)
            {
                return;
            }

            SerializedObject serialized = new SerializedObject(behavior);
            SerializedProperty modelProperty = serialized.FindProperty("m_Model");
            if (modelProperty != null)
            {
                modelProperty.objectReferenceValue = modelAsset;
                serialized.ApplyModifiedPropertiesWithoutUndo();
            }
        }

        private static void ClearTeacherReplayOrchestratorReference(StudentMlAgent student)
        {
            if (student == null)
            {
                return;
            }

            var prop = typeof(StudentMlAgent).GetProperty(
                "TeacherReplayOrchestrator",
                System.Reflection.BindingFlags.Instance
                | System.Reflection.BindingFlags.Public
                | System.Reflection.BindingFlags.NonPublic);
            if (prop != null && prop.CanWrite)
            {
                prop.SetValue(student, null);
            }
        }

        private static bool TryCopyOnnxToAssets(out bool importSucceeded, out string error)
        {
            importSucceeded = false;
            error = string.Empty;

            string sourceFullPath = GetAbsoluteProjectPath(OnnxSourceRelativePath);
            string targetFullPath = GetAbsoluteProjectPath(OnnxAssetTargetPath);

            if (!File.Exists(sourceFullPath))
            {
                error = "ONNX source missing: " + sourceFullPath;
                return false;
            }

            try
            {
                string targetDir = Path.GetDirectoryName(targetFullPath);
                if (!string.IsNullOrWhiteSpace(targetDir))
                {
                    Directory.CreateDirectory(targetDir);
                }

                File.Copy(sourceFullPath, targetFullPath, true);
                AssetDatabase.ImportAsset(OnnxAssetTargetPath, ImportAssetOptions.ForceSynchronousImport | ImportAssetOptions.ForceUpdate);
                UnityEngine.Object imported = AssetDatabase.LoadMainAssetAtPath(OnnxAssetTargetPath);
                importSucceeded = imported != null;
                if (!importSucceeded)
                {
                    error = "Unity import did not create a model asset for path: " + OnnxAssetTargetPath;
                }

                return true;
            }
            catch (Exception ex)
            {
                error = ex.Message;
                return false;
            }
        }

        private static bool HasTimedOut()
        {
            return HasTimedOut(StartedAtTicksKey, TimeoutSeconds);
        }

        private static bool HasTimedOut(string startedAtKey, double timeoutSeconds)
        {
            string ticksString = SessionState.GetString(startedAtKey, string.Empty);
            if (!long.TryParse(ticksString, out long ticks) || ticks <= 0)
            {
                return false;
            }

            DateTime started = new DateTime(ticks, DateTimeKind.Utc);
            return (DateTime.UtcNow - started).TotalSeconds > timeoutSeconds;
        }

        private static void ConfigureForExtended8DArtifacts()
        {
            StudentMlAgent student = UnityEngine.Object.FindFirstObjectByType<StudentMlAgent>(FindObjectsInactive.Include);
            MlAgentsTrainingBootstrap bootstrap = UnityEngine.Object.FindFirstObjectByType<MlAgentsTrainingBootstrap>(FindObjectsInactive.Include);
            Stage7BInferenceSmokeDiagnostics diagnostics = EnsureDiagnosticsComponent(bootstrap, student);

            if (student != null)
            {
                SerializedObject studentSerialized = new SerializedObject(student);
                studentSerialized.FindProperty("_actualCollectTraceRelativePath")?.SetValue(Collect8DTraceJsonlPath);
                studentSerialized.FindProperty("_actionTraceRelativePath")?.SetValue(Action8DTraceJsonlPath);
                studentSerialized.FindProperty("_runtimeApplyTraceRelativePath")?.SetValue(RuntimeApply8DTraceJsonlPath);
                studentSerialized.FindProperty("_decisionSchedulerTraceRelativePath")?.SetValue(DecisionScheduler8DTraceJsonlPath);
                studentSerialized.ApplyModifiedPropertiesWithoutUndo();
                EditorUtility.SetDirty(student);
            }

            if (diagnostics != null)
            {
                SerializedObject diagnosticsSerialized = new SerializedObject(diagnostics);
                diagnosticsSerialized.FindProperty("_reportJsonRelativePath")?.SetValue(Report8DJsonPath);
                diagnosticsSerialized.FindProperty("_reportMdRelativePath")?.SetValue(Report8DMdPath);
                diagnosticsSerialized.FindProperty("_traceJsonlRelativePath")?.SetValue(Trace8DJsonlPath);
                diagnosticsSerialized.FindProperty("_sourceTraceRelativePath")?.SetValue(SourceTraceJsonlPath);
                diagnosticsSerialized.FindProperty("_actualCollectTraceRelativePath")?.SetValue(Collect8DTraceJsonlPath);
                diagnosticsSerialized.FindProperty("_agentInventoryRelativePath")?.SetValue(AgentInventory8DJsonPath);
                diagnosticsSerialized.ApplyModifiedPropertiesWithoutUndo();
                EditorUtility.SetDirty(diagnostics);
            }

            EditorSceneManager.MarkSceneDirty(EditorSceneManager.GetActiveScene());
            EditorSceneManager.SaveOpenScenes();
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
        }

        private static void DeleteIfExists(string relativePath)
        {
            string fullPath = GetAbsoluteProjectPath(relativePath);
            if (File.Exists(fullPath))
            {
                File.Delete(fullPath);
            }
        }

        private static string GetAbsoluteProjectPath(string relativePath)
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
