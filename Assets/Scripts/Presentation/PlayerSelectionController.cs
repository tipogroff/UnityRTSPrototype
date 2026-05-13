using System;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;
using UnityEngine.EventSystems;

#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace RTS.Presentation
{
    [DisallowMultipleComponent]
    public sealed class PlayerSelectionController : MonoBehaviour
    {
        [Header("References")]
        [SerializeField] private Camera _selectionCamera;
        [SerializeField] private GridManager _gridManager;

        [Header("Selection")]
        [SerializeField] private LayerMask _raycastMask = ~0;
        [SerializeField] private float _raycastDistance = 500f;
        [SerializeField] private bool _clearSelectionOnEmptyClick = true;

        [Header("Marker")]
        [SerializeField] private bool _createSelectionMarker = true;
        [SerializeField] private Color _markerColor = new Color(0.1f, 0.9f, 0.2f, 0.55f);
        [SerializeField] private Vector3 _markerScale = new Vector3(0.8f, 0.04f, 0.8f);
        [SerializeField] private float _markerYOffset = 0.03f;

        [Header("Diagnostics")]
        [SerializeField] private bool _logWarnings = true;

        private Owner _humanSide = Owner.Player1;
        private bool _manualInputEnabled;
        private bool _legacyInputUnavailable;
        private GameObject _selectionMarker;

        public UnitRuntime SelectedUnit { get; private set; }
        public bool HasSelection => SelectedUnit != null;

        public event Action<UnitRuntime> OnSelectionChanged;

        private void Awake()
        {
            ResolveReferences();
            if (_createSelectionMarker)
            {
                EnsureSelectionMarker();
            }

            UpdateSelectionMarker();
        }

        private void Update()
        {
            ResolveReferences();
            ValidateSelectedUnit();
            UpdateSelectionMarker();

            if (!_manualInputEnabled)
            {
                return;
            }

            if (!IsLeftClickPressed())
            {
                return;
            }

            if (EventSystem.current != null && EventSystem.current.IsPointerOverGameObject())
            {
                return;
            }

            if (!TryGetPointerRay(out Ray ray))
            {
                return;
            }

            if (TryResolveUnitFromRay(ray, out UnitRuntime hitUnit, out Vector3 worldPoint))
            {
                if (IsSelectableByHuman(hitUnit))
                {
                    Select(hitUnit);
                }
                else if (_clearSelectionOnEmptyClick)
                {
                    ClearSelection();
                }

                return;
            }

            if (!TryResolveWorldPointOnGround(ray, out worldPoint))
            {
                return;
            }

            GridPosition grid = _gridManager.WorldToCell(worldPoint);
            if (!_gridManager.IsInside(grid))
            {
                if (_clearSelectionOnEmptyClick)
                {
                    ClearSelection();
                }

                return;
            }

            UnitRuntime occupant = _gridManager.GetOccupant(grid);
            if (IsSelectableByHuman(occupant))
            {
                Select(occupant);
            }
            else if (_clearSelectionOnEmptyClick)
            {
                ClearSelection();
            }
        }

        public void SetHumanSide(Owner humanSide)
        {
            _humanSide = humanSide;
            ValidateSelectedUnit();
            UpdateSelectionMarker();
        }

        public void SetManualInputEnabled(bool enabled)
        {
            _manualInputEnabled = enabled;
            if (!enabled)
            {
                ClearSelection();
            }
        }

        public void Select(UnitRuntime unit)
        {
            if (!IsSelectableByHuman(unit))
            {
                return;
            }

            if (SelectedUnit == unit)
            {
                return;
            }

            SelectedUnit = unit;
            OnSelectionChanged?.Invoke(SelectedUnit);
            UpdateSelectionMarker();
        }

        public void ClearSelection()
        {
            if (SelectedUnit == null)
            {
                return;
            }

            SelectedUnit = null;
            OnSelectionChanged?.Invoke(null);
            UpdateSelectionMarker();
        }

        private void ResolveReferences()
        {
            if (_selectionCamera == null)
            {
                _selectionCamera = Camera.main;
                if (_selectionCamera == null)
                {
                    _selectionCamera = FindFirstObjectByType<Camera>();
                }
            }

            if (_gridManager == null)
            {
                _gridManager = GridManager.Instance;
                if (_gridManager == null)
                {
                    _gridManager = FindFirstObjectByType<GridManager>();
                }
            }
        }

        private void ValidateSelectedUnit()
        {
            if (SelectedUnit == null)
            {
                return;
            }

            if (!IsSelectableByHuman(SelectedUnit))
            {
                ClearSelection();
            }
        }

        private bool IsSelectableByHuman(UnitRuntime unit)
        {
            return unit != null
                && unit.IsAlive
                && unit.Owner == _humanSide
                && _humanSide != Owner.Neutral;
        }

        private bool TryGetPointerRay(out Ray ray)
        {
            ray = default;
            if (_selectionCamera == null)
            {
                return false;
            }

#if ENABLE_INPUT_SYSTEM
            Mouse mouse = Mouse.current;
            if (mouse != null)
            {
                Vector2 pointer = mouse.position.ReadValue();
                ray = _selectionCamera.ScreenPointToRay(pointer);
                return true;
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER
            if (_legacyInputUnavailable)
            {
                return false;
            }

            try
            {
                ray = _selectionCamera.ScreenPointToRay(Input.mousePosition);
                return true;
            }
            catch (InvalidOperationException)
            {
                _legacyInputUnavailable = true;
                return false;
            }
#else
            return false;
#endif
        }

        private bool TryResolveUnitFromRay(Ray ray, out UnitRuntime unit, out Vector3 worldPoint)
        {
            worldPoint = default;
            unit = null;

            if (Physics.Raycast(ray, out RaycastHit hit, _raycastDistance, _raycastMask, QueryTriggerInteraction.Ignore))
            {
                worldPoint = hit.point;
                unit = hit.collider != null ? hit.collider.GetComponentInParent<UnitRuntime>() : null;
                return true;
            }

            return false;
        }

        private static bool TryResolveWorldPointOnGround(Ray ray, out Vector3 worldPoint)
        {
            Plane ground = new Plane(Vector3.up, Vector3.zero);
            if (ground.Raycast(ray, out float distance))
            {
                worldPoint = ray.GetPoint(distance);
                return true;
            }

            worldPoint = default;
            return false;
        }

        private bool IsLeftClickPressed()
        {
#if ENABLE_INPUT_SYSTEM
            Mouse mouse = Mouse.current;
            if (mouse != null)
            {
                return mouse.leftButton.wasPressedThisFrame;
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER
            if (_legacyInputUnavailable)
            {
                return false;
            }

            try
            {
                return Input.GetMouseButtonDown(0);
            }
            catch (InvalidOperationException)
            {
                _legacyInputUnavailable = true;
                return false;
            }
#else
            return false;
#endif
        }

        private void EnsureSelectionMarker()
        {
            if (_selectionMarker != null)
            {
                return;
            }

            _selectionMarker = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            _selectionMarker.name = "SelectionMarker";
            _selectionMarker.transform.SetParent(transform, false);
            _selectionMarker.transform.localScale = _markerScale;
            int ignoreRaycastLayer = LayerMask.NameToLayer("Ignore Raycast");
            if (ignoreRaycastLayer >= 0)
            {
                _selectionMarker.layer = ignoreRaycastLayer;
            }

            Collider markerCollider = _selectionMarker.GetComponent<Collider>();
            if (markerCollider != null)
            {
                markerCollider.enabled = false;
            }

            Renderer markerRenderer = _selectionMarker.GetComponent<Renderer>();
            if (markerRenderer != null)
            {
                Material markerMaterial = new Material(Shader.Find("Standard"));
                markerMaterial.color = _markerColor;
                markerRenderer.material = markerMaterial;
            }

            _selectionMarker.SetActive(false);
        }

        private void UpdateSelectionMarker()
        {
            if (_selectionMarker == null)
            {
                return;
            }

            if (SelectedUnit == null)
            {
                _selectionMarker.SetActive(false);
                return;
            }

            _selectionMarker.SetActive(true);
            Vector3 position = SelectedUnit.transform.position;
            position.y += _markerYOffset;
            _selectionMarker.transform.position = position;
        }

        private void OnDestroy()
        {
            if (_selectionMarker != null)
            {
                Destroy(_selectionMarker);
            }
        }

        private void Warn(string message)
        {
            if (_logWarnings)
            {
                Debug.LogWarning("[PlayerSelectionController] " + message);
            }
        }
    }
}
