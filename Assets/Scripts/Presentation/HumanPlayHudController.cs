using RTS.Core;
using RTS.Gameplay;
using RTS.ML;
using RTS.MLAgents.Stage7B;
using UnityEngine;

namespace RTS.Presentation
{
    [DisallowMultipleComponent]
    public sealed class HumanPlayHudController : MonoBehaviour
    {
        [Header("References")]
        [SerializeField] private HumanPlayModeController _humanPlayModeController;
        [SerializeField] private HumanPlayerController _humanPlayerController;
        [SerializeField] private PlayerSelectionController _playerSelectionController;
        [SerializeField] private PlayerCommandController _playerCommandController;
        [SerializeField] private GameSpeedController _gameSpeedController;
        [SerializeField] private EpisodeController _episodeController;
        [SerializeField] private MatchManager _matchManager;
        [SerializeField] private UnitRegistry _unitRegistry;
        [SerializeField] private ResourceManager _resourceManager;
        [SerializeField] private MlAgentsTrainingBootstrap _trainingBootstrap;

        [Header("HUD")]
        [SerializeField] private bool _showHud = true;
        [SerializeField] private Vector2 _leftPanelPosition = new Vector2(10f, 120f);
        [SerializeField] private Vector2 _rightPanelPosition = new Vector2(500f, 120f);
        [SerializeField] private float _panelWidth = 460f;
        [SerializeField] private float _leftPanelHeight = 560f;
        [SerializeField] private float _rightPanelHeight = 560f;

        [Header("Refresh")]
        [SerializeField] private float _resolveIntervalSeconds = 1f;
        [SerializeField] private float _snapshotIntervalSeconds = 0.25f;

        private const float CommandDiagnosticsWindowSeconds = 5f;
        private float _nextResolveTime;
        private float _nextSnapshotTime;
        private string _hudStatus = "HUD initialized.";
        private bool _lastCommandAccepted;
        private int _player1Resource;
        private int _player2Resource;
        private int _player1AliveUnits = -1;
        private int _player2AliveUnits = -1;
        private bool _hasCachedCounts;
        private MatchManager _subscribedMatchManager;

        private void Awake()
        {
            ResolveReferences(force: true);
            SubscribeEvents();
            RefreshSnapshot(force: true);
        }

        private void OnEnable()
        {
            ResolveReferences(force: true);
            SubscribeEvents();
            RefreshSnapshot(force: true);
        }

        private void OnDisable()
        {
            UnsubscribeEvents();
        }

        private void Update()
        {
            if (Time.unscaledTime >= _nextResolveTime)
            {
                ResolveReferences(force: false);
                SubscribeEvents();
                _nextResolveTime = Time.unscaledTime + Mathf.Max(0.2f, _resolveIntervalSeconds);
            }

            if (Time.unscaledTime >= _nextSnapshotTime)
            {
                RefreshSnapshot(force: false);
                _nextSnapshotTime = Time.unscaledTime + Mathf.Max(0.1f, _snapshotIntervalSeconds);
            }
        }

        private void OnGUI()
        {
            if (!_showHud)
            {
                return;
            }

            Rect leftRect = new Rect(_leftPanelPosition.x, _leftPanelPosition.y, _panelWidth, _leftPanelHeight);
            Rect rightRect = new Rect(_rightPanelPosition.x, _rightPanelPosition.y, _panelWidth, _rightPanelHeight);

            DrawLeftPanel(leftRect);
            DrawRightPanel(rightRect);
        }

        private void DrawLeftPanel(Rect area)
        {
            GUILayout.BeginArea(area, GUI.skin.window);
            GUILayout.Label("HumanPlay-2 HUD: Demo / Match");
            GUILayout.Space(6f);

            DrawModeBlock();
            GUILayout.Space(8f);
            DrawMatchBlock();
            GUILayout.Space(8f);
            DrawResourcesBlock();
            GUILayout.Space(8f);
            DrawSpeedBlock();
            GUILayout.Space(8f);
            DrawModeButtons();

            GUILayout.EndArea();
        }

        private void DrawRightPanel(Rect area)
        {
            GUILayout.BeginArea(area, GUI.skin.window);
            GUILayout.Label("HumanPlay-2 HUD: Selection / Commands");
            GUILayout.Space(6f);

            DrawSelectedUnitBlock();
            GUILayout.Space(8f);
            DrawCommandBlock();
            GUILayout.Space(8f);
            DrawManualCommandButtons();
            GUILayout.Space(8f);

            GUILayout.Label("HUD Status: " + _hudStatus);

            GUILayout.EndArea();
        }

        private void DrawModeBlock()
        {
            GUILayout.Label("Mode");

            string mode = _humanPlayModeController != null ? _humanPlayModeController.CurrentMode.ToString() : "n/a";
            string hasHuman = _humanPlayModeController != null ? _humanPlayModeController.HasHumanSide.ToString() : "n/a";
            string humanSide = _humanPlayModeController != null ? _humanPlayModeController.HumanSide.ToString() : "n/a";
            string diagnostics = _humanPlayModeController != null ? _humanPlayModeController.LastDiagnostics : "Controller missing";
            HumanPlayCommandDiagnosticsSnapshot commandSnapshot = HumanPlayCommandSourceDiagnostics.GetSnapshot(CommandDiagnosticsWindowSeconds);

            bool trainerControlled = IsTrainerControlled();
            bool humanControlActive = _humanPlayerController != null && _humanPlayerController.IsHumanControlActive;

            GUILayout.Label("Current mode: " + mode);
            GUILayout.Label("Has human side: " + hasHuman);
            GUILayout.Label("Human side: " + humanSide);
            GUILayout.Label("Human control active: " + humanControlActive);
            GUILayout.Label("TrainerControlled runtime: " + trainerControlled);
            GUILayout.Label("Enable student match control: " + commandSnapshot.EnableStudentMatchControl);
            GUILayout.Label("P1 decision mode: " + commandSnapshot.Player1DecisionMode);
            GUILayout.Label("P2 decision mode: " + commandSnapshot.Player2DecisionMode);
            GUILayout.Label($"Player2 automatic cmds last {CommandDiagnosticsWindowSeconds:0}s: {commandSnapshot.Player2AutomaticCommandCount}");
            GUILayout.Label($"Player2 human cmds last {CommandDiagnosticsWindowSeconds:0}s: {commandSnapshot.Player2HumanCommandCount}");
            GUILayout.Label("Last Player2 command source: " + commandSnapshot.LastPlayer2CommandSource);
            GUILayout.Label("Mode diagnostics: " + diagnostics);

            if (trainerControlled)
            {
                GUILayout.Label("Human play is disabled in TrainerControlled mode.");
            }
        }

        private void DrawMatchBlock()
        {
            GUILayout.Label("Match");

            string phase = _matchManager != null ? _matchManager.Phase.ToString() : "n/a";
            string step = _matchManager != null ? _matchManager.Step.ToString() : "n/a";
            string episode = _episodeController != null ? _episodeController.EpisodeIndex.ToString() : "n/a";

            string winner = "n/a";
            string terminalReason = "n/a";

            if (_matchManager != null)
            {
                winner = _matchManager.Winner.ToString();
                terminalReason = _matchManager.EndReason.ToString();
            }

            if (_episodeController != null && _episodeController.LastTerminalReport.IsTerminal)
            {
                winner = _episodeController.LastTerminalReport.Winner.ToString();
                terminalReason = _episodeController.LastTerminalReport.TerminalReason + " / runtime=" + _episodeController.LastTerminalReport.RuntimeEndReason;
            }

            GUILayout.Label("Phase: " + phase);
            GUILayout.Label("Step: " + step);
            GUILayout.Label("Episode index: " + episode);
            GUILayout.Label("Winner: " + winner);
            GUILayout.Label("Terminal reason: " + terminalReason);
        }

        private void DrawResourcesBlock()
        {
            GUILayout.Label("Resources");
            GUILayout.Label("Player1 resources: " + _player1Resource);
            GUILayout.Label("Player2 resources: " + _player2Resource);

            if (_hasCachedCounts)
            {
                GUILayout.Label("Player1 alive units: " + _player1AliveUnits);
                GUILayout.Label("Player2 alive units: " + _player2AliveUnits);
            }
            else
            {
                GUILayout.Label("Alive unit counts: n/a");
            }

            string resourceManagerState = _resourceManager != null ? "available" : "n/a";
            GUILayout.Label("ResourceManager: " + resourceManagerState);
        }

        private void DrawSelectedUnitBlock()
        {
            GUILayout.Label("Selected Unit");

            UnitRuntime selected = GetSelectedUnit();
            if (selected == null)
            {
                GUILayout.Label("Selection: none");
                return;
            }

            GUILayout.Label("Owner: " + selected.Owner);
            GUILayout.Label("Type: " + selected.Type);
            GUILayout.Label("HP: " + selected.HP + "/" + selected.MaxHP);
            GUILayout.Label("Carried resources: " + selected.CarriedResources);
            GUILayout.Label("Grid position: " + selected.GridPos);
            GUILayout.Label("Alive: " + selected.IsAlive);
        }

        private void DrawCommandBlock()
        {
            GUILayout.Label("Command");

            string commandMode = _playerCommandController != null ? _playerCommandController.CurrentMode.ToString() : "n/a";
            string status = _humanPlayerController != null
                ? _humanPlayerController.LastCommandStatus
                : (_playerCommandController != null ? _playerCommandController.LastCommandStatus : "Controller missing");

            bool accepted = _humanPlayerController != null
                ? _humanPlayerController.LastCommandAccepted
                : (_playerCommandController != null && _playerCommandController.LastCommandAccepted);

            string rejectedReason = _humanPlayerController != null
                ? _humanPlayerController.LastCommandRejectedReason
                : (_playerCommandController != null ? _playerCommandController.LastCommandRejectedReason : "Controller missing");

            GUILayout.Label("HumanCommandMode: " + commandMode);
            GUILayout.Label("Last status: " + status);
            GUILayout.Label("Last accepted: " + accepted);
            GUILayout.Label("Last rejection reason: " + (string.IsNullOrWhiteSpace(rejectedReason) ? "n/a" : rejectedReason));
        }

        private void DrawSpeedBlock()
        {
            GUILayout.Label("Speed");
            if (_gameSpeedController == null)
            {
                GUILayout.Label("GameSpeedController: Controller missing");
                return;
            }

            GUILayout.Label("Paused: " + _gameSpeedController.IsPaused);
            GUILayout.Label("Current speed: " + _gameSpeedController.CurrentSpeed.ToString("0.00"));

            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Pause/Resume"))
            {
                InvokeSafe(() => _gameSpeedController.TogglePause(), "Speed toggled.", "GameSpeedController missing");
            }

            if (GUILayout.Button("Step"))
            {
                bool stepped = _gameSpeedController.StepOnce();
                _hudStatus = stepped ? "Step executed." : "Step skipped (pause required or controller missing).";
            }
            GUILayout.EndHorizontal();

            GUILayout.BeginHorizontal();
            if (GUILayout.Button("1x"))
            {
                InvokeSafe(() => _gameSpeedController.SetSpeed(1f), "Speed set to 1x.", "GameSpeedController missing");
            }
            if (GUILayout.Button("0.5x"))
            {
                InvokeSafe(() => _gameSpeedController.SetSpeed(0.5f), "Speed set to 0.5x.", "GameSpeedController missing");
            }
            if (GUILayout.Button("0.25x"))
            {
                InvokeSafe(() => _gameSpeedController.SetSpeed(0.25f), "Speed set to 0.25x.", "GameSpeedController missing");
            }
            if (GUILayout.Button("0.1x"))
            {
                InvokeSafe(() => _gameSpeedController.SetSpeed(0.1f), "Speed set to 0.1x.", "GameSpeedController missing");
            }
            GUILayout.EndHorizontal();
        }

        private void DrawModeButtons()
        {
            GUILayout.Label("Mode / Menu");

            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Start Player1 vs AI"))
            {
                InvokeSafe(() => _humanPlayModeController.StartPlayer1VsAI(), "Started Player1 vs AI.", "HumanPlayModeController missing");
            }

            if (GUILayout.Button("Start AI vs Player2"))
            {
                InvokeSafe(() => _humanPlayModeController.StartAIvsPlayer2(), "Started AI vs Player2.", "HumanPlayModeController missing");
            }
            GUILayout.EndHorizontal();

            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Start AI vs AI"))
            {
                InvokeSafe(() => _humanPlayModeController.StartAIvsAI(), "Started AI vs AI.", "HumanPlayModeController missing");
            }

            if (GUILayout.Button("Restart"))
            {
                InvokeSafe(() => _humanPlayModeController.RestartMatch(), "Restart requested.", "HumanPlayModeController missing");
            }
            GUILayout.EndHorizontal();

            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Return to Menu"))
            {
                InvokeSafe(() => _humanPlayModeController.ReturnToMenu(), "Return-to-menu requested.", "HumanPlayModeController missing");
            }

            if (GUILayout.Button("Quit"))
            {
                InvokeSafe(() => _humanPlayModeController.QuitApplication(), "Quit requested.", "HumanPlayModeController missing");
            }
            GUILayout.EndHorizontal();
        }

        private void DrawManualCommandButtons()
        {
            GUILayout.Label("Manual Commands");

            bool canManualUse = CanUseManualCommands(out string disabledReason);
            bool hasSelection = GetSelectedUnit() != null;
            bool canUseSelectionCommands = canManualUse && hasSelection;

            GUI.enabled = canUseSelectionCommands;
            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Move"))
            {
                InvokeSafe(() => _playerCommandController.BeginMoveCommandMode(), "Move mode enabled.", "PlayerCommandController missing");
            }

            if (GUILayout.Button("Attack"))
            {
                InvokeSafe(() => _playerCommandController.BeginAttackCommandMode(), "Attack mode enabled.", "PlayerCommandController missing");
            }
            GUILayout.EndHorizontal();

            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Harvest"))
            {
                InvokeSafe(() => _playerCommandController.TryHarvestSelected(), "Harvest requested.", "PlayerCommandController missing");
            }

            if (GUILayout.Button("Return"))
            {
                InvokeSafe(() => _playerCommandController.TryReturnSelected(), "Return requested.", "PlayerCommandController missing");
            }
            GUILayout.EndHorizontal();

            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Produce Worker"))
            {
                InvokeSafe(() => _playerCommandController.TryProduceWorker(), "Produce Worker requested.", "PlayerCommandController missing");
            }

            if (GUILayout.Button("Build Barracks"))
            {
                InvokeSafe(() => _playerCommandController.TryBuildBarracks(), "Build Barracks requested.", "PlayerCommandController missing");
            }
            GUILayout.EndHorizontal();

            GUILayout.BeginHorizontal();
            if (GUILayout.Button("Produce Light"))
            {
                InvokeSafe(() => _playerCommandController.TryProduceLight(), "Produce Light requested.", "PlayerCommandController missing");
            }

            if (GUILayout.Button("Produce Heavy"))
            {
                InvokeSafe(() => _playerCommandController.TryProduceHeavy(), "Produce Heavy requested.", "PlayerCommandController missing");
            }

            if (GUILayout.Button("Produce Ranged"))
            {
                InvokeSafe(() => _playerCommandController.TryProduceRanged(), "Produce Ranged requested.", "PlayerCommandController missing");
            }
            GUILayout.EndHorizontal();
            GUI.enabled = true;

            if (!canManualUse)
            {
                GUILayout.Label("Manual commands unavailable: " + disabledReason);
            }
            else if (!hasSelection)
            {
                GUILayout.Label("Manual commands require selected unit.");
            }
        }

        private bool CanUseManualCommands(out string reason)
        {
            if (_playerCommandController == null)
            {
                reason = "PlayerCommandController missing";
                return false;
            }

            if (_humanPlayerController == null)
            {
                reason = "HumanPlayerController missing";
                return false;
            }

            if (IsTrainerControlled())
            {
                reason = "TrainerControlled mode";
                return false;
            }

            if (!_humanPlayerController.IsHumanControlActive)
            {
                reason = "Human control is inactive";
                return false;
            }

            if (_matchManager == null || _matchManager.Phase != MatchPhase.Running)
            {
                reason = "Match not running";
                return false;
            }

            reason = string.Empty;
            return true;
        }

        private UnitRuntime GetSelectedUnit()
        {
            if (_humanPlayerController != null && _humanPlayerController.SelectedUnit != null)
            {
                return _humanPlayerController.SelectedUnit;
            }

            return _playerSelectionController != null ? _playerSelectionController.SelectedUnit : null;
        }

        private bool IsTrainerControlled()
        {
            if (_humanPlayModeController != null && _humanPlayModeController.IsTrainerControlled)
            {
                return true;
            }

            return _trainingBootstrap != null && _trainingBootstrap.RuntimeMode == Stage7BRuntimeMode.TrainerControlled;
        }

        private void RefreshSnapshot(bool force)
        {
            if (!force && _matchManager == null && _unitRegistry == null)
            {
                return;
            }

            if (_matchManager != null)
            {
                _player1Resource = _matchManager.GetResources(Owner.Player1);
                _player2Resource = _matchManager.GetResources(Owner.Player2);
            }

            if (_unitRegistry != null)
            {
                _player1AliveUnits = CountAliveUnits(Owner.Player1);
                _player2AliveUnits = CountAliveUnits(Owner.Player2);
                _hasCachedCounts = true;
            }
            else
            {
                _hasCachedCounts = false;
            }
        }

        private int CountAliveUnits(Owner owner)
        {
            if (_unitRegistry == null)
            {
                return -1;
            }

            int count = 0;
            var units = _unitRegistry.GetUnitsByOwner(owner);
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit != null && unit.IsAlive)
                {
                    count++;
                }
            }

            return count;
        }

        private void ResolveReferences(bool force)
        {
            if (force || _humanPlayModeController == null)
            {
                _humanPlayModeController = FindFirstObjectByType<HumanPlayModeController>();
            }

            if (force || _humanPlayerController == null)
            {
                _humanPlayerController = FindFirstObjectByType<HumanPlayerController>();
            }

            if (force || _playerSelectionController == null)
            {
                _playerSelectionController = FindFirstObjectByType<PlayerSelectionController>();
            }

            if (force || _playerCommandController == null)
            {
                _playerCommandController = FindFirstObjectByType<PlayerCommandController>();
            }

            if (force || _gameSpeedController == null)
            {
                _gameSpeedController = FindFirstObjectByType<GameSpeedController>();
            }

            if (force || _episodeController == null)
            {
                _episodeController = EpisodeController.Instance;
                if (_episodeController == null)
                {
                    _episodeController = FindFirstObjectByType<EpisodeController>();
                }
            }

            if (force || _matchManager == null)
            {
                _matchManager = MatchManager.Instance;
                if (_matchManager == null)
                {
                    _matchManager = FindFirstObjectByType<MatchManager>();
                }
            }

            if (force || _unitRegistry == null)
            {
                _unitRegistry = UnitRegistry.Instance;
                if (_unitRegistry == null)
                {
                    _unitRegistry = FindFirstObjectByType<UnitRegistry>();
                }
            }

            if (force || _resourceManager == null)
            {
                _resourceManager = ResourceManager.Instance;
                if (_resourceManager == null)
                {
                    _resourceManager = FindFirstObjectByType<ResourceManager>();
                }
            }

            if (force || _trainingBootstrap == null)
            {
                _trainingBootstrap = FindFirstObjectByType<MlAgentsTrainingBootstrap>();
            }
        }

        private void SubscribeEvents()
        {
            if (_subscribedMatchManager != null && _subscribedMatchManager != _matchManager)
            {
                _subscribedMatchManager.OnCommandAccepted -= HandleCommandAccepted;
                _subscribedMatchManager.OnCommandRejectedDetailed -= HandleCommandRejectedDetailed;
                _subscribedMatchManager = null;
            }

            if (_playerCommandController != null)
            {
                _playerCommandController.OnCommandStatusChanged -= HandleCommandStatusChanged;
                _playerCommandController.OnCommandStatusChanged += HandleCommandStatusChanged;
            }

            if (_playerSelectionController != null)
            {
                _playerSelectionController.OnSelectionChanged -= HandleSelectionChanged;
                _playerSelectionController.OnSelectionChanged += HandleSelectionChanged;
            }

            if (_matchManager != null)
            {
                _matchManager.OnCommandAccepted -= HandleCommandAccepted;
                _matchManager.OnCommandAccepted += HandleCommandAccepted;
                _matchManager.OnCommandRejectedDetailed -= HandleCommandRejectedDetailed;
                _matchManager.OnCommandRejectedDetailed += HandleCommandRejectedDetailed;
                _subscribedMatchManager = _matchManager;
            }
        }

        private void UnsubscribeEvents()
        {
            if (_subscribedMatchManager != null)
            {
                _subscribedMatchManager.OnCommandAccepted -= HandleCommandAccepted;
                _subscribedMatchManager.OnCommandRejectedDetailed -= HandleCommandRejectedDetailed;
                _subscribedMatchManager = null;
            }

            if (_playerCommandController != null)
            {
                _playerCommandController.OnCommandStatusChanged -= HandleCommandStatusChanged;
            }

            if (_playerSelectionController != null)
            {
                _playerSelectionController.OnSelectionChanged -= HandleSelectionChanged;
            }
        }

        private void HandleCommandStatusChanged(string status, bool accepted)
        {
            _hudStatus = string.IsNullOrWhiteSpace(status) ? "Command status updated." : status;
            _lastCommandAccepted = accepted;
        }

        private void HandleSelectionChanged(UnitRuntime unit)
        {
            _hudStatus = unit == null
                ? "Selection cleared."
                : $"Selected: {unit.Owner} {unit.Type} at {unit.GridPos}";
        }

        private void HandleCommandAccepted(MatchCommand command)
        {
            HumanPlayCommandSourceDiagnostics.RecordCommand(command, accepted: true, rejectionReason: string.Empty);
        }

        private void HandleCommandRejectedDetailed(MatchCommand command, string reason, MatchCommandRejectionDiagnostics diagnostics)
        {
            HumanPlayCommandSourceDiagnostics.RecordCommand(command, accepted: false, rejectionReason: reason);
        }

        private void InvokeSafe(System.Action action, string successMessage, string missingMessage)
        {
            if (action == null)
            {
                _hudStatus = missingMessage;
                _lastCommandAccepted = false;
                return;
            }

            try
            {
                action();
                _hudStatus = successMessage;
                _lastCommandAccepted = true;
            }
            catch (System.Exception ex)
            {
                _hudStatus = "Action failed: " + ex.Message;
                _lastCommandAccepted = false;
            }
        }
    }
}
