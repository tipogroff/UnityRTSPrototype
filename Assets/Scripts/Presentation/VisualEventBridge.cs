using RTS.Gameplay;
using UnityEngine;

namespace RTS.Presentation
{
    /// <summary>
    /// Thin gameplay-to-presentation bridge.
    /// Polls runtime state and forwards visual updates only.
    /// </summary>
    public sealed class VisualEventBridge : MonoBehaviour
    {
        [SerializeField] private UnitRuntime unitRuntime;
        [SerializeField] private UnitVisualAnimator unitVisualAnimator;
        [SerializeField] private float movementLatchSeconds = 0.15f;

        private GridPosition _lastGridPos;
        private bool _hadValidGridPos;
        private float _movingUntil;
        private bool _deathPlayed;

        private void Awake()
        {
            if (unitRuntime == null)
            {
                unitRuntime = GetComponent<UnitRuntime>();
            }

            if (unitVisualAnimator == null)
            {
                unitVisualAnimator = GetComponentInChildren<UnitVisualAnimator>(true);
            }
        }

        private void Start()
        {
            if (unitRuntime == null || unitVisualAnimator == null)
            {
                return;
            }

            unitVisualAnimator.SetOwnerVisual(unitRuntime.Owner);
            unitVisualAnimator.SetCarrying(unitRuntime.CarriedResources > 0);

            if (unitRuntime.Model != null)
            {
                _lastGridPos = unitRuntime.GridPos;
                _hadValidGridPos = true;
            }

            unitVisualAnimator.PlaySpawn();
        }

        private void Update()
        {
            if (unitRuntime == null || unitVisualAnimator == null)
            {
                return;
            }

            if (!unitRuntime.IsAlive)
            {
                if (!_deathPlayed)
                {
                    _deathPlayed = true;
                    unitVisualAnimator.SetMoving(false);
                    unitVisualAnimator.PlayDeath();
                }

                return;
            }

            var isMoving = false;
            if (unitRuntime.Model != null)
            {
                var currentPos = unitRuntime.GridPos;
                if (_hadValidGridPos && currentPos != _lastGridPos)
                {
                    _movingUntil = Time.time + movementLatchSeconds;
                    _lastGridPos = currentPos;
                }
                else if (!_hadValidGridPos)
                {
                    _lastGridPos = currentPos;
                    _hadValidGridPos = true;
                }

                isMoving = Time.time <= _movingUntil;
            }

            unitVisualAnimator.SetMoving(isMoving);
            unitVisualAnimator.SetCarrying(unitRuntime.CarriedResources > 0);
        }

        // Optional visual-only hooks for explicit wiring from gameplay call sites.
        public void OnVisualAttack()
        {
            unitVisualAnimator?.PlayAttack();
        }

        public void OnVisualHarvest()
        {
            unitVisualAnimator?.PlayHarvest();
        }

        public void OnVisualHit()
        {
            unitVisualAnimator?.PlayHit();
        }

        public void OnVisualSpawn()
        {
            unitVisualAnimator?.PlaySpawn();
        }

        public void OnVisualDeath()
        {
            unitVisualAnimator?.PlayDeath();
        }
    }
}
