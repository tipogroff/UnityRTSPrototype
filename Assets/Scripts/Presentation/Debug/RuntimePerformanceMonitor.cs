using System.Collections.Generic;
using System;
using System.Text;
using RTS.Core;
using RTS.MLAgents.Stage7B;
using RTS.Gameplay;
using RTS.Presentation;
using UnityEngine;

namespace RTS.Presentation.Diagnostics
{
    [DisallowMultipleComponent]
    public sealed class RuntimePerformanceMonitor : MonoBehaviour
    {
#if UNITY_EDITOR || DEVELOPMENT_BUILD
        [SerializeField] private bool _showOverlay = false;
        [SerializeField] private bool _logSpikes = false;
        [SerializeField] private float _overlayRefreshSeconds = 0.25f;
        [SerializeField] private float _summaryIntervalSeconds = 30f;
        [SerializeField] private float _warningFrameMs = 33f;
        [SerializeField] private float _severeFrameMs = 50f;

        private readonly StringBuilder _builder = new StringBuilder(512);
        private MatchManager _matchManager;
        private EpisodeController _episodeController;
        private UnitRegistry _unitRegistry;
        private ResourceManager _resourceManager;
        private GameSpeedController _speedController;
                private StudentMlAgent _studentAgent;
private HumanPlayModeController _modeController;
        private GUIStyle _style;
        private string _overlayText = string.Empty;
        private float _nextOverlayRefresh;
        private float _nextReferenceRefresh;
        private float _summaryStartTime;
        private float _lastSummaryTime;
        private int _summaryStartFrame;
        private int _sampleCount;
        private double _frameMsTotal;
        private float _minFps = float.MaxValue;
        private float _worstFrameMs;
        private int _spikesOver33;
        private int _spikesOver50;
        private int _gc0Start;
        private int _gc1Start;
        private int _gc2Start;
        private int _lastGc0;
        private int _lastGc1;
        private int _lastGc2;

        public static RuntimePerformanceMonitor EnsureInScene()
        {
            RuntimePerformanceMonitor existing = FindFirstObjectByType<RuntimePerformanceMonitor>();
            if (existing != null)
            {
                return existing;
            }

            GameObject go = new GameObject("RuntimePerformanceMonitor");
            DontDestroyOnLoad(go);
            return go.AddComponent<RuntimePerformanceMonitor>();
        }

        public void Configure(bool showOverlay, bool logSpikes)
        {
            _showOverlay = showOverlay;
            _logSpikes = logSpikes;
        }

        private void OnEnable()
        {
            ResetSummaryWindow();
            ResolveReferences(force: true);
        }

        private void Update()
        {
            float dt = Time.unscaledDeltaTime;
            if (dt <= 0f)
            {
                return;
            }

            float frameMs = dt * 1000f;
            float fps = 1f / dt;
            _sampleCount++;
            _frameMsTotal += frameMs;
            _minFps = Mathf.Min(_minFps, fps);
            _worstFrameMs = Mathf.Max(_worstFrameMs, frameMs);

            int gc0 = GC.CollectionCount(0);
            int gc1 = GC.CollectionCount(1);
            int gc2 = GC.CollectionCount(2);
            int gc0Delta = gc0 - _lastGc0;
            int gc1Delta = gc1 - _lastGc1;
            int gc2Delta = gc2 - _lastGc2;
            _lastGc0 = gc0;
            _lastGc1 = gc1;
            _lastGc2 = gc2;

            bool warningSpike = frameMs >= _warningFrameMs;
            if (warningSpike)
            {
                _spikesOver33++;
                if (frameMs >= _severeFrameMs)
                {
                    _spikesOver50++;
                }

                if (_logSpikes)
                {
                    ResolveReferences(force: false);
                    UnityEngine.Debug.Log(
                        $"[Perf] Spike frame={Time.frameCount} dt={frameMs:0.0}ms mode={GetModeLabel()} step={GetStep()} units={GetUnitCount()} resources={GetResourceCount()} gc0_delta={gc0Delta} gc1_delta={gc1Delta} gc2_delta={gc2Delta} sourceHint=frame");
                }
            }

            if (_showOverlay && Time.unscaledTime >= _nextOverlayRefresh)
            {
                ResolveReferences(force: false);
                RebuildOverlayText(frameMs, fps, gc0, gc1, gc2);
                _nextOverlayRefresh = Time.unscaledTime + Mathf.Max(0.1f, _overlayRefreshSeconds);
            }

            if (Time.unscaledTime - _lastSummaryTime >= _summaryIntervalSeconds)
            {
                LogSummary();
                ResetSummaryWindow();
            }
        }

        private void OnGUI()
        {
            if (!_showOverlay)
            {
                return;
            }

            _style ??= new GUIStyle(GUI.skin.box)
            {
                alignment = TextAnchor.UpperLeft,
                fontSize = 13,
                normal = { textColor = Color.white },
                padding = new RectOffset(8, 8, 6, 6)
            };

            GUI.Box(new Rect(12f, 12f, 360f, 166f), _overlayText, _style);
        }

private void ResolveReferences(bool force)
        {
            if (!force && Time.unscaledTime < _nextReferenceRefresh)
            {
                return;
            }

            _nextReferenceRefresh = Time.unscaledTime + 1f;
            _matchManager = MatchManager.Instance != null ? MatchManager.Instance : FindFirstObjectByType<MatchManager>();
            _episodeController = EpisodeController.Instance != null ? EpisodeController.Instance : FindFirstObjectByType<EpisodeController>();
            _unitRegistry = UnitRegistry.Instance != null ? UnitRegistry.Instance : FindFirstObjectByType<UnitRegistry>();
            _resourceManager = ResourceManager.Instance != null ? ResourceManager.Instance : FindFirstObjectByType<ResourceManager>();
            _speedController = FindFirstObjectByType<GameSpeedController>();
            _modeController = FindFirstObjectByType<HumanPlayModeController>();
            _studentAgent = FindFirstObjectByType<StudentMlAgent>();
        }

private void RebuildOverlayText(float frameMs, float fps, int gc0, int gc1, int gc2)
        {
            _builder.Clear();
            _builder.Append("FPS ").Append(fps.ToString("0.0"))
                .Append("  frame ").Append(frameMs.ToString("0.0")).Append(" ms\n");
            _builder.Append("Worst ").Append(_worstFrameMs.ToString("0.0"))
                .Append(" ms  minFPS ").Append((_minFps < float.MaxValue ? _minFps : 0f).ToString("0.0")).Append('\n');
            _builder.Append("Mode ").Append(GetModeLabel())
                .Append("  step ").Append(GetStep()).Append('\n');
            _builder.Append("Units ").Append(GetUnitCount())
                .Append("  P1/P2 ").Append(GetAliveUnitCount(Owner.Player1)).Append('/').Append(GetAliveUnitCount(Owner.Player2))
                .Append("  resources ").Append(GetResourceCount()).Append('\n');
            _builder.Append("VisualBridge ").Append(GetVisualBridgeCount())
                .Append("  ghosts ").Append(GetDeathGhostCount())
                .Append("  candidates ").Append(GetLastCandidateCount()).Append('\n');
            _builder.Append("Combat attackers/checks ").Append(GetCombatAttackers())
                .Append('/').Append(GetCombatTargetChecks()).Append('\n');
            _builder.Append("Speed ").Append(GetSpeedLabel())
                .Append("  paused ").Append(IsPaused() ? "yes" : "no").Append('\n');
            _builder.Append("GC ").Append(gc0 - _gc0Start)
                .Append('/').Append(gc1 - _gc1Start)
                .Append('/').Append(gc2 - _gc2Start)
                .Append("  spikes ").Append(_spikesOver33)
                .Append('/').Append(_spikesOver50);
            _overlayText = _builder.ToString();
        }

private void LogSummary()
        {
            ResolveReferences(force: false);
            float duration = Mathf.Max(0.001f, Time.unscaledTime - _summaryStartTime);
            float avgFrameMs = _sampleCount > 0 ? (float)(_frameMsTotal / _sampleCount) : 0f;
            float avgFps = avgFrameMs > 0f ? 1000f / avgFrameMs : 0f;
            UnityEngine.Debug.Log(
                $"[Perf] Summary mode={GetModeLabel()} duration={duration:0.0}s frames={Time.frameCount - _summaryStartFrame} step={GetStep()} avgFps={avgFps:0.0} minFps={(_minFps < float.MaxValue ? _minFps : 0f):0.0} avgMs={avgFrameMs:0.0} worstMs={_worstFrameMs:0.0} units={GetUnitCount()} p1Units={GetAliveUnitCount(Owner.Player1)} p2Units={GetAliveUnitCount(Owner.Player2)} visualBridges={GetVisualBridgeCount()} deathGhosts={GetDeathGhostCount()} candidates={GetLastCandidateCount()} combatAttackers={GetCombatAttackers()} combatChecks={GetCombatTargetChecks()} spikes33={_spikesOver33} spikes50={_spikesOver50} gc0={GC.CollectionCount(0) - _gc0Start} gc1={GC.CollectionCount(1) - _gc1Start} gc2={GC.CollectionCount(2) - _gc2Start}");
        }

        private void ResetSummaryWindow()
        {
            _summaryStartTime = Time.unscaledTime;
            _lastSummaryTime = Time.unscaledTime;
            _summaryStartFrame = Time.frameCount;
            _sampleCount = 0;
            _frameMsTotal = 0d;
            _minFps = float.MaxValue;
            _worstFrameMs = 0f;
            _spikesOver33 = 0;
            _spikesOver50 = 0;
            _gc0Start = GC.CollectionCount(0);
            _gc1Start = GC.CollectionCount(1);
            _gc2Start = GC.CollectionCount(2);
            _lastGc0 = _gc0Start;
            _lastGc1 = _gc1Start;
            _lastGc2 = _gc2Start;
        }

        private string GetModeLabel()
            => _modeController != null ? _modeController.CurrentMode.ToString() : "n/a";

        private int GetStep()
            => _matchManager != null ? _matchManager.Step : -1;

        private int GetUnitCount()
            => _unitRegistry != null ? _unitRegistry.UnitCount : 0;

private int GetAliveUnitCount(Owner owner)
        {
            if (_unitRegistry == null)
            {
                return 0;
            }

            IReadOnlyList<UnitRuntime> units = _unitRegistry.GetUnitsByOwnerReadOnly(owner);
            int count = 0;
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

        private int GetVisualBridgeCount()
            => FindObjectsByType<VisualEventBridge>(FindObjectsInactive.Exclude, FindObjectsSortMode.None).Length;

        private int GetDeathGhostCount()
            => FindObjectsByType<VisualDeathPlaybackGhost>(FindObjectsInactive.Exclude, FindObjectsSortMode.None).Length;

        private int GetLastCandidateCount()
            => _studentAgent != null ? _studentAgent.LastCandidateCount : 0;

        private int GetCombatAttackers()
            => _matchManager != null ? _matchManager.LastCombatAttackersEvaluated : 0;

        private int GetCombatTargetChecks()
            => _matchManager != null ? _matchManager.LastCombatTargetCellChecks : 0;


        private int GetResourceCount()
            => _resourceManager != null ? _resourceManager.GetActiveResourceCount() : 0;

        private string GetSpeedLabel()
            => _speedController != null ? _speedController.CurrentSpeed.ToString("0.##") : "n/a";

        private bool IsPaused()
            => (_speedController != null && _speedController.IsPaused)
               || (_episodeController != null && _episodeController.IsAutomaticSteppingPaused);
#endif
    }
}
