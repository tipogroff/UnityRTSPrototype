using System;
using RTS.Core;
using UnityEngine;

namespace RTS.Presentation
{
    /// <summary>
    /// Visual-only adapter for animator, optional VFX and owner tinting.
    /// Does not mutate gameplay state.
    /// </summary>
    public sealed class UnitVisualAnimator : MonoBehaviour
    {
        private static readonly int IsMovingHash = Animator.StringToHash("IsMoving");
        private static readonly int IsCarryingHash = Animator.StringToHash("IsCarrying");
        private static readonly int AttackHash = Animator.StringToHash("Attack");
        private static readonly int HarvestHash = Animator.StringToHash("Harvest");
        private static readonly int DeathHash = Animator.StringToHash("Death");
        private static readonly int SpawnHash = Animator.StringToHash("Spawn");
        private static readonly int HitHash = Animator.StringToHash("Hit");

        [Header("Animator")]
        [SerializeField] private Animator animator;

        [Header("Owner Visuals")]
        [SerializeField] private Renderer[] materialRenderers;
        [SerializeField] private Material player1Material;
        [SerializeField] private Material player2Material;
        [SerializeField] private Material neutralMaterial;

        [Header("Optional VFX")]
        [SerializeField] private GameObject attackHitVfxPrefab;
        [SerializeField] private GameObject harvestVfxPrefab;
        [SerializeField] private GameObject spawnVfxPrefab;
        [SerializeField] private GameObject deathVfxPrefab;
        [SerializeField] private float defaultVfxLifetimeSeconds = 2.0f;

        private bool _warnedAnimatorMissing;
        private bool _warnedRendererListMissing;
        private bool _warnedDuplicateMarker;
        private bool _warnedInactiveAuthoritativeMarker;

        private void Awake()
        {
            if (animator == null)
            {
                animator = GetComponentInChildren<Animator>(true);
            }

            TryResolveAuthoritativeTeamMarkerRenderer(out _);
        }

        /// <summary>Depth-first search for a child transform by name.</summary>
        private static Transform FindChildByName(Transform parent, string childName)
        {
            for (int i = 0; i < parent.childCount; i++)
            {
                var child = parent.GetChild(i);
                if (child.name == childName)
                {
                    return child;
                }
                var found = FindChildByName(child, childName);
                if (found != null)
                {
                    return found;
                }
            }
            return null;
        }

        public void SetMoving(bool value)
        {
            if (!TryGetAnimator(out var a))
            {
                return;
            }

            a.SetBool(IsMovingHash, value);
        }

        public void SetCarrying(bool value)
        {
            if (!TryGetAnimator(out var a))
            {
                return;
            }

            a.SetBool(IsCarryingHash, value);
        }

        public void PlayAttack()
        {
            Trigger(AttackHash);
            SpawnOptionalVfx(attackHitVfxPrefab);
        }

        public void PlayHarvest()
        {
            Trigger(HarvestHash);
            SpawnOptionalVfx(harvestVfxPrefab);
        }

        public void PlayDeath()
        {
            Trigger(DeathHash);
            SpawnOptionalVfx(deathVfxPrefab);
        }

        public void PlaySpawn()
        {
            Trigger(SpawnHash);
            SpawnOptionalVfx(spawnVfxPrefab);
        }

        public void PlayHit()
        {
            Trigger(HitHash);
            SpawnOptionalVfx(attackHitVfxPrefab);
        }

        public void SetOwnerVisual(Owner owner)
        {
            if (!TryResolveAuthoritativeTeamMarkerRenderer(out _))
            {
                WarnOnce(ref _warnedRendererListMissing, "Renderer list is empty. Owner visual update skipped.");
                return;
            }

            var targetMaterial = GetOwnerMaterial(owner);
            if (targetMaterial == null)
            {
                return;
            }

            for (var i = 0; i < materialRenderers.Length; i++)
            {
                var rendererRef = materialRenderers[i];
                if (rendererRef == null)
                {
                    continue;
                }

                rendererRef.sharedMaterial = targetMaterial;
            }
        }

        public void SetVisible(bool value)
        {
            if (!TryResolveAuthoritativeTeamMarkerRenderer(out _))
            {
                WarnOnce(ref _warnedRendererListMissing, "Renderer list is empty. Visibility update skipped.");
                return;
            }

            for (var i = 0; i < materialRenderers.Length; i++)
            {
                var rendererRef = materialRenderers[i];
                if (rendererRef == null)
                {
                    continue;
                }

                rendererRef.enabled = value;
            }
        }

        public int GetMaterialRendererCount()
        {
            return materialRenderers != null ? materialRenderers.Length : 0;
        }

        public string[] GetMaterialRendererDebugPaths()
        {
            if (materialRenderers == null || materialRenderers.Length == 0)
            {
                return Array.Empty<string>();
            }

            var paths = new string[materialRenderers.Length];
            for (var i = 0; i < materialRenderers.Length; i++)
            {
                var rendererRef = materialRenderers[i];
                paths[i] = rendererRef == null ? "(null)" : GetHierarchyPath(rendererRef.transform);
            }

            return paths;
        }

        public string GetCurrentOwnerMaterialName()
        {
            if (materialRenderers == null || materialRenderers.Length == 0)
            {
                return string.Empty;
            }

            for (var i = 0; i < materialRenderers.Length; i++)
            {
                var rendererRef = materialRenderers[i];
                if (rendererRef == null)
                {
                    continue;
                }

                var sharedMaterial = rendererRef.sharedMaterial;
                return sharedMaterial != null ? sharedMaterial.name : string.Empty;
            }

            return string.Empty;
        }

        public bool HasPlayer1Material()
        {
            return player1Material != null;
        }

        public bool HasPlayer2Material()
        {
            return player2Material != null;
        }

        public bool HasNeutralMaterial()
        {
            return neutralMaterial != null;
        }

        public bool ForceDiscoverTeamMarkerRenderer()
        {
            return TryResolveAuthoritativeTeamMarkerRenderer(out _);
        }

        public bool ForceApplyOwnerVisual(Owner owner)
        {
            if (!TryResolveAuthoritativeTeamMarkerRenderer(out _))
            {
                return false;
            }

            SetOwnerVisual(owner);
            var expectedMaterial = GetOwnerMaterial(owner);
            return AreOwnerRenderersUsingMaterial(expectedMaterial);
        }

        public bool ApplyOwnerVisualAndVerify(Owner owner, out string diagnostic)
        {
            diagnostic = string.Empty;

            if (!TryResolveAuthoritativeTeamMarkerRenderer(out _))
            {
                diagnostic = "Authoritative TeamMarker_Ring renderer not found.";
                return false;
            }

            var targetMaterial = GetOwnerMaterial(owner);
            if (targetMaterial == null)
            {
                diagnostic = $"Owner material for {owner} is not assigned.";
                return false;
            }

            SetOwnerVisual(owner);
            if (IsMarkerMaterialCorrectForOwner(owner))
            {
                return true;
            }

            diagnostic = $"Marker material mismatch after apply. actual={GetCurrentOwnerMaterialName()}, expected={targetMaterial.name}";
            return false;
        }

        public bool IsMarkerMaterialCorrectForOwner(Owner owner)
        {
            if (!TryResolveAuthoritativeTeamMarkerRenderer(out _))
            {
                return false;
            }

            var expectedMaterial = GetOwnerMaterial(owner);
            return AreOwnerRenderersUsingMaterial(expectedMaterial);
        }

        private void Trigger(int triggerHash)
        {
            if (!TryGetAnimator(out var a))
            {
                return;
            }

            a.SetTrigger(triggerHash);
        }

        private Material GetOwnerMaterial(Owner owner)
        {
            return owner switch
            {
                Owner.Player1 => player1Material,
                Owner.Player2 => player2Material,
                _ => neutralMaterial
            };
        }

        private bool AreOwnerRenderersUsingMaterial(Material targetMaterial)
        {
            if (targetMaterial == null || materialRenderers == null || materialRenderers.Length == 0)
            {
                return false;
            }

            var sawRenderer = false;
            for (var i = 0; i < materialRenderers.Length; i++)
            {
                var rendererRef = materialRenderers[i];
                if (rendererRef == null)
                {
                    continue;
                }

                sawRenderer = true;
                if (rendererRef.sharedMaterial != targetMaterial)
                {
                    return false;
                }
            }

            return sawRenderer;
        }

        private bool TryResolveAuthoritativeTeamMarkerRenderer(out Renderer renderer)
        {
            renderer = null;

            var visualRoot = transform.Find("VisualRoot");
            Transform authoritativeMarker = null;
            if (visualRoot != null)
            {
                authoritativeMarker = visualRoot.Find("TeamMarker_Ring");
            }

            var allMarkers = new System.Collections.Generic.List<Transform>(4);
            CollectTeamMarkerTransforms(transform, allMarkers);

            if (authoritativeMarker == null && allMarkers.Count > 0)
            {
                for (var i = 0; i < allMarkers.Count; i++)
                {
                    if (allMarkers[i] != null && allMarkers[i].gameObject.activeInHierarchy)
                    {
                        authoritativeMarker = allMarkers[i];
                        break;
                    }
                }

                authoritativeMarker ??= allMarkers[0];
            }

            if (authoritativeMarker == null)
            {
                return false;
            }

            if (!authoritativeMarker.gameObject.activeSelf)
            {
                WarnOnce(ref _warnedInactiveAuthoritativeMarker, "Authoritative TeamMarker_Ring was inactive and has been activated.");
                authoritativeMarker.gameObject.SetActive(true);
            }

            renderer = authoritativeMarker.GetComponent<Renderer>();
            if (renderer == null)
            {
                return false;
            }

            for (var i = 0; i < allMarkers.Count; i++)
            {
                var marker = allMarkers[i];
                if (marker == null || marker == authoritativeMarker)
                {
                    continue;
                }

                if (marker.gameObject.activeSelf)
                {
                    marker.gameObject.SetActive(false);
                    WarnOnce(ref _warnedDuplicateMarker, $"Duplicate TeamMarker_Ring disabled at {GetHierarchyPath(marker)}.");
                }
            }

            if (materialRenderers == null || materialRenderers.Length != 1 || materialRenderers[0] != renderer)
            {
                materialRenderers = new Renderer[] { renderer };
            }

            return true;
        }

        private static void CollectTeamMarkerTransforms(Transform root, System.Collections.Generic.List<Transform> markers)
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

        private void SpawnOptionalVfx(GameObject prefab)
        {
            if (prefab == null)
            {
                return;
            }

            var instance = Instantiate(prefab, transform.position, Quaternion.identity, transform);
            var life = defaultVfxLifetimeSeconds > 0f ? defaultVfxLifetimeSeconds : 2f;
            Destroy(instance, life);
        }

        private bool TryGetAnimator(out Animator value)
        {
            value = animator;
            if (value != null)
            {
                return true;
            }

            WarnOnce(ref _warnedAnimatorMissing, "Animator is not assigned. Visual animation calls will be ignored.");
            return false;
        }

        private static void WarnOnce(ref bool warnedFlag, string message)
        {
            if (warnedFlag)
            {
                return;
            }

            warnedFlag = true;
#if UNITY_EDITOR || DEVELOPMENT_BUILD
            Debug.LogWarning($"[UnitVisualAnimator] {message}");
#endif
        }
    }
}
