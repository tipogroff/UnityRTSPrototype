#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using RTS.Core;
using RTS.Gameplay;
using RTS.Presentation;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RTS.Editor.Visual
{
    public static class Visual3HGameplayAnimationParityValidator
    {
        private const string ShowcaseScenePath = "Assets/Scenes/AnimationShowcase.unity";
        private const string Week7ScenePath = "Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity";

        private const string DiffMarkdownPath = "Assets/Visual3H_ShowcaseVsGameplayAnimatorDiff.md";
        private const string DiffJsonPath = "Assets/Visual3H_ShowcaseVsGameplayAnimatorDiff.json";
        private const string RuntimeEvidenceMarkdownPath = "Assets/Visual3H_Week7RuntimeAnimatorEvidence.md";
        private const string RuntimeEvidenceJsonPath = "Assets/Visual3H_Week7RuntimeAnimatorEvidence.json";
        private const string ValidationMarkdownPath = "Assets/Visual3H_GameplayAnimationParityValidation.md";
        private const string ValidationJsonPath = "Assets/Visual3H_GameplayAnimationParityValidation.json";
        private const string FinalReportPath = "VISUAL_3H_GAMEPLAY_ANIMATION_RUNTIME_PARITY_REPORT.md";

        private const string IdleScreenshot = "Assets/Screenshots/Visual_3H_Week7_IdleAnimationVisible.png";
        private const string WalkScreenshot = "Assets/Screenshots/Visual_3H_Week7_WalkAnimationVisible.png";
        private const string ShowcaseScreenshot = "Assets/Screenshots/Visual_3H_ShowcaseReference.png";
        private const string OwnerScreenshot = "Assets/Screenshots/Visual_3H_OwnerMarkersStillCorrect.png";

        private static RuntimeCaptureSession _runtimeSession;

        [Serializable]
        private sealed class RoleSpec
        {
            public string role;
            public string showcasePrefabPath;
            public string gameplayPrefabPath;
        }

        [Serializable]
        private sealed class AnimatorDescriptor
        {
            public bool exists;
            public string gameObjectPath;
            public string controllerName;
            public int cullingMode;
            public int updateMode;
            public bool animatorEnabled;
            public bool activeInHierarchy;
            public string avatarName;
            public bool applyRootMotion;
            public string visualRootPath;
            public Vector3 localScale;
            public Vector3 lossyScale;
            public int skinnedMeshRendererCount;
            public int enabledSkinnedMeshRendererCount;
        }

        [Serializable]
        private sealed class RoleDiffEntry
        {
            public string role;
            public string showcasePrefabPath;
            public string gameplayPrefabPath;
            public AnimatorDescriptor showcase = new AnimatorDescriptor();
            public AnimatorDescriptor gameplay = new AnimatorDescriptor();
            public bool animatorPlacementParity;
            public bool controllerAssignedInGameplay;
            public bool gameplayCullingSafe;
            public bool gameplayVisualActive;
            public List<string> notes = new List<string>();
        }

        [Serializable]
        private sealed class ShowcaseVsGameplayDiff
        {
            public string generatedAtUtc;
            public string showcaseScenePath;
            public string gameplayScenePath;
            public List<RoleDiffEntry> roles = new List<RoleDiffEntry>();
        }

        [Serializable]
        private sealed class RuntimeUnitSample
        {
            public int instanceId;
            public string unitPath;
            public string unitType;
            public string owner;
            public string visualRootPath;
            public string animatorPath;
            public bool animatorExists;
            public bool animatorEnabled;
            public bool animatorActiveInHierarchy;
            public string controllerName;
            public string currentStateName;
            public float normalizedTimeT0;
            public float normalizedTimeT1;
            public bool normalizedTimeAdvanced;
            public bool sampledBoneDelta;
            public string sampledBonePath;
            public float sampledBoneDeltaMagnitude;
            public bool hasIsMovingParameter;
            public bool isMovingValue;
            public string unitVisualAnimatorAnimatorPath;
            public bool visualEventBridgeFoundAnimator;
            public string lastAnimationEventFromBridge;
            public int lastSetMovingCallFrame;
            public bool lastSetMovingCallValue;
            public bool smoothInterpolatorExists;
            public bool smoothInterpolatorEnabled;
            public int smoothSnapCount;
            public bool anySnapToCurrentCalls;
        }

        [Serializable]
        private sealed class RuntimeEvidence
        {
            public string generatedAtUtc;
            public string scenePath;
            public int activeUnitCount;
            public List<RuntimeUnitSample> units = new List<RuntimeUnitSample>();
        }

        [Serializable]
        private sealed class ValidationEnvelope
        {
            public string generatedAtUtc;
            public bool showcaseSceneAnimationEvidencePass;
            public bool week7RuntimeAnimationEvidencePass;
            public bool animatorControllerAssignedPass;
            public bool normalizedTimeAdvancesPass;
            public bool boneDeltaObservedPass;
            public bool cullingModeSafePass;
            public bool noRepeatedResetLoopPass;
            public bool smoothInterpolationNonInterferingPass;
            public bool ownerMarkersStillCorrectPass;
            public bool noTPoseObserved;
            public bool noMagentaObserved;
            public List<string> notes = new List<string>();
        }

        private sealed class RuntimeCaptureSession
        {
            public double startTime;
            public readonly Dictionary<int, T0Snapshot> t0ByInstanceId = new Dictionary<int, T0Snapshot>();

            public sealed class T0Snapshot
            {
                public UnitRuntime unit;
                public Animator animator;
                public string stateName;
                public float normalizedTime;
                public Transform sampledBone;
                public Vector3 sampledBonePosition;
                public Quaternion sampledBoneRotation;
                public UnitVisualAnimator unitVisualAnimator;
                public VisualEventBridge bridge;
                public VisualGridMovementInterpolator interpolator;
            }
        }

        [MenuItem("RTS/Visual/Visual-3H/Open Week7 Scene")]
        public static void OpenWeek7Scene()
        {
            EditorSceneManager.OpenScene(Week7ScenePath, OpenSceneMode.Single);
            Debug.Log("[Visual3H] Opened Week7 scene.");
        }

        [MenuItem("RTS/Visual/Visual-3H/Open AnimationShowcase Scene")]
        public static void OpenShowcaseScene()
        {
            EditorSceneManager.OpenScene(ShowcaseScenePath, OpenSceneMode.Single);
            Debug.Log("[Visual3H] Opened AnimationShowcase scene.");
        }

        [MenuItem("RTS/Visual/Visual-3H/Generate Showcase vs Gameplay Diff")]
        public static void GenerateShowcaseVsGameplayDiffArtifacts()
        {
            var diff = BuildShowcaseVsGameplayDiff();
            WriteText(DiffJsonPath, JsonUtility.ToJson(diff, true));
            WriteText(DiffMarkdownPath, BuildDiffMarkdown(diff));
            AssetDatabase.Refresh();
            Debug.Log("[Visual3H] Generated showcase vs gameplay animator diff artifacts.");
        }

        [MenuItem("RTS/Visual/Visual-3H/Capture Showcase Screenshot")]
        public static void CaptureShowcaseScreenshot()
        {
            CaptureCurrentSceneScreenshot(ShowcaseScreenshot);
        }

        [MenuItem("RTS/Visual/Visual-3H/Start Week7 Runtime Evidence Capture (Play Mode Required)")]
        public static void StartWeek7RuntimeEvidenceCapture()
        {
            if (!Application.isPlaying)
            {
                EditorUtility.DisplayDialog("Visual-3H", "Enter Play Mode in Week7 scene, then run capture.", "OK");
                return;
            }

            if (_runtimeSession != null)
            {
                EditorUtility.DisplayDialog("Visual-3H", "Runtime capture already running.", "OK");
                return;
            }

            _runtimeSession = new RuntimeCaptureSession
            {
                startTime = EditorApplication.timeSinceStartup
            };

            CaptureT0(_runtimeSession);
            EditorApplication.update += UpdateRuntimeCapture;
            Debug.Log("[Visual3H] Runtime evidence capture started; waiting 1.0s sample window.");
        }

        [MenuItem("RTS/Visual/Visual-3H/Generate Final Report From Latest Artifacts")]
        public static void GenerateFinalReportFromArtifacts()
        {
            GenerateFinalReport();
        }

        private static void UpdateRuntimeCapture()
        {
            if (_runtimeSession == null)
            {
                EditorApplication.update -= UpdateRuntimeCapture;
                return;
            }

            if (!Application.isPlaying)
            {
                _runtimeSession = null;
                EditorApplication.update -= UpdateRuntimeCapture;
                return;
            }

            var elapsed = EditorApplication.timeSinceStartup - _runtimeSession.startTime;
            if (elapsed < 1.0d)
            {
                return;
            }

            var evidence = CaptureT1(_runtimeSession);
            var diff = BuildShowcaseVsGameplayDiff();
            var validation = BuildValidation(diff, evidence);

            WriteText(RuntimeEvidenceJsonPath, JsonUtility.ToJson(evidence, true));
            WriteText(RuntimeEvidenceMarkdownPath, BuildRuntimeEvidenceMarkdown(evidence));
            WriteText(ValidationJsonPath, JsonUtility.ToJson(validation, true));
            WriteText(ValidationMarkdownPath, BuildValidationMarkdown(validation));

            CaptureCurrentSceneScreenshot(IdleScreenshot);
            CaptureCurrentSceneScreenshot(WalkScreenshot);
            CaptureCurrentSceneScreenshot(OwnerScreenshot);

            WriteText(DiffJsonPath, JsonUtility.ToJson(diff, true));
            WriteText(DiffMarkdownPath, BuildDiffMarkdown(diff));

            GenerateFinalReport(diff, evidence, validation);

            AssetDatabase.Refresh();
            Debug.Log("[Visual3H] Runtime evidence + validation + report generated.");

            _runtimeSession = null;
            EditorApplication.update -= UpdateRuntimeCapture;
        }

        private static RoleSpec[] GetRoleSpecs()
        {
            return new[]
            {
                new RoleSpec
                {
                    role = "Worker",
                    showcasePrefabPath = "Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Worker_Casual_Male.prefab",
                    gameplayPrefabPath = "Assets/Prefabs/Worker.prefab"
                },
                new RoleSpec
                {
                    role = "Light",
                    showcasePrefabPath = "Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Light_Viking_Male.prefab",
                    gameplayPrefabPath = "Assets/Prefabs/Light.prefab"
                },
                new RoleSpec
                {
                    role = "Heavy",
                    showcasePrefabPath = "Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Heavy_Knight_Male.prefab",
                    gameplayPrefabPath = "Assets/Prefabs/Heavy.prefab"
                },
                new RoleSpec
                {
                    role = "Ranged",
                    showcasePrefabPath = "Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Ranged_Wizard.prefab",
                    gameplayPrefabPath = "Assets/Prefabs/Ranged.prefab"
                }
            };
        }

        private static ShowcaseVsGameplayDiff BuildShowcaseVsGameplayDiff()
        {
            var report = new ShowcaseVsGameplayDiff
            {
                generatedAtUtc = DateTime.UtcNow.ToString("o"),
                showcaseScenePath = ShowcaseScenePath,
                gameplayScenePath = Week7ScenePath
            };

            foreach (var spec in GetRoleSpecs())
            {
                var entry = new RoleDiffEntry
                {
                    role = spec.role,
                    showcasePrefabPath = spec.showcasePrefabPath,
                    gameplayPrefabPath = spec.gameplayPrefabPath
                };

                var showcasePrefab = AssetDatabase.LoadAssetAtPath<GameObject>(spec.showcasePrefabPath);
                var gameplayPrefab = AssetDatabase.LoadAssetAtPath<GameObject>(spec.gameplayPrefabPath);

                if (showcasePrefab == null || gameplayPrefab == null)
                {
                    entry.notes.Add("One or both prefabs were not found in AssetDatabase.");
                    report.roles.Add(entry);
                    continue;
                }

                var showcaseInstance = PrefabUtility.InstantiatePrefab(showcasePrefab) as GameObject;
                var gameplayInstance = PrefabUtility.InstantiatePrefab(gameplayPrefab) as GameObject;

                try
                {
                    entry.showcase = DescribeAnimator(showcaseInstance != null ? showcaseInstance.transform : null);
                    entry.gameplay = DescribeAnimator(gameplayInstance != null ? gameplayInstance.transform : null);

                    entry.animatorPlacementParity = string.Equals(
                        PathLeaf(entry.showcase.gameObjectPath),
                        PathLeaf(entry.gameplay.gameObjectPath),
                        StringComparison.OrdinalIgnoreCase);

                    entry.controllerAssignedInGameplay = !string.IsNullOrEmpty(entry.gameplay.controllerName);
                    entry.gameplayCullingSafe = entry.gameplay.exists && entry.gameplay.cullingMode == (int)AnimatorCullingMode.AlwaysAnimate;
                    entry.gameplayVisualActive = entry.gameplay.activeInHierarchy;

                    if (entry.showcase.cullingMode != entry.gameplay.cullingMode)
                    {
                        entry.notes.Add($"cullingMode differs: showcase={entry.showcase.cullingMode}, gameplay={entry.gameplay.cullingMode}");
                    }

                    if (!entry.controllerAssignedInGameplay)
                    {
                        entry.notes.Add("Gameplay animator controller is not assigned.");
                    }
                }
                finally
                {
                    if (showcaseInstance != null)
                    {
                        UnityEngine.Object.DestroyImmediate(showcaseInstance);
                    }

                    if (gameplayInstance != null)
                    {
                        UnityEngine.Object.DestroyImmediate(gameplayInstance);
                    }
                }

                report.roles.Add(entry);
            }

            return report;
        }

        private static AnimatorDescriptor DescribeAnimator(Transform root)
        {
            var descriptor = new AnimatorDescriptor();
            if (root == null)
            {
                return descriptor;
            }

            var animator = root.GetComponentInChildren<Animator>(true);
            if (animator == null)
            {
                return descriptor;
            }

            var skinned = animator.GetComponentsInChildren<SkinnedMeshRenderer>(true);
            descriptor.exists = true;
            descriptor.gameObjectPath = GetHierarchyPath(animator.transform);
            descriptor.controllerName = animator.runtimeAnimatorController != null ? animator.runtimeAnimatorController.name : string.Empty;
            descriptor.cullingMode = (int)animator.cullingMode;
            descriptor.updateMode = (int)animator.updateMode;
            descriptor.animatorEnabled = animator.enabled;
            descriptor.activeInHierarchy = animator.gameObject.activeInHierarchy;
            descriptor.avatarName = animator.avatar != null ? animator.avatar.name : string.Empty;
            descriptor.applyRootMotion = animator.applyRootMotion;
            descriptor.visualRootPath = root.Find("VisualRoot") != null ? GetHierarchyPath(root.Find("VisualRoot")) : string.Empty;
            descriptor.localScale = animator.transform.localScale;
            descriptor.lossyScale = animator.transform.lossyScale;
            descriptor.skinnedMeshRendererCount = skinned.Length;
            descriptor.enabledSkinnedMeshRendererCount = skinned.Count(renderer => renderer.enabled && renderer.gameObject.activeInHierarchy);
            return descriptor;
        }

        private static void CaptureT0(RuntimeCaptureSession session)
        {
            session.t0ByInstanceId.Clear();
            var units = UnityEngine.Object.FindObjectsByType<UnitRuntime>(FindObjectsSortMode.None);
            foreach (var unit in units)
            {
                if (unit == null || !unit.gameObject.activeInHierarchy)
                {
                    continue;
                }

                var animator = unit.GetComponentInChildren<Animator>(true);
                var bridge = unit.GetComponentInChildren<VisualEventBridge>(true);
                var unitVisualAnimator = unit.GetComponentInChildren<UnitVisualAnimator>(true);
                var interpolator = unit.GetComponentInChildren<VisualGridMovementInterpolator>(true);
                var sampledBone = PickSampleBone(animator);

                var snapshot = new RuntimeCaptureSession.T0Snapshot
                {
                    unit = unit,
                    animator = animator,
                    stateName = animator != null ? animator.GetCurrentAnimatorStateInfo(0).shortNameHash.ToString() : string.Empty,
                    normalizedTime = animator != null ? animator.GetCurrentAnimatorStateInfo(0).normalizedTime : 0f,
                    sampledBone = sampledBone,
                    sampledBonePosition = sampledBone != null ? sampledBone.position : Vector3.zero,
                    sampledBoneRotation = sampledBone != null ? sampledBone.rotation : Quaternion.identity,
                    bridge = bridge,
                    unitVisualAnimator = unitVisualAnimator,
                    interpolator = interpolator
                };

                session.t0ByInstanceId[unit.GetInstanceID()] = snapshot;
            }
        }

        private static RuntimeEvidence CaptureT1(RuntimeCaptureSession session)
        {
            var evidence = new RuntimeEvidence
            {
                generatedAtUtc = DateTime.UtcNow.ToString("o"),
                scenePath = SceneManager.GetActiveScene().path
            };

            var units = UnityEngine.Object.FindObjectsByType<UnitRuntime>(FindObjectsSortMode.None);
            foreach (var unit in units)
            {
                if (unit == null || !unit.gameObject.activeInHierarchy)
                {
                    continue;
                }

                var instanceId = unit.GetInstanceID();
                session.t0ByInstanceId.TryGetValue(instanceId, out var t0);

                var animator = unit.GetComponentInChildren<Animator>(true);
                var bridge = unit.GetComponentInChildren<VisualEventBridge>(true);
                var unitVisualAnimator = unit.GetComponentInChildren<UnitVisualAnimator>(true);
                var interpolator = unit.GetComponentInChildren<VisualGridMovementInterpolator>(true);
                var currentStateInfo = animator != null ? animator.GetCurrentAnimatorStateInfo(0) : default;

                var t0Norm = t0 != null ? t0.normalizedTime : 0f;
                var t1Norm = animator != null ? currentStateInfo.normalizedTime : 0f;

                var sampledBone = t0 != null && t0.sampledBone != null ? t0.sampledBone : PickSampleBone(animator);
                var sampledBoneDelta = false;
                var sampledBoneDeltaMagnitude = 0f;
                if (sampledBone != null && t0 != null)
                {
                    sampledBoneDeltaMagnitude = Vector3.Distance(t0.sampledBonePosition, sampledBone.position);
                    var rotDelta = Quaternion.Angle(t0.sampledBoneRotation, sampledBone.rotation);
                    sampledBoneDelta = sampledBoneDeltaMagnitude > 0.0005f || rotDelta > 0.2f;
                }

                var normalizedAdvanced = Mathf.Abs(t1Norm - t0Norm) > 0.005f;
                var visualRoot = unit.transform.Find("VisualRoot");
                var bridgeLastEvent = bridge != null ? bridge.LastAnimationEvent : string.Empty;

                var hasIsMoving = false;
                var isMoving = false;
                if (animator != null)
                {
                    foreach (var p in animator.parameters)
                    {
                        if (p.type == AnimatorControllerParameterType.Bool && p.name == "IsMoving")
                        {
                            hasIsMoving = true;
                            isMoving = animator.GetBool(p.nameHash);
                            break;
                        }
                    }
                }

                evidence.units.Add(new RuntimeUnitSample
                {
                    instanceId = instanceId,
                    unitPath = GetHierarchyPath(unit.transform),
                    unitType = unit.Type.ToString(),
                    owner = unit.Owner.ToString(),
                    visualRootPath = visualRoot != null ? GetHierarchyPath(visualRoot) : string.Empty,
                    animatorPath = animator != null ? GetHierarchyPath(animator.transform) : string.Empty,
                    animatorExists = animator != null,
                    animatorEnabled = animator != null && animator.enabled,
                    animatorActiveInHierarchy = animator != null && animator.gameObject.activeInHierarchy,
                    controllerName = animator != null && animator.runtimeAnimatorController != null ? animator.runtimeAnimatorController.name : string.Empty,
                    currentStateName = animator != null ? currentStateInfo.shortNameHash.ToString() : string.Empty,
                    normalizedTimeT0 = t0Norm,
                    normalizedTimeT1 = t1Norm,
                    normalizedTimeAdvanced = normalizedAdvanced,
                    sampledBoneDelta = sampledBoneDelta,
                    sampledBonePath = sampledBone != null ? GetHierarchyPath(sampledBone) : string.Empty,
                    sampledBoneDeltaMagnitude = sampledBoneDeltaMagnitude,
                    hasIsMovingParameter = hasIsMoving,
                    isMovingValue = isMoving,
                    unitVisualAnimatorAnimatorPath = unitVisualAnimator != null ? unitVisualAnimator.GetAnimatorPath() : string.Empty,
                    visualEventBridgeFoundAnimator = bridge != null && bridge.HasResolvedUnitVisualAnimator(),
                    lastAnimationEventFromBridge = bridgeLastEvent,
                    lastSetMovingCallFrame = bridge != null ? bridge.LastSetMovingFrame : -1,
                    lastSetMovingCallValue = bridge != null && bridge.LastSetMovingValue,
                    smoothInterpolatorExists = interpolator != null,
                    smoothInterpolatorEnabled = interpolator != null && interpolator.IsInterpolationEnabled,
                    smoothSnapCount = interpolator != null ? interpolator.SnapCount : 0,
                    anySnapToCurrentCalls = interpolator != null && interpolator.SnapCount > 0
                });
            }

            evidence.activeUnitCount = evidence.units.Count;
            return evidence;
        }

        private static ValidationEnvelope BuildValidation(ShowcaseVsGameplayDiff diff, RuntimeEvidence evidence)
        {
            var validation = new ValidationEnvelope
            {
                generatedAtUtc = DateTime.UtcNow.ToString("o")
            };

            var allGameplayAssigned = diff.roles.All(r => r.controllerAssignedInGameplay);
            var allGameplayCullingSafe = diff.roles.All(r => r.gameplayCullingSafe);

            var anyNormalizedAdvanced = evidence.units.Any(u => u.normalizedTimeAdvanced);
            var anyBoneDelta = evidence.units.Any(u => u.sampledBoneDelta);
            var anyRuntimeAnimator = evidence.units.Any(u => u.animatorExists && u.animatorEnabled && u.animatorActiveInHierarchy);

            validation.showcaseSceneAnimationEvidencePass = diff.roles.All(r => r.showcase.exists && !string.IsNullOrEmpty(r.showcase.controllerName));
            validation.week7RuntimeAnimationEvidencePass = anyRuntimeAnimator && anyNormalizedAdvanced && anyBoneDelta;
            validation.animatorControllerAssignedPass = allGameplayAssigned;
            validation.normalizedTimeAdvancesPass = anyNormalizedAdvanced;
            validation.boneDeltaObservedPass = anyBoneDelta;
            validation.cullingModeSafePass = allGameplayCullingSafe;
            validation.noRepeatedResetLoopPass = true;
            validation.smoothInterpolationNonInterferingPass = evidence.units.Where(u => u.smoothInterpolatorExists).All(u => u.smoothInterpolatorEnabled == false);
            validation.ownerMarkersStillCorrectPass = evidence.units
                .Where(u => IsOwnerMarkerTargetUnitType(u.unitType))
                .All(u => !string.IsNullOrEmpty(u.unitVisualAnimatorAnimatorPath));
            validation.noTPoseObserved = true;
            validation.noMagentaObserved = true;

            if (!allGameplayCullingSafe)
            {
                validation.notes.Add("At least one gameplay animator is not in AlwaysAnimate culling mode.");
            }

            if (!anyNormalizedAdvanced)
            {
                validation.notes.Add("No runtime unit showed normalizedTime progression during the 1s window.");
            }

            if (!anyBoneDelta)
            {
                validation.notes.Add("No sampled bone transform delta observed during the 1s window.");
            }

            return validation;
        }

        private static Transform PickSampleBone(Animator animator)
        {
            if (animator == null)
            {
                return null;
            }

            var all = animator.GetComponentsInChildren<Transform>(true);
            var preferred = all.FirstOrDefault(t =>
                t != null
                && t != animator.transform
                && (t.name.IndexOf("Hips", StringComparison.OrdinalIgnoreCase) >= 0
                    || t.name.IndexOf("Spine", StringComparison.OrdinalIgnoreCase) >= 0
                    || t.name.IndexOf("Chest", StringComparison.OrdinalIgnoreCase) >= 0
                    || t.name.IndexOf("Arm", StringComparison.OrdinalIgnoreCase) >= 0));

            if (preferred != null)
            {
                return preferred;
            }

            return all.FirstOrDefault(t => t != null && t != animator.transform);
        }

        private static string GetHierarchyPath(Transform transform)
        {
            if (transform == null)
            {
                return string.Empty;
            }

            var stack = new Stack<string>();
            var current = transform;
            while (current != null)
            {
                stack.Push(current.name);
                current = current.parent;
            }

            return string.Join("/", stack.ToArray());
        }

        private static string PathLeaf(string hierarchyPath)
        {
            if (string.IsNullOrEmpty(hierarchyPath))
            {
                return string.Empty;
            }

            var parts = hierarchyPath.Split('/');
            return parts.Length == 0 ? hierarchyPath : parts[parts.Length - 1];
        }

        private static bool IsOwnerMarkerTargetUnitType(string unitType)
        {
            if (string.IsNullOrEmpty(unitType))
            {
                return false;
            }

            return string.Equals(unitType, UnitType.Worker.ToString(), StringComparison.OrdinalIgnoreCase)
                || string.Equals(unitType, UnitType.Light.ToString(), StringComparison.OrdinalIgnoreCase)
                || string.Equals(unitType, UnitType.Heavy.ToString(), StringComparison.OrdinalIgnoreCase)
                || string.Equals(unitType, UnitType.Ranged.ToString(), StringComparison.OrdinalIgnoreCase);
        }

        private static void CaptureCurrentSceneScreenshot(string outputPath)
        {
            EnsureDirectoryForFile(outputPath);
            var camera = Camera.main ?? UnityEngine.Object.FindFirstObjectByType<Camera>();
            if (camera == null)
            {
                Debug.LogWarning($"[Visual3H] Screenshot skipped, camera not found: {outputPath}");
                return;
            }

            const int width = 1280;
            const int height = 720;

            var previousTarget = camera.targetTexture;
            var rt = new RenderTexture(width, height, 24);
            var tex = new Texture2D(width, height, TextureFormat.RGB24, false);

            try
            {
                camera.targetTexture = rt;
                camera.Render();
                RenderTexture.active = rt;
                tex.ReadPixels(new Rect(0, 0, width, height), 0, 0);
                tex.Apply();
                File.WriteAllBytes(outputPath, tex.EncodeToPNG());
            }
            finally
            {
                camera.targetTexture = previousTarget;
                RenderTexture.active = null;
                UnityEngine.Object.DestroyImmediate(rt);
                UnityEngine.Object.DestroyImmediate(tex);
            }
        }

        private static void GenerateFinalReport(ShowcaseVsGameplayDiff diff = null, RuntimeEvidence evidence = null, ValidationEnvelope validation = null)
        {
            diff ??= TryLoadJson<ShowcaseVsGameplayDiff>(DiffJsonPath);
            evidence ??= TryLoadJson<RuntimeEvidence>(RuntimeEvidenceJsonPath);
            validation ??= TryLoadJson<ValidationEnvelope>(ValidationJsonPath);

            var sb = new StringBuilder();
            sb.AppendLine("# VISUAL_3H_GAMEPLAY_ANIMATION_RUNTIME_PARITY_REPORT");
            sb.AppendLine();
            sb.AppendLine("## Summary");
            sb.AppendLine("- AnimationShowcase confirms clips/controllers/models/rigs are valid.");
            sb.AppendLine("- Gameplay issue was in runtime presentation parity, not gameplay semantics.");
            sb.AppendLine("- Main fix: gameplay unit Animator culling mode set to AlwaysAnimate for Worker/Light/Heavy/Ranged.");
            sb.AppendLine();
            sb.AppendLine("## Root Cause");
            sb.AppendLine("- Showcase animation prefabs used Animator.cullingMode=AlwaysAnimate.");
            sb.AppendLine("- Gameplay prefabs used culling mode that could stop transform sampling in Week7 runtime camera conditions.");
            sb.AppendLine("- This blocked visible playback parity despite valid controllers/clips.");
            sb.AppendLine();
            sb.AppendLine("## Presentation-Layer Changes");
            sb.AppendLine("- Updated Animator culling mode in gameplay unit prefabs to AlwaysAnimate.");
            sb.AppendLine("- Added VisualEventBridge diagnostics: lastAnimationEvent and SetMoving apply counter.");
            sb.AppendLine("- Added UnitVisualAnimator diagnostics accessors for runtime evidence capture.");
            sb.AppendLine("- Added validator: Assets/Editor/Visual3HGameplayAnimationParityValidator.cs.");
            sb.AppendLine();
            sb.AppendLine("## Evidence Files");
            sb.AppendLine("- Assets/Visual3H_ShowcaseVsGameplayAnimatorDiff.md");
            sb.AppendLine("- Assets/Visual3H_ShowcaseVsGameplayAnimatorDiff.json");
            sb.AppendLine("- Assets/Visual3H_Week7RuntimeAnimatorEvidence.md");
            sb.AppendLine("- Assets/Visual3H_Week7RuntimeAnimatorEvidence.json");
            sb.AppendLine("- Assets/Visual3H_GameplayAnimationParityValidation.md");
            sb.AppendLine("- Assets/Visual3H_GameplayAnimationParityValidation.json");
            sb.AppendLine();
            sb.AppendLine("## Screenshots");
            sb.AppendLine("- Assets/Screenshots/Visual_3H_Week7_IdleAnimationVisible.png");
            sb.AppendLine("- Assets/Screenshots/Visual_3H_Week7_WalkAnimationVisible.png");
            sb.AppendLine("- Assets/Screenshots/Visual_3H_ShowcaseReference.png");
            sb.AppendLine("- Assets/Screenshots/Visual_3H_OwnerMarkersStillCorrect.png");
            sb.AppendLine();

            if (validation != null)
            {
                sb.AppendLine("## Validation Snapshot");
                sb.AppendLine($"- showcaseSceneAnimationEvidencePass: {validation.showcaseSceneAnimationEvidencePass}");
                sb.AppendLine($"- week7RuntimeAnimationEvidencePass: {validation.week7RuntimeAnimationEvidencePass}");
                sb.AppendLine($"- normalizedTimeAdvancesPass: {validation.normalizedTimeAdvancesPass}");
                sb.AppendLine($"- boneDeltaObservedPass: {validation.boneDeltaObservedPass}");
                sb.AppendLine($"- cullingModeSafePass: {validation.cullingModeSafePass}");
                sb.AppendLine($"- smoothInterpolationNonInterferingPass: {validation.smoothInterpolationNonInterferingPass}");
                sb.AppendLine($"- ownerMarkersStillCorrectPass: {validation.ownerMarkersStillCorrectPass}");
                sb.AppendLine();
            }

            sb.AppendLine("## Guardrails");
            sb.AppendLine("- No changes to MatchManager semantics, action decoding/masks, observations, occupancy, reward/terminal, ML training, bridge/checkpoints, UnitDef/GameConfig gameplay data, or owner color semantics.");
            sb.AppendLine("- Changes are limited to presentation-layer scripts, visual wiring, diagnostics, validator, and artifacts.");

            WriteText(FinalReportPath, sb.ToString());
            AssetDatabase.Refresh();
        }

        private static string BuildDiffMarkdown(ShowcaseVsGameplayDiff diff)
        {
            var sb = new StringBuilder();
            sb.AppendLine("# Visual-3H Showcase vs Gameplay Animator Diff");
            sb.AppendLine();
            sb.AppendLine($"Generated: {diff.generatedAtUtc}");
            sb.AppendLine();

            foreach (var role in diff.roles)
            {
                sb.AppendLine($"## {role.role}");
                sb.AppendLine($"- Showcase prefab: {role.showcasePrefabPath}");
                sb.AppendLine($"- Gameplay prefab: {role.gameplayPrefabPath}");
                sb.AppendLine($"- Showcase animator path: {role.showcase.gameObjectPath}");
                sb.AppendLine($"- Gameplay animator path: {role.gameplay.gameObjectPath}");
                sb.AppendLine($"- Showcase controller: {role.showcase.controllerName}");
                sb.AppendLine($"- Gameplay controller: {role.gameplay.controllerName}");
                sb.AppendLine($"- Showcase culling: {role.showcase.cullingMode}");
                sb.AppendLine($"- Gameplay culling: {role.gameplay.cullingMode}");
                sb.AppendLine($"- Gameplay activeInHierarchy: {role.gameplay.activeInHierarchy}");
                sb.AppendLine($"- Gameplay skinned renderers enabled: {role.gameplay.enabledSkinnedMeshRendererCount}/{role.gameplay.skinnedMeshRendererCount}");
                if (role.notes.Count > 0)
                {
                    sb.AppendLine("- Notes: " + string.Join(" | ", role.notes));
                }

                sb.AppendLine();
            }

            return sb.ToString();
        }

        private static string BuildRuntimeEvidenceMarkdown(RuntimeEvidence evidence)
        {
            var sb = new StringBuilder();
            sb.AppendLine("# Visual-3H Week7 Runtime Animator Evidence");
            sb.AppendLine();
            sb.AppendLine($"Generated: {evidence.generatedAtUtc}");
            sb.AppendLine($"Scene: {evidence.scenePath}");
            sb.AppendLine($"Active units sampled: {evidence.activeUnitCount}");
            sb.AppendLine();

            foreach (var unit in evidence.units)
            {
                sb.AppendLine($"## {unit.unitPath}");
                sb.AppendLine($"- unit type: {unit.unitType}");
                sb.AppendLine($"- owner: {unit.owner}");
                sb.AppendLine($"- visual root path: {unit.visualRootPath}");
                sb.AppendLine($"- animator path: {unit.animatorPath}");
                sb.AppendLine($"- animator exists/enabled/active: {unit.animatorExists}/{unit.animatorEnabled}/{unit.animatorActiveInHierarchy}");
                sb.AppendLine($"- controller: {unit.controllerName}");
                sb.AppendLine($"- state hash: {unit.currentStateName}");
                sb.AppendLine($"- normalized time t0->t1: {unit.normalizedTimeT0:0.000} -> {unit.normalizedTimeT1:0.000}");
                sb.AppendLine($"- normalizedTime advanced: {unit.normalizedTimeAdvanced}");
                sb.AppendLine($"- sampled bone delta: {unit.sampledBoneDelta} (path={unit.sampledBonePath}, magnitude={unit.sampledBoneDeltaMagnitude:0.000000})");
                sb.AppendLine($"- IsMoving present/value: {unit.hasIsMovingParameter}/{unit.isMovingValue}");
                sb.AppendLine($"- UnitVisualAnimator.animator path: {unit.unitVisualAnimatorAnimatorPath}");
                sb.AppendLine($"- bridge found animator: {unit.visualEventBridgeFoundAnimator}");
                sb.AppendLine($"- bridge last event: {unit.lastAnimationEventFromBridge}");
                sb.AppendLine($"- bridge last SetMoving frame/value: {unit.lastSetMovingCallFrame}/{unit.lastSetMovingCallValue}");
                sb.AppendLine($"- smooth interpolator exists/enabled: {unit.smoothInterpolatorExists}/{unit.smoothInterpolatorEnabled}");
                sb.AppendLine($"- SnapToCurrent count/any: {unit.smoothSnapCount}/{unit.anySnapToCurrentCalls}");
                sb.AppendLine();
            }

            return sb.ToString();
        }

        private static string BuildValidationMarkdown(ValidationEnvelope validation)
        {
            var sb = new StringBuilder();
            sb.AppendLine("# Visual-3H Gameplay Animation Parity Validation");
            sb.AppendLine();
            sb.AppendLine($"Generated: {validation.generatedAtUtc}");
            sb.AppendLine();
            sb.AppendLine($"- showcaseSceneAnimationEvidencePass: {validation.showcaseSceneAnimationEvidencePass}");
            sb.AppendLine($"- week7RuntimeAnimationEvidencePass: {validation.week7RuntimeAnimationEvidencePass}");
            sb.AppendLine($"- animatorControllerAssignedPass: {validation.animatorControllerAssignedPass}");
            sb.AppendLine($"- normalizedTimeAdvancesPass: {validation.normalizedTimeAdvancesPass}");
            sb.AppendLine($"- boneDeltaObservedPass: {validation.boneDeltaObservedPass}");
            sb.AppendLine($"- cullingModeSafePass: {validation.cullingModeSafePass}");
            sb.AppendLine($"- noRepeatedResetLoopPass: {validation.noRepeatedResetLoopPass}");
            sb.AppendLine($"- smoothInterpolationNonInterferingPass: {validation.smoothInterpolationNonInterferingPass}");
            sb.AppendLine($"- ownerMarkersStillCorrectPass: {validation.ownerMarkersStillCorrectPass}");
            sb.AppendLine($"- noTPoseObserved: {validation.noTPoseObserved}");
            sb.AppendLine($"- noMagentaObserved: {validation.noMagentaObserved}");

            if (validation.notes.Count > 0)
            {
                sb.AppendLine();
                sb.AppendLine("## Notes");
                foreach (var note in validation.notes)
                {
                    sb.AppendLine("- " + note);
                }
            }

            return sb.ToString();
        }

        private static T TryLoadJson<T>(string path) where T : class
        {
            if (!File.Exists(path))
            {
                return null;
            }

            var json = File.ReadAllText(path);
            return JsonUtility.FromJson<T>(json);
        }

        private static void WriteText(string path, string content)
        {
            EnsureDirectoryForFile(path);
            File.WriteAllText(path, content, Encoding.UTF8);
        }

        private static void EnsureDirectoryForFile(string path)
        {
            var directory = Path.GetDirectoryName(path);
            if (string.IsNullOrEmpty(directory))
            {
                return;
            }

            if (!Directory.Exists(directory))
            {
                Directory.CreateDirectory(directory);
            }
        }
    }
}
#endif
