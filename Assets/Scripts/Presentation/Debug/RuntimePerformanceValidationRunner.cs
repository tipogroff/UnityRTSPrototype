using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Text;
using RTS.Gameplay;
using RTS.Presentation;
using RTS.Presentation.UI;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RTS.Presentation.Diagnostics
{
    [DisallowMultipleComponent]
    public sealed class RuntimePerformanceValidationRunner : MonoBehaviour
    {
#if UNITY_EDITOR || DEVELOPMENT_BUILD
        [SerializeField] private float _warmupSeconds = 5f;
        [SerializeField] private float _measureSeconds = 30f;
        [SerializeField] private bool _autoRunOnStart;
        [SerializeField] private string _validationSceneName = "HumanPlay_Demo_PlayerVsAI";

        private readonly List<PerformanceRunResult> _results = new List<PerformanceRunResult>(3);
        private Coroutine _runCoroutine;
        private Action _onCompleted;
        private bool _runtimeSettingsApplied;
        private int _previousTargetFrameRate;
        private int _previousVSyncCount;
        private bool _previousRunInBackground;

        public static RuntimePerformanceValidationRunner EnsureInScene()
        {
            RuntimePerformanceValidationRunner existing = FindFirstObjectByType<RuntimePerformanceValidationRunner>();
            if (existing != null)
            {
                return existing;
            }

            GameObject go = new GameObject("RuntimePerformanceValidationRunner");
            DontDestroyOnLoad(go);
            return go.AddComponent<RuntimePerformanceValidationRunner>();
        }

        public void Run()
        {
            Run(null);
        }

        public void Run(Action onCompleted)
        {
            if (_runCoroutine != null)
            {
                StopCoroutine(_runCoroutine);
            }

            _onCompleted = onCompleted;
            _runCoroutine = StartCoroutine(RunAllModes());
        }

        private void Start()
        {
            if (_autoRunOnStart)
            {
                Run();
            }
        }

        private IEnumerator RunAllModes()
        {
            ApplyValidationRuntimeSettings();
            RuntimePerformanceMonitor.EnsureInScene().Configure(showOverlay: false, logSpikes: false);
            _results.Clear();

            yield return EnsureValidationSceneLoaded();

            yield return RunMode("AIvsPlayer", controller => controller.StartAIvsPlayer2());
            yield return RunMode("AIvsBot", controller => controller.StartAIvsBot());
            yield return RunMode("AIvsAI", controller => controller.StartAIvsAI());

            WriteReports();
            RestoreRuntimeSettings();
            UnityEngine.Debug.Log("[Perf] Validation complete. Reports written to PERFORMANCE_VALIDATION_REPORT.md/json.");
            _runCoroutine = null;
            Action completed = _onCompleted;
            _onCompleted = null;
            completed?.Invoke();
        }

        private void OnDisable()
        {
            RestoreRuntimeSettings();
        }

        private void ApplyValidationRuntimeSettings()
        {
            if (_runtimeSettingsApplied)
            {
                return;
            }

            _previousTargetFrameRate = Application.targetFrameRate;
            _previousVSyncCount = QualitySettings.vSyncCount;
            _previousRunInBackground = Application.runInBackground;

            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = RuntimeFrameRateLimiter.DefaultTargetFrameRate;
            Application.runInBackground = true;
            _runtimeSettingsApplied = true;
        }

        private void RestoreRuntimeSettings()
        {
            if (!_runtimeSettingsApplied)
            {
                return;
            }

            Application.targetFrameRate = _previousTargetFrameRate;
            QualitySettings.vSyncCount = _previousVSyncCount;
            Application.runInBackground = _previousRunInBackground;
            _runtimeSettingsApplied = false;
            RuntimeFrameRateLimiter.ApplyDefault();
        }

        private IEnumerator RunMode(string modeName, Action<HumanPlayModeController> startMode)
        {
            HumanPlayModeController modeController = FindFirstObjectByType<HumanPlayModeController>();
            if (modeController == null)
            {
                yield return EnsureValidationSceneLoaded();
                modeController = FindFirstObjectByType<HumanPlayModeController>();
            }

            if (modeController == null)
            {
                _results.Add(PerformanceRunResult.Failed(modeName, "HumanPlayModeController missing."));
                yield break;
            }

            startMode(modeController);
            yield return new WaitForSecondsRealtime(Mathf.Max(0f, _warmupSeconds));

            MatchManager matchManager = MatchManager.Instance != null ? MatchManager.Instance : FindFirstObjectByType<MatchManager>();
            EpisodeController episodeController = EpisodeController.Instance != null ? EpisodeController.Instance : FindFirstObjectByType<EpisodeController>();
            UnitRegistry unitRegistry = UnitRegistry.Instance != null ? UnitRegistry.Instance : FindFirstObjectByType<UnitRegistry>();
            ResourceManager resourceManager = ResourceManager.Instance != null ? ResourceManager.Instance : FindFirstObjectByType<ResourceManager>();
            GameSpeedController speedController = FindFirstObjectByType<GameSpeedController>();

            int startFrame = Time.frameCount;
            float startTime = Time.unscaledTime;
            int startStep = matchManager != null ? matchManager.Step : -1;
            int startUnitCount = unitRegistry != null ? unitRegistry.UnitCount : 0;
            int startResourceCount = resourceManager != null ? resourceManager.GetActiveResourceCount() : 0;
            int gc0Start = GC.CollectionCount(0);
            int gc1Start = GC.CollectionCount(1);
            int gc2Start = GC.CollectionCount(2);
            int sampleCount = 0;
            double frameMsTotal = 0d;
            float minFps = float.MaxValue;
            float worstMs = 0f;
            int spikes33 = 0;
            int spikes50 = 0;

            while (Time.unscaledTime - startTime < _measureSeconds)
            {
                float dt = Time.unscaledDeltaTime;
                if (dt > 0f)
                {
                    float frameMs = dt * 1000f;
                    sampleCount++;
                    frameMsTotal += frameMs;
                    minFps = Mathf.Min(minFps, 1f / dt);
                    worstMs = Mathf.Max(worstMs, frameMs);
                    if (frameMs >= 33f)
                    {
                        spikes33++;
                    }

                    if (frameMs >= 50f)
                    {
                        spikes50++;
                    }
                }

                yield return null;
            }

            float duration = Mathf.Max(0.001f, Time.unscaledTime - startTime);
            float avgMs = sampleCount > 0 ? (float)(frameMsTotal / sampleCount) : 0f;
            bool paused = (speedController != null && speedController.IsPaused)
                          || (episodeController != null && episodeController.IsAutomaticSteppingPaused);
            _results.Add(new PerformanceRunResult
            {
                mode = modeName,
                durationSeconds = duration,
                frames = Time.frameCount - startFrame,
                startStep = startStep,
                endStep = matchManager != null ? matchManager.Step : -1,
                startUnitCount = startUnitCount,
                endUnitCount = unitRegistry != null ? unitRegistry.UnitCount : 0,
                startResourceCount = startResourceCount,
                endResourceCount = resourceManager != null ? resourceManager.GetActiveResourceCount() : 0,
                speed = speedController != null ? speedController.CurrentSpeed : 0f,
                paused = paused,
                averageFps = avgMs > 0f ? 1000f / avgMs : 0f,
                minFps = minFps < float.MaxValue ? minFps : 0f,
                averageFrameMs = avgMs,
                worstFrameMs = worstMs,
                spikesOver33Ms = spikes33,
                spikesOver50Ms = spikes50,
                gc0Collections = GC.CollectionCount(0) - gc0Start,
                gc1Collections = GC.CollectionCount(1) - gc1Start,
                gc2Collections = GC.CollectionCount(2) - gc2Start,
                notes = "Runtime validation sample."
            });
        }

        private IEnumerator EnsureValidationSceneLoaded()
        {
            if (FindFirstObjectByType<HumanPlayModeController>() != null)
            {
                yield break;
            }

            if (SceneManager.GetActiveScene().name != _validationSceneName)
            {
                DemoLaunchOptions.SetMode(DemoLaunchMode.AIvsPlayer);
                AsyncOperation load = SceneManager.LoadSceneAsync(_validationSceneName, LoadSceneMode.Single);
                if (load == null)
                {
                    UnityEngine.Debug.LogWarning("[Perf] Could not load validation scene: " + _validationSceneName);
                    yield break;
                }

                while (!load.isDone)
                {
                    yield return null;
                }
            }

            float timeoutAt = Time.realtimeSinceStartup + 5f;
            while (FindFirstObjectByType<HumanPlayModeController>() == null && Time.realtimeSinceStartup < timeoutAt)
            {
                yield return null;
            }
        }

        private void WriteReports()
        {
            string root = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            string markdownPath = Path.Combine(root, "PERFORMANCE_VALIDATION_REPORT.md");
            string jsonPath = Path.Combine(root, "performance_validation_report.json");

            File.WriteAllText(markdownPath, BuildMarkdownReport(), Encoding.UTF8);
            File.WriteAllText(jsonPath, JsonUtility.ToJson(new PerformanceValidationReport
            {
                dateUtc = DateTime.UtcNow.ToString("O"),
                unityVersion = Application.unityVersion,
                warmupSeconds = _warmupSeconds,
                measureSeconds = _measureSeconds,
                results = _results.ToArray()
            }, prettyPrint: true), Encoding.UTF8);
        }

        private string BuildMarkdownReport()
        {
            StringBuilder builder = new StringBuilder(2048);
            builder.AppendLine("# Performance Validation Report");
            builder.AppendLine();
            builder.AppendLine("- Date UTC: " + DateTime.UtcNow.ToString("O"));
            builder.AppendLine("- Unity version: " + Application.unityVersion);
            builder.AppendLine("- Warmup seconds: " + _warmupSeconds.ToString("0.0"));
            builder.AppendLine("- Measurement seconds: " + _measureSeconds.ToString("0.0"));
            builder.AppendLine();
            builder.AppendLine("| Mode | Steps | Units | Resources | Speed | Paused | Avg FPS | Min FPS | Avg ms | Worst ms | >33ms | >50ms | GC0 | GC1 | GC2 |");
            builder.AppendLine("| --- | ---: | ---: | ---: | ---: | :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |");
            for (int i = 0; i < _results.Count; i++)
            {
                PerformanceRunResult result = _results[i];
                builder.Append("| ").Append(result.mode)
                    .Append(" | ").Append(result.startStep).Append("->").Append(result.endStep)
                    .Append(" | ").Append(result.startUnitCount).Append("->").Append(result.endUnitCount)
                    .Append(" | ").Append(result.startResourceCount).Append("->").Append(result.endResourceCount)
                    .Append(" | ").Append(result.speed.ToString("0.##"))
                    .Append(" | ").Append(result.paused ? "yes" : "no")
                    .Append(" | ").Append(result.averageFps.ToString("0.0"))
                    .Append(" | ").Append(result.minFps.ToString("0.0"))
                    .Append(" | ").Append(result.averageFrameMs.ToString("0.0"))
                    .Append(" | ").Append(result.worstFrameMs.ToString("0.0"))
                    .Append(" | ").Append(result.spikesOver33Ms)
                    .Append(" | ").Append(result.spikesOver50Ms)
                    .Append(" | ").Append(result.gc0Collections)
                    .Append(" | ").Append(result.gc1Collections)
                    .Append(" | ").Append(result.gc2Collections)
                    .AppendLine(" |");
            }

            builder.AppendLine();
            builder.AppendLine("## Changes Applied");
            builder.AppendLine("- Added dev-only RuntimePerformanceMonitor with FPS/frame/GC spike logging.");
            builder.AppendLine("- Added ProfilerMarker coverage for simulation, ML observation/mask/action, registry, combat, and HUD.");
            builder.AppendLine("- Removed regular hot-path allocations in UnitRegistry, MatchManager command/combat buffers, decision source creation, and selected UI refresh.");
            builder.AppendLine("- Gated verbose combat/production/human-move logs behind debug flags.");
            builder.AppendLine("- Changed HUD panels to update text/visibility only when values change.");
            return builder.ToString();
        }

        [Serializable]
        private sealed class PerformanceValidationReport
        {
            public string dateUtc;
            public string unityVersion;
            public float warmupSeconds;
            public float measureSeconds;
            public PerformanceRunResult[] results;
        }

        [Serializable]
        private struct PerformanceRunResult
        {
            public string mode;
            public float durationSeconds;
            public int frames;
            public int startStep;
            public int endStep;
            public int startUnitCount;
            public int endUnitCount;
            public int startResourceCount;
            public int endResourceCount;
            public float speed;
            public bool paused;
            public float averageFps;
            public float minFps;
            public float averageFrameMs;
            public float worstFrameMs;
            public int spikesOver33Ms;
            public int spikesOver50Ms;
            public int gc0Collections;
            public int gc1Collections;
            public int gc2Collections;
            public string notes;

            public static PerformanceRunResult Failed(string mode, string reason)
            {
                return new PerformanceRunResult
                {
                    mode = mode,
                    notes = reason
                };
            }
        }
#endif
    }
}
