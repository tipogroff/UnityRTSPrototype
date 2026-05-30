using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using RTS.MLAgents.Stage7B;
using UnityEngine;

namespace RTS.Presentation
{
    [DisallowMultipleComponent]
    public sealed class HumanPlayerController : MonoBehaviour
    {
        [Header("References")]
        [SerializeField] private HumanPlayModeController _modeController;
        [SerializeField] private PlayerSelectionController _selectionController;
        [SerializeField] private PlayerCommandController _commandController;
        [SerializeField] private MlAgentsTrainingBootstrap _trainingBootstrap;
        [SerializeField] private MatchManager _matchManager;

        [Header("Diagnostics")]
        [SerializeField] private bool _logDiagnostics = true;

        private bool _isHumanControlActive;
        private Owner _humanSide = Owner.Neutral;
        private bool _missingModeControllerWarned;

        public bool IsHumanControlActive => _isHumanControlActive;
        public Owner HumanSide => _humanSide;
        public UnitRuntime SelectedUnit => _selectionController != null ? _selectionController.SelectedUnit : null;
        public IReadOnlyList<UnitRuntime> SelectedUnits => _selectionController != null ? _selectionController.SelectedUnits : System.Array.Empty<UnitRuntime>();
        public string LastCommandStatus => _commandController != null ? _commandController.LastCommandStatus : "PlayerCommandController is missing.";
        public bool LastCommandAccepted => _commandController != null && _commandController.LastCommandAccepted;
        public string LastCommandRejectedReason => _commandController != null ? _commandController.LastCommandRejectedReason : "PlayerCommandController is missing.";

        private void Awake()
        {
            ResolveReferences();
            ApplyManualControlState(forceDisable: true);
        }

        private void OnEnable()
        {
            ResolveReferences();
            SubscribeModeController();
            RefreshActivationState();
        }

        private void OnDisable()
        {
            UnsubscribeModeController();
            ApplyManualControlState(forceDisable: true);
        }

        private void Update()
        {
            ResolveReferences();
            RefreshActivationState();
        }

        private void HandleModeStateChanged(HumanPlayModeState state)
        {
            _humanSide = state.HasHumanSide ? state.HumanSide : Owner.Neutral;
            ApplyHumanSideToControllers();
            RefreshActivationState();
        }

        private void RefreshActivationState()
        {
            if (_modeController == null)
            {
                if (!_missingModeControllerWarned)
                {
                    Warn("HumanPlayModeController is missing. Manual input remains disabled.");
                    _missingModeControllerWarned = true;
                }

                ApplyManualControlState(forceDisable: true);
                return;
            }

            bool hasHumanSide = _modeController.HasHumanSide;
            Owner candidateSide = hasHumanSide ? _modeController.HumanSide : Owner.Neutral;
            _humanSide = candidateSide;
            ApplyHumanSideToControllers();

            bool trainerControlled = IsTrainerControlledRuntime();
            bool matchRunning = _matchManager != null && _matchManager.Phase == MatchPhase.Running;
            bool canEnable = hasHumanSide && !trainerControlled && matchRunning;

            ApplyManualControlState(forceDisable: !canEnable);
        }

        private bool IsTrainerControlledRuntime()
        {
            if (_modeController != null && _modeController.IsTrainerControlled)
            {
                return true;
            }

            return _trainingBootstrap != null
                && _trainingBootstrap.RuntimeMode == Stage7BRuntimeMode.TrainerControlled;
        }

        private void ApplyManualControlState(bool forceDisable)
        {
            bool nextActive = !forceDisable;
            if (_isHumanControlActive == nextActive)
            {
                if (!nextActive)
                {
                    if (_selectionController != null)
                    {
                        _selectionController.SetManualInputEnabled(false);
                    }

                    if (_commandController != null)
                    {
                        _commandController.SetManualInputEnabled(false);
                    }
                }

                return;
            }

            _isHumanControlActive = nextActive;

            if (_selectionController != null)
            {
                _selectionController.SetManualInputEnabled(_isHumanControlActive);
                if (!_isHumanControlActive)
                {
                    _selectionController.ClearSelection();
                }
            }

            if (_commandController != null)
            {
                _commandController.SetManualInputEnabled(_isHumanControlActive);
            }

            if (_logDiagnostics)
            {
                string state = _isHumanControlActive ? "enabled" : "disabled";
                Debug.Log($"[HumanPlayerController] Human control {state}. Side={_humanSide}");
            }
        }

        private void ApplyHumanSideToControllers()
        {
            if (_selectionController != null)
            {
                _selectionController.SetHumanSide(_humanSide);
            }

            if (_commandController != null)
            {
                _commandController.SetHumanSide(_humanSide);
            }
        }

        private void ResolveReferences()
        {
            if (_modeController == null)
            {
                _modeController = FindFirstObjectByType<HumanPlayModeController>();
            }

            if (_selectionController == null)
            {
                _selectionController = FindFirstObjectByType<PlayerSelectionController>();
            }

            if (_commandController == null)
            {
                _commandController = FindFirstObjectByType<PlayerCommandController>();
            }

            if (_trainingBootstrap == null)
            {
                _trainingBootstrap = FindFirstObjectByType<MlAgentsTrainingBootstrap>();
            }

            if (_matchManager == null)
            {
                _matchManager = MatchManager.Instance;
                if (_matchManager == null)
                {
                    _matchManager = FindFirstObjectByType<MatchManager>();
                }
            }
        }

        private void SubscribeModeController()
        {
            if (_modeController == null)
            {
                return;
            }

            _modeController.OnModeStateChanged -= HandleModeStateChanged;
            _modeController.OnModeStateChanged += HandleModeStateChanged;

            _humanSide = _modeController.HasHumanSide ? _modeController.HumanSide : Owner.Neutral;
            ApplyHumanSideToControllers();
        }

        private void UnsubscribeModeController()
        {
            if (_modeController == null)
            {
                return;
            }

            _modeController.OnModeStateChanged -= HandleModeStateChanged;
        }

        private void Warn(string message)
        {
            if (_logDiagnostics)
            {
                Debug.LogWarning("[HumanPlayerController] " + message);
            }
        }
    }
}
