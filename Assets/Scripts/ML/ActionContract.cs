// ActionContract.cs — точная спецификация пространства действий
// Технический контракт MVP. Неделя 1.
//
// ПОДХОД: Глобальная политика с действием на каждую клетку сетки.
// Совместимо с Gym-µRTS «per-cell action» форматом.
//
// Для каждой из GridH * GridW ячеек агент выдаёт ОДИН вектор из
// ActionBranchCount ветвей (MultiDiscrete). Ячейки без управляемого
// юнита должны получать action 0 (NoOp) — этого можно добиться
// через invalid action masking.
//
// ИТОГО параметров действия за шаг:
//   (GridH * GridW) vet * ActionBranchCount ветвей = 576 * 7 = 4032 int-значений.
// Это совпадает с плоским форматом Gym-µRTS action tensor.

namespace RTS.ML
{
    /// <summary>
    /// Контракт пространства действий.
    ///
    /// Важно для Week 3 v1:
    /// - это transfer-compatible MVP surface, а не claim о полной Gym parity;
    /// - attack targeting намеренно ограничен локальной 3×3 окрестностью;
    /// - более широкие action semantics и richer production spaces остаются за пределами текущего контракта.
    ///
    /// Ветвь                       Размер  Значения
    /// ──────────────────────────────────────────────────────────────────────
    /// BRANCH_ACTION_TYPE          6       0=NoOp, 1=Move, 2=Harvest,
    ///                                     3=Return, 4=Produce, 5=Attack
    /// BRANCH_MOVE_DIR             4       0=N, 1=E, 2=S, 3=W
    /// BRANCH_HARVEST_DIR          4       0=N, 1=E, 2=S, 3=W
    /// BRANCH_RETURN_DIR           4       0=N, 1=E, 2=S, 3=W
    /// BRANCH_PRODUCE_DIR          4       0=N, 1=E, 2=S, 3=W
    /// BRANCH_PRODUCE_UNIT_TYPE    4       0=Worker, 1=Light, 2=Heavy, 3=Ranged
    /// BRANCH_ATTACK_TARGET        9       индекс клетки в зоне 3×3 (0..8, 4=центр)
    /// ──────────────────────────────────────────────────────────────────────
    /// ActionBranchCount = 7 ветвей, ActionFlatSize = 6+4+4+4+4+4+9 = 35.
    ///
    /// Примечание: в Gym-µRTS действие кодируется как flat int по формуле
    ///   flat = sum(branch_sizes[0..i-1]) + branch_value[i]
    /// для каждой ячейки.
    /// </summary>
    public static class ActionContract
    {
        // ── Количество ветвей на клетку ───────────────────────────────────────
        public const int ActionBranchCount = 7;

        // ── Индексы ветвей ────────────────────────────────────────────────────
        public const int BRANCH_ACTION_TYPE       = 0;
        public const int BRANCH_MOVE_DIR          = 1;
        public const int BRANCH_HARVEST_DIR       = 2;
        public const int BRANCH_RETURN_DIR        = 3;
        public const int BRANCH_PRODUCE_DIR       = 4;
        public const int BRANCH_PRODUCE_UNIT_TYPE = 5;
        public const int BRANCH_ATTACK_TARGET     = 6;

        // ── Размеры ветвей ────────────────────────────────────────────────────
        public const int SIZE_ACTION_TYPE       = 6;   // NoOp..Attack
        public const int SIZE_DIRECTION         = 4;   // N, E, S, W
        public const int SIZE_PRODUCE_UNIT_TYPE = 4;   // Worker..Ranged
        public const int SIZE_ATTACK_TARGET     = 9;   // 3×3 neighbourhood

        // ── Flat суммарный размер одного «действия на клетку» ────────────────
        public const int ActionFlatSize =
            SIZE_ACTION_TYPE +                      // 6
            SIZE_DIRECTION   +                      // 4 (move)
            SIZE_DIRECTION   +                      // 4 (harvest)
            SIZE_DIRECTION   +                      // 4 (return)
            SIZE_DIRECTION   +                      // 4 (produce dir)
            SIZE_PRODUCE_UNIT_TYPE +                // 4
            SIZE_ATTACK_TARGET;                     // 9  → итого 35

        // ── Общий размер action tensor за шаг ────────────────────────────────
        public const int TotalCells = ObservationContract.GridH * ObservationContract.GridW; // 576
        public const int TotalActionFlatSize = TotalCells * ActionFlatSize;                  // 20160

        // ── Значения ActionType ───────────────────────────────────────────────
        public const int ACTION_NOOP    = 0;
        public const int ACTION_MOVE    = 1;
        public const int ACTION_HARVEST = 2;
        public const int ACTION_RETURN  = 3;
        public const int ACTION_PRODUCE = 4;
        public const int ACTION_ATTACK  = 5;

        // ── Значения направлений ──────────────────────────────────────────────
        public const int DIR_NORTH = 0;
        public const int DIR_EAST  = 1;
        public const int DIR_SOUTH = 2;
        public const int DIR_WEST  = 3;

        // ── AttackTarget: соответствие indeks → (dRow, dCol) в 3×3 ──────────
        // Карта относительных смещений, центр = индекс 4
        //   0 1 2
        //   3 4 5
        //   6 7 8
        public static readonly (int dRow, int dCol)[] AttackOffsets = new (int, int)[]
        {
            (-1, -1), (-1, 0), (-1, 1),
            ( 0, -1), ( 0, 0), ( 0, 1),
            ( 1, -1), ( 1, 0), ( 1, 1)
        };

        // ── Вспомогательные методы ────────────────────────────────────────────

        /// <summary>
        /// Flat-смещение ветви BRANCH в одном action-векторе на клетку.
        /// Соответствует Gym-µRTS action encoding.
        /// </summary>
        public static int BranchOffset(int branch)
        {
            return branch switch
            {
                BRANCH_ACTION_TYPE       => 0,
                BRANCH_MOVE_DIR          => SIZE_ACTION_TYPE,
                BRANCH_HARVEST_DIR       => SIZE_ACTION_TYPE + SIZE_DIRECTION,
                BRANCH_RETURN_DIR        => SIZE_ACTION_TYPE + SIZE_DIRECTION * 2,
                BRANCH_PRODUCE_DIR       => SIZE_ACTION_TYPE + SIZE_DIRECTION * 3,
                BRANCH_PRODUCE_UNIT_TYPE => SIZE_ACTION_TYPE + SIZE_DIRECTION * 4,
                BRANCH_ATTACK_TARGET     => SIZE_ACTION_TYPE + SIZE_DIRECTION * 4 + SIZE_PRODUCE_UNIT_TYPE,
                _ => -1
            };
        }
    }
}
