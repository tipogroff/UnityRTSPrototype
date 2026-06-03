// UnitRegistry.cs — единый реестр активных юнитов матча.
// Неделя 2, Этап 2 (Игровые сущности).

using System.Collections.Generic;
using UnityEngine;
using RTS.Core;
using Unity.Profiling;

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
        private readonly List<UnitRuntime> _snapshot = new List<UnitRuntime>(128);
        private readonly List<UnitRuntime> _player1Units = new List<UnitRuntime>(64);
        private readonly List<UnitRuntime> _player2Units = new List<UnitRuntime>(64);
        private readonly List<UnitRuntime> _neutralUnits = new List<UnitRuntime>(64);
        private readonly List<UnitRuntime> _player1Buildings = new List<UnitRuntime>(16);
        private readonly List<UnitRuntime> _player2Buildings = new List<UnitRuntime>(16);
        private readonly List<UnitRuntime> _neutralBuildings = new List<UnitRuntime>(16);
        private bool _dirty = true;

        private static readonly ProfilerMarker GetAllUnitsMarker = new ProfilerMarker("UnitRegistry.GetAllUnits");
        private static readonly ProfilerMarker RebuildCacheMarker = new ProfilerMarker("UnitRegistry.RebuildCache");

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
            if (_units.Add(unit))
            {
                _dirty = true;
            }
        }

        /// <summary>
        /// Удаляет юнита из активного списка.
        /// </summary>
        public void Unregister(UnitRuntime unit)
        {
            if (unit == null) return;
            if (_units.Remove(unit))
            {
                _dirty = true;
            }
        }

        /// <summary>
        /// Возвращает снимок всех активных юнитов.
        /// </summary>
        public List<UnitRuntime> GetAllUnits()
        {
            using (GetAllUnitsMarker.Auto())
            {
                EnsureCache();
                return new List<UnitRuntime>(_snapshot);
            }
        }

        public IReadOnlyList<UnitRuntime> GetAllUnitsReadOnly()
        {
            using (GetAllUnitsMarker.Auto())
            {
                EnsureCache();
                return _snapshot;
            }
        }

        public int UnitCount
        {
            get
            {
                EnsureCache();
                return _snapshot.Count;
            }
        }

        /// <summary>
        /// Возвращает юнитов конкретного владельца.
        /// </summary>
        public List<UnitRuntime> GetUnitsByOwner(Owner owner)
        {
            IReadOnlyList<UnitRuntime> source = GetUnitsByOwnerReadOnly(owner);
            return new List<UnitRuntime>(source);
        }

        public IReadOnlyList<UnitRuntime> GetUnitsByOwnerReadOnly(Owner owner)
        {
            EnsureCache();
            switch (owner)
            {
                case Owner.Player1:
                    return _player1Units;
                case Owner.Player2:
                    return _player2Units;
                default:
                    return _neutralUnits;
            }
        }

        /// <summary>
        /// Возвращает строения конкретного владельца.
        /// Критерий строения берётся из UnitModel.IsBuilding.
        /// </summary>
        public List<UnitRuntime> GetBuildingsByOwner(Owner owner)
        {
            IReadOnlyList<UnitRuntime> source = GetBuildingsByOwnerReadOnly(owner);
            return new List<UnitRuntime>(source);
        }

        public IReadOnlyList<UnitRuntime> GetBuildingsByOwnerReadOnly(Owner owner)
        {
            EnsureCache();
            switch (owner)
            {
                case Owner.Player1:
                    return _player1Buildings;
                case Owner.Player2:
                    return _player2Buildings;
                default:
                    return _neutralBuildings;
            }
        }

        private void EnsureCache()
        {
            if (!_dirty)
            {
                return;
            }

            using (RebuildCacheMarker.Auto())
            {
                CleanupNulls();
                _snapshot.Clear();
                _player1Units.Clear();
                _player2Units.Clear();
                _neutralUnits.Clear();
                _player1Buildings.Clear();
                _player2Buildings.Clear();
                _neutralBuildings.Clear();

                foreach (UnitRuntime unit in _units)
                {
                    if (unit == null)
                    {
                        continue;
                    }

                    _snapshot.Add(unit);
                    List<UnitRuntime> ownerUnits = unit.Owner == Owner.Player1
                        ? _player1Units
                        : unit.Owner == Owner.Player2 ? _player2Units : _neutralUnits;
                    ownerUnits.Add(unit);

                    if (!unit.IsBuilding)
                    {
                        continue;
                    }

                    List<UnitRuntime> ownerBuildings = unit.Owner == Owner.Player1
                        ? _player1Buildings
                        : unit.Owner == Owner.Player2 ? _player2Buildings : _neutralBuildings;
                    ownerBuildings.Add(unit);
                }

                _dirty = false;
            }
        }

        private void CleanupNulls()
        {
            // После Destroy Unity-перегрузка оставляет "fake null" ссылки,
            // поэтому чистим перед выдачей выборок.
            if (_units.RemoveWhere(u => u == null) > 0)
            {
                _dirty = true;
            }
        }
        /// <summary>
        /// Очищает реестр (вызывается при reset эпизода).
        /// </summary>
        public void Clear()
        {
            _units.Clear();
            _dirty = true;
        }
    }
}
