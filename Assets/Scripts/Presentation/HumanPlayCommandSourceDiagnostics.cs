using System;
using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using RTS.ML;
using UnityEngine;

namespace RTS.Presentation
{
    public readonly struct HumanPlayCommandDiagnosticsSnapshot
    {
        public HumanPlayCommandDiagnosticsSnapshot(
            HumanPlayMode currentMode,
            Owner humanSide,
            bool hasHumanSide,
            bool humanControlActive,
            bool enableStudentMatchControl,
            Week6PlayerControlMode player1DecisionMode,
            Week6PlayerControlMode player2DecisionMode,
            int player2AutomaticCommandCount,
            int player2HumanCommandCount,
            string lastPlayer2CommandSource)
        {
            CurrentMode = currentMode;
            HumanSide = humanSide;
            HasHumanSide = hasHumanSide;
            HumanControlActive = humanControlActive;
            EnableStudentMatchControl = enableStudentMatchControl;
            Player1DecisionMode = player1DecisionMode;
            Player2DecisionMode = player2DecisionMode;
            Player2AutomaticCommandCount = player2AutomaticCommandCount;
            Player2HumanCommandCount = player2HumanCommandCount;
            LastPlayer2CommandSource = lastPlayer2CommandSource ?? "n/a";
        }

        public HumanPlayMode CurrentMode { get; }
        public Owner HumanSide { get; }
        public bool HasHumanSide { get; }
        public bool HumanControlActive { get; }
        public bool EnableStudentMatchControl { get; }
        public Week6PlayerControlMode Player1DecisionMode { get; }
        public Week6PlayerControlMode Player2DecisionMode { get; }
        public int Player2AutomaticCommandCount { get; }
        public int Player2HumanCommandCount { get; }
        public string LastPlayer2CommandSource { get; }
    }

    public static class HumanPlayCommandSourceDiagnostics
    {
        private const float RetentionWindowSeconds = 30f;
        private static readonly List<CommandRecord> Records = new List<CommandRecord>(128);
        private static readonly Stack<string> SourceStack = new Stack<string>(8);

        private readonly struct CommandRecord
        {
            public CommandRecord(
                float timestamp,
                int frame,
                MatchCommand command,
                bool accepted,
                string source,
                HumanPlayMode currentMode,
                Owner humanSide,
                bool hasHumanSide,
                bool humanControlActive,
                bool enableStudentMatchControl,
                Week6PlayerControlMode player1DecisionMode,
                Week6PlayerControlMode player2DecisionMode,
                string rejectionReason)
            {
                Timestamp = timestamp;
                Frame = frame;
                Command = command;
                Accepted = accepted;
                Source = source ?? "Unknown";
                CurrentMode = currentMode;
                HumanSide = humanSide;
                HasHumanSide = hasHumanSide;
                HumanControlActive = humanControlActive;
                EnableStudentMatchControl = enableStudentMatchControl;
                Player1DecisionMode = player1DecisionMode;
                Player2DecisionMode = player2DecisionMode;
                RejectionReason = rejectionReason ?? string.Empty;
            }

            public float Timestamp { get; }
            public int Frame { get; }
            public MatchCommand Command { get; }
            public bool Accepted { get; }
            public string Source { get; }
            public HumanPlayMode CurrentMode { get; }
            public Owner HumanSide { get; }
            public bool HasHumanSide { get; }
            public bool HumanControlActive { get; }
            public bool EnableStudentMatchControl { get; }
            public Week6PlayerControlMode Player1DecisionMode { get; }
            public Week6PlayerControlMode Player2DecisionMode { get; }
            public string RejectionReason { get; }
        }

        private sealed class Scope : IDisposable
        {
            private bool _disposed;

            public void Dispose()
            {
                if (_disposed)
                {
                    return;
                }

                _disposed = true;
                if (SourceStack.Count > 0)
                {
                    SourceStack.Pop();
                }
            }
        }

        public static string CurrentSource => SourceStack.Count > 0 ? SourceStack.Peek() : "Unknown";

        public static IDisposable PushSource(string source)
        {
            SourceStack.Push(string.IsNullOrWhiteSpace(source) ? "Unknown" : source);
            return new Scope();
        }

        public static IDisposable PushSourceIfUnset(string source)
        {
            return SourceStack.Count == 0 ? PushSource(source) : new Scope();
        }

        public static void ResetHistory()
        {
            Records.Clear();
        }

        public static void RecordCommand(MatchCommand command, bool accepted, string rejectionReason)
        {
            ResolveContext(
                out HumanPlayMode currentMode,
                out Owner humanSide,
                out bool hasHumanSide,
                out bool humanControlActive,
                out bool enableStudentMatchControl,
                out Week6PlayerControlMode player1DecisionMode,
                out Week6PlayerControlMode player2DecisionMode);

            string source = CurrentSource;
            float timestamp = Time.unscaledTime;
            if (timestamp <= 0f)
            {
                timestamp = Time.realtimeSinceStartup;
            }

            Prune(timestamp);

            var record = new CommandRecord(
                timestamp,
                Time.frameCount,
                command,
                accepted,
                source,
                currentMode,
                humanSide,
                hasHumanSide,
                humanControlActive,
                enableStudentMatchControl,
                player1DecisionMode,
                player2DecisionMode,
                rejectionReason);

            Records.Add(record);

            string outcome = accepted ? "accepted" : "rejected";
            string reasonSuffix = string.IsNullOrWhiteSpace(rejectionReason)
                ? string.Empty
                : $" rejectionReason={rejectionReason}";
            Debug.Log(
                "[HumanPlayCommandSourceDiagnostics] "
                + outcome
                + $" owner={command.Owner} action={command.ActionType} unit={command.UnitPosition}"
                + $" source={source} frame={record.Frame} mode={currentMode} humanSide={humanSide}"
                + $" humanControlActive={humanControlActive} enableStudentMatchControl={enableStudentMatchControl}"
                + $" p1Mode={player1DecisionMode} p2Mode={player2DecisionMode}"
                + reasonSuffix);
        }

        public static HumanPlayCommandDiagnosticsSnapshot GetSnapshot(float windowSeconds)
        {
            ResolveContext(
                out HumanPlayMode currentMode,
                out Owner humanSide,
                out bool hasHumanSide,
                out bool humanControlActive,
                out bool enableStudentMatchControl,
                out Week6PlayerControlMode player1DecisionMode,
                out Week6PlayerControlMode player2DecisionMode);

            float now = Time.unscaledTime;
            if (now <= 0f)
            {
                now = Time.realtimeSinceStartup;
            }

            Prune(now);

            int player2AutomaticCommandCount = 0;
            int player2HumanCommandCount = 0;
            string lastPlayer2CommandSource = "n/a";
            float cutoff = now - Mathf.Max(0.1f, windowSeconds);

            for (int i = Records.Count - 1; i >= 0; i--)
            {
                CommandRecord record = Records[i];
                if (record.Command.Owner != Owner.Player2)
                {
                    continue;
                }

                if (lastPlayer2CommandSource == "n/a")
                {
                    lastPlayer2CommandSource = record.Source;
                }

                if (record.Timestamp < cutoff)
                {
                    continue;
                }

                if (IsHumanSource(record.Source))
                {
                    player2HumanCommandCount++;
                }
                else
                {
                    player2AutomaticCommandCount++;
                }
            }

            return new HumanPlayCommandDiagnosticsSnapshot(
                currentMode,
                humanSide,
                hasHumanSide,
                humanControlActive,
                enableStudentMatchControl,
                player1DecisionMode,
                player2DecisionMode,
                player2AutomaticCommandCount,
                player2HumanCommandCount,
                lastPlayer2CommandSource);
        }

        public static int CountCommands(Owner owner, float windowSeconds, bool humanOnly)
        {
            float now = Time.unscaledTime;
            if (now <= 0f)
            {
                now = Time.realtimeSinceStartup;
            }

            Prune(now);

            float cutoff = now - Mathf.Max(0.1f, windowSeconds);
            int count = 0;
            for (int i = 0; i < Records.Count; i++)
            {
                CommandRecord record = Records[i];
                if (record.Command.Owner != owner || record.Timestamp < cutoff)
                {
                    continue;
                }

                if (humanOnly == IsHumanSource(record.Source))
                {
                    count++;
                }
            }

            return count;
        }

        public static string GetLastCommandSource(Owner owner)
        {
            for (int i = Records.Count - 1; i >= 0; i--)
            {
                if (Records[i].Command.Owner == owner)
                {
                    return Records[i].Source;
                }
            }

            return "n/a";
        }

        public static bool IsHumanSource(string source)
        {
            return !string.IsNullOrWhiteSpace(source)
                && source.IndexOf("PlayerCommandController", StringComparison.OrdinalIgnoreCase) >= 0;
        }

        private static void ResolveContext(
            out HumanPlayMode currentMode,
            out Owner humanSide,
            out bool hasHumanSide,
            out bool humanControlActive,
            out bool enableStudentMatchControl,
            out Week6PlayerControlMode player1DecisionMode,
            out Week6PlayerControlMode player2DecisionMode)
        {
            HumanPlayModeController modeController = UnityEngine.Object.FindFirstObjectByType<HumanPlayModeController>();
            HumanPlayerController playerController = UnityEngine.Object.FindFirstObjectByType<HumanPlayerController>();
            EpisodeController episodeController = EpisodeController.Instance ?? UnityEngine.Object.FindFirstObjectByType<EpisodeController>();

            currentMode = modeController != null ? modeController.CurrentMode : HumanPlayMode.AIvsAI;
            humanSide = modeController != null ? modeController.HumanSide : Owner.Neutral;
            hasHumanSide = modeController != null && modeController.HasHumanSide;
            humanControlActive = playerController != null && playerController.IsHumanControlActive;
            enableStudentMatchControl = episodeController != null && episodeController.EnableWeek6StudentMatchControl;
            player1DecisionMode = episodeController != null ? episodeController.Player1DecisionMode : Week6PlayerControlMode.Idle;
            player2DecisionMode = episodeController != null ? episodeController.Player2DecisionMode : Week6PlayerControlMode.Idle;
        }

        private static void Prune(float now)
        {
            float cutoff = now - RetentionWindowSeconds;
            int removeCount = 0;
            while (removeCount < Records.Count && Records[removeCount].Timestamp < cutoff)
            {
                removeCount++;
            }

            if (removeCount > 0)
            {
                Records.RemoveRange(0, removeCount);
            }
        }
    }
}
