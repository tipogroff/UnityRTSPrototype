// VictoryResolver.cs — проверка условий победы/поражения.
// Этап 4: Боевая механика. Неделя 2.

using UnityEngine;
using RTS.Core;

namespace RTS.Gameplay
{
    /// <summary>
    /// Проверяет условия победы/поражения каждый шаг.
    /// Победа = враг потерял все базы, текущий игрок имеет хотя бы одну базу.
    /// </summary>
    public class VictoryResolver : MonoBehaviour
    {
        // ── Singleton ─────────────────────────────────────────────────────────

        public static VictoryResolver Instance { get; private set; }

        // ── Unity lifecycle ───────────────────────────────────────────────────

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Destroy(gameObject);
                return;
            }
            Instance = this;
        }

        private void OnDestroy()
        {
            if (Instance == this) Instance = null;
        }

        // ── Victory conditions ─────────────────────────────────────────────────

        /// <summary>
        /// Проверяет, может ли кто-то выиграть.
        /// Победа = у одного игрока есть базы, у другого нет.
        /// </summary>
        public void CheckVictoryConditions()
        {
            var matchMgr = MatchManager.Instance;
            var registry = UnitRegistry.Instance;

            if (matchMgr == null || registry == null) return;
            if (matchMgr.Phase != MatchPhase.Running) return;

            // Подсчитаем базы для каждого игрока
            var p1Buildings = registry.GetBuildingsByOwner(Owner.Player1);
            var p2Buildings = registry.GetBuildingsByOwner(Owner.Player2);

            bool p1HasBases = p1Buildings.Count > 0;
            bool p2HasBases = p2Buildings.Count > 0;

            // Проверка условия победы
            if (!p1HasBases && p2HasBases)
            {
                // Player1 потерял все базы → Player2 выигрывает
                Debug.Log("[VictoryResolver] Player1 потерял все базы. Player2 победил!");
                matchMgr.DeclareWinner(Owner.Player2);
            }
            else if (!p2HasBases && p1HasBases)
            {
                // Player2 потерял все базы → Player1 выигрывает
                Debug.Log("[VictoryResolver] Player2 потерял все базы. Player1 победил!");
                matchMgr.DeclareWinner(Owner.Player1);
            }
            else if (!p1HasBases && !p2HasBases)
            {
                // Обе стороны без баз (экстремальный случай) → Ничья
                Debug.Log("[VictoryResolver] Обе стороны без баз. Ничья!");
                matchMgr.DeclareWinner(Owner.Neutral);
            }
        }

        /// <summary>
        /// Проверить статус конкретного игрока (для логирования).
        /// </summary>
        public int GetBuildingCount(Owner owner)
        {
            var registry = UnitRegistry.Instance;
            if (registry == null) return 0;

            return registry.GetBuildingsByOwner(owner).Count;
        }
    }
}
