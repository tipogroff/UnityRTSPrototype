#if UNITY_EDITOR
using System;
using System.IO;
using System.Linq;
using System.Text;
using RTS.ML;
using RTS.MLAgents.Stage7B;
using Unity.MLAgents;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.Editor
{
    [InitializeOnLoad]
    public static class PpoSandboxBotR1CenterPressureSmokeMenu
    {
        private const string MenuPath = "RTS/Week7/PPO Sandbox/Run Bot R1 Center Pressure Smoke";
        private const string ScenePath = "Assets/Scenes/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot.unity";
        private const string ArtifactFileName = "ppo_sandbox_bot_r1_center_pressure_smoke_runtime.json";
        private const string PendingKey = "RTS.Stage7B.PPO.BotR1CenterPressure.Pending";
        private const string StartedAtTicksKey = "RTS.Stage7B.PPO.BotR1CenterPressure.StartedAtTicks";
        private const double TimeoutSeconds = 55d;

        static PpoSandboxBotR1CenterPressureSmokeMenu()
        {
            EditorApplication.update -= PollSmokeRun;
            EditorApplication.update += PollSmokeRun;
            EditorApplication.playModeStateChanged -= OnPlayModeStateChanged;
            EditorApplication.playModeStateChanged += OnPlayModeStateChanged;
        }

        [MenuItem(MenuPath)]
        public static void Run()
        {
            if (Application.isPlaying)
            {
                Debug.LogWarning("[PPO-SANDBOX-BOT-R1] Smoke run must be started from Edit Mode.");
                return;
            }

            if (SessionState.GetBool(PendingKey, false))
            {
                Debug.LogWarning("[PPO-SANDBOX-BOT-R1] Smoke run is already pending.");
                return;
            }

            if (EditorSceneManager.GetActiveScene().isDirty)
            {
                Debug.LogError("[PPO-SANDBOX-BOT-R1] Save or revert current scene before running smoke.");
                return;
            }

            if (EditorSceneManager.OpenScene(ScenePath) == default)
            {
                Debug.LogError("[PPO-SANDBOX-BOT-R1] Failed to open sandbox scene.");
                return;
            }

            string artifactPath = GetArtifactPath();
            if (File.Exists(artifactPath))
            {
                File.Delete(artifactPath);
            }

            SessionState.SetBool(PendingKey, true);
            SessionState.SetString(StartedAtTicksKey, DateTime.UtcNow.Ticks.ToString());
            Debug.Log("[PPO-SANDBOX-BOT-R1] Entering Play Mode for center-pressure smoke.");
            EditorApplication.isPlaying = true;
        }

        private static void PollSmokeRun()
        {
            if (!Application.isPlaying || !SessionState.GetBool(PendingKey, false))
            {
                return;
            }

            DateTime startedAtUtc = ReadStartTimeUtc();
            bool timedOut = startedAtUtc != default
                && (DateTime.UtcNow - startedAtUtc).TotalSeconds >= TimeoutSeconds;

            HeuristicPolicyAdapter adapter = UnityEngine.Object.FindFirstObjectByType<HeuristicPolicyAdapter>();
            bool hasEnoughDecisions = adapter != null && adapter.CenterPressureDecisionsExecuted >= 160;
            bool hasCenterRally = adapter != null && adapter.CenterPressureCenterRallyMoves > 0;
            bool hasCenterVisit = adapter != null && adapter.CenterPressureCenterAreaVisits > 0;
            bool hasAttackPhase = adapter != null && adapter.CenterPressureFirstAttackStep >= 0;

            if (!timedOut && !(hasEnoughDecisions && hasCenterRally && hasCenterVisit && hasAttackPhase))
            {
                return;
            }

            WriteRuntimeArtifact();
            EditorApplication.isPlaying = false;
        }

        private static void OnPlayModeStateChanged(PlayModeStateChange state)
        {
            if (state != PlayModeStateChange.EnteredEditMode || !SessionState.GetBool(PendingKey, false))
            {
                return;
            }

            SessionState.SetBool(PendingKey, false);

            string artifactPath = GetArtifactPath();
            if (!File.Exists(artifactPath))
            {
                Debug.LogError("[PPO-SANDBOX-BOT-R1] Smoke run ended without runtime artifact.");
            }
            else
            {
                Debug.Log("[PPO-SANDBOX-BOT-R1] Smoke run finished. Artifact: " + ArtifactFileName);
            }
        }

        private static void WriteRuntimeArtifact()
        {
            HeuristicPolicyAdapter adapter = UnityEngine.Object.FindFirstObjectByType<HeuristicPolicyAdapter>();
            MlAgentsTrainingBootstrap bootstrap = UnityEngine.Object.FindFirstObjectByType<MlAgentsTrainingBootstrap>();
            StudentMlAgent student = UnityEngine.Object.FindFirstObjectByType<StudentMlAgent>();

            Agent[] agents = UnityEngine.Object.FindObjectsByType<Agent>(FindObjectsInactive.Include, FindObjectsSortMode.None);
            int nonStudentAgentCount = agents.Count(a => a != null && a is not StudentMlAgent);

            int decisions = adapter != null ? adapter.CenterPressureDecisionsExecuted : 0;
            int actionsAttempted = adapter != null ? adapter.CenterPressureActionsAttempted : 0;
            int accepted = adapter != null ? adapter.CenterPressureCommandsAccepted : 0;
            int rejected = adapter != null ? adapter.CenterPressureCommandsRejected : 0;
            int centerMoves = adapter != null ? adapter.CenterPressureCenterRallyMoves : 0;
            int centerVisits = adapter != null ? adapter.CenterPressureCenterAreaVisits : 0;
            int edgeMoves = adapter != null ? adapter.CenterPressureEdgeLaneMoves : 0;
            int baseIdleSteps = adapter != null ? adapter.CenterPressureBaseIdleSteps : 0;
            int firstCenterMove = adapter != null ? adapter.CenterPressureFirstCenterMoveStep : -1;
            int firstAttack = adapter != null ? adapter.CenterPressureFirstAttackStep : -1;
            float avgDist = adapter != null ? adapter.CenterPressureAverageCombatDistanceToCenter : 0f;
            bool permanentBaseIdle = adapter != null && adapter.CenterPressurePermanentBaseIdle;
            bool centerObserved = adapter != null && adapter.CenterPressureObserved;

            var sb = new StringBuilder(1024);
            sb.AppendLine("{");
            sb.AppendLine("  \"sandbox_scene\": \"Assets/Scenes/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot.unity\",");
            sb.Append("  \"center_pressure_enabled\": ").Append(adapter != null && adapter.CenterPressureEnabled ? "true" : "false").AppendLine(",");
            sb.Append("  \"scripted_opponent_profile\": \"").Append(adapter != null ? adapter.Player2TacticProfile.ToString() : "unknown").AppendLine("\",");
            sb.Append("  \"student_agent_found\": ").Append(student != null ? "true" : "false").AppendLine(",");
            sb.Append("  \"bootstrap_found\": ").Append(bootstrap != null ? "true" : "false").AppendLine(",");
            sb.Append("  \"scripted_opponent_active\": ").Append(bootstrap != null && bootstrap.StepScriptedOpponent ? "true" : "false").AppendLine(",");
            sb.Append("  \"duplicate_agent_found\": ").Append(nonStudentAgentCount > 0 ? "true" : "false").AppendLine(",");
            sb.Append("  \"non_student_agent_count\": ").Append(nonStudentAgentCount).AppendLine(",");
            sb.Append("  \"bot_decisions_executed\": ").Append(decisions).AppendLine(",");
            sb.Append("  \"bot_actions_attempted\": ").Append(actionsAttempted).AppendLine(",");
            sb.Append("  \"bot_commands_accepted\": ").Append(accepted).AppendLine(",");
            sb.Append("  \"bot_commands_rejected\": ").Append(rejected).AppendLine(",");
            sb.Append("  \"center_rally_moves\": ").Append(centerMoves).AppendLine(",");
            sb.Append("  \"center_area_visits\": ").Append(centerVisits).AppendLine(",");
            sb.Append("  \"edge_lane_moves\": ").Append(edgeMoves).AppendLine(",");
            sb.Append("  \"base_idle_steps\": ").Append(baseIdleSteps).AppendLine(",");
            sb.Append("  \"first_center_move_step\": ").Append(firstCenterMove).AppendLine(",");
            sb.Append("  \"first_attack_step\": ").Append(firstAttack).AppendLine(",");
            sb.Append("  \"avg_combat_distance_to_center\": ").Append(avgDist.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture)).AppendLine(",");
            sb.Append("  \"permanent_base_idle\": ").Append(permanentBaseIdle ? "true" : "false").AppendLine(",");
            sb.Append("  \"center_pressure_observed\": ").Append(centerObserved ? "true" : "false").AppendLine();
            sb.AppendLine("}");

            File.WriteAllText(GetArtifactPath(), sb.ToString(), Encoding.UTF8);
            Debug.Log("[PPO-SANDBOX-BOT-R1] Wrote runtime artifact.");
        }

        private static DateTime ReadStartTimeUtc()
        {
            string raw = SessionState.GetString(StartedAtTicksKey, string.Empty);
            if (!long.TryParse(raw, out long ticks))
            {
                return default;
            }

            return new DateTime(ticks, DateTimeKind.Utc);
        }

        private static string GetArtifactPath()
        {
            string root = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            return Path.Combine(root, ArtifactFileName);
        }
    }
}
#endif
