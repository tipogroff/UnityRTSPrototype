// EpisodeController.cs — episode lifecycle and reset orchestration.

using System.Collections.Generic;
using UnityEngine;
using RTS.Core;
using RTS.Logging;

namespace RTS.Gameplay
{
    [DisallowMultipleComponent]
    public class EpisodeController : MonoBehaviour
    {
        public static EpisodeController Instance { get; private set; }

        [Header("Scene references")]
        [SerializeField] private MatchManager _matchManager;
        [SerializeField] private MatchBootstrap _matchBootstrap;
        [SerializeField] private GridManager _gridManager;
        [SerializeField] private UnitRegistry _unitRegistry;
        [SerializeField] private ResourceManager _resourceManager;
        [SerializeField] private ExperimentLogger _experimentLogger;

        [Header("Runtime")]
        [SerializeField] private bool _autoStartOnPlay = true;
        [SerializeField] private bool _autoStepInFixedUpdate = true;
        [SerializeField] private bool _logLifecycleEvents;

        private bool _episodeRunning;
        private bool _episodeFinalized;

        public int EpisodeIndex { get; private set; }
        public bool IsRunning => _episodeRunning && _matchManager != null && _matchManager.Phase == MatchPhase.Running;

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }

            Instance = this;
            ResolveReferences();
        }

        private void OnEnable()
        {
            ResolveReferences();
            SubscribeMatchEvents();
        }

        private void OnDisable()
        {
            UnsubscribeMatchEvents();
        }

        private void OnDestroy()
        {
            UnsubscribeMatchEvents();

            if (Instance == this)
            {
                Instance = null;
            }
        }

        private void Start()
        {
            if (_autoStartOnPlay)
            {
                StartNewEpisode();
            }
        }

        private void FixedUpdate()
        {
            if (!_autoStepInFixedUpdate || !_episodeRunning)
            {
                return;
            }

            if (_matchManager == null || _matchManager.Phase != MatchPhase.Running)
            {
                return;
            }

            _matchManager.StepMatch();
        }

        public void StartNewEpisode()
        {
            ResolveReferences();

            if (_matchManager == null || _matchBootstrap == null)
            {
                Debug.LogError("[EpisodeController] MatchManager or MatchBootstrap is missing.");
                _episodeRunning = false;
                return;
            }

            CleanupRuntimeObjects();

            _matchBootstrap.Setup();

            _episodeRunning = _matchManager.Phase == MatchPhase.Running;
            _episodeFinalized = false;

            if (_episodeRunning)
            {
                EpisodeIndex++;
                _experimentLogger?.BeginEpisode();
            }

            if (_logLifecycleEvents)
            {
                Debug.Log($"[EpisodeController] Episode {EpisodeIndex} started. Running={_episodeRunning}");
            }
        }

        public void ResetEpisode()
        {
            StartNewEpisode();
        }

        public bool StepEpisodeOnce()
        {
            ResolveReferences();

            if (_matchManager == null || _matchManager.Phase != MatchPhase.Running)
            {
                return false;
            }

            _episodeRunning = true;
            return _matchManager.StepMatch();
        }

        public bool ApplyCommand(MatchCommand command)
        {
            ResolveReferences();
            return _matchManager != null && _matchManager.ApplyCommand(command);
        }

        public int ApplyCommands(IReadOnlyList<MatchCommand> commands)
        {
            ResolveReferences();
            return _matchManager != null ? _matchManager.ApplyCommands(commands) : 0;
        }

        public MatchStateSnapshot GetMatchState()
        {
            ResolveReferences();
            return _matchManager != null ? _matchManager.GetMatchState() : default;
        }

        public void SetRunning(bool running)
        {
            _episodeRunning = running;
        }

        private void HandleMatchEnded(Owner winner)
        {
            _episodeRunning = false;

            if (_episodeFinalized)
            {
                return;
            }

            _episodeFinalized = true;
            bool player1Win = winner == Owner.Player1;
            _experimentLogger?.EndEpisode(player1Win);

            if (_logLifecycleEvents)
            {
                Debug.Log($"[EpisodeController] Episode {EpisodeIndex} ended. Winner={winner}");
            }
        }

        private void CleanupRuntimeObjects()
        {
            if (_unitRegistry != null)
            {
                List<UnitRuntime> units = _unitRegistry.GetAllUnits();
                for (int i = 0; i < units.Count; i++)
                {
                    UnitRuntime unit = units[i];
                    if (unit != null)
                    {
                        Destroy(unit.gameObject);
                    }
                }

                _unitRegistry.Clear();
            }

            if (_gridManager != null)
            {
                int width = _gridManager.Width > 0 ? _gridManager.Width : GameConstants.MapWidth;
                int height = _gridManager.Height > 0 ? _gridManager.Height : GameConstants.MapHeight;
                _gridManager.InitGrid(width, height);
            }

            _resourceManager?.Clear();
            _matchManager?.ResetMatch();
        }

        private void ResolveReferences()
        {
            if (_matchManager == null)
            {
                _matchManager = MatchManager.Instance;
            }

            if (_matchBootstrap == null)
            {
                _matchBootstrap = MatchBootstrap.Instance;
            }

            if (_gridManager == null)
            {
                _gridManager = GridManager.Instance;
            }

            if (_unitRegistry == null)
            {
                _unitRegistry = UnitRegistry.Instance;
            }

            if (_resourceManager == null)
            {
                _resourceManager = ResourceManager.Instance;
            }

            if (_experimentLogger == null)
            {
                _experimentLogger = FindFirstObjectByType<ExperimentLogger>();
            }
        }

        private void SubscribeMatchEvents()
        {
            if (_matchManager == null)
            {
                return;
            }

            _matchManager.OnMatchEnded -= HandleMatchEnded;
            _matchManager.OnMatchEnded += HandleMatchEnded;
        }

        private void UnsubscribeMatchEvents()
        {
            if (_matchManager == null)
            {
                return;
            }

            _matchManager.OnMatchEnded -= HandleMatchEnded;
        }
    }
}
