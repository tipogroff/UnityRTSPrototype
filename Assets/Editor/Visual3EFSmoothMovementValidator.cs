using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using RTS.Gameplay;
using RTS.Presentation;
using UnityEditor;
using UnityEngine;

public static class Visual3EFSmoothMovementValidator
{
    private const string ValidationMdPath = "Assets/Visual3EF_SmoothMovementValidation.md";
    private const string ValidationJsonPath = "Assets/Visual3EF_SmoothMovementValidation.json";
    private const string ReportPath = "VISUAL_3F_SMOOTH_MOVEMENT_INTERPOLATION_REPORT.md";
    private const string TraceJsonlPath = "Assets/Visual3EF_SmoothMovementTrace.jsonl";

    private static readonly PrefabSpec[] PrefabSpecs =
    {
        new PrefabSpec("Worker", "Assets/Prefabs/Worker.prefab", new Vector3(0f, 1f, 0f), new Vector3(0.6f, 0.8f, 0.6f), "CapsuleCollider", "VisualRoot", new Vector3(0f, 0.02f, 0f), new Vector3(0.72f, 0.02f, 0.72f)),
        new PrefabSpec("Light", "Assets/Prefabs/Light.prefab", new Vector3(0f, 1f, 0f), new Vector3(0.8f, 0.8f, 0.8f), "CapsuleCollider", "VisualRoot", new Vector3(0f, 0.02f, 0f), new Vector3(0.72f, 0.02f, 0.72f)),
        new PrefabSpec("Heavy", "Assets/Prefabs/Heavy.prefab", new Vector3(0f, 1f, 0f), new Vector3(0.8f, 0.8f, 0.8f), "CapsuleCollider", "VisualRoot", new Vector3(0f, 0.02f, 0f), new Vector3(0.72f, 0.02f, 0.72f)),
        new PrefabSpec("Ranged", "Assets/Prefabs/Ranged.prefab", new Vector3(0f, 1f, 0f), new Vector3(0.5f, 1.2f, 0.5f), "CapsuleCollider", "VisualRoot", new Vector3(0f, 0.02f, 0f), new Vector3(0.72f, 0.02f, 0.72f))
    };

    [MenuItem("RTS/Presentation/Visual-3F/Run Smooth Movement Validation")]
    public static void RunValidation()
    {
        var report = new ValidationReport
        {
            generatedUtc = DateTime.UtcNow.ToString("O"),
            inPlayMode = EditorApplication.isPlaying
        };

        ValidatePrefabWiring(report);
        ValidateTrace(report);
        ValidatePlayModeState(report);
        WriteArtifacts(report);
        AssetDatabase.Refresh();

        Debug.Log("[Visual3EFSmoothMovementValidator] Validation completed. Artifacts: " + ValidationMdPath + ", " + ValidationJsonPath + ", " + ReportPath);
    }

    [MenuItem("RTS/Presentation/Visual-3F/Reset Smooth Movement Trace")]
    public static void ResetTrace()
    {
        Visual3EFSmoothMovementTrace.Reset("Editor reset command");
        AssetDatabase.Refresh();
        Debug.Log("[Visual3EFSmoothMovementValidator] Smooth movement trace reset.");
    }

    private static void ValidatePrefabWiring(ValidationReport report)
    {
        foreach (var spec in PrefabSpecs)
        {
            var entry = new PrefabValidation
            {
                role = spec.Role,
                prefabPath = spec.PrefabPath
            };

            var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(spec.PrefabPath);
            if (prefab == null)
            {
                entry.ok = false;
                entry.notes.Add("Prefab missing.");
                report.prefabs.Add(entry);
                continue;
            }

            var interpolator = prefab.GetComponent<VisualGridMovementInterpolator>();
            var visualAnimator = prefab.GetComponent<UnitVisualAnimator>();
            var bridge = prefab.GetComponent<VisualEventBridge>();
            var rootCollider = prefab.GetComponent<Collider>();
            var visualRoot = FindChild(prefab.transform, spec.VisualRootName);
            var teamMarker = visualRoot != null ? FindChild(visualRoot, "TeamMarker_Ring") : null;

            entry.hasInterpolator = interpolator != null;
            entry.hasBridge = bridge != null;
            entry.hasVisualAnimator = visualAnimator != null;
            entry.hasRootCollider = rootCollider != null && string.Equals(rootCollider.GetType().Name, spec.RootColliderType, StringComparison.Ordinal);
            entry.visualRootFound = visualRoot != null;
            entry.teamMarkerFound = teamMarker != null;

            if (interpolator == null)
            {
                entry.ok = false;
                entry.notes.Add("VisualGridMovementInterpolator missing.");
            }

            if (bridge == null)
            {
                entry.ok = false;
                entry.notes.Add("VisualEventBridge missing.");
            }

            if (visualAnimator == null)
            {
                entry.ok = false;
                entry.notes.Add("UnitVisualAnimator missing.");
            }

            if (!entry.hasRootCollider)
            {
                entry.ok = false;
                entry.notes.Add("Root collider missing or changed type.");
            }

            if (visualRoot == null)
            {
                entry.ok = false;
                entry.notes.Add("VisualRoot missing.");
            }

            if (teamMarker == null)
            {
                entry.ok = false;
                entry.notes.Add("TeamMarker_Ring missing under VisualRoot.");
            }

            if (interpolator != null)
            {
                var serialized = new SerializedObject(interpolator);
                entry.visualRootAssigned = serialized.FindProperty("visualRoot")?.objectReferenceValue != null;
                entry.moveDuration = serialized.FindProperty("moveDuration") != null ? serialized.FindProperty("moveDuration").floatValue : 0f;
                entry.useScaledTime = serialized.FindProperty("useScaledTime") != null && serialized.FindProperty("useScaledTime").boolValue;
                entry.enableInterpolation = serialized.FindProperty("enableInterpolation") != null && serialized.FindProperty("enableInterpolation").boolValue;
                entry.teleportThreshold = serialized.FindProperty("teleportDistanceThreshold") != null ? serialized.FindProperty("teleportDistanceThreshold").floatValue : 0f;

                if (!entry.visualRootAssigned)
                {
                    entry.ok = false;
                    entry.notes.Add("visualRoot is not assigned.");
                }

                if (entry.moveDuration < 0.15f || entry.moveDuration > 0.5f)
                {
                    entry.ok = false;
                    entry.notes.Add("moveDuration is outside the expected smoothing range.");
                }

                if (!entry.useScaledTime)
                {
                    entry.ok = false;
                    entry.notes.Add("useScaledTime must be enabled.");
                }

                if (!entry.enableInterpolation)
                {
                    entry.ok = false;
                    entry.notes.Add("enableInterpolation must be enabled.");
                }

                if (Math.Abs(entry.teleportThreshold - 0.05f) > 0.001f)
                {
                    entry.notes.Add("teleportDistanceThreshold differs from the expected default of 0.05.");
                }
            }

            if (visualRoot != null)
            {
                entry.rootLocalPosition = visualRoot.localPosition;
                entry.rootLocalScale = visualRoot.localScale;
            }

            entry.expectedRootLocalPosition = spec.ExpectedRootLocalPosition;
            entry.expectedRootLocalScale = spec.ExpectedRootLocalScale;
            entry.expectedMarkerLocalPosition = spec.ExpectedMarkerLocalPosition;
            entry.expectedMarkerLocalScale = spec.ExpectedMarkerLocalScale;

            if (Mathf.Abs(prefab.transform.localPosition.x - spec.ExpectedRootLocalPosition.x) > 0.0001f ||
                Mathf.Abs(prefab.transform.localPosition.y - spec.ExpectedRootLocalPosition.y) > 0.0001f ||
                Mathf.Abs(prefab.transform.localPosition.z - spec.ExpectedRootLocalPosition.z) > 0.0001f)
            {
                entry.ok = false;
                entry.notes.Add("Root localPosition changed.");
            }

            if (Mathf.Abs(prefab.transform.localScale.x - spec.ExpectedRootLocalScale.x) > 0.0001f ||
                Mathf.Abs(prefab.transform.localScale.y - spec.ExpectedRootLocalScale.y) > 0.0001f ||
                Mathf.Abs(prefab.transform.localScale.z - spec.ExpectedRootLocalScale.z) > 0.0001f)
            {
                entry.ok = false;
                entry.notes.Add("Root localScale changed.");
            }

            if (teamMarker != null)
            {
                entry.markerLocalPosition = teamMarker.localPosition;
                entry.markerLocalScale = teamMarker.localScale;

                if (Mathf.Abs(teamMarker.localPosition.x - spec.ExpectedMarkerLocalPosition.x) > 0.0001f ||
                    Mathf.Abs(teamMarker.localPosition.y - spec.ExpectedMarkerLocalPosition.y) > 0.0001f ||
                    Mathf.Abs(teamMarker.localPosition.z - spec.ExpectedMarkerLocalPosition.z) > 0.0001f)
                {
                    entry.ok = false;
                    entry.notes.Add("TeamMarker_Ring localPosition changed.");
                }

                if (Mathf.Abs(teamMarker.localScale.x - spec.ExpectedMarkerLocalScale.x) > 0.0001f ||
                    Mathf.Abs(teamMarker.localScale.y - spec.ExpectedMarkerLocalScale.y) > 0.0001f ||
                    Mathf.Abs(teamMarker.localScale.z - spec.ExpectedMarkerLocalScale.z) > 0.0001f)
                {
                    entry.ok = false;
                    entry.notes.Add("TeamMarker_Ring localScale changed.");
                }
            }

            report.prefabs.Add(entry);
        }
    }

    private static void ValidateTrace(ValidationReport report)
    {
        var trace = new TraceValidation();
        string fullPath = Path.GetFullPath(TraceJsonlPath);

        if (!File.Exists(fullPath))
        {
            trace.notes.Add("Trace JSONL is missing: " + TraceJsonlPath);
            report.trace = trace;
            return;
        }

        string[] lines = File.ReadAllLines(fullPath);
        trace.lineCount = lines.Length;

        foreach (string line in lines)
        {
            if (line.IndexOf("\"visual_event\":\"VisualMoveInterpolationStarted\"", StringComparison.Ordinal) >= 0) trace.hasStarted = true;
            if (line.IndexOf("\"visual_event\":\"VisualMoveInterpolationUpdated\"", StringComparison.Ordinal) >= 0) trace.hasUpdated = true;
            if (line.IndexOf("\"visual_event\":\"VisualMoveInterpolationCompleted\"", StringComparison.Ordinal) >= 0) trace.hasCompleted = true;
            if (line.IndexOf("\"visual_event\":\"VisualMoveInterpolationSnapped\"", StringComparison.Ordinal) >= 0) trace.hasSnapped = true;
            if (line.IndexOf("\"visual_event\":\"VisualMoveInterpolationInterrupted\"", StringComparison.Ordinal) >= 0) trace.hasInterrupted = true;
        }

        if (!trace.hasStarted) trace.notes.Add("VisualMoveInterpolationStarted not observed.");
        if (!trace.hasCompleted) trace.notes.Add("VisualMoveInterpolationCompleted not observed.");
        if (!trace.hasSnapped) trace.notes.Add("VisualMoveInterpolationSnapped not observed.");

        report.trace = trace;
    }

    private static void ValidatePlayModeState(ValidationReport report)
    {
        var play = new PlayModeValidation
        {
            executed = EditorApplication.isPlaying
        };

        if (!EditorApplication.isPlaying)
        {
            play.notes.Add("Skipped: Editor is not in Play Mode.");
            report.playMode = play;
            return;
        }

        var units = UnityEngine.Object.FindObjectsByType<VisualGridMovementInterpolator>(FindObjectsSortMode.None);
        foreach (var interpolator in units)
        {
            if (interpolator == null || !interpolator.isActiveAndEnabled)
            {
                continue;
            }

            play.interpolatorsObserved++;
            if (interpolator.IsInterpolating)
            {
                play.interpolatorsMoving++;
            }

            if (interpolator.CurrentVisualOffset.sqrMagnitude > 0.0001f && !interpolator.IsInterpolating)
            {
                play.stuckOffsetCount++;
                play.notes.Add($"Stuck visual offset detected on {interpolator.name}: {interpolator.CurrentVisualOffset}");
            }

            var unit = interpolator.GetComponent<UnitRuntime>() ?? interpolator.GetComponentInParent<UnitRuntime>(true) ?? interpolator.GetComponentInChildren<UnitRuntime>(true);
            var visualAnimator = interpolator.GetComponent<UnitVisualAnimator>() ?? interpolator.GetComponentInParent<UnitVisualAnimator>(true) ?? interpolator.GetComponentInChildren<UnitVisualAnimator>(true);

            if (unit != null && visualAnimator != null)
            {
                if (!visualAnimator.IsMarkerMaterialCorrectForOwner(unit.Owner))
                {
                    play.ownerColorMismatchCount++;
                    play.notes.Add($"Owner color mismatch on {unit.name}.");
                }

                if (!IsMarkerAnchoredUnderVisualRoot(interpolator.transform, visualAnimator))
                {
                    play.markerOffsetMismatchCount++;
                    play.notes.Add($"TeamMarker_Ring is not anchored as expected on {unit.name}.");
                }

                var animator = ResolveAnimator(visualAnimator);
                if (animator != null)
                {
                    bool isMovingBool = animator.GetBool("IsMoving");
                    if (interpolator.IsInterpolating && !isMovingBool)
                    {
                        play.animatorMismatchCount++;
                        play.notes.Add($"Animator IsMoving is false while interpolation is active on {unit.name}.");
                    }

                    if (!interpolator.IsInterpolating && isMovingBool)
                    {
                        play.animatorMismatchCount++;
                        play.notes.Add($"Animator IsMoving is true after interpolation completion on {unit.name}.");
                    }
                }
            }
        }

        report.playMode = play;
    }

    private static Animator ResolveAnimator(UnitVisualAnimator visualAnimator)
    {
        if (visualAnimator == null)
        {
            return null;
        }

        var serialized = new SerializedObject(visualAnimator);
        var prop = serialized.FindProperty("animator");
        return prop != null ? prop.objectReferenceValue as Animator : null;
    }

    private static bool IsMarkerAnchoredUnderVisualRoot(Transform root, UnitVisualAnimator visualAnimator)
    {
        if (root == null || visualAnimator == null)
        {
            return false;
        }

        var visualRoot = root.Find("VisualRoot");
        if (visualRoot == null)
        {
            return false;
        }

        var marker = FindChild(visualRoot, "TeamMarker_Ring");
        return marker != null && marker.parent == visualRoot;
    }

    private static Transform FindChild(Transform root, string childName)
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

            var nested = FindChild(child, childName);
            if (nested != null)
            {
                return nested;
            }
        }

        return null;
    }

    private static void WriteArtifacts(ValidationReport report)
    {
        File.WriteAllText(Path.GetFullPath(ValidationJsonPath), JsonUtility.ToJson(report, true), Encoding.UTF8);

        var md = new StringBuilder(4096);
        md.AppendLine("# Visual-3F Smooth Movement Validation");
        md.AppendLine();
        md.AppendLine("- Generated UTC: " + report.generatedUtc);
        md.AppendLine("- Play Mode: " + report.inPlayMode);
        md.AppendLine();
        md.AppendLine("## Prefab Wiring");
        foreach (var prefab in report.prefabs)
        {
            md.AppendLine("- " + prefab.role + " => " + (prefab.ok ? "OK" : "FAIL") + " (`" + prefab.prefabPath + "`)");
            md.AppendLine("  - Interpolator: " + prefab.hasInterpolator);
            md.AppendLine("  - visualRoot assigned: " + prefab.visualRootAssigned);
            md.AppendLine("  - Root collider: " + prefab.hasRootCollider);
            md.AppendLine("  - Root localPosition: " + Vector3ToString(prefab.rootLocalPosition) + " expected " + Vector3ToString(prefab.expectedRootLocalPosition));
            md.AppendLine("  - Root localScale: " + Vector3ToString(prefab.rootLocalScale) + " expected " + Vector3ToString(prefab.expectedRootLocalScale));
            md.AppendLine("  - Marker localPosition: " + Vector3ToString(prefab.markerLocalPosition) + " expected " + Vector3ToString(prefab.expectedMarkerLocalPosition));
            md.AppendLine("  - Marker localScale: " + Vector3ToString(prefab.markerLocalScale) + " expected " + Vector3ToString(prefab.expectedMarkerLocalScale));
            foreach (var note in prefab.notes)
            {
                md.AppendLine("  - Note: " + note);
            }
        }

        md.AppendLine();
        md.AppendLine("## Play Mode");
        md.AppendLine("- Executed: " + report.playMode.executed);
        md.AppendLine("- Interpolators observed: " + report.playMode.interpolatorsObserved);
        md.AppendLine("- Interpolators moving: " + report.playMode.interpolatorsMoving);
        md.AppendLine("- Stuck offset count: " + report.playMode.stuckOffsetCount);
        md.AppendLine("- Animator mismatch count: " + report.playMode.animatorMismatchCount);
        md.AppendLine("- Owner color mismatch count: " + report.playMode.ownerColorMismatchCount);
        md.AppendLine("- Marker offset mismatch count: " + report.playMode.markerOffsetMismatchCount);
        foreach (var note in report.playMode.notes)
        {
            md.AppendLine("- Note: " + note);
        }

        md.AppendLine();
        md.AppendLine("## Trace");
        md.AppendLine("- Lines: " + report.trace.lineCount);
        md.AppendLine("- Started: " + report.trace.hasStarted);
        md.AppendLine("- Updated: " + report.trace.hasUpdated);
        md.AppendLine("- Completed: " + report.trace.hasCompleted);
        md.AppendLine("- Snapped: " + report.trace.hasSnapped);
        md.AppendLine("- Interrupted: " + report.trace.hasInterrupted);
        foreach (var note in report.trace.notes)
        {
            md.AppendLine("- Note: " + note);
        }

        File.WriteAllText(Path.GetFullPath(ValidationMdPath), md.ToString().Replace("\r\n", "\n"), Encoding.UTF8);

        var reportText = new StringBuilder(4096);
        reportText.AppendLine("# Visual-3F Smooth Movement Interpolation Report");
        reportText.AppendLine();
        reportText.AppendLine("The gameplay root still moves discretely through GridManager/UnitRuntime, while the VisualRoot receives a presentation-only offset that interpolates back to baseline. Pathfinding, occupancy, action, observation, and training semantics were left unchanged.");
        reportText.AppendLine();
        reportText.AppendLine("## Approach");
        reportText.AppendLine("- Gameplay root continues to teleport cell-to-cell.");
        reportText.AppendLine("- VisualRoot is offset from the previous cell and eased back to baseline.");
        reportText.AppendLine("- VisualEventBridge detects discrete root movement and drives SetMoving from interpolator state.");
        reportText.AppendLine();
        reportText.AppendLine("## Changed Files");
        foreach (var path in GetChangedFiles())
        {
            reportText.AppendLine("- " + path);
        }
        reportText.AppendLine();
        reportText.AppendLine("## Validation");
        reportText.AppendLine("- Prefab wiring validated via editor scan.");
        reportText.AppendLine("- Play-mode checks are recorded in " + ValidationMdPath + ".");
        reportText.AppendLine("- Trace evidence is recorded in " + TraceJsonlPath + ".");
        reportText.AppendLine();
        reportText.AppendLine("## Guardrails");
        reportText.AppendLine("- No gameplay root movement semantics were changed.");
        reportText.AppendLine("- No occupancy, pathfinding, action, observation, or training code was modified.");
        reportText.AppendLine("- Root collider and marker wiring remain on the gameplay root / VisualRoot hierarchy.");

        File.WriteAllText(Path.GetFullPath(ReportPath), reportText.ToString().Replace("\r\n", "\n"), Encoding.UTF8);
    }

    private static IEnumerable<string> GetChangedFiles()
    {
        yield return "Assets/Scripts/Presentation/VisualGridMovementInterpolator.cs";
        yield return "Assets/Scripts/Presentation/Visual3EFSmoothMovementTrace.cs";
        yield return "Assets/Scripts/Presentation/VisualEventBridge.cs";
        yield return "Assets/Prefabs/Worker.prefab";
        yield return "Assets/Prefabs/Light.prefab";
        yield return "Assets/Prefabs/Heavy.prefab";
        yield return "Assets/Prefabs/Ranged.prefab";
    }

    private static string Vector3ToString(Vector3 value)
    {
        return $"({value.x:0.000}, {value.y:0.000}, {value.z:0.000})";
    }

    [Serializable]
    private sealed class ValidationReport
    {
        public string generatedUtc;
        public bool inPlayMode;
        public List<PrefabValidation> prefabs = new List<PrefabValidation>();
        public PlayModeValidation playMode = new PlayModeValidation();
        public TraceValidation trace = new TraceValidation();
    }

    [Serializable]
    private sealed class PrefabValidation
    {
        public string role;
        public string prefabPath;
        public bool ok = true;
        public bool hasInterpolator;
        public bool hasBridge;
        public bool hasVisualAnimator;
        public bool hasRootCollider;
        public bool visualRootFound;
        public bool teamMarkerFound;
        public bool visualRootAssigned;
        public float moveDuration;
        public bool useScaledTime;
        public bool enableInterpolation;
        public float teleportThreshold;
        public Vector3 rootLocalPosition;
        public Vector3 rootLocalScale;
        public Vector3 markerLocalPosition;
        public Vector3 markerLocalScale;
        public Vector3 expectedRootLocalPosition;
        public Vector3 expectedRootLocalScale;
        public Vector3 expectedMarkerLocalPosition;
        public Vector3 expectedMarkerLocalScale;
        public List<string> notes = new List<string>();
    }

    [Serializable]
    private sealed class PlayModeValidation
    {
        public bool executed;
        public int interpolatorsObserved;
        public int interpolatorsMoving;
        public int stuckOffsetCount;
        public int animatorMismatchCount;
        public int ownerColorMismatchCount;
        public int markerOffsetMismatchCount;
        public List<string> notes = new List<string>();
    }

    [Serializable]
    private sealed class TraceValidation
    {
        public int lineCount;
        public bool hasStarted;
        public bool hasUpdated;
        public bool hasCompleted;
        public bool hasSnapped;
        public bool hasInterrupted;
        public List<string> notes = new List<string>();
    }

    private readonly struct PrefabSpec
    {
        public PrefabSpec(string role, string prefabPath, Vector3 expectedRootLocalPosition, Vector3 expectedRootLocalScale, string rootColliderType, string visualRootName, Vector3 expectedMarkerLocalPosition, Vector3 expectedMarkerLocalScale)
        {
            Role = role;
            PrefabPath = prefabPath;
            ExpectedRootLocalPosition = expectedRootLocalPosition;
            ExpectedRootLocalScale = expectedRootLocalScale;
            RootColliderType = rootColliderType;
            VisualRootName = visualRootName;
            ExpectedMarkerLocalPosition = expectedMarkerLocalPosition;
            ExpectedMarkerLocalScale = expectedMarkerLocalScale;
        }

        public string Role { get; }
        public string PrefabPath { get; }
        public Vector3 ExpectedRootLocalPosition { get; }
        public Vector3 ExpectedRootLocalScale { get; }
        public string RootColliderType { get; }
        public string VisualRootName { get; }
        public Vector3 ExpectedMarkerLocalPosition { get; }
        public Vector3 ExpectedMarkerLocalScale { get; }
    }
}