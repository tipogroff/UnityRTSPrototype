using System.Collections;
using System.Reflection;
using RTS.Core;
using RTS.Gameplay;
using RTS.ML;
using RTS.MLAgents.Stage7B;
using RTS.Presentation.CameraControls;
using RTS.Presentation.UI;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RTS.Presentation
{
    [DisallowMultipleComponent]
    public sealed class HumanPlayModeController : MonoBehaviour
    {
        [Header("References")]
        [SerializeField] private EpisodeController _episodeController;
        [SerializeField] private MlAgentsTrainingBootstrap _trainingBootstrap;
        [SerializeField] private RtsCameraController _cameraController;

        [Header("AI Defaults")]
        [SerializeField] private Week6PlayerControlMode _preferredAiMode = Week6PlayerControlMode.StudentInference;
        [SerializeField] private Week6PlayerControlMode _fallbackAiMode = Week6PlayerControlMode.HeuristicBaseline;

        [Header("Menu")]
        [SerializeField] private bool _loadMenuSceneOnReturn = false;
        [SerializeField] private string _menuSceneName = "Bootstrap";
        [SerializeField] private bool _redirectToMainMenuWhenNoLaunchMode = true;

        [Header("Startup")]
        [SerializeField] private HumanPlayMode _initialMode = HumanPlayMode.AIvsAI;
        [SerializeField] private bool _autoStartOnEnable;
        [SerializeField] private float _autoStartRuntimeReadyTimeoutSeconds = 5f;

        [Header("Diagnostics")]
        [SerializeField] private bool _logDiagnostics = true;

        private HumanPlayModeState _state = new HumanPlayModeState(HumanPlayMode.AIvsAI, false, Owner.Neutral, "Not started");
        private Coroutine _startupCoroutine;
        private bool _initialAutoStartCompleted;

        public HumanPlayMode CurrentMode => _state.Mode;
        public bool HasHumanSide => _state.HasHumanSide;
        public Owner HumanSide => _state.HumanSide;
        public string LastDiagnostics => _state.Diagnostics;
        public bool IsTrainerControlled => _trainingBootstrap != null && _trainingBootstrap.RuntimeMode == Stage7BRuntimeMode.TrainerControlled;

        public event System.Action<HumanPlayModeState> OnModeStateChanged;

        private void Awake()
        {
            ResolveReferences();
        }

        private void OnEnable()
        {
            ResolveReferences();
            LogStartupDiagnostics("OnEnable");
            BeginInitialAutoStartIfNeeded();
        }

        private void Start()
        {
            ResolveReferences();
            LogStartupDiagnostics("Start");
            BeginInitialAutoStartIfNeeded();
        }

        private void BeginInitialAutoStartIfNeeded()
        {
            if (!_autoStartOnEnable)
            {
                return;
            }

            if (_initialAutoStartCompleted || _startupCoroutine != null)
            {
                return;
            }

            _startupCoroutine = StartCoroutine(StartInitialModeWhenRuntimeReady());
        }

        private void OnDisable()
        {
            if (_startupCoroutine != null)
            {
                StopCoroutine(_startupCoroutine);
                _startupCoroutine = null;
            }
        }

        public void StartPlayer1VsAI()
        {
            StartHumanVsAi(Owner.Player1, HumanPlayMode.Player1vsAI);
        }

        public void StartAIvsPlayer2()
        {
            EmitDiagnostic("StartAIvsPlayer2 invoked.");
            StartHumanVsAi(Owner.Player2, HumanPlayMode.AIvsPlayer2);
        }

        public void StartAIvsAI()
        {
            ResolveReferences();

            if (_episodeController == null)
            {
                SetState(HumanPlayMode.AIvsAI, false, Owner.Neutral, "EpisodeController is missing. AI mode was not started.");
                return;
            }

            _episodeController.ConfigureWeek6PlayerControlModes(
                enableStudentMatchControl: false,
                player1Mode: Week6PlayerControlMode.Idle,
                player2Mode: Week6PlayerControlMode.Idle);

            HumanPlayCommandSourceDiagnostics.ResetHistory();
            _episodeController.StartNewEpisode();
            FocusCameraForMode(HumanPlayMode.AIvsAI, Owner.Neutral);
            SetState(HumanPlayMode.AIvsAI, false, Owner.Neutral, "AI vs AI started.");
        }

        public void StartAIvsBot()
        {
            ResolveReferences();

            if (IsTrainerControlled)
            {
                SetState(HumanPlayMode.AIvsBot, false, Owner.Neutral, "AI vs Bot mode is disabled in TrainerControlled runtime mode.");
                return;
            }

            if (_episodeController == null)
            {
                SetState(HumanPlayMode.AIvsBot, false, Owner.Neutral, "EpisodeController is missing. AI vs Bot mode was not started.");
                return;
            }

            Week6PlayerControlMode aiMode = ResolveAiControlMode();
            if (aiMode == Week6PlayerControlMode.StudentInference)
            {
                _episodeController.ConfigureWeek6PlayerControlModes(
                    enableStudentMatchControl: true,
                    player1Mode: Week6PlayerControlMode.StudentInference,
                    player2Mode: Week6PlayerControlMode.HeuristicBaseline);
            }
            else
            {
                _episodeController.ConfigureWeek6PlayerControlModes(
                    enableStudentMatchControl: false,
                    player1Mode: Week6PlayerControlMode.Idle,
                    player2Mode: Week6PlayerControlMode.Idle);
            }

            HumanPlayCommandSourceDiagnostics.ResetHistory();
            _episodeController.StartNewEpisode();
            FocusCameraForMode(HumanPlayMode.AIvsBot, Owner.Neutral);
            SetState(HumanPlayMode.AIvsBot, false, Owner.Neutral, $"AI vs Bot started. Player1 AI mode: {aiMode}.");
        }

        public void RestartMatch()
        {
            ResolveReferences();

            if (_state.Mode == HumanPlayMode.AIvsPlayer2)
            {
                StartAIvsPlayer2();
                return;
            }

            if (_state.Mode == HumanPlayMode.Player1vsAI || _state.Mode == HumanPlayMode.Player1vsScriptedOrHeuristic)
            {
                StartPlayer1VsAI();
                return;
            }

            if (_state.Mode == HumanPlayMode.AIvsBot)
            {
                StartAIvsBot();
                return;
            }

            if (_episodeController != null)
            {
                HumanPlayCommandSourceDiagnostics.ResetHistory();
                _episodeController.ResetEpisode();
                FocusCameraForMode(_state.Mode, _state.HumanSide);
                SetState(_state.Mode, _state.HasHumanSide, _state.HumanSide, "Match restarted.");
                return;
            }

            if (_trainingBootstrap != null)
            {
                bool started = _trainingBootstrap.StartNewEpisode("human_play_restart", nameof(HumanPlayModeController) + ".RestartMatch");
                string diagnostics = started
                    ? "Match restarted through MlAgentsTrainingBootstrap."
                    : "MlAgentsTrainingBootstrap rejected restart request.";
                if (started)
                {
                    FocusCameraForMode(_state.Mode, _state.HumanSide);
                }

                SetState(_state.Mode, _state.HasHumanSide, _state.HumanSide, diagnostics);
                return;
            }

            SetState(_state.Mode, _state.HasHumanSide, _state.HumanSide, "No runtime controller found for restart.");
        }

        public void ReturnToMenu()
        {
            if (_loadMenuSceneOnReturn && !string.IsNullOrWhiteSpace(_menuSceneName))
            {
                SceneManager.LoadScene(_menuSceneName);
                return;
            }

            SetState(HumanPlayMode.PausedDemo, false, Owner.Neutral, "ReturnToMenu requested but scene loading is disabled.");
        }

        public void QuitApplication()
        {
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#else
            Application.Quit();
#endif
        }

        private void StartHumanVsAi(Owner humanSide, HumanPlayMode mode)
        {
            ResolveReferences();
            LogStartupDiagnostics("StartHumanVsAi.before_configure");

            if (IsTrainerControlled)
            {
                SetState(mode, false, Owner.Neutral, "Human play mode is disabled in TrainerControlled runtime mode.");
                return;
            }

            if (_episodeController == null)
            {
                SetState(mode, false, Owner.Neutral, "EpisodeController is missing. Human mode was not started.");
                return;
            }

            Week6PlayerControlMode aiMode = ResolveAiControlMode();
            Week6PlayerControlMode p1ModeBefore = _episodeController.Player1DecisionMode;
            Week6PlayerControlMode p2ModeBefore = _episodeController.Player2DecisionMode;
            MatchPhase phaseBefore = _episodeController.GetMatchState().Phase;
            Week6PlayerControlMode p1Mode = humanSide == Owner.Player1 ? Week6PlayerControlMode.Idle : aiMode;
            Week6PlayerControlMode p2Mode = humanSide == Owner.Player2 ? Week6PlayerControlMode.Idle : aiMode;

            _episodeController.ConfigureWeek6PlayerControlModes(
                enableStudentMatchControl: true,
                player1Mode: p1Mode,
                player2Mode: p2Mode);

            HumanPlayCommandSourceDiagnostics.ResetHistory();
            if (_logDiagnostics)
            {
                Debug.Log(
                    $"[HumanPlayModeController] StartHumanVsAi invoked mode={mode} humanSide={humanSide} resolvedAiMode={aiMode} "
                    + $"p1ModeBefore={p1ModeBefore} p2ModeBefore={p2ModeBefore} "
                    + $"p1ModeAfterConfigure={_episodeController.Player1DecisionMode} p2ModeAfterConfigure={_episodeController.Player2DecisionMode} "
                    + $"enableStudentMatchControl={_episodeController.EnableWeek6StudentMatchControl} "
                    + $"episodeControllerId={_episodeController.GetInstanceID()} matchPhaseBeforeStart={phaseBefore}");
            }

            _episodeController.StartNewEpisode();
            FocusCameraForMode(mode, humanSide);
            if (_logDiagnostics)
            {
                MatchPhase phaseAfter = _episodeController.GetMatchState().Phase;
                Debug.Log(
                    $"[HumanPlayModeController] StartHumanVsAi started mode={mode} humanSide={humanSide} "
                    + $"p1Mode={_episodeController.Player1DecisionMode} p2Mode={_episodeController.Player2DecisionMode} "
                    + $"matchPhaseAfterStart={phaseAfter}");
            }
            LogStartupDiagnostics("StartHumanVsAi.after_start");
            SetState(mode, true, humanSide, $"{mode} started. AI side mode: {aiMode}.");
        }

        private IEnumerator StartInitialModeWhenRuntimeReady()
        {
            if (_initialAutoStartCompleted)
            {
                yield break;
            }

            if (!DemoLaunchOptions.HasExplicitMode)
            {
                HandleMissingLaunchMode();
                yield break;
            }

            float timeout = Mathf.Max(0.25f, _autoStartRuntimeReadyTimeoutSeconds);
            float start = Time.realtimeSinceStartup;
            while (!AreRuntimeServicesReady(out string missing))
            {
                if (Time.realtimeSinceStartup - start >= timeout)
                {
                    SetState(_initialMode, false, Owner.Neutral, "Initial auto-start skipped; runtime services missing: " + missing);
                    _startupCoroutine = null;
                    yield break;
                }

                yield return null;
            }

            _initialAutoStartCompleted = true;
            LogStartupDiagnostics("InitialAutoStart.ready");

            DemoLaunchMode requestedMode = DemoLaunchOptions.RequestedMode;
            DemoLaunchOptions.Clear();
            StartRequestedDemoMode(requestedMode);

            _startupCoroutine = null;
        }

        private void HandleMissingLaunchMode()
        {
            _initialAutoStartCompleted = true;
            _startupCoroutine = null;

            if (_redirectToMainMenuWhenNoLaunchMode
                && !string.IsNullOrWhiteSpace(_menuSceneName)
                && SceneManager.GetActiveScene().name != _menuSceneName)
            {
                EmitDiagnostic("No explicit demo launch mode. Redirecting to main menu.");
                Time.timeScale = 1f;
                SceneManager.LoadScene(_menuSceneName);
                return;
            }

            SetState(HumanPlayMode.PausedDemo, false, Owner.Neutral, "No explicit demo launch mode. Demo remains idle.");
        }

        private void StartRequestedDemoMode(DemoLaunchMode requestedMode)
        {
            switch (requestedMode)
            {
                case DemoLaunchMode.AIvsAI:
                    StartAIvsAI();
                    break;
                case DemoLaunchMode.AIvsBot:
                    StartAIvsBot();
                    break;
                default:
                    StartAIvsPlayer2();
                    break;
            }
        }

        private bool AreRuntimeServicesReady(out string missing)
        {
            ResolveReferences();

            System.Text.StringBuilder builder = new System.Text.StringBuilder();
            if (_episodeController == null)
            {
                builder.Append("EpisodeController ");
            }

            if (MatchManager.Instance == null && FindFirstObjectByType<MatchManager>() == null)
            {
                builder.Append("MatchManager ");
            }

            if (MatchBootstrap.Instance == null && FindFirstObjectByType<MatchBootstrap>() == null)
            {
                builder.Append("MatchBootstrap ");
            }

            if (GridManager.Instance == null && FindFirstObjectByType<GridManager>() == null)
            {
                builder.Append("GridManager ");
            }

            missing = builder.ToString().Trim();
            return string.IsNullOrEmpty(missing);
        }

        private Week6PlayerControlMode ResolveAiControlMode()
        {
            Week6PlayerControlMode resolved = _preferredAiMode;
            if (resolved == Week6PlayerControlMode.StudentInference && FindFirstObjectByType<Week6StudentPolicyAdapter>() == null)
            {
                resolved = _fallbackAiMode;
                EmitDiagnostic("StudentInference adapter is missing. Falling back to " + resolved + ".");
            }

            if (resolved == Week6PlayerControlMode.HeuristicBaseline && FindFirstObjectByType<HeuristicPolicyAdapter>() == null)
            {
                EmitDiagnostic("HeuristicPolicyAdapter is missing. Falling back to Idle.");
                resolved = Week6PlayerControlMode.Idle;
            }

            return resolved;
        }

        private void ResolveReferences()
        {
            if (_episodeController == null)
            {
                _episodeController = EpisodeController.Instance;
                if (_episodeController == null)
                {
                    _episodeController = FindFirstObjectByType<EpisodeController>();
                }
            }

            if (_trainingBootstrap == null)
            {
                _trainingBootstrap = FindFirstObjectByType<MlAgentsTrainingBootstrap>();
            }

            if (_cameraController == null)
            {
                _cameraController = FindFirstObjectByType<RtsCameraController>();
            }
        }

        private void FocusCameraForMode(HumanPlayMode mode, Owner humanSide)
        {
            if (_cameraController == null)
            {
                ResolveReferences();
            }

            if (_cameraController == null)
            {
                EmitDiagnostic("RtsCameraController is missing. Match start camera focus skipped.");
                return;
            }

            switch (mode)
            {
                case HumanPlayMode.AIvsPlayer2:
                    _cameraController.FocusOnOwnerAfterMatchStart(Owner.Player2);
                    break;
                case HumanPlayMode.AIvsBot:
                case HumanPlayMode.AIvsAI:
                    _cameraController.FocusOnOwnerAfterMatchStart(Owner.Player1);
                    break;
                default:
                    _cameraController.FocusOnOwnerAfterMatchStart(humanSide);
                    break;
            }
        }

        private void EmitDiagnostic(string message)
        {
            if (_logDiagnostics)
            {
                Debug.Log("[HumanPlayModeController] " + message);
            }
        }

        private void LogStartupDiagnostics(string context)
        {
            if (!_logDiagnostics)
            {
                return;
            }

            ResolveReferences();
            bool bootstrapAutoStart = ReadPrivateBool(_trainingBootstrap, "_autoStartEpisodeOnStart");
            bool bootstrapStepScripted = ReadPrivateBool(_trainingBootstrap, "_stepScriptedOpponent");
            bool episodeAutoStart = ReadPrivateBool(_episodeController, "_autoStartOnPlay");
            bool demoOrchestratorEnabled = IsAnyEnabledComponentType("RTS.MLAgents.Stage7B.TeacherReplay.Stage7BTeacherReplayDemoOrchestrator");
            bool scriptedOpponentEnabled = IsAnyEnabledComponentType("RTS.ML.HeuristicPolicyAdapter")
                || IsAnyEnabledComponentType("RTS.MLAgents.Stage7B.Week7ScriptedOpponentPacing");
            string p1 = _episodeController != null ? _episodeController.Player1DecisionMode.ToString() : "n/a";
            string p2 = _episodeController != null ? _episodeController.Player2DecisionMode.ToString() : "n/a";
            bool control = _episodeController != null && _episodeController.EnableWeek6StudentMatchControl;

            Debug.Log(
                $"[HumanPlayModeController][Startup] context={context} "
                + $"bootstrapAutoStart={bootstrapAutoStart} episodeAutoStart={episodeAutoStart} "
                + $"initialMode={_initialMode} autoStartOnEnable={_autoStartOnEnable} "
                + $"p1DecisionMode={p1} p2DecisionMode={p2} enableStudentMatchControl={control} "
                + $"humanSide={_state.HumanSide} hasHumanSide={_state.HasHumanSide} "
                + $"stage7BDemoOrchestratorEnabled={demoOrchestratorEnabled} "
                + $"scriptedOpponentComponentEnabled={scriptedOpponentEnabled} "
                + $"bootstrapStepScriptedOpponent={bootstrapStepScripted}");
        }

        private static bool ReadPrivateBool(object target, string fieldName)
        {
            if (target == null)
            {
                return false;
            }

            FieldInfo field = target.GetType().GetField(fieldName, BindingFlags.Instance | BindingFlags.NonPublic);
            return field != null && field.FieldType == typeof(bool) && (bool)field.GetValue(target);
        }

        private static bool IsAnyEnabledComponentType(string fullTypeName)
        {
            MonoBehaviour[] behaviours = FindObjectsByType<MonoBehaviour>(FindObjectsInactive.Include, FindObjectsSortMode.None);
            for (int i = 0; i < behaviours.Length; i++)
            {
                MonoBehaviour behaviour = behaviours[i];
                if (behaviour == null)
                {
                    continue;
                }

                if (behaviour.GetType().FullName == fullTypeName && behaviour.enabled)
                {
                    return true;
                }
            }

            return false;
        }

        private void SetState(HumanPlayMode mode, bool hasHumanSide, Owner humanSide, string diagnostics)
        {
            _state = new HumanPlayModeState(mode, hasHumanSide, humanSide, diagnostics);
            EmitDiagnostic(diagnostics);
            OnModeStateChanged?.Invoke(_state);
        }
    }
}
