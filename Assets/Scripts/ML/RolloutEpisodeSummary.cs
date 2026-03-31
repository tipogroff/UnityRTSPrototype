// RolloutEpisodeSummary.cs — Day 6 episode-level diagnostics for baseline rollout analysis.
//
// Captures per-episode metrics for sanity-checking reward distribution and terminal behavior
// across a batch of baseline/heuristic rollouts. Non-ML specific; used for diagnostics only.

using RTS.Core;
using RTS.Gameplay;

namespace RTS.ML
{
    /// <summary>
    /// Episode-level summary for a single baseline rollout.
    /// Constructed after episode termination and fed into <see cref="RolloutBatchSummary"/>.
    /// </summary>
    public struct RolloutEpisodeSummary
    {
        public int EpisodeIndex;
        public int StepCount;

        // ─── Reward breakdown ────────────────────────────────────────────────
        public float TotalReward;
        public float EconomyReward;
        public float CombatReward;
        public float TerminalReward;
        public float ShapingReward;

        // Number of individual reward events that fired in this episode
        public int RewardEventCount;

        // ─── Terminal state ──────────────────────────────────────────────────
        public bool IsTerminal;
        public TerminalReason TerminalReason;
        public Owner Winner;
        /// <summary>True when the terminal evaluator recognized a terminal case and ran the terminal path.</summary>
        public bool TerminalEventProcessed;
        /// <summary>True when terminal reward bucket contains at least one non-zero value.</summary>
        public bool TerminalRewardNonZero;
        public MatchEndReason RuntimeEndReason;

        // ─── Runtime diagnostics ────────────────────────────────────────────
        public int InvalidActionCount;
        /// <summary>
        /// True when invalid-action counts were available for at least one step.
        /// False means rate/count are unavailable on this decision-source path.
        /// </summary>
        public bool InvalidActionRateMeasured;
        /// <summary>Number of steps where ActionCountsAvailable=true.</summary>
        public int InvalidActionMeasuredStepCount;
        /// <summary>Number of steps where ActionCountsAvailable=false.</summary>
        public int InvalidActionUnavailableStepCount;
        /// <summary>
        /// InvalidActionCount / InvalidActionMeasuredStepCount when measured,
        /// otherwise 0.0 (must be interpreted with InvalidActionRateMeasured).
        /// </summary>
        public float InvalidActionRate;

        // ─── User-friendly outcome label ────────────────────────────────────
        /// <summary>
        /// Derived outcome for easy interpretation: "Win", "Loss", "Draw", "Timeout", "InvalidRuntimeState", etc.
        /// </summary>
        public string OutcomeLabel;

        /// <summary>
        /// Human-readable summary line for console/log output.
        /// Example: "Episode 5: reward=12.3, steps=150, outcome=Win, terminal_reason=PlayerVictory"
        /// </summary>
        public string GetSummaryLine()
        {
            string invalidRateText = InvalidActionRateMeasured
                ? $"{InvalidActionRate:P1}"
                : "N/A";
            return $"Episode {EpisodeIndex}: reward={TotalReward:F2}, steps={StepCount}, outcome={OutcomeLabel}, " +
                   $"terminal_reason={TerminalReason}, invalid_rate={invalidRateText}";
        }

        /// <summary>
        /// Returns diagnostics as a compact single line suitable for batch logging.
        /// Useful for quick visual scan of all episodes in a batch.
        /// </summary>
        public string GetCompactLine()
        {
            string invalidText = InvalidActionRateMeasured
                ? $"{InvalidActionRate:P0}"
                : "N/A";
            return $"#{EpisodeIndex:D2} | r={TotalReward:F1} | steps={StepCount:D3} | outcome={OutcomeLabel,-8} | invalid={invalidText}";
        }
    }
}
