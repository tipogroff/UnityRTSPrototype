#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using RTS.Core;
using UnityEditor;
using UnityEditor.Animations;
using UnityEngine;

namespace RTS.Presentation.Editor
{
    public static class VisualLayerAssetBuilder
    {
        private const string AnimatorControllerPath = "Assets/Art/AnimatorControllers/RTS_Unit_Template.controller";

        [MenuItem("RTS/Presentation/Rebuild Visual Layer Assets")]
        public static void RebuildAll()
        {
            EnsureFolder("Assets/Art");
            EnsureFolder("Assets/Art/AnimatorControllers");
            EnsureFolder("Assets/Art/Prefabs");
            EnsureFolder("Assets/Art/Prefabs/VFX");

            BuildAnimatorTemplate();
            BuildVfxPrefabs();
            AssetDatabase.SaveAssets();
            AssetDatabase.Refresh();
            Debug.Log("[VisualLayerAssetBuilder] Visual layer assets rebuilt.");
        }

        [MenuItem("RTS/Presentation/Rebuild Animator Template")]
        public static void BuildAnimatorTemplate()
        {
            var controller = AnimatorController.CreateAnimatorControllerAtPath(AnimatorControllerPath);
            var stateMachine = controller.layers[0].stateMachine;

            controller.AddParameter("IsMoving", AnimatorControllerParameterType.Bool);
            controller.AddParameter("IsCarrying", AnimatorControllerParameterType.Bool);
            controller.AddParameter("Attack", AnimatorControllerParameterType.Trigger);
            controller.AddParameter("Harvest", AnimatorControllerParameterType.Trigger);
            controller.AddParameter("Death", AnimatorControllerParameterType.Trigger);
            controller.AddParameter("Spawn", AnimatorControllerParameterType.Trigger);
            controller.AddParameter("Hit", AnimatorControllerParameterType.Trigger);

            var idle = stateMachine.AddState("Idle");
            var walk = stateMachine.AddState("Walk");
            var attack = stateMachine.AddState("Attack");
            var harvest = stateMachine.AddState("Harvest");
            var death = stateMachine.AddState("Death");

            stateMachine.defaultState = idle;

            AssignCandidateClip(idle, new[] { "idle", "stand" });
            AssignCandidateClip(walk, new[] { "walk", "run" });
            AssignCandidateClip(attack, new[] { "attack", "melee", "shoot" });
            AssignCandidateClip(harvest, new[] { "harvest", "gather", "collect" });
            AssignCandidateClip(death, new[] { "death", "die" });

            var idleToWalk = idle.AddTransition(walk);
            idleToWalk.hasExitTime = false;
            idleToWalk.duration = 0.08f;
            idleToWalk.AddCondition(AnimatorConditionMode.If, 0f, "IsMoving");

            var walkToIdle = walk.AddTransition(idle);
            walkToIdle.hasExitTime = false;
            walkToIdle.duration = 0.08f;
            walkToIdle.AddCondition(AnimatorConditionMode.IfNot, 0f, "IsMoving");

            AddAnyStateTrigger(stateMachine, attack, "Attack");
            AddAnyStateTrigger(stateMachine, harvest, "Harvest");
            AddAnyStateTrigger(stateMachine, death, "Death");

            EditorUtility.SetDirty(controller);
            Debug.Log($"[VisualLayerAssetBuilder] Animator template generated at {AnimatorControllerPath}");
        }

        [MenuItem("RTS/Presentation/Rebuild VFX Placeholders")]
        public static void BuildVfxPrefabs()
        {
            CreateVfxPrefab("Assets/Art/Prefabs/VFX/VFX_AttackHit.prefab", new Color(1.0f, 0.45f, 0.15f, 1f), 0.45f, 0.15f, 18f, false);
            CreateVfxPrefab("Assets/Art/Prefabs/VFX/VFX_Harvest.prefab", new Color(0.28f, 0.9f, 0.3f, 1f), 0.6f, 0.2f, 16f, true);
            CreateVfxPrefab("Assets/Art/Prefabs/VFX/VFX_Spawn.prefab", new Color(0.35f, 0.55f, 1f, 1f), 0.7f, 0.25f, 20f, true);
            CreateVfxPrefab("Assets/Art/Prefabs/VFX/VFX_Death.prefab", new Color(0.75f, 0.75f, 0.75f, 1f), 0.85f, 0.3f, 24f, false);
        }

        private static void AddAnyStateTrigger(AnimatorStateMachine stateMachine, AnimatorState targetState, string trigger)
        {
            var transition = stateMachine.AddAnyStateTransition(targetState);
            transition.hasExitTime = false;
            transition.duration = 0.04f;
            transition.AddCondition(AnimatorConditionMode.If, 0f, trigger);
        }

        private static void AssignCandidateClip(AnimatorState state, IReadOnlyList<string> keywords)
        {
            foreach (var keyword in keywords)
            {
                var guids = AssetDatabase.FindAssets($"t:AnimationClip {keyword}");
                foreach (var guid in guids)
                {
                    var path = AssetDatabase.GUIDToAssetPath(guid);
                    var clip = AssetDatabase.LoadAssetAtPath<AnimationClip>(path);
                    if (clip == null)
                    {
                        continue;
                    }

                    var lowerName = clip.name.ToLowerInvariant();
                    if (!ContainsAny(lowerName, keywords))
                    {
                        continue;
                    }

                    state.motion = clip;
                    return;
                }
            }
        }

        private static bool ContainsAny(string value, IReadOnlyList<string> keywords)
        {
            for (var i = 0; i < keywords.Count; i++)
            {
                if (value.Contains(keywords[i], StringComparison.OrdinalIgnoreCase))
                {
                    return true;
                }
            }

            return false;
        }

        private static void CreateVfxPrefab(string assetPath, Color color, float duration, float startSize, float startSpeed, bool looping)
        {
            var go = new GameObject(System.IO.Path.GetFileNameWithoutExtension(assetPath));
            var ps = go.AddComponent<ParticleSystem>();

            var main = ps.main;
            main.duration = duration;
            main.loop = looping;
            main.startLifetime = looping ? 0.35f : 0.3f;
            main.startSpeed = startSpeed;
            main.startSize = startSize;
            main.startColor = color;
            main.playOnAwake = true;
            main.simulationSpace = ParticleSystemSimulationSpace.Local;
            main.maxParticles = 48;

            var emission = ps.emission;
            emission.enabled = true;
            emission.rateOverTime = looping ? 16f : 0f;
            emission.SetBursts(new[] { new ParticleSystem.Burst(0f, (short)(looping ? 6 : 14)) });

            var shape = ps.shape;
            shape.enabled = true;
            shape.shapeType = ParticleSystemShapeType.Cone;
            shape.angle = 25f;
            shape.radius = 0.08f;

            var col = ps.collision;
            col.enabled = false;

            var renderer = ps.GetComponent<ParticleSystemRenderer>();
            renderer.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            renderer.receiveShadows = false;

            EnsureFolder("Assets/Art");
            EnsureFolder("Assets/Art/Prefabs");
            EnsureFolder("Assets/Art/Prefabs/VFX");

            var existing = AssetDatabase.LoadAssetAtPath<GameObject>(assetPath);
            if (existing != null)
            {
                PrefabUtility.SaveAsPrefabAssetAndConnect(go, assetPath, InteractionMode.AutomatedAction);
                PrefabUtility.UnpackPrefabInstance(go, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            }
            else
            {
                PrefabUtility.SaveAsPrefabAsset(go, assetPath);
            }

            UnityEngine.Object.DestroyImmediate(go);
        }

        private static void EnsureFolder(string path)
        {
            if (AssetDatabase.IsValidFolder(path))
            {
                return;
            }

            var normalized = path.Replace('\\', '/');
            var segments = normalized.Split('/');
            var current = segments[0];
            for (var i = 1; i < segments.Length; i++)
            {
                var next = current + "/" + segments[i];
                if (!AssetDatabase.IsValidFolder(next))
                {
                    AssetDatabase.CreateFolder(current, segments[i]);
                }

                current = next;
            }
        }
    }
}
#endif
