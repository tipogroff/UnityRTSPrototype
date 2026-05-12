// Visual3DROwnerColorRuntimeValidator.cs
// Editor utility: capture runtime evidence and validate owner color sync.
// Run via menu: RTS/Visual/Validate Owner Colors (Play Mode Required)

#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using RTS.Core;
using RTS.Gameplay;
using RTS.Presentation;
using UnityEditor;
using UnityEngine;

namespace RTS.Editor.Visual
{
    public static class Visual3DROwnerColorRuntimeValidator
    {
        private const string Player1MatGuid = "046d8d71a2ff43a4284957952132f14a";
        private const string Player2MatGuid = "8c3b99924bcffe1498d75cd1f3882723";
        private const string NeutralMatGuid = "130f33fad9309b441b25b24afb4b7166";

        private const string RuntimeEvidenceMarkdownPath = "Assets/Visual3DR3_LateSpawnOwnerColorEvidence.md";
        private const string RuntimeEvidenceJsonPath = "Assets/Visual3DR3_LateSpawnOwnerColorEvidence.json";
        private const string RuntimeValidationMarkdownPath = "Assets/Visual3DR3_OwnerColorValidation_OverTime.md";
        private const string RuntimeValidationJsonPath = "Assets/Visual3DR3_OwnerColorValidation_OverTime.json";

        private static OverTimeValidationSession _activeSession;

        [MenuItem("RTS/Visual/Validate Owner Colors")]
        [MenuItem("RTS/Visual/Validate Owner Colors (Play Mode Required)")]
        public static void ValidateOwnerColors()
        {
            ValidateOwnerColorsOverTime();
        }

        [MenuItem("RTS/Visual/Validate Owner Colors Over Time")]
        [MenuItem("RTS/Visual/Validate Owner Colors Over Time (Play Mode Required)")]
        public static void ValidateOwnerColorsOverTime()
        {
            if (!Application.isPlaying)
            {
                EditorUtility.DisplayDialog(
                    "Validation Requires Play Mode",
                    "Enter Play Mode first, then run this validation.",
                    "OK");
                return;
            }

            if (_activeSession != null)
            {
                EditorUtility.DisplayDialog(
                    "Owner Color Validation",
                    "Over-time validation is already running.",
                    "OK");
                return;
            }

            _activeSession = new OverTimeValidationSession();
            _activeSession.Start();

            EditorUtility.DisplayDialog(
                "Owner Color Validation",
                "Over-time validation started. Keep Play Mode active for at least 5 seconds.\n\nOutputs will be written to Assets/ when complete.",
                "OK");
        }

        private static void CompleteOverTimeValidation(OverTimeValidationReport overTimeReport)
        {
            _activeSession = null;

            var evidenceMarkdown = BuildLateSpawnEvidenceMarkdown(overTimeReport);
            var validationMarkdown = BuildOverTimeValidationMarkdown(overTimeReport);
            var evidenceJson = JsonUtility.ToJson(overTimeReport.Evidence, true);
            var validationJson = JsonUtility.ToJson(overTimeReport, true);

            WriteTextFile(RuntimeEvidenceMarkdownPath, evidenceMarkdown);
            WriteTextFile(RuntimeEvidenceJsonPath, evidenceJson);
            WriteTextFile(RuntimeValidationMarkdownPath, validationMarkdown);
            WriteTextFile(RuntimeValidationJsonPath, validationJson);

            Debug.Log(validationMarkdown);

            EditorUtility.DisplayDialog(
                "Owner Color Validation",
                $"Validation complete.\n\nInitial P1 correct: {overTimeReport.InitialPlayer1CorrectCount}\nInitial P2 correct: {overTimeReport.InitialPlayer2CorrectCount}\nLate P1 correct: {overTimeReport.LateSpawnPlayer1CorrectCount}\nLate P2 correct: {overTimeReport.LateSpawnPlayer2CorrectCount}\nLate mismatches: {overTimeReport.LateSpawnMismatchCount}\nMissing animator: {overTimeReport.MissingAnimatorCount}\nMissing bridge: {overTimeReport.MissingBridgeCount}\nMissing marker: {overTimeReport.MissingMarkerCount}\n\nSaved to:\n- {RuntimeEvidenceMarkdownPath}\n- {RuntimeEvidenceJsonPath}\n- {RuntimeValidationMarkdownPath}\n- {RuntimeValidationJsonPath}",
                "OK");
        }

        public static RuntimeEvidenceReport CollectRuntimeEvidence()
        {
            var report = new RuntimeEvidenceReport
            {
                CapturedAtUtc = DateTime.UtcNow.ToString("o"),
                SceneName = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name,
                ScenePath = UnityEngine.SceneManagement.SceneManager.GetActiveScene().path
            };

            var units = UnityEngine.Object.FindObjectsByType<UnitRuntime>(FindObjectsSortMode.None);
            var entries = new List<UnitRuntimeEvidenceEntry>(units.Length);

            for (var i = 0; i < units.Length; i++)
            {
                var unit = units[i];
                if (unit == null || !unit.gameObject.activeInHierarchy)
                {
                    continue;
                }

                var entry = CollectUnitEvidence(unit);
                entries.Add(entry);

                if (!entry.IsOwnerColorTarget)
                {
                    continue;
                }

                if (entry.HasUnitVisualAnimator == false)
                {
                    report.MissingAnimatorCount++;
                }

                if (entry.HasVisualEventBridge == false)
                {
                    report.MissingBridgeCount++;
                }

                if (entry.HasTeamMarkerRing == false)
                {
                    report.MissingMarkerCount++;
                }

                if (entry.MaterialMatchesExpected)
                {
                    if (entry.Owner == nameof(Owner.Player1))
                    {
                        report.Player1CorrectCount++;
                    }
                    else if (entry.Owner == nameof(Owner.Player2))
                    {
                        report.Player2CorrectCount++;
                    }
                }
                else if (entry.Owner != nameof(Owner.Neutral))
                {
                    report.Mismatches.Add(entry);
                }

                if (entry.DuplicateMarkerPaths != null && entry.DuplicateMarkerPaths.Length > 0)
                {
                    report.DuplicateMarkerCount += entry.DuplicateMarkerPaths.Length;
                }
            }

            report.MismatchCount = report.Mismatches.Count;
            report.TotalUnits = units.Length;
            report.ActiveUnits = entries.Count;
            report.Entries = entries.ToArray();
            return report;
        }

        private static UnitRuntimeEvidenceEntry CollectUnitEvidence(UnitRuntime unit)
        {
            var animator = unit.GetComponent<UnitVisualAnimator>();
            if (animator == null)
            {
                animator = unit.GetComponentInChildren<UnitVisualAnimator>(true);
            }

            var bridge = unit.GetComponent<VisualEventBridge>();
            if (bridge == null)
            {
                bridge = unit.GetComponentInChildren<VisualEventBridge>(true);
            }

            var visualRoot = unit.transform.Find("VisualRoot");
            var authoritativeMarker = visualRoot != null ? visualRoot.Find("TeamMarker_Ring") : null;
            if (authoritativeMarker == null)
            {
                authoritativeMarker = FindFirstTeamMarker(unit.transform);
            }

            var allMarkers = new List<Transform>(4);
            CollectTeamMarkerTransforms(unit.transform, allMarkers);

            var duplicateMarkerPaths = BuildDuplicateMarkerPaths(authoritativeMarker, allMarkers);
            var materialRendererPaths = animator != null ? animator.GetMaterialRendererDebugPaths() : Array.Empty<string>();

            var markerRenderer = authoritativeMarker != null ? authoritativeMarker.GetComponent<Renderer>() : null;
            var markerMaterial = markerRenderer != null ? markerRenderer.sharedMaterial : null;
            var markerMaterialName = markerMaterial != null ? markerMaterial.name : string.Empty;
            var markerMaterialGuid = markerMaterial != null ? GetAssetGuid(markerMaterial) : string.Empty;
            var markerMaterialPath = markerMaterial != null ? AssetDatabase.GetAssetPath(markerMaterial) : string.Empty;

            var expectedGuid = GetExpectedMaterialGuid(unit.Owner);
            var expectedName = GetExpectedMaterialName(unit.Owner);
            var actualGuid = markerMaterialGuid;
            var actualName = markerMaterialName;

            return new UnitRuntimeEvidenceEntry
            {
                InstanceId = unit.GetInstanceID(),
                UnitName = unit.name,
                GameObjectPath = GetHierarchyPath(unit.transform),
                UnitType = unit.Type.ToString(),
                Owner = unit.Owner.ToString(),
                IsOwnerColorTarget = IsOwnerColorTarget(unit.Type),
                ModelIsNull = unit.Model == null,
                HasVisualRoot = visualRoot != null,
                HasTeamMarkerRing = authoritativeMarker != null,
                TeamMarkerRingPath = authoritativeMarker != null ? GetHierarchyPath(authoritativeMarker) : string.Empty,
                TeamMarkerRingActiveSelf = authoritativeMarker != null && authoritativeMarker.gameObject.activeSelf,
                TeamMarkerRingActiveInHierarchy = authoritativeMarker != null && authoritativeMarker.gameObject.activeInHierarchy,
                TeamMarkerRingHasRenderer = markerRenderer != null,
                TeamMarkerRingRendererMaterialName = markerMaterialName,
                TeamMarkerRingRendererMaterialAssetPath = markerMaterialPath,
                TeamMarkerRingRendererMaterialGuid = markerMaterialGuid,
                HasUnitVisualAnimator = animator != null,
                UnitVisualAnimatorActiveAndEnabled = animator != null && animator.isActiveAndEnabled,
                HasVisualEventBridge = bridge != null,
                VisualEventBridgeActiveAndEnabled = bridge != null && bridge.isActiveAndEnabled,
                BridgeResolvedUnitRuntime = bridge != null && bridge.HasResolvedUnitRuntime(),
                BridgeResolvedUnitVisualAnimator = bridge != null && bridge.HasResolvedUnitVisualAnimator(),
                BridgeResolvedUnitRuntimeName = bridge != null ? bridge.GetResolvedUnitRuntimeName() : string.Empty,
                BridgeResolvedUnitVisualAnimatorName = bridge != null ? bridge.GetResolvedUnitVisualAnimatorName() : string.Empty,
                OwnerSyncAttemptCount = bridge != null ? bridge.GetOwnerSyncAttemptCount() : 0,
                OwnerSyncEverSucceeded = bridge != null && bridge.HasOwnerSyncEverSucceeded(),
                LastSyncedOwner = bridge != null ? bridge.GetLastSyncedOwner().ToString() : string.Empty,
                LastOwnerSyncMaterialName = bridge != null ? bridge.GetLastOwnerSyncMaterialName() : string.Empty,
                BridgeHasSyncedSuccessfully = bridge != null && bridge.HasSyncedSuccessfully,
                BridgeLastSyncFrame = bridge != null ? bridge.LastSyncFrame : -1,
                BridgeLastSyncReason = bridge != null ? bridge.LastSyncReason : string.Empty,
                BridgeLastObservedOwner = bridge != null ? bridge.LastObservedOwner.ToString() : string.Empty,
                BridgeLastObservedModelNull = bridge != null && bridge.LastObservedModelNull,
                BridgeLastMaterialMatchedExpected = bridge != null && bridge.LastMaterialMatchedExpected,
                BridgeLastMarkerMaterialName = bridge != null ? bridge.LastMarkerMaterialName : string.Empty,
                MaterialRendererCount = animator != null ? animator.GetMaterialRendererCount() : 0,
                MaterialRendererDebugPaths = materialRendererPaths,
                HasPlayer1Material = animator != null && animator.HasPlayer1Material(),
                HasPlayer2Material = animator != null && animator.HasPlayer2Material(),
                HasNeutralMaterial = animator != null && animator.HasNeutralMaterial(),
                ExpectedMaterialName = expectedName,
                ExpectedMaterialGuid = expectedGuid,
                ActualMaterialName = actualName,
                ActualMaterialGuid = actualGuid,
                MaterialMatchesExpected = string.Equals(expectedGuid, actualGuid, StringComparison.OrdinalIgnoreCase),
                DuplicateMarkerPaths = duplicateMarkerPaths,
                CurrentOwnerMaterialName = animator != null ? animator.GetCurrentOwnerMaterialName() : string.Empty,
                LastSeenFrame = Time.frameCount,
                Notes = BuildNotes(unit, animator, bridge, authoritativeMarker, duplicateMarkerPaths)
            };
        }

        private static string BuildNotes(UnitRuntime unit, UnitVisualAnimator animator, VisualEventBridge bridge, Transform authoritativeMarker, string[] duplicateMarkerPaths)
        {
            var notes = new List<string>(4);

            if (unit.Model == null)
            {
                notes.Add("Model is null.");
            }

            if (authoritativeMarker == null)
            {
                notes.Add("No TeamMarker_Ring found.");
            }

            if (duplicateMarkerPaths != null && duplicateMarkerPaths.Length > 0)
            {
                notes.Add($"Duplicate TeamMarker_Ring count={duplicateMarkerPaths.Length}.");
            }

            if (animator == null)
            {
                notes.Add("UnitVisualAnimator missing.");
            }

            if (bridge == null)
            {
                notes.Add("VisualEventBridge missing.");
            }

            return notes.Count > 0 ? string.Join(" ", notes) : string.Empty;
        }

        private static string[] BuildDuplicateMarkerPaths(Transform authoritativeMarker, List<Transform> allMarkers)
        {
            if (allMarkers == null || allMarkers.Count == 0)
            {
                return Array.Empty<string>();
            }

            var duplicates = new List<string>(Math.Max(0, allMarkers.Count - 1));
            for (var i = 0; i < allMarkers.Count; i++)
            {
                var marker = allMarkers[i];
                if (marker == null || marker == authoritativeMarker)
                {
                    continue;
                }

                if (!marker.gameObject.activeInHierarchy)
                {
                    continue;
                }

                duplicates.Add(GetHierarchyPath(marker));
            }

            return duplicates.Count > 0 ? duplicates.ToArray() : Array.Empty<string>();
        }

        private static void CollectTeamMarkerTransforms(Transform root, List<Transform> markers)
        {
            if (root == null || markers == null)
            {
                return;
            }

            for (var i = 0; i < root.childCount; i++)
            {
                var child = root.GetChild(i);
                if (child.name == "TeamMarker_Ring")
                {
                    markers.Add(child);
                }

                CollectTeamMarkerTransforms(child, markers);
            }
        }

        private static Transform FindFirstTeamMarker(Transform root)
        {
            if (root == null)
            {
                return null;
            }

            for (var i = 0; i < root.childCount; i++)
            {
                var child = root.GetChild(i);
                if (child.name == "TeamMarker_Ring")
                {
                    return child;
                }

                var found = FindFirstTeamMarker(child);
                if (found != null)
                {
                    return found;
                }
            }

            return null;
        }

        private static string GetExpectedMaterialName(Owner owner)
        {
            return owner switch
            {
                Owner.Player1 => "Player1_Blue",
                Owner.Player2 => "Player2_Red",
                Owner.Neutral => "Neutral_Resource",
                _ => string.Empty
            };
        }

        private static string GetExpectedMaterialGuid(Owner owner)
        {
            return owner switch
            {
                Owner.Player1 => Player1MatGuid,
                Owner.Player2 => Player2MatGuid,
                Owner.Neutral => NeutralMatGuid,
                _ => string.Empty
            };
        }

        private static string GetAssetGuid(UnityEngine.Object asset)
        {
            if (asset == null)
            {
                return string.Empty;
            }

            if (!AssetDatabase.TryGetGUIDAndLocalFileIdentifier(asset, out string guid, out long _))
            {
                return string.Empty;
            }

            return guid;
        }

        private static string GetHierarchyPath(Transform node)
        {
            if (node == null)
            {
                return string.Empty;
            }

            var current = node;
            var path = current.name;
            while (current.parent != null)
            {
                current = current.parent;
                path = string.Concat(current.name, "/", path);
            }

            return path;
        }

        private static void WriteTextFile(string assetRelativePath, string contents)
        {
            var absolutePath = Path.Combine(Application.dataPath, "..", assetRelativePath.Replace('/', Path.DirectorySeparatorChar));
            File.WriteAllText(absolutePath, contents, Encoding.UTF8);
            AssetDatabase.Refresh();
        }

        private static string BuildRuntimeEvidenceMarkdown(RuntimeEvidenceReport report)
        {
            var sb = new StringBuilder();
            sb.AppendLine("# Visual-3D-R2 Owner Color Runtime Evidence");
            sb.AppendLine();
            sb.AppendLine($"- Captured UTC: {report.CapturedAtUtc}");
            sb.AppendLine($"- Scene: {report.SceneName}");
            sb.AppendLine($"- Scene path: {report.ScenePath}");
            sb.AppendLine($"- Total UnitRuntime instances: {report.TotalUnits}");
            sb.AppendLine($"- Active UnitRuntime instances: {report.ActiveUnits}");
            sb.AppendLine($"- Player1 correct: {report.Player1CorrectCount}");
            sb.AppendLine($"- Player2 correct: {report.Player2CorrectCount}");
            sb.AppendLine($"- Mismatches: {report.MismatchCount}");
            sb.AppendLine($"- Missing TeamMarker_Ring: {report.MissingMarkerCount}");
            sb.AppendLine($"- Missing UnitVisualAnimator: {report.MissingAnimatorCount}");
            sb.AppendLine($"- Missing VisualEventBridge: {report.MissingBridgeCount}");
            sb.AppendLine($"- Duplicate TeamMarker_Ring count: {report.DuplicateMarkerCount}");
            sb.AppendLine();

            for (var i = 0; i < report.Entries.Length; i++)
            {
                var entry = report.Entries[i];
                sb.AppendLine($"## {entry.GameObjectPath}");
                sb.AppendLine($"- UnitRuntime.Type: {entry.UnitType}");
                sb.AppendLine($"- UnitRuntime.Owner: {entry.Owner}");
                sb.AppendLine($"- Owner-color validation target: {entry.IsOwnerColorTarget}");
                sb.AppendLine($"- UnitRuntime.Model is null: {entry.ModelIsNull}");
                sb.AppendLine($"- VisualRoot present: {entry.HasVisualRoot}");
                sb.AppendLine($"- TeamMarker_Ring present: {entry.HasTeamMarkerRing}");
                sb.AppendLine($"- TeamMarker_Ring path: {entry.TeamMarkerRingPath}");
                sb.AppendLine($"- TeamMarker_Ring activeSelf: {entry.TeamMarkerRingActiveSelf}");
                sb.AppendLine($"- TeamMarker_Ring activeInHierarchy: {entry.TeamMarkerRingActiveInHierarchy}");
                sb.AppendLine($"- TeamMarker_Ring renderer present: {entry.TeamMarkerRingHasRenderer}");
                sb.AppendLine($"- TeamMarker_Ring renderer.sharedMaterial.name: {entry.TeamMarkerRingRendererMaterialName}");
                sb.AppendLine($"- TeamMarker_Ring renderer.sharedMaterial asset path: {entry.TeamMarkerRingRendererMaterialAssetPath}");
                sb.AppendLine($"- TeamMarker_Ring renderer.sharedMaterial guid: {entry.TeamMarkerRingRendererMaterialGuid}");
                sb.AppendLine($"- UnitVisualAnimator present: {entry.HasUnitVisualAnimator}");
                sb.AppendLine($"- UnitVisualAnimator activeAndEnabled: {entry.UnitVisualAnimatorActiveAndEnabled}");
                sb.AppendLine($"- VisualEventBridge present: {entry.HasVisualEventBridge}");
                sb.AppendLine($"- VisualEventBridge activeAndEnabled: {entry.VisualEventBridgeActiveAndEnabled}");
                sb.AppendLine($"- VisualEventBridge resolved UnitRuntime: {entry.BridgeResolvedUnitRuntime} ({entry.BridgeResolvedUnitRuntimeName})");
                sb.AppendLine($"- VisualEventBridge resolved UnitVisualAnimator: {entry.BridgeResolvedUnitVisualAnimator} ({entry.BridgeResolvedUnitVisualAnimatorName})");
                sb.AppendLine($"- VisualEventBridge owner sync attempt count: {entry.OwnerSyncAttemptCount}");
                sb.AppendLine($"- VisualEventBridge owner sync ever succeeded: {entry.OwnerSyncEverSucceeded}");
                sb.AppendLine($"- VisualEventBridge last synced owner: {entry.LastSyncedOwner}");
                sb.AppendLine($"- VisualEventBridge last owner sync material name: {entry.LastOwnerSyncMaterialName}");
                sb.AppendLine($"- UnitVisualAnimator.materialRenderers length: {entry.MaterialRendererCount}");
                sb.AppendLine($"- UnitVisualAnimator.materialRenderers paths: {(entry.MaterialRendererDebugPaths.Length > 0 ? string.Join(", ", entry.MaterialRendererDebugPaths) : string.Empty)}");
                sb.AppendLine($"- player1Material assigned: {entry.HasPlayer1Material}");
                sb.AppendLine($"- player2Material assigned: {entry.HasPlayer2Material}");
                sb.AppendLine($"- neutralMaterial assigned: {entry.HasNeutralMaterial}");
                sb.AppendLine($"- expected material by Owner: {entry.ExpectedMaterialName} ({entry.ExpectedMaterialGuid})");
                sb.AppendLine($"- actual material: {entry.ActualMaterialName} ({entry.ActualMaterialGuid})");
                sb.AppendLine($"- current owner material name: {entry.CurrentOwnerMaterialName}");
                sb.AppendLine($"- match / mismatch: {(entry.MaterialMatchesExpected ? "match" : "mismatch")}");
                sb.AppendLine($"- duplicate TeamMarker_Ring paths: {(entry.DuplicateMarkerPaths.Length > 0 ? string.Join(", ", entry.DuplicateMarkerPaths) : string.Empty)}");
                if (!string.IsNullOrEmpty(entry.Notes))
                {
                    sb.AppendLine($"- notes: {entry.Notes}");
                }

                sb.AppendLine();
            }

            return sb.ToString();
        }

        private static bool IsOwnerColorTarget(UnitType unitType)
        {
            return unitType == UnitType.Worker
                || unitType == UnitType.Light
                || unitType == UnitType.Heavy
                || unitType == UnitType.Ranged;
        }

        private static string BuildRuntimeValidationMarkdown(RuntimeEvidenceReport report)
        {
            var sb = new StringBuilder();
            sb.AppendLine("# Visual-3D-R2 Owner Color Runtime Validation");
            sb.AppendLine();
            sb.AppendLine($"- Captured UTC: {report.CapturedAtUtc}");
            sb.AppendLine($"- Player1 units with correct blue marker: {report.Player1CorrectCount}");
            sb.AppendLine($"- Player2 units with correct red marker: {report.Player2CorrectCount}");
            sb.AppendLine($"- Mismatches: {report.MismatchCount}");
            sb.AppendLine($"- Missing TeamMarker_Ring: {report.MissingMarkerCount}");
            sb.AppendLine($"- Missing UnitVisualAnimator: {report.MissingAnimatorCount}");
            sb.AppendLine($"- Missing VisualEventBridge: {report.MissingBridgeCount}");
            sb.AppendLine($"- Duplicate TeamMarker_Ring count: {report.DuplicateMarkerCount}");
            sb.AppendLine();

            if (report.MismatchCount > 0)
            {
                sb.AppendLine("## Mismatches");
                for (var i = 0; i < report.Mismatches.Count; i++)
                {
                    var entry = report.Mismatches[i];
                    sb.AppendLine($"- {entry.GameObjectPath} | Owner={entry.Owner} | Expected={entry.ExpectedMaterialName} | Actual={entry.ActualMaterialName} | Marker={entry.TeamMarkerRingRendererMaterialName}");
                }

                sb.AppendLine();
            }

            if (report.MissingAnimatorCount > 0 || report.MissingBridgeCount > 0 || report.MissingMarkerCount > 0)
            {
                sb.AppendLine("## Missing Components");
                for (var i = 0; i < report.Entries.Length; i++)
                {
                    var entry = report.Entries[i];
                    if (!entry.HasUnitVisualAnimator || !entry.HasVisualEventBridge || !entry.HasTeamMarkerRing)
                    {
                        sb.AppendLine($"- {entry.GameObjectPath} | Animator={entry.HasUnitVisualAnimator} | Bridge={entry.HasVisualEventBridge} | Marker={entry.HasTeamMarkerRing}");
                    }
                }

                sb.AppendLine();
            }

            return sb.ToString();
        }

        private static OverTimeValidationReport BuildOverTimeReport(List<SnapshotReport> snapshots)
        {
            var report = new OverTimeValidationReport
            {
                CapturedAtUtc = DateTime.UtcNow.ToString("o"),
                SceneName = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name,
                ScenePath = UnityEngine.SceneManagement.SceneManager.GetActiveScene().path,
                Snapshots = snapshots.ToArray(),
                Evidence = new RuntimeEvidenceReport()
            };

            if (snapshots.Count == 0)
            {
                return report;
            }

            var initialSnapshot = snapshots[0];
            var initialIds = new HashSet<int>();
            var latestByInstance = new Dictionary<int, UnitRuntimeEvidenceEntry>();
            var firstSeen = new Dictionary<int, SnapshotReport>();
            var seenSet = new HashSet<int>();

            for (var i = 0; i < initialSnapshot.Entries.Length; i++)
            {
                initialIds.Add(initialSnapshot.Entries[i].InstanceId);
            }

            for (var snapIndex = 0; snapIndex < snapshots.Count; snapIndex++)
            {
                var snapshot = snapshots[snapIndex];
                for (var i = 0; i < snapshot.Entries.Length; i++)
                {
                    var entry = snapshot.Entries[i];
                    if (!seenSet.Contains(entry.InstanceId))
                    {
                        seenSet.Add(entry.InstanceId);
                        firstSeen[entry.InstanceId] = snapshot;
                    }

                    entry.WasPresentInInitialSnapshot = initialIds.Contains(entry.InstanceId);
                    entry.IsLateSpawned = !entry.WasPresentInInitialSnapshot;
                    entry.FirstSeenFrame = firstSeen[entry.InstanceId].Frame;
                    entry.LastSeenFrame = snapshot.Frame;
                    entry.FirstSeenSnapshotLabel = firstSeen[entry.InstanceId].Label;
                    entry.FirstSeenSnapshotIndex = snapshots.IndexOf(firstSeen[entry.InstanceId]);
                    latestByInstance[entry.InstanceId] = entry;
                }
            }

            var uniqueEntries = new List<UnitRuntimeEvidenceEntry>(latestByInstance.Values);
            uniqueEntries.Sort((a, b) => a.InstanceId.CompareTo(b.InstanceId));

            report.Evidence = new RuntimeEvidenceReport
            {
                CapturedAtUtc = report.CapturedAtUtc,
                SceneName = report.SceneName,
                ScenePath = report.ScenePath,
                TotalUnits = uniqueEntries.Count,
                ActiveUnits = uniqueEntries.Count,
                Entries = uniqueEntries.ToArray(),
                Mismatches = new List<UnitRuntimeEvidenceEntry>()
            };

            for (var i = 0; i < uniqueEntries.Count; i++)
            {
                var entry = uniqueEntries[i];
                if (!entry.IsOwnerColorTarget)
                {
                    continue;
                }

                if (!entry.HasUnitVisualAnimator)
                {
                    report.MissingAnimatorCount++;
                }

                if (!entry.HasVisualEventBridge)
                {
                    report.MissingBridgeCount++;
                }

                if (!entry.HasTeamMarkerRing)
                {
                    report.MissingMarkerCount++;
                }

                if (entry.DuplicateMarkerPaths != null)
                {
                    for (var d = 0; d < entry.DuplicateMarkerPaths.Length; d++)
                    {
                        if (!string.IsNullOrEmpty(entry.DuplicateMarkerPaths[d]))
                        {
                            report.DuplicateVisibleMarkerCount++;
                        }
                    }
                }

                if (!entry.MaterialMatchesExpected && entry.Owner != nameof(Owner.Neutral))
                {
                    report.Evidence.Mismatches.Add(entry);
                    if (entry.IsLateSpawned)
                    {
                        report.LateSpawnMismatchCount++;
                    }
                }

                if (entry.WasPresentInInitialSnapshot)
                {
                    if (entry.Owner == nameof(Owner.Player1) && entry.MaterialMatchesExpected)
                    {
                        report.InitialPlayer1CorrectCount++;
                    }

                    if (entry.Owner == nameof(Owner.Player2) && entry.MaterialMatchesExpected)
                    {
                        report.InitialPlayer2CorrectCount++;
                    }
                }

                if (entry.IsLateSpawned)
                {
                    if (entry.Owner == nameof(Owner.Player1) && entry.MaterialMatchesExpected)
                    {
                        report.LateSpawnPlayer1CorrectCount++;
                    }

                    if (entry.Owner == nameof(Owner.Player2) && entry.MaterialMatchesExpected)
                    {
                        report.LateSpawnPlayer2CorrectCount++;
                    }
                }
            }

            report.Evidence.MismatchCount = report.Evidence.Mismatches.Count;
            report.Evidence.Player1CorrectCount = report.InitialPlayer1CorrectCount + report.LateSpawnPlayer1CorrectCount;
            report.Evidence.Player2CorrectCount = report.InitialPlayer2CorrectCount + report.LateSpawnPlayer2CorrectCount;
            report.Evidence.MissingAnimatorCount = report.MissingAnimatorCount;
            report.Evidence.MissingBridgeCount = report.MissingBridgeCount;
            report.Evidence.MissingMarkerCount = report.MissingMarkerCount;
            report.Evidence.DuplicateMarkerCount = report.DuplicateVisibleMarkerCount;
            report.UniqueInstancesSeen = uniqueEntries.Count;

            return report;
        }

        private static string BuildLateSpawnEvidenceMarkdown(OverTimeValidationReport report)
        {
            var sb = new StringBuilder();
            sb.AppendLine("# Visual-3D-R3 Late Spawn Owner Color Evidence");
            sb.AppendLine();
            sb.AppendLine($"- Captured UTC: {report.CapturedAtUtc}");
            sb.AppendLine($"- Scene: {report.SceneName}");
            sb.AppendLine($"- Snapshot count: {(report.Snapshots != null ? report.Snapshots.Length : 0)}");
            sb.AppendLine($"- Unique UnitRuntime instances seen: {report.UniqueInstancesSeen}");
            sb.AppendLine();

            sb.AppendLine("## Snapshots");
            if (report.Snapshots != null)
            {
                for (var i = 0; i < report.Snapshots.Length; i++)
                {
                    var snapshot = report.Snapshots[i];
                    sb.AppendLine($"- {snapshot.Label}: frame={snapshot.Frame}, elapsed={snapshot.ElapsedSeconds:F2}s, activeUnits={snapshot.ActiveUnits}");
                }
            }

            sb.AppendLine();
            sb.AppendLine("## Initial Units");
            AppendEntries(sb, report.Evidence.Entries, true);

            sb.AppendLine();
            sb.AppendLine("## Late-Spawned Units");
            AppendEntries(sb, report.Evidence.Entries, false);

            sb.AppendLine();
            sb.AppendLine("## Late-Spawn Mismatches Only");
            var foundLateMismatch = false;
            for (var i = 0; i < report.Evidence.Entries.Length; i++)
            {
                var entry = report.Evidence.Entries[i];
                if (!entry.IsLateSpawned || entry.MaterialMatchesExpected || entry.Owner == nameof(Owner.Neutral))
                {
                    continue;
                }

                foundLateMismatch = true;
                AppendEntryLine(sb, entry);
            }

            if (!foundLateMismatch)
            {
                sb.AppendLine("- none");
            }

            return sb.ToString();
        }

        private static void AppendEntries(StringBuilder sb, UnitRuntimeEvidenceEntry[] entries, bool initialOnly)
        {
            if (entries == null || entries.Length == 0)
            {
                sb.AppendLine("- none");
                return;
            }

            var wroteAny = false;
            for (var i = 0; i < entries.Length; i++)
            {
                var entry = entries[i];
                if (!entry.IsOwnerColorTarget)
                {
                    continue;
                }

                if (entry.WasPresentInInitialSnapshot != initialOnly)
                {
                    continue;
                }

                wroteAny = true;
                AppendEntryLine(sb, entry);
            }

            if (!wroteAny)
            {
                sb.AppendLine("- none");
            }
        }

        private static void AppendEntryLine(StringBuilder sb, UnitRuntimeEvidenceEntry entry)
        {
            var rendererPath = entry.MaterialRendererDebugPaths != null && entry.MaterialRendererDebugPaths.Length > 0
                ? entry.MaterialRendererDebugPaths[0]
                : string.Empty;
            sb.AppendLine($"- instanceId={entry.InstanceId} | name={entry.UnitName} | unitType={entry.UnitType} | owner={entry.Owner} | initial={(entry.WasPresentInInitialSnapshot ? "yes" : "no")} | firstSeen={entry.FirstSeenSnapshotLabel}@f{entry.FirstSeenFrame} | lastSeenFrame={entry.LastSeenFrame} | actual={entry.ActualMaterialName} | expected={entry.ExpectedMaterialName} | mismatch={(!entry.MaterialMatchesExpected)} | hasAnimator={entry.HasUnitVisualAnimator} | hasBridge={entry.HasVisualEventBridge} | bridgeLastOwner={entry.LastSyncedOwner} | bridgeSyncSuccess={entry.BridgeHasSyncedSuccessfully} | bridgeModelNull={entry.BridgeLastObservedModelNull} | rendererPath={rendererPath}");
        }

        private static string BuildOverTimeValidationMarkdown(OverTimeValidationReport report)
        {
            var sb = new StringBuilder();
            sb.AppendLine("# Visual-3D-R3 Owner Color Validation Over Time");
            sb.AppendLine();
            sb.AppendLine($"- Captured UTC: {report.CapturedAtUtc}");
            sb.AppendLine($"- Scene: {report.SceneName}");
            sb.AppendLine($"- Unique UnitRuntime instances: {report.UniqueInstancesSeen}");
            sb.AppendLine($"- Initial Player1 correct: {report.InitialPlayer1CorrectCount}");
            sb.AppendLine($"- Initial Player2 correct: {report.InitialPlayer2CorrectCount}");
            sb.AppendLine($"- Late-spawned Player1 correct: {report.LateSpawnPlayer1CorrectCount}");
            sb.AppendLine($"- Late-spawned Player2 correct: {report.LateSpawnPlayer2CorrectCount}");
            sb.AppendLine($"- Late-spawn mismatches: {report.LateSpawnMismatchCount}");
            sb.AppendLine($"- Missing UnitVisualAnimator: {report.MissingAnimatorCount}");
            sb.AppendLine($"- Missing VisualEventBridge: {report.MissingBridgeCount}");
            sb.AppendLine($"- Missing TeamMarker_Ring: {report.MissingMarkerCount}");
            sb.AppendLine($"- Duplicate visible markers: {report.DuplicateVisibleMarkerCount}");
            sb.AppendLine();

            if (report.LateSpawnMismatchCount > 0)
            {
                sb.AppendLine("## Late-Spawn Mismatches");
                for (var i = 0; i < report.Evidence.Entries.Length; i++)
                {
                    var entry = report.Evidence.Entries[i];
                    if (entry.IsLateSpawned && !entry.MaterialMatchesExpected && entry.Owner != nameof(Owner.Neutral))
                    {
                        sb.AppendLine($"- {entry.GameObjectPath} | owner={entry.Owner} | expected={entry.ExpectedMaterialName} | actual={entry.ActualMaterialName} | firstSeen={entry.FirstSeenSnapshotLabel}");
                    }
                }

                sb.AppendLine();
            }

            return sb.ToString();
        }

        private sealed class OverTimeValidationSession
        {
            private readonly float[] _checkpointsSeconds = { 0f, 1f, 3f, 5f, 8f, 12f };
            private readonly string[] _labels = { "frame-1", "t+1s", "t+3s", "t+5s", "t+8s", "t+12s" };
            private readonly List<SnapshotReport> _snapshots = new List<SnapshotReport>(4);
            private float _startRealtime;
            private int _nextCheckpointIndex;

            public void Start()
            {
                _startRealtime = Time.realtimeSinceStartup;
                _nextCheckpointIndex = 0;
                EditorApplication.update += OnEditorUpdate;
            }

            private void Stop()
            {
                EditorApplication.update -= OnEditorUpdate;
            }

            private void OnEditorUpdate()
            {
                if (!Application.isPlaying)
                {
                    Stop();
                    _activeSession = null;
                    return;
                }

                if (_nextCheckpointIndex >= _checkpointsSeconds.Length)
                {
                    Stop();
                    var report = BuildOverTimeReport(_snapshots);
                    CompleteOverTimeValidation(report);
                    return;
                }

                var elapsed = Time.realtimeSinceStartup - _startRealtime;
                if (_nextCheckpointIndex == 0 && Time.frameCount < 1)
                {
                    return;
                }

                if (elapsed < _checkpointsSeconds[_nextCheckpointIndex])
                {
                    return;
                }

                var runtimeReport = CollectRuntimeEvidence();
                _snapshots.Add(new SnapshotReport
                {
                    Label = _labels[_nextCheckpointIndex],
                    Frame = Time.frameCount,
                    ElapsedSeconds = elapsed,
                    ActiveUnits = runtimeReport.ActiveUnits,
                    Entries = runtimeReport.Entries
                });
                _nextCheckpointIndex++;
            }
        }

        [Serializable]
        public sealed class RuntimeEvidenceReport
        {
            public string CapturedAtUtc;
            public string SceneName;
            public string ScenePath;
            public int TotalUnits;
            public int ActiveUnits;
            public int Player1CorrectCount;
            public int Player2CorrectCount;
            public int MismatchCount;
            public int MissingMarkerCount;
            public int MissingAnimatorCount;
            public int MissingBridgeCount;
            public int DuplicateMarkerCount;
            public List<UnitRuntimeEvidenceEntry> Mismatches = new List<UnitRuntimeEvidenceEntry>();
            public UnitRuntimeEvidenceEntry[] Entries;
        }

        [Serializable]
        public sealed class SnapshotReport
        {
            public string Label;
            public int Frame;
            public float ElapsedSeconds;
            public int ActiveUnits;
            public UnitRuntimeEvidenceEntry[] Entries;
        }

        [Serializable]
        public sealed class OverTimeValidationReport
        {
            public string CapturedAtUtc;
            public string SceneName;
            public string ScenePath;
            public int UniqueInstancesSeen;
            public int InitialPlayer1CorrectCount;
            public int InitialPlayer2CorrectCount;
            public int LateSpawnPlayer1CorrectCount;
            public int LateSpawnPlayer2CorrectCount;
            public int LateSpawnMismatchCount;
            public int MissingMarkerCount;
            public int MissingAnimatorCount;
            public int MissingBridgeCount;
            public int DuplicateVisibleMarkerCount;
            public SnapshotReport[] Snapshots;
            public RuntimeEvidenceReport Evidence;
        }

        [Serializable]
        public sealed class UnitRuntimeEvidenceEntry
        {
            public int InstanceId;
            public string UnitName;
            public string GameObjectPath;
            public string UnitType;
            public string Owner;
            public bool WasPresentInInitialSnapshot;
            public bool IsLateSpawned;
            public int FirstSeenFrame;
            public int LastSeenFrame;
            public string FirstSeenSnapshotLabel;
            public int FirstSeenSnapshotIndex;
            public bool IsOwnerColorTarget;
            public bool ModelIsNull;
            public bool HasVisualRoot;
            public bool HasTeamMarkerRing;
            public string TeamMarkerRingPath;
            public bool TeamMarkerRingActiveSelf;
            public bool TeamMarkerRingActiveInHierarchy;
            public bool TeamMarkerRingHasRenderer;
            public string TeamMarkerRingRendererMaterialName;
            public string TeamMarkerRingRendererMaterialAssetPath;
            public string TeamMarkerRingRendererMaterialGuid;
            public bool HasUnitVisualAnimator;
            public bool UnitVisualAnimatorActiveAndEnabled;
            public bool HasVisualEventBridge;
            public bool VisualEventBridgeActiveAndEnabled;
            public bool BridgeResolvedUnitRuntime;
            public bool BridgeResolvedUnitVisualAnimator;
            public string BridgeResolvedUnitRuntimeName;
            public string BridgeResolvedUnitVisualAnimatorName;
            public int OwnerSyncAttemptCount;
            public bool OwnerSyncEverSucceeded;
            public string LastSyncedOwner;
            public string LastOwnerSyncMaterialName;
            public bool BridgeHasSyncedSuccessfully;
            public int BridgeLastSyncFrame;
            public string BridgeLastSyncReason;
            public string BridgeLastObservedOwner;
            public bool BridgeLastObservedModelNull;
            public bool BridgeLastMaterialMatchedExpected;
            public string BridgeLastMarkerMaterialName;
            public int MaterialRendererCount;
            public string[] MaterialRendererDebugPaths;
            public bool HasPlayer1Material;
            public bool HasPlayer2Material;
            public bool HasNeutralMaterial;
            public string ExpectedMaterialName;
            public string ExpectedMaterialGuid;
            public string ActualMaterialName;
            public string ActualMaterialGuid;
            public bool MaterialMatchesExpected;
            public string[] DuplicateMarkerPaths;
            public string CurrentOwnerMaterialName;
            public string Notes;
        }
    }
}
#endif
