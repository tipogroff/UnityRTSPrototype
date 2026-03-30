using System;

namespace RTS.ML
{
    /// <summary>
    /// Week 4 Day 1 contract skeleton.
    ///
    /// This file intentionally defines only semantic types. It does not collect reward,
    /// does not modify runtime, and does not alter the existing Week 3 execution pipeline.
    /// </summary>
    public enum RewardCategory
    {
        Economy = 0,
        Combat = 1,
        Terminal = 2,
        Shaping = 3,
        Diagnostic = 4
    }

    public enum RewardAttributionBasis
    {
        RuntimeEffect = 0,
        AcceptedCommand = 1,
        Intent = 2,
        AuthoritativeRejection = 3
    }

    public enum RewardEventType
    {
        None = 0,

        EconomyHarvestSuccess = 10,
        EconomyReturnSuccess = 11,
        EconomyProduceSuccess = 12,

        CombatDamageDealt = 20,
        CombatEnemyDestroyed = 21,
        CombatSelfUnitLost = 22,
        CombatSelfBaseLost = 23,

        TerminalWin = 30,
        TerminalLoss = 31,
        TerminalDraw = 32,
        TerminalTimeout = 33,
        TerminalInvalidRuntimeState = 34,

        ShapingInvalidCommand = 40,
        ShapingIdleStep = 41,
        ShapingLongEpisode = 42
    }

    /// <summary>
    /// RL-facing terminal reasons.
    ///
    /// These reasons are intended to map to runtime-authoritative match lifecycle signals.
    /// Day 1 does not implement mapping logic yet.
    /// </summary>
    public enum TerminalReason
    {
        None = 0,
        Win = 1,
        Loss = 2,
        Draw = 3,
        Timeout = 4,
        InvalidRuntimeState = 5
    }

    [Serializable]
    public struct RewardConfig
    {
        public float EconomyHarvestSuccess;
        public float EconomyReturnSuccess;
        public float EconomyProduceSuccess;

        public float CombatDamageDealt;
        public float CombatEnemyDestroyed;
        public float CombatSelfUnitLost;
        public float CombatSelfBaseLost;

        public float TerminalWin;
        public float TerminalLoss;
        public float TerminalDraw;
        public float TerminalTimeout;

        public float ShapingInvalidCommand;
        public float ShapingIdleStep;
        public float ShapingLongEpisode;

        public static RewardConfig CreateV1Defaults()
        {
            return new RewardConfig
            {
                EconomyHarvestSuccess = 0.02f,
                EconomyReturnSuccess = 0.05f,
                EconomyProduceSuccess = 0.03f,

                CombatDamageDealt = 0.01f,
                CombatEnemyDestroyed = 0.20f,
                CombatSelfUnitLost = -0.12f,
                CombatSelfBaseLost = -0.50f,

                TerminalWin = 1.00f,
                TerminalLoss = -1.00f,
                TerminalDraw = 0.00f,
                TerminalTimeout = 0.00f,

                ShapingInvalidCommand = -0.005f,
                ShapingIdleStep = -0.001f,
                ShapingLongEpisode = -0.001f
            };
        }
    }

    [Serializable]
    public struct RewardBreakdown
    {
        public float Total;
        public float Economy;
        public float Combat;
        public float Terminal;
        public float Shaping;

        public int EventCount;
        public bool IsTerminalStep;
        public TerminalReason TerminalReason;
    }
}