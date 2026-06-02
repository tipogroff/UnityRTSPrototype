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
    public static class PpoSandboxBotR2EconomyCompositionSmokeMenu
    {
        private const string MenuPath = "RTS/Week7/PPO Sandbox/Run Bot R2 Economy+Composition Smoke";
        private const string ScenePath = "Assets/Scenes/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot.unity";
        private const string ArtifactFileName = "ppo_sandbox_bot_r2_economy_composition_smoke_runtime.json";
        private const string PendingKey = "RTS.Stage7B.PPO.BotR2EconomyComposition.Pending";
        private const string StartedAtTicksKey = "RTS.Stage7B.PPO.BotR2EconomyComposition.StartedAtTicks";
        private const double TimeoutSeconds = 30d;

        static PpoSandboxBotR2EconomyCompositionSmokeMenu()
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
                Debug.LogWarning("[PPO-SANDBOX-BOT-R2] Smoke run must be started from Edit Mode.");
                return;
            }

            if (SessionState.GetBool(PendingKey, false))
            {
                Debug.LogWarning("[PPO-SANDBOX-BOT-R2] Smoke run is already pending.");
                return;
            }

            if (EditorSceneManager.GetActiveScene().isDirty)
            {
                Debug.LogError("[PPO-SANDBOX-BOT-R2] Save or revert current scene before running smoke.");
                return;
            }

            if (EditorSceneManager.OpenScene(ScenePath) == default)
            {
                Debug.LogError("[PPO-SANDBOX-BOT-R2] Failed to open sandbox scene.");
                return;
            }

            string artifactPath = GetArtifactPath();
            if (File.Exists(artifactPath))
            {
                File.Delete(artifactPath);
            }

            SessionState.SetBool(PendingKey, true);
            SessionState.SetString(StartedAtTicksKey, DateTime.UtcNow.Ticks.ToString());
            Debug.Log("[PPO-SANDBOX-BOT-R2] Entering Play Mode for economy/composition smoke.");
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
            bool hasEnoughDecisions = adapter != null && adapter.CenterPressureDecisionsExecuted >= 120;
            bool hasCenterRouting = adapter != null && adapter.CenterPressureCenterRallyMoves > 0 && adapter.CenterPressureCenterAreaVisits > 0;
            bool hasCombatProduction = adapter != null && adapter.CenterPressureCombatProduceAttempts > 0;
            bool hasAttackSignal = adapter != null && (adapter.CenterPressureAttackIntentCount > 0 || adapter.CenterPressureAttackSubmitCount > 0);

            if (!timedOut && !(hasEnoughDecisions && hasCenterRouting && hasCombatProduction && hasAttackSignal))
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
                WriteRuntimeArtifact();
                if (!File.Exists(artifactPath))
                {
                    Debug.LogError("[PPO-SANDBOX-BOT-R2] Smoke run ended without runtime artifact.");
                    return;
                }
            }

            Debug.Log("[PPO-SANDBOX-BOT-R2] Smoke run finished. Artifact: " + ArtifactFileName);
        }

        private static void WriteRuntimeArtifact()
        {
            HeuristicPolicyAdapter adapter = UnityEngine.Object.FindFirstObjectByType<HeuristicPolicyAdapter>();
            MlAgentsTrainingBootstrap bootstrap = UnityEngine.Object.FindFirstObjectByType<MlAgentsTrainingBootstrap>();
            StudentMlAgent student = UnityEngine.Object.FindFirstObjectByType<StudentMlAgent>();

            Agent[] agents = UnityEngine.Object.FindObjectsByType<Agent>(FindObjectsInactive.Include, FindObjectsSortMode.None);
            int nonStudentAgentCount = agents.Count(a => a != null && a is not StudentMlAgent);

            var sb = new StringBuilder(4096);
            sb.AppendLine("{");
            sb.AppendLine("  \"sandbox_scene\": \"Assets/Scenes/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot.unity\",");
            sb.Append("  \"center_pressure_enabled\": ").Append(adapter != null && adapter.CenterPressureEnabled ? "true" : "false").AppendLine(",");
            sb.Append("  \"scripted_opponent_profile\": \"").Append(adapter != null ? adapter.Player2TacticProfile.ToString() : "unknown").AppendLine("\",");
            sb.Append("  \"student_agent_found\": ").Append(student != null ? "true" : "false").AppendLine(",");
            sb.Append("  \"bootstrap_found\": ").Append(bootstrap != null ? "true" : "false").AppendLine(",");
            sb.Append("  \"scripted_opponent_active\": ").Append(bootstrap != null && bootstrap.StepScriptedOpponent ? "true" : "false").AppendLine(",");
            sb.Append("  \"duplicate_agent_found\": ").Append(nonStudentAgentCount > 0 ? "true" : "false").AppendLine(",");
            sb.Append("  \"non_student_agent_count\": ").Append(nonStudentAgentCount).AppendLine(",");

            AppendCenterPressureMetrics(sb, adapter);

            sb.AppendLine("}");
            File.WriteAllText(GetArtifactPath(), sb.ToString(), Encoding.UTF8);
            Debug.Log("[PPO-SANDBOX-BOT-R2] Wrote runtime artifact.");
        }

        private static void AppendCenterPressureMetrics(StringBuilder sb, HeuristicPolicyAdapter adapter)
        {
            int decisions = adapter != null ? adapter.CenterPressureDecisionsExecuted : 0;
            int actionsAttempted = adapter != null ? adapter.CenterPressureActionsAttempted : 0;
            int accepted = adapter != null ? adapter.CenterPressureCommandsAccepted : 0;
            int rejected = adapter != null ? adapter.CenterPressureCommandsRejected : 0;
            int centerMoves = adapter != null ? adapter.CenterPressureCenterRallyMoves : 0;
            int centerVisits = adapter != null ? adapter.CenterPressureCenterAreaVisits : 0;
            int centerApproachMoves = adapter != null ? adapter.CenterPressureCenterToEnemyApproachMoves : 0;
            int edgeMoves = adapter != null ? adapter.CenterPressureEdgeLaneMoves : 0;
            int baseIdleSteps = adapter != null ? adapter.CenterPressureBaseIdleSteps : 0;
            int firstCenterMove = adapter != null ? adapter.CenterPressureFirstCenterMoveStep : -1;
            float avgDist = adapter != null ? adapter.CenterPressureAverageCombatDistanceToCenter : 0f;
            bool permanentBaseIdle = adapter != null && adapter.CenterPressurePermanentBaseIdle;
            bool centerObserved = adapter != null && adapter.CenterPressureObserved;
            bool healthy = adapter != null && adapter.CenterPressureEconomyCompositionHealthy;

            sb.Append("  \"bot_decisions_executed\": ").Append(decisions).AppendLine(",");
            sb.Append("  \"bot_actions_attempted\": ").Append(actionsAttempted).AppendLine(",");
            sb.Append("  \"bot_commands_accepted\": ").Append(accepted).AppendLine(",");
            sb.Append("  \"bot_commands_rejected\": ").Append(rejected).AppendLine(",");
            sb.Append("  \"worker_count_min\": ").Append(adapter != null ? adapter.CenterPressureWorkerCountMin : 0).AppendLine(",");
            sb.Append("  \"worker_count_max\": ").Append(adapter != null ? adapter.CenterPressureWorkerCountMax : 0).AppendLine(",");
            sb.Append("  \"worker_count_final\": ").Append(adapter != null ? adapter.CenterPressureWorkerCountFinal : 0).AppendLine(",");
            sb.Append("  \"worker_soft_cap\": ").Append(adapter != null ? adapter.CenterPressureWorkerSoftCap : 0).AppendLine(",");
            sb.Append("  \"worker_hard_cap\": ").Append(adapter != null ? adapter.CenterPressureWorkerHardCap : 0).AppendLine(",");
            sb.Append("  \"worker_produce_attempts\": ").Append(adapter != null ? adapter.CenterPressureWorkerProduceAttempts : 0).AppendLine(",");
            sb.Append("  \"worker_produce_blocked_by_cap\": ").Append(adapter != null ? adapter.CenterPressureWorkerProduceBlockedByCap : 0).AppendLine(",");
            sb.Append("  \"barracks_count\": ").Append(adapter != null ? adapter.CenterPressureBarracksCount : 0).AppendLine(",");
            sb.Append("  \"barracks_build_attempts\": ").Append(adapter != null ? adapter.CenterPressureBarracksBuildAttempts : 0).AppendLine(",");
            sb.Append("  \"barracks_build_accepted\": ").Append(adapter != null ? adapter.CenterPressureBarracksBuildAccepted : 0).AppendLine(",");
            sb.Append("  \"combat_unit_count_min\": ").Append(adapter != null ? adapter.CenterPressureCombatCountMin : 0).AppendLine(",");
            sb.Append("  \"combat_unit_count_max\": ").Append(adapter != null ? adapter.CenterPressureCombatCountMax : 0).AppendLine(",");
            sb.Append("  \"combat_unit_count_final\": ").Append(adapter != null ? adapter.CenterPressureCombatCountFinal : 0).AppendLine(",");
            sb.Append("  \"combat_unit_produce_attempts\": ").Append(adapter != null ? adapter.CenterPressureCombatProduceAttempts : 0).AppendLine(",");
            sb.Append("  \"combat_unit_produce_accepted\": ").Append(adapter != null ? adapter.CenterPressureCombatProduceAccepted : 0).AppendLine(",");
            sb.Append("  \"worker_idle_steps\": ").Append(adapter != null ? adapter.CenterPressureWorkerIdleSteps : 0).AppendLine(",");
            sb.Append("  \"worker_gather_attempts\": ").Append(adapter != null ? adapter.CenterPressureWorkerGatherAttempts : 0).AppendLine(",");
            sb.Append("  \"worker_build_attempts\": ").Append(adapter != null ? adapter.CenterPressureWorkerBuildAttempts : 0).AppendLine(",");
            sb.Append("  \"center_rally_moves\": ").Append(centerMoves).AppendLine(",");
            sb.Append("  \"center_area_visits\": ").Append(centerVisits).AppendLine(",");
            sb.Append("  \"center_to_enemy_approach_moves\": ").Append(centerApproachMoves).AppendLine(",");
            sb.Append("  \"edge_lane_moves\": ").Append(edgeMoves).AppendLine(",");
            sb.Append("  \"base_idle_steps\": ").Append(baseIdleSteps).AppendLine(",");
            sb.Append("  \"first_center_move_step\": ").Append(firstCenterMove).AppendLine(",");
            sb.Append("  \"attack_intent_count\": ").Append(adapter != null ? adapter.CenterPressureAttackIntentCount : 0).AppendLine(",");
            sb.Append("  \"attack_submit_count\": ").Append(adapter != null ? adapter.CenterPressureAttackSubmitCount : 0).AppendLine(",");
            sb.Append("  \"accepted_attack_count\": ").Append(adapter != null ? adapter.CenterPressureAcceptedAttackCount : 0).AppendLine(",");
            sb.Append("  \"first_attack_intent_step\": ").Append(adapter != null ? adapter.CenterPressureFirstAttackIntentStep : -1).AppendLine(",");
            sb.Append("  \"first_attack_submit_step\": ").Append(adapter != null ? adapter.CenterPressureFirstAttackSubmitStep : -1).AppendLine(",");
            sb.Append("  \"first_accepted_attack_step\": ").Append(adapter != null ? adapter.CenterPressureFirstAcceptedAttackStep : -1).AppendLine(",");
            sb.Append("  \"center_attack_intent_count\": ").Append(adapter != null ? adapter.CenterPressureCenterAttackIntentCount : 0).AppendLine(",");
            sb.Append("  \"center_attack_submit_count\": ").Append(adapter != null ? adapter.CenterPressureCenterAttackSubmitCount : 0).AppendLine(",");
            sb.Append("  \"center_accepted_attack_count\": ").Append(adapter != null ? adapter.CenterPressureCenterAcceptedAttackCount : 0).AppendLine(",");
            sb.Append("  \"avg_combat_distance_to_center\": ").Append(avgDist.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture)).AppendLine(",");
            sb.Append("  \"permanent_base_idle\": ").Append(permanentBaseIdle ? "true" : "false").AppendLine(",");
            sb.Append("  \"center_pressure_observed\": ").Append(centerObserved ? "true" : "false").AppendLine(",");
            sb.Append("  \"economy_composition_healthy\": ").Append(healthy ? "true" : "false").AppendLine();
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
