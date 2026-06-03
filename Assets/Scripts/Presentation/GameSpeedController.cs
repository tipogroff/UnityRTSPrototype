using RTS.Gameplay;
using RTS.MLAgents.Stage7B;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

#if UNITY_EDITOR
using System.Reflection;
#endif

namespace RTS.Presentation
{
    [System.Flags]
    public enum SimulationPauseReason
    {
        None = 0,
        Hotkey = 1 << 0,
        Menu = 1 << 1,
        External = 1 << 2,
    }

    [DisallowMultipleComponent]
    public sealed class GameSpeedController : MonoBehaviour
    {
        private enum InputBackendMode
        {
            Unknown = 0,
            NewInputOnly = 1,
            LegacyOnly = 2,
            Both = 3,
        }

        [Header("Mode Safety")]
        [SerializeField] private bool _enableOnlyInManualPlayMode = true;
        [SerializeField] private MlAgentsTrainingBootstrap _trainingBootstrap;

        [Header("Diagnostics")]
        [SerializeField] private bool _showDiagnostics = true;
        [SerializeField] private bool _logPauseDiagnostics = true;
        [SerializeField] private bool _hotkeysEnabled = true;

        [Header("Simulation Step Presets")]
        [SerializeField] private float _normalStepsPerSecond = 5f;
        [SerializeField] private float _slowStepsPerSecond = 2f;
        [SerializeField] private float _fastStepsPerSecond = 10f;
        [SerializeField] private float _debugStepsPerSecond = 20f;

        [Header("Input")]
        [SerializeField] private KeyCode _pauseKey = KeyCode.Space;
        [SerializeField] private KeyCode _speed1xKey = KeyCode.Alpha1;
        [SerializeField] private KeyCode _speedHalfKey = KeyCode.Alpha2;
        [SerializeField] private KeyCode _speedQuarterKey = KeyCode.Alpha3;
        [SerializeField] private KeyCode _speedTenthKey = KeyCode.Alpha4;
        [SerializeField] private KeyCode _stepKey = KeyCode.N;

        [Header("Overlay")]
        [SerializeField] private bool _showOverlay = true;
        [SerializeField] private Vector2 _overlayPosition = new Vector2(10f, 10f);

        private EpisodeController _episodeController;
        private SimulationPauseReason _pauseReasons;
        private float _activeStepsPerSecond = 5f;
        private bool _isActiveForCurrentMode = true;
        private bool _inputPollingActive;
        private string _lastHotkey = "none";
        private string _lastInputSource = "none";
        private int _updateCount;
        private float _lastUpdateRealtime;
        private string _inputBackendDescription = "unknown";
        private InputBackendMode _inputBackendMode = InputBackendMode.Unknown;
        private bool _legacyPollingEnabled;
        private bool _newInputPollingEnabled;
        private bool _keyboardCurrentExists;
        private bool _legacyInputUnavailable;

        public float CurrentSpeed => IsPaused ? 0f : _activeStepsPerSecond / Mathf.Max(0.01f, _normalStepsPerSecond);
        public float CurrentStepsPerSecond => IsPaused ? 0f : _activeStepsPerSecond;
        public bool IsPaused => _pauseReasons != SimulationPauseReason.None;
        public SimulationPauseReason ActiveReasons => _pauseReasons;
        public bool IsPausedByMenu => (_pauseReasons & SimulationPauseReason.Menu) != 0;
        public bool IsPausedByHotkey => (_pauseReasons & SimulationPauseReason.Hotkey) != 0;
        public string PauseReasons => _pauseReasons.ToString();
        public bool HotkeysEnabled => _hotkeysEnabled;
        public bool OverlayEnabled => _showOverlay;
        public bool InputPollingActive => _inputPollingActive;
        public string LastHotkey => _lastHotkey;
        public string LastInputSource => _lastInputSource;
        public string InputBackendDescription => _inputBackendDescription;
        public bool KeyboardCurrentExists => _keyboardCurrentExists;
        public bool LegacyPollingEnabled => _legacyPollingEnabled;
        public bool NewInputPollingEnabled => _newInputPollingEnabled;

        private void Awake()
        {
            _inputBackendMode = DetectInputBackendMode();
            _inputBackendDescription = DescribeInputBackend(_inputBackendMode);

            if (_trainingBootstrap == null)
            {
                _trainingBootstrap = FindFirstObjectByType<MlAgentsTrainingBootstrap>();
            }

            _episodeController = EpisodeController.Instance;
            if (_episodeController == null)
            {
                _episodeController = FindFirstObjectByType<EpisodeController>();
            }

            _activeStepsPerSecond = Mathf.Max(0.01f, _normalStepsPerSecond);
            _isActiveForCurrentMode = EvaluateModeGate();
            _legacyPollingEnabled = _inputBackendMode == InputBackendMode.LegacyOnly || _inputBackendMode == InputBackendMode.Both;
            _newInputPollingEnabled = _inputBackendMode == InputBackendMode.NewInputOnly || _inputBackendMode == InputBackendMode.Both;
            _inputPollingActive = _isActiveForCurrentMode && _hotkeysEnabled && (_legacyPollingEnabled || _newInputPollingEnabled);

            if (_isActiveForCurrentMode)
            {
                ApplyStepsPerSecond(_activeStepsPerSecond);
            }
            else
            {
                RestoreTimeDefaults();
            }
        }

        private void OnEnable()
        {
            if (!_isActiveForCurrentMode)
            {
                return;
            }

            if (IsPaused)
            {
                ApplyPauseStateToEpisode();
                return;
            }

            ApplyStepsPerSecond(_activeStepsPerSecond);
        }

        private void Update()
        {
            _updateCount++;
            _lastUpdateRealtime = Time.unscaledTime;
            RefreshInputDiagnostics();

            if (!_inputPollingActive)
            {
                return;
            }

            if (WasKeyPressed(_pauseKey))
            {
                _lastHotkey = "Space";
                TogglePauseFromHotkey();
            }

            if (_pauseKey != KeyCode.Escape
                && !HasActiveHumanPlayCanvasController()
                && WasKeyPressed(KeyCode.Escape))
            {
                _lastHotkey = "Escape";
                TogglePauseFromHotkey();
            }

            if (WasKeyPressed(_speed1xKey) || WasKeyPressed(KeyCode.Keypad1))
            {
                _lastHotkey = "1";
                SetTargetStepsPerSecond(_normalStepsPerSecond);
            }

            if (WasKeyPressed(_speedHalfKey) || WasKeyPressed(KeyCode.Keypad2))
            {
                _lastHotkey = "2";
                SetTargetStepsPerSecond(_slowStepsPerSecond);
            }

            if (WasKeyPressed(_speedQuarterKey) || WasKeyPressed(KeyCode.Keypad3))
            {
                _lastHotkey = "3";
                SetTargetStepsPerSecond(_fastStepsPerSecond);
            }

            if (WasKeyPressed(_speedTenthKey) || WasKeyPressed(KeyCode.Keypad4))
            {
                _lastHotkey = "4";
                SetTargetStepsPerSecond(_debugStepsPerSecond);
            }

            if (WasKeyPressed(_stepKey))
            {
                _lastHotkey = "N";
                StepOnce();
            }
        }

        private void OnDisable()
        {
            RestoreTimeDefaults();
        }

        private void OnDestroy()
        {
            RestoreTimeDefaults();
        }

        public void SetSpeed(float speed)
        {
            SetTargetStepsPerSecond(_normalStepsPerSecond * Mathf.Max(0.01f, speed));
        }

        public void SetTargetStepsPerSecond(float stepsPerSecond)
        {
            if (!_isActiveForCurrentMode)
            {
                return;
            }

            _activeStepsPerSecond = Mathf.Max(0.01f, stepsPerSecond);
            if (IsPaused)
            {
                ApplySelectedStepsPerSecondWhilePaused();
                return;
            }

            ApplyStepsPerSecond(_activeStepsPerSecond);
        }

        public void Pause()
        {
            RequestPause(SimulationPauseReason.External);
        }

        public void Resume()
        {
            ReleasePause(SimulationPauseReason.External);
        }

        public void TogglePause()
        {
            TogglePauseFromHotkey();
        }

        public void TogglePauseFromHotkey()
        {
            if ((_pauseReasons & SimulationPauseReason.Hotkey) == 0)
            {
                RequestPause(SimulationPauseReason.Hotkey);
            }
            else
            {
                ReleasePause(SimulationPauseReason.Hotkey);
            }
        }

        public void PauseFromMenu()
        {
            RequestPause(SimulationPauseReason.Menu);
        }

        public void ResumeFromMenu()
        {
            ReleasePause(SimulationPauseReason.Menu);
        }

        public void SetPausedFromExternal(bool paused)
        {
            if (paused)
            {
                RequestPause(SimulationPauseReason.External);
            }
            else
            {
                ReleasePause(SimulationPauseReason.External);
            }
        }

        public void RequestPause(SimulationPauseReason reason)
        {
            SetPauseReason(reason, true);
        }

        public void ReleasePause(SimulationPauseReason reason)
        {
            SetPauseReason(reason, false);
        }

        public void ClearAllPauseReasons(string source = null)
        {
            if (!_isActiveForCurrentMode)
            {
                _pauseReasons = SimulationPauseReason.None;
                return;
            }

            if (_pauseReasons == SimulationPauseReason.None)
            {
                ReapplyPauseState(source ?? "ClearAllPauseReasons.noop");
                return;
            }

            SimulationPauseReason previousReasons = _pauseReasons;
            _pauseReasons = SimulationPauseReason.None;
            LogPauseDiagnostic($"ClearAllPauseReasons source={source ?? "unspecified"} previous={previousReasons}");
            ReapplyPauseState(source ?? "ClearAllPauseReasons");
        }

        public void ReapplyPauseState(string source = null)
        {
            ResolveEpisodeController();
            bool shouldPause = IsPaused;
            if (_episodeController == null)
            {
                LogPauseDiagnostic($"Reapply skipped source={source ?? "unspecified"} active={_pauseReasons} isPaused={shouldPause} episodeController=<null>");
                return;
            }

            _episodeController.SetAutomaticSteppingPaused(shouldPause);
            if (!shouldPause)
            {
                _episodeController.SetTargetStepsPerSecond(Mathf.Max(0.01f, _activeStepsPerSecond));
            }

            LogPauseDiagnostic(
                $"Reapply source={source ?? "unspecified"} active={_pauseReasons} isPaused={shouldPause} "
                + $"episodeController={_episodeController.GetInstanceID()} stepsPerSecond={_activeStepsPerSecond:0.##}");
        }

        private void SetPauseReason(SimulationPauseReason reason, bool active)
        {
            if (!_isActiveForCurrentMode)
            {
                return;
            }

            if (reason == SimulationPauseReason.None)
            {
                return;
            }

            SimulationPauseReason previousReasons = _pauseReasons;
            if (active)
            {
                _pauseReasons |= reason;
            }
            else
            {
                _pauseReasons &= ~reason;
            }

            if (previousReasons == _pauseReasons)
            {
                LogPauseDiagnostic($"Request unchanged reason={reason} active={active} activeReasons={_pauseReasons} isPaused={IsPaused}");
                ReapplyPauseState("unchanged");
                return;
            }

            LogPauseDiagnostic($"Request reason={reason} active={active} activeReasons={_pauseReasons} isPaused={IsPaused}");
            ReapplyPauseState(active ? "RequestPause" : "ReleasePause");
        }

        public bool StepOnce()
        {
            if (!_isActiveForCurrentMode || !IsPaused)
            {
                LogPauseDiagnostic($"StepOnce rejected: active={_isActiveForCurrentMode} isPaused={IsPaused} activeReasons={_pauseReasons}");
                return false;
            }

            if (_episodeController == null)
            {
                _episodeController = EpisodeController.Instance;
                if (_episodeController == null)
                {
                    _episodeController = FindFirstObjectByType<EpisodeController>();
                }
            }

            if (_episodeController == null)
            {
                Debug.LogWarning("[GameSpeedController] StepOnce skipped: EpisodeController is missing.");
                return false;
            }

            bool stepped = _episodeController.StepEpisodeOnce();
            LogPauseDiagnostic($"StepOnce {(stepped ? "accepted" : "rejected")} activeReasons={_pauseReasons}");
            ReapplyPauseState("StepOnce");
            return stepped;
        }

        public void ResetSpeed()
        {
            _activeStepsPerSecond = Mathf.Max(0.01f, _normalStepsPerSecond);
            ClearAllPauseReasons("ResetSpeed");

            if (_isActiveForCurrentMode)
            {
                ApplyStepsPerSecond(_activeStepsPerSecond);
            }
            else
            {
                RestoreTimeDefaults();
            }
        }

        public void SetOverlayVisible(bool visible)
        {
            _showOverlay = visible;
        }

        private bool EvaluateModeGate()
        {
            if (!_enableOnlyInManualPlayMode)
            {
                return true;
            }

            if (_trainingBootstrap == null)
            {
                _trainingBootstrap = FindFirstObjectByType<MlAgentsTrainingBootstrap>();
            }

            if (_trainingBootstrap == null)
            {
                return true;
            }

            return _trainingBootstrap.RuntimeMode != Stage7BRuntimeMode.TrainerControlled;
        }

        private bool WasKeyPressed(KeyCode key)
        {
            if (IsUiFieldFocused())
            {
                return false;
            }

            if (_inputBackendMode == InputBackendMode.NewInputOnly)
            {
                if (TryGetInputSystemKeyPressed(key, out bool inputSystemPressedNewOnly) && inputSystemPressedNewOnly)
                {
                    _lastInputSource = "NewInput";
                    return true;
                }

                return false;
            }

            if (_inputBackendMode == InputBackendMode.Both)
            {
                if (TryGetInputSystemKeyPressed(key, out bool inputSystemPressedBoth) && inputSystemPressedBoth)
                {
                    _lastInputSource = "NewInput";
                    return true;
                }

                if (TryGetLegacyKeyPressed(key))
                {
                    _lastInputSource = "Legacy";
                    return true;
                }

                return false;
            }

            if (_inputBackendMode == InputBackendMode.LegacyOnly)
            {
                if (TryGetLegacyKeyPressed(key))
                {
                    _lastInputSource = "Legacy";
                    return true;
                }

                return false;
            }

            return false;
        }

        private static bool IsUiFieldFocused()
        {
            EventSystem eventSystem = EventSystem.current;
            if (eventSystem == null || eventSystem.currentSelectedGameObject == null)
            {
                return false;
            }

            return eventSystem.currentSelectedGameObject.GetComponent<InputField>() != null;
        }

        private static bool HasActiveHumanPlayCanvasController()
        {
            MonoBehaviour[] behaviours = FindObjectsByType<MonoBehaviour>(FindObjectsInactive.Exclude, FindObjectsSortMode.None);
            for (int i = 0; i < behaviours.Length; i++)
            {
                MonoBehaviour behaviour = behaviours[i];
                if (behaviour != null && behaviour.GetType().Name == "HumanPlayCanvasController")
                {
                    return true;
                }
            }

            return false;
        }

#if ENABLE_INPUT_SYSTEM
        private static bool TryGetInputSystemKeyPressed(KeyCode key, out bool isPressed)
        {
            isPressed = false;
            Keyboard keyboard = Keyboard.current;
            if (keyboard == null)
            {
                return false;
            }

            // New Input System path only. Legacy fallback is intentionally not called here.

            switch (key)
            {
                case KeyCode.Space:
                    isPressed = keyboard.spaceKey.wasPressedThisFrame;
                    return true;
                case KeyCode.Alpha1:
                case KeyCode.Keypad1:
                    isPressed = keyboard.digit1Key.wasPressedThisFrame || keyboard.numpad1Key.wasPressedThisFrame;
                    return true;
                case KeyCode.Alpha2:
                case KeyCode.Keypad2:
                    isPressed = keyboard.digit2Key.wasPressedThisFrame || keyboard.numpad2Key.wasPressedThisFrame;
                    return true;
                case KeyCode.Alpha3:
                case KeyCode.Keypad3:
                    isPressed = keyboard.digit3Key.wasPressedThisFrame || keyboard.numpad3Key.wasPressedThisFrame;
                    return true;
                case KeyCode.Alpha4:
                case KeyCode.Keypad4:
                    isPressed = keyboard.digit4Key.wasPressedThisFrame || keyboard.numpad4Key.wasPressedThisFrame;
                    return true;
                case KeyCode.N:
                    isPressed = keyboard.nKey.wasPressedThisFrame;
                    return true;
                case KeyCode.Escape:
                    isPressed = keyboard.escapeKey.wasPressedThisFrame;
                    return true;
                default:
                    return false;
            }
        }
#endif

        private bool TryGetLegacyKeyPressed(KeyCode key)
        {
            if (_legacyInputUnavailable)
            {
                return false;
            }

#if ENABLE_LEGACY_INPUT_MANAGER
            try
            {
                return Input.GetKeyDown(key);
            }
            catch (System.InvalidOperationException)
            {
                _legacyInputUnavailable = true;
                return false;
            }
#else
            return false;
#endif
        }

        private static InputBackendMode DetectInputBackendMode()
        {
#if UNITY_EDITOR
            object value = ReadEditorInputBackendValue();
            if (value != null)
            {
                InputBackendMode editorMode = ConvertEditorInputBackendValue(value);
                if (editorMode != InputBackendMode.Unknown)
                {
                    return editorMode;
                }
            }
#endif

#if ENABLE_INPUT_SYSTEM && ENABLE_LEGACY_INPUT_MANAGER
            return InputBackendMode.Both;
#elif ENABLE_INPUT_SYSTEM
            return InputBackendMode.NewInputOnly;
#elif ENABLE_LEGACY_INPUT_MANAGER
            return InputBackendMode.LegacyOnly;
#else
            return InputBackendMode.Unknown;
#endif
        }

#if UNITY_EDITOR
        private static object ReadEditorInputBackendValue()
        {
            System.Type playerSettingsType = typeof(UnityEditor.PlayerSettings);
            PropertyInfo property = playerSettingsType.GetProperty("activeInputHandler", BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic)
                ?? playerSettingsType.GetProperty("activeInputHandling", BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic);

            if (property == null)
            {
                return null;
            }

            try
            {
                return property.GetValue(null);
            }
            catch
            {
                return null;
            }
        }

        private static InputBackendMode ConvertEditorInputBackendValue(object value)
        {
            string text = value.ToString();
            if (!string.IsNullOrEmpty(text))
            {
                if (text.IndexOf("Both", System.StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    return InputBackendMode.Both;
                }

                if (text.IndexOf("InputSystem", System.StringComparison.OrdinalIgnoreCase) >= 0
                    || text.IndexOf("New", System.StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    return InputBackendMode.NewInputOnly;
                }

                if (text.IndexOf("InputManager", System.StringComparison.OrdinalIgnoreCase) >= 0
                    || text.IndexOf("Legacy", System.StringComparison.OrdinalIgnoreCase) >= 0)
                {
                    return InputBackendMode.LegacyOnly;
                }
            }

            if (value is int integerValue)
            {
                switch (integerValue)
                {
                    case 0:
                        return InputBackendMode.LegacyOnly;
                    case 1:
                        return InputBackendMode.NewInputOnly;
                    case 2:
                        return InputBackendMode.Both;
                    default:
                        return InputBackendMode.Unknown;
                }
            }

            return InputBackendMode.Unknown;
        }
#endif

        private static string DescribeInputBackend(InputBackendMode mode)
        {
            switch (mode)
            {
                case InputBackendMode.NewInputOnly:
                    return "NewInputOnly";
                case InputBackendMode.LegacyOnly:
                    return "LegacyOnly";
                case InputBackendMode.Both:
                    return "Both";
                default:
                    return "Unknown";
            }
        }

        private void ApplyStepsPerSecond(float stepsPerSecond)
        {
            ResolveEpisodeController();
            if (_episodeController == null)
            {
                LogPauseDiagnostic($"ApplyStepsPerSecond skipped: EpisodeController missing stepsPerSecond={stepsPerSecond:0.##}");
                return;
            }

            _episodeController.SetAutomaticSteppingPaused(false);
            _episodeController?.SetTargetStepsPerSecond(Mathf.Max(0.01f, stepsPerSecond));
            LogPauseDiagnostic($"ApplyStepsPerSecond stepsPerSecond={stepsPerSecond:0.##}");
        }

        private void ApplySelectedStepsPerSecondWhilePaused()
        {
            ResolveEpisodeController();
            _episodeController?.SetTargetStepsPerSecond(Mathf.Max(0.01f, _activeStepsPerSecond));
            ApplyPauseStateToEpisode();
        }

        private void ApplyPauseStateToEpisode()
        {
            ReapplyPauseState("ApplyPauseStateToEpisode");
        }

        private void RestoreTimeDefaults()
        {
            ResolveEpisodeController();
            _pauseReasons = SimulationPauseReason.None;
            _episodeController?.SetAutomaticSteppingPaused(false);
        }

        private void ResolveEpisodeController()
        {
            if (_episodeController == null)
            {
                _episodeController = EpisodeController.Instance;
                if (_episodeController == null)
                {
                    _episodeController = FindFirstObjectByType<EpisodeController>();
                }
            }
        }

        private void RefreshInputDiagnostics()
        {
#if ENABLE_INPUT_SYSTEM
            _keyboardCurrentExists = Keyboard.current != null;
#else
            _keyboardCurrentExists = false;
#endif
        }

        private void LogPauseDiagnostic(string message)
        {
            if (_logPauseDiagnostics)
            {
                Debug.Log("[Pause] " + message);
            }
        }

        private void OnGUI()
        {
            if (!_showOverlay)
            {
                return;
            }

            GUILayout.BeginArea(new Rect(_overlayPosition.x, _overlayPosition.y, 420f, 290f), GUI.skin.box);
            GUILayout.Label("Human/Demo Speed Controller", new GUIStyle(GUI.skin.label)
            {
                fontStyle = FontStyle.Bold,
                fontSize = 13,
            });

            string mode = _isActiveForCurrentMode ? "Enabled" : "Disabled (TrainerControlled mode)";
            string speedLabel = IsPaused ? "Paused" : _activeStepsPerSecond.ToString("0.##") + " steps/sec";
            GUILayout.Label("Mode: " + mode);
            GUILayout.Label("Controller enabled: " + enabled);
            GUILayout.Label("Input polling active: " + _inputPollingActive);
            GUILayout.Label("Legacy polling enabled: " + _legacyPollingEnabled);
            GUILayout.Label("New input polling enabled: " + _newInputPollingEnabled);
            GUILayout.Label("Keyboard.current exists: " + _keyboardCurrentExists);
            if (!_keyboardCurrentExists)
            {
                GUILayout.Label("Keyboard.current = null / input unavailable / focus issue");
            }
            GUILayout.Label("Last hotkey: " + _lastHotkey);
            GUILayout.Label("Last input source: " + _lastInputSource);
            GUILayout.Label("Input backend: " + _inputBackendDescription);
            GUILayout.Label("Update called: " + (_updateCount > 0) + " (ticks=" + _updateCount + ")");
            GUILayout.Label("Last update realtime: " + _lastUpdateRealtime.ToString("0.00"));
            GUILayout.Label("Current timeScale: " + Time.timeScale.ToString("0.00"));
            GUILayout.Label("Current fixedDeltaTime: " + Time.fixedDeltaTime.ToString("0.0000"));
            GUILayout.Label("Simulation speed: " + speedLabel);
            GUILayout.Label("Paused: " + IsPaused);
            GUILayout.Label("Pause reasons: " + _pauseReasons);
            GUILayout.Label("Controls: Space pause/resume, 1/2/3/4 speed, N step (paused only)");
            GUILayout.Space(6f);

            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Normal", GUILayout.Height(28f)))
            {
                _lastHotkey = "mouse:normal";
                _lastInputSource = "GUI";
                SetTargetStepsPerSecond(_normalStepsPerSecond);
            }

            if (GUILayout.Button("Slow", GUILayout.Height(28f)))
            {
                _lastHotkey = "mouse:slow";
                _lastInputSource = "GUI";
                SetTargetStepsPerSecond(_slowStepsPerSecond);
            }

            if (GUILayout.Button("Fast", GUILayout.Height(28f)))
            {
                _lastHotkey = "mouse:fast";
                _lastInputSource = "GUI";
                SetTargetStepsPerSecond(_fastStepsPerSecond);
            }

            if (GUILayout.Button("Debug", GUILayout.Height(28f)))
            {
                _lastHotkey = "mouse:debug";
                _lastInputSource = "GUI";
                SetTargetStepsPerSecond(_debugStepsPerSecond);
            }
            GUILayout.EndHorizontal();

            GUILayout.BeginHorizontal();
            if (GUILayout.Button(IsPaused ? "Resume" : "Pause", GUILayout.Height(28f)))
            {
                _lastHotkey = "mouse:pause";
                _lastInputSource = "GUI";
                TogglePause();
            }

            GUI.enabled = IsPaused;
            if (GUILayout.Button("Step", GUILayout.Height(28f)))
            {
                _lastHotkey = "mouse:step";
                _lastInputSource = "GUI";
                StepOnce();
            }
            GUI.enabled = true;
            GUILayout.EndHorizontal();

            if (_showDiagnostics)
            {
                GUILayout.Label("Diagnostics active");
            }

            GUILayout.EndArea();
        }
    }
}
