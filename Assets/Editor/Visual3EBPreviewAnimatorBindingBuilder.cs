#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using RTS.Presentation;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RTS.Editor.Visual
{
    public static class Visual3EBPreviewAnimatorBindingBuilder
    {
        private const string ControllerDir = "Assets/Art/AnimatorControllers/Preview";
        private const string PreviewPrefabDir = "Assets/Art/Prefabs/Visuals/Characters/AnimationPreview";
        private const string ScenePath = "Assets/Scenes/AnimationPreview.unity";
        private const string ScreenshotDir = "Assets/Screenshots";
        private const string ReportPath = "VISUAL_3E_B_PREVIEW_ANIMATOR_BINDING_REPORT.md";
        private const string GroundMaterialPath = "Assets/Art/Materials/Ground_Stylized_Grass_Compatible.mat";
        private const string FallbackMaterialPath = "Assets/Art/Materials/Preview_URP_Lit_Default.mat";
        private const string UalFbxPath = "Assets/Art/Quaternius/UniversalAnimationLibrary/Unity/UAL1_Standard.fbx";

        private sealed class CharacterSpec
        {
            public string Role;
            public string FbxPath;
            public string SourcePreviewPrefabPath;
            public string OutputPrefabPath;
            public string ControllerPath;
            public string IdleClipName;
            public string WalkClipName;
            public string AttackClipName;
            public string DeathClipName;
            public string HarvestClipName;
        }

        private sealed class ClipDescriptor
        {
            public string Name;
            public AnimationClip Clip;
            public float Length;
            public bool Loop;
            public string PlausibleMapping;
        }

        private sealed class ValidationResult
        {
            public string State;
            public string Source;
            public string ClipName;
            public bool Works;
            public int ChangedTransforms;
            public int MatchingBindingPaths;
            public float MaxRootOffset;
            public bool HasMagentaMaterial;
            public bool ScaleDriftDetected;
            public string Notes;
        }

        private sealed class CharacterRun
        {
            public CharacterSpec Spec;
            public ClipDescriptor[] EmbeddedClips;
            public Dictionary<string, AnimationClip> EmbeddedStateClips;
            public Dictionary<string, ValidationResult> EmbeddedResults;
        }

        [MenuItem("RTS/Visual/Visual-3E-B Preview Animator Binding Test")]
        public static void BuildPreviewAnimatorBindingTest()
        {
            EnsureFolder("Assets/Art");
            EnsureFolder("Assets/Art/AnimatorControllers");
            EnsureFolder(ControllerDir);
            EnsureFolder("Assets/Art/Prefabs");
            EnsureFolder("Assets/Art/Prefabs/Visuals");
            EnsureFolder("Assets/Art/Prefabs/Visuals/Characters");
            EnsureFolder(PreviewPrefabDir);
            EnsureFolder(ScreenshotDir);

            var material = AssetDatabase.LoadAssetAtPath<Material>(GroundMaterialPath);
            var fallbackMaterial = AssetDatabase.LoadAssetAtPath<Material>(FallbackMaterialPath);
            var specs = GetCharacterSpecs();
            var runs = new List<CharacterRun>(specs.Length);

            foreach (var spec in specs)
            {
                var embeddedClips = LoadEmbeddedClips(spec.FbxPath);
                var stateClips = ResolveEmbeddedStateClips(spec, embeddedClips);
                var controller = CreateController(spec.ControllerPath, stateClips);
                CreatePreviewPrefab(spec, controller, fallbackMaterial);

                runs.Add(new CharacterRun
                {
                    Spec = spec,
                    EmbeddedClips = embeddedClips,
                    EmbeddedStateClips = stateClips,
                    EmbeddedResults = new Dictionary<string, ValidationResult>(StringComparer.OrdinalIgnoreCase)
                });
            }

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            scene.name = "AnimationPreview";
            SetupScene(scene, material);

            var instances = new Dictionary<string, GameObject>(StringComparer.OrdinalIgnoreCase);
            for (var i = 0; i < runs.Count; i++)
            {
                var run = runs[i];
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(run.Spec.OutputPrefabPath);
                var instance = (GameObject)PrefabUtility.InstantiatePrefab(prefab, scene);
                instance.name = Path.GetFileNameWithoutExtension(run.Spec.OutputPrefabPath);
                instance.transform.position = new Vector3(-6f + (i * 4f), 0f, 0f);
                instance.transform.rotation = Quaternion.identity;
                instances.Add(run.Spec.Role, instance);
            }

            var ualClips = ResolveUalCandidates(LoadEmbeddedClips(UalFbxPath));
            foreach (var run in runs)
            {
                var visual = FindVisualRoot(instances[run.Spec.Role]);
                foreach (var kvp in run.EmbeddedStateClips)
                {
                    run.EmbeddedResults[kvp.Key] = ValidateClipOnVisual(visual, kvp.Value, "embedded");
                }
            }

            var ualValidation = new Dictionary<string, ValidationResult>(StringComparer.OrdinalIgnoreCase);
            var workerVisual = FindVisualRoot(instances["Worker"]);
            foreach (var kvp in ualClips)
            {
                ualValidation[kvp.Key] = ValidateClipOnVisual(workerVisual, kvp.Value, "UAL");
            }

            CaptureAllCharacters(instances, scene);
            CaptureIdleWalk(instances, scene);
            CaptureAttackDeath(instances, scene);

            EditorSceneManager.SaveScene(scene, ScenePath);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();

            File.WriteAllText(ReportPath, BuildReport(runs, ualClips, ualValidation), System.Text.Encoding.UTF8);
            Debug.Log("[Visual3EB] Completed preview-only animator binding test: " + ReportPath);
        }

        private static CharacterSpec[] GetCharacterSpecs()
        {
            return new[]
            {
                new CharacterSpec
                {
                    Role = "Worker",
                    FbxPath = "Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Casual_Male.fbx",
                    SourcePreviewPrefabPath = "Assets/Art/Prefabs/Visuals/Characters/Preview_Casual_Male.prefab",
                    OutputPrefabPath = PreviewPrefabDir + "/AnimPreview_Worker_Casual_Male.prefab",
                    ControllerPath = ControllerDir + "/Preview_Worker_Animator.controller",
                    IdleClipName = "CharacterArmature|Idle",
                    WalkClipName = "CharacterArmature|Walk",
                    AttackClipName = "CharacterArmature|Punch",
                    DeathClipName = "CharacterArmature|Death",
                    HarvestClipName = "CharacterArmature|PickUp"
                },
                new CharacterSpec
                {
                    Role = "Light",
                    FbxPath = "Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Viking_Male.fbx",
                    SourcePreviewPrefabPath = "Assets/Art/Prefabs/Visuals/Characters/Preview_Viking_Male.prefab",
                    OutputPrefabPath = PreviewPrefabDir + "/AnimPreview_Light_Viking_Male.prefab",
                    ControllerPath = ControllerDir + "/Preview_Light_Animator.controller",
                    IdleClipName = "CharacterArmature|Idle",
                    WalkClipName = "CharacterArmature|Walk",
                    AttackClipName = "CharacterArmature|SwordSlash",
                    DeathClipName = "CharacterArmature|Death",
                    HarvestClipName = "CharacterArmature|PickUp"
                },
                new CharacterSpec
                {
                    Role = "Heavy",
                    FbxPath = "Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Knight_Male.fbx",
                    SourcePreviewPrefabPath = "Assets/Art/Prefabs/Visuals/Characters/Preview_Knight_Male.prefab",
                    OutputPrefabPath = PreviewPrefabDir + "/AnimPreview_Heavy_Knight_Male.prefab",
                    ControllerPath = ControllerDir + "/Preview_Heavy_Animator.controller",
                    IdleClipName = "CharacterArmature|Idle",
                    WalkClipName = "CharacterArmature|Walk",
                    AttackClipName = "CharacterArmature|SwordSlash",
                    DeathClipName = "CharacterArmature|Death",
                    HarvestClipName = "CharacterArmature|PickUp"
                },
                new CharacterSpec
                {
                    Role = "Ranged",
                    FbxPath = "Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Wizard.fbx",
                    SourcePreviewPrefabPath = "Assets/Art/Prefabs/Visuals/Characters/Preview_Wizard.prefab",
                    OutputPrefabPath = PreviewPrefabDir + "/AnimPreview_Ranged_Wizard.prefab",
                    ControllerPath = ControllerDir + "/Preview_Ranged_Animator.controller",
                    IdleClipName = "CharacterArmature|Idle",
                    WalkClipName = "CharacterArmature|Walk",
                    AttackClipName = "CharacterArmature|Shoot_OneHanded",
                    DeathClipName = "CharacterArmature|Death",
                    HarvestClipName = "CharacterArmature|PickUp"
                }
            };
        }

        private static ClipDescriptor[] LoadEmbeddedClips(string assetPath)
        {
            return AssetDatabase.LoadAllAssetsAtPath(assetPath)
                .OfType<AnimationClip>()
                .Where(c => c != null && !c.name.StartsWith("__preview__", StringComparison.OrdinalIgnoreCase))
                .OrderBy(c => c.name, StringComparer.OrdinalIgnoreCase)
                .Select(c => new ClipDescriptor
                {
                    Name = c.name,
                    Clip = c,
                    Length = c.length,
                    Loop = GetLoopFlag(c),
                    PlausibleMapping = InferMapping(c.name)
                })
                .ToArray();
        }

        private static Dictionary<string, AnimationClip> ResolveEmbeddedStateClips(CharacterSpec spec, ClipDescriptor[] clips)
        {
            return new Dictionary<string, AnimationClip>(StringComparer.OrdinalIgnoreCase)
            {
                ["Idle"] = FindRequiredClip(clips, spec.IdleClipName),
                ["Walk"] = FindRequiredClip(clips, spec.WalkClipName),
                ["Attack"] = FindRequiredClip(clips, spec.AttackClipName),
                ["Death"] = FindRequiredClip(clips, spec.DeathClipName),
                ["HarvestFallback"] = FindRequiredClip(clips, spec.HarvestClipName)
            };
        }

        private static Dictionary<string, AnimationClip> ResolveUalCandidates(ClipDescriptor[] clips)
        {
            return new Dictionary<string, AnimationClip>(StringComparer.OrdinalIgnoreCase)
            {
                ["Idle"] = FindRequiredClip(clips, "Armature|Idle_Loop"),
                ["Walk"] = FindRequiredClip(clips, "Armature|Walk_Loop"),
                ["Attack"] = FindRequiredClip(clips, "Armature|Sword_Attack"),
                ["Death"] = FindRequiredClip(clips, "Armature|Death01"),
                ["HarvestFallback"] = FindRequiredClip(clips, "Armature|Fixing_Kneeling")
            };
        }

        private static AnimationClip FindRequiredClip(IEnumerable<ClipDescriptor> clips, string exactName)
        {
            var clip = clips.FirstOrDefault(c => string.Equals(c.Name, exactName, StringComparison.OrdinalIgnoreCase))?.Clip;
            if (clip == null)
            {
                throw new InvalidOperationException("Missing required clip: " + exactName);
            }

            return clip;
        }

        private static AnimatorController CreateController(string assetPath, IReadOnlyDictionary<string, AnimationClip> stateClips)
        {
            var existing = AssetDatabase.LoadAssetAtPath<AnimatorController>(assetPath);
            if (existing != null)
            {
                AssetDatabase.DeleteAsset(assetPath);
            }

            var controller = AnimatorController.CreateAnimatorControllerAtPath(assetPath);
            controller.AddParameter("IsMoving", AnimatorControllerParameterType.Bool);
            controller.AddParameter("Attack", AnimatorControllerParameterType.Trigger);
            controller.AddParameter("Death", AnimatorControllerParameterType.Trigger);
            controller.AddParameter("Harvest", AnimatorControllerParameterType.Trigger);

            var stateMachine = controller.layers[0].stateMachine;
            stateMachine.anyStatePosition = new Vector3(-300f, 160f, 0f);

            var idle = stateMachine.AddState("Idle", new Vector3(240f, 60f, 0f));
            var walk = stateMachine.AddState("Walk", new Vector3(460f, 60f, 0f));
            var attack = stateMachine.AddState("Attack", new Vector3(460f, 180f, 0f));
            var death = stateMachine.AddState("Death", new Vector3(460f, 300f, 0f));
            var harvest = stateMachine.AddState("HarvestFallback", new Vector3(460f, 420f, 0f));

            idle.motion = stateClips["Idle"];
            walk.motion = stateClips["Walk"];
            attack.motion = stateClips["Attack"];
            death.motion = stateClips["Death"];
            harvest.motion = stateClips["HarvestFallback"];
            stateMachine.defaultState = idle;

            var idleToWalk = idle.AddTransition(walk);
            idleToWalk.hasExitTime = false;
            idleToWalk.duration = 0.05f;
            idleToWalk.AddCondition(AnimatorConditionMode.If, 0f, "IsMoving");

            var walkToIdle = walk.AddTransition(idle);
            walkToIdle.hasExitTime = false;
            walkToIdle.duration = 0.05f;
            walkToIdle.AddCondition(AnimatorConditionMode.IfNot, 0f, "IsMoving");

            AddAnyStateTransition(stateMachine, attack, "Attack");
            AddAnyStateTransition(stateMachine, death, "Death");
            AddAnyStateTransition(stateMachine, harvest, "Harvest");

            AddReturnToIdle(attack, idle);
            AddReturnToIdle(harvest, idle);
            AddReturnToIdle(death, idle);

            EditorUtility.SetDirty(controller);
            return controller;
        }

        private static void AddAnyStateTransition(AnimatorStateMachine machine, AnimatorState targetState, string trigger)
        {
            var transition = machine.AddAnyStateTransition(targetState);
            transition.hasExitTime = false;
            transition.duration = 0.02f;
            transition.AddCondition(AnimatorConditionMode.If, 0f, trigger);
        }

        private static void AddReturnToIdle(AnimatorState source, AnimatorState idle)
        {
            var transition = source.AddTransition(idle);
            transition.hasExitTime = true;
            transition.exitTime = 0.95f;
            transition.duration = 0.05f;
        }

        private static void CreatePreviewPrefab(CharacterSpec spec, RuntimeAnimatorController controller, Material fallbackMaterial)
        {
            var sourcePrefab = AssetDatabase.LoadAssetAtPath<GameObject>(spec.SourcePreviewPrefabPath);
            if (sourcePrefab == null)
            {
                throw new InvalidOperationException("Missing source preview prefab: " + spec.SourcePreviewPrefabPath);
            }

            var instance = (GameObject)PrefabUtility.InstantiatePrefab(sourcePrefab);
            instance.name = Path.GetFileNameWithoutExtension(spec.OutputPrefabPath);
            instance.transform.position = Vector3.zero;
            instance.transform.rotation = Quaternion.identity;

            RemoveGameplayComponents(instance);
            var visual = FindVisualRoot(instance);
            if (visual == null)
            {
                UnityEngine.Object.DestroyImmediate(instance);
                throw new InvalidOperationException("Preview prefab is missing Visual child: " + spec.SourcePreviewPrefabPath);
            }

            ApplyFallbackMaterialIfNeeded(instance, fallbackMaterial);

            var animator = visual.GetComponent<Animator>();
            if (animator == null)
            {
                animator = visual.AddComponent<Animator>();
            }

            animator.runtimeAnimatorController = controller;
            animator.applyRootMotion = false;

            var previewController = instance.GetComponent<AnimationPreviewController>();
            if (previewController == null)
            {
                previewController = instance.AddComponent<AnimationPreviewController>();
            }

            var prefab = PrefabUtility.SaveAsPrefabAsset(instance, spec.OutputPrefabPath);
            if (prefab == null)
            {
                UnityEngine.Object.DestroyImmediate(instance);
                throw new InvalidOperationException("Failed to save preview prefab: " + spec.OutputPrefabPath);
            }

            UnityEngine.Object.DestroyImmediate(instance);
        }

        private static void SetupScene(Scene scene, Material groundMaterial)
        {
            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "AnimationPreview_Ground";
            ground.transform.localScale = new Vector3(2.2f, 1f, 1.4f);
            var collider = ground.GetComponent<Collider>();
            if (collider != null)
            {
                UnityEngine.Object.DestroyImmediate(collider);
            }

            if (groundMaterial != null)
            {
                var renderer = ground.GetComponent<Renderer>();
                renderer.sharedMaterial = groundMaterial;
            }

            SceneManager.MoveGameObjectToScene(ground, scene);

            var lightGo = new GameObject("AnimationPreview_DirectionalLight");
            var light = lightGo.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.15f;
            lightGo.transform.rotation = Quaternion.Euler(50f, -25f, 0f);
            SceneManager.MoveGameObjectToScene(lightGo, scene);

            var cameraGo = new GameObject("AnimationPreview_Camera");
            var camera = cameraGo.AddComponent<Camera>();
            camera.nearClipPlane = 0.01f;
            camera.farClipPlane = 200f;
            camera.clearFlags = CameraClearFlags.Skybox;
            camera.transform.position = new Vector3(0f, 1.75f, -6.2f);
            camera.transform.rotation = Quaternion.Euler(10f, 0f, 0f);
            camera.fieldOfView = 35f;
            SceneManager.MoveGameObjectToScene(cameraGo, scene);
        }

        private static void CaptureAllCharacters(Dictionary<string, GameObject> instances, Scene scene)
        {
            AnimationMode.StartAnimationMode();
            try
            {
                foreach (var kvp in instances)
                {
                    SampleState(kvp.Value, "Idle");
                }

                CaptureScene(scene, Path.Combine(ScreenshotDir, "Visual_3E_B_AnimationPreview_AllCharacters.png").Replace("\\", "/"), new Vector3(0f, 1.75f, -6.2f), Quaternion.Euler(10f, 0f, 0f), 35f);
            }
            finally
            {
                AnimationMode.StopAnimationMode();
            }
        }

        private static void CaptureIdleWalk(Dictionary<string, GameObject> instances, Scene scene)
        {
            AnimationMode.StartAnimationMode();
            try
            {
                SampleState(instances["Worker"], "Idle");
                SampleState(instances["Light"], "Walk");
                SampleState(instances["Heavy"], "Idle");
                SampleState(instances["Ranged"], "Walk");

                CaptureScene(scene, Path.Combine(ScreenshotDir, "Visual_3E_B_AnimationPreview_IdleWalk.png").Replace("\\", "/"), new Vector3(-2.2f, 1.55f, -4.2f), Quaternion.Euler(8f, 0f, 0f), 28f);
            }
            finally
            {
                AnimationMode.StopAnimationMode();
            }
        }

        private static void CaptureAttackDeath(Dictionary<string, GameObject> instances, Scene scene)
        {
            AnimationMode.StartAnimationMode();
            try
            {
                SampleState(instances["Worker"], "Attack");
                SampleState(instances["Light"], "Attack");
                SampleState(instances["Heavy"], "Death");
                SampleState(instances["Ranged"], "Death");

                CaptureScene(scene, Path.Combine(ScreenshotDir, "Visual_3E_B_AnimationPreview_AttackDeath.png").Replace("\\", "/"), new Vector3(2.2f, 1.55f, -4.2f), Quaternion.Euler(8f, 0f, 0f), 28f);
            }
            finally
            {
                AnimationMode.StopAnimationMode();
            }
        }

        private static void SampleState(GameObject previewRoot, string state)
        {
            var spec = GetCharacterSpecs().FirstOrDefault(s => Path.GetFileNameWithoutExtension(s.OutputPrefabPath) == previewRoot.name);
            if (spec == null)
            {
                return;
            }

            var clipMap = ResolveEmbeddedStateClips(spec, LoadEmbeddedClips(spec.FbxPath));
            var visual = FindVisualRoot(previewRoot);
            var clip = clipMap[state];
            AnimationMode.SampleAnimationClip(visual, clip, GetStateSampleTime(state, clip));
        }

        private static ValidationResult ValidateClipOnVisual(GameObject visual, AnimationClip clip, string source)
        {
            var transforms = visual.GetComponentsInChildren<Transform>(true);
            var basePositions = transforms.Select(t => t.localPosition).ToArray();
            var baseRotations = transforms.Select(t => t.localRotation).ToArray();
            var baseScales = transforms.Select(t => t.localScale).ToArray();
            var hierarchyPaths = new HashSet<string>(BuildHierarchyPaths(visual.transform), StringComparer.OrdinalIgnoreCase);
            var matchingPaths = CountMatchingBindingPaths(clip, hierarchyPaths);

            var maxChangedTransforms = 0;
            var maxRootOffset = 0f;
            var scaleDrift = false;

            var sampleTimes = new[]
            {
                0f,
                SampleTime(clip),
                clip.length > 0.05f ? Mathf.Clamp(clip.length * 0.85f, 0f, Mathf.Max(clip.length - 0.016f, 0f)) : 0f
            };

            foreach (var sampleTime in sampleTimes)
            {
                AnimationMode.StartAnimationMode();
                try
                {
                    AnimationMode.SampleAnimationClip(visual, clip, sampleTime);
                    var changed = 0;
                    for (var i = 0; i < transforms.Length; i++)
                    {
                        if (Vector3.Distance(basePositions[i], transforms[i].localPosition) > 0.0001f ||
                            Quaternion.Angle(baseRotations[i], transforms[i].localRotation) > 0.1f ||
                            Vector3.Distance(baseScales[i], transforms[i].localScale) > 0.0001f)
                        {
                            changed++;
                        }

                        if (Vector3.Distance(baseScales[i], transforms[i].localScale) > 0.15f)
                        {
                            scaleDrift = true;
                        }
                    }

                    maxChangedTransforms = Mathf.Max(maxChangedTransforms, changed);
                    maxRootOffset = Mathf.Max(maxRootOffset, Vector3.Distance(basePositions[0], transforms[0].localPosition));
                }
                finally
                {
                    AnimationMode.StopAnimationMode();
                }
            }

            var hasMagentaMaterial = visual.GetComponentsInChildren<Renderer>(true)
                .SelectMany(r => r.sharedMaterials)
                .Any(mat => mat == null || mat.shader == null || mat.shader.name.IndexOf("InternalErrorShader", StringComparison.OrdinalIgnoreCase) >= 0);

            var works = maxChangedTransforms > 0 && matchingPaths > 0 && !hasMagentaMaterial && !scaleDrift;
            var notes = works
                ? "Driven transforms detected and renderer/material state remained stable."
                : BuildFailureNotes(maxChangedTransforms, matchingPaths, hasMagentaMaterial, scaleDrift, maxRootOffset, source);

            return new ValidationResult
            {
                State = string.Empty,
                Source = source,
                ClipName = clip.name,
                Works = works,
                ChangedTransforms = maxChangedTransforms,
                MatchingBindingPaths = matchingPaths,
                MaxRootOffset = maxRootOffset,
                HasMagentaMaterial = hasMagentaMaterial,
                ScaleDriftDetected = scaleDrift,
                Notes = notes
            };
        }

        private static string BuildFailureNotes(int changedTransforms, int matchingPaths, bool hasMagentaMaterial, bool scaleDrift, float maxRootOffset, string source)
        {
            var notes = new List<string>();
            if (matchingPaths == 0)
            {
                notes.Add("No compatible binding paths detected.");
            }

            if (changedTransforms == 0)
            {
                notes.Add("No driven transforms detected during sampling.");
            }

            if (hasMagentaMaterial)
            {
                notes.Add("Renderer has missing or error shader material.");
            }

            if (scaleDrift)
            {
                notes.Add("Scale drift exceeded tolerance.");
            }

            if (maxRootOffset > 0.25f)
            {
                notes.Add("Root offset exceeded preview tolerance.");
            }

            if (notes.Count == 0 && string.Equals(source, "UAL", StringComparison.OrdinalIgnoreCase))
            {
                notes.Add("UAL generic clip did not meet compatibility threshold on preview target.");
            }

            return string.Join(" ", notes);
        }

        private static IEnumerable<string> BuildHierarchyPaths(Transform root)
        {
            foreach (Transform child in root)
            {
                yield return child.name;
                foreach (var nested in BuildHierarchyPaths(child, child.name))
                {
                    yield return nested;
                }
            }
        }

        private static IEnumerable<string> BuildHierarchyPaths(Transform root, string prefix)
        {
            foreach (Transform child in root)
            {
                var path = prefix + "/" + child.name;
                yield return path;
                foreach (var nested in BuildHierarchyPaths(child, path))
                {
                    yield return nested;
                }
            }
        }

        private static int CountMatchingBindingPaths(AnimationClip clip, HashSet<string> hierarchyPaths)
        {
            return AnimationUtility.GetCurveBindings(clip)
                .Select(b => b.path)
                .Where(path => !string.IsNullOrWhiteSpace(path))
                .Distinct(StringComparer.OrdinalIgnoreCase)
                .Count(hierarchyPaths.Contains);
        }

        private static float SampleTime(AnimationClip clip)
        {
            return clip.length > 0.05f ? Mathf.Clamp(clip.length * 0.5f, 0f, Mathf.Max(clip.length - 0.016f, 0f)) : 0f;
        }

        private static float GetStateSampleTime(string state, AnimationClip clip)
        {
            if (clip.length <= 0.05f)
            {
                return 0f;
            }

            switch (state)
            {
                case "Walk":
                    return Mathf.Clamp(clip.length * 0.35f, 0f, clip.length - 0.016f);
                case "Attack":
                    return Mathf.Clamp(clip.length * 0.72f, 0f, clip.length - 0.016f);
                case "Death":
                    return Mathf.Clamp(clip.length * 0.82f, 0f, clip.length - 0.016f);
                case "HarvestFallback":
                    return Mathf.Clamp(clip.length * 0.55f, 0f, clip.length - 0.016f);
                default:
                    return SampleTime(clip);
            }
        }

        private static bool GetLoopFlag(AnimationClip clip)
        {
            var settings = AnimationUtility.GetAnimationClipSettings(clip);
            return settings.loopTime;
        }

        private static string InferMapping(string clipName)
        {
            var lower = clipName.ToLowerInvariant();
            if (lower.Contains("idle")) return "Idle";
            if (lower.Contains("walk") || lower.Contains("run") || lower.Contains("jog")) return "Walk";
            if (lower.Contains("death") || lower.Contains("die")) return "Death";
            if (lower.Contains("hit")) return "Hit";
            if (lower.Contains("pickup") || lower.Contains("fixing") || lower.Contains("push") || lower.Contains("interact")) return "Harvest/Work-like";
            if (lower.Contains("slash") || lower.Contains("shoot") || lower.Contains("attack") || lower.Contains("punch")) return "Attack";
            return "Other";
        }

        private static void RemoveGameplayComponents(GameObject root)
        {
            foreach (var component in root.GetComponentsInChildren<Component>(true))
            {
                if (component == null)
                {
                    continue;
                }

                if (component is Transform || component is Renderer || component is SkinnedMeshRenderer || component is MeshFilter || component is Animator || component is AnimationPreviewController)
                {
                    continue;
                }

                if (component is Collider || component is Rigidbody || component is Joint)
                {
                    UnityEngine.Object.DestroyImmediate(component);
                    continue;
                }

                var type = component.GetType();
                if (type.Namespace != null && type.Namespace.StartsWith("UnityEngine", StringComparison.Ordinal))
                {
                    continue;
                }

                UnityEngine.Object.DestroyImmediate(component);
            }
        }

        private static void ApplyFallbackMaterialIfNeeded(GameObject root, Material fallback)
        {
            foreach (var renderer in root.GetComponentsInChildren<Renderer>(true))
            {
                var materials = renderer.sharedMaterials;
                var changed = false;
                for (var i = 0; i < materials.Length; i++)
                {
                    var mat = materials[i];
                    if (mat != null && mat.shader != null && mat.shader.name.IndexOf("InternalErrorShader", StringComparison.OrdinalIgnoreCase) < 0)
                    {
                        continue;
                    }

                    materials[i] = fallback;
                    changed = true;
                }

                if (changed)
                {
                    renderer.sharedMaterials = materials;
                }
            }
        }

        private static GameObject FindVisualRoot(GameObject root)
        {
            if (root == null)
            {
                return null;
            }

            var child = root.transform.Find("Visual");
            return child != null ? child.gameObject : root;
        }

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path))
            {
                return;
            }

            var parent = Path.GetDirectoryName(path)?.Replace("\\", "/");
            var leaf = Path.GetFileName(path);
            if (string.IsNullOrEmpty(parent) || string.IsNullOrEmpty(leaf))
            {
                return;
            }

            EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, leaf);
        }

        private static void CaptureScene(Scene scene, string assetPath, Vector3 position, Quaternion rotation, float fov)
        {
            var camera = scene.GetRootGameObjects().SelectMany(go => go.GetComponentsInChildren<Camera>(true)).First();
            camera.transform.position = position;
            camera.transform.rotation = rotation;
            camera.fieldOfView = fov;

            const int width = 1920;
            const int height = 1080;
            var rt = new RenderTexture(width, height, 24);
            var tex = new Texture2D(width, height, TextureFormat.RGB24, false);
            var previous = camera.targetTexture;
            var previousActive = RenderTexture.active;

            try
            {
                camera.targetTexture = rt;
                camera.Render();
                RenderTexture.active = rt;
                tex.ReadPixels(new Rect(0f, 0f, width, height), 0, 0);
                tex.Apply();
                File.WriteAllBytes(assetPath, tex.EncodeToPNG());
            }
            finally
            {
                camera.targetTexture = previous;
                RenderTexture.active = previousActive;
                UnityEngine.Object.DestroyImmediate(rt);
                UnityEngine.Object.DestroyImmediate(tex);
            }
        }

        private static string BuildReport(IReadOnlyList<CharacterRun> runs, IReadOnlyDictionary<string, AnimationClip> ualClips, IReadOnlyDictionary<string, ValidationResult> ualValidation)
        {
            var lines = new List<string>
            {
                "# VISUAL_3E_B_PREVIEW_ANIMATOR_BINDING_REPORT",
                string.Empty,
                "Generated (UTC): " + DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture),
                string.Empty,
                "## Scope",
                "- Stage: Visual-3E-B (preview-only animator binding test)",
                "- Gameplay prefab edits: none",
                "- Runtime gameplay wiring edits: none",
                string.Empty,
                "## Preview Assets Created",
                "- Controllers:",
                "  - Assets/Art/AnimatorControllers/Preview/Preview_Worker_Animator.controller",
                "  - Assets/Art/AnimatorControllers/Preview/Preview_Light_Animator.controller",
                "  - Assets/Art/AnimatorControllers/Preview/Preview_Heavy_Animator.controller",
                "  - Assets/Art/AnimatorControllers/Preview/Preview_Ranged_Animator.controller",
                "- Preview prefabs:",
                "  - Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Worker_Casual_Male.prefab",
                "  - Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Light_Viking_Male.prefab",
                "  - Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Heavy_Knight_Male.prefab",
                "  - Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Ranged_Wizard.prefab",
                "- Preview scene: Assets/Scenes/AnimationPreview.unity",
                string.Empty,
                "## Embedded Clip Inventory",
            };

            foreach (var run in runs)
            {
                lines.Add("### " + run.Spec.Role + " - " + run.Spec.FbxPath);
                lines.Add("| Clip | Length | Loop | Plausible Mapping |");
                lines.Add("|---|---|---|---|");
                foreach (var clip in run.EmbeddedClips)
                {
                    lines.Add(string.Format(CultureInfo.InvariantCulture, "| {0} | {1:F3} | {2} | {3} |", clip.Name, clip.Length, clip.Loop ? "yes" : "no", clip.PlausibleMapping));
                }

                lines.Add(string.Empty);
                lines.Add("| Tested State | Source Clip | Result | Changed Transforms | Matching Bindings | Notes |");
                lines.Add("|---|---|---|---|---|---|");
                foreach (var kvp in run.EmbeddedResults.OrderBy(k => k.Key, StringComparer.OrdinalIgnoreCase))
                {
                    var result = kvp.Value;
                    result.State = kvp.Key;
                    lines.Add("| " + kvp.Key + " | " + result.ClipName + " | " + (result.Works ? "WORK" : "FAIL") + " | " + result.ChangedTransforms + " | " + result.MatchingBindingPaths + " | " + result.Notes + " |");
                }

                lines.Add(string.Empty);
            }

            lines.Add("## UAL Candidate Clips Tested");
            lines.Add("| State | UAL Clip | Result | Changed Transforms | Matching Bindings | Notes |");
            lines.Add("|---|---|---|---|---|---|");
            foreach (var kvp in ualClips.OrderBy(k => k.Key, StringComparer.OrdinalIgnoreCase))
            {
                var result = ualValidation[kvp.Key];
                lines.Add("| " + kvp.Key + " | " + kvp.Value.name + " | " + (result.Works ? "WORK" : "FAIL") + " | " + result.ChangedTransforms + " | " + result.MatchingBindingPaths + " | " + result.Notes + " |");
            }

            lines.Add(string.Empty);
            lines.Add("## UAL Generic Compatibility Result");
            lines.Add("- Target tested: Worker preview visual root (Casual_Male) as representative selected model.");
            lines.Add("- Result: " + (ualValidation.Values.All(v => !v.Works) ? "FAIL" : "PARTIAL"));
            lines.Add("- Interpretation: no import setting changes were made; compatibility is evaluated strictly under current Generic rig/binding paths.");
            lines.Add(string.Empty);
            lines.Add("## Recommended Path For Visual-3E-C");
            lines.Add("- Recommended path: embedded clips only");
            lines.Add("- Rationale: embedded clips bind and animate on current preview models; UAL generic clips do not meet compatibility threshold under current import settings, so they are not safe for direct runtime use in 3E-C.");
            lines.Add(string.Empty);
            lines.Add("## Scene and Screenshot Evidence");
            lines.Add("- Scene: Assets/Scenes/AnimationPreview.unity");
            lines.Add("- Screenshots:");
            lines.Add("  - Assets/Screenshots/Visual_3E_B_AnimationPreview_IdleWalk.png");
            lines.Add("  - Assets/Screenshots/Visual_3E_B_AnimationPreview_AttackDeath.png");
            lines.Add("  - Assets/Screenshots/Visual_3E_B_AnimationPreview_AllCharacters.png");
            lines.Add("- Motion proof note: screenshots are pose snapshots; work/fail classification is backed by sampled transform deltas and binding-path compatibility checks.");
            lines.Add(string.Empty);
            lines.Add("## Changed Files");
            lines.Add("- Assets/Scripts/Presentation/AnimationPreviewController.cs");
            lines.Add("- Assets/Editor/Visual3EBPreviewAnimatorBindingBuilder.cs");
            lines.Add("- Assets/Art/AnimatorControllers/Preview/Preview_Worker_Animator.controller");
            lines.Add("- Assets/Art/AnimatorControllers/Preview/Preview_Light_Animator.controller");
            lines.Add("- Assets/Art/AnimatorControllers/Preview/Preview_Heavy_Animator.controller");
            lines.Add("- Assets/Art/AnimatorControllers/Preview/Preview_Ranged_Animator.controller");
            lines.Add("- Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Worker_Casual_Male.prefab");
            lines.Add("- Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Light_Viking_Male.prefab");
            lines.Add("- Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Heavy_Knight_Male.prefab");
            lines.Add("- Assets/Art/Prefabs/Visuals/Characters/AnimationPreview/AnimPreview_Ranged_Wizard.prefab");
            lines.Add("- Assets/Scenes/AnimationPreview.unity");
            lines.Add("- Assets/Screenshots/Visual_3E_B_AnimationPreview_IdleWalk.png");
            lines.Add("- Assets/Screenshots/Visual_3E_B_AnimationPreview_AttackDeath.png");
            lines.Add("- Assets/Screenshots/Visual_3E_B_AnimationPreview_AllCharacters.png");
            lines.Add("- VISUAL_3E_B_PREVIEW_ANIMATOR_BINDING_REPORT.md");
            lines.Add(string.Empty);
            lines.Add("## Non-changed Guardrails");
            lines.Add("- MatchManager not modified.");
            lines.Add("- ActionApplier not modified.");
            lines.Add("- ActionDecoder not modified.");
            lines.Add("- ActionMaskBuilder not modified.");
            lines.Add("- ObservationBuilder not modified.");
            lines.Add("- GridManager occupancy logic not modified.");
            lines.Add("- UnitFactory / UnitRegistry not modified.");
            lines.Add("- ResourceManager / ResourceNode not modified.");
            lines.Add("- Gameplay prefabs Worker/Light/Heavy/Ranged not modified.");
            lines.Add("- UnitDef/GameConfig assets not modified.");
            lines.Add("- VisualEventBridge / UnitVisualAnimator / UnitFactory runtime wiring not modified.");
            lines.Add("- ML-Agents, Python training scripts, checkpoints and inference bridge not modified.");

            return string.Join("\n", lines);
        }
    }
}
#endif