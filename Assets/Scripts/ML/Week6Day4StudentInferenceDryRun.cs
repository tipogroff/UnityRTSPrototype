using System;
using System.Collections;
using System.Diagnostics;
using System.IO;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace RTS.ML
{
    /// <summary>
    /// Week 6 Day 4 technical dry run:
    /// Unity observation -> student checkpoint inference (Python bridge) -> decoder -> ActionApplier
    /// under v2/Gridnet-compatible action contract [6,4,4,4,4,7,49].
    ///
    /// This component validates wiring only and does not claim gameplay quality.
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class Week6Day4StudentInferenceDryRun : MonoBehaviour
    {
        private const string ExpectedStudentCheckpointFileName = "student_bc_transfer_best.pt";
        private const string ExpectedActionContractVersion = "v2_gridnet_compatible";

        [Serializable]
        private sealed class AdapterResult
        {
            public string status;
            public string error;
            public string action_contract_version;
            public string checkpoint_path;
            public int checkpoint_epoch;
            public string checkpoint_model_variant;
            public int[] observation_shape;
            public string observation_dtype;
            public int observation_element_count;
            public string[] branch_order;
            public int[] branch_sizes;
            public string[] logits_keys;
            public int action_flat_size;
            public int[] action_flat;
        }

        [Serializable]
        private sealed class Day4PlayModeSmokeReport
        {
            public string status = "fail";
            public string checkpoint_path = string.Empty;
            public string action_contract_version = string.Empty;
            public int[] branch_sizes = Array.Empty<int>();
            public bool observation_validated;
            public string python_adapter_status = "fail";
            public int action_flat_size;
            public string unity_decode_submit_status = "fail";
            public bool canonical_path_reached;
            public string error = string.Empty;
            public string python_executable_path = string.Empty;
            public string adapter_script_path = string.Empty;
            public string observation_bin_path = string.Empty;
            public string output_json_path = string.Empty;
            public string working_directory = string.Empty;
            public string command_line_args = string.Empty;
            public string python_stdout = string.Empty;
            public string python_stderr = string.Empty;
            public int python_exit_code = -1;
            public bool output_json_exists;
            public string output_json_status = string.Empty;
            public string output_json_error = string.Empty;
        }

        [Header("Execution")]
        [SerializeField] private bool _runOnAwake;
        [SerializeField] private bool _verboseLogs = true;
        [SerializeField] private bool _stepMatchAfterSubmit;
        [SerializeField] private Owner _playerPerspective = Owner.Player1;

        [Header("Python Bridge")]
        [SerializeField] private string _pythonExecutableRelativePath = ".venv/Scripts/python.exe";
        [SerializeField] private string _adapterScriptRelativePath = "python/week6_student/student_inference_adapter.py";
        [SerializeField] private string _checkpointRelativePath = "python/week6_student/runs/legacy032_v2_bc_minimal_20260501T195501Z/student_bc_transfer_best.pt";
        [SerializeField] private string _artifactDirectoryRelativePath = "WEEK6/artifacts/day4_student_inference";
        [SerializeField] private string _smokeReportRelativePath = "python/week6_student/tmp/day4_unity_playmode_smoke_report.json";

        private GridManager _gridManager;
        private UnitRegistry _unitRegistry;
        private MatchManager _matchManager;
        private MatchBootstrap _matchBootstrap;
        private ResourceManager _resourceManager;
        private ObservationBuilder _observationBuilder;
        private MlPolicyPipelineFacade _pipeline;

        private void Awake()
        {
            if (_runOnAwake)
            {
                StartCoroutine(WaitAndRunDryRunWhenReady());
            }
        }

        private IEnumerator WaitAndRunDryRunWhenReady()
        {
            const float timeoutSeconds = 15f;
            float endTime = Time.realtimeSinceStartup + timeoutSeconds;

            while (Time.realtimeSinceStartup < endTime)
            {
                if (ResolveRuntimeReferences())
                {
                    RunDryRun();
                    yield break;
                }

                yield return null;
            }

            RunDryRun();
        }

        [ContextMenu("Run Week6 Day4 Student Inference Dry Run")]
        public void RunDryRun()
        {
            string projectRoot = ResolveProjectRoot();
            if (string.IsNullOrWhiteSpace(projectRoot))
            {
                Debug.LogError("[Week6Day4StudentInferenceDryRun] Cannot resolve Unity project root.");
                return;
            }

            string smokeReportPath = Path.GetFullPath(Path.Combine(projectRoot, _smokeReportRelativePath));
            var smokeReport = new Day4PlayModeSmokeReport();

            if (!ResolveRuntimeReferences())
            {
                FailAndWriteReport(smokeReport, smokeReportPath, "Runtime references are missing");
                return;
            }

            string pythonPath = Path.GetFullPath(Path.Combine(projectRoot, _pythonExecutableRelativePath));
            string adapterPath = Path.GetFullPath(Path.Combine(projectRoot, _adapterScriptRelativePath));
            string checkpointPath = Path.GetFullPath(Path.Combine(projectRoot, _checkpointRelativePath));
            string artifactDir = Path.GetFullPath(Path.Combine(projectRoot, _artifactDirectoryRelativePath));
            Directory.CreateDirectory(artifactDir);
            smokeReport.checkpoint_path = checkpointPath;

            if (!string.Equals(Path.GetFileName(checkpointPath), ExpectedStudentCheckpointFileName, StringComparison.OrdinalIgnoreCase))
            {
                FailAndWriteReport(
                    smokeReport,
                    smokeReportPath,
                    "Unexpected checkpoint file name. Day4 requires student_bc_transfer_best.pt");
                return;
            }

            string observationBinPath = Path.Combine(artifactDir, "unity_observation.bin");
            string adapterResultPath = Path.Combine(artifactDir, "student_inference_result.json");

            smokeReport.python_executable_path = pythonPath;
            smokeReport.adapter_script_path = adapterPath;
            smokeReport.observation_bin_path = observationBinPath;
            smokeReport.output_json_path = adapterResultPath;
            smokeReport.working_directory = projectRoot;

            ObservationPackage observationPackage = _pipeline.BuildObservationPackage(_playerPerspective, ObservationMode.UnityMvpTransfer);
            ObservationValidationResult validation = _observationBuilder.ValidateObservation(observationPackage.SpatialObservation);
            if (!validation.IsValid)
            {
                FailAndWriteReport(
                    smokeReport,
                    smokeReportPath,
                    "Observation validation failed: " + validation);
                return;
            }
            smokeReport.observation_validated = true;

            if (observationPackage.SpatialObservation == null || observationPackage.SpatialObservation.Length != ObservationContract.TotalFloats)
            {
                FailAndWriteReport(
                    smokeReport,
                    smokeReportPath,
                    "Observation length mismatch. " +
                    $"Expected {ObservationContract.TotalFloats}, got {(observationPackage.SpatialObservation == null ? 0 : observationPackage.SpatialObservation.Length)}");
                return;
            }

            WriteFloat32Buffer(observationPackage.SpatialObservation, observationBinPath);

            if (!File.Exists(pythonPath))
            {
                FailAndWriteReport(smokeReport, smokeReportPath, $"Python executable not found: {pythonPath}");
                return;
            }

            if (!File.Exists(adapterPath))
            {
                FailAndWriteReport(smokeReport, smokeReportPath, $"Adapter script not found: {adapterPath}");
                return;
            }

            if (!File.Exists(checkpointPath))
            {
                FailAndWriteReport(smokeReport, smokeReportPath, $"Student checkpoint not found: {checkpointPath}");
                return;
            }

            string arguments =
                Quote(adapterPath) + " " +
                "--checkpoint " + Quote(checkpointPath) + " " +
                "--observation-bin " + Quote(observationBinPath) + " " +
                "--output-json " + Quote(adapterResultPath) + " " +
                "--device cpu";

            smokeReport.command_line_args = arguments;
            Debug.Log(
                "[Week6Day4StudentInferenceDryRun] Python invocation diagnostics: " +
                $"python={pythonPath}, script={adapterPath}, checkpoint={checkpointPath}, " +
                $"observation_bin={observationBinPath}, output_json={adapterResultPath}, " +
                $"working_dir={projectRoot}, args={arguments}");

            bool bridgeOk = RunProcess(
                pythonPath,
                arguments,
                projectRoot,
                out string stdout,
                out string stderr,
                out int exitCode);

            smokeReport.python_stdout = stdout;
            smokeReport.python_stderr = stderr;
            smokeReport.python_exit_code = exitCode;
            smokeReport.output_json_exists = File.Exists(adapterResultPath);

            if (smokeReport.output_json_exists)
            {
                TryReadAdapterFailureSummary(adapterResultPath, out string outStatus, out string outError);
                smokeReport.output_json_status = outStatus;
                smokeReport.output_json_error = outError;
            }

            if (_verboseLogs)
            {
                if (!string.IsNullOrWhiteSpace(stdout))
                {
                    Debug.Log("[Week6Day4StudentInferenceDryRun] Python stdout:\n" + stdout);
                }

                if (!string.IsNullOrWhiteSpace(stderr))
                {
                    Debug.LogWarning("[Week6Day4StudentInferenceDryRun] Python stderr:\n" + stderr);
                }
            }

            if (!bridgeOk || exitCode != 0)
            {
                if (IsLikelyV1CheckpointHeadMismatch(smokeReport.output_json_error))
                {
                    SkipConfigAndWriteReport(
                        smokeReport,
                        smokeReportPath,
                        "SKIPPED_CONFIG_REQUIRED: checkpoint branch heads are v1-sized (produce=4, attack=9) " +
                        "and incompatible with Unity v2 contract [6,4,4,4,4,7,49]. Provide v2-compatible checkpoint artifact.");
                    return;
                }

                FailAndWriteReport(
                    smokeReport,
                    smokeReportPath,
                    "Python adapter failed. " +
                    $"exitCode={exitCode}, outputJsonExists={smokeReport.output_json_exists}, " +
                    $"outputJsonStatus={smokeReport.output_json_status}, outputJsonError={smokeReport.output_json_error}");
                return;
            }
            smokeReport.python_adapter_status = "ok";

            if (!File.Exists(adapterResultPath))
            {
                FailAndWriteReport(smokeReport, smokeReportPath, $"Adapter output not found: {adapterResultPath}");
                return;
            }

            string jsonText = File.ReadAllText(adapterResultPath);
            AdapterResult adapter = JsonUtility.FromJson<AdapterResult>(jsonText);
            if (adapter == null)
            {
                FailAndWriteReport(smokeReport, smokeReportPath, "Cannot parse adapter JSON output");
                return;
            }

            if (!string.Equals(adapter.status, "ok", StringComparison.Ordinal))
            {
                FailAndWriteReport(smokeReport, smokeReportPath, "Adapter status is not ok: " + adapter.error);
                return;
            }

            if (!ValidateAdapterPayload(adapter, out string adapterPayloadError))
            {
                FailAndWriteReport(smokeReport, smokeReportPath, adapterPayloadError);
                return;
            }
            smokeReport.action_contract_version = adapter.action_contract_version ?? string.Empty;
            smokeReport.branch_sizes = adapter.branch_sizes ?? Array.Empty<int>();
            smokeReport.action_flat_size = adapter.action_flat_size;

            ActionMaskSet mask = _pipeline.BuildTransferCompatibleMask(_playerPerspective);
            PolicyExecutionReport execution;
            try
            {
                execution = _pipeline.ExecuteTransferCompatible(
                    adapter.action_flat,
                    _playerPerspective,
                    mask,
                    "week6-day4-student-checkpoint");
                smokeReport.canonical_path_reached = true;
                smokeReport.unity_decode_submit_status = "pass";
            }
            catch (Exception ex)
            {
                FailAndWriteReport(
                    smokeReport,
                    smokeReportPath,
                    "Canonical Unity decode/apply path failed: " + ex.Message);
                return;
            }

            if (_stepMatchAfterSubmit && _matchManager != null && _matchManager.Phase == MatchPhase.Running)
            {
                _matchManager.StepMatch();
            }

            smokeReport.status = "pass";
            smokeReport.error = string.Empty;
            WriteSmokeReport(smokeReport, smokeReportPath);

            Debug.Log(
                "[Week6Day4StudentInferenceDryRun] PASS technical wiring: " +
                $"checkpoint={adapter.checkpoint_path}, epoch={adapter.checkpoint_epoch}, " +
                $"actionContract={adapter.action_contract_version}, branchSizes=[{string.Join(",", adapter.branch_sizes ?? Array.Empty<int>())}], " +
                $"decodedActions={execution.DecodedActions.Count}, accepted={execution.AcceptedCount}, rejected={execution.RejectedCount}. " +
                $"report={smokeReportPath}. " +
                "Scope note: this is Day 4 technical integration only; no gameplay strength claim.");
        }

        private static void FailAndWriteReport(Day4PlayModeSmokeReport report, string reportPath, string error)
        {
            report.status = "fail";
            report.error = error;
            WriteSmokeReport(report, reportPath);
            Debug.LogError("[Week6Day4StudentInferenceDryRun] " + error + " | report=" + reportPath);
        }

        private static void SkipConfigAndWriteReport(Day4PlayModeSmokeReport report, string reportPath, string reason)
        {
            report.status = "skipped_config_required";
            report.error = reason;
            WriteSmokeReport(report, reportPath);
            Debug.LogWarning("[Week6Day4StudentInferenceDryRun] " + reason + " | report=" + reportPath);
        }

        private bool ResolveRuntimeReferences()
        {
            _gridManager = GridManager.Instance
                           ?? FindFirstObjectByType<GridManager>(FindObjectsInactive.Include)
                           ?? EnsureSceneComponent<GridManager>("GridManager");

            _unitRegistry = UnitRegistry.Instance
                            ?? FindFirstObjectByType<UnitRegistry>(FindObjectsInactive.Include)
                            ?? EnsureSceneComponent<UnitRegistry>("UnitRegistry");

            _matchManager = MatchManager.Instance
                            ?? FindFirstObjectByType<MatchManager>(FindObjectsInactive.Include)
                            ?? EnsureSceneComponent<MatchManager>("MatchManager");

            _matchBootstrap = MatchBootstrap.Instance
                              ?? FindFirstObjectByType<MatchBootstrap>(FindObjectsInactive.Include)
                              ?? EnsureSceneComponent<MatchBootstrap>("MatchBootstrap");

            _resourceManager = ResourceManager.Instance
                               ?? FindFirstObjectByType<ResourceManager>(FindObjectsInactive.Include)
                               ?? EnsureSceneComponent<ResourceManager>("ResourceManager");

            if (_gridManager == null || _unitRegistry == null || _matchManager == null)
            {
                return false;
            }

            _observationBuilder = new ObservationBuilder(_gridManager, _unitRegistry, _resourceManager);
            _pipeline = new MlPolicyPipelineFacade(
                _gridManager,
                _unitRegistry,
                _resourceManager,
                _matchManager,
                _matchBootstrap);

            return true;
        }

        private static T EnsureSceneComponent<T>(string gameObjectName) where T : Component
        {
            T existing = FindFirstObjectByType<T>(FindObjectsInactive.Include);
            if (existing != null)
            {
                return existing;
            }

            GameObject host = GameObject.Find(gameObjectName);
            if (host == null)
            {
                host = new GameObject(gameObjectName);
            }

            T component = host.GetComponent<T>();
            if (component == null)
            {
                component = host.AddComponent<T>();
            }

            return component;
        }

        private static string ResolveProjectRoot()
        {
            string assetsPath = Application.dataPath;
            if (string.IsNullOrWhiteSpace(assetsPath))
            {
                return string.Empty;
            }

            DirectoryInfo assetsDir = new DirectoryInfo(assetsPath);
            return assetsDir.Parent != null ? assetsDir.Parent.FullName : string.Empty;
        }

        private static string Quote(string value)
        {
            return "\"" + value + "\"";
        }

        private static bool RunProcess(
            string fileName,
            string arguments,
            string workingDirectory,
            out string stdout,
            out string stderr,
            out int exitCode)
        {
            stdout = string.Empty;
            stderr = string.Empty;
            exitCode = -1;

            try
            {
                var startInfo = new ProcessStartInfo
                {
                    FileName = fileName,
                    Arguments = arguments,
                    WorkingDirectory = workingDirectory,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true,
                };

                using var process = new Process { StartInfo = startInfo };
                process.Start();

                stdout = process.StandardOutput.ReadToEnd();
                stderr = process.StandardError.ReadToEnd();

                process.WaitForExit();
                exitCode = process.ExitCode;
                return true;
            }
            catch (Exception ex)
            {
                stderr = ex.ToString();
                return false;
            }
        }

        private static void WriteFloat32Buffer(float[] values, string path)
        {
            using var stream = new FileStream(path, FileMode.Create, FileAccess.Write, FileShare.None);
            using var writer = new BinaryWriter(stream);
            for (int i = 0; i < values.Length; i++)
            {
                writer.Write(values[i]);
            }
        }

        private static void WriteSmokeReport(Day4PlayModeSmokeReport report, string reportPath)
        {
            try
            {
                string parentDir = Path.GetDirectoryName(reportPath);
                if (!string.IsNullOrWhiteSpace(parentDir))
                {
                    Directory.CreateDirectory(parentDir);
                }

                string json = JsonUtility.ToJson(report, true);
                File.WriteAllText(reportPath, json);
            }
            catch (Exception ex)
            {
                Debug.LogWarning("[Week6Day4StudentInferenceDryRun] Failed to write smoke report: " + ex.Message);
            }
        }

        private static bool ValidateAdapterPayload(AdapterResult adapter, out string error)
        {
            error = string.Empty;

            if (adapter.observation_shape == null || adapter.observation_shape.Length != 3)
            {
                error = "Adapter did not return observation_shape [H,W,C]";
                return false;
            }

            if (adapter.observation_shape[0] != ObservationContract.GridH
                || adapter.observation_shape[1] != ObservationContract.GridW
                || adapter.observation_shape[2] != ObservationContract.ChannelsPerCell)
            {
                error =
                    "Observation shape mismatch from adapter. " +
                    $"Expected [{ObservationContract.GridH},{ObservationContract.GridW},{ObservationContract.ChannelsPerCell}], " +
                    $"got [{adapter.observation_shape[0]},{adapter.observation_shape[1]},{adapter.observation_shape[2]}]";
                return false;
            }

            if (!string.Equals(adapter.observation_dtype, "float32", StringComparison.OrdinalIgnoreCase))
            {
                error = "Observation dtype mismatch from adapter. " +
                        $"Expected float32, got {adapter.observation_dtype}";
                return false;
            }

            string[] expectedBranchOrder =
            {
                "action_type",
                "move_dir",
                "harvest_dir",
                "return_dir",
                "produce_dir",
                "produce_unit_type",
                "attack_target_local",
            };

            if (adapter.branch_order == null || adapter.branch_order.Length != expectedBranchOrder.Length)
            {
                error = "Adapter branch_order is missing or malformed";
                return false;
            }

            for (int i = 0; i < expectedBranchOrder.Length; i++)
            {
                if (!string.Equals(adapter.branch_order[i], expectedBranchOrder[i], StringComparison.Ordinal))
                {
                    error =
                        "Branch order mismatch. " +
                        $"index={i}, expected={expectedBranchOrder[i]}, got={adapter.branch_order[i]}";
                    return false;
                }
            }

            int[] expectedBranchSizes =
            {
                ActionContract.SIZE_ACTION_TYPE,
                ActionContract.SIZE_DIRECTION,
                ActionContract.SIZE_DIRECTION,
                ActionContract.SIZE_DIRECTION,
                ActionContract.SIZE_DIRECTION,
                ActionContract.SIZE_PRODUCE_UNIT_TYPE,
                ActionContract.SIZE_ATTACK_TARGET,
            };

            if (adapter.branch_sizes == null || adapter.branch_sizes.Length != expectedBranchSizes.Length)
            {
                error = "Adapter branch_sizes are missing or malformed";
                return false;
            }

            for (int i = 0; i < expectedBranchSizes.Length; i++)
            {
                if (adapter.branch_sizes[i] != expectedBranchSizes[i])
                {
                    bool isLegacyV1 =
                        adapter.branch_sizes.Length == 7
                        && adapter.branch_sizes[0] == 6
                        && adapter.branch_sizes[1] == 4
                        && adapter.branch_sizes[2] == 4
                        && adapter.branch_sizes[3] == 4
                        && adapter.branch_sizes[4] == 4
                        && adapter.branch_sizes[5] == 4
                        && adapter.branch_sizes[6] == 9;

                    if (isLegacyV1)
                    {
                        error = "v1 action contract artifact is incompatible with Unity v2 runtime";
                        return false;
                    }

                    error =
                        "Branch size mismatch. " +
                        $"index={i}, expected={expectedBranchSizes[i]}, got={adapter.branch_sizes[i]}";
                    return false;
                }
            }

            if (!string.Equals(adapter.action_contract_version, ExpectedActionContractVersion, StringComparison.Ordinal))
            {
                error =
                    "action_contract_version mismatch. " +
                    $"Expected {ExpectedActionContractVersion}, got {adapter.action_contract_version}";
                return false;
            }

            if (adapter.action_flat == null)
            {
                error = "Adapter action_flat is null";
                return false;
            }

            if (adapter.action_flat_size != ActionContract.TotalActionFlatSize)
            {
                error =
                    "action_flat_size mismatch. " +
                    $"Expected {ActionContract.TotalActionFlatSize}, got {adapter.action_flat_size}";
                return false;
            }

            if (adapter.action_flat.Length != ActionContract.TotalActionFlatSize)
            {
                error =
                    "action_flat array length mismatch. " +
                    $"Expected {ActionContract.TotalActionFlatSize}, got {adapter.action_flat.Length}";
                return false;
            }

            return true;
        }

        private static void TryReadAdapterFailureSummary(string adapterResultPath, out string status, out string error)
        {
            status = string.Empty;
            error = string.Empty;

            try
            {
                string jsonText = File.ReadAllText(adapterResultPath);
                AdapterResult adapter = JsonUtility.FromJson<AdapterResult>(jsonText);
                if (adapter == null)
                {
                    status = "parse_null";
                    error = "adapter output JSON parsed to null";
                    return;
                }

                status = adapter.status ?? string.Empty;
                error = adapter.error ?? string.Empty;
            }
            catch (Exception ex)
            {
                status = "parse_error";
                error = ex.Message;
            }
        }

        private static bool IsLikelyV1CheckpointHeadMismatch(string error)
        {
            if (string.IsNullOrWhiteSpace(error))
            {
                return false;
            }

            return error.Contains("produce_unit_type_head.weight", StringComparison.Ordinal)
                   && error.Contains("torch.Size([4", StringComparison.Ordinal)
                   && error.Contains("torch.Size([7", StringComparison.Ordinal)
                   && error.Contains("attack_target_local_head.weight", StringComparison.Ordinal)
                   && error.Contains("torch.Size([9", StringComparison.Ordinal)
                   && error.Contains("torch.Size([49", StringComparison.Ordinal);
        }
    }
}
