using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using RTS.Gameplay;
using RTS.Presentation;
using UnityEditor;
using UnityEngine;

public static class Visual3FRAnimationAndSmoothMovementValidator
{
    private const string RegressionEvidenceMdPath = "Assets/Visual3FR_AnimationRegressionEvidence.md";
    private const string RegressionEvidenceJsonPath = "Assets/Visual3FR_AnimationRegressionEvidence.json";
    private const string ValidationMdPath = "Assets/Visual3FR_AnimationSmoothMovementValidation.md";
    private const string ValidationJsonPath = "Assets/Visual3FR_AnimationSmoothMovementValidation.json";
    private const string SmoothTracePath = "Assets/Visual3EF_SmoothMovementTrace.jsonl";

    private const int SampleDelayMs = 1000;

    [MenuItem("RTS/Presentation/Visual-3F-R/Capture Animation Regression Evidence (Play Mode)")]
    public static async void CaptureRegressionEvidence()
    {
        if (!EditorApplication.isPlaying)
        {
            Debug.LogWarning("[Visual3FR] Enter Play Mode before capturing regression evidence.");
            return;
        }

        var report = await BuildRegressionEvidenceAsync("CurrentPlayMode");
        WriteRegressionEvidenceArtifacts(report);
        AssetDatabase.Refresh();
        Debug.Log("[Visual3FR] Regression evidence written to " + RegressionEvidenceMdPath + " and " + RegressionEvidenceJsonPath);
    }

    [MenuItem("RTS/Presentation/Visual-3F-R/Run Animation+Smooth Validation (Play Mode)")]
    public static async void RunAnimationAndSmoothValidation()
    {
        if (!EditorApplication.isPlaying)
        {
            Debug.LogWarning("[Visual3FR] Enter Play Mode before running validation.");
            return;
        }

        var result = new ValidationReport
        {
            generatedUtc = DateTime.UtcNow.ToString("O")
        };

        ApplyInterpolationToRuntime(false, "Visual-3F-R mode A");
        await Task.Delay(150);
        result.modeA = await BuildRegressionEvidenceAsync("SmoothDisabled");

        ApplyInterpolationToRuntime(true, "Visual-3F-R mode B");
        await Task.Delay(150);
        result.modeB = await BuildRegressionEvidenceAsync("SmoothEnabled");

        result.trace = ReadSmoothTraceStats();
        result.summary = BuildSummary(result);

        WriteValidationArtifacts(result);
        AssetDatabase.Refresh();

        Debug.Log("[Visual3FR] Validation written to " + ValidationMdPath + " and " + ValidationJsonPath);
    }

    [MenuItem("RTS/Presentation/Visual-3F-R/Set Smooth Movement Disabled (Play Mode)")]
    public static void SetSmoothMovementDisabled()
    {
        if (!EditorApplication.isPlaying)
        {
            Debug.LogWarning("[Visual3FR] Enter Play Mode before toggling smooth movement.");
            return;
        }

        ApplyInterpolationToRuntime(false, "Manual toggle disabled");
        Debug.Log("[Visual3FR] Smooth movement disabled for active runtime interpolators.");
    }

    [MenuItem("RTS/Presentation/Visual-3F-R/Set Smooth Movement Enabled (Play Mode)")]
    public static void SetSmoothMovementEnabled()
    {
        if (!EditorApplication.isPlaying)
        {
            Debug.LogWarning("[Visual3FR] Enter Play Mode before toggling smooth movement.");
            return;
        }

        ApplyInterpolationToRuntime(true, "Manual toggle enabled");
        Debug.Log("[Visual3FR] Smooth movement enabled for active runtime interpolators.");
    }

    private static async Task<RegressionEvidenceReport> BuildRegressionEvidenceAsync(string mode)
    {
        var units = UnityEngine.Object.FindObjectsByType<UnitRuntime>(FindObjectsSortMode.None)
            .Where(u => u != null && u.gameObject.activeInHierarchy)
            .OrderBy(u => GetHierarchyPath(u.transform), StringComparer.Ordinal)
            .ToArray();

        var t0 = CaptureUnitSamples(units, mode, "t0");
        await Task.Delay(SampleDelayMs);
        var t1 = CaptureUnitSamples(units, mode, "t1");

        var merged = MergeUnitSamples(t0, t1);

        var report = new RegressionEvidenceReport
        {
            generatedUtc = DateTime.UtcNow.ToString("O"),
            mode = mode,
            unitCount = merged.Count,
            units = merged,
            summary = BuildRegressionSummary(merged)
        };

        return report;
    }

    private static List<UnitEvidence> CaptureUnitSamples(UnitRuntime[] units, string mode, string phase)
    {
        var list = new List<UnitEvidence>(units.Length);

        foreach (var unit in units)
        {
            var bridge = unit.GetComponent<VisualEventBridge>() ?? unit.GetComponentInChildren<VisualEventBridge>(true);
            var visualAnimator = unit.GetComponent<UnitVisualAnimator>() ?? unit.GetComponentInChildren<UnitVisualAnimator>(true);
            var interpolator = unit.GetComponent<VisualGridMovementInterpolator>() ?? unit.GetComponentInChildren<VisualGridMovementInterpolator>(true);
            var visualRoot = ResolveVisualRoot(unit.transform, interpolator);
            var animator = ResolveAnimator(visualAnimator, unit.transform);

            var evidence = new UnitEvidence
            {
                mode = mode,
                phase = phase,
                unitInstanceId = unit.GetInstanceID(),
                unitName = unit.name,
                gameObjectPath = GetHierarchyPath(unit.transform),
                unitType = unit.Type.ToString(),
                owner = unit.Owner.ToString(),
                modelNull = unit.Model == null,
                visualRootPath = visualRoot != null ? GetHierarchyPath(visualRoot) : string.Empty,
                visualRootLocalPosition = visualRoot != null ? visualRoot.localPosition : Vector3.zero,
                unitVisualAnimatorAnimatorPath = visualAnimator != null ? visualAnimator.GetAnimatorReferencePath() : string.Empty,
                interpolatorPresent = interpolator != null,
                interpolatorEnabled = interpolator != null && interpolator.enabled,
                interpolatorIsInterpolating = interpolator != null && interpolator.IsInterpolating,
                interpolatorCurrentVisualOffset = interpolator != null ? interpolator.CurrentVisualOffset : Vector3.zero,
                interpolatorSnapCount = interpolator != null ? interpolator.SnapCount : 0,
                interpolatorExcessiveSnapCount = interpolator != null ? interpolator.ExcessiveSnapCount : 0,
                interpolatorLastSnapFrame = interpolator != null ? interpolator.LastSnapFrame : -1,
                interpolatorLastSnapReason = interpolator != null ? interpolator.LastSnapReason : string.Empty,
                bridgeLastSetMovingValue = bridge != null && bridge.LastSetMovingValue,
                bridgeLastSetMovingFrame = bridge != null ? bridge.LastSetMovingFrame : -1,
                bridgeLastMoveStartFrame = bridge != null ? bridge.LastMoveStartFrame : -1,
                bridgeLastMoveEndFrame = bridge != null ? bridge.LastMoveEndFrame : -1,
                bridgeAnimatorMovingMatchesInterpolator = bridge == null || bridge.AnimatorMovingMatchesInterpolator
            };

            PopulateAnimatorEvidence(evidence, animator);
            PopulateTeamMarkerEvidence(evidence, visualRoot);
            list.Add(evidence);
        }

        return list;
    }

    private static void PopulateAnimatorEvidence(UnitEvidence evidence, Animator animator)
    {
        evidence.animatorExists = animator != null;
        if (animator == null)
        {
            return;
        }

        evidence.animatorPath = GetHierarchyPath(animator.transform);
        evidence.animatorEnabled = animator.enabled;
        evidence.animatorActiveInHierarchy = animator.gameObject.activeInHierarchy;
        evidence.animatorAvatarNull = animator.avatar == null;
        evidence.animatorCullingMode = animator.cullingMode.ToString();
        evidence.animatorUpdateMode = animator.updateMode.ToString();

        var controller = animator.runtimeAnimatorController;
        evidence.animatorControllerName = controller != null ? controller.name : string.Empty;
        evidence.animatorControllerPath = controller != null ? AssetDatabase.GetAssetPath(controller) : string.Empty;

        var state = animator.GetCurrentAnimatorStateInfo(0);
        evidence.currentStateHash = state.shortNameHash;
        evidence.currentStateNormalizedTime = state.normalizedTime;

        var clips = animator.GetCurrentAnimatorClipInfo(0);
        evidence.currentStateName = clips != null && clips.Length > 0 && clips[0].clip != null ? clips[0].clip.name : string.Empty;

        evidence.hasIsMovingParameter = HasParameter(animator, "IsMoving", AnimatorControllerParameterType.Bool);
        evidence.hasAttackTrigger = HasParameter(animator, "Attack", AnimatorControllerParameterType.Trigger);
        evidence.hasHarvestTrigger = HasParameter(animator, "Harvest", AnimatorControllerParameterType.Trigger);
        evidence.hasDeathTrigger = HasParameter(animator, "Death", AnimatorControllerParameterType.Trigger);

        if (evidence.hasIsMovingParameter)
        {
            evidence.isMovingValue = animator.GetBool("IsMoving");
        }

        var sampleTransform = ResolveBoneSampleTransform(animator.transform);
        evidence.sampleBonePath = sampleTransform != null ? GetHierarchyPath(sampleTransform) : string.Empty;
        evidence.sampleBoneWorldPosition = sampleTransform != null ? sampleTransform.position : Vector3.zero;
    }

    private static void PopulateTeamMarkerEvidence(UnitEvidence evidence, Transform visualRoot)
    {
        if (visualRoot == null)
        {
            return;
        }

        var marker = FindChildByName(visualRoot, "TeamMarker_Ring");
        if (marker == null)
        {
            return;
        }

        evidence.teamMarkerExists = true;
        evidence.teamMarkerPath = GetHierarchyPath(marker);
        evidence.teamMarkerActive = marker.gameObject.activeInHierarchy;
        evidence.teamMarkerAnchored = marker.parent == visualRoot;
    }

    private static List<UnitEvidence> MergeUnitSamples(List<UnitEvidence> t0, List<UnitEvidence> t1)
    {
        var merged = new List<UnitEvidence>(t0.Count);
        var byInstanceId = t1.ToDictionary(x => x.unitInstanceId);

        foreach (var first in t0)
        {
            if (!byInstanceId.TryGetValue(first.unitInstanceId, out var second))
            {
                first.notes.Add("Missing t1 sample for this unit path.");
                merged.Add(first);
                continue;
            }

            first.normalizedTimeT0 = first.currentStateNormalizedTime;
            first.normalizedTimeT1 = second.currentStateNormalizedTime;
            first.normalizedTimeAdvanced = Math.Abs(first.normalizedTimeT1 - first.normalizedTimeT0) > 0.0001f;

            first.sampleBoneWorldPositionT0 = first.sampleBoneWorldPosition;
            first.sampleBoneWorldPositionT1 = second.sampleBoneWorldPosition;
            first.sampleBoneDeltaMagnitude = Vector3.Distance(first.sampleBoneWorldPositionT0, first.sampleBoneWorldPositionT1);
            first.boneDeltaAdvanced = first.sampleBoneDeltaMagnitude > 0.00005f;

            if (!first.normalizedTimeAdvanced && !first.boneDeltaAdvanced && first.animatorExists)
            {
                first.notes.Add("Animator state did not advance and sampled bone delta is near zero.");
            }

            first.interpolatorIsInterpolating = first.interpolatorIsInterpolating || second.interpolatorIsInterpolating;
            first.interpolatorSnapCount = Math.Max(first.interpolatorSnapCount, second.interpolatorSnapCount);
            first.interpolatorExcessiveSnapCount = Math.Max(first.interpolatorExcessiveSnapCount, second.interpolatorExcessiveSnapCount);
            first.interpolatorLastSnapFrame = Math.Max(first.interpolatorLastSnapFrame, second.interpolatorLastSnapFrame);
            first.interpolatorLastSnapReason = string.IsNullOrWhiteSpace(second.interpolatorLastSnapReason) ? first.interpolatorLastSnapReason : second.interpolatorLastSnapReason;
            first.visualRootLocalPositionT0 = first.visualRootLocalPosition;
            first.visualRootLocalPositionT1 = second.visualRootLocalPosition;
            first.interpolatorCurrentVisualOffsetT0 = first.interpolatorCurrentVisualOffset;
            first.interpolatorCurrentVisualOffsetT1 = second.interpolatorCurrentVisualOffset;

            merged.Add(first);
        }

        return merged;
    }

    private static Summary BuildRegressionSummary(List<UnitEvidence> units)
    {
        var summary = new Summary
        {
            unitsWithAnimator = units.Count(x => x.animatorExists),
            unitsWithAdvancingAnimatorTime = units.Count(x => x.normalizedTimeAdvanced),
            unitsWithAdvancingBoneDelta = units.Count(x => x.boneDeltaAdvanced),
            unitsWithOwnerMarkerIssues = units.Count(x => x.teamMarkerExists && (!x.teamMarkerActive || !x.teamMarkerAnchored)),
            unitsWithInterpolator = units.Count(x => x.interpolatorPresent),
            unitsInterpolating = units.Count(x => x.interpolatorIsInterpolating),
            unitsWithExcessiveSnaps = units.Count(x => x.interpolatorExcessiveSnapCount > 0),
            unitsWithBridgeMismatch = units.Count(x => !x.bridgeAnimatorMovingMatchesInterpolator)
        };

        summary.idlePlaybackHealthy = summary.unitsWithAnimator > 0 && (summary.unitsWithAdvancingAnimatorTime > 0 || summary.unitsWithAdvancingBoneDelta > 0);
        return summary;
    }

    private static void ApplyInterpolationToRuntime(bool enabled, string reason)
    {
        var interpolators = UnityEngine.Object.FindObjectsByType<VisualGridMovementInterpolator>(FindObjectsSortMode.None);
        foreach (var interpolator in interpolators)
        {
            if (interpolator == null)
            {
                continue;
            }

            interpolator.SetInterpolationEnabled(enabled, reason);
            if (!enabled)
            {
                interpolator.SnapToCurrent(reason);
            }
        }
    }

    private static TraceStats ReadSmoothTraceStats()
    {
        string fullPath = Path.GetFullPath(SmoothTracePath);
        var stats = new TraceStats();

        if (!File.Exists(fullPath))
        {
            stats.notes.Add("Trace file not found: " + SmoothTracePath);
            return stats;
        }

        var lines = File.ReadAllLines(fullPath);
        stats.lineCount = lines.Length;

        int lastSnapFrame = -1;
        foreach (var line in lines)
        {
            if (line.IndexOf("\"visual_event\":\"VisualMoveInterpolationStarted\"", StringComparison.Ordinal) >= 0) stats.startedCount++;
            if (line.IndexOf("\"visual_event\":\"VisualMoveInterpolationCompleted\"", StringComparison.Ordinal) >= 0) stats.completedCount++;
            if (line.IndexOf("\"visual_event\":\"VisualMoveInterpolationSnapped\"", StringComparison.Ordinal) >= 0)
            {
                stats.snappedCount++;
                int frame = ReadIntField(line, "\"frame\":");
                if (frame >= 0 && frame == lastSnapFrame)
                {
                    stats.repeatedSnapSameFrameCount++;
                }

                lastSnapFrame = frame;
            }
        }

        return stats;
    }

    private static ValidationSummary BuildSummary(ValidationReport report)
    {
        var summary = new ValidationSummary
        {
            modeAIdlePlaybackHealthy = report.modeA.summary.idlePlaybackHealthy,
            modeBIdlePlaybackHealthy = report.modeB.summary.idlePlaybackHealthy,
            modeAOwnerMarkerHealthy = report.modeA.summary.unitsWithOwnerMarkerIssues == 0,
            modeBOwnerMarkerHealthy = report.modeB.summary.unitsWithOwnerMarkerIssues == 0,
            modeBNoExcessiveSnaps = report.modeB.summary.unitsWithExcessiveSnaps == 0 && report.trace.repeatedSnapSameFrameCount == 0,
            smoothMovementEnabledValidated = report.modeB.summary.idlePlaybackHealthy && report.modeB.summary.unitsWithExcessiveSnaps == 0
        };

        summary.recommendedDefault = summary.smoothMovementEnabledValidated ? "Enabled" : "Disabled";
        if (!summary.smoothMovementEnabledValidated)
        {
            summary.notes.Add("Smooth movement should remain disabled by default until snap/jerk regressions are eliminated.");
        }

        return summary;
    }

    private static void WriteRegressionEvidenceArtifacts(RegressionEvidenceReport report)
    {
        File.WriteAllText(Path.GetFullPath(RegressionEvidenceJsonPath), JsonUtility.ToJson(report, true), Encoding.UTF8);

        var md = new StringBuilder(4096);
        md.AppendLine("# Visual-3F-R Animation Regression Evidence");
        md.AppendLine();
        md.AppendLine("- Generated UTC: " + report.generatedUtc);
        md.AppendLine("- Mode: " + report.mode);
        md.AppendLine("- Unit count: " + report.unitCount);
        md.AppendLine();
        md.AppendLine("## Summary");
        md.AppendLine("- Units with animator: " + report.summary.unitsWithAnimator);
        md.AppendLine("- Units with advancing normalizedTime: " + report.summary.unitsWithAdvancingAnimatorTime);
        md.AppendLine("- Units with advancing bone delta: " + report.summary.unitsWithAdvancingBoneDelta);
        md.AppendLine("- Idle playback healthy: " + report.summary.idlePlaybackHealthy);
        md.AppendLine("- Units with owner marker issues: " + report.summary.unitsWithOwnerMarkerIssues);
        md.AppendLine("- Units with bridge/interpolator moving mismatch: " + report.summary.unitsWithBridgeMismatch);
        md.AppendLine();
        md.AppendLine("## Per Unit");

        foreach (var unit in report.units)
        {
            md.AppendLine("- " + unit.gameObjectPath);
            md.AppendLine("  - UnitType/Owner: " + unit.unitType + " / " + unit.owner);
            md.AppendLine("  - Animator: exists=" + unit.animatorExists + ", enabled=" + unit.animatorEnabled + ", activeInHierarchy=" + unit.animatorActiveInHierarchy);
            md.AppendLine("  - Animator controller: " + unit.animatorControllerName + " (" + unit.animatorControllerPath + ")");
            md.AppendLine("  - State: " + unit.currentStateName + " (hash=" + unit.currentStateHash + ")");
            md.AppendLine("  - normalizedTime t0->t1: " + unit.normalizedTimeT0.ToString("0.000") + " -> " + unit.normalizedTimeT1.ToString("0.000") + ", advanced=" + unit.normalizedTimeAdvanced);
            md.AppendLine("  - Bone delta magnitude: " + unit.sampleBoneDeltaMagnitude.ToString("0.000000") + " (advanced=" + unit.boneDeltaAdvanced + ")");
            md.AppendLine("  - IsMoving param exists/value: " + unit.hasIsMovingParameter + " / " + unit.isMovingValue);
            md.AppendLine("  - Attack/Harvest/Death triggers exist: " + unit.hasAttackTrigger + " / " + unit.hasHarvestTrigger + " / " + unit.hasDeathTrigger);
            md.AppendLine("  - Interpolator present/enabled/interpolating: " + unit.interpolatorPresent + " / " + unit.interpolatorEnabled + " / " + unit.interpolatorIsInterpolating);
            md.AppendLine("  - Offset t0->t1: " + Vec(unit.interpolatorCurrentVisualOffsetT0) + " -> " + Vec(unit.interpolatorCurrentVisualOffsetT1));
            md.AppendLine("  - VisualRoot localPosition t0->t1: " + Vec(unit.visualRootLocalPositionT0) + " -> " + Vec(unit.visualRootLocalPositionT1));
            md.AppendLine("  - Team marker active/anchored: " + unit.teamMarkerActive + " / " + unit.teamMarkerAnchored);
            md.AppendLine("  - Last moving write: value=" + unit.bridgeLastSetMovingValue + ", frame=" + unit.bridgeLastSetMovingFrame);
            foreach (var note in unit.notes)
            {
                md.AppendLine("  - Note: " + note);
            }
        }

        File.WriteAllText(Path.GetFullPath(RegressionEvidenceMdPath), md.ToString().Replace("\r\n", "\n"), Encoding.UTF8);
    }

    private static void WriteValidationArtifacts(ValidationReport report)
    {
        File.WriteAllText(Path.GetFullPath(ValidationJsonPath), JsonUtility.ToJson(report, true), Encoding.UTF8);

        var md = new StringBuilder(4096);
        md.AppendLine("# Visual-3F-R Animation + Smooth Movement Validation");
        md.AppendLine();
        md.AppendLine("- Generated UTC: " + report.generatedUtc);
        md.AppendLine();
        md.AppendLine("## Mode A (Smooth Disabled)");
        md.AppendLine("- Idle playback healthy: " + report.modeA.summary.idlePlaybackHealthy);
        md.AppendLine("- Units with owner marker issues: " + report.modeA.summary.unitsWithOwnerMarkerIssues);
        md.AppendLine("- Units with bridge/interpolator moving mismatch: " + report.modeA.summary.unitsWithBridgeMismatch);
        md.AppendLine();
        md.AppendLine("## Mode B (Smooth Enabled)");
        md.AppendLine("- Idle playback healthy: " + report.modeB.summary.idlePlaybackHealthy);
        md.AppendLine("- Units with owner marker issues: " + report.modeB.summary.unitsWithOwnerMarkerIssues);
        md.AppendLine("- Units interpolating: " + report.modeB.summary.unitsInterpolating);
        md.AppendLine("- Units with excessive snaps: " + report.modeB.summary.unitsWithExcessiveSnaps);
        md.AppendLine();
        md.AppendLine("## Trace");
        md.AppendLine("- Lines: " + report.trace.lineCount);
        md.AppendLine("- Started count: " + report.trace.startedCount);
        md.AppendLine("- Completed count: " + report.trace.completedCount);
        md.AppendLine("- Snapped count: " + report.trace.snappedCount);
        md.AppendLine("- Repeated snap same frame count: " + report.trace.repeatedSnapSameFrameCount);
        foreach (var note in report.trace.notes)
        {
            md.AppendLine("- Note: " + note);
        }
        md.AppendLine();
        md.AppendLine("## Final Recommendation");
        md.AppendLine("- Smooth movement default: " + report.summary.recommendedDefault);
        md.AppendLine("- Mode A idle healthy: " + report.summary.modeAIdlePlaybackHealthy);
        md.AppendLine("- Mode B idle healthy: " + report.summary.modeBIdlePlaybackHealthy);
        md.AppendLine("- Mode B no excessive snaps: " + report.summary.modeBNoExcessiveSnaps);
        md.AppendLine("- Smooth enabled validated: " + report.summary.smoothMovementEnabledValidated);
        foreach (var note in report.summary.notes)
        {
            md.AppendLine("- Note: " + note);
        }

        File.WriteAllText(Path.GetFullPath(ValidationMdPath), md.ToString().Replace("\r\n", "\n"), Encoding.UTF8);
    }

    private static Animator ResolveAnimator(UnitVisualAnimator unitVisualAnimator, Transform root)
    {
        if (unitVisualAnimator != null)
        {
            var refAnimator = unitVisualAnimator.GetAnimatorReference();
            if (refAnimator != null)
            {
                return refAnimator;
            }
        }

        return root != null ? root.GetComponentInChildren<Animator>(true) : null;
    }

    private static Transform ResolveVisualRoot(Transform unitRoot, VisualGridMovementInterpolator interpolator)
    {
        if (interpolator != null)
        {
            var serialized = new SerializedObject(interpolator);
            var prop = serialized.FindProperty("visualRoot");
            if (prop != null && prop.objectReferenceValue != null)
            {
                return prop.objectReferenceValue as Transform;
            }
        }

        if (unitRoot == null)
        {
            return null;
        }

        return FindChildByName(unitRoot, "VisualRoot");
    }

    private static Transform ResolveBoneSampleTransform(Transform animatorTransform)
    {
        if (animatorTransform == null)
        {
            return null;
        }

        var hips = FindChildByName(animatorTransform, "Hips");
        if (hips != null)
        {
            return hips;
        }

        return animatorTransform.childCount > 0 ? animatorTransform.GetChild(0) : animatorTransform;
    }

    private static bool HasParameter(Animator animator, string name, AnimatorControllerParameterType type)
    {
        if (animator == null)
        {
            return false;
        }

        var targetHash = Animator.StringToHash(name);
        var parameters = animator.parameters;
        for (int index = 0; index < parameters.Length; index++)
        {
            if (parameters[index].nameHash == targetHash && parameters[index].type == type)
            {
                return true;
            }
        }

        return false;
    }

    private static int ReadIntField(string jsonLine, string fieldPrefix)
    {
        int start = jsonLine.IndexOf(fieldPrefix, StringComparison.Ordinal);
        if (start < 0)
        {
            return -1;
        }

        start += fieldPrefix.Length;
        int end = start;
        while (end < jsonLine.Length && char.IsDigit(jsonLine[end]))
        {
            end++;
        }

        if (end <= start)
        {
            return -1;
        }

        return int.TryParse(jsonLine.Substring(start, end - start), out int value) ? value : -1;
    }

    private static Transform FindChildByName(Transform root, string childName)
    {
        if (root == null)
        {
            return null;
        }

        for (int index = 0; index < root.childCount; index++)
        {
            var child = root.GetChild(index);
            if (child.name == childName)
            {
                return child;
            }

            var nested = FindChildByName(child, childName);
            if (nested != null)
            {
                return nested;
            }
        }

        return null;
    }

    private static string GetHierarchyPath(Transform node)
    {
        if (node == null)
        {
            return string.Empty;
        }

        string path = node.name;
        var current = node.parent;
        while (current != null)
        {
            path = current.name + "/" + path;
            current = current.parent;
        }

        return path;
    }

    private static string Vec(Vector3 value)
    {
        return "(" + value.x.ToString("0.000") + ", " + value.y.ToString("0.000") + ", " + value.z.ToString("0.000") + ")";
    }

    [Serializable]
    public sealed class RegressionEvidenceReport
    {
        public string generatedUtc;
        public string mode;
        public int unitCount;
        public List<UnitEvidence> units = new List<UnitEvidence>();
        public Summary summary = new Summary();
    }

    [Serializable]
    public sealed class ValidationReport
    {
        public string generatedUtc;
        public RegressionEvidenceReport modeA = new RegressionEvidenceReport();
        public RegressionEvidenceReport modeB = new RegressionEvidenceReport();
        public TraceStats trace = new TraceStats();
        public ValidationSummary summary = new ValidationSummary();
    }

    [Serializable]
    public sealed class UnitEvidence
    {
        public string mode;
        public string phase;
        public int unitInstanceId;
        public string unitName;
        public string gameObjectPath;
        public string unitType;
        public string owner;
        public bool modelNull;

        public string visualRootPath;
        public Vector3 visualRootLocalPosition;
        public Vector3 visualRootLocalPositionT0;
        public Vector3 visualRootLocalPositionT1;

        public bool animatorExists;
        public string animatorPath;
        public bool animatorEnabled;
        public bool animatorActiveInHierarchy;
        public string animatorControllerName;
        public string animatorControllerPath;
        public bool animatorAvatarNull;
        public string animatorCullingMode;
        public string animatorUpdateMode;
        public string currentStateName;
        public int currentStateHash;
        public float currentStateNormalizedTime;
        public float normalizedTimeT0;
        public float normalizedTimeT1;
        public bool normalizedTimeAdvanced;

        public string sampleBonePath;
        public Vector3 sampleBoneWorldPosition;
        public Vector3 sampleBoneWorldPositionT0;
        public Vector3 sampleBoneWorldPositionT1;
        public float sampleBoneDeltaMagnitude;
        public bool boneDeltaAdvanced;

        public bool hasIsMovingParameter;
        public bool isMovingValue;
        public bool hasAttackTrigger;
        public bool hasHarvestTrigger;
        public bool hasDeathTrigger;

        public string unitVisualAnimatorAnimatorPath;

        public bool interpolatorPresent;
        public bool interpolatorEnabled;
        public bool interpolatorIsInterpolating;
        public Vector3 interpolatorCurrentVisualOffset;
        public Vector3 interpolatorCurrentVisualOffsetT0;
        public Vector3 interpolatorCurrentVisualOffsetT1;
        public int interpolatorSnapCount;
        public int interpolatorExcessiveSnapCount;
        public int interpolatorLastSnapFrame;
        public string interpolatorLastSnapReason;

        public bool teamMarkerExists;
        public string teamMarkerPath;
        public bool teamMarkerActive;
        public bool teamMarkerAnchored;

        public bool bridgeLastSetMovingValue;
        public int bridgeLastSetMovingFrame;
        public int bridgeLastMoveStartFrame;
        public int bridgeLastMoveEndFrame;
        public bool bridgeAnimatorMovingMatchesInterpolator;

        public List<string> notes = new List<string>();
    }

    [Serializable]
    public sealed class Summary
    {
        public int unitsWithAnimator;
        public int unitsWithAdvancingAnimatorTime;
        public int unitsWithAdvancingBoneDelta;
        public int unitsWithOwnerMarkerIssues;
        public int unitsWithInterpolator;
        public int unitsInterpolating;
        public int unitsWithExcessiveSnaps;
        public int unitsWithBridgeMismatch;
        public bool idlePlaybackHealthy;
    }

    [Serializable]
    public sealed class TraceStats
    {
        public int lineCount;
        public int startedCount;
        public int completedCount;
        public int snappedCount;
        public int repeatedSnapSameFrameCount;
        public List<string> notes = new List<string>();
    }

    [Serializable]
    public sealed class ValidationSummary
    {
        public bool modeAIdlePlaybackHealthy;
        public bool modeBIdlePlaybackHealthy;
        public bool modeAOwnerMarkerHealthy;
        public bool modeBOwnerMarkerHealthy;
        public bool modeBNoExcessiveSnaps;
        public bool smoothMovementEnabledValidated;
        public string recommendedDefault;
        public List<string> notes = new List<string>();
    }
}
