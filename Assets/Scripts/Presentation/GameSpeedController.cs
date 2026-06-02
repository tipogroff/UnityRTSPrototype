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
        [SerializeField] private bool _hotkeysEnabled = true;

        [Header("Speed Presets")]
        [SerializeField] private float _defaultSpeed = 1f;
        [SerializeField] private float _speedHalf = 0.5f;
        [SerializeField] private float _speedQuarter = 0.25f;
        [SerializeField] private float _speedTenth = 0.1f;

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
        private bool _isPaused;
        private float _activeSpeed = 1f;
        private float _baseTimeScale = 1f;
        private float _baseFixedDeltaTime = 0.02f;
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

        public float CurrentSpeed => _isPaused ? 0f : _activeSpeed;
        public bool IsPaused => _isPaused;
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
            _baseTimeScale = Mathf.Max(0f, Time.timeScale);
            _baseFixedDeltaTime = Time.fixedDeltaTime;
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

            _activeSpeed = Mathf.Max(0.01f, _defaultSpeed);
            _isActiveForCurrentMode = EvaluateModeGate();
            _legacyPollingEnabled = _inputBackendMode == InputBackendMode.LegacyOnly || _inputBackendMode == InputBackendMode.Both;
            _newInputPollingEnabled = _inputBackendMode == InputBackendMode.NewInputOnly || _inputBackendMode == InputBackendMode.Both;
            _inputPollingActive = _isActiveForCurrentMode && _hotkeysEnabled && (_legacyPollingEnabled || _newInputPollingEnabled);

            if (_isActiveForCurrentMode)
            {
                ApplySpeed(_activeSpeed);
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

            if (_isPaused)
            {
                ApplyPauseTimeScale();
                return;
            }

            ApplySpeed(_activeSpeed);
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
                TogglePause();
            }

            if (WasKeyPressed(_speed1xKey) || WasKeyPressed(KeyCode.Keypad1))
            {
                _lastHotkey = "1";
                SetSpeed(_defaultSpeed);
            }

            if (WasKeyPressed(_speedHalfKey) || WasKeyPressed(KeyCode.Keypad2))
            {
                _lastHotkey = "2";
                SetSpeed(_speedHalf);
            }

            if (WasKeyPressed(_speedQuarterKey) || WasKeyPressed(KeyCode.Keypad3))
            {
                _lastHotkey = "3";
                SetSpeed(_speedQuarter);
            }

            if (WasKeyPressed(_speedTenthKey) || WasKeyPressed(KeyCode.Keypad4))
            {
                _lastHotkey = "4";
                SetSpeed(_speedTenth);
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
            if (!_isActiveForCurrentMode)
            {
                return;
            }

            _activeSpeed = Mathf.Max(0.01f, speed);
            _isPaused = false;
            ApplySpeed(_activeSpeed);
        }

        public void Pause()
        {
            if (!_isActiveForCurrentMode)
            {
                return;
            }

            _isPaused = true;
            ApplyPauseTimeScale();
        }

        public void Resume()
        {
            if (!_isActiveForCurrentMode)
            {
                return;
            }

            _isPaused = false;
            ApplySpeed(_activeSpeed);
        }

        public void TogglePause()
        {
            if (_isPaused)
            {
                Resume();
            }
            else
            {
                Pause();
            }
        }

        public bool StepOnce()
        {
            if (!_isActiveForCurrentMode || !_isPaused)
            {
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

            return _episodeController.StepEpisodeOnce();
        }

        public void ResetSpeed()
        {
            _activeSpeed = Mathf.Max(0.01f, _defaultSpeed);
            _isPaused = false;

            if (_isActiveForCurrentMode)
            {
                ApplySpeed(_activeSpeed);
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
                return ConvertEditorInputBackendValue(value);
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

        private void ApplySpeed(float speed)
        {
            float clamped = Mathf.Max(0.01f, speed);
            Time.timeScale = clamped;
            Time.fixedDeltaTime = _baseFixedDeltaTime * clamped;
        }

        private void ApplyPauseTimeScale()
        {
            Time.timeScale = 0f;
            Time.fixedDeltaTime = _baseFixedDeltaTime * 0.01f;
        }

        private void RestoreTimeDefaults()
        {
            Time.timeScale = 1f;
            Time.fixedDeltaTime = _baseFixedDeltaTime;
        }

        private void RefreshInputDiagnostics()
        {
#if ENABLE_INPUT_SYSTEM
            _keyboardCurrentExists = Keyboard.current != null;
#else
            _keyboardCurrentExists = false;
#endif
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
            string speedLabel = _isPaused ? "0.00x" : _activeSpeed.ToString("0.00") + "x";
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
            GUILayout.Label("Base timeScale@Awake: " + _baseTimeScale.ToString("0.00"));
            GUILayout.Label("Current timeScale: " + Time.timeScale.ToString("0.00"));
            GUILayout.Label("Current fixedDeltaTime: " + Time.fixedDeltaTime.ToString("0.0000"));
            GUILayout.Label("Game speed: " + speedLabel);
            GUILayout.Label("Paused: " + _isPaused);
            GUILayout.Label("Controls: Space pause/resume, 1/2/3/4 speed, N step (paused only)");
            GUILayout.Space(6f);

            GUILayout.BeginHorizontal();
            if (GUILayout.Button("1x", GUILayout.Height(28f)))
            {
                _lastHotkey = "mouse:1x";
                _lastInputSource = "GUI";
                SetSpeed(1f);
            }

            if (GUILayout.Button("0.5x", GUILayout.Height(28f)))
            {
                _lastHotkey = "mouse:0.5x";
                _lastInputSource = "GUI";
                SetSpeed(_speedHalf);
            }

            if (GUILayout.Button("0.25x", GUILayout.Height(28f)))
            {
                _lastHotkey = "mouse:0.25x";
                _lastInputSource = "GUI";
                SetSpeed(_speedQuarter);
            }

            if (GUILayout.Button("0.1x", GUILayout.Height(28f)))
            {
                _lastHotkey = "mouse:0.1x";
                _lastInputSource = "GUI";
                SetSpeed(_speedTenth);
            }
            GUILayout.EndHorizontal();

            GUILayout.BeginHorizontal();
            if (GUILayout.Button(_isPaused ? "Resume" : "Pause", GUILayout.Height(28f)))
            {
                _lastHotkey = "mouse:pause";
                _lastInputSource = "GUI";
                TogglePause();
            }

            GUI.enabled = _isPaused;
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
