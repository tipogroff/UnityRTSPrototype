// GridManager.cs — единственный источник истины о состоянии карты 24×24.
// Неделя 2, Этап 1.
// Управляет occupancy-таблицей, переводом координат и навигацией соседей.

using System.Collections.Generic;
using UnityEngine;
using RTS.Core;

namespace RTS.Gameplay
{
    /// <summary>
    /// Singleton MonoBehaviour.
    /// Хранит двумерную карту занятости и предоставляет единый API для:
    /// — спавна и перемещения юнитов;
    /// — проверки свободных клеток;
    /// — перевода клеточных координат в мировые.
    ///
    /// Размер карты берётся из <see cref="GameConfig"/> (если назначен),
    /// иначе из <see cref="GameConstants"/>.
    /// </summary>
    public class GridManager : MonoBehaviour
    {
        // ── Singleton ─────────────────────────────────────────────────────────

        public static GridManager Instance { get; private set; }

        // ── Inspector ─────────────────────────────────────────────────────────

        [Header("Конфигурация")]
        [Tooltip("Эталонный сценарий. Если null — используются GameConstants.")]
        [SerializeField] private GameConfig config;

        // ── Состояние ─────────────────────────────────────────────────────────

        private int _width;
        private int _height;

        // Основное хранилище занятости: ключ = клетка, значение = занявший её юнит.
        private Dictionary<GridPosition, UnitRuntime> _occupancy;

        // ── Unity lifecycle ───────────────────────────────────────────────────

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Debug.LogWarning("[GridManager] Обнаружен дубликат. Уничтожаем лишний.");
                Destroy(gameObject);
                return;
            }
            Instance = this;
            InitGrid();
        }

        private void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        // ── Инициализация / сброс ─────────────────────────────────────────────

        /// <summary>
        /// Создаёт (или пересоздаёт) пустую occupancy-таблицу.
        /// Вызывается из <see cref="Awake"/> и из EpisodeManager.ResetEpisode.
        /// </summary>
        public void InitGrid()
        {
            _width  = config != null ? config.mapWidth  : GameConstants.MapWidth;
            _height = config != null ? config.mapHeight : GameConstants.MapHeight;
            _occupancy = new Dictionary<GridPosition, UnitRuntime>(_width * _height);
        }

        /// <summary>
        /// Альтернативная инициализация с явными размерами (для тестов).
        /// </summary>
        public void InitGrid(int width, int height)
        {
            _width  = width;
            _height = height;
            _occupancy = new Dictionary<GridPosition, UnitRuntime>(_width * _height);
        }

        // ── Базовые запросы ───────────────────────────────────────────────────

        /// <summary>Ширина карты в клетках.</summary>
        public int Width  => _width;

        /// <summary>Высота карты в клетках.</summary>
        public int Height => _height;

        /// <summary>
        /// True, если позиция находится внутри границ карты.
        /// </summary>
        public bool IsInside(GridPosition pos)
            => pos.IsInsideMap(_width, _height);

        /// <summary>True, если клетка занята каким-либо юнитом.</summary>
        public bool IsCellOccupied(GridPosition pos)
        {
            EnsureGridStorageInitialized();
            return _occupancy.ContainsKey(pos);
        }

        /// <summary>
        /// True, если клетка находится внутри карты И свободна.
        /// Удобная комбинация для проверки перед Move.
        /// </summary>
        public bool IsWalkable(GridPosition pos)
            => IsInside(pos) && !IsCellOccupied(pos);

        /// <summary>
        /// Возвращает юнита, занимающего клетку, или null.
        /// </summary>
        public UnitRuntime GetOccupant(GridPosition pos)
        {
            EnsureGridStorageInitialized();
            _occupancy.TryGetValue(pos, out var unit);
            return unit;
        }

        /// <summary>
        /// Пытается получить юнита, занимающего клетку.
        /// </summary>
        public bool TryGetOccupant(GridPosition pos, out UnitRuntime unit)
        {
            EnsureGridStorageInitialized();
            return _occupancy.TryGetValue(pos, out unit);
        }

        // ── Размещение и перемещение ──────────────────────────────────────────

        /// <summary>
        /// Помещает юнита на позицию <paramref name="pos"/>.
        /// Возвращает false, если позиция вне карты или занята.
        /// При успехе обновляет <see cref="UnitRuntime.GridPos"/>.
        /// </summary>
        public bool TryPlaceUnit(UnitRuntime unit, GridPosition pos)
        {
            EnsureGridStorageInitialized();

            if (unit == null)
            {
                Debug.LogError("[GridManager] TryPlaceUnit: unit == null");
                return false;
            }
            if (!IsInside(pos))
            {
                Debug.LogWarning($"[GridManager] TryPlaceUnit: позиция {pos} вне карты.");
                return false;
            }
            if (IsCellOccupied(pos))
            {
                Debug.LogWarning($"[GridManager] TryPlaceUnit: клетка {pos} занята {_occupancy[pos]}.");
                return false;
            }

            _occupancy[pos] = unit;
            unit.GridPos = pos;
            return true;
        }

        /// <summary>
        /// Удаляет юнита из occupancy-таблицы (напр., после гибели).
        /// Не уничтожает GameObject — это ответственность вызывающей системы.
        /// </summary>
        public void RemoveUnit(GridPosition pos)
        {
            EnsureGridStorageInitialized();

            if (!_occupancy.Remove(pos))
                Debug.LogWarning($"[GridManager] RemoveUnit: клетка {pos} не была занята.");
        }

        /// <summary>
        /// Перемещает юнита из <paramref name="from"/> в <paramref name="to"/>.
        /// Обновляет occupancy-таблицу и <see cref="UnitRuntime.GridPos"/>.
        ///
        /// Логирует ошибку (но не бросает исключение) если:
        /// — <paramref name="to"/> вне карты;
        /// — <paramref name="to"/> уже занята;
        /// — в <paramref name="from"/> нет этого юнита.
        /// </summary>
        public void MoveUnit(UnitRuntime unit, GridPosition from, GridPosition to)
        {
            EnsureGridStorageInitialized();

            if (unit == null)
            {
                Debug.LogError("[GridManager] MoveUnit: unit == null");
                return;
            }
            if (!IsInside(to))
            {
                Debug.LogError($"[GridManager] MoveUnit: цель {to} вне карты.");
                return;
            }
            if (IsCellOccupied(to))
            {
                Debug.LogError($"[GridManager] MoveUnit: клетка {to} занята {_occupancy[to]}.");
                return;
            }
            if (!_occupancy.TryGetValue(from, out var registered) || registered != unit)
            {
                Debug.LogError(
                    $"[GridManager] MoveUnit: в клетке {from} зарегистрирован другой юнит " +
                    $"(ожидался {unit}, найден {registered}).");
                return;
            }

            _occupancy.Remove(from);
            _occupancy[to] = unit;
            unit.GridPos = to;
        }

        private void EnsureGridStorageInitialized()
        {
            if (_occupancy != null)
            {
                return;
            }

            _width = _width > 0 ? _width : (config != null ? config.mapWidth : GameConstants.MapWidth);
            _height = _height > 0 ? _height : (config != null ? config.mapHeight : GameConstants.MapHeight);
            _occupancy = new Dictionary<GridPosition, UnitRuntime>(_width * _height);
        }

        // ── Перевод координат ─────────────────────────────────────────────────

        /// <summary>
        /// Переводит клетку в мировую позицию Unity (центр клетки, Y=0).
        /// </summary>
        public Vector3 CellToWorld(GridPosition pos)
            => pos.ToWorldPosition();

        /// <summary>
        /// Переводит мировую позицию Unity в ближайшую клетку сетки.
        /// </summary>
        public GridPosition WorldToCell(Vector3 world)
            => GridPosition.FromWorldPosition(world);

        // ── Навигация ─────────────────────────────────────────────────────────

        /// <summary>
        /// Возвращает соседнюю клетку в заданном направлении.
        /// Не проверяет, находится ли сосед внутри карты — проверяйте IsInside отдельно.
        /// </summary>
        public GridPosition GetNeighbour(GridPosition pos, Direction dir)
            => pos.Neighbour(dir);

        /// <summary>
        /// Возвращает список всех существующих (IsInside) соседей клетки
        /// по четырём направлениям NESW.
        /// </summary>
        public List<GridPosition> GetValidNeighbours(GridPosition pos)
        {
            var result = new List<GridPosition>(4);
            foreach (Direction dir in System.Enum.GetValues(typeof(Direction)))
            {
                var n = pos.Neighbour(dir);
                if (IsInside(n)) result.Add(n);
            }
            return result;
        }

        // ── Только чтение occupancy (для логгирования / ML-наблюдений) ────────

        /// <summary>
        /// Read-only вид таблицы занятости.
        /// Используется ObservationBuilder и ExperimentLogger.
        /// </summary>
        public IReadOnlyDictionary<GridPosition, UnitRuntime> Occupancy => _occupancy;

        // ── Отладочная визуализация ────────────────────────────────────────────

#if UNITY_EDITOR
        private void OnDrawGizmosSelected()
        {
            int w = config != null ? config.mapWidth  : GameConstants.MapWidth;
            int h = config != null ? config.mapHeight : GameConstants.MapHeight;

            float cs = GameConstants.CellSize;

            Gizmos.color = new Color(0.3f, 0.8f, 0.3f, 0.25f);
            for (int x = 0; x < w; x++)
            for (int y = 0; y < h; y++)
            {
                var center = new GridPosition(x, y).ToWorldPosition();
                Gizmos.DrawWireCube(center, new Vector3(cs, 0.02f, cs));
            }
        }
#endif
    }
}
