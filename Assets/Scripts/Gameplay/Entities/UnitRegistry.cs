// UnitRegistry.cs — единый реестр активных юнитов матча.
// Неделя 2, Этап 2 (Игровые сущности).

using System.Collections.Generic;
using UnityEngine;
using RTS.Core;

namespace RTS.Gameplay
{
    /// <summary>
    /// Хранит все активные UnitRuntime в текущем матче.
    ///
    /// Используется в системах:
    /// - победа/поражение (наличие ключевых юнитов);
    /// - бой (поиск целей);
    /// - сбор статистики и логирование.
    /// </summary>
    [DisallowMultipleComponent]
    public class UnitRegistry : MonoBehaviour
    {
        public static UnitRegistry Instance { get; private set; }

        private readonly HashSet<UnitRuntime> _units = new HashSet<UnitRuntime>();

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Debug.LogWarning("[UnitRegistry] Обнаружен дубликат. Уничтожаем лишний.");
                Destroy(gameObject);
                return;
            }

            Instance = this;
        }

        private void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        /// <summary>
        /// Регистрирует юнита в активном списке.
        /// </summary>
        public void Register(UnitRuntime unit)
        {
            if (unit == null) return;
            _units.Add(unit);
        }

        /// <summary>
        /// Удаляет юнита из активного списка.
        /// </summary>
        public void Unregister(UnitRuntime unit)
        {
            if (unit == null) return;
            _units.Remove(unit);
        }

        /// <summary>
        /// Возвращает снимок всех активных юнитов.
        /// </summary>
        public List<UnitRuntime> GetAllUnits()
        {
            CleanupNulls();
            return new List<UnitRuntime>(_units);
        }

        /// <summary>
        /// Возвращает юнитов конкретного владельца.
        /// </summary>
        public List<UnitRuntime> GetUnitsByOwner(Owner owner)
        {
            CleanupNulls();
            var result = new List<UnitRuntime>();
            foreach (var unit in _units)
            {
                if (unit.Owner == owner)
                    result.Add(unit);
            }
            return result;
        }

        /// <summary>
        /// Возвращает строения конкретного владельца.
        /// Критерий строения берётся из UnitModel.IsBuilding.
        /// </summary>
        public List<UnitRuntime> GetBuildingsByOwner(Owner owner)
        {
            CleanupNulls();
            var result = new List<UnitRuntime>();
            foreach (var unit in _units)
            {
                if (unit.Owner == owner && unit.IsBuilding)
                    result.Add(unit);
            }
            return result;
        }

        private void CleanupNulls()
        {
            // После Destroy Unity-перегрузка оставляет "fake null" ссылки,
            // поэтому чистим перед выдачей выборок.
            _units.RemoveWhere(u => u == null);
        }
    }
}
