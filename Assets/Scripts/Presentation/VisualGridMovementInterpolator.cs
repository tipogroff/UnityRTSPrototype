using RTS.Gameplay;
using UnityEngine;

namespace RTS.Presentation
{
    /// <summary>
    /// Presentation-only visual movement interpolator.
    /// The gameplay root remains authoritative and jumps discretely between cells.
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class VisualGridMovementInterpolator : MonoBehaviour
    {
        [SerializeField] private Transform visualRoot;
        [SerializeField] private float moveDuration = 0.3f;
        [SerializeField] private AnimationCurve easing = AnimationCurve.Linear(0f, 0f, 1f, 1f);
        [SerializeField] private bool useScaledTime = true;
        [SerializeField] private bool enableInterpolation = true;
        [SerializeField] private bool debugDisableSmoothMovement;
        [SerializeField] private bool fallbackToTeleportOnError = true;
        [SerializeField] private float maxOffsetMagnitude = 2.5f;
        [SerializeField] private float hardSnapDistanceThreshold = 2.5f;
        [SerializeField] private float teleportDistanceThreshold = 0.05f;
        [SerializeField] private bool traceEnabled;

        private UnitRuntime _unitRuntime;
        private Transform _rootTransform;
        private Vector3 _baselineLocalPosition;
        private Vector3 _startOffsetLocal;
        private Vector3 _currentOffsetLocal;
        private Vector3 _lastPreviousWorldPosition;
        private Vector3 _lastCurrentWorldPosition;
        private bool _baselineCached;
        private bool _isInterpolating;
        private float _elapsed;
        private int _snapCount;
        private int _excessiveSnapCount;
        private int _lastSnapFrame = -1;
        private string _lastSnapReason = string.Empty;
        private int _lastInterpolationStartFrame = -1;
        private int _lastInterpolationEndFrame = -1;

        public bool IsInterpolating => _isInterpolating;
        public Vector3 CurrentVisualOffset => _currentOffsetLocal;
        public bool IsInterpolationEnabled => enableInterpolation && !debugDisableSmoothMovement;
        public int SnapCount => _snapCount;
        public int ExcessiveSnapCount => _excessiveSnapCount;
        public int LastSnapFrame => _lastSnapFrame;
        public string LastSnapReason => _lastSnapReason;
        public int LastInterpolationStartFrame => _lastInterpolationStartFrame;
        public int LastInterpolationEndFrame => _lastInterpolationEndFrame;

        private void Awake()
        {
            ResolveReferences();
            CacheBaselineIfNeeded();
            SnapInternal(true, "Awake", "Baseline initialized.");
        }

        private void OnEnable()
        {
            ResolveReferences();
            CacheBaselineIfNeeded();
            SnapInternal(true, "OnEnable", "Baseline restored.");
        }

        private void OnDisable()
        {
            SnapInternal(true, "OnDisable", "Interpolator disabled.");
        }

        private void OnDestroy()
        {
            SnapInternal(true, "OnDestroy", "Interpolator destroyed.");
        }

        private void LateUpdate()
        {
            if (!_isInterpolating || !IsInterpolationEnabled || visualRoot == null)
            {
                return;
            }

            float deltaTime = useScaledTime ? Time.deltaTime : Time.unscaledDeltaTime;
            if (deltaTime < 0f)
            {
                deltaTime = 0f;
            }

            if (moveDuration <= Mathf.Epsilon)
            {
                CompleteInterpolation("moveDuration <= epsilon.");
                return;
            }

            _elapsed = Mathf.Min(_elapsed + deltaTime, moveDuration);
            float normalizedTime = Mathf.Clamp01(_elapsed / moveDuration);
            float easedTime = easing != null && easing.length > 0 ? easing.Evaluate(normalizedTime) : normalizedTime;
            _currentOffsetLocal = Vector3.LerpUnclamped(_startOffsetLocal, Vector3.zero, easedTime);

            if (fallbackToTeleportOnError && IsOffsetAbnormal(_currentOffsetLocal))
            {
                SnapInternal(true, "LateUpdate", "Offset exceeded maxOffsetMagnitude during interpolation.");
                return;
            }

            visualRoot.localPosition = _baselineLocalPosition + _currentOffsetLocal;
            TraceUpdated(_lastPreviousWorldPosition, _lastCurrentWorldPosition, _currentOffsetLocal, "VisualGridMovementInterpolator.LateUpdate", "Interpolation updated.");

            if (_elapsed >= moveDuration)
            {
                CompleteInterpolation("Interpolation completed.");
            }
        }

        public void NotifyRootTeleported(Vector3 previousWorldPosition, Vector3 currentWorldPosition)
        {
            ResolveReferences();
            CacheBaselineIfNeeded();

            if (!IsInterpolationEnabled || visualRoot == null)
            {
                SnapInternal(false, "NotifyRootTeleported", "Interpolation disabled or visualRoot missing.");
                return;
            }

            float threshold = Mathf.Max(0f, teleportDistanceThreshold);
            float sqrThreshold = threshold * threshold;
            Vector3 delta = previousWorldPosition - currentWorldPosition;
            if (delta.sqrMagnitude <= sqrThreshold)
            {
                SnapInternal(false, "NotifyRootTeleported", "Teleport delta below threshold.");
                return;
            }

            if (hardSnapDistanceThreshold > 0f && delta.magnitude >= hardSnapDistanceThreshold)
            {
                SnapInternal(true, "NotifyRootTeleported", "Teleport delta exceeded hardSnapDistanceThreshold.");
                return;
            }

            Vector3 startWorldPosition = _isInterpolating ? visualRoot.position : previousWorldPosition;
            Vector3 startOffsetLocal = WorldDeltaToLocalOffset(startWorldPosition - currentWorldPosition);

            if (fallbackToTeleportOnError && IsOffsetAbnormal(startOffsetLocal))
            {
                SnapInternal(true, "NotifyRootTeleported", "Computed initial offset exceeded maxOffsetMagnitude.");
                return;
            }

            if (_isInterpolating)
            {
                TraceInterrupted(previousWorldPosition, currentWorldPosition, _currentOffsetLocal, "New teleport arrived before previous interpolation completed.");
            }

            _lastPreviousWorldPosition = previousWorldPosition;
            _lastCurrentWorldPosition = currentWorldPosition;
            _startOffsetLocal = startOffsetLocal;
            _currentOffsetLocal = startOffsetLocal;
            _elapsed = 0f;
            _isInterpolating = true;
            _lastInterpolationStartFrame = Time.frameCount;
            visualRoot.localPosition = _baselineLocalPosition + _startOffsetLocal;

            TraceStarted(previousWorldPosition, currentWorldPosition, _startOffsetLocal, "VisualGridMovementInterpolator.NotifyRootTeleported", "Interpolation started from teleported root state.");
        }

        public void SnapToCurrent()
        {
            SnapInternal(true, "SnapToCurrent", "Explicit snap requested.");
        }

        public void SnapToCurrent(string reason)
        {
            string resolvedReason = string.IsNullOrWhiteSpace(reason) ? "Explicit snap requested." : reason;
            SnapInternal(true, "SnapToCurrent", resolvedReason);
        }

        public void SetInterpolationEnabled(bool value, string reason = "Runtime toggle")
        {
            enableInterpolation = value;
            if (!IsInterpolationEnabled)
            {
                SnapInternal(true, "SetInterpolationEnabled", reason + " => disabled");
            }
        }

        private void CompleteInterpolation(string diagnostic)
        {
            _elapsed = moveDuration;
            _isInterpolating = false;
            _startOffsetLocal = Vector3.zero;
            _currentOffsetLocal = Vector3.zero;
            _lastInterpolationEndFrame = Time.frameCount;

            if (visualRoot != null)
            {
                visualRoot.localPosition = _baselineLocalPosition;
            }

            TraceCompleted(_lastPreviousWorldPosition, _lastCurrentWorldPosition, "VisualGridMovementInterpolator.LateUpdate", diagnostic);
        }

        private void SnapInternal(bool recordTrace, string sourceMethod, string diagnostic)
        {
            ResolveReferences();
            CacheBaselineIfNeeded();

            bool wasInterpolatingBeforeSnap = _isInterpolating;
            Vector3 visualOffsetBeforeSnap = _currentOffsetLocal;

            _elapsed = 0f;
            _isInterpolating = false;
            _startOffsetLocal = Vector3.zero;
            _currentOffsetLocal = Vector3.zero;
            _lastInterpolationEndFrame = Time.frameCount;

            int frame = Time.frameCount;
            if (_lastSnapFrame >= 0 && frame == _lastSnapFrame)
            {
                _excessiveSnapCount++;
            }

            _snapCount++;
            _lastSnapFrame = frame;
            _lastSnapReason = diagnostic ?? string.Empty;

            if (visualRoot != null)
            {
                visualRoot.localPosition = _baselineLocalPosition;
            }

            if (recordTrace)
            {
                Vector3 currentWorldPosition = visualRoot != null ? visualRoot.position : transform.position;
                _lastPreviousWorldPosition = currentWorldPosition;
                _lastCurrentWorldPosition = currentWorldPosition;
                TraceSnapped(sourceMethod, currentWorldPosition, _lastSnapReason, wasInterpolatingBeforeSnap, visualOffsetBeforeSnap);
            }
        }

        private void ResolveReferences()
        {
            if (visualRoot == null)
            {
                if (transform.name == "VisualRoot")
                {
                    visualRoot = transform;
                }
                else
                {
                    visualRoot = transform.Find("VisualRoot");
                }
            }

            if (_unitRuntime == null)
            {
                _unitRuntime = GetComponent<UnitRuntime>();
            }

            if (_unitRuntime == null)
            {
                _unitRuntime = GetComponentInParent<UnitRuntime>(true);
            }

            if (_unitRuntime == null)
            {
                _unitRuntime = GetComponentInChildren<UnitRuntime>(true);
            }

            if (visualRoot != null)
            {
                _rootTransform = visualRoot.parent != null ? visualRoot.parent : transform;
            }
        }

        private void CacheBaselineIfNeeded()
        {
            if (_baselineCached || visualRoot == null)
            {
                return;
            }

            _baselineLocalPosition = visualRoot.localPosition;
            _baselineCached = true;
        }

        private Vector3 WorldDeltaToLocalOffset(Vector3 worldDelta)
        {
            if (_rootTransform == null)
            {
                return worldDelta;
            }

            return _rootTransform.InverseTransformVector(worldDelta);
        }

        private bool IsOffsetAbnormal(Vector3 offset)
        {
            if (maxOffsetMagnitude <= 0f)
            {
                return false;
            }

            return offset.sqrMagnitude > (maxOffsetMagnitude * maxOffsetMagnitude);
        }

        private void TraceStarted(Vector3 previousWorldPosition, Vector3 currentWorldPosition, Vector3 initialOffset, string sourceMethod, string diagnostic)
        {
            if (!traceEnabled)
            {
                return;
            }

            Visual3EFSmoothMovementTrace.RecordStarted(
                _unitRuntime,
                previousWorldPosition,
                currentWorldPosition,
                initialOffset,
                moveDuration,
                sourceMethod,
                diagnostic);
        }

        private void TraceCompleted(Vector3 previousWorldPosition, Vector3 currentWorldPosition, string sourceMethod, string diagnostic)
        {
            if (!traceEnabled)
            {
                return;
            }

            Visual3EFSmoothMovementTrace.RecordCompleted(
                _unitRuntime,
                previousWorldPosition,
                currentWorldPosition,
                Vector3.zero,
                moveDuration,
                sourceMethod,
                diagnostic);
        }

        private void TraceUpdated(Vector3 previousWorldPosition, Vector3 currentWorldPosition, Vector3 currentOffset, string sourceMethod, string diagnostic)
        {
            if (!traceEnabled)
            {
                return;
            }

            Visual3EFSmoothMovementTrace.RecordUpdated(
                _unitRuntime,
                previousWorldPosition,
                currentWorldPosition,
                currentOffset,
                moveDuration,
                sourceMethod,
                diagnostic);
        }

        private void TraceSnapped(string sourceMethod, Vector3 currentWorldPosition, string diagnostic, bool wasInterpolatingBeforeSnap, Vector3 visualOffsetBeforeSnap)
        {
            if (!traceEnabled)
            {
                return;
            }

            Visual3EFSmoothMovementTrace.RecordSnapped(
                _unitRuntime,
                currentWorldPosition,
                currentWorldPosition,
                Vector3.zero,
                0f,
                sourceMethod,
                diagnostic,
                wasInterpolatingBeforeSnap,
                visualOffsetBeforeSnap);
        }

        private void TraceInterrupted(Vector3 previousWorldPosition, Vector3 currentWorldPosition, Vector3 initialOffset, string diagnostic)
        {
            if (!traceEnabled)
            {
                return;
            }

            Visual3EFSmoothMovementTrace.RecordInterrupted(
                _unitRuntime,
                previousWorldPosition,
                currentWorldPosition,
                initialOffset,
                moveDuration,
                "VisualGridMovementInterpolator.NotifyRootTeleported",
                diagnostic);
        }
    }
}