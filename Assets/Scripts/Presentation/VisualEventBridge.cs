using RTS.Core;
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
        [SerializeField] private bool forceInitialSyncUntilSuccess = true;
        [SerializeField] private bool enableRuntimeTrace;

        private GridPosition _lastGridPos;
        private bool _hadValidGridPos;
        private float _movingUntil;
        private bool _deathPlayed;
        private bool _ownerVisualSynced;
        private Owner _lastSyncedOwner = (Owner)(-1);
        private Owner _lastMismatchLoggedOwner = (Owner)(-1);
        private int _ownerSyncAttemptCount;
        private bool _ownerSyncEverSucceeded;
        private string _lastOwnerSyncMaterialName = string.Empty;
        private string _lastSyncReason = string.Empty;
        private bool _lastObservedModelNull = true;
        private bool _lastMaterialMatchedExpected;
        private int _lastSyncFrame = -1;
        private Owner _lastObservedOwner = Owner.Neutral;
        private bool _wasMoving;
        private bool _idleLogged;

        public Owner LastSyncedOwner => _lastSyncedOwner;
        public bool HasSyncedSuccessfully => _ownerVisualSynced;
        public int LastSyncFrame => _lastSyncFrame;
        public string LastSyncReason => _lastSyncReason;
        public Owner LastObservedOwner => _lastObservedOwner;
        public bool LastObservedModelNull => _lastObservedModelNull;
        public bool LastMaterialMatchedExpected => _lastMaterialMatchedExpected;
        public string LastMarkerMaterialName => _lastOwnerSyncMaterialName;

        private void Awake()
        {
            ResolveReferences();
            if (unitRuntime != null && unitRuntime.Model != null)
            {
                TrySyncOwner("Awake");
            }
        }

        private void OnEnable()
        {
            ResolveReferences();
            ResetOwnerSyncState();
        }

        private void Start()
        {
            ResolveReferences();
            if (unitRuntime == null || unitVisualAnimator == null)
            {
                return;
            }

            TrySyncOwner("Start");

            unitVisualAnimator.SetCarrying(unitRuntime.CarriedResources > 0);

            if (unitRuntime.Model != null)
            {
                _lastGridPos = unitRuntime.GridPos;
                _hadValidGridPos = true;
            }

            unitVisualAnimator.PlaySpawn();
            TraceEvent("Idle", "IsMoving=false", "VisualEventBridge.Start", true, "Default idle state initialized.");
            _idleLogged = true;
        }

        private void Update()
        {
            ResolveReferences();
            if (unitRuntime == null || unitVisualAnimator == null)
            {
                return;
            }

            TrySyncOwner("Update");

            if (!unitRuntime.IsAlive)
            {
                if (!_deathPlayed)
                {
                    _deathPlayed = true;
                    unitVisualAnimator.SetMoving(false);
                    unitVisualAnimator.PlayDeath();
                    TraceEvent("Death", "Death trigger", "VisualEventBridge.Update", true, "Unit marked not alive in runtime state.");
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

            if (isMoving && !_wasMoving)
            {
                TraceEvent("MoveStart", "IsMoving=true", "VisualEventBridge.Update", true, "Movement latch activated by grid position change.");
                _idleLogged = false;
            }
            else if (!isMoving && _wasMoving)
            {
                TraceEvent("MoveEnd", "IsMoving=false", "VisualEventBridge.Update", true, "Movement latch expired; returning to idle.");
                TraceEvent("Idle", "IsMoving=false", "VisualEventBridge.Update", true, "Returned to idle after movement.");
                _idleLogged = true;
            }
            else if (!isMoving && !_idleLogged)
            {
                TraceEvent("Idle", "IsMoving=false", "VisualEventBridge.Update", true, "Idle state observed.");
                _idleLogged = true;
            }

            _wasMoving = isMoving;
        }

        private void LateUpdate()
        {
            ResolveReferences();
            if (!forceInitialSyncUntilSuccess)
            {
                return;
            }

            if (unitRuntime == null || unitVisualAnimator == null)
            {
                return;
            }

            if (_ownerVisualSynced)
            {
                return;
            }

            TrySyncOwner("LateUpdate");
        }

        public void NotifyRuntimeInitialized()
        {
            ResolveReferences();
            _ownerVisualSynced = false;
            TrySyncOwner("NotifyRuntimeInitialized");
            if (unitRuntime != null)
            {
                TraceEvent("Idle", "IsMoving=false", "VisualEventBridge.NotifyRuntimeInitialized", true, "Runtime initialized notification from UnitFactory.");
                _idleLogged = true;
            }
        }

        public void SetRuntimeTraceEnabled(bool value)
        {
            enableRuntimeTrace = value;
        }

        public void PulseMoving(float seconds = 0.2f)
        {
            var pulse = Mathf.Max(0.01f, seconds);
            _movingUntil = Mathf.Max(_movingUntil, Time.time + pulse);
            unitVisualAnimator?.SetMoving(true);

            if (!_wasMoving)
            {
                _wasMoving = true;
                _idleLogged = false;
                TraceEvent("MoveStart", "IsMoving=true", "VisualEventBridge.PulseMoving", true, $"Manual pulse for {pulse:0.000}s.");
            }
        }

        public int GetOwnerSyncAttemptCount()
        {
            return _ownerSyncAttemptCount;
        }

        public bool HasOwnerSyncEverSucceeded()
        {
            return _ownerSyncEverSucceeded;
        }

        public string GetLastOwnerSyncMaterialName()
        {
            return _lastOwnerSyncMaterialName;
        }

        public bool HasResolvedUnitRuntime()
        {
            return unitRuntime != null;
        }

        public bool HasResolvedUnitVisualAnimator()
        {
            return unitVisualAnimator != null;
        }

        public string GetResolvedUnitRuntimeName()
        {
            return unitRuntime != null ? unitRuntime.name : string.Empty;
        }

        public string GetResolvedUnitVisualAnimatorName()
        {
            return unitVisualAnimator != null ? unitVisualAnimator.name : string.Empty;
        }

        public Owner GetLastSyncedOwner()
        {
            return _lastSyncedOwner;
        }

        /// <summary>
        /// Syncs owner color to UnitVisualAnimator when the owner has changed or
        /// has not yet been synced. Safe to call every frame; no-ops when stable.
        /// </summary>
        private bool TrySyncOwner(string reason)
        {
            ResolveReferences();
            if (unitRuntime == null || unitVisualAnimator == null)
            {
                _lastSyncReason = reason;
                return false;
            }

            if (unitRuntime.Model == null)
            {
                _lastObservedModelNull = true;
                _lastSyncReason = reason;
                _ownerVisualSynced = false;
                return false;
            }

            var currentOwner = unitRuntime.Owner;
            _lastObservedOwner = currentOwner;
            _lastObservedModelNull = false;

            var materialMatchesExpected = unitVisualAnimator.IsMarkerMaterialCorrectForOwner(currentOwner);
            _lastMaterialMatchedExpected = materialMatchesExpected;
            _lastOwnerSyncMaterialName = unitVisualAnimator.GetCurrentOwnerMaterialName();

            if (_ownerVisualSynced && currentOwner == _lastSyncedOwner && materialMatchesExpected)
            {
                _lastSyncReason = reason;
                return true;
            }

            _ownerSyncAttemptCount++;
            var applied = unitVisualAnimator.ApplyOwnerVisualAndVerify(currentOwner, out var diagnostic);
            if (applied)
            {
                _lastSyncedOwner = currentOwner;
                _lastSyncFrame = Time.frameCount;
                _lastSyncReason = reason;
            }
            else
            {
                _lastSyncReason = string.IsNullOrWhiteSpace(diagnostic) ? reason : $"{reason}: {diagnostic}";
            }

            _ownerVisualSynced = applied;
            _ownerSyncEverSucceeded |= applied;
            _lastOwnerSyncMaterialName = unitVisualAnimator.GetCurrentOwnerMaterialName();
            _lastMaterialMatchedExpected = unitVisualAnimator.IsMarkerMaterialCorrectForOwner(currentOwner);

#if UNITY_EDITOR || DEVELOPMENT_BUILD
            if (!applied && _lastMismatchLoggedOwner != currentOwner)
            {
                _lastMismatchLoggedOwner = currentOwner;
                Debug.LogWarning(
                    $"[VisualEventBridge] Owner visual mismatch on {GetHierarchyPath(transform)} | owner={currentOwner} | currentMaterial={unitVisualAnimator.GetCurrentOwnerMaterialName()} | renderers={string.Join(", ", unitVisualAnimator.GetMaterialRendererDebugPaths())}");
            }
#endif

            return applied;
        }

        private void ResolveReferences()
        {
            if (unitRuntime == null)
            {
                unitRuntime = GetComponent<UnitRuntime>();
            }

            if (unitRuntime == null)
            {
                unitRuntime = GetComponentInParent<UnitRuntime>(true);
            }

            if (unitRuntime == null)
            {
                unitRuntime = GetComponentInChildren<UnitRuntime>(true);
            }

            if (unitVisualAnimator == null)
            {
                unitVisualAnimator = GetComponent<UnitVisualAnimator>();
            }

            if (unitVisualAnimator == null)
            {
                unitVisualAnimator = GetComponentInParent<UnitVisualAnimator>(true);
            }

            if (unitVisualAnimator == null)
            {
                unitVisualAnimator = GetComponentInChildren<UnitVisualAnimator>(true);
            }
        }

        private void ResetOwnerSyncState()
        {
            _ownerVisualSynced = false;
            _lastSyncedOwner = (Owner)(-1);
            _lastMismatchLoggedOwner = (Owner)(-1);
            _lastObservedOwner = (Owner)(-1);
            _lastObservedModelNull = true;
            _lastMaterialMatchedExpected = false;
            _lastSyncReason = "OnEnable";
            _lastSyncFrame = -1;
            _lastOwnerSyncMaterialName = string.Empty;
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

        // Optional visual-only hooks for explicit wiring from gameplay call sites.
        public void OnVisualAttack()
        {
            unitVisualAnimator?.PlayAttack();
            TraceEvent("Attack", "Attack trigger", "VisualEventBridge.OnVisualAttack", true, "Applied runtime attack visual notification.");
        }

        public void OnVisualHarvest()
        {
            unitVisualAnimator?.PlayHarvest();
            TraceEvent("Harvest", "Harvest trigger", "VisualEventBridge.OnVisualHarvest", true, "Applied runtime harvest visual notification.");
        }

        public void OnVisualHit()
        {
            unitVisualAnimator?.PlayHit();
            TraceEvent("Hit", "Hit trigger", "VisualEventBridge.OnVisualHit", true, "Applied runtime hit visual notification.");
        }

        public void OnVisualSpawn()
        {
            unitVisualAnimator?.PlaySpawn();
            TraceEvent("Idle", "Spawn trigger", "VisualEventBridge.OnVisualSpawn", true, "Spawn visual notification.");
        }

        public void OnVisualDeath()
        {
            unitVisualAnimator?.PlayDeath();
            TraceEvent("Death", "Death trigger", "VisualEventBridge.OnVisualDeath", true, "Applied runtime death visual notification.");
        }

        private void TraceEvent(string visualEvent, string animatorParameter, string source, bool success, string diagnostic)
        {
#if UNITY_EDITOR || DEVELOPMENT_BUILD
            if (!enableRuntimeTrace)
            {
                return;
            }

            Visual3EDRuntimeAnimationTrace.Record(
                unitRuntime,
                visualEvent,
                animatorParameter,
                source,
                success,
                diagnostic);
#endif
        }
    }
}
