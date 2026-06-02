#if UNITY_EDITOR
using System;
using System.IO;
using System.Linq;
using System.Text;
using RTS.Core;
using RTS.Gameplay;
using RTS.ML;
using RTS.MLAgents.Stage7B;
using Unity.MLAgents;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.Editor
{
    [InitializeOnLoad]
    public static class PpoSandboxBotR4CenterCorridorRouteSmokeMenu
    {
        private const string MenuPath = "RTS/Week7/PPO Sandbox/Run Bot R4 Center Corridor Route Smoke";
        private const string ScenePath = "Assets/Scenes/PPO_TrainingSandbox_Player1AI_vs_ScriptedBot.unity";
        private const string ArtifactFileName = "ppo_sandbox_bot_r4_center_corridor_route_smoke_runtime.json";
        private const string PendingKey = "RTS.Stage7B.PPO.BotR4CenterCorridorRoute.Pending";
        private const string StartedAtTicksKey = "RTS.Stage7B.PPO.BotR4CenterCorridorRoute.StartedAtTicks";
        private const double TimeoutSeconds = 120d;

        static PpoSandboxBotR4CenterCorridorRouteSmokeMenu()
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
                Debug.LogWarning("[PPO-SANDBOX-BOT-R4] Smoke run must be started from Edit Mode.");
                return;
            }

            if (SessionState.GetBool(PendingKey, false))
            {
                Debug.LogWarning("[PPO-SANDBOX-BOT-R4] Smoke run is already pending.");
                return;
            }

            if (EditorSceneManager.GetActiveScene().isDirty)
            {
                Debug.LogError("[PPO-SANDBOX-BOT-R4] Save or revert current scene before running smoke.");
                return;
            }

            if (EditorSceneManager.OpenScene(ScenePath) == default)
            {
                Debug.LogError("[PPO-SANDBOX-BOT-R4] Failed to open sandbox scene.");
                return;
            }

            string artifactPath = GetArtifactPath();
            if (File.Exists(artifactPath))
            {
                File.Delete(artifactPath);
            }

            SessionState.SetBool(PendingKey, true);
            SessionState.SetString(StartedAtTicksKey, DateTime.UtcNow.Ticks.ToString());
            Debug.Log("[PPO-SANDBOX-BOT-R4] Entering Play Mode for center corridor route smoke.");
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
            bool hasCentralCorridorRoute = adapter != null
                                           && adapter.CenterPressureWaveCrossedCenter
                                           && adapter.CenterPressureCentralCorridorSteps > 0
                                           && adapter.CenterPressureRouteDominant
                                           && adapter.CenterPressureAttackAfterCenterCrossing;

            if (!timedOut && !(hasEnoughDecisions && hasCenterRouting && hasCombatProduction && hasAttackSignal && hasCentralCorridorRoute))
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
                    Debug.LogError("[PPO-SANDBOX-BOT-R4] Smoke run ended without runtime artifact.");
                    return;
                }
            }

            Debug.Log("[PPO-SANDBOX-BOT-R4] Smoke run finished. Artifact: " + ArtifactFileName);
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

            AppendResourceSettings(sb, bootstrap);
            AppendCenterPressureMetrics(sb, adapter);

            sb.AppendLine("}");
            File.WriteAllText(GetArtifactPath(), sb.ToString(), Encoding.UTF8);
            Debug.Log("[PPO-SANDBOX-BOT-R4] Wrote runtime artifact.");
        }

        private static void AppendResourceSettings(StringBuilder sb, MlAgentsTrainingBootstrap bootstrap)
        {
            MatchManager match = bootstrap != null ? bootstrap.MatchManager : null;
            ResourceManager resources = bootstrap != null ? bootstrap.ResourceManager : null;
            GameConfig config = bootstrap != null && bootstrap.MatchBootstrap != null
                ? bootstrap.MatchBootstrap.GetConfig()
                : null;
            ResourceNode[] nodes = resources != null
                ? resources.GetAllResourceNodes().Where(node => node != null).ToArray()
                : Array.Empty<ResourceNode>();

            AppendDefinition(sb, config, UnitType.Worker, "worker");
            AppendDefinition(sb, config, UnitType.Light, "light");
            AppendDefinition(sb, config, UnitType.Heavy, "heavy");
            AppendDefinition(sb, config, UnitType.Ranged, "ranged");
            AppendDefinition(sb, config, UnitType.Barracks, "barracks");
            int configuredStartResources = bootstrap != null ? bootstrap.ConfiguredStartResources : 0;
            sb.Append("  \"player1_start_resources\": ").Append(configuredStartResources).AppendLine(",");
            sb.Append("  \"player2_start_resources\": ").Append(configuredStartResources).AppendLine(",");
            sb.Append("  \"player1_current_resources\": ").Append(match != null ? match.GetPlayerState(Owner.Player1)?.CurrentResources ?? 0 : 0).AppendLine(",");
            sb.Append("  \"player2_current_resources\": ").Append(match != null ? match.GetPlayerState(Owner.Player2)?.CurrentResources ?? 0 : 0).AppendLine(",");
            sb.Append("  \"map_resource_node_count\": ").Append(nodes.Length).AppendLine(",");
            sb.Append("  \"map_total_available_resources\": ").Append(nodes.Sum(node => node.MaxResources)).AppendLine(",");
            sb.Append("  \"map_current_available_resources\": ").Append(nodes.Sum(node => node.CurrentResources)).AppendLine(",");
            sb.Append("  \"per_resource_node_amount\": ").Append(nodes.Length > 0 ? nodes[0].MaxResources : 0).AppendLine(",");
        }

        private static void AppendDefinition(StringBuilder sb, GameConfig config, UnitType unitType, string prefix)
        {
            UnitDefinition definition = config != null ? config.GetDefinition(unitType) : null;
            sb.Append("  \"").Append(prefix).Append("_cost\": ").Append(definition != null ? definition.productionCost : 0).AppendLine(",");
            sb.Append("  \"").Append(prefix).Append("_production_time\": ").Append(definition != null ? definition.productionTime : 0).AppendLine(",");
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
            sb.Append("  \"light_produce_attempts\": ").Append(adapter != null ? adapter.CenterPressureLightProduceAttempts : 0).AppendLine(",");
            sb.Append("  \"heavy_produce_attempts\": ").Append(adapter != null ? adapter.CenterPressureHeavyProduceAttempts : 0).AppendLine(",");
            sb.Append("  \"heavy_produce_accepted\": ").Append(adapter != null ? adapter.CenterPressureHeavyProduceAccepted : 0).AppendLine(",");
            sb.Append("  \"heavy_produce_blocked_by_cap\": ").Append(adapter != null ? adapter.CenterPressureHeavyProduceBlockedByCap : 0).AppendLine(",");
            sb.Append("  \"heavy_produce_blocked_by_cooldown\": ").Append(adapter != null ? adapter.CenterPressureHeavyProduceBlockedByCooldown : 0).AppendLine(",");
            sb.Append("  \"consecutive_heavy_produce_attempts\": ").Append(adapter != null ? adapter.CenterPressureConsecutiveHeavyProduceAttempts : 0).AppendLine(",");
            sb.Append("  \"ranged_produce_attempts\": ").Append(adapter != null ? adapter.CenterPressureRangedProduceAttempts : 0).AppendLine(",");
            sb.Append("  \"light_count_max\": ").Append(adapter != null ? adapter.CenterPressureLightCountMax : 0).AppendLine(",");
            sb.Append("  \"heavy_count_max\": ").Append(adapter != null ? adapter.CenterPressureHeavyCountMax : 0).AppendLine(",");
            sb.Append("  \"ranged_count_max\": ").Append(adapter != null ? adapter.CenterPressureRangedCountMax : 0).AppendLine(",");
            sb.Append("  \"total_army_count_max\": ").Append(adapter != null ? adapter.CenterPressureTotalArmyCountMax : 0).AppendLine(",");
            sb.Append("  \"light_hard_cap\": ").Append(adapter != null ? adapter.CenterPressureLightHardCap : 0).AppendLine(",");
            sb.Append("  \"heavy_hard_cap\": ").Append(adapter != null ? adapter.CenterPressureHeavyHardCap : 0).AppendLine(",");
            sb.Append("  \"ranged_hard_cap\": ").Append(adapter != null ? adapter.CenterPressureRangedHardCap : 0).AppendLine(",");
            sb.Append("  \"combat_unit_cap\": ").Append(adapter != null ? adapter.CenterPressureCombatUnitCap : 0).AppendLine(",");
            sb.Append("  \"total_army_cap\": ").Append(adapter != null ? adapter.CenterPressureTotalArmyCap : 0).AppendLine(",");
            sb.Append("  \"worker_idle_steps\": ").Append(adapter != null ? adapter.CenterPressureWorkerIdleSteps : 0).AppendLine(",");
            sb.Append("  \"worker_gather_attempts\": ").Append(adapter != null ? adapter.CenterPressureWorkerGatherAttempts : 0).AppendLine(",");
            sb.Append("  \"worker_build_attempts\": ").Append(adapter != null ? adapter.CenterPressureWorkerBuildAttempts : 0).AppendLine(",");
            sb.Append("  \"center_rally_moves\": ").Append(centerMoves).AppendLine(",");
            sb.Append("  \"center_area_visits\": ").Append(centerVisits).AppendLine(",");
            sb.Append("  \"center_to_enemy_approach_moves\": ").Append(centerApproachMoves).AppendLine(",");
            sb.Append("  \"edge_lane_moves\": ").Append(edgeMoves).AppendLine(",");
            sb.Append("  \"base_idle_steps\": ").Append(baseIdleSteps).AppendLine(",");
            sb.Append("  \"attack_wave_size_min\": ").Append(adapter != null ? adapter.CenterPressureAttackWaveSizeMin : 0).AppendLine(",");
            sb.Append("  \"attack_wave_size_max\": ").Append(adapter != null ? adapter.CenterPressureAttackWaveSizeMax : 0).AppendLine(",");
            sb.Append("  \"attack_wave_size_at_first_attack\": ").Append(adapter != null ? adapter.CenterPressureAttackWaveSizeAtFirstAttack : -1).AppendLine(",");
            sb.Append("  \"combat_units_sent_to_center\": ").Append(adapter != null ? adapter.CenterPressureCombatUnitsSentToCenter : 0).AppendLine(",");
            sb.Append("  \"combat_units_kept_near_base\": ").Append(adapter != null ? adapter.CenterPressureCombatUnitsKeptNearBase : 0).AppendLine(",");
            sb.Append("  \"over_army_cap_steps\": ").Append(adapter != null ? adapter.CenterPressureOverArmyCapSteps : 0).AppendLine(",");
            sb.Append("  \"central_corridor_steps\": ").Append(adapter != null ? adapter.CenterPressureCentralCorridorSteps : 0).AppendLine(",");
            sb.Append("  \"center_area_steps\": ").Append(adapter != null ? adapter.CenterPressureCenterAreaSteps : 0).AppendLine(",");
            sb.Append("  \"edge_lane_steps\": ").Append(adapter != null ? adapter.CenterPressureEdgeLaneSteps : 0).AppendLine(",");
            sb.Append("  \"base_area_steps\": ").Append(adapter != null ? adapter.CenterPressureBaseAreaSteps : 0).AppendLine(",");
            sb.Append("  \"center_crossing_count\": ").Append(adapter != null ? adapter.CenterPressureCenterCrossingCount : 0).AppendLine(",");
            sb.Append("  \"wave_crossed_center\": ").Append(adapter != null && adapter.CenterPressureWaveCrossedCenter ? "true" : "false").AppendLine(",");
            sb.Append("  \"center_crossing_step\": ").Append(adapter != null ? adapter.CenterPressureCenterCrossingStep : -1).AppendLine(",");
            sb.Append("  \"attack_after_center_crossing\": ").Append(adapter != null && adapter.CenterPressureAttackAfterCenterCrossing ? "true" : "false").AppendLine(",");
            sb.Append("  \"first_attack_after_center_crossing_step\": ").Append(adapter != null ? adapter.CenterPressureFirstAttackAfterCenterCrossingStep : -1).AppendLine(",");
            sb.Append("  \"edge_attack_detected\": ").Append(adapter != null && adapter.CenterPressureEdgeAttackDetected ? "true" : "false").AppendLine(",");
            sb.Append("  \"edge_attack_count\": ").Append(adapter != null ? adapter.CenterPressureEdgeAttackCount : 0).AppendLine(",");
            sb.Append("  \"central_approach_moves\": ").Append(adapter != null ? adapter.CenterPressureCentralApproachMoves : 0).AppendLine(",");
            sb.Append("  \"edge_approach_moves\": ").Append(adapter != null ? adapter.CenterPressureEdgeApproachMoves : 0).AppendLine(",");
            sb.Append("  \"central_route_ratio\": ").Append(adapter != null ? adapter.CenterPressureCentralRouteRatio.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture) : "0").AppendLine(",");
            sb.Append("  \"edge_route_ratio\": ").Append(adapter != null ? adapter.CenterPressureEdgeRouteRatio.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture) : "0").AppendLine(",");
            sb.Append("  \"center_route_dominant\": ").Append(adapter != null && adapter.CenterPressureRouteDominant ? "true" : "false").AppendLine(",");
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

