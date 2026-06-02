using System;
using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using RTS.Presentation.Selection;
using UnityEngine;

namespace RTS.Presentation
{
    [DisallowMultipleComponent]
    public sealed class PlayerSelectionController : MonoBehaviour
    {
        [Header("Compatibility Facade")]
        [SerializeField] private SelectionManager _selectionManager;

        private static readonly IReadOnlyList<UnitRuntime> EmptySelection = Array.Empty<UnitRuntime>();

        public UnitRuntime SelectedUnit => PrimarySelectedUnit;
        public UnitRuntime PrimarySelectedUnit => _selectionManager != null ? _selectionManager.PrimarySelectedUnit : null;
        public IReadOnlyList<UnitRuntime> SelectedUnits => _selectionManager != null ? _selectionManager.SelectedUnits : EmptySelection;
        public bool HasSelection => _selectionManager != null && _selectionManager.HasSelection;
        public bool HasMultiSelection => _selectionManager != null && _selectionManager.HasMultiSelection;
        public Owner HumanSide => _selectionManager != null ? _selectionManager.HumanSide : Owner.Neutral;

        public event Action<UnitRuntime> OnSelectionChanged;
        public event Action<IReadOnlyList<UnitRuntime>> OnSelectionListChanged;

        private void Awake()
        {
            ResolveSelectionManager();
        }

        private void OnEnable()
        {
            ResolveSelectionManager();
            Subscribe();
        }

        private void OnDisable()
        {
            Unsubscribe();
        }

        public void SetHumanSide(Owner humanSide)
        {
            ResolveSelectionManager();
            _selectionManager?.SetHumanSide(humanSide);
        }

        public void SetManualInputEnabled(bool enabled)
        {
            ResolveSelectionManager();
            _selectionManager?.SetManualInputEnabled(enabled);
        }

        public void Select(UnitRuntime unit)
        {
            SelectSingle(unit);
        }

        public void SelectSingle(UnitRuntime unit)
        {
            ResolveSelectionManager();
            _selectionManager?.SelectSingle(unit);
        }

        public void AddToSelection(UnitRuntime unit)
        {
            ResolveSelectionManager();
            _selectionManager?.AddToSelection(unit);
        }

        public void RemoveFromSelection(UnitRuntime unit)
        {
            ResolveSelectionManager();
            _selectionManager?.RemoveFromSelection(unit);
        }

        public void ClearSelection()
        {
            ResolveSelectionManager();
            _selectionManager?.ClearSelection();
        }

        public void SetSelection(IEnumerable<UnitRuntime> units)
        {
            ResolveSelectionManager();
            _selectionManager?.SetSelection(units);
        }

        private void ResolveSelectionManager()
        {
            if (_selectionManager == null)
            {
                _selectionManager = GetComponent<SelectionManager>();
            }

            if (_selectionManager == null)
            {
                _selectionManager = FindFirstObjectByType<SelectionManager>();
            }

            if (_selectionManager == null)
            {
                _selectionManager = gameObject.AddComponent<SelectionManager>();
            }
        }

        private void Subscribe()
        {
            if (_selectionManager == null)
            {
                return;
            }

            _selectionManager.OnSelectionChanged -= HandleSelectionChanged;
            _selectionManager.OnSelectionChanged += HandleSelectionChanged;
        }

        private void Unsubscribe()
        {
            if (_selectionManager == null)
            {
                return;
            }

            _selectionManager.OnSelectionChanged -= HandleSelectionChanged;
        }

        private void HandleSelectionChanged(IReadOnlyList<UnitRuntime> selectedUnits)
        {
            OnSelectionChanged?.Invoke(PrimarySelectedUnit);
            OnSelectionListChanged?.Invoke(selectedUnits);
        }
    }
}
