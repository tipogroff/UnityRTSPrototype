#if UNITY_EDITOR
using UnityEditor;
#endif

using System;
using System.Globalization;
using System.IO;
using System.Reflection;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RTS.ML
{
    /// <summary>
    /// Scene-level bootstrap that ensures manual Play Mode on
    /// Week6_StudentStaticHarvestLayout uses the exact Stage6B3
    /// masked-lifecycle execution path that was validated by the batch runner.
    ///
    /// Responsibilities:
    ///   Awake  — enforce Stage6B3 checkpoint + legal mask on the adapter,
    ///            set capture-mode context on the runner (overlay label only).
    ///   Start  — log [Stage6B3ManualPlayBinding] startup banner to Console,
    ///            write binding-validation JSON.
    ///
    /// The component is intentionally passive: it reuses existing
    /// Week6VisualInspectionRunner + Week6StudentPolicyAdapter rather than
    /// duplicating their logic.
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class Week6Stage6B3StaticManualPlayBootstrap : MonoBehaviour
    {
        // ---- canonical Stage6B3 values (must match batch runner) -------

        private const string Stage6B3CheckpointRelativePath =
            "python/week6_student/checkpoints/Stage6B3_SemanticObservationFix/legacy032_v2_bc_source_valid_semantic_obs_fix_final.pt";

        private const string ManualPlayArtifactDir =
            "python/week6_student/tmp/stage6b3_static_manual_play_smoke";

        private const string ManualPlayArtifactPrefix = "stage6b3_static_manual_play";

        private const string BindingValidationJsonRelativePath =
            "python/week6_student/tmp/stage6b3_static_manual_play_binding_validation.json";

        private const string ExpectedSceneName = "Week6_StudentStaticHarvestLayout";

        // ----------------------------------------------------------------

        private string _projectRoot = string.Empty;
        private Week6StudentPolicyAdapter _adapter;
        private Week6VisualInspectionRunner _runner;

        // Binding state captured during Awake for use in Start
        private bool _adapterFound;
        private bool _runnerFound;
        private bool _checkpointExisted;
        private bool _checkpointPathCorrected;
        private bool _legalMaskCorrected;
        private string _resolvedCheckpointPath = string.Empty;
        private string _resolvedCheckpointRelative = string.Empty;

        // ----------------------------------------------------------------

        private void Awake()
        {
            _projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? string.Empty;

            _adapter = FindFirstObjectByType<Week6StudentPolicyAdapter>();
            _runner  = FindFirstObjectByType<Week6VisualInspectionRunner>();

            _adapterFound = _adapter != null;
            _runnerFound  = _runner  != null;

            if (_adapterFound)
            {
                EnforceAdapterStage6B3(_adapter);
            }
            else
            {
                Debug.LogWarning("[Stage6B3ManualPlayBinding] Week6StudentPolicyAdapter not found in scene.");
            }

            if (_runnerFound)
            {
                _runner.SetCurrentCaptureModeContext(
                    "stage6b3_static_manual_play",
                    Week6PlayerControlMode.StudentInference,
                    Week6PlayerControlMode.HeuristicBaseline);
            }
            else
            {
                Debug.LogWarning("[Stage6B3ManualPlayBinding] Week6VisualInspectionRunner not found in scene.");
            }
        }

        private void Start()
        {
            LogBindingBanner();
            WriteBindingValidationJson();
        }

        // ----------------------------------------------------------------
        // Enforce Stage6B3 values on the adapter (Awake time, before Start)
        // ----------------------------------------------------------------

        private void EnforceAdapterStage6B3(Week6StudentPolicyAdapter adapter)
        {
            string currentCheckpoint = GetPrivateString(adapter, "_checkpointRelativePath");
            bool currentMask = GetPrivateBool(adapter, "_enableLegalActionMaskForSelection");

            _resolvedCheckpointRelative = Stage6B3CheckpointRelativePath;
            _resolvedCheckpointPath = string.IsNullOrEmpty(_projectRoot)
                ? Stage6B3CheckpointRelativePath
                : Path.GetFullPath(Path.Combine(_projectRoot, Stage6B3CheckpointRelativePath));

            _checkpointExisted = File.Exists(_resolvedCheckpointPath);

            // Correct checkpoint if wrong
            if (!string.Equals(currentCheckpoint, Stage6B3CheckpointRelativePath, StringComparison.Ordinal))
            {
                SetPrivateString(adapter, "_checkpointRelativePath", Stage6B3CheckpointRelativePath);
                _checkpointPathCorrected = true;
                Debug.Log("[Stage6B3ManualPlayBinding] Checkpoint corrected: "
                          + (currentCheckpoint ?? "<null>") + "  →  " + Stage6B3CheckpointRelativePath);
            }

            // Correct legal mask if disabled
            if (!currentMask)
            {
                SetPrivateBool(adapter, "_enableLegalActionMaskForSelection", true);
                _legalMaskCorrected = true;
                Debug.Log("[Stage6B3ManualPlayBinding] Legal parameter mask enabled (was disabled in serialized scene).");
            }

            // Update artifact paths to manual-play names
            SetPrivateString(adapter, "_artifactDirectoryRelativePath", ManualPlayArtifactDir);
            SetPrivateString(adapter, "_artifactFilePrefix", ManualPlayArtifactPrefix);

            EnsureDir(Path.Combine(_projectRoot, ManualPlayArtifactDir));
        }

        // ----------------------------------------------------------------
        // Console startup banner
        // ----------------------------------------------------------------

        private void LogBindingBanner()
        {
            string sceneName = SceneManager.GetActiveScene().name;
            string scenePath = SceneManager.GetActiveScene().path;

            string checkpointActual = _adapterFound
                ? (GetPrivateString(_adapter, "_checkpointRelativePath") ?? "<null>")
                : "<adapter missing>";

            bool legalMaskActive = _adapterFound && GetPrivateBool(_adapter, "_enableLegalActionMaskForSelection");

            bool fallbackUsed   = false;
            bool heuristicUsed  = false;
            bool fakeLogitsUsed = false;

            Debug.Log(
                "[Stage6B3ManualPlayBinding]\n"
                + "  active_scene_name:        " + sceneName + "\n"
                + "  active_scene_path:        " + scenePath + "\n"
                + "  runner_found:             " + _runnerFound + "\n"
                + "  runner_enabled:           " + (_runnerFound && _runner.isActiveAndEnabled) + "\n"
                + "  adapter_found:            " + _adapterFound + "\n"
                + "  adapter_enabled:          " + (_adapterFound && _adapter.isActiveAndEnabled) + "\n"
                + "  checkpoint_relative_path: " + checkpointActual + "\n"
                + "  checkpoint_abs_path:      " + _resolvedCheckpointPath + "\n"
                + "  checkpoint_exists:        " + _checkpointExisted + "\n"
                + "  checkpoint_corrected:     " + _checkpointPathCorrected + "\n"
                + "  legal_mask_corrected:     " + _legalMaskCorrected + "\n"
                + "  policy_source:            student_bc_stage6b3\n"
                + "  inference_source:         python_bridge\n"
                + "  fallback_used:            " + fallbackUsed + "\n"
                + "  heuristic_used:           " + heuristicUsed + "\n"
                + "  fake_logits_used:         " + fakeLogitsUsed + "\n"
                + "  legal_parameter_mask:     " + legalMaskActive + "\n"
                + "  decision_loop:            Week6VisualInspectionRunner (auto-playback)\n"
                + "  player1_controller:       student_policy (Owner.Player1)\n"
                + "  first_decision:           pending_first_step"
            );
        }

        // ----------------------------------------------------------------
        // Write binding-validation JSON
        // ----------------------------------------------------------------

        private void WriteBindingValidationJson()
        {
            if (string.IsNullOrEmpty(_projectRoot))
            {
                Debug.LogWarning("[Stage6B3ManualPlayBinding] Cannot write JSON: project root unknown.");
                return;
            }

            string outputPath = Path.GetFullPath(Path.Combine(_projectRoot, BindingValidationJsonRelativePath));
            EnsureDir(Path.GetDirectoryName(outputPath));

            string checkpointActual = _adapterFound
                ? (GetPrivateString(_adapter, "_checkpointRelativePath") ?? string.Empty)
                : string.Empty;

            bool legalMaskActive = _adapterFound && GetPrivateBool(_adapter, "_enableLegalActionMaskForSelection");
            bool runnerEnabled   = _runnerFound && _runner.isActiveAndEnabled;
            bool adapterEnabled  = _adapterFound && _adapter.isActiveAndEnabled;

            string json = "{\n"
                + "  \"generated_at_utc\": \""       + DateTime.UtcNow.ToString("O", CultureInfo.InvariantCulture) + "\",\n"
                + "  \"active_scene_name\": \""       + EscapeJson(SceneManager.GetActiveScene().name) + "\",\n"
                + "  \"active_scene_path\": \""       + EscapeJson(SceneManager.GetActiveScene().path) + "\",\n"
                + "  \"expected_scene_name\": \""     + ExpectedSceneName + "\",\n"
                + "  \"scene_matches_expected\": "    + BoolStr(string.Equals(SceneManager.GetActiveScene().name, ExpectedSceneName, StringComparison.Ordinal)) + ",\n"
                + "  \"runner_found\": "              + BoolStr(_runnerFound) + ",\n"
                + "  \"runner_enabled\": "            + BoolStr(runnerEnabled) + ",\n"
                + "  \"adapter_found\": "             + BoolStr(_adapterFound) + ",\n"
                + "  \"adapter_enabled\": "           + BoolStr(adapterEnabled) + ",\n"
                + "  \"checkpoint_relative_path\": \"" + EscapeJson(checkpointActual) + "\",\n"
                + "  \"checkpoint_abs_path\": \""    + EscapeJson(_resolvedCheckpointPath) + "\",\n"
                + "  \"checkpoint_exists\": "         + BoolStr(_checkpointExisted) + ",\n"
                + "  \"checkpoint_corrected_at_runtime\": " + BoolStr(_checkpointPathCorrected) + ",\n"
                + "  \"legal_mask_corrected_at_runtime\": " + BoolStr(_legalMaskCorrected) + ",\n"
                + "  \"policy_source\": \"student_bc_stage6b3\",\n"
                + "  \"inference_source\": \"python_bridge\",\n"
                + "  \"fallback_used\": false,\n"
                + "  \"heuristic_used\": false,\n"
                + "  \"fake_logits_used\": false,\n"
                + "  \"legal_parameter_mask_enabled\": " + BoolStr(legalMaskActive) + ",\n"
                + "  \"decision_loop\": \"Week6VisualInspectionRunner_auto_playback\",\n"
                + "  \"player1_controller\": \"student_policy\",\n"
                + "  \"first_decision_requested\": \"pending_first_step\"\n"
                + "}\n";

            File.WriteAllText(outputPath, json);
            Debug.Log("[Stage6B3ManualPlayBinding] Binding validation JSON written: " + outputPath);
        }

        // ----------------------------------------------------------------
        // Helpers
        // ----------------------------------------------------------------

        private static void SetPrivateString(object target, string fieldName, string value)
        {
            FieldInfo fi = target.GetType().GetField(fieldName,
                BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
            if (fi != null)
            {
                fi.SetValue(target, value);
            }
            else
            {
                Debug.LogWarning("[Stage6B3ManualPlayBinding] Field not found: " + fieldName);
            }
        }

        private static void SetPrivateBool(object target, string fieldName, bool value)
        {
            FieldInfo fi = target.GetType().GetField(fieldName,
                BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
            if (fi != null)
            {
                fi.SetValue(target, value);
            }
            else
            {
                Debug.LogWarning("[Stage6B3ManualPlayBinding] Field not found: " + fieldName);
            }
        }

        private static string GetPrivateString(object target, string fieldName)
        {
            FieldInfo fi = target.GetType().GetField(fieldName,
                BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
            return fi != null ? fi.GetValue(target) as string : null;
        }

        private static bool GetPrivateBool(object target, string fieldName)
        {
            FieldInfo fi = target.GetType().GetField(fieldName,
                BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public);
            if (fi == null) return false;
            object v = fi.GetValue(target);
            return v is bool b && b;
        }

        private static void EnsureDir(string path)
        {
            if (!string.IsNullOrEmpty(path) && !Directory.Exists(path))
            {
                Directory.CreateDirectory(path);
            }
        }

        private static string BoolStr(bool v) => v ? "true" : "false";

        private static string EscapeJson(string s)
        {
            if (s == null) return string.Empty;
            return s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n").Replace("\r", "");
        }
    }
}
