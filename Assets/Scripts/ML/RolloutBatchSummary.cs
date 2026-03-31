// RolloutBatchSummary.cs — Day 6 batch-level summary and sanity-check warnings.
//
// Aggregates episode summaries from a baseline rollout batch and computes statistical
// summaries, outcome distributions, and warning flags for anomaly detection.

using System;
using System.Collections.Generic;
using RTS.Core;

namespace RTS.ML
{
    /// <summary>
    /// Batch-level summary and diagnostics for a set of baseline rollout episodes.
    /// Produced by <see cref="BaselineRolloutRunner.StartBatchRollout"/>.
    ///
    /// Used to detect rudimentary sanity issues:
    /// - Reward explosion / starvation
    /// - Shaping dominance
    /// - Invalid action spikes
    /// - Terminal event processing anomalies
    /// - Outcome imbalance (possible stuck state)
    /// </summary>
    public class RolloutBatchSummary
    {
        public int EpisodeCount { get; set; }
        public List<RolloutEpisodeSummary> Episodes { get; set; } = new();

        // ─── Reward aggregates ───────────────────────────────────────────────
        public float AvgTotalReward { get; set; }
        public float StdTotalReward { get; set; }
        public float MinTotalReward { get; set; }
        public float MaxTotalReward { get; set; }

        public float AvgEconomyReward { get; set; }
        public float AvgCombatReward { get; set; }
        public float AvgTerminalReward { get; set; }
        public float AvgShapingReward { get; set; }

        // ─── Step and event statistics ───────────────────────────────────────
        public float AvgStepCount { get; set; }
        public int MinStepCount { get; set; }
        public int MaxStepCount { get; set; }
        public float AvgRewardEventCount { get; set; }

        // ─── Terminal processing ────────────────────────────────────────────
        public int TerminalEventProcessedCount { get; set; }
        public float TerminalEventProcessedRate { get; set; }  // Fraction of episodes with terminal event processed

        public int TerminalRewardNonZeroCount { get; set; }
        public float TerminalRewardNonZeroRate { get; set; }   // Fraction of terminal events with non-zero reward

        // Terminal reason distribution
        public Dictionary<TerminalReason, int> TerminalReasonCounts { get; set; } = new();

        // Outcome label distribution (Win, Loss, Draw, Timeout, etc.)
        public Dictionary<string, int> OutcomeCounts { get; set; } = new();

        // ─── Invalid action statistics ───────────────────────────────────────
        /// <summary>Episodes where invalid-action rate is measured and trustworthy.</summary>
        public int EpisodesWithMeasuredInvalidRate { get; set; }
        /// <summary>Episodes where invalid-action rate is unavailable (counts unavailable in step reports).</summary>
        public int EpisodesWithUnavailableInvalidRate { get; set; }
        /// <summary>Total steps contributing to measured invalid-action rates.</summary>
        public int TotalInvalidMeasuredSteps { get; set; }
        /// <summary>Total steps where invalid-action counts were unavailable.</summary>
        public int TotalInvalidUnavailableSteps { get; set; }
        /// <summary>Average invalid-action rate across measured episodes only.</summary>
        public float AvgInvalidActionRateMeasured { get; set; }
        /// <summary>Maximum invalid-action rate across measured episodes only.</summary>
        public float MaxInvalidActionRateMeasured { get; set; }
        /// <summary>Measured episodes with invalid-action rate above the threshold.</summary>
        public int EpisodesWithHighInvalidRateMeasured { get; set; }

        // ─── Shaping reward ratio ────────────────────────────────────────────
        /// <summary>
        /// Average fraction of total reward sum that comes from shaping.
        /// High values (>0.5) indicate shaping may dominate learning signal.
        /// </summary>
        public float AvgShapingFractionOfTotal { get; set; }

        // ─── Sanity warnings ────────────────────────────────────────────────
        /// <summary>
        /// List of detected anomalies and warnings for manual review.
        /// Examples:
        /// - "High reward mean (12.5): possible explosion"
        /// - "Shaping dominates (73% of mean reward)"
        /// - "Invalid action rate spike (22% avg)"
        /// - "80% episodes are Draws: possible stuck state"
        /// </summary>
        public List<string> SanityWarnings { get; set; } = new();

        /// <summary>
        /// Build a simple markdown-formatted report of the batch summary.
        /// Useful for documentation and manual review.
        /// </summary>
        public string ToMarkdown()
        {
            var sb = new System.Text.StringBuilder();
            sb.AppendLine("# Baseline Rollout Batch Summary");
            sb.AppendLine();
            sb.AppendLine($"**Episodes:** {EpisodeCount}");
            sb.AppendLine();

            sb.AppendLine("## Reward Statistics");
            sb.AppendLine($"- **Total Reward:** {AvgTotalReward:F2} ± {StdTotalReward:F2} (min={MinTotalReward:F2}, max={MaxTotalReward:F2})");
            sb.AppendLine($"- **Economy:** {AvgEconomyReward:F2}");
            sb.AppendLine($"- **Combat:** {AvgCombatReward:F2}");
            sb.AppendLine($"- **Terminal:** {AvgTerminalReward:F2}");
            sb.AppendLine($"- **Shaping:** {AvgShapingReward:F2}");
            sb.AppendLine($"- **Shaping Fraction Of Total:** {AvgShapingFractionOfTotal:P1}");
            sb.AppendLine();

            sb.AppendLine("## Episode Statistics");
            sb.AppendLine($"- **Avg Steps:** {AvgStepCount:F1} (min={MinStepCount}, max={MaxStepCount})");
            sb.AppendLine($"- **Avg Reward Events:** {AvgRewardEventCount:F1}");
            sb.AppendLine();

            sb.AppendLine("## Terminal Behavior");
            sb.AppendLine($"- **Terminal Events Processed:** {TerminalEventProcessedCount}/{EpisodeCount} ({TerminalEventProcessedRate:P1})");
            sb.AppendLine($"- **Terminal Reward Non-Zero:** {TerminalRewardNonZeroCount}/{TerminalEventProcessedCount} ({TerminalRewardNonZeroRate:P1})");
            sb.AppendLine();

            sb.AppendLine("### Terminal Reasons");
            foreach (var kvp in TerminalReasonCounts)
            {
                sb.AppendLine($"- {kvp.Key}: {kvp.Value}");
            }
            sb.AppendLine();

            sb.AppendLine("### Outcomes");
            foreach (var kvp in OutcomeCounts)
            {
                float pct = (float)kvp.Value / EpisodeCount * 100f;
                sb.AppendLine($"- {kvp.Key}: {kvp.Value} ({pct:F1}%)");
            }
            sb.AppendLine();

            sb.AppendLine("## Invalid Actions");
            sb.AppendLine($"- **Episodes With Measured Rate:** {EpisodesWithMeasuredInvalidRate}/{EpisodeCount}");
            sb.AppendLine($"- **Episodes With Unavailable Rate:** {EpisodesWithUnavailableInvalidRate}/{EpisodeCount}");
            sb.AppendLine($"- **Avg Invalid Rate (Measured Only):** {AvgInvalidActionRateMeasured:P1}");
            sb.AppendLine($"- **Max Invalid Rate (Measured Only):** {MaxInvalidActionRateMeasured:P1}");
            sb.AppendLine($"- **Episodes with High Rate (>15%, Measured Only):** {EpisodesWithHighInvalidRateMeasured}");
            sb.AppendLine();

            if (SanityWarnings.Count > 0)
            {
                sb.AppendLine("## ⚠️ Sanity Warnings");
                foreach (var warning in SanityWarnings)
                {
                    sb.AppendLine($"- {warning}");
                }
            }
            else
            {
                sb.AppendLine("## ✅ No Sanity Warnings");
            }

            return sb.ToString();
        }

        /// <summary>
        /// Build a compact single-line summary for quick console output.
        /// </summary>
        public string ToOneLine()
        {
            return $"Batch({EpisodeCount}): avg_reward={AvgTotalReward:F1}±{StdTotalReward:F1}, " +
                   $"avg_steps={AvgStepCount:F0}, invalid_measured={EpisodesWithMeasuredInvalidRate}/{EpisodeCount}, " +
                   $"outcomes={string.Join("|", OutcomeCounts.Keys)}, " +
                   $"warnings={SanityWarnings.Count}";
        }
    }
}
