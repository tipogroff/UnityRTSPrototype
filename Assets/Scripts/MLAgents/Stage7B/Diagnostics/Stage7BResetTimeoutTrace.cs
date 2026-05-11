using System;
using System.Globalization;
using System.IO;
using System.Text;
using RTS.Gameplay;
using RTS.MLAgents.Stage7B.TeacherReplay;
using Unity.MLAgents;
using Unity.MLAgents.Policies;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.Diagnostics
{
    public static class Stage7BResetTimeoutTrace
    {
        private const string TraceRelativePath = "python/stage7b_teacher_replay/stage7b_8b5_lifecycle_trace.jsonl";
        private static bool _clearedForSession;

        public static void ResetSession()
        {
            _clearedForSession = false;
        }

        public static void Record(
            string phase,
            StudentMlAgent agent = null,
            MlAgentsTrainingBootstrap bootstrap = null,
            string note = null,
            int observationLength = -1,
            int observationNanCount = -1,
            int lastActionIndex = -1,
            int candidateCount = -1,
            int maskedSlots = -1)
        {
            try
            {
                string path = ResolveProjectPath(TraceRelativePath);
                EnsureParentDirectory(path);
                if (!_clearedForSession)
                {
                    File.WriteAllText(path, string.Empty, Encoding.UTF8);
                    _clearedForSession = true;
                }

                string line = BuildJsonLine(
                    phase,
                    agent,
                    bootstrap,
                    note,
                    observationLength,
                    observationNanCount,
                    lastActionIndex,
                    candidateCount,
                    maskedSlots);

                File.AppendAllText(path, line + Environment.NewLine, Encoding.UTF8);
            }
            catch
            {
                // Diagnostics must not affect runtime behavior.
            }
        }

        private static string BuildJsonLine(
            string phase,
            StudentMlAgent agent,
            MlAgentsTrainingBootstrap bootstrap,
            string note,
            int observationLength,
            int observationNanCount,
            int lastActionIndex,
            int candidateCount,
            int maskedSlots)
        {
            BehaviorParameters behavior = agent != null ? agent.GetComponent<BehaviorParameters>() : null;
            DecisionRequester requester = agent != null ? agent.GetComponent<DecisionRequester>() : null;
            Stage7BTeacherReplayDemoOrchestrator sceneOrchestrator = FindSceneOrchestrator();
            Stage7BTeacherReplayDemoOrchestrator attachedOrchestrator = agent != null ? agent.TeacherReplayOrchestrator : null;
            Academy academy = Academy.IsInitialized ? Academy.Instance : null;
            MatchManager matchManager = bootstrap != null ? bootstrap.MatchManager : null;

            int effectiveObservationLength = observationLength >= 0 ? observationLength : (agent != null ? agent.LastObservationLength : -1);
            int effectiveObservationNanCount = observationNanCount >= 0 ? observationNanCount : (agent != null ? agent.LastObservationNanCount : -1);
            int effectiveActionIndex = lastActionIndex >= 0 ? lastActionIndex : (agent != null ? agent.LastActionCandidateIndex : -1);
            int effectiveCandidateCount = candidateCount >= 0 ? candidateCount : (agent != null && agent.CurrentCandidates != null ? agent.CurrentCandidates.CandidateCount : -1);

            var sb = new StringBuilder(1024);
            sb.Append('{');
            Append(sb, "timestamp_utc", DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture), true);
            Append(sb, "phase", phase, true);
            Append(sb, "note", note ?? string.Empty, true);
            Append(sb, "frame_count", Time.frameCount, true);
            Append(sb, "fixed_time", Time.fixedTime, true);
            Append(sb, "time_since_startup", Time.realtimeSinceStartup, true);
            Append(sb, "academy_initialized", academy != null, true);
            Append(sb, "academy_step_count", academy != null ? academy.StepCount : -1L, true);
            Append(sb, "communicator_on", academy != null && academy.IsCommunicatorOn, true);
            Append(sb, "behavior_name", behavior != null ? behavior.BehaviorName : "missing", true);
            Append(sb, "behavior_type", behavior != null ? behavior.BehaviorType.ToString() : "missing", true);
            Append(sb, "decision_requester_enabled", requester != null && requester.enabled, true);
            Append(sb, "decision_period", requester != null ? requester.DecisionPeriod : 0, true);
            Append(sb, "take_actions_between_decisions", requester != null && requester.TakeActionsBetweenDecisions, true);
            Append(sb, "manual_loop_enabled", agent != null && agent.ManualFixedUpdateDecisionRequestsEnabled, true);
            Append(sb, "watchdog_manual_fallback_enabled", agent != null && agent.DecisionRequesterWatchdogFallbackEnabled, true);
            Append(sb, "watchdog_manual_fallback_active", agent != null && agent.DecisionRequesterWatchdogFallbackActive, true);
            Append(sb, "teacher_replay_orchestrator_enabled", sceneOrchestrator != null && sceneOrchestrator.isActiveAndEnabled, true);
            Append(sb, "student_teacher_replay_orchestrator_is_null", attachedOrchestrator == null, true);
            Append(sb, "demo_mode_active", attachedOrchestrator != null && attachedOrchestrator.IsActive, true);
            Append(sb, "match_phase", matchManager != null ? matchManager.Phase.ToString() : "missing", true);
            Append(sb, "match_step", matchManager != null ? matchManager.Step : -1, true);
            Append(sb, "duplicate_spawn_detected", bootstrap != null && bootstrap.DuplicateSpawnDetected, true);
            Append(sb, "observation_length", effectiveObservationLength, true);
            Append(sb, "observation_nan_count", effectiveObservationNanCount, true);
            Append(sb, "last_action_index", effectiveActionIndex, true);
            Append(sb, "candidate_count", effectiveCandidateCount, true);
            Append(sb, "masked_slots", maskedSlots, false);
            sb.Append('}');
            return sb.ToString();
        }

        private static Stage7BTeacherReplayDemoOrchestrator FindSceneOrchestrator()
        {
            Stage7BTeacherReplayDemoOrchestrator[] all = UnityEngine.Object.FindObjectsByType<Stage7BTeacherReplayDemoOrchestrator>(
                FindObjectsInactive.Include,
                FindObjectsSortMode.None);
            return all != null && all.Length > 0 ? all[0] : null;
        }

        private static string ResolveProjectPath(string relativePath)
        {
            string relative = string.IsNullOrWhiteSpace(relativePath) ? TraceRelativePath : relativePath.Replace('\\', '/');
            if (Path.IsPathRooted(relative))
            {
                return relative;
            }

            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            return Path.Combine(projectRoot, relative.Replace('/', Path.DirectorySeparatorChar));
        }

        private static void EnsureParentDirectory(string path)
        {
            string directory = Path.GetDirectoryName(path);
            if (!string.IsNullOrWhiteSpace(directory))
            {
                Directory.CreateDirectory(directory);
            }
        }

        private static void Append(StringBuilder sb, string key, string value, bool comma)
        {
            sb.Append('"').Append(Escape(key)).Append('"').Append(':').Append('"').Append(Escape(value)).Append('"');
            if (comma) sb.Append(',');
        }

        private static void Append(StringBuilder sb, string key, int value, bool comma)
        {
            sb.Append('"').Append(Escape(key)).Append('"').Append(':').Append(value.ToString(CultureInfo.InvariantCulture));
            if (comma) sb.Append(',');
        }

        private static void Append(StringBuilder sb, string key, long value, bool comma)
        {
            sb.Append('"').Append(Escape(key)).Append('"').Append(':').Append(value.ToString(CultureInfo.InvariantCulture));
            if (comma) sb.Append(',');
        }

        private static void Append(StringBuilder sb, string key, float value, bool comma)
        {
            sb.Append('"').Append(Escape(key)).Append('"').Append(':').Append(value.ToString("R", CultureInfo.InvariantCulture));
            if (comma) sb.Append(',');
        }

        private static void Append(StringBuilder sb, string key, bool value, bool comma)
        {
            sb.Append('"').Append(Escape(key)).Append('"').Append(':').Append(value ? "true" : "false");
            if (comma) sb.Append(',');
        }

        private static string Escape(string value)
        {
            return (value ?? string.Empty).Replace("\\", "\\\\").Replace("\"", "\\\"");
        }
    }
}