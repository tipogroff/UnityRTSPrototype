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

        public bool IsInterpolating => _isInterpolating;
        public Vector3 CurrentVisualOffset => _currentOffsetLocal;

        private void Awake()
        {
            ResolveReferences();
            CacheBaselineIfNeeded();
            SnapInternal(false, "Awake", "Baseline initialized.");
        }

        private void OnEnable()
        {
            ResolveReferences();
            CacheBaselineIfNeeded();
            SnapInternal(false, "OnEnable", "Baseline restored.");
        }

        private void LateUpdate()
        {
            if (!_isInterpolating || !enableInterpolation || visualRoot == null)
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
            visualRoot.localPosition = _baselineLocalPosition + _currentOffsetLocal;

            if (_elapsed >= moveDuration)
            {
                CompleteInterpolation("Interpolation completed.");
            }
        }

        public void NotifyRootTeleported(Vector3 previousWorldPosition, Vector3 currentWorldPosition)
        {
            ResolveReferences();
            CacheBaselineIfNeeded();

            if (!enableInterpolation || visualRoot == null)
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

            Vector3 startWorldPosition = _isInterpolating ? visualRoot.position : previousWorldPosition;
            Vector3 startOffsetLocal = WorldDeltaToLocalOffset(startWorldPosition - currentWorldPosition);

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
            visualRoot.localPosition = _baselineLocalPosition + _startOffsetLocal;

            TraceStarted(previousWorldPosition, currentWorldPosition, _startOffsetLocal, "VisualGridMovementInterpolator.NotifyRootTeleported", "Interpolation started from teleported root state.");
        }

        public void SnapToCurrent()
        {
            SnapInternal(true, "SnapToCurrent", "Explicit snap requested.");
        }

        private void CompleteInterpolation(string diagnostic)
        {
            _elapsed = moveDuration;
            _isInterpolating = false;
            _startOffsetLocal = Vector3.zero;
            _currentOffsetLocal = Vector3.zero;

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

            _elapsed = 0f;
            _isInterpolating = false;
            _startOffsetLocal = Vector3.zero;
            _currentOffsetLocal = Vector3.zero;

            if (visualRoot != null)
            {
                visualRoot.localPosition = _baselineLocalPosition;
            }

            if (recordTrace)
            {
                Vector3 currentWorldPosition = visualRoot != null ? visualRoot.position : transform.position;
                _lastPreviousWorldPosition = currentWorldPosition;
                _lastCurrentWorldPosition = currentWorldPosition;
                TraceSnapped(sourceMethod, currentWorldPosition, diagnostic);
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

        private void TraceSnapped(string sourceMethod, Vector3 currentWorldPosition, string diagnostic)
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
                diagnostic);
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