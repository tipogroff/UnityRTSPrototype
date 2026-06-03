using System;
using System.Diagnostics;
using System.IO;
using RTS.MLAgents.Stage7B.CandidateActions;
using Unity.MLAgents.Policies;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.Diagnostics
{
    [DisallowMultipleComponent]
    public sealed class Stage7BHeuristicDryRunLogger : MonoBehaviour
    {
        [SerializeField] private string _artifactFileName = "stage7b_mlagents_heuristic_dryrun.json";
        [SerializeField] private float _writeIntervalSeconds = 2f;
        [SerializeField] private bool _enableRuntimeArtifactWrites = false;

        private StudentMlAgent _agent;
        private float _timer;

        private void Awake()
        {
            _agent = FindFirstObjectByType<StudentMlAgent>();
        }

private void Start()
        {
            if (!_enableRuntimeArtifactWrites)
            {
                return;
            }

            RefreshEnvironmentVersions();
            WriteArtifact();
        }

private void Update()
        {
            if (!_enableRuntimeArtifactWrites)
            {
                return;
            }

            _timer += Time.unscaledDeltaTime;
            if (_timer >= _writeIntervalSeconds)
            {
                _timer = 0f;
                WriteArtifact();
            }
        }

private void OnDisable()
        {
            if (!_enableRuntimeArtifactWrites)
            {
                return;
            }

            WriteArtifact();
        }

public void WriteArtifact()
        {
            if (!_enableRuntimeArtifactWrites)
            {
                return;
            }

            if (_agent == null)
            {
                _agent = FindFirstObjectByType<StudentMlAgent>();
            }

            if (_agent == null)
            {
                return;
            }

            if (_agent.Trace.MlAgentsPackageVersion == "unknown"
                || _agent.Trace.PythonVersion == "unavailable")
            {
                RefreshEnvironmentVersions();
            }

            RefreshRuntimeMetadata();

            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            string path = Path.Combine(projectRoot, _artifactFileName);
            File.WriteAllText(path, _agent.Trace.ToJson());
        }

private void RefreshEnvironmentVersions()
        {
            if (!_enableRuntimeArtifactWrites || _agent == null)
            {
                return;
            }

            Stage7BActionTrace trace = _agent.Trace;
            trace.UnityVersion = Application.unityVersion;
            trace.MlAgentsPackageVersion = ResolveUnityMlAgentsPackageVersion();
            trace.PythonVersion = RunVersionCommand("python", "--version");
            trace.MlAgentsPythonVersion = RunVersionCommand("python", "-m mlagents.trainers.learn --version");
            trace.MlAgentsEnvsPythonVersion = RunVersionCommand("python", "-m pip show mlagents-envs");
        }

        private void RefreshRuntimeMetadata()
        {
            if (_agent == null)
            {
                return;
            }

            BehaviorParameters behavior = _agent.GetComponent<BehaviorParameters>();
            _agent.Trace.RecordDecisionSource(_agent.CurrentDecisionSource);
            _agent.Trace.RecordBehaviorSpec(
                behavior != null ? behavior.BehaviorName : "unknown",
                discreteBranchCount: 1,
                MlAgentsCandidateActionList.BranchSize);
            _agent.Trace.RecordActionContract(
                MlAgentsCandidateActionList.AttackTargetSize,
                MlAgentsCandidateActionList.AttackTargetCenterIndex);
        }

        private static string ResolveUnityMlAgentsPackageVersion()
        {
            string manifestPath = Path.Combine(Directory.GetParent(Application.dataPath)?.FullName ?? string.Empty, "Packages", "manifest.json");
            if (!File.Exists(manifestPath))
            {
                return "unknown";
            }

            string text = File.ReadAllText(manifestPath);
            const string key = "\"com.unity.ml-agents\"";
            int keyIndex = text.IndexOf(key, StringComparison.Ordinal);
            if (keyIndex < 0)
            {
                return "not-installed";
            }

            int colon = text.IndexOf(':', keyIndex);
            int firstQuote = colon >= 0 ? text.IndexOf('"', colon + 1) : -1;
            int secondQuote = firstQuote >= 0 ? text.IndexOf('"', firstQuote + 1) : -1;
            return firstQuote >= 0 && secondQuote > firstQuote
                ? text.Substring(firstQuote + 1, secondQuote - firstQuote - 1)
                : "unknown";
        }

        private static string RunVersionCommand(string executable, string arguments)
        {
            try
            {
                var info = new ProcessStartInfo(executable, arguments)
                {
                    CreateNoWindow = true,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true
                };

                using Process process = Process.Start(info);
                if (process == null)
                {
                    return "unavailable";
                }

                if (!process.WaitForExit(2000))
                {
                    process.Kill();
                    return "timeout";
                }

                string output = process.StandardOutput.ReadToEnd().Trim();
                string error = process.StandardError.ReadToEnd().Trim();
                string combined = string.IsNullOrWhiteSpace(output) ? error : output;
                return string.IsNullOrWhiteSpace(combined) ? "unavailable" : combined.Replace("\r", " ").Replace("\n", " ");
            }
            catch (Exception ex)
            {
                return ex.GetType().Name;
            }
        }
    }
}
