// ManualStepController.cs — удобная отладка пошагового выполнения матча.
// Неделя 2, Этап 6.

using UnityEngine;
using RTS.Core;

namespace RTS.Gameplay
{
    /// <summary>
    /// Контроллер для пошагового выполнения матча при отладке.
    /// Позволяет:
    /// - нажать кнопку → один тик
    /// - нажать кнопку → 10 тиков
    /// - play/pause весь матч
    /// - reset матч
    ///
    /// Может быть использован как с UI, так и с клавиатурными командами.
    /// </summary>
    public class ManualStepController : MonoBehaviour
    {
        public static ManualStepController Instance { get; private set; }

        [SerializeField] private EpisodeController _episodeController;
        [SerializeField] private MatchManager _matchManager;

        [Header("Keyboard controls")]
        [SerializeField] private KeyCode stepOneKey = KeyCode.Space;
        [SerializeField] private KeyCode stepTenKey = KeyCode.T;
        [SerializeField] private KeyCode togglePlayKey = KeyCode.P;
        [SerializeField] private KeyCode resetKey = KeyCode.R;

        [Header("UI")]
        [SerializeField] private bool showDebugUI = true;
        [SerializeField] private bool useKeyboardOnly = false;

        private bool _isPlaying = false;
        private int _ticksToExecuteThisFrame = 0;

        // ── UI Debug Info ────────────────────────────────────────────────────────
        private int _currentStep = 0;
        private bool _isPaused = false;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
        }

        private void Start()
        {
            ResolveReferences();
        }

        private void Update()
        {
            HandleKeyboardInput();

            // Выполняем запланированные тики
            ExecuteSteps(_ticksToExecuteThisFrame);
            _ticksToExecuteThisFrame = 0;
        }

        private void HandleKeyboardInput()
        {
            if (Input.GetKeyDown(stepOneKey))
            {
                Step(1);
            }

            if (Input.GetKeyDown(stepTenKey))
            {
                Step(10);
            }

            if (Input.GetKeyDown(togglePlayKey))
            {
                TogglePlayPause();
            }

            if (Input.GetKeyDown(resetKey))
            {
                ResetMatch();
            }
        }

        // ── Public API ───────────────────────────────────────────────────────────

        /// <summary>
        /// Выполнить N тиков матча.
        /// </summary>
        public void Step(int count = 1)
        {
            if (_episodeController == null)
            {
                Debug.LogError("[ManualStepController] EpisodeController не установлен.");
                return;
            }

            _ticksToExecuteThisFrame = count;
            _isPlaying = false;
            _isPaused = true;
            _episodeController.SetRunning(false);
        }

        /// <summary>
        /// Начать/остановить автоматическое выполнение.
        /// </summary>
        public void TogglePlayPause()
        {
            _isPlaying = !_isPlaying;
            _isPaused = !_isPlaying;
            _episodeController?.SetRunning(_isPlaying);
            Debug.Log($"[ManualStepController] Play/Pause: {(_isPlaying ? "PLAYING" : "PAUSED")}");
        }

        /// <summary>
        /// Начать новый матч.
        /// </summary>
        public void ResetMatch()
        {
            if (_episodeController == null)
            {
                Debug.LogError("[ManualStepController] EpisodeController не установлен.");
                return;
            }

            Debug.Log("[ManualStepController] Reset match");
            _episodeController.StartNewEpisode();
            _currentStep = 0;
            _isPlaying = true;
            _isPaused = false;
            _episodeController.SetRunning(true);
        }

        public bool IsPlaying => _isPlaying;
        public bool IsPaused => _isPaused;
        public int CurrentStep => _currentStep;

        // ── Внутренние методы ────────────────────────────────────────────────────

        private void ExecuteSteps(int stepCount)
        {
            if (_episodeController == null)
                return;

            for (int i = 0; i < stepCount; i++)
            {
                bool stillRunning = _episodeController.StepEpisodeOnce();
                if (!stillRunning)
                {
                    _isPlaying = false;
                    _isPaused = true;
                    break;
                }

                _currentStep++;
            }
        }

        private void ResolveReferences()
        {
            if (_episodeController == null)
            {
                _episodeController = EpisodeController.Instance;
            }

            if (_matchManager == null)
            {
                _matchManager = MatchManager.Instance;
            }

            if (_episodeController != null)
            {
                _isPlaying = _episodeController.IsRunning;
                _isPaused = !_isPlaying;
            }
        }

        // ── Debug UI (OnGUI) ────────────────────────────────────────────────────

        private void OnGUI()
        {
            if (!showDebugUI || useKeyboardOnly)
                return;

            GUILayout.BeginArea(new Rect(10, 10, 300, 250), GUI.skin.box);

            GUILayout.Label("= Manual Step Controller =", new GUIStyle(GUI.skin.label) { fontSize = 14, fontStyle = FontStyle.Bold });
            GUILayout.Space(10);

            GUILayout.Label($"Status: {(_isPlaying ? "PLAYING" : "PAUSED")}", new GUIStyle(GUI.skin.label) { fontStyle = FontStyle.Bold });
            GUILayout.Label($"Current Step: {_currentStep}");
            GUILayout.Label($"Match Phase: {(_matchManager != null ? _matchManager.Phase.ToString() : "NULL")}");

            if (_episodeController != null)
            {
                GUILayout.Label($"Episode: {_episodeController.EpisodeIndex}");
                GUILayout.Label($"Running: {_episodeController.IsRunning}");
            }

            GUILayout.Space(10);
            GUILayout.Label("Controls:", new GUIStyle(GUI.skin.label) { fontStyle = FontStyle.Bold });

            if (GUILayout.Button($"Step 1 tick ({stepOneKey})", GUILayout.Height(30)))
            {
                Step(1);
            }

            if (GUILayout.Button($"Step 10 ticks ({stepTenKey})", GUILayout.Height(30)))
            {
                Step(10);
            }

            if (GUILayout.Button($"{(_isPlaying ? "Pause" : "Play")} ({togglePlayKey})", GUILayout.Height(30)))
            {
                TogglePlayPause();
            }

            if (GUILayout.Button($"Reset ({resetKey})", GUILayout.Height(30)))
            {
                ResetMatch();
            }

            GUILayout.EndArea();
        }
    }
}
