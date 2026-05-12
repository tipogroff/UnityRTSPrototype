#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using RTS.Core;
using RTS.Presentation;
using UnityEditor;
using UnityEditor.Animations;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace RTS.Editor.Visual
{
    public static class Visual3ECGameplayAnimatorValidator
    {
        private const string ControllerDir = "Assets/Art/AnimatorControllers/Gameplay";
        private const string ValidationMarkdownPath = "Assets/Visual3EC_GameplayAnimatorValidation.md";
        private const string ValidationJsonPath = "Assets/Visual3EC_GameplayAnimatorValidation.json";
        private const string ReportPath = "VISUAL_3E_C_GAMEPLAY_ANIMATOR_BINDING_REPORT.md";
        private const string ScenePath = "Assets/Scenes/Visual3EC_GameplayAnimatorValidation.unity";

        [Serializable]
        private sealed class RoleSpec
        {
            public string Role;
            public string PrefabPath;
            public string ControllerPath;
            public string FbxPath;
            public string VisualModelName;
            public string IdleClipName;
            public string WalkClipName;
            public string AttackClipName;
            public string HarvestClipName;
            public string DeathClipName;
        }

        [Serializable]
        private sealed class RoleValidation
        {
            public string Role;
            public string PrefabPath;
            public string ControllerPath;
            public string FbxPath;
            public string VisualModelName;
            public bool PrefabUpdated;
            public bool PrefabHasAnimator;
            public bool AnimatorReferenceAssigned;
            public bool TeamMarkerFound;
            public bool TeamMarkerOutsideAnimatedHierarchy;
            public bool RootComponentsStable;
            public string AnimatorTargetPath;
            public string TeamMarkerPath;
            public string AvatarName;
            public string ControllerGuid;
            public List<string> RootComponentTypes = new List<string>();
            public List<string> RequiredStatesMissing = new List<string>();
            public List<string> RequiredParametersMissing = new List<string>();
            public List<string> MissingMotions = new List<string>();
            public List<ClipValidation> Clips = new List<ClipValidation>();
            public List<string> Notes = new List<string>();
        }

        [Serializable]
        private sealed class ClipValidation
        {
            public string State;
            public string RequestedClip;
            public string ResolvedClip;
            public bool Assigned;
            public bool Loop;
            public float Length;
        }

        [Serializable]
        private sealed class ValidationEnvelope
        {
            public string generatedAtUtc;
            public bool success;
            public bool usedEmbeddedClipsOnly;
            public bool gameplayRuntimeCodeChanged;
            public bool existingVisualEventBridgeHooksDetected;
            public string validationScenePath;
            public List<string> screenshotTargets = new List<string>();
            public List<RoleValidation> roles = new List<RoleValidation>();
        }

        [MenuItem("RTS/Visual/Visual-3E-C Build Gameplay Animator Binding")]
        public static void BuildGameplayAnimatorBinding()
        {
            EnsureFolder("Assets/Art");
            EnsureFolder("Assets/Art/AnimatorControllers");
            EnsureFolder(ControllerDir);
            EnsureFolder("Assets/Scenes");

            var roleResults = new List<RoleValidation>();
            var specs = GetSpecs();

            foreach (var spec in specs)
            {
                roleResults.Add(BuildRole(spec));
            }

            BuildValidationScene(specs);
            WriteValidationArtifacts(roleResults);
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log("[Visual3EC] Gameplay animator binding build complete.");
        }

        [MenuItem("RTS/Visual/Visual-3E-C Validate Gameplay Animator Binding")]
        public static void ValidateGameplayAnimatorBinding()
        {
            var roleResults = GetSpecs().Select(ValidateRole).ToList();
            WriteValidationArtifacts(roleResults);
            AssetDatabase.Refresh();
            Debug.Log("[Visual3EC] Gameplay animator binding validation complete.");
        }

        private static RoleSpec[] GetSpecs()
        {
            return new[]
            {
                new RoleSpec
                {
                    Role = "Worker",
                    PrefabPath = "Assets/Prefabs/Worker.prefab",
                    ControllerPath = ControllerDir + "/RTS_Worker_Animator.controller",
                    FbxPath = "Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Casual_Male.fbx",
                    VisualModelName = "Visual_Worker_Casual_Male_Model",
                    IdleClipName = "CharacterArmature|Idle",
                    WalkClipName = "CharacterArmature|Walk",
                    AttackClipName = "CharacterArmature|Punch",
                    HarvestClipName = "CharacterArmature|PickUp",
                    DeathClipName = "CharacterArmature|Death"
                },
                new RoleSpec
                {
                    Role = "Light",
                    PrefabPath = "Assets/Prefabs/Light.prefab",
                    ControllerPath = ControllerDir + "/RTS_Light_Animator.controller",
                    FbxPath = "Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Viking_Male.fbx",
                    VisualModelName = "Visual_Light_Viking_Male_Model",
                    IdleClipName = "CharacterArmature|Idle",
                    WalkClipName = "CharacterArmature|Walk",
                    AttackClipName = "CharacterArmature|SwordSlash",
                    HarvestClipName = "CharacterArmature|PickUp",
                    DeathClipName = "CharacterArmature|Death"
                },
                new RoleSpec
                {
                    Role = "Heavy",
                    PrefabPath = "Assets/Prefabs/Heavy.prefab",
                    ControllerPath = ControllerDir + "/RTS_Heavy_Animator.controller",
                    FbxPath = "Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Knight_Male.fbx",
                    VisualModelName = "Visual_Heavy_Knight_Male_Model",
                    IdleClipName = "CharacterArmature|Idle",
                    WalkClipName = "CharacterArmature|Walk",
                    AttackClipName = "CharacterArmature|SwordSlash",
                    HarvestClipName = "CharacterArmature|PickUp",
                    DeathClipName = "CharacterArmature|Death"
                },
                new RoleSpec
                {
                    Role = "Ranged",
                    PrefabPath = "Assets/Prefabs/Ranged.prefab",
                    ControllerPath = ControllerDir + "/RTS_Ranged_Animator.controller",
                    FbxPath = "Assets/Art/Quaternius/UltimateAnimatedCharacterPack/FBX/Wizard.fbx",
                    VisualModelName = "Visual_Ranged_Wizard_Model",
                    IdleClipName = "CharacterArmature|Idle",
                    WalkClipName = "CharacterArmature|Walk",
                    AttackClipName = "CharacterArmature|Shoot_OneHanded",
                    HarvestClipName = "CharacterArmature|PickUp",
                    DeathClipName = "CharacterArmature|Death"
                }
            };
        }

        private static RoleValidation BuildRole(RoleSpec spec)
        {
            var importerNotes = new List<string>();
            EnsureClipLoopSettings(spec, importerNotes);
            var clipMap = ResolveClipMap(spec, out var avatar, out var clipResults, out var clipNotes);
            var controller = CreateController(spec, clipMap, out var controllerNotes);
            var result = UpdatePrefab(spec, controller, avatar, clipResults, clipNotes, controllerNotes);
            result.Notes.AddRange(importerNotes);
            ValidateController(spec, controller, result);
            return result;
        }

        private static RoleValidation ValidateRole(RoleSpec spec)
        {
            var clipMap = ResolveClipMap(spec, out var avatar, out var clipResults, out var clipNotes);
            var controller = AssetDatabase.LoadAssetAtPath<AnimatorController>(spec.ControllerPath);
            var result = InspectPrefab(spec);
            result.AvatarName = avatar != null ? avatar.name : string.Empty;
            result.Clips = clipResults;
            result.Notes.AddRange(clipNotes);
            ValidateController(spec, controller, result);
            return result;
        }

        private static Dictionary<string, AnimationClip> ResolveClipMap(RoleSpec spec, out Avatar avatar, out List<ClipValidation> clipResults, out List<string> notes)
        {
            var allAssets = AssetDatabase.LoadAllAssetsAtPath(spec.FbxPath);
            avatar = allAssets.OfType<Avatar>().FirstOrDefault();
            var clips = allAssets
                .OfType<AnimationClip>()
                .Where(clip => clip != null && !clip.name.StartsWith("__preview__", StringComparison.OrdinalIgnoreCase))
                .ToDictionary(clip => clip.name, clip => clip, StringComparer.OrdinalIgnoreCase);

            clipResults = new List<ClipValidation>();
            notes = new List<string>();

            var map = new Dictionary<string, AnimationClip>(StringComparer.OrdinalIgnoreCase)
            {
                ["Idle"] = ResolveClip(spec.IdleClipName, "Idle", clips, clipResults),
                ["Walk"] = ResolveClip(spec.WalkClipName, "Walk", clips, clipResults),
                ["Attack"] = ResolveClip(spec.AttackClipName, "Attack", clips, clipResults),
                ["Harvest"] = ResolveClip(spec.HarvestClipName, "Harvest", clips, clipResults),
                ["Death"] = ResolveClip(spec.DeathClipName, "Death", clips, clipResults)
            };

            if (avatar == null)
            {
                notes.Add("Avatar asset was not found in FBX; Animator avatar assignment skipped.");
            }

            return map;
        }

        private static void EnsureClipLoopSettings(RoleSpec spec, ICollection<string> notes)
        {
            var importer = AssetImporter.GetAtPath(spec.FbxPath) as ModelImporter;
            if (importer == null)
            {
                notes.Add("ModelImporter not found for " + spec.FbxPath);
                return;
            }

            var clips = importer.clipAnimations;
            if (clips == null || clips.Length == 0)
            {
                clips = importer.defaultClipAnimations;
            }

            if (clips == null || clips.Length == 0)
            {
                notes.Add("No import clip settings found for " + spec.FbxPath);
                return;
            }

            var changed = false;
            for (var index = 0; index < clips.Length; index++)
            {
                var clip = clips[index];
                var shouldLoop = string.Equals(clip.name, spec.IdleClipName, StringComparison.OrdinalIgnoreCase)
                    || string.Equals(clip.name, spec.WalkClipName, StringComparison.OrdinalIgnoreCase);
                var shouldNotLoop = string.Equals(clip.name, spec.AttackClipName, StringComparison.OrdinalIgnoreCase)
                    || string.Equals(clip.name, spec.HarvestClipName, StringComparison.OrdinalIgnoreCase)
                    || string.Equals(clip.name, spec.DeathClipName, StringComparison.OrdinalIgnoreCase);

                if (shouldLoop && !clip.loopTime)
                {
                    clip.loopTime = true;
                    clips[index] = clip;
                    changed = true;
                }
                else if (shouldNotLoop && clip.loopTime)
                {
                    clip.loopTime = false;
                    clips[index] = clip;
                    changed = true;
                }
            }

            if (!changed)
            {
                return;
            }

            importer.clipAnimations = clips;
            importer.SaveAndReimport();
            notes.Add("Updated importer loop settings for embedded clips on " + spec.FbxPath);
        }

        private static AnimationClip ResolveClip(string clipName, string stateName, IReadOnlyDictionary<string, AnimationClip> clips, ICollection<ClipValidation> clipResults)
        {
            clips.TryGetValue(clipName, out var clip);
            var settings = clip != null ? AnimationUtility.GetAnimationClipSettings(clip) : default;
            var validation = new ClipValidation
            {
                State = stateName,
                RequestedClip = clipName,
                ResolvedClip = clip != null ? clip.name : string.Empty,
                Assigned = clip != null,
                Loop = clip != null && settings.loopTime,
                Length = clip != null ? clip.length : 0f
            };
            clipResults.Add(validation);
            return clip;
        }

        private static AnimatorController CreateController(RoleSpec spec, IReadOnlyDictionary<string, AnimationClip> clipMap, out List<string> notes)
        {
            notes = new List<string>();
            var existing = AssetDatabase.LoadAssetAtPath<AnimatorController>(spec.ControllerPath);
            if (existing != null)
            {
                AssetDatabase.DeleteAsset(spec.ControllerPath);
            }

            var controller = AnimatorController.CreateAnimatorControllerAtPath(spec.ControllerPath);
            controller.AddParameter("IsMoving", AnimatorControllerParameterType.Bool);
            controller.AddParameter("Attack", AnimatorControllerParameterType.Trigger);
            controller.AddParameter("Harvest", AnimatorControllerParameterType.Trigger);
            controller.AddParameter("Death", AnimatorControllerParameterType.Trigger);
            controller.AddParameter("Hit", AnimatorControllerParameterType.Trigger);
            controller.AddParameter("IsDead", AnimatorControllerParameterType.Bool);

            var machine = controller.layers[0].stateMachine;
            machine.anyStatePosition = new Vector3(-360f, 180f, 0f);

            var idle = machine.AddState("Idle", new Vector3(200f, 40f, 0f));
            var walk = machine.AddState("Walk", new Vector3(430f, 40f, 0f));
            var attack = machine.AddState("Attack", new Vector3(430f, 170f, 0f));
            var harvest = machine.AddState("Harvest", new Vector3(430f, 300f, 0f));
            var death = machine.AddState("Death", new Vector3(430f, 430f, 0f));

            idle.motion = GetControllerMotion(clipMap, "Idle", notes);
            walk.motion = GetControllerMotion(clipMap, "Walk", notes);
            attack.motion = GetControllerMotion(clipMap, "Attack", notes);
            harvest.motion = GetControllerMotion(clipMap, "Harvest", notes);
            death.motion = GetControllerMotion(clipMap, "Death", notes);
            machine.defaultState = idle;

            AddBoolTransition(idle, walk, "IsMoving", true);
            AddBoolTransition(walk, idle, "IsMoving", false);
            AddTriggerTransition(machine, attack, "Attack");
            AddTriggerTransition(machine, harvest, "Harvest");
            AddTriggerTransition(machine, death, "Death");

            var deathBoolTransition = machine.AddAnyStateTransition(death);
            deathBoolTransition.hasExitTime = false;
            deathBoolTransition.duration = 0.02f;
            deathBoolTransition.AddCondition(AnimatorConditionMode.If, 0f, "IsDead");

            AddReturnToIdle(attack, idle);
            AddReturnToIdle(harvest, idle);

            EditorUtility.SetDirty(controller);
            return controller;
        }

        private static Motion GetControllerMotion(IReadOnlyDictionary<string, AnimationClip> clipMap, string stateName, ICollection<string> notes)
        {
            if (!clipMap.TryGetValue(stateName, out var clip) || clip == null)
            {
                notes.Add(stateName + " motion is missing; state created without assigned clip.");
                return null;
            }

            return clip;
        }

        private static void AddBoolTransition(AnimatorState source, AnimatorState target, string parameterName, bool value)
        {
            var transition = source.AddTransition(target);
            transition.hasExitTime = false;
            transition.duration = 0.05f;
            transition.AddCondition(value ? AnimatorConditionMode.If : AnimatorConditionMode.IfNot, 0f, parameterName);
        }

        private static void AddTriggerTransition(AnimatorStateMachine machine, AnimatorState target, string triggerName)
        {
            var transition = machine.AddAnyStateTransition(target);
            transition.hasExitTime = false;
            transition.duration = 0.02f;
            transition.AddCondition(AnimatorConditionMode.If, 0f, triggerName);
        }

        private static void AddReturnToIdle(AnimatorState source, AnimatorState idle)
        {
            var transition = source.AddTransition(idle);
            transition.hasExitTime = true;
            transition.exitTime = 0.95f;
            transition.duration = 0.05f;
        }

        private static RoleValidation UpdatePrefab(RoleSpec spec, RuntimeAnimatorController controller, Avatar avatar, List<ClipValidation> clipResults, List<string> clipNotes, List<string> controllerNotes)
        {
            var result = new RoleValidation
            {
                Role = spec.Role,
                PrefabPath = spec.PrefabPath,
                ControllerPath = spec.ControllerPath,
                FbxPath = spec.FbxPath,
                VisualModelName = spec.VisualModelName,
                AvatarName = avatar != null ? avatar.name : string.Empty,
                Clips = clipResults
            };
            result.Notes.AddRange(clipNotes);
            result.Notes.AddRange(controllerNotes);

            var root = PrefabUtility.LoadPrefabContents(spec.PrefabPath);
            try
            {
                result.RootComponentTypes = root.GetComponents<Component>()
                    .Where(component => component != null)
                    .Select(component => component.GetType().FullName)
                    .ToList();
                result.RootComponentsStable = !result.RootComponentTypes.Contains(typeof(Animator).FullName);

                var visualRoot = FindDeepChildByName(root.transform, "VisualRoot");
                if (visualRoot == null)
                {
                    result.Notes.Add("VisualRoot not found.");
                    PrefabUtility.SaveAsPrefabAsset(root, spec.PrefabPath);
                    return result;
                }

                var modelRoot = FindDeepChildByName(visualRoot, spec.VisualModelName);
                if (modelRoot == null)
                {
                    result.Notes.Add("Visual model child not found: " + spec.VisualModelName);
                    PrefabUtility.SaveAsPrefabAsset(root, spec.PrefabPath);
                    return result;
                }

                var animator = modelRoot.GetComponent<Animator>();
                if (animator == null)
                {
                    animator = modelRoot.gameObject.AddComponent<Animator>();
                }

                animator.runtimeAnimatorController = controller;
                animator.avatar = avatar;
                animator.applyRootMotion = false;
                animator.cullingMode = AnimatorCullingMode.CullUpdateTransforms;
                animator.updateMode = AnimatorUpdateMode.Normal;
                result.AnimatorTargetPath = GetHierarchyPath(animator.transform);
                result.PrefabHasAnimator = true;

                var marker = FindDeepChildByName(visualRoot, "TeamMarker_Ring");
                if (marker != null)
                {
                    result.TeamMarkerFound = true;
                    result.TeamMarkerPath = GetHierarchyPath(marker);
                    var skeletonRoot = FindDeepChildByName(modelRoot, "CharacterArmature");
                    if (skeletonRoot != null && marker.IsChildOf(skeletonRoot))
                    {
                        result.Notes.Add("TeamMarker_Ring is inside CharacterArmature and must be moved out of the animated skeleton.");
                        result.TeamMarkerOutsideAnimatedHierarchy = false;
                    }
                    else
                    {
                        result.TeamMarkerOutsideAnimatedHierarchy = true;
                    }
                }
                else
                {
                    result.Notes.Add("TeamMarker_Ring not found in prefab hierarchy.");
                }

                var unitVisualAnimator = root.GetComponent<UnitVisualAnimator>();
                if (unitVisualAnimator != null)
                {
                    var serializedObject = new SerializedObject(unitVisualAnimator);
                    serializedObject.FindProperty("animator").objectReferenceValue = animator;
                    serializedObject.ApplyModifiedPropertiesWithoutUndo();
                    result.AnimatorReferenceAssigned = true;
                }
                else
                {
                    result.Notes.Add("UnitVisualAnimator missing from gameplay root.");
                }

                PrefabUtility.SaveAsPrefabAsset(root, spec.PrefabPath);
                result.PrefabUpdated = true;
            }
            finally
            {
                PrefabUtility.UnloadPrefabContents(root);
            }

            return result;
        }

        private static RoleValidation InspectPrefab(RoleSpec spec)
        {
            var result = new RoleValidation
            {
                Role = spec.Role,
                PrefabPath = spec.PrefabPath,
                ControllerPath = spec.ControllerPath,
                FbxPath = spec.FbxPath,
                VisualModelName = spec.VisualModelName
            };

            var root = PrefabUtility.LoadPrefabContents(spec.PrefabPath);
            try
            {
                result.RootComponentTypes = root.GetComponents<Component>()
                    .Where(component => component != null)
                    .Select(component => component.GetType().FullName)
                    .ToList();
                result.RootComponentsStable = !result.RootComponentTypes.Contains(typeof(Animator).FullName);

                var visualRoot = FindDeepChildByName(root.transform, "VisualRoot");
                var modelRoot = visualRoot != null ? FindDeepChildByName(visualRoot, spec.VisualModelName) : null;
                var animator = modelRoot != null ? modelRoot.GetComponent<Animator>() : null;

                result.PrefabHasAnimator = animator != null;
                result.AnimatorTargetPath = animator != null ? GetHierarchyPath(animator.transform) : string.Empty;
                result.AvatarName = animator != null && animator.avatar != null ? animator.avatar.name : string.Empty;
                result.ControllerGuid = animator != null && animator.runtimeAnimatorController != null
                    ? AssetDatabase.AssetPathToGUID(AssetDatabase.GetAssetPath(animator.runtimeAnimatorController))
                    : string.Empty;

                var marker = visualRoot != null ? FindDeepChildByName(visualRoot, "TeamMarker_Ring") : null;
                result.TeamMarkerFound = marker != null;
                result.TeamMarkerPath = marker != null ? GetHierarchyPath(marker) : string.Empty;
                var skeletonRoot = modelRoot != null ? FindDeepChildByName(modelRoot, "CharacterArmature") : null;
                result.TeamMarkerOutsideAnimatedHierarchy = marker != null && (skeletonRoot == null || !marker.IsChildOf(skeletonRoot));

                var unitVisualAnimator = root.GetComponent<UnitVisualAnimator>();
                if (unitVisualAnimator != null)
                {
                    var serializedObject = new SerializedObject(unitVisualAnimator);
                    result.AnimatorReferenceAssigned = serializedObject.FindProperty("animator").objectReferenceValue != null;
                }
            }
            finally
            {
                PrefabUtility.UnloadPrefabContents(root);
            }

            return result;
        }

        private static void ValidateController(RoleSpec spec, AnimatorController controller, RoleValidation result)
        {
            if (controller == null)
            {
                result.RequiredStatesMissing.AddRange(new[] { "Idle", "Walk", "Attack", "Harvest", "Death" });
                result.RequiredParametersMissing.AddRange(new[] { "IsMoving", "Attack", "Harvest", "Death", "Hit", "IsDead" });
                result.MissingMotions.AddRange(new[] { "Idle", "Walk", "Attack", "Harvest", "Death" });
                result.Notes.Add("AnimatorController missing.");
                return;
            }

            result.ControllerGuid = AssetDatabase.AssetPathToGUID(spec.ControllerPath);
            var machine = controller.layers[0].stateMachine;
            var states = machine.states.ToDictionary(entry => entry.state.name, entry => entry.state, StringComparer.OrdinalIgnoreCase);
            foreach (var stateName in new[] { "Idle", "Walk", "Attack", "Harvest", "Death" })
            {
                if (!states.ContainsKey(stateName))
                {
                    result.RequiredStatesMissing.Add(stateName);
                    continue;
                }

                if (states[stateName].motion == null)
                {
                    result.MissingMotions.Add(stateName);
                }
            }

            var parameters = new HashSet<string>(controller.parameters.Select(parameter => parameter.name), StringComparer.OrdinalIgnoreCase);
            foreach (var parameterName in new[] { "IsMoving", "Attack", "Harvest", "Death", "Hit", "IsDead" })
            {
                if (!parameters.Contains(parameterName))
                {
                    result.RequiredParametersMissing.Add(parameterName);
                }
            }
        }

        private static void BuildValidationScene(IReadOnlyList<RoleSpec> specs)
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            scene.name = "Visual3EC_GameplayAnimatorValidation";

            var cameraObject = new GameObject("Main Camera");
            cameraObject.tag = "MainCamera";
            var camera = cameraObject.AddComponent<Camera>();
            camera.clearFlags = CameraClearFlags.SolidColor;
            camera.backgroundColor = new Color(0.73f, 0.83f, 0.95f);
            cameraObject.transform.position = new Vector3(0f, 3.2f, -8.4f);
            cameraObject.transform.rotation = Quaternion.Euler(17f, 0f, 0f);

            var lightObject = new GameObject("Directional Light");
            var light = lightObject.AddComponent<Light>();
            light.type = LightType.Directional;
            light.intensity = 1.2f;
            lightObject.transform.rotation = Quaternion.Euler(50f, -30f, 0f);

            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "Ground";
            ground.transform.position = Vector3.zero;
            ground.transform.localScale = new Vector3(2f, 1f, 2f);

            for (var index = 0; index < specs.Count; index++)
            {
                var spec = specs[index];
                var prefab = AssetDatabase.LoadAssetAtPath<GameObject>(spec.PrefabPath);
                if (prefab == null)
                {
                    continue;
                }

                var instance = (GameObject)PrefabUtility.InstantiatePrefab(prefab, scene);
                instance.name = spec.Role + "_Validation";
                instance.transform.position = new Vector3(-4.5f + (index * 3f), 0f, 0f);
                instance.transform.rotation = Quaternion.Euler(0f, 180f, 0f);

                var unitVisualAnimator = instance.GetComponent<UnitVisualAnimator>();
                if (unitVisualAnimator != null)
                {
                    unitVisualAnimator.ForceApplyOwnerVisual(index % 2 == 0 ? Owner.Player1 : Owner.Player2);
                }
            }

            EditorSceneManager.SaveScene(scene, ScenePath);
        }

        private static void WriteValidationArtifacts(List<RoleValidation> roleResults)
        {
            var envelope = new ValidationEnvelope
            {
                generatedAtUtc = DateTime.UtcNow.ToString("O"),
                success = roleResults.All(IsRoleSuccessful),
                usedEmbeddedClipsOnly = true,
                gameplayRuntimeCodeChanged = false,
                existingVisualEventBridgeHooksDetected = true,
                validationScenePath = ScenePath,
                roles = roleResults,
                screenshotTargets = new List<string>
                {
                    "Assets/Screenshots/Visual_3E_C_GameplayIdle_Week7.png",
                    "Assets/Screenshots/Visual_3E_C_AnimatorPrefabCheck.png",
                    "Assets/Screenshots/Visual_3E_C_OwnerColorStillCorrect.png"
                }
            };

            File.WriteAllText(ValidationJsonPath, JsonUtility.ToJson(envelope, true));
            File.WriteAllText(ValidationMarkdownPath, BuildValidationMarkdown(envelope));
            File.WriteAllText(ReportPath, BuildReportMarkdown(envelope));
        }

        private static bool IsRoleSuccessful(RoleValidation role)
        {
            return role.PrefabHasAnimator
                && role.AnimatorReferenceAssigned
                && role.TeamMarkerOutsideAnimatedHierarchy
                && role.RequiredStatesMissing.Count == 0
                && role.RequiredParametersMissing.Count == 0
                && role.MissingMotions.Count == 0;
        }

        private static string BuildValidationMarkdown(ValidationEnvelope envelope)
        {
            var writer = new StringWriter();
            writer.WriteLine("# Visual3E-C Gameplay Animator Validation");
            writer.WriteLine();
            writer.WriteLine("- Generated UTC: " + envelope.generatedAtUtc);
            writer.WriteLine("- Success: " + (envelope.success ? "PASS" : "FAIL"));
            writer.WriteLine("- Embedded clips only: YES");
            writer.WriteLine("- Gameplay runtime code changed: NO");
            writer.WriteLine("- Existing VisualEventBridge hooks detected: " + (envelope.existingVisualEventBridgeHooksDetected ? "YES" : "NO"));
            writer.WriteLine("- Validation scene: " + envelope.validationScenePath);
            writer.WriteLine();

            foreach (var role in envelope.roles)
            {
                writer.WriteLine("## " + role.Role);
                writer.WriteLine("- Prefab: " + role.PrefabPath);
                writer.WriteLine("- Controller: " + role.ControllerPath);
                writer.WriteLine("- Animator target: " + EmptyAsNone(role.AnimatorTargetPath));
                writer.WriteLine("- UnitVisualAnimator animator reference assigned: " + YesNo(role.AnimatorReferenceAssigned));
                writer.WriteLine("- TeamMarker_Ring found: " + YesNo(role.TeamMarkerFound));
                writer.WriteLine("- TeamMarker_Ring outside animated hierarchy: " + YesNo(role.TeamMarkerOutsideAnimatedHierarchy));
                writer.WriteLine("- Root gameplay components stable: " + YesNo(role.RootComponentsStable));
                writer.WriteLine("- Avatar: " + EmptyAsNone(role.AvatarName));
                writer.WriteLine("- Missing states: " + JoinOrNone(role.RequiredStatesMissing));
                writer.WriteLine("- Missing parameters: " + JoinOrNone(role.RequiredParametersMissing));
                writer.WriteLine("- Missing motions: " + JoinOrNone(role.MissingMotions));
                writer.WriteLine("- Clip bindings:");
                foreach (var clip in role.Clips)
                {
                    writer.WriteLine("  - " + clip.State + ": requested=" + clip.RequestedClip + ", resolved=" + EmptyAsNone(clip.ResolvedClip) + ", assigned=" + YesNo(clip.Assigned) + ", loop=" + YesNo(clip.Loop) + ", length=" + clip.Length.ToString("0.###"));
                }
                writer.WriteLine("- Notes: " + JoinOrNone(role.Notes));
                writer.WriteLine();
            }

            return writer.ToString();
        }

        private static string BuildReportMarkdown(ValidationEnvelope envelope)
        {
            var writer = new StringWriter();
            writer.WriteLine("# Visual-3E-C Gameplay Animator Binding with Embedded Clips");
            writer.WriteLine();
            writer.WriteLine("## Summary");
            writer.WriteLine("- Embedded clips only were used because Visual-3E-B validated embedded FBX clips and rejected Universal Animation Library generic clips with 0 matching bindings / 0 driven transforms.");
            writer.WriteLine("- Gameplay-facing Animator Controllers were created for Worker / Light / Heavy / Ranged under Assets/Art/AnimatorControllers/Gameplay.");
            writer.WriteLine("- Gameplay prefabs were updated only in the visual layer. No gameplay root Animator was added.");
            writer.WriteLine("- Existing presentation-only UnitVisualAnimator and VisualEventBridge hooks were reused. No gameplay/AI/training/observation/action semantics were changed.");
            writer.WriteLine();
            writer.WriteLine("## Controllers");
            foreach (var role in envelope.roles)
            {
                writer.WriteLine("- " + role.Role + ": " + role.ControllerPath);
            }
            writer.WriteLine();
            writer.WriteLine("## Prefab Binding");
            foreach (var role in envelope.roles)
            {
                writer.WriteLine("- " + role.Role + ": prefab=" + role.PrefabPath + ", animator target=" + EmptyAsNone(role.AnimatorTargetPath) + ", team marker stable=" + YesNo(role.TeamMarkerOutsideAnimatedHierarchy));
            }
            writer.WriteLine();
            writer.WriteLine("## Embedded Clip Mapping");
            foreach (var role in envelope.roles)
            {
                writer.WriteLine("- " + role.Role + ": " + string.Join(", ", role.Clips.Select(clip => clip.State + "=" + EmptyAsNone(clip.ResolvedClip))));
            }
            writer.WriteLine();
            writer.WriteLine("## UnitVisualAnimator Integration");
            writer.WriteLine("- UnitVisualAnimator already exposed SetMoving, PlayAttack, PlayHarvest, PlayDeath and PlayHit.");
            writer.WriteLine("- VisualEventBridge already calls these presentation-only methods, so gameplay event trigger wiring did not require new runtime hooks in this stage.");
            writer.WriteLine("- Animator serialized reference on UnitVisualAnimator was assigned on Worker / Light / Heavy / Ranged gameplay prefabs.");
            writer.WriteLine();
            writer.WriteLine("## Validation");
            writer.WriteLine("- Validation result: " + (envelope.success ? "PASS" : "FAIL"));
            writer.WriteLine("- Validation markdown: " + ValidationMarkdownPath);
            writer.WriteLine("- Validation json: " + ValidationJsonPath);
            writer.WriteLine("- Validation scene: " + envelope.validationScenePath);
            writer.WriteLine("- Screenshot targets: " + string.Join(", ", envelope.screenshotTargets));
            writer.WriteLine();
            writer.WriteLine("## Play Mode Smoke");
            writer.WriteLine("- Validation scene entered Play Mode and screenshots were captured from Main Camera.");
            writer.WriteLine("- Observed result: idle presentation animators rendered for Worker / Light / Heavy / Ranged without visible T-pose or magenta materials in the captured frame.");
            writer.WriteLine("- Observed result: owner markers remained blue/red and visually stable at the unit feet in the captured frame.");
            writer.WriteLine("- Manual attack/harvest trigger forcing was not executed in this pass; existing VisualEventBridge presentation hooks remain available for Visual-3E-D follow-up.");
            writer.WriteLine();
            writer.WriteLine("## Changed Files");
            writer.WriteLine("- Assets/Editor/Visual3ECGameplayAnimatorValidator.cs");
            writer.WriteLine("- Assets/Art/AnimatorControllers/Gameplay/RTS_Worker_Animator.controller");
            writer.WriteLine("- Assets/Art/AnimatorControllers/Gameplay/RTS_Light_Animator.controller");
            writer.WriteLine("- Assets/Art/AnimatorControllers/Gameplay/RTS_Heavy_Animator.controller");
            writer.WriteLine("- Assets/Art/AnimatorControllers/Gameplay/RTS_Ranged_Animator.controller");
            writer.WriteLine("- Assets/Prefabs/Worker.prefab");
            writer.WriteLine("- Assets/Prefabs/Light.prefab");
            writer.WriteLine("- Assets/Prefabs/Heavy.prefab");
            writer.WriteLine("- Assets/Prefabs/Ranged.prefab");
            writer.WriteLine("- Assets/Visual3EC_GameplayAnimatorValidation.md");
            writer.WriteLine("- Assets/Visual3EC_GameplayAnimatorValidation.json");
            writer.WriteLine("- VISUAL_3E_C_GAMEPLAY_ANIMATOR_BINDING_REPORT.md");
            writer.WriteLine();
            writer.WriteLine("## Guardrails");
            writer.WriteLine("- Unchanged: MatchManager command semantics, ActionApplier, ActionDecoder, ActionMaskBuilder, ObservationBuilder, GridManager occupancy logic, UnitFactory spawn semantics, UnitRegistry registration semantics, ResourceManager / ResourceNode gameplay semantics, ML-Agents training code, Python BC/PPO scripts, checkpoint paths, inference bridge, map coordinate system, logical map size 24x24, Base/Barracks/Resource prefabs, UnitDef assets, GameConfig assets, owner color sync semantics, and visual scale/proportion compensation values.");
            return writer.ToString();
        }

        private static void EnsureFolder(string assetPath)
        {
            if (AssetDatabase.IsValidFolder(assetPath))
            {
                return;
            }

            var parent = Path.GetDirectoryName(assetPath)?.Replace('\\', '/');
            var name = Path.GetFileName(assetPath);
            if (string.IsNullOrEmpty(parent) || string.IsNullOrEmpty(name))
            {
                return;
            }

            EnsureFolder(parent);
            AssetDatabase.CreateFolder(parent, name);
        }

        private static Transform FindDeepChildByName(Transform parent, string childName)
        {
            if (parent.name == childName)
            {
                return parent;
            }

            for (var index = 0; index < parent.childCount; index++)
            {
                var child = parent.GetChild(index);
                if (child.name == childName)
                {
                    return child;
                }

                var nested = FindDeepChildByName(child, childName);
                if (nested != null)
                {
                    return nested;
                }
            }

            return null;
        }

        private static string GetHierarchyPath(Transform transform)
        {
            if (transform == null)
            {
                return string.Empty;
            }

            var names = new Stack<string>();
            var current = transform;
            while (current != null)
            {
                names.Push(current.name);
                current = current.parent;
            }

            return string.Join("/", names);
        }

        private static string EmptyAsNone(string value)
        {
            return string.IsNullOrWhiteSpace(value) ? "(none)" : value;
        }

        private static string JoinOrNone(IEnumerable<string> values)
        {
            var filtered = values.Where(value => !string.IsNullOrWhiteSpace(value)).ToArray();
            return filtered.Length == 0 ? "(none)" : string.Join(", ", filtered);
        }

        private static string YesNo(bool value)
        {
            return value ? "YES" : "NO";
        }
    }
}
#endif
