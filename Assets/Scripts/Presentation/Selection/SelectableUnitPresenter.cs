using RTS.Gameplay;
using UnityEngine;

namespace RTS.Presentation.Selection
{
    [DisallowMultipleComponent]
    public sealed class SelectableUnitPresenter : MonoBehaviour
    {
        public UnitRuntime Runtime { get; private set; }
        public bool IsSelected { get; private set; }
        public bool IsPrimarySelection { get; private set; }

        private void Awake()
        {
            Runtime = GetComponent<UnitRuntime>();
        }

        public void SetSelectionState(bool selected, bool primary)
        {
            IsSelected = selected;
            IsPrimarySelection = selected && primary;
        }
    }
}
