using System;
using System.IO;
using System.Text;
using UnityEngine;

namespace RTS.MLAgents.Stage7B
{
    [DisallowMultipleComponent]
    public sealed class Week7ScriptedOpponentPacing : MonoBehaviour
    {
        [Header("Week7 Scripted Opponent Throttle")]
        [SerializeField] private bool _enableWeek7BotThrottle = true;
        [SerializeField] private bool _throttleAffectsOnlyOpponent = true;
        [SerializeField, Min(1)] private int _botDecisionIntervalSteps = 3;
        [SerializeField, Min(0f)] private float _botActionCooldownSeconds;
        [SerializeField] private string _reportRelativePath = "python/stage7b_teacher_replay/stage7b_week7_scripted_bot_throttle_report.json";

        private int _decisionAttemptCounter;
        private float _lastDecisionTime = float.NegativeInfinity;
        private int _botActionsAttemptedAfter;
        private int _studentActionsAttempted;
        private int _acceptedBotCommands;
        private int _rejectedBotCommands;
        private string _terminalReason = "not_terminal";
        private bool _duplicateSpawnDetected;
        private bool _reportWrittenThisEpisode;

        public bool ThrottleEnabled => _enableWeek7BotThrottle;
        public int BotDecisionIntervalSteps => Mathf.Max(1, _botDecisionIntervalSteps);
        public bool ThrottleAffectsOnlyOpponent => _throttleAffectsOnlyOpponent;
        public int StudentActionsAttempted => _studentActionsAttempted;
        public int BotActionsAttempted => _botActionsAttemptedAfter;
        public int AcceptedBotCommands => _acceptedBotCommands;
        public int RejectedBotCommands => _rejectedBotCommands;
        public string TerminalReason => _terminalReason;

        public void ResetForEpisode(bool duplicateSpawnDetected)
        {
            _decisionAttemptCounter = 0;
            _lastDecisionTime = float.NegativeInfinity;
            _botActionsAttemptedAfter = 0;
            _studentActionsAttempted = 0;
            _acceptedBotCommands = 0;
            _rejectedBotCommands = 0;
            _terminalReason = "not_terminal";
            _duplicateSpawnDetected = duplicateSpawnDetected;
            _reportWrittenThisEpisode = false;
        }

        public void RecordStudentActionAttempt()
        {
            _studentActionsAttempted++;
        }

        public bool ShouldExecuteBotDecisionStep(float nowSeconds)
        {
            _decisionAttemptCounter++;

            if (!_enableWeek7BotThrottle || !_throttleAffectsOnlyOpponent)
            {
                _botActionsAttemptedAfter++;
                _lastDecisionTime = nowSeconds;
                return true;
            }

            int interval = Mathf.Max(1, _botDecisionIntervalSteps);
            bool intervalReady = ((_decisionAttemptCounter - 1) % interval) == 0;
            bool cooldownReady = _botActionCooldownSeconds <= 0f
                                 || nowSeconds - _lastDecisionTime >= _botActionCooldownSeconds;
            if (!intervalReady || !cooldownReady)
            {
                return false;
            }

            _botActionsAttemptedAfter++;
            _lastDecisionTime = nowSeconds;
            return true;
        }

        public void RecordBotDecisionOutcome(int acceptedCommands, int rejectedCommands)
        {
            _acceptedBotCommands += Mathf.Max(0, acceptedCommands);
            _rejectedBotCommands += Mathf.Max(0, rejectedCommands);
        }

        public void FinalizeEpisodeAndWriteReport(string terminalReason)
        {
            _terminalReason = string.IsNullOrWhiteSpace(terminalReason) ? "unknown" : terminalReason;
            if (_reportWrittenThisEpisode)
            {
                return;
            }

            _reportWrittenThisEpisode = true;
            WriteReport();
        }

        private void WriteReport()
        {
            try
            {
                string fullPath = ResolveReportPath();
                string directory = Path.GetDirectoryName(fullPath);
                if (!string.IsNullOrEmpty(directory))
                {
                    Directory.CreateDirectory(directory);
                }

                var sb = new StringBuilder(512);
                sb.AppendLine("{");
                sb.Append("  \"throttle_enabled\": ").Append(_enableWeek7BotThrottle ? "true" : "false").AppendLine(",");
                sb.Append("  \"bot_decision_interval_steps\": ").Append(Mathf.Max(1, _botDecisionIntervalSteps)).AppendLine(",");
                sb.AppendLine("  \"bot_actions_attempted_before_or_baseline\": null,");
                sb.Append("  \"bot_actions_attempted_after\": ").Append(_botActionsAttemptedAfter).AppendLine(",");
                sb.Append("  \"student_actions_attempted\": ").Append(_studentActionsAttempted).AppendLine(",");
                sb.Append("  \"accepted_bot_commands\": ").Append(_acceptedBotCommands).AppendLine(",");
                sb.Append("  \"rejected_bot_commands\": ").Append(_rejectedBotCommands).AppendLine(",");
                sb.Append("  \"terminal_reason\": \"").Append(EscapeJson(_terminalReason)).AppendLine("\",");
                sb.Append("  \"duplicate_spawn_detected\": ").Append(_duplicateSpawnDetected ? "true" : "false").AppendLine(",");
                sb.AppendLine("  \"stage6b3_files_touched\": []");
                sb.AppendLine("}");

                File.WriteAllText(fullPath, sb.ToString(), Encoding.UTF8);
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[Stage7B] Failed to write scripted bot throttle report: {ex.Message}");
            }
        }

        private string ResolveReportPath()
        {
            string relative = string.IsNullOrWhiteSpace(_reportRelativePath)
                ? "python/stage7b_teacher_replay/stage7b_week7_scripted_bot_throttle_report.json"
                : _reportRelativePath.Replace('\\', '/');

            if (Path.IsPathRooted(relative))
            {
                return relative;
            }

            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            return Path.Combine(projectRoot, relative.Replace('/', Path.DirectorySeparatorChar));
        }

        private static string EscapeJson(string value)
        {
            return value
                .Replace("\\", "\\\\")
                .Replace("\"", "\\\"")
                .Replace("\r", "\\r")
                .Replace("\n", "\\n")
                .Replace("\t", "\\t");
        }
    }
}