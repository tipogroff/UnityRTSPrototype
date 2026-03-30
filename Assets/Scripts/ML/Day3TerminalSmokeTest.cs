// Day3TerminalSmokeTest.cs — Smoke/integration test for the Week 4 Day 3 terminal pipeline.
//
// Covers 5 canonical episode-end scenarios:
//   S1 Win          — DeclareWinner(Player1) → TerminalReason.Win
//   S2 Loss         — DeclareWinner(Player2) → TerminalReason.Loss
//   S3 Draw         — DeclareWinner(Neutral, Elimination) → TerminalReason.Draw
//   S4 Timeout      — DeclareWinner(Neutral, StepLimitReached) → TerminalReason.Timeout
//   S5 GuardedReset — ResetEpisode() while Running → TerminalReason.InvalidRuntimeState [GuardedReset]
//
// Each scenario asserts the resulting EpisodeEndReport (EpisodeController.LastTerminalReport) against
// a runtime snapshot to verify that the evaluator and controller agree on the terminal classification.
//
// Usage:
//   - Enter Play Mode with the RTS scene loaded.
//   - Open SmokeTest/11 – Day3 Terminal Pipeline Smoke Test  (or RTS/Smoke/Day3)
//   - Inspect the Console for ✅/❌ per scenario and a final summary.
//
// Notes:
//   - All scenarios run synchronously (single frame). FixedUpdate cannot interleave.
//   - S5 uses Application.logMessageReceived to capture LastTerminalReport before
//     StartNewEpisode() resets it (both called within the same ResetEpisode() stack frame).

using System;
using UnityEngine;
using RTS.Core;
using RTS.Gameplay;

namespace RTS.ML
{
    /// <summary>
    /// Day 3 Week 4 smoke runner: terminal pipeline — 5 scenarios, auto-verifies LastTerminalReport.
    /// </summary>
    public class Day3TerminalSmokeTest : MonoBehaviour
    {
        [SerializeField] private bool _runOnAwake = true;

        private int _passCount;
        private int _failCount;
        private int _lastRunFrame = -1;

        // S5 (GuardedReset) captures the report inside the log callback because
        // StartNewEpisode() resets LastTerminalReport in the same call stack.
        private EpisodeEndReport _capturedReport;
        private bool _reportCaptured;

        private void Awake()
        {
            if (_runOnAwake)
            {
                RunTests();
            }
        }

        // ──────────────────────────────────────────────────────────────
        // Entry point
        // ──────────────────────────────────────────────────────────────

        private void RunTests()
        {
            if (_lastRunFrame == Time.frameCount)
            {
                Debug.Log("[Day3TerminalSmokeTest] RunTests skipped: already executed in current frame.");
                return;
            }

            _lastRunFrame = Time.frameCount;
            _passCount = 0;
            _failCount = 0;

            Debug.Log("╔════════════════════════════════════════════════════════════╗");
            Debug.Log("║     DAY 3 TERMINAL PIPELINE SMOKE TEST — 5 SCENARIOS      ║");
            Debug.Log("╚════════════════════════════════════════════════════════════╝");

            RunIsolated(TestScenario_Win,          "S1 Win");
            RunIsolated(TestScenario_Loss,         "S2 Loss");
            RunIsolated(TestScenario_Draw,         "S3 Draw");
            RunIsolated(TestScenario_Timeout,      "S4 Timeout");
            RunIsolated(TestScenario_GuardedReset, "S5 GuardedReset");

            int total = _passCount + _failCount;
            Debug.Log("╔════════════════════════════════════════════════════════════╗");
            Debug.Log($"║  RESULT: {_passCount}/{total} passed                                    ║");
            Debug.Log("╚════════════════════════════════════════════════════════════╝");

            if (_failCount == 0)
                Debug.Log("[Day3TerminalSmokeTest] ✅ All terminal pipeline scenarios nominal.");
            else
                Debug.LogWarning($"[Day3TerminalSmokeTest] ⚠️ {_failCount} scenario(s) failed — review ❌ entries above.");
        }

        // ──────────────────────────────────────────────────────────────
        // Scenarios
        // ──────────────────────────────────────────────────────────────

        // S1: Player1 wins by enemy base destruction.
        //     Expects: TerminalReason.Win, Winner=Player1, RuntimeWasTerminal=true.
        private void TestScenario_Win()
        {
            (EpisodeController ec, MatchManager mm) = EnsureRunning();

            mm.DeclareWinner(Owner.Player1, MatchEndReason.EnemyBaseDestroyed, "smoke-win");

            EpisodeEndReport r = ec.LastTerminalReport;
            Require(r.IsTerminal,                                                  "IsTerminal should be true");
            Require(r.TerminalReason == TerminalReason.Win,                        $"Expected Win, got {r.TerminalReason}");
            Require(r.RuntimeWasTerminal,                                          "RuntimeWasTerminal should be true");
            Require(r.TerminalEventProcessed,                                      "TerminalEventProcessed should be true");
            Require(r.Winner == Owner.Player1,                                     $"Winner should be Player1, got {r.Winner}");
            Require(r.RuntimeEndReason == MatchEndReason.EnemyBaseDestroyed,       $"RuntimeEndReason should be EnemyBaseDestroyed, got {r.RuntimeEndReason}");
        }

        // S2: Player2 wins (perspective=Player1 → Loss).
        //     Expects: TerminalReason.Loss, Winner=Player2, RuntimeWasTerminal=true.
        private void TestScenario_Loss()
        {
            (EpisodeController ec, MatchManager mm) = EnsureRunning();

            mm.DeclareWinner(Owner.Player2, MatchEndReason.EnemyBaseDestroyed, "smoke-loss");

            EpisodeEndReport r = ec.LastTerminalReport;
            Require(r.IsTerminal,                                 "IsTerminal should be true");
            Require(r.TerminalReason == TerminalReason.Loss,      $"Expected Loss, got {r.TerminalReason}");
            Require(r.RuntimeWasTerminal,                         "RuntimeWasTerminal should be true");
            Require(r.TerminalEventProcessed,                     "TerminalEventProcessed should be true");
            Require(r.Winner == Owner.Player2,                    $"Winner should be Player2, got {r.Winner}");
        }

        // S3: Neutral winner with a non-step-limit reason → Draw (not Timeout).
        //     Expects: TerminalReason.Draw, Winner=Neutral, RuntimeEndReason!=StepLimitReached.
        private void TestScenario_Draw()
        {
            (EpisodeController ec, MatchManager mm) = EnsureRunning();

            mm.DeclareWinner(Owner.Neutral, MatchEndReason.Elimination, "smoke-draw");

            EpisodeEndReport r = ec.LastTerminalReport;
            Require(r.IsTerminal,                                               "IsTerminal should be true");
            Require(r.TerminalReason == TerminalReason.Draw,                    $"Expected Draw, got {r.TerminalReason}");
            Require(r.RuntimeWasTerminal,                                       "RuntimeWasTerminal should be true");
            Require(r.TerminalEventProcessed,                                   "TerminalEventProcessed should be true");
            Require(r.Winner == Owner.Neutral,                                  $"Winner should be Neutral, got {r.Winner}");
            Require(r.RuntimeEndReason != MatchEndReason.StepLimitReached,      "RuntimeEndReason must not be StepLimitReached for Draw (that path produces Timeout)");
        }

        // S4: Neutral winner with StepLimitReached → Timeout (distinct from Draw).
        //     Expects: TerminalReason.Timeout, RuntimeEndReason=StepLimitReached.
        private void TestScenario_Timeout()
        {
            (EpisodeController ec, MatchManager mm) = EnsureRunning();

            mm.DeclareWinner(Owner.Neutral, MatchEndReason.StepLimitReached, "smoke-timeout");

            EpisodeEndReport r = ec.LastTerminalReport;
            Require(r.IsTerminal,                                                  "IsTerminal should be true");
            Require(r.TerminalReason == TerminalReason.Timeout,                    $"Expected Timeout, got {r.TerminalReason}");
            Require(r.RuntimeWasTerminal,                                          "RuntimeWasTerminal should be true");
            Require(r.TerminalEventProcessed,                                      "TerminalEventProcessed should be true");
            Require(r.Winner == Owner.Neutral,                                     $"Winner should be Neutral, got {r.Winner}");
            Require(r.RuntimeEndReason == MatchEndReason.StepLimitReached,         $"RuntimeEndReason should be StepLimitReached, got {r.RuntimeEndReason}");
        }

        // S5: ResetEpisode() called while the match is still Running (no DeclareWinner first).
        //     EpisodeTerminalEvaluator.CreateGuardedStop fires → [GuardedReset] subtype.
        //     Expects: TerminalReason.InvalidRuntimeState, RuntimeWasTerminal=false,
        //              DiagnosticDescription contains "[GuardedReset]".
        //     Post-condition: a new episode started cleanly (Phase=Running, EpisodeIndex incremented).
        //
        //     Implementation note: StartNewEpisode() clears LastTerminalReport in the same
        //     ResetEpisode() call stack as FinalizeEpisodeWithTerminalReport(). We intercept the
        //     value via Application.logMessageReceived, which fires synchronously inside
        //     FinalizeEpisodeWithTerminalReport after LastTerminalReport is assigned.
        private void TestScenario_GuardedReset()
        {
            (EpisodeController ec, MatchManager mm) = EnsureRunning();

            _reportCaptured = false;
            _capturedReport = default;

            Application.logMessageReceived += OnTerminalLog;
            int episodeBefore = ec.EpisodeIndex;

            ec.ResetEpisode(); // triggers guarded stop path while match is Running

            Application.logMessageReceived -= OnTerminalLog;

            Require(_reportCaptured,
                "Terminal report was not captured — FinalizeEpisodeWithTerminalReport may not have fired or _logTerminalDiagnostics is disabled");

            EpisodeEndReport r = _capturedReport;
            Require(r.IsTerminal,                                                          "IsTerminal should be true");
            Require(r.TerminalReason == TerminalReason.InvalidRuntimeState,                $"Expected InvalidRuntimeState, got {r.TerminalReason}");
            Require(!r.RuntimeWasTerminal,                                                 "RuntimeWasTerminal should be false (match was Running, not Ended)");
            Require(r.TerminalEventProcessed,                                              "TerminalEventProcessed should be true");
            Require(r.DiagnosticDescription.Contains("[GuardedReset]"),                    $"DiagnosticDescription should contain [GuardedReset], got: \"{r.DiagnosticDescription}\"");
            Require(r.RuntimeEndReason == MatchEndReason.None,                             $"RuntimeEndReason should be None for GuardedReset, got {r.RuntimeEndReason}");

            // Post-condition: new episode must have started cleanly.
            Require(ec.EpisodeIndex == episodeBefore + 1,   $"EpisodeIndex should be {episodeBefore + 1}, got {ec.EpisodeIndex}");
            Require(mm.Phase == MatchPhase.Running,          $"Phase should be Running after guarded reset, got {mm.Phase}");
        }

        // ──────────────────────────────────────────────────────────────
        // Helpers
        // ──────────────────────────────────────────────────────────────

        /// <summary>
        /// Ensures a Running episode exists. If the match is not Running, calls ResetEpisode()
        /// to establish a fresh episode. Throws SmokeAssertException if Running cannot be achieved.
        /// </summary>
        private (EpisodeController ec, MatchManager mm) EnsureRunning()
        {
            EpisodeController ec = EpisodeController.Instance;
            MatchManager mm      = MatchManager.Instance;

            if (ec == null)
                throw new SmokeAssertException("EpisodeController.Instance is null — enter Play Mode with the RTS scene loaded.");
            if (mm == null)
                throw new SmokeAssertException("MatchManager.Instance is null — enter Play Mode with the RTS scene loaded.");

            if (mm.Phase != MatchPhase.Running)
                ec.ResetEpisode();

            if (mm.Phase != MatchPhase.Running)
                throw new SmokeAssertException($"Could not establish a Running match phase (current: {mm.Phase}). Check MatchBootstrap setup.");

            return (ec, mm);
        }

        /// <summary>
        /// Fired synchronously by Debug.Log inside FinalizeEpisodeWithTerminalReport,
        /// after LastTerminalReport is written but before StartNewEpisode() resets it.
        /// Used exclusively by TestScenario_GuardedReset.
        /// </summary>
        private void OnTerminalLog(string message, string stackTrace, LogType type)
        {
            if (_reportCaptured)
                return;

            // The target log entry is emitted from the _logTerminalDiagnostics branch.
            // The [Mismatch] variant is a separate warning emitted before it — skip that one.
            if (message.Contains("[EpisodeController][Terminal]") && !message.Contains("[Mismatch]"))
            {
                EpisodeController ec = EpisodeController.Instance;
                if (ec != null)
                {
                    _capturedReport  = ec.LastTerminalReport;
                    _reportCaptured  = true;
                }
            }
        }

        private void RunIsolated(Action test, string label)
        {
            try
            {
                test();
                _passCount++;
                Debug.Log($"  ✅ [PASS] {label}");
            }
            catch (SmokeAssertException ex)
            {
                _failCount++;
                Debug.LogError($"  ❌ [FAIL] {label}: {ex.Message}");
            }
            catch (Exception ex)
            {
                _failCount++;
                Debug.LogError($"  ❌ [FAIL] {label} ({ex.GetType().Name}): {ex.Message}");
            }
        }

        private static void Require(bool condition, string message)
        {
            if (!condition)
                throw new SmokeAssertException(message);
        }

        private sealed class SmokeAssertException : Exception
        {
            public SmokeAssertException(string message) : base(message) { }
        }
    }
}
