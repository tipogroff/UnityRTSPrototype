// SmokeTestAutomation.cs — автоматизированный smoke-test для Play Mode.
// Этот скрипт ТОЛЬКО для Editor-отладки во время Play Mode.
// 
// Использование:
//   1. В Unity Editor: Window → SmokeTest (или нажмите кнопку в какой-нибудь панели)
//   2. Нажмите "Play Mode Smoke-Test"
//   3. Игра войдет в Play Mode и автоматически запустит тест
//   4. Смотрите результаты в Console

#if UNITY_EDITOR
using UnityEngine;
using RTS.Gameplay;

namespace RTS.Testing
{
    /// <summary>
    /// Один-в-один автоматизированный smoke-test.
    /// Запускается автоматически, если эпизод стартует.
    /// </summary>
    public class SmokeTestAutomation : MonoBehaviour
    {
        public static SmokeTestAutomation Instance { get; private set; }

        private int _targetSteps = 0;
        private int _stepsReachedCount = 0;
        private bool _waitingForTerminal = false;
        private int _startStep = 0;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
        }

        public void StartAutomatedTest(int stepsBeforeCheck = 5)
        {
            _targetSteps = stepsBeforeCheck;
            _startStep = 0;
            _stepsReachedCount = 0;
            _waitingForTerminal = false;

            Debug.Log("╔════════════════════════════════════════════════════════════╗");
            Debug.Log("║          AUTOMATED SMOKE-TEST STARTED                      ║");
            Debug.Log($"║          Goal: Run {_targetSteps} steps, check terminal, reset    ║");
            Debug.Log("╚════════════════════════════════════════════════════════════╝");
        }

        private void FixedUpdate()
        {
            if (!TestIsRunning())
            {
                return;
            }

            MatchManager mm = MatchManager.Instance;
            EpisodeController ec = EpisodeController.Instance;

            if (mm == null || ec == null)
            {
                return;
            }

            // Phase: Stepping
            if (_stepsReachedCount < _targetSteps && mm.Phase == MatchPhase.Running)
            {
                if (mm.Step != _startStep)
                {
                    _stepsReachedCount = mm.Step - _startStep;
                    Debug.Log($"[SmokeTest] Step {mm.Step} | Progress: {_stepsReachedCount}/{_targetSteps}");

                    if (_stepsReachedCount >= _targetSteps)
                    {
                        Debug.Log($"[SmokeTest] ✅ Reached {_targetSteps} steps. Waiting for terminal...");
                        _waitingForTerminal = true;
                    }
                }
            }

            // Phase: Waiting for terminal
            if (_waitingForTerminal && mm.Phase == MatchPhase.Ended)
            {
                Debug.Log($"\n[SmokeTest] ✅ TERMINAL REACHED!");
                Debug.Log($"  Winner: {mm.Winner}");
                Debug.Log($"  Reason: {mm.EndReason}");
                Debug.Log($"  Details: {mm.EndReasonDetails}");
                Debug.Log($"  Final Step: {mm.Step}");

                // Reset
                Debug.Log($"\n[SmokeTest] Resetting episode...");
                ec.ResetEpisode();

                // Check post-reset
                Debug.Log($"\n[SmokeTest] ✅ RESET COMPLETE!");
                Debug.Log($"  Episode Index: {ec.EpisodeIndex}");
                Debug.Log($"  Phase: {mm.Phase}");
                Debug.Log($"  Step: {mm.Step}");
                Debug.Log($"  Winner (should be Neutral): {mm.Winner}");

                PrintFinalResults(mm, ec);
                StopTest();
            }
        }

        private void PrintFinalResults(MatchManager mm, EpisodeController ec)
        {
            bool phaseOk = mm.Phase == MatchPhase.Running;
            bool stepOk = mm.Step == 0;
            bool episodeOk = ec.EpisodeIndex >= 2;

            Debug.Log($"\n╔════════════════════════════════════════════════════════════╗");
            Debug.Log($"║                  SMOKE-TEST RESULTS                       ║");
            Debug.Log($"╚════════════════════════════════════════════════════════════╝");
            Debug.Log($"  ✓ Executed {_targetSteps}+ steps: ✅ PASS");
            Debug.Log($"  ✓ Reached terminal: ✅ PASS");
            Debug.Log($"  ✓ Phase reset to Running: {(phaseOk ? "✅ PASS" : "❌ FAIL")}");
            Debug.Log($"  ✓ Step counter reset to 0: {(stepOk ? "✅ PASS" : "❌ FAIL")}");
            Debug.Log($"  ✓ Episode index incremented: {(episodeOk ? "✅ PASS" : "❌ FAIL")}");

            if (phaseOk && stepOk && episodeOk)
            {
                Debug.Log($"\n🎉 ALL SMOKE-TESTS PASSED!");
            }
            else
            {
                Debug.LogWarning($"\n⚠️  Some tests failed. Check results above.");
            }
        }

        public void StopTest()
        {
            _waitingForTerminal = false;
            _stepsReachedCount = 0;
        }

        public bool TestIsRunning()
        {
            return _stepsReachedCount >= 0 && _stepsReachedCount < _targetSteps;
        }
    }
}
#endif
