#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEngine;

namespace RTS.ML
{
    public static class ActionContractV2GlobalSmokeRunner
    {
        private const string MenuPath = "SmokeTest/11 - Unity Action Contract v2 Full Evidence Smoke";
        private const string Tag = "[ActionContractV2GlobalSmokeRunner]";

        [Serializable]
        private sealed class Day4SmokeReport
        {
            public string status;
            public string error;
        }

        private enum SmokeStatus
        {
            PASS,
            FAIL,
            SKIPPED_WITH_REASON,
        }

        private readonly struct SmokeResult
        {
            public readonly string Name;
            public readonly SmokeStatus Status;
            public readonly string Detail;

            public SmokeResult(string name, SmokeStatus status, string detail)
            {
                Name = name;
                Status = status;
                Detail = detail;
            }
        }

        [MenuItem(MenuPath)]
        public static void Run()
        {
            var results = new List<SmokeResult>(5);
            GameObject host = null;
            bool hostCreated = false;

            try
            {
                host = UnityEngine.Object.FindFirstObjectByType<ActionContractV2SmokeTest>()?.gameObject;
                if (host == null)
                {
                    host = new GameObject("ActionContractV2GlobalSmokeRunner_AutoHost");
                    host.hideFlags = HideFlags.DontSave;
                    hostCreated = true;
                }

                results.Add(RunActionContractSmoke(host));
                results.Add(RunActionDecoderSmoke(host));
                results.Add(RunDay5ObservationSmoke(host));
                results.Add(RunDay4DryRunSmoke(host));
                results.Add(RunWeek6AdapterContractSmoke(host));
            }
            finally
            {
                if (hostCreated && host != null)
                {
                    UnityEngine.Object.DestroyImmediate(host);
                }
            }

            PrintSummary(results);
        }

        private static SmokeResult RunActionContractSmoke(GameObject host)
        {
            const string name = "ActionContractV2SmokeTest.Run";
            var component = GetOrCreateComponent<ActionContractV2SmokeTest>(host);

            using var capture = new LogCapture("[ActionContractV2SmokeTest]");
            try
            {
                component.Run();
            }
            catch (Exception ex)
            {
                return new SmokeResult(name, SmokeStatus.FAIL, "Exception: " + ex.Message);
            }

            return capture.HasError
                ? new SmokeResult(name, SmokeStatus.FAIL, capture.FirstError)
                : new SmokeResult(name, SmokeStatus.PASS, "Contract constants/mappings validated.");
        }

        private static SmokeResult RunActionDecoderSmoke(GameObject host)
        {
            const string name = "ActionDecoderV2SmokeTest.Run";
            var component = GetOrCreateComponent<ActionDecoderV2SmokeTest>(host);

            using var capture = new LogCapture("[ActionDecoderV2SmokeTest]");
            try
            {
                component.Run();
            }
            catch (Exception ex)
            {
                return new SmokeResult(name, SmokeStatus.FAIL, "Exception: " + ex.Message);
            }

            return capture.HasError
                ? new SmokeResult(name, SmokeStatus.FAIL, capture.FirstError)
                : new SmokeResult(name, SmokeStatus.PASS, "Decoder branch/attack-index checks validated.");
        }

        private static SmokeResult RunDay5ObservationSmoke(GameObject host)
        {
            const string name = "Day5AttackTargetObservationSmokeTest.RunChecks";

            if (!Application.isPlaying)
            {
                return new SmokeResult(name, SmokeStatus.SKIPPED_WITH_REASON, "Requires Play Mode runtime managers.");
            }

            RTS.Gameplay.GridManager grid = RTS.Gameplay.GridManager.Instance
                ?? UnityEngine.Object.FindFirstObjectByType<RTS.Gameplay.GridManager>(FindObjectsInactive.Include);
            RTS.Gameplay.UnitRegistry registry = RTS.Gameplay.UnitRegistry.Instance
                ?? UnityEngine.Object.FindFirstObjectByType<RTS.Gameplay.UnitRegistry>(FindObjectsInactive.Include);
            RTS.Gameplay.ResourceManager resources = RTS.Gameplay.ResourceManager.Instance
                ?? UnityEngine.Object.FindFirstObjectByType<RTS.Gameplay.ResourceManager>(FindObjectsInactive.Include);

            if (grid == null || registry == null || resources == null)
            {
                return new SmokeResult(name, SmokeStatus.SKIPPED_WITH_REASON, "Runtime managers missing (GridManager/UnitRegistry/ResourceManager).");
            }

            var component = GetOrCreateComponent<Day5AttackTargetObservationSmokeTest>(host);
            using var capture = new LogCapture("[Day5AttackTargetObservationSmokeTest]");
            try
            {
                component.RunChecks();
            }
            catch (Exception ex)
            {
                return new SmokeResult(name, SmokeStatus.FAIL, "Exception: " + ex.Message);
            }

            return capture.HasError
                ? new SmokeResult(name, SmokeStatus.FAIL, capture.FirstError)
                : new SmokeResult(name, SmokeStatus.PASS, "attack_target[26] observation checks validated.");
        }

        private static SmokeResult RunDay4DryRunSmoke(GameObject host)
        {
            const string name = "Week6Day4StudentInferenceDryRun.RunDryRun";

            if (!Application.isPlaying)
            {
                return new SmokeResult(name, SmokeStatus.SKIPPED_WITH_REASON, "Requires Play Mode for runtime references and canonical execute path.");
            }

            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? string.Empty;
            if (string.IsNullOrWhiteSpace(projectRoot))
            {
                return new SmokeResult(name, SmokeStatus.SKIPPED_WITH_REASON, "Cannot resolve project root from Application.dataPath.");
            }

            var component = GetOrCreateComponent<Week6Day4StudentInferenceDryRun>(host);

            string pythonRel = ReadPrivateStringField(component, "_pythonExecutableRelativePath", ".venv/Scripts/python.exe");
            string adapterRel = ReadPrivateStringField(component, "_adapterScriptRelativePath", "python/week6_student/student_action_adapter.py");
            string checkpointRel = ReadPrivateStringField(component, "_checkpointRelativePath", "python/week6_student/runs/legacy032_v2_bc_minimal_20260501T195501Z/student_bc_transfer_best.pt");
            string reportRel = ReadPrivateStringField(component, "_smokeReportRelativePath", "python/week6_student/tmp/day4_unity_playmode_smoke_report.json");

            string pythonAbs = Path.GetFullPath(Path.Combine(projectRoot, pythonRel));
            string adapterAbs = Path.GetFullPath(Path.Combine(projectRoot, adapterRel));
            string checkpointAbs = Path.GetFullPath(Path.Combine(projectRoot, checkpointRel));
            string reportAbs = Path.GetFullPath(Path.Combine(projectRoot, reportRel));

            if (!File.Exists(pythonAbs))
            {
                return new SmokeResult(name, SmokeStatus.SKIPPED_WITH_REASON, "Python executable not found: " + pythonAbs);
            }

            if (!File.Exists(adapterAbs))
            {
                return new SmokeResult(name, SmokeStatus.SKIPPED_WITH_REASON, "Adapter script not found: " + adapterAbs);
            }

            if (!File.Exists(checkpointAbs))
            {
                return new SmokeResult(name, SmokeStatus.SKIPPED_WITH_REASON, "Student checkpoint not found: " + checkpointAbs);
            }

            using var capture = new LogCapture("[Week6Day4StudentInferenceDryRun]");
            try
            {
                component.RunDryRun();
            }
            catch (Exception ex)
            {
                return new SmokeResult(name, SmokeStatus.FAIL, "Exception: " + ex.Message);
            }

            if (capture.HasError)
            {
                return new SmokeResult(name, SmokeStatus.FAIL, capture.FirstError);
            }

            if (!File.Exists(reportAbs))
            {
                return new SmokeResult(name, SmokeStatus.FAIL, "Smoke report not found after run: " + reportAbs);
            }

            Day4SmokeReport report;
            try
            {
                string json = File.ReadAllText(reportAbs);
                report = JsonUtility.FromJson<Day4SmokeReport>(json);
            }
            catch (Exception ex)
            {
                return new SmokeResult(name, SmokeStatus.FAIL, "Cannot parse smoke report JSON: " + ex.Message);
            }

            if (report == null)
            {
                return new SmokeResult(name, SmokeStatus.FAIL, "Smoke report JSON is empty.");
            }

            if (string.Equals(report.status, "skipped_config_required", StringComparison.OrdinalIgnoreCase))
            {
                string skipReason = string.IsNullOrWhiteSpace(report.error) ? "config-required skip" : report.error;
                return new SmokeResult(name, SmokeStatus.SKIPPED_WITH_REASON, skipReason);
            }

            if (!string.Equals(report.status, "pass", StringComparison.OrdinalIgnoreCase))
            {
                string reportError = string.IsNullOrWhiteSpace(report.error) ? "unknown error" : report.error;
                return new SmokeResult(name, SmokeStatus.FAIL, "Dry-run report status is not pass: " + reportError);
            }

            return new SmokeResult(name, SmokeStatus.PASS, "Day4 technical wiring dry-run passed.");
        }

        private static SmokeResult RunWeek6AdapterContractSmoke(GameObject host)
        {
            const string name = "Week6StudentPolicyAdapter.RunAdapterContractValidationSmokeForEvidence";
            var component = GetOrCreateComponent<Week6StudentPolicyAdapter>(host);

            try
            {
                bool passed = component.RunAdapterContractValidationSmokeForEvidence(out string detail);
                return passed
                    ? new SmokeResult(name, SmokeStatus.PASS, detail)
                    : new SmokeResult(name, SmokeStatus.FAIL, detail);
            }
            catch (Exception ex)
            {
                return new SmokeResult(name, SmokeStatus.FAIL, "Exception: " + ex.Message);
            }
        }

        private static string ReadPrivateStringField<T>(T component, string fieldName, string fallback) where T : Component
        {
            var field = typeof(T).GetField(fieldName, System.Reflection.BindingFlags.Instance | System.Reflection.BindingFlags.NonPublic);
            if (field == null)
            {
                return fallback;
            }

            object value = field.GetValue(component);
            return value as string ?? fallback;
        }

        private static T GetOrCreateComponent<T>(GameObject host) where T : Component
        {
            T existing = UnityEngine.Object.FindFirstObjectByType<T>(FindObjectsInactive.Include);
            if (existing != null)
            {
                return existing;
            }

            return host.AddComponent<T>();
        }

        private static void PrintSummary(List<SmokeResult> results)
        {
            int passCount = 0;
            int failCount = 0;
            int skippedCount = 0;

            Debug.Log(Tag + " ===== Unity Action Contract v2 Full Evidence Smoke =====");

            for (int i = 0; i < results.Count; i++)
            {
                SmokeResult row = results[i];
                if (row.Status == SmokeStatus.PASS)
                {
                    passCount++;
                }
                else if (row.Status == SmokeStatus.FAIL)
                {
                    failCount++;
                }
                else
                {
                    skippedCount++;
                }

                Debug.Log($"{Tag} RESULT | name={row.Name} | status={row.Status} | detail={row.Detail}");
            }

            Debug.Log($"{Tag} TOTAL | pass={passCount} | fail={failCount} | skipped={skippedCount}");
        }

        private sealed class LogCapture : IDisposable
        {
            private readonly string _tagFilter;

            public bool HasError { get; private set; }
            public string FirstError { get; private set; } = string.Empty;

            public LogCapture(string tagFilter)
            {
                _tagFilter = tagFilter;
                Application.logMessageReceived += HandleLog;
            }

            public void Dispose()
            {
                Application.logMessageReceived -= HandleLog;
            }

            private void HandleLog(string condition, string stackTrace, LogType type)
            {
                if (string.IsNullOrEmpty(condition) || !condition.Contains(_tagFilter, StringComparison.Ordinal))
                {
                    return;
                }

                if (type == LogType.Error || type == LogType.Exception || type == LogType.Assert)
                {
                    if (!HasError)
                    {
                        FirstError = condition;
                    }

                    HasError = true;
                }
            }
        }
    }
}
#endif
