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

        private void Awake()
        {
            if (animator == null)
            {
                animator = GetComponentInChildren<Animator>(true);
            }
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
            if (materialRenderers == null || materialRenderers.Length == 0)
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
            if (materialRenderers == null || materialRenderers.Length == 0)
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
