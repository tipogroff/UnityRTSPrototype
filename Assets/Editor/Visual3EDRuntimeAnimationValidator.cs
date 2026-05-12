using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using RTS.Gameplay;
using RTS.Presentation;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;

public static class Visual3EDRuntimeAnimationValidator
{
    private const string ValidationMdPath = "Assets/Visual3ED_RuntimeAnimationValidation.md";
    private const string ValidationJsonPath = "Assets/Visual3ED_RuntimeAnimationValidation.json";
    private const string TraceJsonlPath = "Assets/Visual3ED_RuntimeAnimationTrace.jsonl";

    private static readonly string[] PrefabPaths =
    {
        "Assets/Prefabs/Worker.prefab",
        "Assets/Prefabs/Light.prefab",
        "Assets/Prefabs/Heavy.prefab",
        "Assets/Prefabs/Ranged.prefab"
    };

    private static readonly Dictionary<string, AnimatorControllerParameterType> RequiredParameters =
        new Dictionary<string, AnimatorControllerParameterType>(StringComparer.Ordinal)
        {
            { "IsMoving", AnimatorControllerParameterType.Bool },
            { "Attack", AnimatorControllerParameterType.Trigger },
            { "Harvest", AnimatorControllerParameterType.Trigger },
            { "Death", AnimatorControllerParameterType.Trigger }
        };

    [MenuItem("RTS/Presentation/Visual-3E-D/Run Runtime Animation Validation")]
    public static void RunValidation()
    {
        var report = new ValidationReport
        {
            generatedUtc = DateTime.UtcNow.ToString("O"),
            inPlayMode = EditorApplication.isPlaying
        };

        ValidateAnimatorWiring(report);
        RunManualTriggerTest(report);
        RunTraceCheck(report);

        WriteValidationArtifacts(report);
        AssetDatabase.Refresh();

        Debug.Log("[Visual3EDRuntimeAnimationValidator] Validation completed. Artifacts: " + ValidationMdPath + ", " + ValidationJsonPath);
    }

    [MenuItem("RTS/Presentation/Visual-3E-D/Reset Runtime Animation Trace")]
    public static void ResetTrace()
    {
        Visual3EDRuntimeAnimationTrace.Reset("Editor reset command");
        AssetDatabase.Refresh();
        Debug.Log("[Visual3EDRuntimeAnimationValidator] Runtime trace reset.");
    }

    private static void ValidateAnimatorWiring(ValidationReport report)
    {
        foreach (string prefabPath in PrefabPaths)
        {
            var entry = new WiringEntry { prefabPath = prefabPath };

            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
            if (prefab == null)
            {
                entry.ok = false;
                entry.notes.Add("Prefab missing.");
                report.wiring.Add(entry);
                continue;
            }

            var animator = prefab.GetComponentInChildren<Animator>(true);
            var visualAnimator = prefab.GetComponentInChildren<UnitVisualAnimator>(true);

            if (animator == null)
            {
                entry.ok = false;
                entry.notes.Add("Animator missing.");
            }

            if (visualAnimator == null)
            {
                entry.ok = false;
                entry.notes.Add("UnitVisualAnimator missing.");
            }

            if (visualAnimator != null)
            {
                var serialized = new SerializedObject(visualAnimator);
                var prop = serialized.FindProperty("animator");
                entry.visualAnimatorReferenceAssigned = prop != null && prop.objectReferenceValue != null;
                if (!entry.visualAnimatorReferenceAssigned)
                {
                    entry.ok = false;
                    entry.notes.Add("UnitVisualAnimator.animator reference is not assigned.");
                }
            }

            var controller = animator != null ? animator.runtimeAnimatorController as AnimatorController : null;
            if (controller == null)
            {
                entry.ok = false;
                entry.notes.Add("AnimatorController missing or not AnimatorController.");
            }
            else
            {
                foreach (var pair in RequiredParameters)
                {
                    bool found = false;
                    foreach (var p in controller.parameters)
                    {
                        if (p.name == pair.Key)
                        {
                            found = p.type == pair.Value;
                            if (!found)
                            {
                                entry.ok = false;
                                entry.notes.Add("Parameter type mismatch: " + pair.Key + " expected=" + pair.Value + " actual=" + p.type);
                            }
                            break;
                        }
                    }

                    if (!found)
                    {
                        entry.ok = false;
                        entry.notes.Add("Required parameter missing: " + pair.Key);
                    }
                }
            }

            report.wiring.Add(entry);
        }
    }

    private static void RunManualTriggerTest(ValidationReport report)
    {
        var result = new ManualTriggerResult
        {
            executed = EditorApplication.isPlaying
        };

        if (!EditorApplication.isPlaying)
        {
            result.notes.Add("Skipped: Editor is not in Play Mode.");
            report.manualTrigger = result;
            return;
        }

        var units = UnityEngine.Object.FindObjectsByType<UnitRuntime>(FindObjectsSortMode.None);
        foreach (var unit in units)
        {
            if (unit == null || !unit.isActiveAndEnabled)
            {
                continue;
            }

            var bridge = unit.GetComponent<VisualEventBridge>()
                         ?? unit.GetComponentInParent<VisualEventBridge>(true)
                         ?? unit.GetComponentInChildren<VisualEventBridge>(true);
            if (bridge == null)
            {
                continue;
            }

            bridge.SetRuntimeTraceEnabled(true);
            bridge.PulseMoving(0.2f);
            bridge.OnVisualAttack();
            bridge.OnVisualHarvest();

            result.pulsedMove++;
            result.triggeredAttack++;
            result.triggeredHarvest++;
            result.unitsTouched++;
        }

        if (result.unitsTouched == 0)
        {
            result.notes.Add("No active UnitRuntime with VisualEventBridge found in scene.");
        }

        report.manualTrigger = result;
    }

    private static void RunTraceCheck(ValidationReport report)
    {
        var trace = new TraceCheckResult();
        string fullPath = Path.GetFullPath(TraceJsonlPath);

        if (!File.Exists(fullPath))
        {
            trace.notes.Add("Trace JSONL is missing: " + TraceJsonlPath);
            report.traceCheck = trace;
            return;
        }

        string[] lines = File.ReadAllLines(fullPath);
        trace.lineCount = lines.Length;

        foreach (string line in lines)
        {
            if (line.IndexOf("\"visual_event\":\"MoveStart\"", StringComparison.Ordinal) >= 0) trace.hasMove = true;
            if (line.IndexOf("\"visual_event\":\"Attack\"", StringComparison.Ordinal) >= 0) trace.hasAttack = true;
            if (line.IndexOf("\"visual_event\":\"Harvest\"", StringComparison.Ordinal) >= 0) trace.hasHarvest = true;
            if (line.IndexOf("\"visual_event\":\"Death\"", StringComparison.Ordinal) >= 0) trace.hasDeath = true;
        }

        if (!trace.hasMove) trace.notes.Add("MoveStart not observed in trace.");
        if (!trace.hasAttack) trace.notes.Add("Attack not observed in trace.");
        if (!trace.hasHarvest) trace.notes.Add("Harvest not observed in trace.");
        if (!trace.hasDeath) trace.notes.Add("Death not observed in trace.");

        report.traceCheck = trace;
    }

    private static void WriteValidationArtifacts(ValidationReport report)
    {
        string json = JsonUtility.ToJson(report, true);
        File.WriteAllText(Path.GetFullPath(ValidationJsonPath), json, Encoding.UTF8);

        var sb = new StringBuilder(1024);
        sb.AppendLine("# Visual-3E-D Runtime Animation Validation");
        sb.AppendLine();
        sb.AppendLine("- Generated UTC: " + report.generatedUtc);
        sb.AppendLine("- Play Mode: " + report.inPlayMode);
        sb.AppendLine();
        sb.AppendLine("## Animator Wiring");

        foreach (var entry in report.wiring)
        {
            sb.AppendLine("- " + entry.prefabPath + " => " + (entry.ok ? "OK" : "FAIL"));
            foreach (var note in entry.notes)
            {
                sb.AppendLine("  - " + note);
            }
        }

        sb.AppendLine();
        sb.AppendLine("## Manual Trigger Test");
        sb.AppendLine("- Executed: " + report.manualTrigger.executed);
        sb.AppendLine("- Units touched: " + report.manualTrigger.unitsTouched);
        sb.AppendLine("- Move pulses: " + report.manualTrigger.pulsedMove);
        sb.AppendLine("- Attack triggers: " + report.manualTrigger.triggeredAttack);
        sb.AppendLine("- Harvest triggers: " + report.manualTrigger.triggeredHarvest);
        foreach (var note in report.manualTrigger.notes)
        {
            sb.AppendLine("- Note: " + note);
        }

        sb.AppendLine();
        sb.AppendLine("## Trace Check");
        sb.AppendLine("- Trace file: " + TraceJsonlPath);
        sb.AppendLine("- Lines: " + report.traceCheck.lineCount);
        sb.AppendLine("- Move observed: " + report.traceCheck.hasMove);
        sb.AppendLine("- Attack observed: " + report.traceCheck.hasAttack);
        sb.AppendLine("- Harvest observed: " + report.traceCheck.hasHarvest);
        sb.AppendLine("- Death observed: " + report.traceCheck.hasDeath);
        foreach (var note in report.traceCheck.notes)
        {
            sb.AppendLine("- Note: " + note);
        }

        File.WriteAllText(Path.GetFullPath(ValidationMdPath), sb.ToString().Replace("\r\n", "\n"), Encoding.UTF8);
    }

    [Serializable]
    private sealed class ValidationReport
    {
        public string generatedUtc;
        public bool inPlayMode;
        public List<WiringEntry> wiring = new List<WiringEntry>();
        public ManualTriggerResult manualTrigger = new ManualTriggerResult();
        public TraceCheckResult traceCheck = new TraceCheckResult();
    }

    [Serializable]
    private sealed class WiringEntry
    {
        public string prefabPath;
        public bool ok = true;
        public bool visualAnimatorReferenceAssigned;
        public List<string> notes = new List<string>();
    }

    [Serializable]
    private sealed class ManualTriggerResult
    {
        public bool executed;
        public int unitsTouched;
        public int pulsedMove;
        public int triggeredAttack;
        public int triggeredHarvest;
        public List<string> notes = new List<string>();
    }

    [Serializable]
    private sealed class TraceCheckResult
    {
        public int lineCount;
        public bool hasMove;
        public bool hasAttack;
        public bool hasHarvest;
        public bool hasDeath;
        public List<string> notes = new List<string>();
    }
}
