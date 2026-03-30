using RTS.Core;
using RTS.Gameplay;

namespace RTS.ML
{
    public readonly struct TerminalEvaluationResult
    {
        public TerminalEvaluationResult(
            bool isTerminal,
            TerminalReason terminalReason,
            Owner winner,
            MatchEndReason runtimeEndReason,
            bool runtimeWasTerminal,
            string diagnosticDescription)
        {
            IsTerminal = isTerminal;
            TerminalReason = terminalReason;
            Winner = winner;
            RuntimeEndReason = runtimeEndReason;
            RuntimeWasTerminal = runtimeWasTerminal;
            DiagnosticDescription = diagnosticDescription ?? string.Empty;
        }

        public bool IsTerminal { get; }
        public TerminalReason TerminalReason { get; }
        public Owner Winner { get; }
        public MatchEndReason RuntimeEndReason { get; }
        public bool RuntimeWasTerminal { get; }
        public string DiagnosticDescription { get; }
    }

    public readonly struct EpisodeEndReport
    {
        public EpisodeEndReport(
            bool isTerminal,
            TerminalReason terminalReason,
            Owner winner,
            MatchEndReason runtimeEndReason,
            bool runtimeWasTerminal,
            bool terminalEventProcessed,
            bool terminalRewardNonZero,
            int episodeStep,
            RewardBreakdown rewardBreakdown,
            string diagnosticDescription)
        {
            IsTerminal = isTerminal;
            TerminalReason = terminalReason;
            Winner = winner;
            RuntimeEndReason = runtimeEndReason;
            RuntimeWasTerminal = runtimeWasTerminal;
            // TerminalEventProcessed: evaluator recognised a terminal case and ran the terminal path,
            // regardless of whether the resulting reward magnitude is zero.
            // Example: Draw/Timeout with default 0.0 config → TerminalEventProcessed=true, TerminalRewardNonZero=false.
            TerminalEventProcessed = terminalEventProcessed;
            // TerminalRewardNonZero: at least one non-zero value was accumulated in the terminal reward bucket.
            TerminalRewardNonZero = terminalRewardNonZero;
            EpisodeStep = episodeStep;
            RewardBreakdown = rewardBreakdown;
            DiagnosticDescription = diagnosticDescription ?? string.Empty;
        }

        public bool IsTerminal { get; }
        public TerminalReason TerminalReason { get; }
        public Owner Winner { get; }
        public MatchEndReason RuntimeEndReason { get; }
        public bool RuntimeWasTerminal { get; }
        /// <summary>True when the evaluator recognised a terminal case and ran through the terminal path,
        /// even if the resulting reward magnitude is zero (e.g. Draw or Timeout with default 0.0 values).</summary>
        public bool TerminalEventProcessed { get; }
        /// <summary>True only when the terminal reward bucket contains a non-zero accumulated value.</summary>
        public bool TerminalRewardNonZero { get; }
        public int EpisodeStep { get; }
        public RewardBreakdown RewardBreakdown { get; }
        public string DiagnosticDescription { get; }
    }

    public static class EpisodeTerminalEvaluator
    {
        public static TerminalEvaluationResult Evaluate(MatchStateSnapshot snapshot, Owner perspective)
        {
            bool runtimeTerminal = snapshot.Phase == MatchPhase.Ended;
            if (!runtimeTerminal)
            {
                return new TerminalEvaluationResult(
                    false,
                    TerminalReason.None,
                    snapshot.Winner,
                    snapshot.EndReason,
                    false,
                    "Runtime phase is not Ended.");
            }

            if (snapshot.EndReason == MatchEndReason.None)
            {
                // [AnomalousEndedState]: runtime transitioned to Ended but did not supply a MatchEndReason.
                // This should not occur in the normal match lifecycle. Treat as InvalidRuntimeState to
                // prevent reward hacking through an undefined terminal boundary.
                return new TerminalEvaluationResult(
                    true,
                    TerminalReason.InvalidRuntimeState,
                    snapshot.Winner,
                    snapshot.EndReason,
                    true,
                    "[AnomalousEndedState] Runtime phase is Ended but MatchEndReason is None.");
            }

            if (snapshot.Winner == perspective)
            {
                return new TerminalEvaluationResult(
                    true,
                    TerminalReason.Win,
                    snapshot.Winner,
                    snapshot.EndReason,
                    true,
                    "Runtime terminal outcome: win.");
            }

            if (snapshot.Winner == Owner.Neutral)
            {
                bool isTimeout = snapshot.EndReason == MatchEndReason.StepLimitReached;
                return new TerminalEvaluationResult(
                    true,
                    isTimeout ? TerminalReason.Timeout : TerminalReason.Draw,
                    snapshot.Winner,
                    snapshot.EndReason,
                    true,
                    isTimeout
                        ? "Runtime terminal outcome: timeout."
                        : "Runtime terminal outcome: draw.");
            }

            return new TerminalEvaluationResult(
                true,
                TerminalReason.Loss,
                snapshot.Winner,
                snapshot.EndReason,
                true,
                "Runtime terminal outcome: loss.");
        }

        /// <summary>
        /// Creates a terminal result for a forced episode end that did not originate from the runtime match lifecycle.
        /// This is the [GuardedReset] subtype of InvalidRuntimeState: the episode was closed by EpisodeController
        /// before MatchManager reached its own terminal state (e.g. manual ResetEpisode() during a live match).
        /// RuntimeWasTerminal is false to distinguish this from an authentic runtime terminal transition.
        /// </summary>
        public static TerminalEvaluationResult CreateGuardedStop(string reason)
        {
            return new TerminalEvaluationResult(
                true,
                TerminalReason.InvalidRuntimeState,
                Owner.Neutral,
                MatchEndReason.None,
                false,
                $"[GuardedReset] {reason ?? "Episode terminated by guarded stop."}");
        }
    }
}