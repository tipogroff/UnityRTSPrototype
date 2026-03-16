// UnitDefinition.cs — ScriptableObject с параметрами одного типа юнита
// Технический контракт MVP. Неделя 1.

using UnityEngine;

namespace RTS.Core
{
    /// <summary>
    /// Параметры одного типа юнита. Создаётся как ассет через
    /// Assets &gt; Create &gt; RTS &gt; Unit Definition.
    /// </summary>
    [CreateAssetMenu(fileName = "UnitDef_", menuName = "RTS/Unit Definition")]
    public class UnitDefinition : ScriptableObject
    {
        [Header("Идентификация")]
        public UnitType unitType;
        public string  displayName;

        [Header("Характеристики")]
        [Min(1)] public int maxHitPoints  = 5;
        [Min(0)] public int attackDamage  = 1;
        [Min(0)] public int attackRange   = 1;   // в клетках
        [Min(1)] public int moveSpeed     = 1;   // клеток за тик (обычно 1)
        [Min(0)] public int productionCost = 1;  // стоимость производства

        [Header("Производство")]
        [Tooltip("True — юнит является строением (статичен, не перемещается)")]
        public bool isBuilding = false;
        [Tooltip("Тики для производства одного экземпляра этого типа")]
        [Min(1)] public int productionTime = 5;

        [Header("Визуал (заглушка до добавления реальных ассетов)")]
        public GameObject prefab;
    }
}
