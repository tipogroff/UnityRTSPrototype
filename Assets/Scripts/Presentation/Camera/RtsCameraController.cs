using System.Collections;
using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using RTS.Presentation.UI;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace RTS.Presentation.CameraControls
{
    [DisallowMultipleComponent]
    [RequireComponent(typeof(Camera))]
    public sealed class RtsCameraController : MonoBehaviour
    {
        [Header("Movement")]
        [SerializeField] private float _moveSpeed = 14f;
        [SerializeField] private float _zoomSpeed = 16f;
        [SerializeField] private float _minZoom = 6f;
        [SerializeField] private float _maxZoom = 18f;
        [SerializeField] private float _boundsPadding = 4f;
        [SerializeField] private float _smoothTime = 0.08f;
        [SerializeField] private bool _enableMiddleMouseDrag = true;

        [Header("Map")]
        [SerializeField] private int _mapWidth = GameConstants.MapWidth;
        [SerializeField] private int _mapHeight = GameConstants.MapHeight;
        [SerializeField] private bool _autoResolveGridBounds = true;

        [Header("View")]
        [SerializeField] private Vector3 _isometricRotation = new Vector3(58f, 45f, 0f);

        [Header("Match Start Focus")]
        [SerializeField] private Camera _camera;
        [SerializeField] private float _height = 14f;
        [SerializeField] private float _zOffset;
        [SerializeField] private float _xOffset;
        [SerializeField] private Vector3 _fallbackCenter = new Vector3(11.5f, 0f, 11.5f);
        [SerializeField] private bool _focusOnMatchStart = true;

        private Vector3 _targetPosition;
        private Vector3 _moveVelocity;
        private float _targetZoom;
        private float _zoomVelocity;
        private Vector2 _lastMousePosition;
        private bool _dragging;
        private Coroutine _focusCoroutine;
        private HumanPlayCanvasController _humanPlayCanvasController;

        private void Awake()
        {
            if (_camera == null)
            {
                _camera = GetComponent<Camera>();
            }

            if (_camera == null)
            {
                Debug.LogError("[RtsCameraController] Camera component is missing.", this);
                enabled = false;
                return;
            }

            _camera.orthographic = true;
            transform.rotation = Quaternion.Euler(_isometricRotation);
            ResolveMapBounds();
            _targetPosition = ClampToBounds(transform.position);
            _targetZoom = Mathf.Clamp(_camera.orthographicSize, _minZoom, _maxZoom);
            _camera.orthographicSize = _targetZoom;
        }

        private void LateUpdate()
        {
            ResolveMapBounds();
            ReadMovement();
            ReadZoom();
            ReadMiddleMouseDrag();

            transform.position = Vector3.SmoothDamp(
                transform.position,
                _targetPosition,
                ref _moveVelocity,
                _smoothTime,
                Mathf.Infinity,
                Time.unscaledDeltaTime);

            _camera.orthographicSize = Mathf.SmoothDamp(
                _camera.orthographicSize,
                _targetZoom,
                ref _zoomVelocity,
                _smoothTime,
                Mathf.Infinity,
                Time.unscaledDeltaTime);
        }

        public void FocusMapCenter()
        {
            _targetPosition = BuildCameraPositionForGroundPoint(GetMapCenter());
            transform.position = _targetPosition;
        }

        public void FocusOnOwnerAfterMatchStart(Owner owner)
        {
            StartMatchFocus(owner, focusCenter: false);
        }

        public void FocusOnCenterAfterMatchStart()
        {
            StartMatchFocus(Owner.Neutral, focusCenter: true);
        }

        private void StartMatchFocus(Owner owner, bool focusCenter)
        {
            if (!_focusOnMatchStart)
            {
                return;
            }

            if (_focusCoroutine != null)
            {
                StopCoroutine(_focusCoroutine);
            }

            _focusCoroutine = StartCoroutine(FocusAfterMatchStart(owner, focusCenter));
        }

        private IEnumerator FocusAfterMatchStart(Owner owner, bool focusCenter)
        {
            yield return null;

            Vector3 groundPoint = focusCenter ? GetFallbackCenter() : ResolveOwnerFocusPoint(owner);
            ApplyGroundFocus(groundPoint);
            _focusCoroutine = null;
        }

        private Vector3 ResolveOwnerFocusPoint(Owner owner)
        {
            UnitRegistry registry = UnitRegistry.Instance != null
                ? UnitRegistry.Instance
                : FindFirstObjectByType<UnitRegistry>();
            if (registry == null)
            {
                return GetFallbackCenter();
            }

            List<UnitRuntime> units = registry.GetUnitsByOwner(owner);
            UnitRuntime firstAlive = null;
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit == null || !unit.IsAlive)
                {
                    continue;
                }

                firstAlive ??= unit;
                if (unit.Type == UnitType.Base)
                {
                    return unit.transform.position;
                }
            }

            return firstAlive != null ? firstAlive.transform.position : GetFallbackCenter();
        }

        private void ApplyGroundFocus(Vector3 groundPoint)
        {
            ResolveMapBounds();
            groundPoint.y = 0f;
            float distance = Mathf.Max(1f, _height / Mathf.Max(0.1f, -transform.forward.y));
            Vector3 cameraPosition = groundPoint - transform.forward * distance;
            cameraPosition.x += _xOffset;
            cameraPosition.z += _zOffset;
            _targetPosition = cameraPosition;
            transform.position = _targetPosition;
            _moveVelocity = Vector3.zero;
        }

        private Vector3 GetFallbackCenter()
        {
            return _fallbackCenter == Vector3.zero ? GetMapCenter() : _fallbackCenter;
        }

        private void ReadMovement()
        {
            if (IsCameraInputBlocked() || IsTextInputFocused())
            {
                return;
            }

            Vector2 input = GetMoveInput();
            if (input.sqrMagnitude <= 0.0001f)
            {
                return;
            }

            Vector3 forward = transform.forward;
            forward.y = 0f;
            forward.Normalize();

            Vector3 right = transform.right;
            right.y = 0f;
            right.Normalize();

            Vector3 delta = (right * input.x + forward * input.y) * (_moveSpeed * Time.unscaledDeltaTime);
            _targetPosition = ClampToBounds(_targetPosition + delta);
        }

        private void ReadZoom()
        {
            if (IsCameraInputBlocked() || IsTextInputFocused())
            {
                return;
            }

            if (IsPointerOverInteractiveUi())
            {
                return;
            }

            float scroll = GetScrollDelta();
            if (Mathf.Abs(scroll) <= 0.0001f)
            {
                return;
            }

            _targetZoom = Mathf.Clamp(_targetZoom - scroll * _zoomSpeed, _minZoom, _maxZoom);
        }

        private void ReadMiddleMouseDrag()
        {
            if (!_enableMiddleMouseDrag)
            {
                return;
            }

            if (IsCameraInputBlocked() || IsTextInputFocused())
            {
                _dragging = false;
                return;
            }

            if (IsPointerOverInteractiveUi())
            {
                _dragging = false;
                return;
            }

            if (WasMiddleMousePressed())
            {
                _dragging = true;
                _lastMousePosition = GetPointerPosition();
                return;
            }

            if (WasMiddleMouseReleased())
            {
                _dragging = false;
                return;
            }

            if (!_dragging)
            {
                return;
            }

            Vector2 current = GetPointerPosition();
            Vector2 delta = current - _lastMousePosition;
            _lastMousePosition = current;

            Vector3 right = transform.right;
            right.y = 0f;
            right.Normalize();
            Vector3 forward = transform.forward;
            forward.y = 0f;
            forward.Normalize();

            float dragScale = Mathf.Max(0.02f, _targetZoom * 0.0025f);
            _targetPosition = ClampToBounds(_targetPosition - (right * delta.x + forward * delta.y) * dragScale);
        }

        private void ResolveMapBounds()
        {
            if (!_autoResolveGridBounds)
            {
                return;
            }

            GridManager grid = GridManager.Instance;
            if (grid == null)
            {
                grid = FindFirstObjectByType<GridManager>();
            }

            if (grid == null)
            {
                return;
            }

            _mapWidth = Mathf.Max(1, grid.Width);
            _mapHeight = Mathf.Max(1, grid.Height);
        }

        private Vector3 ClampToBounds(Vector3 position)
        {
            Vector3 ground = ProjectCameraPositionToGround(position);
            float minX = -_boundsPadding;
            float minZ = -_boundsPadding;
            float maxX = (_mapWidth - 1) * GameConstants.CellSize + _boundsPadding;
            float maxZ = (_mapHeight - 1) * GameConstants.CellSize + _boundsPadding;
            ground.x = Mathf.Clamp(ground.x, minX, maxX);
            ground.z = Mathf.Clamp(ground.z, minZ, maxZ);
            return BuildCameraPositionForGroundPoint(ground);
        }

        private Vector3 ProjectCameraPositionToGround(Vector3 cameraPosition)
        {
            Ray ray = new Ray(cameraPosition, transform.forward);
            Plane ground = new Plane(Vector3.up, Vector3.zero);
            if (ground.Raycast(ray, out float distance))
            {
                return ray.GetPoint(distance);
            }

            return GetMapCenter();
        }

        private Vector3 BuildCameraPositionForGroundPoint(Vector3 groundPoint)
        {
            float distance = Mathf.Max(1f, transform.position.y / Mathf.Max(0.1f, -transform.forward.y));
            return groundPoint - transform.forward * distance;
        }

        private Vector3 GetMapCenter()
        {
            return new Vector3((_mapWidth - 1) * GameConstants.CellSize * 0.5f, 0f, (_mapHeight - 1) * GameConstants.CellSize * 0.5f);
        }

        private static Vector2 GetMoveInput()
        {
            Vector2 input = Vector2.zero;
#if ENABLE_INPUT_SYSTEM
            Keyboard keyboard = Keyboard.current;
            if (keyboard != null)
            {
                input.x += keyboard.dKey.isPressed ? 1f : 0f;
                input.x -= keyboard.aKey.isPressed ? 1f : 0f;
                input.y += keyboard.wKey.isPressed ? 1f : 0f;
                input.y -= keyboard.sKey.isPressed ? 1f : 0f;
                return Vector2.ClampMagnitude(input, 1f);
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER && !ENABLE_INPUT_SYSTEM
            input.x += Input.GetKey(KeyCode.D) ? 1f : 0f;
            input.x -= Input.GetKey(KeyCode.A) ? 1f : 0f;
            input.y += Input.GetKey(KeyCode.W) ? 1f : 0f;
            input.y -= Input.GetKey(KeyCode.S) ? 1f : 0f;
#endif
            return Vector2.ClampMagnitude(input, 1f);
        }

        private static float GetScrollDelta()
        {
#if ENABLE_INPUT_SYSTEM
            Mouse mouse = Mouse.current;
            if (mouse != null)
            {
                return mouse.scroll.ReadValue().y / 120f;
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER && !ENABLE_INPUT_SYSTEM
            return Input.mouseScrollDelta.y;
#else
            return 0f;
#endif
        }

        private static Vector2 GetPointerPosition()
        {
#if ENABLE_INPUT_SYSTEM
            Mouse mouse = Mouse.current;
            if (mouse != null)
            {
                return mouse.position.ReadValue();
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER && !ENABLE_INPUT_SYSTEM
            return Input.mousePosition;
#else
            return Vector2.zero;
#endif
        }

        private static bool WasMiddleMousePressed()
        {
#if ENABLE_INPUT_SYSTEM
            Mouse mouse = Mouse.current;
            if (mouse != null)
            {
                return mouse.middleButton.wasPressedThisFrame;
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER && !ENABLE_INPUT_SYSTEM
            return Input.GetMouseButtonDown(2);
#else
            return false;
#endif
        }

        private static bool WasMiddleMouseReleased()
        {
#if ENABLE_INPUT_SYSTEM
            Mouse mouse = Mouse.current;
            if (mouse != null)
            {
                return mouse.middleButton.wasReleasedThisFrame;
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER && !ENABLE_INPUT_SYSTEM
            return Input.GetMouseButtonUp(2);
#else
            return false;
#endif
        }

        private static bool IsTextInputFocused()
        {
            EventSystem eventSystem = EventSystem.current;
            if (eventSystem == null || eventSystem.currentSelectedGameObject == null)
            {
                return false;
            }

            return eventSystem.currentSelectedGameObject.GetComponent<InputField>() != null;
        }

        private bool IsCameraInputBlocked()
        {
            _humanPlayCanvasController ??= FindFirstObjectByType<HumanPlayCanvasController>();
            return _humanPlayCanvasController != null && _humanPlayCanvasController.IsCameraInputBlocked;
        }

        private static bool IsPointerOverInteractiveUi()
        {
            EventSystem eventSystem = EventSystem.current;
            if (eventSystem == null)
            {
                return false;
            }

            PointerEventData pointer = new PointerEventData(eventSystem)
            {
                position = GetPointerPosition(),
            };
            List<RaycastResult> results = new List<RaycastResult>();
            eventSystem.RaycastAll(pointer, results);
            for (int i = 0; i < results.Count; i++)
            {
                GameObject hit = results[i].gameObject;
                if (hit != null && hit.GetComponentInParent<Selectable>() != null)
                {
                    return true;
                }
            }

            return false;
        }
    }
}
