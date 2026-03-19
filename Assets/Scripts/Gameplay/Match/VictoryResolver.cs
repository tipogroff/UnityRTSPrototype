// VictoryResolver.cs — formal match termination rules.

using System.Collections.Generic;
using UnityEngine;
using RTS.Core;

namespace RTS.Gameplay
{
    public enum MatchEndReason
    {
        None = 0,
        EnemyBaseDestroyed = 1,
        Elimination = 2,
        StepLimitReached = 3
    }

    public readonly struct MatchResolution
    {
        public MatchResolution(bool isTerminal, Owner winner, MatchEndReason reason, int stepCount, string details)
        {
            IsTerminal = isTerminal;
            Winner = winner;
            Reason = reason;
            StepCount = stepCount;
            Details = details ?? string.Empty;
        }

        public bool IsTerminal { get; }
        public Owner Winner { get; }
        public MatchEndReason Reason { get; }
        public int StepCount { get; }
        public string Details { get; }

        public static MatchResolution Continue(int stepCount)
            => new MatchResolution(false, Owner.Neutral, MatchEndReason.None, stepCount, string.Empty);
    }

    [DisallowMultipleComponent]
    public class VictoryResolver : MonoBehaviour
    {
        public static VictoryResolver Instance { get; private set; }

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
            if (Instance == this)
            {
                Instance = null;
            }
        }

        public MatchResolution Evaluate(UnitRegistry registry, int currentStep, int maxSteps)
        {
            if (registry == null)
            {
                return MatchResolution.Continue(currentStep);
            }

            PlayerPresence player1 = GetPresence(registry, Owner.Player1);
            PlayerPresence player2 = GetPresence(registry, Owner.Player2);

            // Condition 1: opponent base has been destroyed.
            if (player1.BaseCount == 0 && player2.BaseCount > 0)
            {
                return Terminal(
                    Owner.Player2,
                    MatchEndReason.EnemyBaseDestroyed,
                    currentStep,
                    "Player1 base destroyed.");
            }

            if (player2.BaseCount == 0 && player1.BaseCount > 0)
            {
                return Terminal(
                    Owner.Player1,
                    MatchEndReason.EnemyBaseDestroyed,
                    currentStep,
                    "Player2 base destroyed.");
            }

            // Condition 2: one side has no units and no base.
            bool player1Eliminated = player1.UnitCount == 0 && player1.BaseCount == 0;
            bool player2Eliminated = player2.UnitCount == 0 && player2.BaseCount == 0;

            if (player1Eliminated && !player2Eliminated)
            {
                return Terminal(
                    Owner.Player2,
                    MatchEndReason.Elimination,
                    currentStep,
                    "Player1 has no units and no base.");
            }

            if (player2Eliminated && !player1Eliminated)
            {
                return Terminal(
                    Owner.Player1,
                    MatchEndReason.Elimination,
                    currentStep,
                    "Player2 has no units and no base.");
            }

            if (player1Eliminated && player2Eliminated)
            {
                return Terminal(
                    Owner.Neutral,
                    MatchEndReason.Elimination,
                    currentStep,
                    "Both players eliminated.");
            }

            // Condition 3: step limit reached.
            if (maxSteps > 0 && currentStep >= maxSteps)
            {
                return Terminal(
                    Owner.Neutral,
                    MatchEndReason.StepLimitReached,
                    currentStep,
                    $"Step limit reached ({currentStep}/{maxSteps}).");
            }

            return MatchResolution.Continue(currentStep);
        }

        public int GetBuildingCount(Owner owner)
        {
            UnitRegistry registry = UnitRegistry.Instance;
            if (registry == null)
            {
                return 0;
            }

            return registry.GetBuildingsByOwner(owner).Count;
        }

        public int GetBaseCount(Owner owner)
        {
            UnitRegistry registry = UnitRegistry.Instance;
            if (registry == null)
            {
                return 0;
            }

            return GetPresence(registry, owner).BaseCount;
        }

        private static MatchResolution Terminal(Owner winner, MatchEndReason reason, int stepCount, string details)
            => new MatchResolution(true, winner, reason, stepCount, details);

        private static PlayerPresence GetPresence(UnitRegistry registry, Owner owner)
        {
            List<UnitRuntime> units = registry.GetUnitsByOwner(owner);
            int unitCount = 0;
            int baseCount = 0;

            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit == null || !unit.IsAlive)
                {
                    continue;
                }

                unitCount++;
                if (unit.Type == UnitType.Base)
                {
                    baseCount++;
                }
            }

            return new PlayerPresence(unitCount, baseCount);
        }

        private readonly struct PlayerPresence
        {
            public PlayerPresence(int unitCount, int baseCount)
            {
                UnitCount = unitCount;
                BaseCount = baseCount;
            }

            public int UnitCount { get; }
            public int BaseCount { get; }
        }
    }
}
