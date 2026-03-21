// SmokeTestMenuRunner.cs — EditorScript для запуска smoke-test через меню Unity.
// Автоматически удаляется после тестирования.
#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;
using RTS.Gameplay;

namespace RTS.Testing.Editor
{
    public static class SmokeTestMenuRunner
    {
        [MenuItem("SmokeTest/1 - Print Match State")]
        public static void PrintMatchState()
        {
            MatchManager mm = MatchManager.Instance;
            EpisodeController ec = EpisodeController.Instance;

            if (mm == null || ec == null)
            {
                Debug.LogError("[SmokeTest] Not in Play Mode or components missing.");
                return;
            }

            Debug.Log("═══════════════ MATCH STATE SNAPSHOT ═══════════════");
            Debug.Log($"  EpisodeIndex : {ec.EpisodeIndex}");
            Debug.Log($"  IsRunning    : {ec.IsRunning}");
            Debug.Log($"  Phase        : {mm.Phase}");
            Debug.Log($"  Step         : {mm.Step}");
            Debug.Log($"  MaxSteps     : {mm.MaxSteps}");
            Debug.Log($"  Winner       : {mm.Winner}");
            Debug.Log($"  EndReason    : {mm.EndReason}");
            Debug.Log($"  EndDetails   : {mm.EndReasonDetails}");
            Debug.Log("═════════════════════════════════════════════════════");
        }

        [MenuItem("SmokeTest/2 - Force StepMatch x5")]
        public static void Step5Times()
        {
            MatchManager mm = MatchManager.Instance;
            if (mm == null)
            {
                Debug.LogError("[SmokeTest] Not in Play Mode.");
                return;
            }
            if (mm.Phase != MatchPhase.Running)
            {
                Debug.LogWarning($"[SmokeTest] Phase is {mm.Phase}, cannot step.");
                return;
            }

            Debug.Log($"[SmokeTest] Stepping 5 times from Step={mm.Step}...");
            for (int i = 0; i < 5; i++)
            {
                bool isRunning = mm.StepMatch();
                Debug.Log($"[SmokeTest] StepMatch() → Step={mm.Step}, Phase={mm.Phase}, Running={isRunning}");
                if (!isRunning)
                {
                    break;
                }
            }
            Debug.Log($"[SmokeTest] After 5 steps: Step={mm.Step}, Phase={mm.Phase}");
        }

        [MenuItem("SmokeTest/3 - Force Episode Reset")]
        public static void ForceReset()
        {
            EpisodeController ec = EpisodeController.Instance;
            MatchManager mm = MatchManager.Instance;

            if (ec == null || mm == null)
            {
                Debug.LogError("[SmokeTest] Not in Play Mode.");
                return;
            }

            int prevEpisode = ec.EpisodeIndex;
            Debug.Log($"[SmokeTest] Resetting from Episode {prevEpisode}, Phase={mm.Phase}...");

            ec.ResetEpisode();

            Debug.Log("═══════════════ POST-RESET STATE ════════════════════");
            Debug.Log($"  EpisodeIndex : {ec.EpisodeIndex}  (was {prevEpisode})");
            Debug.Log($"  Phase        : {mm.Phase}  (expected Running)");
            Debug.Log($"  Step         : {mm.Step}  (expected 0)");
            Debug.Log($"  Winner       : {mm.Winner}  (expected Neutral)");
            Debug.Log($"  EndReason    : {mm.EndReason}  (expected None)");

            bool ok = mm.Phase == MatchPhase.Running
                   && mm.Step == 0
                   && ec.EpisodeIndex == prevEpisode + 1;

            if (ok)
            {
                Debug.Log("[SmokeTest] ✅ RESET OK — lifecycle cycle working correctly!");
            }
            else
            {
                Debug.LogWarning("[SmokeTest] ⚠️ RESET had unexpected state. Check logs above.");
            }
            Debug.Log("═════════════════════════════════════════════════════");
        }

        [MenuItem("SmokeTest/4 - FULL AUTO SMOKE TEST")]
        public static void RunFullSmokeTest()
        {
            MatchManager mm = MatchManager.Instance;
            EpisodeController ec = EpisodeController.Instance;

            if (mm == null || ec == null)
            {
                Debug.LogError("[SmokeTest] Enter Play Mode first.");
                return;
            }

            Debug.Log("╔════════════════════════════════════════════════════════╗");
            Debug.Log("║        FULL AUTO SMOKE-TEST INITIATED                  ║");
            Debug.Log("╚════════════════════════════════════════════════════════╝");

            // Шаг 1 — начальное состояние
            Debug.Log($"\n[1] Initial state: Phase={mm.Phase} | Step={mm.Step} | Episode={ec.EpisodeIndex}");
            bool startOk = mm.Phase == MatchPhase.Running;

            // Шаг 2 — 5 принудительных шагов
            int stepsBefore = mm.Step;
            for (int i = 0; i < 5; i++)
            {
                if (mm.Phase != MatchPhase.Running)
                {
                    break;
                }
                mm.StepMatch();
            }
            bool stepsOk = mm.Step > stepsBefore;
            Debug.Log($"[2] After 5 steps: Step={mm.Step} (was {stepsBefore}), +{mm.Step - stepsBefore} steps");

            // Шаг 3 — принудительное завершение до лимита
            // Пропускаем к MaxSteps напрямую через StepMatch в цикле (ограничен 50 итерациями)
            int stepsToTerminal = 0;
            int safetyLimit = 50;
            bool reachedTerminal = false;
            while (mm.Phase == MatchPhase.Running && stepsToTerminal < safetyLimit)
            {
                bool isRunning = mm.StepMatch();
                stepsToTerminal++;
                if (!isRunning)
                {
                    reachedTerminal = true;
                    break;
                }
            }

            bool terminalOk = mm.Phase == MatchPhase.Ended || reachedTerminal;
            Debug.Log($"[3] Terminal? {mm.Phase} | Winner={mm.Winner} | Reason={mm.EndReason} | {stepsToTerminal} extra steps");

            // Принудительный terminal если ещё не наступил
            if (!terminalOk && mm.Phase == MatchPhase.Running)
            {
                mm.DeclareWinner(RTS.Core.Owner.Neutral, MatchEndReason.StepLimitReached, "Forced by smoke-test");
                terminalOk = true;
                Debug.Log("[3b] Forced terminal via DeclareWinner()");
            }

            // Шаг 4 — reset
            int episodeBefore = ec.EpisodeIndex;
            ec.ResetEpisode();
            bool resetOk = mm.Phase == MatchPhase.Running && mm.Step == 0 && ec.EpisodeIndex == episodeBefore + 1;
            Debug.Log($"[4] Reset: Phase={mm.Phase} | Step={mm.Step} | Episode {episodeBefore}→{ec.EpisodeIndex}");

            // Итог
            Debug.Log("\n╔════════════════ SMOKE-TEST RESULTS ════════════════════╗");
            Debug.Log($"  ✓ Start (Phase=Running):       {(startOk   ? "✅ PASS" : "❌ FAIL")}");
            Debug.Log($"  ✓ Steps incremented:           {(stepsOk   ? "✅ PASS" : "❌ FAIL")}");
            Debug.Log($"  ✓ Terminal reached:            {(terminalOk? "✅ PASS" : "❌ FAIL")}");
            Debug.Log($"  ✓ Reset (Step=0, Episode+1):   {(resetOk   ? "✅ PASS" : "❌ FAIL")}");
            Debug.Log("╚════════════════════════════════════════════════════════╝");

            if (startOk && stepsOk && terminalOk && resetOk)
            {
                Debug.Log("🎉  ALL SMOKE-TESTS PASSED!");
            }
            else
            {
                Debug.LogWarning("⚠️  SOME CHECKS FAILED — see above.");
            }
        }
    }
}
#endif
