// GridPosition.cs — единый тип координат клетки карты.
// Неделя 2, Этап 1.
// Заменяет хаотичное использование Vector2Int / Vector3 в игровой логике.

using System;
using UnityEngine;
using RTS.Core;

namespace RTS.Gameplay
{
    /// <summary>
    /// Целочисленные координаты клетки карты.
    /// Используется как единственный тип адресации во всех игровых системах:
    /// спавн, движение, атака, сбор ресурсов, наблюдения.
    ///
    /// Является readonly struct — нет аллокаций на хипе, value semantics.
    /// </summary>
    [Serializable]
    public readonly struct GridPosition : IEquatable<GridPosition>
    {
        public readonly int X;
        public readonly int Y;

        // ── Конструктор ──────────────────────────────────────────────────────

        public GridPosition(int x, int y)
        {
            X = x;
            Y = y;
        }

        // ── Статические константы ────────────────────────────────────────────

        /// <summary>Начало координат (0, 0).</summary>
        public static readonly GridPosition Zero = new GridPosition(0, 0);

        // ── Валидация ────────────────────────────────────────────────────────

        /// <summary>
        /// Проверяет, что координата находится внутри карты.
        /// Использует размеры из GameConstants, не требует передачи параметров.
        /// </summary>
        public bool IsInsideMap()
            => X >= 0 && X < GameConstants.MapWidth
            && Y >= 0 && Y < GameConstants.MapHeight;

        /// <summary>
        /// Проверяет, что координата находится внутри карты с явными размерами.
        /// Используется в тестах и в случаях, когда размер карты известен явно.
        /// </summary>
        public bool IsInsideMap(int width, int height)
            => X >= 0 && X < width
            && Y >= 0 && Y < height;

        // ── Конвертация координат ────────────────────────────────────────────

        /// <summary>
        /// Переводит клетку в мировую позицию Unity.
        /// Центр клетки: X * CellSize, 0, Y * CellSize.
        /// </summary>
        public Vector3 ToWorldPosition()
            => new Vector3(X * GameConstants.CellSize, 0f, Y * GameConstants.CellSize);

        /// <summary>
        /// Переводит мировую позицию Unity в ближайшую клетку сетки.
        /// Игнорирует ось Y (высота).
        /// </summary>
        public static GridPosition FromWorldPosition(Vector3 world)
            => new GridPosition(
                Mathf.RoundToInt(world.x / GameConstants.CellSize),
                Mathf.RoundToInt(world.z / GameConstants.CellSize));

        /// <summary>Создаёт GridPosition из Vector2Int (x→X, y→Y).</summary>
        public static GridPosition FromVector2Int(Vector2Int v)
            => new GridPosition(v.x, v.y);

        /// <summary>Возвращает Vector2Int (X, Y).</summary>
        public Vector2Int ToVector2Int()
            => new Vector2Int(X, Y);

        // ── Соседи и смещения ────────────────────────────────────────────────

        /// <summary>
        /// Возвращает соседнюю клетку в заданном направлении.
        /// North — +Y, South — -Y, East — +X, West — -X.
        /// </summary>
        public GridPosition Neighbour(Direction direction)
        {
            return direction switch
            {
                Direction.North => new GridPosition(X,     Y + 1),
                Direction.East  => new GridPosition(X + 1, Y),
                Direction.South => new GridPosition(X,     Y - 1),
                Direction.West  => new GridPosition(X - 1, Y),
                _               => this
            };
        }

        /// <summary>Применяет смещение (dx, dy) и возвращает новую позицию.</summary>
        public GridPosition Offset(int dx, int dy)
            => new GridPosition(X + dx, Y + dy);

        // ── Расстояния ───────────────────────────────────────────────────────

        /// <summary>Манхэттенское расстояние между двумя клетками.</summary>
        public int ManhattanDistance(GridPosition other)
            => Math.Abs(X - other.X) + Math.Abs(Y - other.Y);

        /// <summary>
        /// Чебышёвское расстояние (max по осям).
        /// Используется для проверки зоны атаки 3×3 (distance == 1).
        /// </summary>
        public int ChebyshevDistance(GridPosition other)
            => Math.Max(Math.Abs(X - other.X), Math.Abs(Y - other.Y));

        // ── Flat-индекс ──────────────────────────────────────────────────────

        /// <summary>
        /// Вычисляет плоский индекс Y * MapWidth + X.
        /// Соответствует порядку каналов в ObservationContract / ActionContract.
        /// </summary>
        public int ToFlatIndex()
            => Y * GameConstants.MapWidth + X;

        /// <summary>
        /// Восстанавливает GridPosition из плоского индекса
        /// при ширине карты GameConstants.MapWidth.
        /// </summary>
        public static GridPosition FromFlatIndex(int index)
            => new GridPosition(index % GameConstants.MapWidth, index / GameConstants.MapWidth);

        // ── Equality / Hash ──────────────────────────────────────────────────

        public bool Equals(GridPosition other) => X == other.X && Y == other.Y;

        public override bool Equals(object obj)
            => obj is GridPosition other && Equals(other);

        public override int GetHashCode()
            // Упаковываем X в старшие 16 бит, Y — в младшие 16.
            // Для карт до 65535×65535 коллизий нет.
            => (X << 16) ^ (ushort)Y;

        public static bool operator ==(GridPosition a, GridPosition b) => a.Equals(b);
        public static bool operator !=(GridPosition a, GridPosition b) => !a.Equals(b);

        // ── Арифметика ───────────────────────────────────────────────────────

        public static GridPosition operator +(GridPosition a, GridPosition b)
            => new GridPosition(a.X + b.X, a.Y + b.Y);

        public static GridPosition operator -(GridPosition a, GridPosition b)
            => new GridPosition(a.X - b.X, a.Y - b.Y);

        // ── Отладка ──────────────────────────────────────────────────────────

        public override string ToString() => $"({X}, {Y})";
    }
}
