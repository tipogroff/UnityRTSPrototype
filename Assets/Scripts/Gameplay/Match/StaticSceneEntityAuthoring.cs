using RTS.Core;
using UnityEngine;

namespace RTS.Gameplay
{
    public enum StaticSceneEntityKind
    {
        Unit = 0,
        Resource = 1,
    }

    [DisallowMultipleComponent]
    public sealed class StaticSceneEntityAuthoring : MonoBehaviour
    {
        [SerializeField] private StaticSceneEntityKind _entityKind = StaticSceneEntityKind.Unit;
        [SerializeField] private UnitType _unitType = UnitType.Worker;
        [SerializeField] private Owner _owner = Owner.Player1;
        [SerializeField] private int _gridX;
        [SerializeField] private int _gridY;
        [Min(1)]
        [SerializeField] private int _resourceAmount = GameConstants.MaxResourcesPerPatch;

        public StaticSceneEntityKind EntityKind => _entityKind;
        public UnitType UnitType => _unitType;
        public Owner Owner => _owner;
        public int ResourceAmount => Mathf.Max(1, _resourceAmount);

        public GridPosition GetGridPosition()
        {
            return GridPosition.FromWorldPosition(transform.position);
        }

        public void CaptureGridFromWorld()
        {
            GridPosition gridPosition = GetGridPosition();
            _gridX = gridPosition.X;
            _gridY = gridPosition.Y;
        }

        public void Configure(StaticSceneEntityKind entityKind, UnitType unitType, Owner owner, GridPosition gridPosition, int resourceAmount)
        {
            _entityKind = entityKind;
            _unitType = unitType;
            _owner = owner;
            _gridX = gridPosition.X;
            _gridY = gridPosition.Y;
            _resourceAmount = Mathf.Max(1, resourceAmount);
            ApplyWorldFromGrid();
        }

        public void ApplyWorldFromGrid()
        {
            transform.position = new GridPosition(_gridX, _gridY).ToWorldPosition();
        }

#if UNITY_EDITOR
        private void OnValidate()
        {
            if (_entityKind == StaticSceneEntityKind.Resource)
            {
                _unitType = UnitType.Resource;
            }

            if (!Application.isPlaying)
            {
                CaptureGridFromWorld();
            }
        }
#endif
    }
}
