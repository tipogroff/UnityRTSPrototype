using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.ML
{
    /// <summary>
    /// v2 decoder-surface smoke checks for branch bounds and local attack index mapping.
    ///
    /// This validates decoder-facing contract assumptions only:
    /// - attack local index geometry (7x7, 49 slots)
    /// - produce branch bound domain (0..6)
    ///
    /// It does NOT claim runtime Produce validity. Runtime/context validity remains in
    /// ActionMaskBuilder + ActionApplier.
    /// </summary>
    public class ActionDecoderV2SmokeTest : MonoBehaviour
    {
        [ContextMenu("Run ActionDecoder v2 Smoke")]
        public void Run()
        {
            var issues = new List<string>();

            Expect(ActionContract.SIZE_ATTACK_TARGET == 49,
                $"SIZE_ATTACK_TARGET expected=49 observed={ActionContract.SIZE_ATTACK_TARGET}", issues);
            Expect(ActionContract.SIZE_PRODUCE_UNIT_TYPE == 7,
                $"SIZE_PRODUCE_UNIT_TYPE expected=7 observed={ActionContract.SIZE_PRODUCE_UNIT_TYPE}", issues);

            GridPosition actor = new GridPosition(10, 10);
            Expect(ActionContractMappings.TryGetAttackTargetPosition(actor, 0, out GridPosition pos0)
                   && pos0.X == 7 && pos0.Y == 7,
                $"attack index 0 expected=(7,7) observed=({pos0.X},{pos0.Y})", issues);

            Expect(ActionContractMappings.TryGetAttackTargetPosition(actor, 24, out GridPosition pos24)
                   && pos24.X == 10 && pos24.Y == 10,
                $"attack index 24 expected=(10,10) observed=({pos24.X},{pos24.Y})", issues);

            Expect(ActionContractMappings.TryGetAttackTargetPosition(actor, 48, out GridPosition pos48)
                   && pos48.X == 13 && pos48.Y == 13,
                $"attack index 48 expected=(13,13) observed=({pos48.X},{pos48.Y})", issues);

            Expect(!ActionContractMappings.TryGetAttackTargetPosition(actor, -1, out _),
                "attack index -1 should be rejected", issues);
            Expect(!ActionContractMappings.TryGetAttackTargetPosition(actor, 49, out _),
                "attack index 49 should be rejected", issues);

            for (int i = 0; i < ActionContract.SIZE_PRODUCE_UNIT_TYPE; i++)
            {
                bool inDecoderBranchBounds = i >= 0 && i < ActionContract.SIZE_PRODUCE_UNIT_TYPE;
                bool hasV2Mapping = ActionContractMappings.TryMapV2ProduceIndexToUnitType(i, out UnitType mappedType);
                Expect(inDecoderBranchBounds && hasV2Mapping,
                    $"produce index {i} should pass branch-bound decode assumptions (mapped={mappedType})",
                    issues);
            }

            Expect(!ActionContractMappings.TryMapV2ProduceIndexToUnitType(-1, out _),
                "produce index -1 should be rejected", issues);
            Expect(!ActionContractMappings.TryMapV2ProduceIndexToUnitType(7, out _),
                "produce index 7 should be rejected", issues);

            Debug.Log("[ActionDecoderV2SmokeTest] Branch-bound decode validity != runtime Produce validity (ActionMaskBuilder/ActionApplier remain authoritative).");

            if (issues.Count == 0)
            {
                Debug.Log("[ActionDecoderV2SmokeTest] PASSED");
                return;
            }

            Debug.LogError($"[ActionDecoderV2SmokeTest] FAILED ({issues.Count} issues)");
            for (int i = 0; i < issues.Count; i++)
            {
                Debug.LogError("[ActionDecoderV2SmokeTest] " + issues[i]);
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
