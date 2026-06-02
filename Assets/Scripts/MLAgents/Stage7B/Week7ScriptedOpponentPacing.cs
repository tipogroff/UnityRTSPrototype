using System;
using System.IO;
using System.Text;
using RTS.Core;
using RTS.ML;
using UnityEngine;

namespace RTS.MLAgents.Stage7B
{
    [DisallowMultipleComponent]
    public sealed class Week7ScriptedOpponentPacing : MonoBehaviour
    {
        [Header("Week7 Scripted Opponent Throttle")]
        [SerializeField] private bool _enableWeek7BotThrottle = true;
        [SerializeField] private bool _throttleAffectsOnlyOpponent = true;
        [SerializeField, Min(1)] private int _botDecisionIntervalSteps = 7;
        [SerializeField, Min(0f)] private float _botActionCooldownSeconds;
        [SerializeField, Min(0)] private int _openingGraceSteps = 80;
        [SerializeField] private bool _allowEconomyActionsDuringGrace = true;
        [SerializeField] private bool _allowAttackDuringGrace;
        [SerializeField, Min(0)] private int _aggressionDelaySteps = 120;
        [SerializeField, Min(0)] private int _attackActionCooldownSteps = 30;
        [SerializeField, Min(1)] private int _aggressionWindowSteps = 100;
        [SerializeField, Min(0)] private int _maxAggressiveActionsPerWindow = 2;
        [SerializeField] private string _reportRelativePath = "python/stage7b_teacher_replay/stage7b_week7_scripted_bot_throttle_report.json";

        private int _decisionAttemptCounter;
        private int _decisionExecutedCounter;
        private int _botActionStepCounter;
        private float _lastDecisionTime = float.NegativeInfinity;
        private int _lastAttackActionStep = int.MinValue;
        private int _firstAttackActionStep = -1;
        private int _maxAggressiveActionsObservedPerWindow;
        private int _botActionsAttemptedAfter;
        private int _studentActionsAttempted;
        private int _acceptedBotCommands;
        private int _rejectedBotCommands;
        private int _blockedAttackDuringGraceCount;
        private int _blockedAttackDuringDelayCount;
        private int _blockedAttackCooldownCount;
        private int _blockedAttackWindowCapCount;
        private int _acceptedBotMoveActions;
        private int _acceptedBotHarvestActions;
        private int _acceptedBotReturnActions;
        private int _acceptedBotProduceActions;
        private int _acceptedBotAttackActions;
        private int _acceptedBotNoOpActions;
        private int _acceptedBotOtherActions;
        private Owner _scriptedOwner = Owner.Player2;
        private HeuristicPolicyAdapter _attachedAdapter;
        private readonly int[] _recentAggressiveActionSteps = new int[256];
        private int _recentAggressiveActionCount;
        private string _terminalReason = "not_terminal";
        private bool _duplicateSpawnDetected;
        private bool _reportWrittenThisEpisode;

        public bool ThrottleEnabled => _enableWeek7BotThrottle;
        public int BotDecisionIntervalSteps => Mathf.Max(1, _botDecisionIntervalSteps);
        public bool ThrottleAffectsOnlyOpponent => _throttleAffectsOnlyOpponent;
        public int OpeningGraceSteps => Mathf.Max(0, _openingGraceSteps);
        public bool AllowEconomyActionsDuringGrace => _allowEconomyActionsDuringGrace;
        public bool AllowAttackDuringGrace => _allowAttackDuringGrace;
        public int AggressionDelaySteps => Mathf.Max(0, _aggressionDelaySteps);
        public int AttackActionCooldownSteps => Mathf.Max(0, _attackActionCooldownSteps);
        public int AggressionWindowSteps => Mathf.Max(1, _aggressionWindowSteps);
        public int MaxAggressiveActionsPerWindow => Mathf.Max(0, _maxAggressiveActionsPerWindow);
        public int StudentActionsAttempted => _studentActionsAttempted;
        public int BotActionsAttempted => _botActionsAttemptedAfter;
        public int AcceptedBotCommands => _acceptedBotCommands;
        public int RejectedBotCommands => _rejectedBotCommands;
        public string TerminalReason => _terminalReason;

        public void AttachAdapter(HeuristicPolicyAdapter adapter, Owner scriptedOwner)
        {
            DetachAdapterHooks();

            _attachedAdapter = adapter;
            _scriptedOwner = scriptedOwner;

            if (_attachedAdapter == null)
            {
                return;
            }

            _attachedAdapter.OnActionEvaluated += OnAdapterActionEvaluated;
            _attachedAdapter.ActionSelectionFilter = IsActionAllowedByThrottle;
        }

        public void DetachAdapterHooks()
        {
            if (_attachedAdapter != null)
            {
                _attachedAdapter.OnActionEvaluated -= OnAdapterActionEvaluated;
                if (_attachedAdapter.ActionSelectionFilter == IsActionAllowedByThrottle)
                {
                    _attachedAdapter.ActionSelectionFilter = null;
                }
            }

            _attachedAdapter = null;
        }

        public void ResetForEpisode(bool duplicateSpawnDetected)
        {
            _decisionAttemptCounter = 0;
            _decisionExecutedCounter = 0;
            _botActionStepCounter = 0;
            _lastDecisionTime = float.NegativeInfinity;
            _lastAttackActionStep = int.MinValue;
            _firstAttackActionStep = -1;
            _maxAggressiveActionsObservedPerWindow = 0;
            _botActionsAttemptedAfter = 0;
            _studentActionsAttempted = 0;
            _acceptedBotCommands = 0;
            _rejectedBotCommands = 0;
            _blockedAttackDuringGraceCount = 0;
            _blockedAttackDuringDelayCount = 0;
            _blockedAttackCooldownCount = 0;
            _blockedAttackWindowCapCount = 0;
            _acceptedBotMoveActions = 0;
            _acceptedBotHarvestActions = 0;
            _acceptedBotReturnActions = 0;
            _acceptedBotProduceActions = 0;
            _acceptedBotAttackActions = 0;
            _acceptedBotNoOpActions = 0;
            _acceptedBotOtherActions = 0;
            _recentAggressiveActionCount = 0;
            _terminalReason = "not_terminal";
            _duplicateSpawnDetected = duplicateSpawnDetected;
            _reportWrittenThisEpisode = false;
        }

        public void RecordStudentActionAttempt()
        {
            _studentActionsAttempted++;
        }

        public bool ShouldExecuteBotDecisionStep(float nowSeconds)
        {
            _decisionAttemptCounter++;
            _botActionStepCounter = _decisionAttemptCounter;

            if (!_enableWeek7BotThrottle || !_throttleAffectsOnlyOpponent)
            {
                _decisionExecutedCounter++;
                _botActionsAttemptedAfter++;
                _lastDecisionTime = nowSeconds;
                return true;
            }

            if (!_allowEconomyActionsDuringGrace && IsInsideOpeningGraceWindow())
            {
                return false;
            }

            int interval = Mathf.Max(1, _botDecisionIntervalSteps);
            bool intervalReady = ((_decisionAttemptCounter - 1) % interval) == 0;
            bool cooldownReady = _botActionCooldownSeconds <= 0f
                                 || nowSeconds - _lastDecisionTime >= _botActionCooldownSeconds;
            if (!intervalReady || !cooldownReady)
            {
                return false;
            }

            _decisionExecutedCounter++;
            _botActionsAttemptedAfter++;
            _lastDecisionTime = nowSeconds;
            return true;
        }

        public void RecordBotDecisionOutcome(int acceptedCommands, int rejectedCommands)
        {
            _acceptedBotCommands += Mathf.Max(0, acceptedCommands);
            _rejectedBotCommands += Mathf.Max(0, rejectedCommands);
        }

        private bool IsActionAllowedByThrottle(Owner owner, UnitActionType actionType)
        {
            if (!_enableWeek7BotThrottle || !_throttleAffectsOnlyOpponent)
            {
                return true;
            }

            if (owner != _scriptedOwner || actionType != UnitActionType.Attack)
            {
                return true;
            }

            if (IsInsideOpeningGraceWindow() && !_allowAttackDuringGrace)
            {
                _blockedAttackDuringGraceCount++;
                return false;
            }

            int delayGate = Mathf.Max(Mathf.Max(0, _openingGraceSteps), Mathf.Max(0, _aggressionDelaySteps));
            if (_botActionStepCounter <= delayGate)
            {
                _blockedAttackDuringDelayCount++;
                return false;
            }

            int cooldownSteps = Mathf.Max(0, _attackActionCooldownSteps);
            if (cooldownSteps > 0 && _lastAttackActionStep > int.MinValue / 2)
            {
                int stepsSinceAttack = _botActionStepCounter - _lastAttackActionStep;
                if (stepsSinceAttack < cooldownSteps)
                {
                    _blockedAttackCooldownCount++;
                    return false;
                }
            }

            int windowSteps = Mathf.Max(1, _aggressionWindowSteps);
            PruneAggressionWindow(windowSteps);
            int maxAggressive = Mathf.Max(0, _maxAggressiveActionsPerWindow);
            if (_recentAggressiveActionCount >= maxAggressive)
            {
                _blockedAttackWindowCapCount++;
                return false;
            }

            return true;
        }

        private bool IsInsideOpeningGraceWindow()
        {
            return _botActionStepCounter <= Mathf.Max(0, _openingGraceSteps);
        }

        private void OnAdapterActionEvaluated(HeuristicActionEvaluation evaluation)
        {
            if (evaluation.PlayerId != _scriptedOwner || !evaluation.Accepted)
            {
                return;
            }

            switch (evaluation.ActionType)
            {
                case UnitActionType.Move:
                    _acceptedBotMoveActions++;
                    break;
                case UnitActionType.Harvest:
                    _acceptedBotHarvestActions++;
                    break;
                case UnitActionType.Return:
                    _acceptedBotReturnActions++;
                    break;
                case UnitActionType.Produce:
                    _acceptedBotProduceActions++;
                    break;
                case UnitActionType.Attack:
                    _acceptedBotAttackActions++;
                    RegisterAggressiveActionAtCurrentStep();
                    break;
                case UnitActionType.NoOp:
                    _acceptedBotNoOpActions++;
                    break;
                default:
                    _acceptedBotOtherActions++;
                    break;
            }
        }

        private void RegisterAggressiveActionAtCurrentStep()
        {
            int currentStep = Mathf.Max(0, _botActionStepCounter);
            if (_firstAttackActionStep < 0)
            {
                _firstAttackActionStep = currentStep;
            }

            _lastAttackActionStep = currentStep;
            int windowSteps = Mathf.Max(1, _aggressionWindowSteps);
            PruneAggressionWindow(windowSteps);

            if (_recentAggressiveActionCount < _recentAggressiveActionSteps.Length)
            {
                _recentAggressiveActionSteps[_recentAggressiveActionCount++] = currentStep;
            }
            else
            {
                Array.Copy(_recentAggressiveActionSteps, 1, _recentAggressiveActionSteps, 0, _recentAggressiveActionSteps.Length - 1);
                _recentAggressiveActionSteps[_recentAggressiveActionSteps.Length - 1] = currentStep;
            }

            if (_recentAggressiveActionCount > _maxAggressiveActionsObservedPerWindow)
            {
                _maxAggressiveActionsObservedPerWindow = _recentAggressiveActionCount;
            }
        }

        private void PruneAggressionWindow(int windowSteps)
        {
            if (_recentAggressiveActionCount <= 0)
            {
                return;
            }

            int minStepInclusive = Mathf.Max(0, _botActionStepCounter - windowSteps + 1);
            int writeIndex = 0;
            for (int i = 0; i < _recentAggressiveActionCount; i++)
            {
                int step = _recentAggressiveActionSteps[i];
                if (step >= minStepInclusive)
                {
                    _recentAggressiveActionSteps[writeIndex++] = step;
                }
            }

            _recentAggressiveActionCount = writeIndex;
        }

        public void FinalizeEpisodeAndWriteReport(string terminalReason)
        {
            _terminalReason = string.IsNullOrWhiteSpace(terminalReason) ? "unknown" : terminalReason;
            if (_reportWrittenThisEpisode)
            {
                return;
            }

            _reportWrittenThisEpisode = true;
            WriteReport();
        }

        private void WriteReport()
        {
            try
            {
                string fullPath = ResolveReportPath();
                string directory = Path.GetDirectoryName(fullPath);
                if (!string.IsNullOrEmpty(directory))
                {
                    Directory.CreateDirectory(directory);
                }

                var sb = new StringBuilder(512);
                sb.AppendLine("{");
                sb.Append("  \"throttle_enabled\": ").Append(_enableWeek7BotThrottle ? "true" : "false").AppendLine(",");
                sb.Append("  \"bot_decision_interval_steps\": ").Append(Mathf.Max(1, _botDecisionIntervalSteps)).AppendLine(",");
                sb.Append("  \"opening_grace_steps\": ").Append(Mathf.Max(0, _openingGraceSteps)).AppendLine(",");
                sb.Append("  \"allow_economy_actions_during_grace\": ").Append(_allowEconomyActionsDuringGrace ? "true" : "false").AppendLine(",");
                sb.Append("  \"allow_attack_during_grace\": ").Append(_allowAttackDuringGrace ? "true" : "false").AppendLine(",");
                sb.Append("  \"aggression_delay_steps\": ").Append(Mathf.Max(0, _aggressionDelaySteps)).AppendLine(",");
                sb.Append("  \"attack_action_cooldown_steps\": ").Append(Mathf.Max(0, _attackActionCooldownSteps)).AppendLine(",");
                sb.Append("  \"aggression_window_steps\": ").Append(Mathf.Max(1, _aggressionWindowSteps)).AppendLine(",");
                sb.Append("  \"max_aggressive_actions_per_window\": ").Append(Mathf.Max(0, _maxAggressiveActionsPerWindow)).AppendLine(",");
                sb.AppendLine("  \"bot_actions_attempted_before_or_baseline\": null,");
                sb.Append("  \"bot_actions_attempted_after\": ").Append(_botActionsAttemptedAfter).AppendLine(",");
                sb.Append("  \"bot_decision_attempt_count\": ").Append(_decisionAttemptCounter).AppendLine(",");
                sb.Append("  \"bot_decision_executed_count\": ").Append(_decisionExecutedCounter).AppendLine(",");
                sb.Append("  \"student_actions_attempted\": ").Append(_studentActionsAttempted).AppendLine(",");
                sb.Append("  \"accepted_bot_commands\": ").Append(_acceptedBotCommands).AppendLine(",");
                sb.Append("  \"rejected_bot_commands\": ").Append(_rejectedBotCommands).AppendLine(",");
                sb.Append("  \"accepted_bot_move_actions\": ").Append(_acceptedBotMoveActions).AppendLine(",");
                sb.Append("  \"accepted_bot_harvest_actions\": ").Append(_acceptedBotHarvestActions).AppendLine(",");
                sb.Append("  \"accepted_bot_return_actions\": ").Append(_acceptedBotReturnActions).AppendLine(",");
                sb.Append("  \"accepted_bot_produce_actions\": ").Append(_acceptedBotProduceActions).AppendLine(",");
                sb.Append("  \"accepted_bot_attack_actions\": ").Append(_acceptedBotAttackActions).AppendLine(",");
                sb.Append("  \"accepted_bot_noop_actions\": ").Append(_acceptedBotNoOpActions).AppendLine(",");
                sb.Append("  \"accepted_bot_other_actions\": ").Append(_acceptedBotOtherActions).AppendLine(",");
                sb.Append("  \"first_attack_step\": ").Append(_firstAttackActionStep).AppendLine(",");
                sb.Append("  \"opening_grace_worked\": ").Append((_firstAttackActionStep < 0 || _firstAttackActionStep > Mathf.Max(0, _openingGraceSteps)) ? "true" : "false").AppendLine(",");
                sb.Append("  \"blocked_attack_during_grace_count\": ").Append(_blockedAttackDuringGraceCount).AppendLine(",");
                sb.Append("  \"blocked_attack_during_delay_count\": ").Append(_blockedAttackDuringDelayCount).AppendLine(",");
                sb.Append("  \"blocked_attack_cooldown_count\": ").Append(_blockedAttackCooldownCount).AppendLine(",");
                sb.Append("  \"blocked_attack_window_cap_count\": ").Append(_blockedAttackWindowCapCount).AppendLine(",");
                sb.Append("  \"max_aggressive_actions_observed_per_window\": ").Append(_maxAggressiveActionsObservedPerWindow).AppendLine(",");
                sb.Append("  \"terminal_reason\": \"").Append(EscapeJson(_terminalReason)).AppendLine("\",");
                sb.Append("  \"duplicate_spawn_detected\": ").Append(_duplicateSpawnDetected ? "true" : "false").AppendLine(",");
                sb.Append("  \"center_pressure_enabled\": ").Append(_attachedAdapter != null && _attachedAdapter.CenterPressureEnabled ? "true" : "false").AppendLine(",");
                sb.Append("  \"center_bot_decisions_executed\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureDecisionsExecuted : 0).AppendLine(",");
                sb.Append("  \"center_bot_actions_attempted\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureActionsAttempted : 0).AppendLine(",");
                sb.Append("  \"center_bot_commands_accepted\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCommandsAccepted : 0).AppendLine(",");
                sb.Append("  \"center_bot_commands_rejected\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCommandsRejected : 0).AppendLine(",");
                sb.Append("  \"center_rally_moves\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCenterRallyMoves : 0).AppendLine(",");
                sb.Append("  \"center_area_visits\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCenterAreaVisits : 0).AppendLine(",");
                sb.Append("  \"center_to_enemy_approach_moves\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCenterToEnemyApproachMoves : 0).AppendLine(",");
                sb.Append("  \"edge_lane_moves\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureEdgeLaneMoves : 0).AppendLine(",");
                sb.Append("  \"base_idle_steps\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureBaseIdleSteps : 0).AppendLine(",");
                sb.Append("  \"worker_count_min\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureWorkerCountMin : 0).AppendLine(",");
                sb.Append("  \"worker_count_max\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureWorkerCountMax : 0).AppendLine(",");
                sb.Append("  \"worker_count_final\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureWorkerCountFinal : 0).AppendLine(",");
                sb.Append("  \"worker_soft_cap\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureWorkerSoftCap : 0).AppendLine(",");
                sb.Append("  \"worker_hard_cap\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureWorkerHardCap : 0).AppendLine(",");
                sb.Append("  \"worker_produce_attempts\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureWorkerProduceAttempts : 0).AppendLine(",");
                sb.Append("  \"worker_produce_blocked_by_cap\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureWorkerProduceBlockedByCap : 0).AppendLine(",");
                sb.Append("  \"worker_idle_steps\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureWorkerIdleSteps : 0).AppendLine(",");
                sb.Append("  \"worker_gather_attempts\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureWorkerGatherAttempts : 0).AppendLine(",");
                sb.Append("  \"worker_build_attempts\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureWorkerBuildAttempts : 0).AppendLine(",");
                sb.Append("  \"barracks_count\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureBarracksCount : 0).AppendLine(",");
                sb.Append("  \"barracks_build_attempts\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureBarracksBuildAttempts : 0).AppendLine(",");
                sb.Append("  \"barracks_build_accepted\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureBarracksBuildAccepted : 0).AppendLine(",");
                sb.Append("  \"combat_unit_count_min\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCombatCountMin : 0).AppendLine(",");
                sb.Append("  \"combat_unit_count_max\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCombatCountMax : 0).AppendLine(",");
                sb.Append("  \"combat_unit_count_final\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCombatCountFinal : 0).AppendLine(",");
                sb.Append("  \"combat_unit_produce_attempts\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCombatProduceAttempts : 0).AppendLine(",");
                sb.Append("  \"combat_unit_produce_accepted\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCombatProduceAccepted : 0).AppendLine(",");
                sb.Append("  \"light_produce_attempts\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureLightProduceAttempts : 0).AppendLine(",");
                sb.Append("  \"heavy_produce_attempts\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureHeavyProduceAttempts : 0).AppendLine(",");
                sb.Append("  \"heavy_produce_accepted\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureHeavyProduceAccepted : 0).AppendLine(",");
                sb.Append("  \"heavy_produce_blocked_by_cap\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureHeavyProduceBlockedByCap : 0).AppendLine(",");
                sb.Append("  \"heavy_produce_blocked_by_cooldown\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureHeavyProduceBlockedByCooldown : 0).AppendLine(",");
                sb.Append("  \"consecutive_heavy_produce_attempts\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureConsecutiveHeavyProduceAttempts : 0).AppendLine(",");
                sb.Append("  \"ranged_produce_attempts\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureRangedProduceAttempts : 0).AppendLine(",");
                sb.Append("  \"light_count_max\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureLightCountMax : 0).AppendLine(",");
                sb.Append("  \"heavy_count_max\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureHeavyCountMax : 0).AppendLine(",");
                sb.Append("  \"ranged_count_max\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureRangedCountMax : 0).AppendLine(",");
                sb.Append("  \"total_army_count_max\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureTotalArmyCountMax : 0).AppendLine(",");
                sb.Append("  \"light_hard_cap\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureLightHardCap : 0).AppendLine(",");
                sb.Append("  \"heavy_hard_cap\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureHeavyHardCap : 0).AppendLine(",");
                sb.Append("  \"ranged_hard_cap\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureRangedHardCap : 0).AppendLine(",");
                sb.Append("  \"combat_unit_cap\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCombatUnitCap : 0).AppendLine(",");
                sb.Append("  \"total_army_cap\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureTotalArmyCap : 0).AppendLine(",");
                sb.Append("  \"attack_wave_size_min\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureAttackWaveSizeMin : 0).AppendLine(",");
                sb.Append("  \"attack_wave_size_max\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureAttackWaveSizeMax : 0).AppendLine(",");
                sb.Append("  \"attack_wave_size_at_first_attack\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureAttackWaveSizeAtFirstAttack : -1).AppendLine(",");
                sb.Append("  \"combat_units_sent_to_center\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCombatUnitsSentToCenter : 0).AppendLine(",");
                sb.Append("  \"combat_units_kept_near_base\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCombatUnitsKeptNearBase : 0).AppendLine(",");
                sb.Append("  \"over_army_cap_steps\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureOverArmyCapSteps : 0).AppendLine(",");
                sb.Append("  \"central_corridor_steps\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCentralCorridorSteps : 0).AppendLine(",");
                sb.Append("  \"center_area_steps\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCenterAreaSteps : 0).AppendLine(",");
                sb.Append("  \"edge_lane_steps\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureEdgeLaneSteps : 0).AppendLine(",");
                sb.Append("  \"base_area_steps\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureBaseAreaSteps : 0).AppendLine(",");
                sb.Append("  \"center_crossing_count\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCenterCrossingCount : 0).AppendLine(",");
                sb.Append("  \"wave_crossed_center\": ").Append(_attachedAdapter != null && _attachedAdapter.CenterPressureWaveCrossedCenter ? "true" : "false").AppendLine(",");
                sb.Append("  \"center_crossing_step\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCenterCrossingStep : -1).AppendLine(",");
                sb.Append("  \"attack_after_center_crossing\": ").Append(_attachedAdapter != null && _attachedAdapter.CenterPressureAttackAfterCenterCrossing ? "true" : "false").AppendLine(",");
                sb.Append("  \"first_attack_after_center_crossing_step\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureFirstAttackAfterCenterCrossingStep : -1).AppendLine(",");
                sb.Append("  \"edge_attack_detected\": ").Append(_attachedAdapter != null && _attachedAdapter.CenterPressureEdgeAttackDetected ? "true" : "false").AppendLine(",");
                sb.Append("  \"edge_attack_count\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureEdgeAttackCount : 0).AppendLine(",");
                sb.Append("  \"central_approach_moves\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCentralApproachMoves : 0).AppendLine(",");
                sb.Append("  \"edge_approach_moves\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureEdgeApproachMoves : 0).AppendLine(",");
                sb.Append("  \"central_route_ratio\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCentralRouteRatio.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture) : "0").AppendLine(",");
                sb.Append("  \"edge_route_ratio\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureEdgeRouteRatio.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture) : "0").AppendLine(",");
                sb.Append("  \"center_route_dominant\": ").Append(_attachedAdapter != null && _attachedAdapter.CenterPressureRouteDominant ? "true" : "false").AppendLine(",");
                sb.Append("  \"first_center_move_step\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureFirstCenterMoveStep : -1).AppendLine(",");
                sb.Append("  \"first_attack_step_center_profile\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureFirstAttackStep : -1).AppendLine(",");
                sb.Append("  \"attack_intent_count\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureAttackIntentCount : 0).AppendLine(",");
                sb.Append("  \"attack_submit_count\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureAttackSubmitCount : 0).AppendLine(",");
                sb.Append("  \"accepted_attack_count\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureAcceptedAttackCount : 0).AppendLine(",");
                sb.Append("  \"first_attack_intent_step\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureFirstAttackIntentStep : -1).AppendLine(",");
                sb.Append("  \"first_attack_submit_step\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureFirstAttackSubmitStep : -1).AppendLine(",");
                sb.Append("  \"first_accepted_attack_step\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureFirstAcceptedAttackStep : -1).AppendLine(",");
                sb.Append("  \"center_attack_intent_count\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCenterAttackIntentCount : 0).AppendLine(",");
                sb.Append("  \"center_attack_submit_count\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCenterAttackSubmitCount : 0).AppendLine(",");
                sb.Append("  \"center_accepted_attack_count\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureCenterAcceptedAttackCount : 0).AppendLine(",");
                sb.Append("  \"avg_combat_distance_to_center\": ").Append(_attachedAdapter != null ? _attachedAdapter.CenterPressureAverageCombatDistanceToCenter.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture) : "0").AppendLine(",");
                sb.Append("  \"permanent_base_idle\": ").Append(_attachedAdapter != null && _attachedAdapter.CenterPressurePermanentBaseIdle ? "true" : "false").AppendLine(",");
                sb.Append("  \"center_pressure_observed\": ").Append(_attachedAdapter != null && _attachedAdapter.CenterPressureObserved ? "true" : "false").AppendLine(",");
                sb.Append("  \"economy_composition_healthy\": ").Append(_attachedAdapter != null && _attachedAdapter.CenterPressureEconomyCompositionHealthy ? "true" : "false").AppendLine(",");
                sb.AppendLine("  \"stage6b3_files_touched\": []");
                sb.AppendLine("}");

                File.WriteAllText(fullPath, sb.ToString(), Encoding.UTF8);
            }
            catch (Exception ex)
            {
                Debug.LogWarning($"[Stage7B] Failed to write scripted bot throttle report: {ex.Message}");
            }
        }

        private string ResolveReportPath()
        {
            string relative = string.IsNullOrWhiteSpace(_reportRelativePath)
                ? "python/stage7b_teacher_replay/stage7b_week7_scripted_bot_throttle_report.json"
                : _reportRelativePath.Replace('\\', '/');

            if (Path.IsPathRooted(relative))
            {
                return relative;
            }

            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName ?? Application.dataPath;
            return Path.Combine(projectRoot, relative.Replace('/', Path.DirectorySeparatorChar));
        }

        private static string EscapeJson(string value)
        {
            return value
                .Replace("\\", "\\\\")
                .Replace("\"", "\\\"")
                .Replace("\r", "\\r")
                .Replace("\n", "\\n")
                .Replace("\t", "\\t");
        }

        private void OnDestroy()
        {
            DetachAdapterHooks();
        }
    }
}
