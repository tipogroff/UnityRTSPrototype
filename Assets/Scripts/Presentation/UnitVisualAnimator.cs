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
        private bool _parameterCacheBuilt;
        private bool _hasIsMoving;
        private bool _hasIsCarrying;
        private bool _hasAttack;
        private bool _hasHarvest;
        private bool _hasDeath;
        private bool _hasSpawn;
        private bool _hasHit;
        private static bool _warnedMissingIsMoving;
        private static bool _warnedMissingIsCarrying;
        private static bool _warnedMissingAttack;
        private static bool _warnedMissingHarvest;
        private static bool _warnedMissingDeath;
        private static bool _warnedMissingSpawn;
        private static bool _warnedMissingHit;

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

            EnsureParameterCache(a);
            if (_hasIsMoving)
            {
                a.SetBool(IsMovingHash, value);
                return;
            }

            WarnOnce(ref _warnedMissingIsMoving, "Animator parameter 'IsMoving' is missing.");
        }

        public void SetCarrying(bool value)
        {
            if (!TryGetAnimator(out var a))
            {
                return;
            }

            EnsureParameterCache(a);
            if (_hasIsCarrying)
            {
                a.SetBool(IsCarryingHash, value);
                return;
            }

            WarnOnce(ref _warnedMissingIsCarrying, "Animator parameter 'IsCarrying' is missing.");
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

        public Animator GetAnimatorComponent()
        {
            return TryGetAnimator(out var resolved) ? resolved : null;
        }

        public string GetAnimatorPath()
        {
            return TryGetAnimator(out var resolved) ? GetHierarchyPath(resolved.transform) : string.Empty;
        }

        public bool HasAnimatorReference()
        {
            return TryGetAnimator(out _);
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

        public Animator GetAnimatorReference()
        {
            return animator;
        }

        public string GetAnimatorReferencePath()
        {
            return animator != null ? GetHierarchyPath(animator.transform) : string.Empty;
        }

        public bool HasBoolParameter(string parameterName)
        {
            if (!TryGetAnimator(out var a))
            {
                return false;
            }

            EnsureParameterCache(a);
            int hash = Animator.StringToHash(parameterName);
            return (hash == IsMovingHash && _hasIsMoving) || (hash == IsCarryingHash && _hasIsCarrying);
        }

        public bool HasTriggerParameter(string parameterName)
        {
            if (!TryGetAnimator(out var a))
            {
                return false;
            }

            EnsureParameterCache(a);
            int hash = Animator.StringToHash(parameterName);
            return (hash == AttackHash && _hasAttack) ||
                   (hash == HarvestHash && _hasHarvest) ||
                   (hash == DeathHash && _hasDeath) ||
                   (hash == SpawnHash && _hasSpawn) ||
                   (hash == HitHash && _hasHit);
        }

        public bool TryGetBool(string parameterName, out bool value)
        {
            value = false;
            if (!TryGetAnimator(out var a))
            {
                return false;
            }

            if (!HasBoolParameter(parameterName))
            {
                return false;
            }

            value = a.GetBool(parameterName);
            return true;
        }

        private void Trigger(int triggerHash)
        {
            if (!TryGetAnimator(out var a))
            {
                return;
            }

            EnsureParameterCache(a);

            if (triggerHash == AttackHash)
            {
                if (_hasAttack)
                {
                    a.SetTrigger(triggerHash);
                    return;
                }

                WarnOnce(ref _warnedMissingAttack, "Animator trigger 'Attack' is missing.");
                return;
            }

            if (triggerHash == HarvestHash)
            {
                if (_hasHarvest)
                {
                    a.SetTrigger(triggerHash);
                    return;
                }

                WarnOnce(ref _warnedMissingHarvest, "Animator trigger 'Harvest' is missing.");
                return;
            }

            if (triggerHash == DeathHash)
            {
                if (_hasDeath)
                {
                    a.SetTrigger(triggerHash);
                    return;
                }

                WarnOnce(ref _warnedMissingDeath, "Animator trigger 'Death' is missing.");
                return;
            }

            if (triggerHash == SpawnHash)
            {
                if (_hasSpawn)
                {
                    a.SetTrigger(triggerHash);
                    return;
                }

                WarnOnce(ref _warnedMissingSpawn, "Animator trigger 'Spawn' is missing.");
                return;
            }

            if (triggerHash == HitHash)
            {
                if (_hasHit)
                {
                    a.SetTrigger(triggerHash);
                    return;
                }

                WarnOnce(ref _warnedMissingHit, "Animator trigger 'Hit' is missing.");
            }
        }

        private void EnsureParameterCache(Animator targetAnimator)
        {
            if (_parameterCacheBuilt || targetAnimator == null)
            {
                return;
            }

            var parameters = targetAnimator.parameters;
            for (var i = 0; i < parameters.Length; i++)
            {
                var parameter = parameters[i];
                if (parameter.type == AnimatorControllerParameterType.Bool)
                {
                    if (parameter.nameHash == IsMovingHash)
                    {
                        _hasIsMoving = true;
                    }
                    else if (parameter.nameHash == IsCarryingHash)
                    {
                        _hasIsCarrying = true;
                    }
                }
                else if (parameter.type == AnimatorControllerParameterType.Trigger)
                {
                    if (parameter.nameHash == AttackHash)
                    {
                        _hasAttack = true;
                    }
                    else if (parameter.nameHash == HarvestHash)
                    {
                        _hasHarvest = true;
                    }
                    else if (parameter.nameHash == DeathHash)
                    {
                        _hasDeath = true;
                    }
                    else if (parameter.nameHash == SpawnHash)
                    {
                        _hasSpawn = true;
                    }
                    else if (parameter.nameHash == HitHash)
                    {
                        _hasHit = true;
                    }
                }
            }

            _parameterCacheBuilt = true;
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
