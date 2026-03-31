// Day6RewardSanitySmokeTest.cs — Day 6 baseline rollout sanity-check smoke test.
//
// Runs a small batch of baseline episodes and validates reward distribution,
// terminal behavior, and trace interpretability. Emits markdown report for analysis.
//
// Usage: Attach to a GameObject in the scene with EpisodeController configured,
// then call ExecuteRewardSanityCheck() from Play Mode or via context menu.

using System;
using System.Collections.Generic;
using System.IO;
using UnityEngine;
using RTS.Gameplay;

#if UNITY_EDITOR
using UnityEditor;
#endif

namespace RTS.ML
{
    [DisallowMultipleComponent]
    public class Day6RewardSanitySmokeTest : MonoBehaviour
    {
        [Header("Rollout Config")]
        [SerializeField] private int _episodeCount = 10;
        [SerializeField] private bool _verboseLogging = true;
        [SerializeField] private bool _generateMarkdownReport = true;

        [Header("Sanity Config")]
        [SerializeField] private RewardSanityCheckConfig _sanityConfig = null;

        [Header("Output")]
        [Tooltip("Directory for markdown report. Relative to project root.")]
        [SerializeField] private string _reportDirectory = "WEEK4_Reports";
        [SerializeField] private bool _openReportAfterGeneration = true;

        private BaselineRolloutRunner _runner;
        private RolloutBatchSummary _lastSummary;

#if UNITY_EDITOR
        [ContextMenu("Execute Reward Sanity Check (Play Mode)")]
        public void ContextMenuExecute()
        {
            if (!EditorApplication.isPlaying)
            {
                EditorUtility.DisplayDialog(
                    "Play Mode Required",
                    "Please enter Play Mode before running the sanity check.",
                    "OK");
                return;
            }

            ExecuteRewardSanityCheck();
        }
#endif

        public void ExecuteRewardSanityCheck()
        {
            if (!EpisodeController.Instance)
            {
                Debug.LogError("[Day6RewardSanitySmokeTest] EpisodeController not found in scene.");
                return;
            }

            // Initialize sanity config if not provided
            if (_sanityConfig == null)
            {
                _sanityConfig = new RewardSanityCheckConfig();
            }

            // Create runner
            _runner = new BaselineRolloutRunner(EpisodeController.Instance, _sanityConfig);

            Debug.Log($"[Day6RewardSanitySmokeTest] Starting reward sanity check: {_episodeCount} episodes");

            // Run batch rollout
            _lastSummary = _runner.StartBatchRollout(_episodeCount, _verboseLogging);

            // Emit diagnostics
            EmitDiagnostics(_lastSummary);

            // Generate markdown report
            if (_generateMarkdownReport)
            {
                GenerateMarkdownReport(_lastSummary);
            }

            Debug.Log("[Day6RewardSanitySmokeTest] Reward sanity check completed.");
        }

        private void EmitDiagnostics(RolloutBatchSummary summary)
        {
            Debug.Log("╔══════════════════════════════════════════════════════════╗");
            Debug.Log("║           BASELINE ROLLOUT BATCH SUMMARY                    ║");
            Debug.Log("╚══════════════════════════════════════════════════════════╝");
            Debug.Log("");
            Debug.Log($"Episodes: {summary.EpisodeCount}");
            Debug.Log("");
            Debug.Log("REWARD STATISTICS:");
            Debug.Log($"  Total:    {summary.AvgTotalReward:F2} ± {summary.StdTotalReward:F2} " +
                      $"(min={summary.MinTotalReward:F2}, max={summary.MaxTotalReward:F2})");
            Debug.Log($"  Economy:  {summary.AvgEconomyReward:F2}");
            Debug.Log($"  Combat:   {summary.AvgCombatReward:F2}");
            Debug.Log($"  Terminal: {summary.AvgTerminalReward:F2}");
            Debug.Log($"  Shaping:  {summary.AvgShapingReward:F2} ({summary.AvgShapingFraction:P1} of total)");
            Debug.Log("");
            Debug.Log("EPISODE STATISTICS:");
            Debug.Log($"  Avg Steps:   {summary.AvgStepCount:F1} (min={summary.MinStepCount}, max={summary.MaxStepCount})");
            Debug.Log($"  Avg Events:  {summary.AvgRewardEventCount:F1}");
            Debug.Log("");
            Debug.Log("TERMINAL BEHAVIOR:");
            Debug.Log($"  Events Processed:    {summary.TerminalEventProcessedCount}/{summary.EpisodeCount} ({summary.TerminalEventProcessedRate:P1})");
            Debug.Log($"  Reward Non-Zero:     {summary.TerminalRewardNonZeroCount}/{summary.TerminalEventProcessedCount} ({summary.TerminalRewardNonZeroRate:P1})");
            Debug.Log("");

            if (summary.TerminalReasonCounts.Count > 0)
            {
                Debug.Log("TERMINAL REASONS:");
                foreach (var kvp in summary.TerminalReasonCounts)
                {
                    Debug.Log($"  {kvp.Key}: {kvp.Value}");
                }
                Debug.Log("");
            }

            if (summary.OutcomeCounts.Count > 0)
            {
                Debug.Log("OUTCOMES:");
                foreach (var kvp in summary.OutcomeCounts)
                {
                    float pct = (float)kvp.Value / summary.EpisodeCount * 100f;
                    Debug.Log($"  {kvp.Key}: {kvp.Value} ({pct:F1}%)");
                }
                Debug.Log("");
            }

            Debug.Log("INVALID ACTIONS:");
            Debug.Log($"  Avg Rate:    {summary.AvgInvalidActionRate:P1}");
            Debug.Log($"  Max Rate:    {summary.MaxInvalidActionRate:P1}");
            Debug.Log($"  High Episodes (>15%): {summary.EpisodesWithHighInvalidRate}");
            Debug.Log("");

            if (summary.SanityWarnings.Count > 0)
            {
                Debug.LogWarning("⚠️  SANITY WARNINGS:");
                foreach (var warning in summary.SanityWarnings)
                {
                    Debug.LogWarning($"  • {warning}");
                }
            }
            else
            {
                Debug.Log("✅ NO SANITY WARNINGS DETECTED");
            }

            Debug.Log("════════════════════════════════════════════════════════════");
        }

        private void GenerateMarkdownReport(RolloutBatchSummary summary)
        {
            string projectRoot = Directory.GetParent(Application.dataPath).FullName;
            string reportDir = Path.Combine(projectRoot, _reportDirectory);

            // Create directory if it doesn't exist
            if (!Directory.Exists(reportDir))
            {
                Directory.CreateDirectory(reportDir);
                Debug.Log($"[Day6RewardSanitySmokeTest] Created report directory: {reportDir}");
            }

            // Generate filename with timestamp
            string timestamp = System.DateTime.Now.ToString("yyyy-MM-dd_HH-mm-ss");
            string filename = $"WEEK4_DAY6_REWARD_SANITY_BATCH_{timestamp}.md";
            string filepath = Path.Combine(reportDir, filename);

            // Generate content
            string content = GenerateMarkdownContent(summary);

            // Write to file
            File.WriteAllText(filepath, content);
            Debug.Log($"[Day6RewardSanitySmokeTest] Report written to: {filepath}");

            // Open report if configured
            if (_openReportAfterGeneration)
            {
#if UNITY_EDITOR
                EditorUtility.OpenWithDefaultApp(filepath);
#else
                System.Diagnostics.Process.Start(filepath);
#endif
            }
        }

        private string GenerateMarkdownContent(RolloutBatchSummary summary)
        {
            var sb = new System.Text.StringBuilder();

            // Header
            sb.AppendLine("# Week 4 Day 6: Baseline Reward Sanity-Check Report");
            sb.AppendLine();
            sb.AppendLine($"**Date:** {System.DateTime.Now:yyyy-MM-dd HH:mm:ss}");
            sb.AppendLine($"**Episodes:** {summary.EpisodeCount}");
            sb.AppendLine($"**Mode:** Baseline/Heuristic");
            sb.AppendLine();

            // Summary
            sb.AppendLine("## Executive Summary");
            sb.AppendLine();
            if (summary.SanityWarnings.Count == 0)
            {
                sb.AppendLine("✅ **Reward distribution passed baseline sanity-checks.**");
            }
            else
            {
                sb.AppendLine($"⚠️  **{summary.SanityWarnings.Count} sanity warnings detected.** See details below.");
            }
            sb.AppendLine();

            // Reward statistics
            sb.AppendLine("## Reward Statistics");
            sb.AppendLine();
            sb.AppendLine("| Metric | Value |");
            sb.AppendLine("|--------|-------|");
            sb.AppendLine($"| Total Mean ± Std | {summary.AvgTotalReward:F2} ± {summary.StdTotalReward:F2} |");
            sb.AppendLine($"| Total Range | [{summary.MinTotalReward:F2}, {summary.MaxTotalReward:F2}] |");
            sb.AppendLine($"| Economy | {summary.AvgEconomyReward:F2} |");
            sb.AppendLine($"| Combat | {summary.AvgCombatReward:F2} |");
            sb.AppendLine($"| Terminal | {summary.AvgTerminalReward:F2} |");
            sb.AppendLine($"| Shaping | {summary.AvgShapingReward:F2} ({summary.AvgShapingFraction:P1}) |");
            sb.AppendLine();

            // Episode statistics
            sb.AppendLine("## Episode Statistics");
            sb.AppendLine();
            sb.AppendLine("| Metric | Value |");
            sb.AppendLine("|--------|-------|");
            sb.AppendLine($"| Avg Steps | {summary.AvgStepCount:F1} |");
            sb.AppendLine($"| Step Range | [{summary.MinStepCount}, {summary.MaxStepCount}] |");
            sb.AppendLine($"| Avg Reward Events | {summary.AvgRewardEventCount:F1} |");
            sb.AppendLine();

            // Terminal behavior
            sb.AppendLine("## Terminal Behavior");
            sb.AppendLine();
            sb.AppendLine("| Metric | Value |");
            sb.AppendLine("|--------|-------|");
            sb.AppendLine($"| Terminal Events Processed | {summary.TerminalEventProcessedCount}/{summary.EpisodeCount} ({summary.TerminalEventProcessedRate:P1}) |");
            sb.AppendLine($"| Terminal Reward Non-Zero | {summary.TerminalRewardNonZeroCount}/{summary.TerminalEventProcessedCount} ({summary.TerminalRewardNonZeroRate:P1}) |");
            sb.AppendLine();

            // Terminal reason distribution
            if (summary.TerminalReasonCounts.Count > 0)
            {
                sb.AppendLine("### Terminal Reasons");
                sb.AppendLine();
                sb.AppendLine("| Reason | Count |");
                sb.AppendLine("|--------|-------|");
                foreach (var kvp in summary.TerminalReasonCounts)
                {
                    sb.AppendLine($"| {kvp.Key} | {kvp.Value} |");
                }
                sb.AppendLine();
            }

            // Outcome distribution
            if (summary.OutcomeCounts.Count > 0)
            {
                sb.AppendLine("### Outcome Distribution");
                sb.AppendLine();
                sb.AppendLine("| Outcome | Count | Percentage |");
                sb.AppendLine("|---------|-------|------------|");
                foreach (var kvp in summary.OutcomeCounts)
                {
                    float pct = (float)kvp.Value / summary.EpisodeCount * 100f;
                    sb.AppendLine($"| {kvp.Key} | {kvp.Value} | {pct:F1}% |");
                }
                sb.AppendLine();
            }

            // Invalid actions
            sb.AppendLine("## Invalid Actions");
            sb.AppendLine();
            sb.AppendLine("| Metric | Value |");
            sb.AppendLine("|--------|-------|");
            sb.AppendLine($"| Avg Invalid Rate | {summary.AvgInvalidActionRate:P1} |");
            sb.AppendLine($"| Max Invalid Rate | {summary.MaxInvalidActionRate:P1} |");
            sb.AppendLine($"| Episodes with High Rate (>15%) | {summary.EpisodesWithHighInvalidRate} |");
            sb.AppendLine();

            // Sanity warnings
            sb.AppendLine("## Sanity Check Results");
            sb.AppendLine();
            if (summary.SanityWarnings.Count == 0)
            {
                sb.AppendLine("✅ **No warnings detected.**");
            }
            else
            {
                sb.AppendLine($"⚠️  **{summary.SanityWarnings.Count} warnings:**");
                sb.AppendLine();
                foreach (var warning in summary.SanityWarnings)
                {
                    sb.AppendLine($"- {warning}");
                }
            }
            sb.AppendLine();

            // Per-episode detail table
            sb.AppendLine("## Per-Episode Detail");
            sb.AppendLine();
            sb.AppendLine("| # | Reward | Steps | Economy | Combat | Terminal | Shaping | Outcome | Invalid % | Terminal? |");
            sb.AppendLine("|---|--------|-------|---------|--------|----------|---------|---------|-----------|-----------|");
            foreach (var ep in summary.Episodes)
            {
                sb.AppendLine($"| {ep.EpisodeIndex:D2} | {ep.TotalReward:F2} | {ep.StepCount:D3} | {ep.EconomyReward:F2} | {ep.CombatReward:F2} | {ep.TerminalReward:F2} | {ep.ShapingReward:F2} | {ep.OutcomeLabel,-8} | {ep.InvalidActionRate:P0} | {(ep.IsTerminal ? "✓" : "✗")} |");
            }
            sb.AppendLine();

            // Interpretation and notes
            sb.AppendLine("## Interpretation");
            sb.AppendLine();
            sb.AppendLine("### What This Report Includes");
            sb.AppendLine("- Episode-level metrics: total reward, reward category breakdown, steps, invalid action rate, terminal reason");
            sb.AppendLine("- Batch aggregates: means, standard deviations, ranges, distributions");
            sb.AppendLine("- Sanity checks: flagged anomalies detected across reward magnitude, shaping dominance, invalid actions, terminal events, and outcome imbalance");
            sb.AppendLine();

            sb.AppendLine("### What This Report Does NOT Include");
            sb.AppendLine("- Mathematical proofs of reward quality or learnability");
            sb.AppendLine("- Policy optimization analysis");
            sb.AppendLine("- Full transfer compatibility validation with Gym-μRTS");
            sb.AppendLine("- Performance timing or computational efficiency analysis");
            sb.AppendLine();

            sb.AppendLine("### Interpretation Guidelines");
            sb.AppendLine("- **Reward Magnitude:** Look for patterns in mean reward and individual episode traces. Stable, non-explosive ranges suggest no immediate reward hacking.");
            sb.AppendLine("- **Shaping vs Terminal:** If shaping dominates, the learning signal may reward intermediate spurious behavior. Typically acceptable up to 50% of total.");
            sb.AppendLine("- **Terminal Events:** High processed rate and non-zero reward indicate terminal pipeline is functioning. Low rates or zero rewards suggest terminal config may need review.");
            sb.AppendLine("- **Invalid Actions:** High rates (>15%) indicate masking or action decoder issues. Very high rates (>30%) suggest fundamental design problems.");
            sb.AppendLine("- **Outcome Distribution:** Imbalance (>80% one outcome) may indicate stuck state or deterministic heuristic behavior.");
            sb.AppendLine();

            sb.AppendLine("### Next Steps if Warnings Detected");
            sb.AppendLine("1. Review specific episode traces where anomalies occurred");
            sb.AppendLine("2. Check reward breakdown composition (economy vs combat vs terminal)");
            sb.AppendLine("3. Validate action mask and decoder correctness");
            sb.AppendLine("4. Examine terminal condition logic and reward assignment");
            sb.AppendLine("5. Consider tuning reward coefficients or thresholds (only after investigation)");
            sb.AppendLine();

            sb.AppendLine("---");
            sb.AppendLine($"Generated by Day6RewardSanitySmokeTest at {System.DateTime.Now:yyyy-MM-dd HH:mm:ss}");

            return sb.ToString();
        }
    }
}
