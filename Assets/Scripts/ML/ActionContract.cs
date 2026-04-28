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
    /// Важно для Week 5R v2 migration step 1:
    /// - это transfer-compatible MVP surface, а не claim о полной Gym parity;
    /// - action contract расширен до Gridnet-compatible branch sizes [6,4,4,4,4,7,49];
    /// - authoritative runtime validation остаётся в ActionApplier.
    ///
    /// Ветвь                       Размер  Значения
    /// ──────────────────────────────────────────────────────────────────────
    /// BRANCH_ACTION_TYPE          6       0=NoOp, 1=Move, 2=Harvest,
    ///                                     3=Return, 4=Produce, 5=Attack
    /// BRANCH_MOVE_DIR             4       0=N, 1=E, 2=S, 3=W
    /// BRANCH_HARVEST_DIR          4       0=N, 1=E, 2=S, 3=W
    /// BRANCH_RETURN_DIR           4       0=N, 1=E, 2=S, 3=W
    /// BRANCH_PRODUCE_DIR          4       0=N, 1=E, 2=S, 3=W
    /// BRANCH_PRODUCE_UNIT_TYPE    7       contract-level UnitType index (Gym/Gridnet order)
    /// BRANCH_ATTACK_TARGET        49      local 7x7 index (0..48, 24=центр)
    /// ──────────────────────────────────────────────────────────────────────
    /// ActionBranchCount = 7 ветвей, ActionFlatSize = 6+4+4+4+4+7+49 = 78.
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
        public const int SIZE_PRODUCE_UNIT_TYPE = 7;   // UnitType order: Resource..Ranged
        public const int SIZE_ATTACK_TARGET     = 49;  // 7x7 neighbourhood

        // ── Flat суммарный размер одного «действия на клетку» ────────────────
        public const int ActionFlatSize =
            SIZE_ACTION_TYPE +                      // 6
            SIZE_DIRECTION   +                      // 4 (move)
            SIZE_DIRECTION   +                      // 4 (harvest)
            SIZE_DIRECTION   +                      // 4 (return)
            SIZE_DIRECTION   +                      // 4 (produce dir)
            SIZE_PRODUCE_UNIT_TYPE +                // 7
            SIZE_ATTACK_TARGET;                     // 49  → итого 78

        // ── Общий размер action tensor за шаг ────────────────────────────────
        public const int TotalCells = ObservationContract.GridH * ObservationContract.GridW; // 576
        public const int TotalActionFlatSize = TotalCells * ActionFlatSize;                  // 44928

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

        // ── AttackTarget: соответствие index → (dx, dy) в local 7x7 ─────────
        // Gridnet-compatible local target window (row-major):
        //   idx 0  -> (-3, -3)
        //   idx 24 -> ( 0,  0) center
        //   idx 48 -> ( 3,  3)
        //
        // NOTE: center index 24 should normally be mask-disabled for attack.
        public static readonly (int dX, int dY)[] AttackOffsets = new (int, int)[]
        {
            (-3, -3), (-2, -3), (-1, -3), ( 0, -3), ( 1, -3), ( 2, -3), ( 3, -3),
            (-3, -2), (-2, -2), (-1, -2), ( 0, -2), ( 1, -2), ( 2, -2), ( 3, -2),
            (-3, -1), (-2, -1), (-1, -1), ( 0, -1), ( 1, -1), ( 2, -1), ( 3, -1),
            (-3,  0), (-2,  0), (-1,  0), ( 0,  0), ( 1,  0), ( 2,  0), ( 3,  0),
            (-3,  1), (-2,  1), (-1,  1), ( 0,  1), ( 1,  1), ( 2,  1), ( 3,  1),
            (-3,  2), (-2,  2), (-1,  2), ( 0,  2), ( 1,  2), ( 2,  2), ( 3,  2),
            (-3,  3), (-2,  3), (-1,  3), ( 0,  3), ( 1,  3), ( 2,  3), ( 3,  3)
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
