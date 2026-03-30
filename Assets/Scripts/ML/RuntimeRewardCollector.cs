using System;
using System.Collections.Generic;
using RTS.Core;
using RTS.Gameplay;
using UnityEngine;

namespace RTS.ML
{
    [Serializable]
    public struct RewardCollectorOptions
    {
        public bool EnableSelfLossPenalty;
        public bool EnableInvalidCommandPenalty;
        public bool EnableTimeoutPenalty;
        public float InvalidPenaltyPerStepCap;

        public static RewardCollectorOptions CreateDefaults()
        {
            return new RewardCollectorOptions
            {
                EnableSelfLossPenalty = false,
                EnableInvalidCommandPenalty = false,
                EnableTimeoutPenalty = false,
                InvalidPenaltyPerStepCap = 0.05f
            };
        }
    }

    public readonly struct RewardEvent
    {
        public RewardEvent(
            RewardEventType type,
            RewardCategory category,
            RewardAttributionBasis attributionBasis,
            float magnitude,
            Owner perspective,
            string sourceDescription)
        {
            Type = type;
            Category = category;
            AttributionBasis = attributionBasis;
            Magnitude = magnitude;
            Perspective = perspective;
            SourceDescription = sourceDescription ?? string.Empty;
        }

        public RewardEventType Type { get; }
        public RewardCategory Category { get; }
        public RewardAttributionBasis AttributionBasis { get; }
        public float Magnitude { get; }
        public Owner Perspective { get; }
        public string SourceDescription { get; }
    }

    public readonly struct RewardStepTrace
    {
        private readonly RewardEvent[] _events;

        public RewardStepTrace(
            RewardBreakdown breakdown,
            IReadOnlyList<RewardEvent> events,
            int step,
            MatchEndReason runtimeEndReason,
            int invalidCommandsLastStep)
        {
            Breakdown = breakdown;
            Step = step;
            RuntimeEndReason = runtimeEndReason;
            InvalidCommandsLastStep = invalidCommandsLastStep;
            _events = Copy(events);
        }

        public RewardBreakdown Breakdown { get; }
        public int Step { get; }
        public MatchEndReason RuntimeEndReason { get; }
        public int InvalidCommandsLastStep { get; }
        public IReadOnlyList<RewardEvent> Events => _events;

        private static RewardEvent[] Copy(IReadOnlyList<RewardEvent> source)
        {
            if (source == null || source.Count == 0)
            {
                return Array.Empty<RewardEvent>();
            }

            var copy = new RewardEvent[source.Count];
            for (int i = 0; i < source.Count; i++)
            {
                copy[i] = source[i];
            }

            return copy;
        }
    }

    public readonly struct RewardEpisodeSummary
    {
        public RewardEpisodeSummary(
            RewardBreakdown breakdown,
            int stepCount,
            int totalEventCount,
            bool terminalReached,
            TerminalReason terminalReason)
        {
            Breakdown = breakdown;
            StepCount = stepCount;
            TotalEventCount = totalEventCount;
            TerminalReached = terminalReached;
            TerminalReason = terminalReason;
        }

        public RewardBreakdown Breakdown { get; }
        public int StepCount { get; }
        public int TotalEventCount { get; }
        public bool TerminalReached { get; }
        public TerminalReason TerminalReason { get; }
    }

    public sealed class RewardRuntimeSnapshot
    {
        public RewardRuntimeSnapshot(
            MatchStateSnapshot matchState,
            int invalidCommandsLastStep,
            int carriedResourcesPlayer1,
            int carriedResourcesPlayer2,
            Dictionary<int, UnitSnapshot> unitsById)
        {
            MatchState = matchState;
            InvalidCommandsLastStep = invalidCommandsLastStep;
            CarriedResourcesPlayer1 = carriedResourcesPlayer1;
            CarriedResourcesPlayer2 = carriedResourcesPlayer2;
            UnitsById = unitsById ?? new Dictionary<int, UnitSnapshot>();
        }

        public MatchStateSnapshot MatchState { get; }
        public int InvalidCommandsLastStep { get; }
        public int CarriedResourcesPlayer1 { get; }
        public int CarriedResourcesPlayer2 { get; }
        public Dictionary<int, UnitSnapshot> UnitsById { get; }
    }

    public readonly struct UnitSnapshot
    {
        public UnitSnapshot(Owner owner, UnitType unitType, int hp, bool isAlive)
        {
            Owner = owner;
            UnitType = unitType;
            HP = Mathf.Max(0, hp);
            IsAlive = isAlive;
        }

        public Owner Owner { get; }
        public UnitType UnitType { get; }
        public int HP { get; }
        public bool IsAlive { get; }
    }

    /// <summary>
    /// Week 4 Day 2 reward collector.
    ///
    /// Runtime-authoritative by design: reward is computed from pre-step vs post-step runtime snapshots.
    /// The collector does not inspect masks, decoder outputs, or heuristic intent.
    /// </summary>
    public sealed class RuntimeRewardCollector
    {
        private readonly RewardConfig _config;
        private readonly RewardCollectorOptions _options;

        private RewardBreakdown _episodeBreakdown;
        private int _episodeStepCount;
        private int _episodeEventCount;
        private bool _terminalReached;
        private TerminalReason _episodeTerminalReason;

        public RuntimeRewardCollector(RewardConfig config, RewardCollectorOptions options)
        {
            _config = config;
            _options = options;
            ResetEpisode();
        }

        public void ResetEpisode()
        {
            _episodeBreakdown = default;
            _episodeStepCount = 0;
            _episodeEventCount = 0;
            _terminalReached = false;
            _episodeTerminalReason = TerminalReason.None;
        }

        public RewardEpisodeSummary CurrentEpisodeSummary => new RewardEpisodeSummary(
            _episodeBreakdown,
            _episodeStepCount,
            _episodeEventCount,
            _terminalReached,
            _episodeTerminalReason);

        public RewardRuntimeSnapshot CaptureSnapshot(MatchManager matchManager, UnitRegistry unitRegistry)
        {
            MatchStateSnapshot matchState = matchManager != null ? matchManager.GetMatchState() : default;
            int invalidCommandsLastStep = matchManager != null ? matchManager.InvalidCommandsLastStep : 0;

            int carriedP1 = 0;
            int carriedP2 = 0;
            var unitsById = new Dictionary<int, UnitSnapshot>(256);

            if (unitRegistry != null)
            {
                List<UnitRuntime> units = unitRegistry.GetAllUnits();
                for (int i = 0; i < units.Count; i++)
                {
                    UnitRuntime unit = units[i];
                    if (unit == null)
                    {
                        continue;
                    }

                    int id = unit.GetInstanceID();
                    unitsById[id] = new UnitSnapshot(unit.Owner, unit.Type, unit.HP, unit.IsAlive);

                    if (!unit.IsAlive)
                    {
                        continue;
                    }

                    if (unit.Owner == Owner.Player1)
                    {
                        carriedP1 += Mathf.Max(0, unit.CarriedResources);
                    }
                    else if (unit.Owner == Owner.Player2)
                    {
                        carriedP2 += Mathf.Max(0, unit.CarriedResources);
                    }
                }
            }

            return new RewardRuntimeSnapshot(matchState, invalidCommandsLastStep, carriedP1, carriedP2, unitsById);
        }

        public RewardStepTrace EvaluateStep(RewardRuntimeSnapshot pre, RewardRuntimeSnapshot post, Owner perspective)
        {
            var events = new List<RewardEvent>(16);
            RewardBreakdown breakdown = default;

            int ownResourceDelta = GetResources(post.MatchState, perspective) - GetResources(pre.MatchState, perspective);
            if (ownResourceDelta > 0)
            {
                // Runtime effect: own resource stock increased after step.
                AddEvent(
                    events,
                    ref breakdown,
                    RewardEventType.EconomyReturnSuccess,
                    RewardCategory.Economy,
                    RewardAttributionBasis.RuntimeEffect,
                    _config.EconomyReturnSuccess * ownResourceDelta,
                    perspective,
                    $"Own resource delta +{ownResourceDelta}");
            }

            int ownCarriedDelta = GetCarried(post, perspective) - GetCarried(pre, perspective);
            if (ownCarriedDelta > 0)
            {
                // Runtime effect proxy for successful harvest extraction.
                AddEvent(
                    events,
                    ref breakdown,
                    RewardEventType.EconomyHarvestSuccess,
                    RewardCategory.Economy,
                    RewardAttributionBasis.RuntimeEffect,
                    _config.EconomyHarvestSuccess * ownCarriedDelta,
                    perspective,
                    $"Own carried-resource delta +{ownCarriedDelta}");
            }

            int ownUnitDelta = GetUnitCount(post.MatchState, perspective) - GetUnitCount(pre.MatchState, perspective);
            if (ownUnitDelta > 0)
            {
                AddEvent(
                    events,
                    ref breakdown,
                    RewardEventType.EconomyProduceSuccess,
                    RewardCategory.Economy,
                    RewardAttributionBasis.RuntimeEffect,
                    _config.EconomyProduceSuccess * ownUnitDelta,
                    perspective,
                    $"Own unit-count delta +{ownUnitDelta}");
            }

            int enemyHpLoss = ComputeEnemyHpLoss(pre, post, perspective);
            if (enemyHpLoss > 0)
            {
                AddEvent(
                    events,
                    ref breakdown,
                    RewardEventType.CombatDamageDealt,
                    RewardCategory.Combat,
                    RewardAttributionBasis.RuntimeEffect,
                    _config.CombatDamageDealt * enemyHpLoss,
                    perspective,
                    $"Enemy HP loss {enemyHpLoss}");
            }

            int enemyDestroyed = ComputeDestroyedUnits(pre, post, GetEnemy(perspective));
            if (enemyDestroyed > 0)
            {
                AddEvent(
                    events,
                    ref breakdown,
                    RewardEventType.CombatEnemyDestroyed,
                    RewardCategory.Combat,
                    RewardAttributionBasis.RuntimeEffect,
                    _config.CombatEnemyDestroyed * enemyDestroyed,
                    perspective,
                    $"Enemy destroyed {enemyDestroyed}");
            }

            if (_options.EnableSelfLossPenalty)
            {
                int ownDestroyed = ComputeDestroyedUnits(pre, post, perspective);
                if (ownDestroyed > 0)
                {
                    AddEvent(
                        events,
                        ref breakdown,
                        RewardEventType.CombatSelfUnitLost,
                        RewardCategory.Combat,
                        RewardAttributionBasis.RuntimeEffect,
                        _config.CombatSelfUnitLost * ownDestroyed,
                        perspective,
                        $"Own units lost {ownDestroyed}");
                }
            }

            bool becameTerminal = pre.MatchState.Phase == MatchPhase.Running && post.MatchState.Phase == MatchPhase.Ended;
            if (becameTerminal)
            {
                AddTerminalEvents(events, ref breakdown, post.MatchState, perspective);
            }

            if (_options.EnableInvalidCommandPenalty && post.InvalidCommandsLastStep > 0)
            {
                float invalidPenalty = _config.ShapingInvalidCommand * post.InvalidCommandsLastStep;
                float cappedAbs = Mathf.Max(0f, _options.InvalidPenaltyPerStepCap);
                invalidPenalty = Mathf.Clamp(invalidPenalty, -cappedAbs, cappedAbs);

                AddEvent(
                    events,
                    ref breakdown,
                    RewardEventType.ShapingInvalidCommand,
                    RewardCategory.Shaping,
                    RewardAttributionBasis.AcceptedCommand,
                    invalidPenalty,
                    perspective,
                    $"Invalid commands {post.InvalidCommandsLastStep}");
            }

            breakdown.EventCount = events.Count;
            breakdown.IsTerminalStep = becameTerminal;
            breakdown.TerminalReason = becameTerminal
                ? MapTerminalReason(post.MatchState, perspective)
                : TerminalReason.None;
            breakdown.Total = breakdown.Economy + breakdown.Combat + breakdown.Terminal + breakdown.Shaping;

            AccumulateEpisode(breakdown);

            return new RewardStepTrace(
                breakdown,
                events,
                post.MatchState.Step,
                post.MatchState.EndReason,
                post.InvalidCommandsLastStep);
        }

        private void AddTerminalEvents(
            List<RewardEvent> events,
            ref RewardBreakdown breakdown,
            MatchStateSnapshot post,
            Owner perspective)
        {
            RewardEventType eventType;
            float magnitude;
            string source;

            if (post.Winner == perspective)
            {
                eventType = RewardEventType.TerminalWin;
                magnitude = _config.TerminalWin;
                source = "Runtime terminal outcome: win";
            }
            else if (post.Winner == Owner.Neutral)
            {
                eventType = RewardEventType.TerminalDraw;
                magnitude = _config.TerminalDraw;
                source = "Runtime terminal outcome: draw";
            }
            else
            {
                eventType = RewardEventType.TerminalLoss;
                magnitude = _config.TerminalLoss;
                source = "Runtime terminal outcome: loss";
            }

            AddEvent(
                events,
                ref breakdown,
                eventType,
                RewardCategory.Terminal,
                RewardAttributionBasis.RuntimeEffect,
                magnitude,
                perspective,
                source);

            if (_options.EnableTimeoutPenalty && post.EndReason == MatchEndReason.StepLimitReached)
            {
                AddEvent(
                    events,
                    ref breakdown,
                    RewardEventType.TerminalTimeout,
                    RewardCategory.Terminal,
                    RewardAttributionBasis.RuntimeEffect,
                    _config.TerminalTimeout,
                    perspective,
                    "Runtime terminal reason: timeout");
            }
        }

        private void AddEvent(
            List<RewardEvent> events,
            ref RewardBreakdown breakdown,
            RewardEventType type,
            RewardCategory category,
            RewardAttributionBasis attribution,
            float magnitude,
            Owner perspective,
            string source)
        {
            if (Mathf.Approximately(magnitude, 0f))
            {
                return;
            }

            events.Add(new RewardEvent(type, category, attribution, magnitude, perspective, source));

            switch (category)
            {
                case RewardCategory.Economy:
                    breakdown.Economy += magnitude;
                    break;
                case RewardCategory.Combat:
                    breakdown.Combat += magnitude;
                    break;
                case RewardCategory.Terminal:
                    breakdown.Terminal += magnitude;
                    break;
                case RewardCategory.Shaping:
                    breakdown.Shaping += magnitude;
                    break;
            }
        }

        private void AccumulateEpisode(RewardBreakdown step)
        {
            _episodeBreakdown.Economy += step.Economy;
            _episodeBreakdown.Combat += step.Combat;
            _episodeBreakdown.Terminal += step.Terminal;
            _episodeBreakdown.Shaping += step.Shaping;
            _episodeBreakdown.Total = _episodeBreakdown.Economy + _episodeBreakdown.Combat + _episodeBreakdown.Terminal + _episodeBreakdown.Shaping;

            _episodeBreakdown.EventCount += step.EventCount;
            _episodeBreakdown.IsTerminalStep = step.IsTerminalStep;
            _episodeBreakdown.TerminalReason = step.TerminalReason;

            _episodeStepCount++;
            _episodeEventCount += step.EventCount;

            if (step.IsTerminalStep)
            {
                _terminalReached = true;
                _episodeTerminalReason = step.TerminalReason;
            }
        }

        private static int ComputeEnemyHpLoss(RewardRuntimeSnapshot pre, RewardRuntimeSnapshot post, Owner perspective)
        {
            Owner enemy = GetEnemy(perspective);
            int totalLoss = 0;

            foreach (KeyValuePair<int, UnitSnapshot> kv in pre.UnitsById)
            {
                UnitSnapshot before = kv.Value;
                if (before.Owner != enemy || !before.IsAlive)
                {
                    continue;
                }

                int afterHp = 0;
                if (post.UnitsById.TryGetValue(kv.Key, out UnitSnapshot after) && after.IsAlive)
                {
                    afterHp = after.HP;
                }

                int delta = before.HP - afterHp;
                if (delta > 0)
                {
                    totalLoss += delta;
                }
            }

            return totalLoss;
        }

        private static int ComputeDestroyedUnits(RewardRuntimeSnapshot pre, RewardRuntimeSnapshot post, Owner owner)
        {
            int destroyed = 0;

            foreach (KeyValuePair<int, UnitSnapshot> kv in pre.UnitsById)
            {
                UnitSnapshot before = kv.Value;
                if (before.Owner != owner || !before.IsAlive)
                {
                    continue;
                }

                bool aliveAfter = post.UnitsById.TryGetValue(kv.Key, out UnitSnapshot after) && after.IsAlive;
                if (!aliveAfter)
                {
                    destroyed++;
                }
            }

            return destroyed;
        }

        private static TerminalReason MapTerminalReason(MatchStateSnapshot state, Owner perspective)
        {
            if (state.Phase != MatchPhase.Ended)
            {
                return TerminalReason.None;
            }

            if (state.Winner == perspective)
            {
                return TerminalReason.Win;
            }

            if (state.Winner == Owner.Neutral)
            {
                return state.EndReason == MatchEndReason.StepLimitReached
                    ? TerminalReason.Timeout
                    : TerminalReason.Draw;
            }

            return TerminalReason.Loss;
        }

        private static int GetResources(MatchStateSnapshot state, Owner owner)
        {
            return owner == Owner.Player1 ? state.Player1Resources : state.Player2Resources;
        }

        private static int GetUnitCount(MatchStateSnapshot state, Owner owner)
        {
            return owner == Owner.Player1 ? state.Player1UnitCount : state.Player2UnitCount;
        }

        private static int GetCarried(RewardRuntimeSnapshot snapshot, Owner owner)
        {
            return owner == Owner.Player1 ? snapshot.CarriedResourcesPlayer1 : snapshot.CarriedResourcesPlayer2;
        }

        private static Owner GetEnemy(Owner owner)
        {
            return owner == Owner.Player1 ? Owner.Player2 : Owner.Player1;
        }
    }
}