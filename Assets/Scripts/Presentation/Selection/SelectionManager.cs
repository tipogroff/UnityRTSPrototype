using System;
using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

#if ENABLE_INPUT_SYSTEM
using UnityEngine.InputSystem;
#endif

namespace RTS.Presentation.Selection
{
    [DisallowMultipleComponent]
    public sealed class SelectionManager : MonoBehaviour
    {
        [Header("References")]
        [SerializeField] private Camera _selectionCamera;
        [SerializeField] private GridManager _gridManager;
        [SerializeField] private UnitRegistry _unitRegistry;
        [SerializeField] private SelectionBoxView _selectionBoxView;
        [SerializeField] private SelectionMarkerController _markerController;

        [Header("Raycast")]
        [SerializeField] private LayerMask _raycastMask = ~0;
        [SerializeField] private float _raycastDistance = 500f;
        [SerializeField] private float _dragThresholdPixels = 8f;
        [SerializeField] private bool _clearSelectionOnEmptyClick = true;

        private readonly List<UnitRuntime> _selectedUnits = new List<UnitRuntime>();
        private readonly List<UnitRuntime> _scratchUnits = new List<UnitRuntime>();
        private Owner _humanSide = Owner.Player2;
        private bool _manualInputEnabled;
        private bool _dragActive;
        private bool _dragStartedOverUi;
        private bool _legacyInputUnavailable;
        private Vector2 _dragStartScreen;
        private Vector2 _dragCurrentScreen;

        public IReadOnlyList<UnitRuntime> SelectedUnits => _selectedUnits;
        public UnitRuntime PrimarySelectedUnit => _selectedUnits.Count > 0 ? _selectedUnits[0] : null;
        public bool HasSelection => PrimarySelectedUnit != null;
        public bool HasMultiSelection => _selectedUnits.Count > 1;
        public Owner HumanSide => _humanSide;

        public event Action<IReadOnlyList<UnitRuntime>> OnSelectionChanged;

        private void Awake()
        {
            ResolveReferences();
            UpdatePresentation();
        }

        private void Update()
        {
            ResolveReferences();
            ValidateSelection();

            if (!_manualInputEnabled)
            {
                if (_dragActive)
                {
                    EndDrag(cancel: true);
                }

                return;
            }

            HandlePointerInput();
        }

        public void SelectSingle(UnitRuntime unit)
        {
            if (!IsSelectableByHuman(unit))
            {
                ClearSelection();
                return;
            }

            SetSelectionInternal(new[] { unit });
        }

        public void AddToSelection(UnitRuntime unit)
        {
            if (!IsSelectableByHuman(unit) || _selectedUnits.Contains(unit))
            {
                return;
            }

            if (!IsEligibleForMultiSelection(unit))
            {
                SelectSingle(unit);
                return;
            }

            RemoveBuildingsFromSelection();
            _selectedUnits.Add(unit);
            SortPrimaryFirst();
            NotifySelectionChanged();
        }

        public void RemoveFromSelection(UnitRuntime unit)
        {
            if (unit == null || !_selectedUnits.Remove(unit))
            {
                return;
            }

            NotifySelectionChanged();
        }

        public void ClearSelection()
        {
            if (_selectedUnits.Count == 0)
            {
                return;
            }

            _selectedUnits.Clear();
            NotifySelectionChanged();
        }

        public void SetSelection(IEnumerable<UnitRuntime> units)
        {
            SetSelectionInternal(units);
        }

        public void SetManualInputEnabled(bool enabled)
        {
            _manualInputEnabled = enabled;
            if (!enabled)
            {
                EndDrag(cancel: true);
                ClearSelection();
            }
        }

        public void SetHumanSide(Owner side)
        {
            _humanSide = side;
            ValidateSelection();
        }

        private void HandlePointerInput()
        {
            if (WasLeftMousePressed())
            {
                _dragStartedOverUi = IsPointerOverUi();
                if (_dragStartedOverUi || IsTextInputFocused())
                {
                    return;
                }

                _dragActive = true;
                _dragStartScreen = GetPointerPosition();
                _dragCurrentScreen = _dragStartScreen;
                HideSelectionBox();
                return;
            }

            if (!_dragActive)
            {
                return;
            }

            _dragCurrentScreen = GetPointerPosition();
            bool isDrag = IsCurrentDragAboveThreshold();
            if (IsLeftMouseHeld() && isDrag)
            {
                ShowSelectionBox(_dragStartScreen, _dragCurrentScreen);
            }

            if (WasLeftMouseReleased())
            {
                if (_dragStartedOverUi)
                {
                    EndDrag(cancel: true);
                    return;
                }

                if (isDrag)
                {
                    ApplyDragSelection(IsShiftHeld());
                }
                else
                {
                    ApplyClickSelection(IsShiftHeld());
                }

                EndDrag(cancel: true);
            }
        }

        private void ApplyClickSelection(bool additive)
        {
            if (!TryGetPointerRay(out Ray ray))
            {
                return;
            }

            UnitRuntime hitUnit = null;
            if (TryResolveUnitFromRay(ray, out UnitRuntime rayUnit, out Vector3 worldPoint))
            {
                hitUnit = rayUnit;
            }
            else if (TryResolveWorldPointOnGround(ray, out worldPoint) && _gridManager != null)
            {
                GridPosition cell = _gridManager.WorldToCell(worldPoint);
                if (_gridManager.IsInside(cell))
                {
                    hitUnit = _gridManager.GetOccupant(cell);
                }
            }

            if (IsSelectableByHuman(hitUnit))
            {
                if (additive)
                {
                    if (!IsEligibleForMultiSelection(hitUnit))
                    {
                        SelectSingle(hitUnit);
                        return;
                    }

                    if (_selectedUnits.Contains(hitUnit))
                    {
                        RemoveFromSelection(hitUnit);
                    }
                    else
                    {
                        AddToSelection(hitUnit);
                    }
                }
                else
                {
                    SelectSingle(hitUnit);
                }

                return;
            }

            if (!additive && _clearSelectionOnEmptyClick)
            {
                ClearSelection();
            }
        }

        private void ApplyDragSelection(bool additive)
        {
            if (_selectionCamera == null)
            {
                return;
            }

            Rect selectionRect = BuildScreenRect(_dragStartScreen, _dragCurrentScreen);
            _scratchUnits.Clear();
            foreach (UnitRuntime unit in EnumerateCandidateUnits())
            {
                if (!IsEligibleForMultiSelection(unit))
                {
                    continue;
                }

                Vector3 screenPoint = _selectionCamera.WorldToScreenPoint(unit.transform.position);
                if (screenPoint.z < 0f)
                {
                    continue;
                }

                if (selectionRect.Contains(new Vector2(screenPoint.x, screenPoint.y)))
                {
                    _scratchUnits.Add(unit);
                }
            }

            if (additive)
            {
                bool changed = RemoveBuildingsFromSelection();
                for (int i = 0; i < _scratchUnits.Count; i++)
                {
                    UnitRuntime unit = _scratchUnits[i];
                    if (_selectedUnits.Contains(unit))
                    {
                        continue;
                    }

                    _selectedUnits.Add(unit);
                    changed = true;
                }

                if (changed)
                {
                    SortPrimaryFirst();
                    NotifySelectionChanged();
                }

                return;
            }

            SetSelectionInternal(_scratchUnits);
        }

        private IEnumerable<UnitRuntime> EnumerateCandidateUnits()
        {
            ResolveReferences();
            if (_unitRegistry != null)
            {
                return _unitRegistry.GetUnitsByOwnerReadOnly(_humanSide);
            }

            return FindObjectsByType<UnitRuntime>(FindObjectsSortMode.InstanceID);
        }

        private void SetSelectionInternal(IEnumerable<UnitRuntime> units)
        {
            var incomingUnits = new List<UnitRuntime>();
            if (units != null)
            {
                foreach (UnitRuntime unit in units)
                {
                    if (unit != null && !incomingUnits.Contains(unit) && IsSelectableByHuman(unit))
                    {
                        incomingUnits.Add(unit);
                    }
                }
            }

            _selectedUnits.Clear();
            bool allowSingleBuilding = incomingUnits.Count == 1;
            for (int i = 0; i < incomingUnits.Count; i++)
            {
                UnitRuntime unit = incomingUnits[i];
                if (allowSingleBuilding || IsEligibleForMultiSelection(unit))
                {
                    _selectedUnits.Add(unit);
                }
            }

            SortPrimaryFirst();
            NotifySelectionChanged();
        }

        private void SortPrimaryFirst()
        {
            _selectedUnits.Sort(CompareSelectionPriority);
        }

        private static int CompareSelectionPriority(UnitRuntime left, UnitRuntime right)
        {
            if (left == right)
            {
                return 0;
            }

            if (left == null)
            {
                return 1;
            }

            if (right == null)
            {
                return -1;
            }

            int leftBuilding = left.IsBuilding ? 1 : 0;
            int rightBuilding = right.IsBuilding ? 1 : 0;
            if (leftBuilding != rightBuilding)
            {
                return leftBuilding.CompareTo(rightBuilding);
            }

            int type = left.Type.CompareTo(right.Type);
            if (type != 0)
            {
                return type;
            }

            int x = left.GridPos.X.CompareTo(right.GridPos.X);
            return x != 0 ? x : left.GridPos.Y.CompareTo(right.GridPos.Y);
        }

        private void ValidateSelection()
        {
            bool changed = false;
            for (int i = _selectedUnits.Count - 1; i >= 0; i--)
            {
                if (!IsSelectableByHuman(_selectedUnits[i]))
                {
                    _selectedUnits.RemoveAt(i);
                    changed = true;
                }
            }

            if (changed)
            {
                SortPrimaryFirst();
                NotifySelectionChanged();
            }
            else
            {
                UpdatePresentation();
            }
        }

        private bool IsSelectableByHuman(UnitRuntime unit)
        {
            return unit != null
                && unit.gameObject.activeInHierarchy
                && unit.IsAlive
                && _humanSide != Owner.Neutral
                && unit.Owner == _humanSide
                && unit.Type != UnitType.Resource;
        }

        private bool IsEligibleForMultiSelection(UnitRuntime unit)
        {
            return IsSelectableByHuman(unit) && !unit.IsBuilding;
        }

        private bool RemoveBuildingsFromSelection()
        {
            bool changed = false;
            for (int i = _selectedUnits.Count - 1; i >= 0; i--)
            {
                if (_selectedUnits[i] != null && _selectedUnits[i].IsBuilding)
                {
                    _selectedUnits.RemoveAt(i);
                    changed = true;
                }
            }

            return changed;
        }

        private void ResolveReferences()
        {
            if (_selectionCamera == null)
            {
                _selectionCamera = Camera.main != null ? Camera.main : FindFirstObjectByType<Camera>();
            }

            if (_gridManager == null)
            {
                _gridManager = GridManager.Instance != null ? GridManager.Instance : FindFirstObjectByType<GridManager>();
            }

            if (_unitRegistry == null)
            {
                _unitRegistry = UnitRegistry.Instance != null ? UnitRegistry.Instance : FindFirstObjectByType<UnitRegistry>();
            }

            if (_markerController == null)
            {
                _markerController = GetComponent<SelectionMarkerController>();
                if (_markerController == null)
                {
                    _markerController = gameObject.AddComponent<SelectionMarkerController>();
                }
            }
        }

        public void SetSelectionBoxView(SelectionBoxView selectionBoxView)
        {
            _selectionBoxView = selectionBoxView;
        }

        public void ClearSelectionBoxView(SelectionBoxView selectionBoxView)
        {
            if (_selectionBoxView == null || _selectionBoxView == selectionBoxView)
            {
                _selectionBoxView = null;
            }
        }

        private void NotifySelectionChanged()
        {
            UpdatePresentation();
            OnSelectionChanged?.Invoke(_selectedUnits);
        }

        private void UpdatePresentation()
        {
            _markerController?.SetSelection(_selectedUnits, PrimarySelectedUnit);
        }

        private bool TryGetPointerRay(out Ray ray)
        {
            ray = default;
            if (_selectionCamera == null)
            {
                return false;
            }

            ray = _selectionCamera.ScreenPointToRay(GetPointerPosition());
            return true;
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

        private bool IsCurrentDragAboveThreshold()
        {
            return (_dragCurrentScreen - _dragStartScreen).sqrMagnitude >= _dragThresholdPixels * _dragThresholdPixels;
        }

        private void EndDrag(bool cancel)
        {
            _dragActive = false;
            _dragStartedOverUi = false;
            HideSelectionBox();
        }

        private void ShowSelectionBox(Vector2 startScreen, Vector2 currentScreen)
        {
            if (_selectionBoxView == null)
            {
                _selectionBoxView = null;
                return;
            }

            _selectionBoxView.Show(startScreen, currentScreen);
        }

        private void HideSelectionBox()
        {
            if (_selectionBoxView == null)
            {
                _selectionBoxView = null;
                return;
            }

            _selectionBoxView.Hide();
        }

        private static Rect BuildScreenRect(Vector2 a, Vector2 b)
        {
            Vector2 min = Vector2.Min(a, b);
            Vector2 max = Vector2.Max(a, b);
            return Rect.MinMaxRect(min.x, min.y, max.x, max.y);
        }

        private static bool IsPointerOverUi()
        {
            return EventSystem.current != null && EventSystem.current.IsPointerOverGameObject();
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

        private bool WasLeftMousePressed()
        {
#if ENABLE_INPUT_SYSTEM
            Mouse mouse = Mouse.current;
            if (mouse != null)
            {
                return mouse.leftButton.wasPressedThisFrame;
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER && !ENABLE_INPUT_SYSTEM
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

        private bool IsLeftMouseHeld()
        {
#if ENABLE_INPUT_SYSTEM
            Mouse mouse = Mouse.current;
            if (mouse != null)
            {
                return mouse.leftButton.isPressed;
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER && !ENABLE_INPUT_SYSTEM
            return Input.GetMouseButton(0);
#else
            return false;
#endif
        }

        private bool WasLeftMouseReleased()
        {
#if ENABLE_INPUT_SYSTEM
            Mouse mouse = Mouse.current;
            if (mouse != null)
            {
                return mouse.leftButton.wasReleasedThisFrame;
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER && !ENABLE_INPUT_SYSTEM
            return Input.GetMouseButtonUp(0);
#else
            return false;
#endif
        }

        private static bool IsShiftHeld()
        {
#if ENABLE_INPUT_SYSTEM
            Keyboard keyboard = Keyboard.current;
            if (keyboard != null)
            {
                return keyboard.leftShiftKey.isPressed || keyboard.rightShiftKey.isPressed;
            }
#endif

#if ENABLE_LEGACY_INPUT_MANAGER && !ENABLE_INPUT_SYSTEM
            return Input.GetKey(KeyCode.LeftShift) || Input.GetKey(KeyCode.RightShift);
#else
            return false;
#endif
        }
    }
}
