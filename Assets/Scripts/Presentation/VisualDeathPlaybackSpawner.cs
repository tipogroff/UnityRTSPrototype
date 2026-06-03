using RTS.Gameplay;
using UnityEngine;

namespace RTS.Presentation
{
    public static class VisualDeathPlaybackSpawner
    {
        private const float DefaultDeathPlaybackSeconds = 2f;
        private const string DeathStateName = "Death";

        public static GameObject LastSpawnedClone { get; private set; }
        public static string LastSpawnedCloneId { get; private set; } = string.Empty;
                public static bool Enabled { get; set; } = false;
public static string LastSpawnDiagnostic { get; private set; } = string.Empty;

        public static bool TrySpawn(UnitRuntime deadUnit, out GameObject clone, out string diagnostic, float deathPlaybackSeconds = DefaultDeathPlaybackSeconds)
        {
            clone = null;
                        if (!Enabled)
            {
                diagnostic = "Visual death playback disabled.";
                LastSpawnDiagnostic = diagnostic;
                return false;
            }

diagnostic = string.Empty;

            if (deadUnit == null || deadUnit.gameObject == null)
            {
                diagnostic = "Dead unit is null.";
                return false;
            }

            var sourceObject = deadUnit.gameObject;
            var position = sourceObject.transform.position;
            var rotation = sourceObject.transform.rotation;
            var scale = sourceObject.transform.lossyScale;

            clone = Object.Instantiate(sourceObject, position, rotation);
            clone.name = sourceObject.name + "_DeathGhost";
            clone.transform.SetParent(null, true);
            clone.transform.position = position;
            clone.transform.rotation = rotation;
            clone.transform.localScale = scale;
            clone.SetActive(false);

            StripGameplayComponents(clone);

            var playback = clone.AddComponent<VisualDeathPlaybackGhost>();
            clone.SetActive(true);

            playback.Initialize(
                deadUnit.GetInstanceID().ToString(),
                deadUnit.Type.ToString(),
                deadUnit.Owner.ToString(),
                deadUnit.GridPos,
                deathPlaybackSeconds,
                DeathStateName);

            LastSpawnedClone = clone;
            LastSpawnedCloneId = clone.GetInstanceID().ToString();
            LastSpawnDiagnostic = $"Spawned visual death clone for {deadUnit.Owner}.{deadUnit.Type} at {deadUnit.GridPos}.";

            Visual3EDRuntimeAnimationTrace.Record(
                deadUnit.GetInstanceID().ToString(),
                deadUnit.Type.ToString(),
                deadUnit.Owner.ToString(),
                deadUnit.GridPos,
                "DeathVisualCloneSpawned",
                "Instantiate clone",
                "VisualDeathPlaybackSpawner.TrySpawn",
                true,
                LastSpawnDiagnostic,
                LastSpawnedCloneId);

            diagnostic = LastSpawnDiagnostic;
            return true;
        }

        private static void StripGameplayComponents(GameObject root)
        {
            if (root == null)
            {
                return;
            }

            foreach (var component in root.GetComponentsInChildren<MonoBehaviour>(true))
            {
                if (component == null || component is VisualDeathPlaybackGhost)
                {
                    continue;
                }

                Object.DestroyImmediate(component);
            }

            foreach (var collider in root.GetComponentsInChildren<Collider>(true))
            {
                if (collider != null)
                {
                    Object.DestroyImmediate(collider);
                }
            }

            foreach (var rigidbody in root.GetComponentsInChildren<Rigidbody>(true))
            {
                if (rigidbody != null)
                {
                    Object.DestroyImmediate(rigidbody);
                }
            }

            foreach (var joint in root.GetComponentsInChildren<Joint>(true))
            {
                if (joint != null)
                {
                    Object.DestroyImmediate(joint);
                }
            }

            foreach (var controller in root.GetComponentsInChildren<CharacterController>(true))
            {
                if (controller != null)
                {
                    Object.DestroyImmediate(controller);
                }
            }
        }
    }

    public sealed class VisualDeathPlaybackGhost : MonoBehaviour
    {
        private const string DeathStateName = "Death";

        private Animator _animator;
        private string _unitInstanceId;
        private string _unitType;
        private string _owner;
        private GridPosition _gridPosition;
        private string _cloneId;
        private string _deathStateName;
        private float _destroyAt;
        private bool _initialized;
        private bool _destroyTraceWritten;

        public void Initialize(
            string unitInstanceId,
            string unitType,
            string owner,
            GridPosition gridPosition,
            float deathPlaybackSeconds,
            string deathStateName)
        {
            _unitInstanceId = unitInstanceId;
            _unitType = unitType;
            _owner = owner;
            _gridPosition = gridPosition;
            _deathStateName = string.IsNullOrWhiteSpace(deathStateName) ? DeathStateName : deathStateName;
            _cloneId = GetInstanceID().ToString();
            _destroyAt = Time.unscaledTime + Mathf.Max(0.1f, deathPlaybackSeconds);

            _animator = GetComponentInChildren<Animator>(true);
            if (_animator != null)
            {
                _animator.Rebind();
                _animator.Update(0f);
                _animator.Play(_deathStateName, 0, 0f);
            }

            _initialized = true;

            Visual3EDRuntimeAnimationTrace.Record(
                _unitInstanceId,
                _unitType,
                _owner,
                _gridPosition,
                "DeathVisualPlaybackStarted",
                "Animator.Play(Death,0,0f)",
                "VisualDeathPlaybackGhost.Initialize",
                true,
                $"Death animation started on visual-only clone {_cloneId}.",
                _cloneId);
        }

        private void Update()
        {
            if (!_initialized || _destroyTraceWritten)
            {
                return;
            }

            if (Time.unscaledTime < _destroyAt)
            {
                return;
            }

            _destroyTraceWritten = true;
            Visual3EDRuntimeAnimationTrace.Record(
                _unitInstanceId,
                _unitType,
                _owner,
                _gridPosition,
                "DeathVisualCloneDestroyed",
                "Destroy(gameObject)",
                "VisualDeathPlaybackGhost.Update",
                true,
                $"Visual death clone {_cloneId} lifetime elapsed.",
                _cloneId);

            Destroy(gameObject);
        }

        private void OnDestroy()
        {
            if (!_initialized || _destroyTraceWritten)
            {
                return;
            }

            _destroyTraceWritten = true;
            Visual3EDRuntimeAnimationTrace.Record(
                _unitInstanceId,
                _unitType,
                _owner,
                _gridPosition,
                "DeathVisualCloneDestroyed",
                "OnDestroy",
                "VisualDeathPlaybackGhost.OnDestroy",
                true,
                $"Visual death clone {_cloneId} destroyed externally.",
                _cloneId);
        }
    }
}