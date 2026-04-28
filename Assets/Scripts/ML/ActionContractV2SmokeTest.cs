using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.ML
{
    /// <summary>
    /// Minimal smoke checks for Action Contract v2 constants and mapping helpers.
    /// This test validates contract shape/mapping only; it does not assert full runtime action validity.
    /// </summary>
    public class ActionContractV2SmokeTest : MonoBehaviour
    {
        [ContextMenu("Run ActionContract v2 Smoke")]
        public void Run()
        {
            var issues = new List<string>();

            Expect(ActionContract.SIZE_ACTION_TYPE == 6, "SIZE_ACTION_TYPE should be 6", issues);
            Expect(ActionContract.SIZE_DIRECTION == 4, "SIZE_DIRECTION should be 4", issues);
            Expect(ActionContract.SIZE_PRODUCE_UNIT_TYPE == 7, "SIZE_PRODUCE_UNIT_TYPE should be 7", issues);
            Expect(ActionContract.SIZE_ATTACK_TARGET == 49, "SIZE_ATTACK_TARGET should be 49", issues);

            int[] expectedBranches = { 6, 4, 4, 4, 4, 7, 49 };
            int[] observedBranches =
            {
                ActionContract.SIZE_ACTION_TYPE,
                ActionContract.SIZE_DIRECTION,
                ActionContract.SIZE_DIRECTION,
                ActionContract.SIZE_DIRECTION,
                ActionContract.SIZE_DIRECTION,
                ActionContract.SIZE_PRODUCE_UNIT_TYPE,
                ActionContract.SIZE_ATTACK_TARGET
            };
            for (int i = 0; i < expectedBranches.Length; i++)
            {
                Expect(observedBranches[i] == expectedBranches[i],
                    $"branch[{i}] expected={expectedBranches[i]} observed={observedBranches[i]}",
                    issues);
            }

            Expect(ActionContract.ActionFlatSize == 78,
                $"ActionFlatSize expected=78 observed={ActionContract.ActionFlatSize}",
                issues);

            int expectedTotal = 24 * 24 * 78;
            Expect(ActionContract.TotalActionFlatSize == expectedTotal,
                $"TotalActionFlatSize expected={expectedTotal} observed={ActionContract.TotalActionFlatSize}",
                issues);

            Expect(ActionContract.AttackOffsets != null, "AttackOffsets should not be null", issues);
            Expect(ActionContract.AttackOffsets.Length == 49,
                $"AttackOffsets.Length expected=49 observed={ActionContract.AttackOffsets.Length}",
                issues);

            var off0 = ActionContract.AttackOffsets[0];
            var off24 = ActionContract.AttackOffsets[24];
            var off48 = ActionContract.AttackOffsets[48];
            Expect(off0.dX == -3 && off0.dY == -3,
                $"AttackOffsets[0] expected=(-3,-3) observed=({off0.dX},{off0.dY})",
                issues);
            Expect(off24.dX == 0 && off24.dY == 0,
                $"AttackOffsets[24] expected=(0,0) observed=({off24.dX},{off24.dY})",
                issues);
            Expect(off48.dX == 3 && off48.dY == 3,
                $"AttackOffsets[48] expected=(3,3) observed=({off48.dX},{off48.dY})",
                issues);

            GridPosition actor = new GridPosition(10, 10);
            Expect(ActionContractMappings.TryGetAttackTargetPosition(actor, 0, out GridPosition pos0)
                   && pos0.X == 7 && pos0.Y == 7,
                $"TryGetAttackTargetPosition idx=0 expected=(7,7) observed=({pos0.X},{pos0.Y})",
                issues);

            Expect(ActionContractMappings.TryGetAttackTargetPosition(actor, 24, out GridPosition pos24)
                   && pos24.X == 10 && pos24.Y == 10,
                $"TryGetAttackTargetPosition idx=24 expected=(10,10) observed=({pos24.X},{pos24.Y})",
                issues);

            Expect(ActionContractMappings.TryGetAttackTargetPosition(actor, 48, out GridPosition pos48)
                   && pos48.X == 13 && pos48.Y == 13,
                $"TryGetAttackTargetPosition idx=48 expected=(13,13) observed=({pos48.X},{pos48.Y})",
                issues);

            Expect(!ActionContractMappings.TryGetAttackTargetPosition(actor, -1, out _),
                "TryGetAttackTargetPosition idx=-1 should be rejected",
                issues);
            Expect(!ActionContractMappings.TryGetAttackTargetPosition(actor, 49, out _),
                "TryGetAttackTargetPosition idx=49 should be rejected",
                issues);

            Expect(ActionContractMappings.TryMapV2ProduceIndexToUnitType(0, out UnitType p0) && p0 == UnitType.Resource,
                $"v2 produce index 0 expected Resource observed {p0}", issues);
            Expect(ActionContractMappings.TryMapV2ProduceIndexToUnitType(1, out UnitType p1) && p1 == UnitType.Base,
                $"v2 produce index 1 expected Base observed {p1}", issues);
            Expect(ActionContractMappings.TryMapV2ProduceIndexToUnitType(2, out UnitType p2) && p2 == UnitType.Barracks,
                $"v2 produce index 2 expected Barracks observed {p2}", issues);
            Expect(ActionContractMappings.TryMapV2ProduceIndexToUnitType(3, out UnitType p3) && p3 == UnitType.Worker,
                $"v2 produce index 3 expected Worker observed {p3}", issues);
            Expect(ActionContractMappings.TryMapV2ProduceIndexToUnitType(4, out UnitType p4) && p4 == UnitType.Light,
                $"v2 produce index 4 expected Light observed {p4}", issues);
            Expect(ActionContractMappings.TryMapV2ProduceIndexToUnitType(5, out UnitType p5) && p5 == UnitType.Heavy,
                $"v2 produce index 5 expected Heavy observed {p5}", issues);
            Expect(ActionContractMappings.TryMapV2ProduceIndexToUnitType(6, out UnitType p6) && p6 == UnitType.Ranged,
                $"v2 produce index 6 expected Ranged observed {p6}", issues);

            Expect(!ActionContractMappings.TryMapV2ProduceIndexToUnitType(-1, out _),
                "v2 produce index -1 should be rejected", issues);
            Expect(!ActionContractMappings.TryMapV2ProduceIndexToUnitType(7, out _),
                "v2 produce index 7 should be rejected", issues);

            Debug.Log("[ActionContractV2SmokeTest] Mapping to UnitType does not imply Produce action validity in every runtime context.");

            if (issues.Count == 0)
            {
                Debug.Log("[ActionContractV2SmokeTest] PASSED");
                return;
            }

            Debug.LogError($"[ActionContractV2SmokeTest] FAILED ({issues.Count} issues)");
            for (int i = 0; i < issues.Count; i++)
            {
                Debug.LogError("[ActionContractV2SmokeTest] " + issues[i]);
            }
        }

        private static void Expect(bool condition, string message, List<string> issues)
        {
            if (!condition)
            {
                issues.Add(message);
            }
        }
    }
}
