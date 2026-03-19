// EpisodeControllerTestHelper.cs — простой EditorHelper для smoke-test цикла.
// Использование:
//   1. Откройте GameScene.unity
//   2. Нажмите Play
//   3. В Console выполните: EpisodeControllerTestHelper.RunSmokeTest()
//   4. Смотрите логи в Console
//
// Этот скрипт НЕ входит в игру, только для отладки.

#if UNITY_EDITOR
using UnityEngine;
using System.Collections;
using RTS.Gameplay;

namespace RTS.Testing
{
    public static class EpisodeControllerTestHelper
    {
        /// <summary>
        /// Вызывается из Console: StartCoroutine(EpisodeControllerTestHelper.RunSmokeTest());
        /// или непосредственно для синхронного теста (ограничено несколькими шагами).
        /// </summary>
        public static void RunSmokeTest()
        {
            EpisodeController controller = EpisodeController.Instance;
            MatchManager matchManager = MatchManager.Instance;

            if (controller == null || matchManager == null)
            {
                UnityEngine.Debug.LogError("[SmokeTest] EpisodeController or MatchManager is null. Make sure you're in Play Mode with GameScene loaded.");
                return;
            }

            UnityEngine.Debug.Log("╔════════════════════════════════════════════════════════════╗");
            UnityEngine.Debug.Log("║           SMOKE-TEST: Episode → Steps → Terminal → Reset   ║");
            UnityEngine.Debug.Log("╚════════════════════════════════════════════════════════════╝");

            // Phase 1: Check initial state
            UnityEngine.Debug.Log($"\n[Phase 1] Initial State:");
            UnityEngine.Debug.Log($"  EpisodeIndex: {controller.EpisodeIndex}");
            UnityEngine.Debug.Log($"  IsRunning: {controller.IsRunning}");
            UnityEngine.Debug.Log($"  MatchManager.Phase: {matchManager.Phase}");
            UnityEngine.Debug.Log($"  MatchManager.Step: {matchManager.Step}");
            UnityEngine.Debug.Log($"  MatchManager.MaxSteps: {matchManager.MaxSteps}");

            // Phase 2: Print step counters loop (will continue in FixedUpdate if auto-step enabled)
            UnityEngine.Debug.Log($"\n[Phase 2] Monitoring steps (FixedUpdate will auto-increment if enabled):");
            _stepSnapshot = matchManager.Step;
            _lastPhase = matchManager.Phase;
            _monitoringEnabled = true;

            UnityEngine.Debug.Log($"\n[Log] The match will step automatically every FixedUpdate (~0.02s).");
            UnityEngine.Debug.Log($"[Log] Watch the Step counter increment and Phase change to 'Ended'.");
            UnityEngine.Debug.Log($"[Log] When terminal is reached, run: EpisodeControllerTestHelper.ResetAndCheckPhase2()");
        }

        public static void ResetAndCheckPhase2()
        {
            if (_monitoringEnabled)
            {
                _monitoringEnabled = false;
            }

            EpisodeController controller = EpisodeController.Instance;
            MatchManager matchManager = MatchManager.Instance;

            if (controller == null || matchManager == null)
            {
                UnityEngine.Debug.LogError("[SmokeTest] Controllers null during reset.");
                return;
            }

            UnityEngine.Debug.Log($"\n[Phase 3] Terminal State Before Reset:");
            UnityEngine.Debug.Log($"  MatchManager.Phase: {matchManager.Phase}");
            UnityEngine.Debug.Log($"  MatchManager.Step: {matchManager.Step}");
            UnityEngine.Debug.Log($"  MatchManager.Winner: {matchManager.Winner}");
            UnityEngine.Debug.Log($"  MatchManager.EndReason: {matchManager.EndReason}");

            // Phase 4: Reset
            UnityEngine.Debug.Log($"\n[Phase 4] Resetting episode...");
            controller.ResetEpisode();

            // Phase 5: Check post-reset state
            UnityEngine.Debug.Log($"\n[Phase 5] Post-Reset State:");
            UnityEngine.Debug.Log($"  EpisodeIndex: {controller.EpisodeIndex}");
            UnityEngine.Debug.Log($"  IsRunning: {controller.IsRunning}");
            UnityEngine.Debug.Log($"  MatchManager.Phase: {matchManager.Phase}");
            UnityEngine.Debug.Log($"  MatchManager.Step: {matchManager.Step}");
            UnityEngine.Debug.Log($"  MatchManager.Winner: {matchManager.Winner}");

            // Verify
            bool phaseCorrect = matchManager.Phase == MatchPhase.Running;
            bool stepReset = matchManager.Step == 0;
            bool episodeIncremented = controller.EpisodeIndex >= 2; // Was 1, now should be 2+

            UnityEngine.Debug.Log($"\n╔════════════════════════════════════════════════════════════╗");
            UnityEngine.Debug.Log($"║                     SMOKE-TEST RESULTS                      ║");
            UnityEngine.Debug.Log($"╚════════════════════════════════════════════════════════════╝");
            UnityEngine.Debug.Log($"  ✓ Phase reset to Running: {(phaseCorrect ? "✅ PASS" : "❌ FAIL")}");
            UnityEngine.Debug.Log($"  ✓ Step counter reset to 0: {(stepReset ? "✅ PASS" : "❌ FAIL")}");
            UnityEngine.Debug.Log($"  ✓ Episode index incremented: {(episodeIncremented ? "✅ PASS" : "❌ FAIL")}");

            if (phaseCorrect && stepReset && episodeIncremented)
            {
                UnityEngine.Debug.Log($"\n🎉 SMOKE-TEST PASSED! Lifecycle cycle is working correctly.");
            }
            else
            {
                UnityEngine.Debug.LogError($"\n⚠️  SMOKE-TEST FAILED! Check the results above.");
            }
        }

        private static bool _monitoringEnabled = false;
        private static int _stepSnapshot = 0;
        private static MatchPhase _lastPhase = MatchPhase.Idle;

        // Call this from FixedUpdate or periodically to monitor
        public static void UpdateMonitoring()
        {
            if (!_monitoringEnabled)
            {
                return;
            }

            MatchManager mm = MatchManager.Instance;
            if (mm == null)
            {
                return;
            }

            if (mm.Step != _stepSnapshot)
            {
                UnityEngine.Debug.Log($"[Monitor] Step: {_stepSnapshot} → {mm.Step}");
                _stepSnapshot = mm.Step;
            }

            if (mm.Phase != _lastPhase)
            {
                UnityEngine.Debug.Log($"[Monitor] Phase: {_lastPhase} → {mm.Phase}");
                _lastPhase = mm.Phase;

                if (mm.Phase == MatchPhase.Ended)
                {
                    UnityEngine.Debug.Log($"[Monitor] ✅ Terminal reached! Winner={mm.Winner}, Reason={mm.EndReason}");
                    UnityEngine.Debug.Log($"[Monitor] Now run: EpisodeControllerTestHelper.ResetAndCheckPhase2()");
                    _monitoringEnabled = false;
                }
            }
        }
    }

    /// <summary>
    /// Небольшой MonoBehaviour, который вызывает UpdateMonitoring каждый FixedUpdate.
    /// Скрипт присоединяется к EpisodeController автоматически при запуске.
    /// </summary>
    public class SmokeTestMonitor : MonoBehaviour
    {
        private void FixedUpdate()
        {
            EpisodeControllerTestHelper.UpdateMonitoring();
        }
    }
}
#endif

