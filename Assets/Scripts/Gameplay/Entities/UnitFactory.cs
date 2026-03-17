// UnitFactory.cs — единый путь создания живых юнитов в сцене.
// Неделя 2, Этап 2 (Игровые сущности).

using UnityEngine;
using RTS.Core;

namespace RTS.Gameplay
{
    /// <summary>
    /// Фабрика создаёт UnitRuntime + UnitModel и регистрирует юнита в GridManager.
    ///
    /// Это инфраструктурный сервис спавна.
    /// Не содержит боевой логики и логики матча.
    /// </summary>
    public class UnitFactory
    {
        private readonly GameConfig _config;
        private readonly GridManager _gridManager;
        private readonly UnitRegistry _unitRegistry;
        private readonly Transform _parent;

        public UnitFactory(GameConfig config, GridManager gridManager, Transform parent = null, UnitRegistry unitRegistry = null)
        {
            _config = config;
            _gridManager = gridManager;
            _parent = parent;
            _unitRegistry = unitRegistry ?? UnitRegistry.Instance;
        }

        /// <summary>
        /// Создаёт юнита заданного типа и владельца в клетке pos.
        /// Возвращает созданный UnitRuntime или null при неуспехе.
        /// </summary>
        public UnitRuntime Spawn(UnitType type, Owner owner, GridPosition pos)
        {
            if (_config == null)
            {
                Debug.LogError("[UnitFactory] Spawn: GameConfig is null.");
                return null;
            }
            if (_gridManager == null)
            {
                Debug.LogError("[UnitFactory] Spawn: GridManager is null.");
                return null;
            }
            if (!_gridManager.IsInside(pos))
            {
                Debug.LogWarning($"[UnitFactory] Spawn: позиция {pos} вне карты ({owner}.{type}).");
                return null;
            }
            if (_gridManager.IsCellOccupied(pos))
            {
                Debug.LogWarning($"[UnitFactory] Spawn: клетка {pos} занята ({owner}.{type}).");
                return null;
            }

            var definition = _config.GetDefinition(type);
            if (definition == null)
            {
                Debug.LogWarning($"[UnitFactory] Spawn: UnitDefinition для {type} не назначен в GameConfig.");
                return null;
            }

            GameObject go;
            if (definition.prefab != null)
            {
                go = Object.Instantiate(
                    definition.prefab,
                    _gridManager.CellToWorld(pos),
                    Quaternion.identity,
                    _parent);
            }
            else
            {
                go = new GameObject();
                if (_parent != null) go.transform.SetParent(_parent);
                go.transform.position = _gridManager.CellToWorld(pos);
            }

            var unit = go.GetComponent<UnitRuntime>();
            if (unit == null)
                unit = go.AddComponent<UnitRuntime>();

            unit.Init(definition, owner, pos);

            if (!_gridManager.TryPlaceUnit(unit, pos))
            {
                Object.Destroy(go);
                return null;
            }

            _unitRegistry?.Register(unit);

            return unit;
        }
    }
}
