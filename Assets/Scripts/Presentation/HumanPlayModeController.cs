using RTS.Core;
using RTS.Gameplay;
using RTS.ML;
using RTS.MLAgents.Stage7B;
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

        [Header("AI Defaults")]
        [SerializeField] private Week6PlayerControlMode _preferredAiMode = Week6PlayerControlMode.StudentInference;
        [SerializeField] private Week6PlayerControlMode _fallbackAiMode = Week6PlayerControlMode.HeuristicBaseline;

        [Header("Menu")]
        [SerializeField] private bool _loadMenuSceneOnReturn = false;
        [SerializeField] private string _menuSceneName = "Bootstrap";

        [Header("Startup")]
        [SerializeField] private HumanPlayMode _initialMode = HumanPlayMode.AIvsAI;
        [SerializeField] private bool _autoStartOnEnable;

        [Header("Diagnostics")]
        [SerializeField] private bool _logDiagnostics = true;

        private HumanPlayModeState _state = new HumanPlayModeState(HumanPlayMode.AIvsAI, false, Owner.Neutral, "Not started");

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

            if (!_autoStartOnEnable)
            {
                return;
            }

            switch (_initialMode)
            {
                case HumanPlayMode.Player1vsAI:
                case HumanPlayMode.Player1vsScriptedOrHeuristic:
                    StartPlayer1VsAI();
                    break;
                case HumanPlayMode.AIvsPlayer2:
                    StartAIvsPlayer2();
                    break;
                default:
                    StartAIvsAI();
                    break;
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
            SetState(HumanPlayMode.AIvsAI, false, Owner.Neutral, "AI vs AI started.");
        }

        public void RestartMatch()
        {
            ResolveReferences();

            if (_episodeController != null)
            {
                HumanPlayCommandSourceDiagnostics.ResetHistory();
                _episodeController.ResetEpisode();
                SetState(_state.Mode, _state.HasHumanSide, _state.HumanSide, "Match restarted.");
                return;
            }

            if (_trainingBootstrap != null)
            {
                bool started = _trainingBootstrap.StartNewEpisode("human_play_restart", nameof(HumanPlayModeController) + ".RestartMatch");
                string diagnostics = started
                    ? "Match restarted through MlAgentsTrainingBootstrap."
                    : "MlAgentsTrainingBootstrap rejected restart request.";
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
            if (_logDiagnostics)
            {
                MatchPhase phaseAfter = _episodeController.GetMatchState().Phase;
                Debug.Log(
                    $"[HumanPlayModeController] StartHumanVsAi started mode={mode} humanSide={humanSide} "
                    + $"p1Mode={_episodeController.Player1DecisionMode} p2Mode={_episodeController.Player2DecisionMode} "
                    + $"matchPhaseAfterStart={phaseAfter}");
            }
            SetState(mode, true, humanSide, $"{mode} started. AI side mode: {aiMode}.");
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
        }

        private void EmitDiagnostic(string message)
        {
            if (_logDiagnostics)
            {
                Debug.Log("[HumanPlayModeController] " + message);
            }
        }

        private void SetState(HumanPlayMode mode, bool hasHumanSide, Owner humanSide, string diagnostics)
        {
            _state = new HumanPlayModeState(mode, hasHumanSide, humanSide, diagnostics);
            EmitDiagnostic(diagnostics);
            OnModeStateChanged?.Invoke(_state);
        }
    }
}
