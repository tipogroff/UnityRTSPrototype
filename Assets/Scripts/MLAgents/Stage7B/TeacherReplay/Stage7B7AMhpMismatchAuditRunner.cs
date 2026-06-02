using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using RTS.Core;
using RTS.Gameplay;
using RTS.ML;
using RTS.MLAgents.Stage7B.CandidateActions;
using UnityEngine;

namespace RTS.MLAgents.Stage7B.TeacherReplay
{
    [DisallowMultipleComponent]
    public sealed class Stage7B7AMhpMismatchAuditRunner : MonoBehaviour
    {
        private const string SourceDir =
            "python/week5_teacher_legacy032/teacher_replay_exports/stage7b_replay_ready_stage7b6j_return_direction_audit_e8_s512_20260510T174822Z";

        private const string ReportJsonPath = "python/stage7b_teacher_replay/stage7b_7a_mhp_mismatch_audit_report.json";
        private const string ReportMdPath = "python/stage7b_teacher_replay/stage7b_7a_mhp_mismatch_audit_report.md";
        private const string MoveMismatchesPath = "python/stage7b_teacher_replay/stage7b_7a_move_mismatches.jsonl";
        private const string HarvestMismatchesPath = "python/stage7b_teacher_replay/stage7b_7a_harvest_mismatches.jsonl";
        private const string ProduceMismatchesPath = "python/stage7b_teacher_replay/stage7b_7a_produce_mismatches.jsonl";
        private const string RuntimeApplyTracePath = "python/stage7b_teacher_replay/stage7b_7a_runtime_apply_trace.jsonl";

        [SerializeField] private Owner _playerPerspective = Owner.Player1;

        private readonly Stage7BTeacherTrajectoryLoader _loader = new Stage7BTeacherTrajectoryLoader();

        [ContextMenu("Run Stage7B-7A M/H/P Mismatch Audit")]
        public void RunStage7B7AMhpMismatchAudit()
        {
            var report = Stage7B7AMhpMismatchAuditReport.CreateDefault();
            report.generated_at_utc = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ");
            report.source_path = SourceDir;
            report.summary = "Stage7B-7A Move/Harvest/Produce mismatch audit.";
            report.notes.Add("Audit-only: no ML-Agents training, PPO, imitation learning, or large .demo recording was started.");
            report.notes.Add("Teacher policy, reward, ActionApplier, MatchManager, and MlAgentsCandidateActionBuilder were not modified by this runner.");
            report.notes.Add("Return direction mapping remains the Stage7B-6K return-only fix; Move/Harvest/Produce mapping is only measured.");

            var moveLines = new List<string>(256);
            var harvestLines = new List<string>(64);
            var produceLines = new List<string>(320);
            var applyTraceLines = new List<string>(4096);

            if (!_loader.TryLoadReplayManifest(SourceDir, out Stage7BTeacherReplayManifest manifest, out string manifestDiag))
            {
                report.status = "NO_GO";
                report.notes.Add("Failed to load replay manifest: " + manifestDiag);
                WriteArtifacts(report, moveLines, harvestLines, produceLines, applyTraceLines);
                return;
            }

            List<string> contractErrors = ValidateManifest(manifest);
            if (contractErrors.Count > 0)
            {
                report.contract_error_count = contractErrors.Count;
                report.notes.Add("Manifest contract mismatch: " + string.Join("; ", contractErrors));
            }

            if (!manifest.replay_ready)
            {
                report.contract_error_count++;
                report.notes.Add("Manifest replay_ready=false.");
            }

            if (!_loader.TryLoadReplayReadyJsonl(SourceDir, out List<Stage7BTeacherTrajectoryStep> steps, out string loadDiag))
            {
                report.status = "NO_GO";
                report.notes.Add("Failed to load replay_ready JSONL: " + loadDiag);
                WriteArtifacts(report, moveLines, harvestLines, produceLines, applyTraceLines);
                return;
            }

            var episodeIds = new HashSet<int>();
            for (int i = 0; i < steps.Count; i++)
            {
                episodeIds.Add(steps[i].episodeId);
            }

            report.episodes_scanned = episodeIds.Count;
            report.steps_total = steps.Count;

            MatchManager match = MatchManager.Instance;
            GridManager grid = GridManager.Instance;
            UnitRegistry registry = UnitRegistry.Instance;
            MatchBootstrap bootstrap = MatchBootstrap.Instance;
            ResourceManager resources = ResourceManager.Instance;

            if (match == null || grid == null || registry == null || bootstrap == null || resources == null)
            {
                report.status = "NO_GO";
                report.notes.Add("Unity runtime service missing. Open Week7 scene first.");
                WriteArtifacts(report, moveLines, harvestLines, produceLines, applyTraceLines);
                return;
            }

            var synchronizer = new Stage7BTeacherReplayStateSynchronizer(match, grid, registry, bootstrap, resources);
            var resolver = new Stage7BTeacherReplayActionResolver();
            var matcher = new Stage7BTeacherReplayCandidateMatcher();
            var actionApplier = new ActionApplier(grid, registry, match, resources);
            var candidateCounts = new List<int>(steps.Count);

            for (int stepIndex = 0; stepIndex < steps.Count; stepIndex++)
            {
                Stage7BTeacherTrajectoryStep step = steps[stepIndex];

                if (!step.HasRuntimeStateTJson)
                {
                    report.state_sync_failed_count++;
                    continue;
                }

                if (!synchronizer.TrySynchronizeRuntimeState(
                        step.runtime_state_t_json,
                        out Stage7BTeacherReplayDropReason syncDrop,
                        out string syncDiagnostics))
                {
                    report.state_sync_failed_count++;
                    AddHistogram(report.state_sync_failure_reasons, ToSnakeCase(syncDrop) + ":" + syncDiagnostics);
                    continue;
                }

                report.state_sync_success_count++;

                var maskBuilder = new ActionMaskBuilder(match, grid, resources, registry, bootstrap);
                var candidateBuilder = new MlAgentsCandidateActionBuilder(maskBuilder);
                MlAgentsCandidateActionList candidates = candidateBuilder.Build(_playerPerspective);
                candidateCounts.Add(candidates.CandidateCount);

                Stage7BTeacherReplayTeacherCommand[] commands = GetTeacherCommands(step);
                if (commands == null || commands.Length == 0)
                {
                    report.no_teacher_command_steps++;
                    continue;
                }

                bool stepHadApply = false;

                for (int commandIndex = 0; commandIndex < commands.Length; commandIndex++)
                {
                    Stage7BTeacherReplayTeacherCommand command = commands[commandIndex];
                    report.teacher_commands_total++;
                    IncrementActionTotal(report, command.action_type);

                    var applyTrace = new Stage7B7ARuntimeApplyTraceEntry
                    {
                        episode_id = step.episodeId,
                        step_id = step.stepId,
                        command_index = commandIndex,
                        actor_flat = command.actor_flat,
                        actor_x = command.actor_x,
                        actor_y = command.actor_y,
                        action_type = command.action_type,
                        action_type_name = ActionTypeToString(command.action_type),
                    };

                    if (!resolver.TryResolveTeacherCommand(command, _playerPerspective, out AgentAction teacherAction, out Stage7BTeacherReplayDropReason resolveDrop))
                    {
                        applyTrace.action_summary = "resolve_failed:" + ToSnakeCase(resolveDrop);
                        applyTraceLines.Add(JsonUtility.ToJson(applyTrace));
                        continue;
                    }

                    applyTrace.teacher_dir = teacherAction.Direction.ToString();
                    applyTrace.action_summary = BuildActionSummary(teacherAction);

                    if (!matcher.TryMatch(teacherAction, candidates, out int candidateIndex, out Stage7BTeacherReplayDropReason matchDrop))
                    {
                        string nearestReason = BuildNearestCandidateDetails(
                            teacherAction,
                            candidates,
                            out bool hasCandidateDir,
                            out Direction candidateDir,
                            out int candidateProduceType);

                        applyTrace.nearest_candidate_reason = nearestReason;
                        applyTrace.nearest_candidate_dir = hasCandidateDir ? candidateDir.ToString() : "none";
                        applyTrace.action_summary += " | match_failed:" + ToSnakeCase(matchDrop) + " nearest:" + nearestReason;
                        applyTraceLines.Add(JsonUtility.ToJson(applyTrace));

                        if (IsMhpAction(command.action_type))
                        {
                            Stage7B7AMismatchEntry mismatch = BuildMismatchEntry(
                                step,
                                commandIndex,
                                command,
                                teacherAction,
                                candidates,
                                matchDrop,
                                nearestReason,
                                hasCandidateDir,
                                candidateDir,
                                candidateProduceType,
                                grid,
                                resources);

                            RecordMismatch(report, mismatch, moveLines, harvestLines, produceLines);
                        }

                        continue;
                    }

                    report.candidate_match_count++;
                    IncrementActionMatched(report, command.action_type);
                    applyTrace.candidate_match = true;
                    applyTrace.candidate_action_index = candidateIndex;

                    report.runtime_apply_attempted_count++;
                    applyTrace.runtime_apply_attempted = true;
                    bool applied = actionApplier.ApplyAction(teacherAction, _playerPerspective);
                    applyTrace.runtime_apply_accepted = applied;

                    if (applied)
                    {
                        report.runtime_apply_accepted_count++;
                        stepHadApply = true;
                    }
                    else
                    {
                        report.runtime_apply_rejected_count++;
                        string rejectReason = "unknown";
                        if (actionApplier.RejectionReasonsLastStep != null && actionApplier.RejectionReasonsLastStep.Count > 0)
                        {
                            rejectReason = actionApplier.RejectionReasonsLastStep[0];
                        }

                        applyTrace.reject_reason = rejectReason;
                        AddHistogram(report.runtime_reject_reason_histogram, rejectReason);
                    }

                    applyTraceLines.Add(JsonUtility.ToJson(applyTrace));
                }

                if (stepHadApply)
                {
                    match.StepMatch();
                }
            }

            FinalizeReport(report, candidateCounts);

            bool go = report.contract_error_count == 0
                && report.state_sync_failed_count == 0
                && report.runtime_apply_attempted_count > 0
                && report.runtime_apply_accept_rate >= 0.99f;

            bool holdForMapping = report.mhp_direction_mismatch_count > 0
                && report.mhp_y_axis_flip_rate >= 0.75f
                && report.mhp_y_axis_flip_count > report.mhp_x_axis_flip_count;

            report.direction_pattern_conclusion = BuildDirectionConclusion(report);
            report.decision = go && !holdForMapping
                ? "GO_TO_STAGE7B_8_SMALL_IMMITATION_SMOKE"
                : "HOLD_FOR_STAGE7B_7B_MAPPING_FIX";
            report.status = go ? "GO" : "NO_GO";

            if (holdForMapping)
            {
                report.notes.Add("M/H/P direction mismatches show a dominant Y-axis pattern; hold before large dataset and run Stage7B-7B mapping fix proposal.");
            }
            else
            {
                report.notes.Add("No dominant M/H/P Y-axis mapping pattern under the configured threshold; Stage7B-8 small imitation smoke is allowed, large export must still record drop rates.");
            }

            report.notes.Add("Stage6B3 baseline/checkpoint assets were not modified by this runner.");
            WriteArtifacts(report, moveLines, harvestLines, produceLines, applyTraceLines);
        }

        private void WriteArtifacts(
            Stage7B7AMhpMismatchAuditReport report,
            List<string> moveLines,
            List<string> harvestLines,
            List<string> produceLines,
            List<string> applyTraceLines)
        {
            _loader.TrySaveText(MoveMismatchesPath, string.Join("\n", moveLines), out _);
            _loader.TrySaveText(HarvestMismatchesPath, string.Join("\n", harvestLines), out _);
            _loader.TrySaveText(ProduceMismatchesPath, string.Join("\n", produceLines), out _);
            _loader.TrySaveText(RuntimeApplyTracePath, string.Join("\n", applyTraceLines), out _);
            _loader.TrySaveText(ReportJsonPath, JsonUtility.ToJson(report, true), out string jsonPath);
            _loader.TrySaveText(ReportMdPath, BuildMarkdown(report), out _);
            Debug.Log("[Stage7B][7A] M/H/P mismatch audit report written: " + jsonPath);
        }

        private static void FinalizeReport(Stage7B7AMhpMismatchAuditReport report, List<int> candidateCounts)
        {
            report.candidate_drop_count = Math.Max(0, report.teacher_commands_total - report.candidate_match_count);
            report.candidate_match_rate = SafeRate(report.candidate_match_count, report.teacher_commands_total);
            report.runtime_apply_accept_rate = SafeRate(report.runtime_apply_accepted_count, report.runtime_apply_attempted_count);

            report.move_commands_dropped = Math.Max(0, report.move_commands_total - report.move_commands_matched);
            report.harvest_commands_dropped = Math.Max(0, report.harvest_commands_total - report.harvest_commands_matched);
            report.produce_commands_dropped = Math.Max(0, report.produce_commands_total - report.produce_commands_matched);

            report.move_match_rate = SafeRate(report.move_commands_matched, report.move_commands_total);
            report.harvest_match_rate = SafeRate(report.harvest_commands_matched, report.harvest_commands_total);
            report.produce_match_rate = SafeRate(report.produce_commands_matched, report.produce_commands_total);

            report.move_direction_mismatch_rate = SafeRate(report.move_direction_mismatch_count, report.move_commands_total);
            report.harvest_direction_mismatch_rate = SafeRate(report.harvest_direction_mismatch_count, report.harvest_commands_total);
            report.produce_direction_mismatch_rate = SafeRate(report.produce_direction_mismatch_count, report.produce_commands_total);

            report.mhp_direction_mismatch_count =
                report.move_direction_mismatch_count
                + report.harvest_direction_mismatch_count
                + report.produce_direction_mismatch_count;
            report.mhp_opposite_direction_count =
                report.move_opposite_direction_count
                + report.harvest_opposite_direction_count
                + report.produce_opposite_direction_count;
            report.mhp_y_axis_flip_count =
                report.move_y_axis_flip_count
                + report.harvest_y_axis_flip_count
                + report.produce_y_axis_flip_count;
            report.mhp_x_axis_flip_count =
                report.move_x_axis_flip_count
                + report.harvest_x_axis_flip_count
                + report.produce_x_axis_flip_count;
            report.mhp_y_axis_flip_rate = SafeRate(report.mhp_y_axis_flip_count, report.mhp_direction_mismatch_count);
            report.mhp_x_axis_flip_rate = SafeRate(report.mhp_x_axis_flip_count, report.mhp_direction_mismatch_count);

            if (candidateCounts.Count > 0)
            {
                int min = candidateCounts[0];
                int max = candidateCounts[0];
                int sum = 0;
                for (int i = 0; i < candidateCounts.Count; i++)
                {
                    int v = candidateCounts[i];
                    if (v < min) min = v;
                    if (v > max) max = v;
                    sum += v;
                }

                report.candidate_count_min = min;
                report.candidate_count_max = max;
                report.candidate_count_mean = (float)sum / candidateCounts.Count;
            }
        }

        private static Stage7B7AMismatchEntry BuildMismatchEntry(
            Stage7BTeacherTrajectoryStep step,
            int commandIndex,
            Stage7BTeacherReplayTeacherCommand command,
            AgentAction teacherAction,
            MlAgentsCandidateActionList candidates,
            Stage7BTeacherReplayDropReason dropReason,
            string nearestReason,
            bool hasCandidateDir,
            Direction candidateDir,
            int candidateProduceType,
            GridManager grid,
            ResourceManager resources)
        {
            Direction teacherDir = teacherAction.Direction;
            GridPosition actorPos = teacherAction.ActorPosition;
            GridPosition teacherTarget = actorPos.Neighbour(teacherDir);
            GridPosition unityTarget = hasCandidateDir ? actorPos.Neighbour(candidateDir) : new GridPosition(-1, -1);

            bool teacherInside = grid != null && grid.IsInside(teacherTarget);
            bool unityInside = grid != null && hasCandidateDir && grid.IsInside(unityTarget);
            UnitRuntime teacherOccupant = teacherInside ? grid.GetOccupant(teacherTarget) : null;
            UnitRuntime unityOccupant = unityInside ? grid.GetOccupant(unityTarget) : null;
            bool teacherOccupied = teacherOccupant != null;
            bool unityOccupied = unityOccupant != null;
            bool teacherHasResource = teacherInside && HasActiveResource(resources, teacherTarget);
            bool unityHasResource = unityInside && HasActiveResource(resources, unityTarget);

            bool teacherExpected = HasExpectedObjectForAction(teacherAction.ActionType, teacherInside, teacherOccupied, teacherHasResource);
            bool unityExpected = HasExpectedObjectForAction(teacherAction.ActionType, unityInside, unityOccupied, unityHasResource);

            bool isOpposite = hasCandidateDir && IsOppositeDirection(teacherDir, candidateDir);
            bool isYFlip = hasCandidateDir && IsYAxisFlip(teacherDir, candidateDir);
            bool isXFlip = hasCandidateDir && IsXAxisFlip(teacherDir, candidateDir);
            bool mappingLike = isOpposite && !teacherExpected && unityExpected;
            bool legalityDivergence = !teacherExpected;

            return new Stage7B7AMismatchEntry
            {
                episode_id = step.episodeId,
                step_id = step.stepId,
                command_index = commandIndex,
                actor_flat = command.actor_flat,
                actor_x = command.actor_x,
                actor_y = command.actor_y,
                action_type = command.action_type,
                action_type_name = ActionTypeToString(command.action_type),
                teacher_dir = teacherDir.ToString(),
                nearest_candidate_dir = hasCandidateDir ? candidateDir.ToString() : "none",
                teacher_target_x = teacherTarget.X,
                teacher_target_y = teacherTarget.Y,
                unity_candidate_target_x = unityTarget.X,
                unity_candidate_target_y = unityTarget.Y,
                teacher_target_inside_map = teacherInside,
                unity_candidate_target_inside_map = unityInside,
                teacher_target_occupied = teacherOccupied,
                unity_candidate_target_occupied = unityOccupied,
                teacher_target_occupant_type = UnitTypeName(teacherOccupant),
                unity_candidate_target_occupant_type = UnitTypeName(unityOccupant),
                teacher_target_has_resource = teacherHasResource,
                unity_candidate_target_has_resource = unityHasResource,
                teacher_target_has_expected_object = teacherExpected,
                unity_candidate_target_has_expected_object = unityExpected,
                expected_object_rule = ExpectedObjectRule(teacherAction.ActionType),
                is_opposite_direction = isOpposite,
                is_y_axis_flip = isYFlip,
                is_x_axis_flip = isXFlip,
                mapping_like_candidate_target = mappingLike,
                legality_or_state_divergence = legalityDivergence,
                drop_reason = ToSnakeCase(dropReason),
                nearest_candidate_reason = nearestReason,
                teacher_produce_unit_type = (int)teacherAction.ProduceUnitType,
                nearest_candidate_produce_unit_type = candidateProduceType,
                candidate_count = candidates != null ? candidates.CandidateCount : 0,
                teacher_command_json = JsonUtility.ToJson(command),
                candidate_list_summary = BuildCandidateListSummary(candidates),
            };
        }

        private static string BuildNearestCandidateDetails(
            AgentAction teacherAction,
            MlAgentsCandidateActionList candidates,
            out bool hasCandidateDir,
            out Direction candidateDir,
            out int candidateProduceType)
        {
            hasCandidateDir = false;
            candidateDir = Direction.North;
            candidateProduceType = -1;

            if (candidates == null || candidates.AvailableCandidates.Count == 0)
            {
                return "no_candidates_available";
            }

            bool actorFound = false;
            bool actionTypeFound = false;
            MlAgentsCandidateAction firstSameType = default;
            bool hasFirstSameType = false;

            for (int i = 0; i < candidates.AvailableCandidates.Count; i++)
            {
                MlAgentsCandidateAction c = candidates.AvailableCandidates[i];
                if (c.IsEmpty) continue;
                if (c.Action.ActorPosition != teacherAction.ActorPosition) continue;

                actorFound = true;
                if (c.Action.ActionType != teacherAction.ActionType) continue;

                actionTypeFound = true;
                if (!hasFirstSameType)
                {
                    firstSameType = c;
                    hasFirstSameType = true;
                }

                if (teacherAction.ActionType == UnitActionType.Produce)
                {
                    if (c.Action.Direction != teacherAction.Direction
                        && (int)c.Action.ProduceUnitType == (int)teacherAction.ProduceUnitType)
                    {
                        hasCandidateDir = true;
                        candidateDir = c.Action.Direction;
                        candidateProduceType = (int)c.Action.ProduceUnitType;
                        return "produce_direction_mismatch (teacher_dir=" + teacherAction.Direction + ", cand_dir=" + c.Action.Direction + ")";
                    }

                    if (c.Action.Direction == teacherAction.Direction
                        && (int)c.Action.ProduceUnitType != (int)teacherAction.ProduceUnitType)
                    {
                        hasCandidateDir = true;
                        candidateDir = c.Action.Direction;
                        candidateProduceType = (int)c.Action.ProduceUnitType;
                        return "produce_type_mismatch (teacher=" + teacherAction.ProduceUnitType + ", cand=" + c.Action.ProduceUnitType + ")";
                    }
                }
                else if (c.Action.Direction != teacherAction.Direction)
                {
                    hasCandidateDir = true;
                    candidateDir = c.Action.Direction;
                    candidateProduceType = (int)c.Action.ProduceUnitType;
                    return "direction_mismatch (actor=" + teacherAction.ActorPosition
                        + ", type=" + teacherAction.ActionType
                        + ", teacher_dir=" + teacherAction.Direction
                        + ", cand_dir=" + c.Action.Direction + ")";
                }
            }

            if (hasFirstSameType)
            {
                hasCandidateDir = true;
                candidateDir = firstSameType.Action.Direction;
                candidateProduceType = (int)firstSameType.Action.ProduceUnitType;
                return "parameter_mismatch (actor and type found but no preferred nearest candidate)";
            }

            if (!actorFound) return "actor_missing_from_candidates (actor=" + teacherAction.ActorPosition + ")";
            if (!actionTypeFound) return "action_type_missing_from_candidates (actor=" + teacherAction.ActorPosition + ", type=" + teacherAction.ActionType + ")";
            return "parameter_mismatch";
        }

        private static void RecordMismatch(
            Stage7B7AMhpMismatchAuditReport report,
            Stage7B7AMismatchEntry mismatch,
            List<string> moveLines,
            List<string> harvestLines,
            List<string> produceLines)
        {
            bool directionMismatch = mismatch.nearest_candidate_reason != null
                && (mismatch.nearest_candidate_reason.StartsWith("direction_mismatch", StringComparison.Ordinal)
                    || mismatch.nearest_candidate_reason.StartsWith("produce_direction_mismatch", StringComparison.Ordinal));
            bool typeMismatch = mismatch.nearest_candidate_reason != null
                && mismatch.nearest_candidate_reason.StartsWith("produce_type_mismatch", StringComparison.Ordinal);

            if (mismatch.action_type == 1)
            {
                moveLines.Add(JsonUtility.ToJson(mismatch));
                if (directionMismatch) report.move_direction_mismatch_count++;
                if (mismatch.is_opposite_direction) report.move_opposite_direction_count++;
                if (mismatch.is_y_axis_flip) report.move_y_axis_flip_count++;
                if (mismatch.is_x_axis_flip) report.move_x_axis_flip_count++;
                if (mismatch.mapping_like_candidate_target) report.move_mapping_like_count++;
                if (mismatch.legality_or_state_divergence) report.move_legality_or_state_divergence_count++;
                AddHistogram(report.move_mismatch_by_teacher_dir, mismatch.teacher_dir);
                AddHistogram(report.move_mismatch_by_candidate_dir, mismatch.nearest_candidate_dir);
                AddFirst10(report.first_10_move_mismatches, mismatch);
            }
            else if (mismatch.action_type == 2)
            {
                harvestLines.Add(JsonUtility.ToJson(mismatch));
                if (directionMismatch) report.harvest_direction_mismatch_count++;
                if (mismatch.is_opposite_direction) report.harvest_opposite_direction_count++;
                if (mismatch.is_y_axis_flip) report.harvest_y_axis_flip_count++;
                if (mismatch.is_x_axis_flip) report.harvest_x_axis_flip_count++;
                if (mismatch.mapping_like_candidate_target) report.harvest_mapping_like_count++;
                if (mismatch.legality_or_state_divergence) report.harvest_legality_or_state_divergence_count++;
                AddHistogram(report.harvest_mismatch_by_teacher_dir, mismatch.teacher_dir);
                AddHistogram(report.harvest_mismatch_by_candidate_dir, mismatch.nearest_candidate_dir);
                AddFirst10(report.first_10_harvest_mismatches, mismatch);
            }
            else if (mismatch.action_type == 4)
            {
                produceLines.Add(JsonUtility.ToJson(mismatch));
                if (directionMismatch) report.produce_direction_mismatch_count++;
                if (typeMismatch) report.produce_type_mismatch_count++;
                if (mismatch.is_opposite_direction) report.produce_opposite_direction_count++;
                if (mismatch.is_y_axis_flip) report.produce_y_axis_flip_count++;
                if (mismatch.is_x_axis_flip) report.produce_x_axis_flip_count++;
                if (mismatch.mapping_like_candidate_target) report.produce_mapping_like_count++;
                if (mismatch.legality_or_state_divergence) report.produce_legality_or_state_divergence_count++;
                AddHistogram(report.produce_mismatch_by_teacher_dir, mismatch.teacher_dir);
                AddHistogram(report.produce_mismatch_by_candidate_dir, mismatch.nearest_candidate_dir);
                AddFirst10(report.first_10_produce_mismatches, mismatch);
            }
        }

        private static void AddFirst10(List<string> target, Stage7B7AMismatchEntry mismatch)
        {
            if (target.Count >= 10) return;
            target.Add("ep=" + mismatch.episode_id
                + ",step=" + mismatch.step_id
                + ",cmd=" + mismatch.command_index
                + ",actor=(" + mismatch.actor_x + "," + mismatch.actor_y + ")"
                + ",teacher_dir=" + mismatch.teacher_dir
                + ",candidate_dir=" + mismatch.nearest_candidate_dir
                + ",teacher_target=(" + mismatch.teacher_target_x + "," + mismatch.teacher_target_y + ")"
                + ",unity_target=(" + mismatch.unity_candidate_target_x + "," + mismatch.unity_candidate_target_y + ")"
                + ",teacher_expected=" + mismatch.teacher_target_has_expected_object
                + ",unity_expected=" + mismatch.unity_candidate_target_has_expected_object
                + ",nearest=" + mismatch.nearest_candidate_reason);
        }

        private static bool HasExpectedObjectForAction(UnitActionType actionType, bool inside, bool occupied, bool hasResource)
        {
            if (!inside) return false;
            switch (actionType)
            {
                case UnitActionType.Move:
                case UnitActionType.Produce:
                    return !occupied;
                case UnitActionType.Harvest:
                    return hasResource;
                default:
                    return false;
            }
        }

        private static string ExpectedObjectRule(UnitActionType actionType)
        {
            switch (actionType)
            {
                case UnitActionType.Move: return "free_cell";
                case UnitActionType.Harvest: return "active_resource";
                case UnitActionType.Produce: return "spawn_cell_free";
                default: return "not_applicable";
            }
        }

        private static bool HasActiveResource(ResourceManager resources, GridPosition pos)
        {
            ResourceNode node = resources != null ? resources.GetResourceNode(pos) : null;
            return node != null && !node.IsExhausted;
        }

        private static void IncrementActionTotal(Stage7B7AMhpMismatchAuditReport report, int actionType)
        {
            if (actionType == 1) report.move_commands_total++;
            else if (actionType == 2) report.harvest_commands_total++;
            else if (actionType == 4) report.produce_commands_total++;
        }

        private static void IncrementActionMatched(Stage7B7AMhpMismatchAuditReport report, int actionType)
        {
            if (actionType == 1) report.move_commands_matched++;
            else if (actionType == 2) report.harvest_commands_matched++;
            else if (actionType == 4) report.produce_commands_matched++;
        }

        private static bool IsMhpAction(int actionType)
        {
            return actionType == 1 || actionType == 2 || actionType == 4;
        }

        private static float SafeRate(int numerator, int denominator)
        {
            return denominator > 0 ? (float)numerator / denominator : -1f;
        }

        private static string BuildDirectionConclusion(Stage7B7AMhpMismatchAuditReport report)
        {
            if (report.mhp_direction_mismatch_count == 0)
            {
                return "no_direction_mismatches";
            }

            if (report.mhp_y_axis_flip_rate >= 0.75f && report.mhp_y_axis_flip_count > report.mhp_x_axis_flip_count)
            {
                return "dominant_y_axis_flip";
            }

            if (report.mhp_x_axis_flip_rate >= 0.75f && report.mhp_x_axis_flip_count > report.mhp_y_axis_flip_count)
            {
                return "dominant_x_axis_flip";
            }

            if (report.mhp_opposite_direction_count == report.mhp_direction_mismatch_count)
            {
                return "opposite_direction_mixed_axes";
            }

            return "mixed_or_legality_state_divergence";
        }

        private static string BuildMarkdown(Stage7B7AMhpMismatchAuditReport r)
        {
            var sb = new StringBuilder(4096);
            sb.AppendLine("# Stage7B-7A Move / Harvest / Produce Mismatch Audit");
            sb.AppendLine();
            sb.AppendLine("- status: " + r.status);
            sb.AppendLine("- decision: " + r.decision);
            sb.AppendLine("- generated_at_utc: " + r.generated_at_utc);
            sb.AppendLine("- source: " + r.source_path);
            sb.AppendLine();
            sb.AppendLine("## General Metrics");
            sb.AppendLine();
            sb.AppendLine("- episodes_scanned: " + r.episodes_scanned);
            sb.AppendLine("- steps_total: " + r.steps_total);
            sb.AppendLine("- teacher_commands_total: " + r.teacher_commands_total);
            sb.AppendLine("- candidate_match_count: " + r.candidate_match_count);
            sb.AppendLine("- candidate_drop_count: " + r.candidate_drop_count);
            sb.AppendLine("- candidate_match_rate: " + ValueOrNull(r.candidate_match_rate));
            sb.AppendLine("- runtime_apply_attempted_count: " + r.runtime_apply_attempted_count);
            sb.AppendLine("- runtime_apply_accepted_count: " + r.runtime_apply_accepted_count);
            sb.AppendLine("- runtime_apply_rejected_count: " + r.runtime_apply_rejected_count);
            sb.AppendLine("- runtime_apply_accept_rate: " + ValueOrNull(r.runtime_apply_accept_rate));
            sb.AppendLine("- state_sync_success_count: " + r.state_sync_success_count);
            sb.AppendLine("- state_sync_failed_count: " + r.state_sync_failed_count);
            sb.AppendLine();
            AppendActionSection(sb, "Move", r.move_commands_total, r.move_commands_matched, r.move_commands_dropped,
                r.move_match_rate, r.move_direction_mismatch_count, r.move_direction_mismatch_rate,
                r.move_y_axis_flip_count, r.move_x_axis_flip_count, r.move_mapping_like_count,
                r.move_legality_or_state_divergence_count, r.move_mismatch_by_teacher_dir,
                r.move_mismatch_by_candidate_dir, r.first_10_move_mismatches);
            AppendActionSection(sb, "Harvest", r.harvest_commands_total, r.harvest_commands_matched, r.harvest_commands_dropped,
                r.harvest_match_rate, r.harvest_direction_mismatch_count, r.harvest_direction_mismatch_rate,
                r.harvest_y_axis_flip_count, r.harvest_x_axis_flip_count, r.harvest_mapping_like_count,
                r.harvest_legality_or_state_divergence_count, r.harvest_mismatch_by_teacher_dir,
                r.harvest_mismatch_by_candidate_dir, r.first_10_harvest_mismatches);
            AppendActionSection(sb, "Produce", r.produce_commands_total, r.produce_commands_matched, r.produce_commands_dropped,
                r.produce_match_rate, r.produce_direction_mismatch_count, r.produce_direction_mismatch_rate,
                r.produce_y_axis_flip_count, r.produce_x_axis_flip_count, r.produce_mapping_like_count,
                r.produce_legality_or_state_divergence_count, r.produce_mismatch_by_teacher_dir,
                r.produce_mismatch_by_candidate_dir, r.first_10_produce_mismatches);
            sb.AppendLine("- produce_type_mismatch_count: " + r.produce_type_mismatch_count);
            sb.AppendLine();
            sb.AppendLine("## Direction Pattern Conclusion");
            sb.AppendLine();
            sb.AppendLine("- y_axis_flip_count: " + r.mhp_y_axis_flip_count);
            sb.AppendLine("- y_axis_flip_rate: " + ValueOrNull(r.mhp_y_axis_flip_rate));
            sb.AppendLine("- x_axis_flip_count: " + r.mhp_x_axis_flip_count);
            sb.AppendLine("- x_axis_flip_rate: " + ValueOrNull(r.mhp_x_axis_flip_rate));
            sb.AppendLine("- opposite_direction_count: " + r.mhp_opposite_direction_count);
            sb.AppendLine("- conclusion: " + r.direction_pattern_conclusion);
            sb.AppendLine();
            sb.AppendLine("## Notes");
            sb.AppendLine();
            for (int i = 0; i < r.notes.Count; i++)
            {
                sb.AppendLine("- " + r.notes[i]);
            }

            return sb.ToString();
        }

        private static void AppendActionSection(
            StringBuilder sb,
            string title,
            int total,
            int matched,
            int dropped,
            float matchRate,
            int directionMismatch,
            float directionRate,
            int yFlip,
            int xFlip,
            int mappingLike,
            int legalityDivergence,
            List<MetricEntry> byTeacher,
            List<MetricEntry> byCandidate,
            List<string> first10)
        {
            sb.AppendLine("## " + title);
            sb.AppendLine();
            sb.AppendLine("- " + title.ToLowerInvariant() + "_commands_total: " + total);
            sb.AppendLine("- " + title.ToLowerInvariant() + "_commands_matched: " + matched);
            sb.AppendLine("- " + title.ToLowerInvariant() + "_commands_dropped: " + dropped);
            sb.AppendLine("- " + title.ToLowerInvariant() + "_match_rate: " + ValueOrNull(matchRate));
            sb.AppendLine("- " + title.ToLowerInvariant() + "_direction_mismatch_count: " + directionMismatch);
            sb.AppendLine("- " + title.ToLowerInvariant() + "_direction_mismatch_rate: " + ValueOrNull(directionRate));
            sb.AppendLine("- y_axis_flip_count: " + yFlip);
            sb.AppendLine("- x_axis_flip_count: " + xFlip);
            sb.AppendLine("- mapping_like_candidate_target_count: " + mappingLike);
            sb.AppendLine("- legality_or_state_divergence_count: " + legalityDivergence);
            sb.AppendLine("- mismatch_by_teacher_dir: " + FormatHistogram(byTeacher));
            sb.AppendLine("- mismatch_by_candidate_dir: " + FormatHistogram(byCandidate));
            sb.AppendLine("- first_10:");
            if (first10.Count == 0)
            {
                sb.AppendLine("  - (none)");
            }
            else
            {
                for (int i = 0; i < first10.Count; i++)
                {
                    sb.AppendLine("  - " + first10[i]);
                }
            }

            sb.AppendLine();
        }

        private static string FormatHistogram(List<MetricEntry> items)
        {
            if (items == null || items.Count == 0) return "{}";
            var sb = new StringBuilder();
            sb.Append("{");
            for (int i = 0; i < items.Count; i++)
            {
                if (i > 0) sb.Append(", ");
                sb.Append(items[i].key).Append(": ").Append(items[i].value);
            }

            sb.Append("}");
            return sb.ToString();
        }

        private static string ValueOrNull(float value)
        {
            return value < 0f ? "null" : value.ToString("0.######", CultureInfo.InvariantCulture);
        }

        private static List<string> ValidateManifest(Stage7BTeacherReplayManifest manifest)
        {
            var errors = new List<string>();
            if (manifest == null)
            {
                errors.Add("manifest is null");
                return errors;
            }

            if (manifest.branch_sizes == null || manifest.branch_sizes.Length != ActionContract.ActionBranchCount)
            {
                errors.Add("branch_sizes length mismatch");
            }

            if (manifest.attack_target_size != ActionContract.SIZE_ATTACK_TARGET)
            {
                errors.Add("attack_target_size mismatch");
            }

            return errors;
        }

        private static Stage7BTeacherReplayTeacherCommand[] GetTeacherCommands(Stage7BTeacherTrajectoryStep step)
        {
            if (step == null) return Array.Empty<Stage7BTeacherReplayTeacherCommand>();
            if (step.teacher_commands_list != null) return step.teacher_commands_list;
            return Array.Empty<Stage7BTeacherReplayTeacherCommand>();
        }

        private static string BuildCandidateListSummary(MlAgentsCandidateActionList candidates)
        {
            if (candidates == null) return "null";
            var sb = new StringBuilder();
            sb.Append("[");
            int limit = Math.Min(candidates.AvailableCandidates.Count, 20);
            for (int i = 0; i < limit; i++)
            {
                MlAgentsCandidateAction c = candidates.AvailableCandidates[i];
                if (i > 0) sb.Append(", ");
                sb.Append("{idx=").Append(c.CandidateIndex)
                    .Append(",pos=").Append(c.Action.ActorPosition)
                    .Append(",type=").Append(c.Action.ActionType)
                    .Append(",dir=").Append(c.Action.Direction)
                    .Append(",produce=").Append(c.Action.ProduceUnitType)
                    .Append("}");
            }

            if (candidates.AvailableCandidates.Count > limit)
            {
                sb.Append(", ...(").Append(candidates.AvailableCandidates.Count - limit).Append(" more)");
            }

            sb.Append("]");
            return sb.ToString();
        }

        private static string BuildActionSummary(AgentAction action)
        {
            return "actor=" + action.ActorPosition + ",type=" + action.ActionType
                + ",dir=" + action.Direction + ",produce=" + action.ProduceUnitType
                + ",target=" + action.AttackTargetPosition;
        }

        private static string UnitTypeName(UnitRuntime unit)
        {
            return unit == null ? "none" : unit.Type.ToString();
        }

        private static string ActionTypeToString(int actionType)
        {
            switch (actionType)
            {
                case 0: return "noop";
                case 1: return "move";
                case 2: return "harvest";
                case 3: return "return";
                case 4: return "produce";
                case 5: return "attack";
                default: return "unknown";
            }
        }

        private static void AddHistogram(List<MetricEntry> histogram, string key)
        {
            if (string.IsNullOrWhiteSpace(key)) return;
            for (int i = 0; i < histogram.Count; i++)
            {
                if (histogram[i].key == key)
                {
                    histogram[i].value++;
                    return;
                }
            }

            histogram.Add(new MetricEntry { key = key, value = 1 });
        }

        private static bool IsOppositeDirection(Direction a, Direction b)
        {
            return (a == Direction.North && b == Direction.South)
                || (a == Direction.South && b == Direction.North)
                || (a == Direction.East && b == Direction.West)
                || (a == Direction.West && b == Direction.East);
        }

        private static bool IsYAxisFlip(Direction a, Direction b)
        {
            return (a == Direction.North && b == Direction.South)
                || (a == Direction.South && b == Direction.North);
        }

        private static bool IsXAxisFlip(Direction a, Direction b)
        {
            return (a == Direction.East && b == Direction.West)
                || (a == Direction.West && b == Direction.East);
        }

        private static string ToSnakeCase(Stage7BTeacherReplayDropReason reason)
        {
            switch (reason)
            {
                case Stage7BTeacherReplayDropReason.None: return "none";
                case Stage7BTeacherReplayDropReason.SourceNotReplayReady: return "source_not_replay_ready";
                case Stage7BTeacherReplayDropReason.ManifestContractMismatch: return "manifest_contract_mismatch";
                case Stage7BTeacherReplayDropReason.MissingRuntimeStateT: return "missing_runtime_state_t";
                case Stage7BTeacherReplayDropReason.StateSyncFailed: return "state_sync_failed";
                case Stage7BTeacherReplayDropReason.UnityStateApiMissing: return "unity_state_api_missing";
                case Stage7BTeacherReplayDropReason.ActorNotFound: return "actor_not_found";
                case Stage7BTeacherReplayDropReason.ActorTypeMismatch: return "actor_type_mismatch";
                case Stage7BTeacherReplayDropReason.ActorOwnerMismatch: return "actor_owner_mismatch";
                case Stage7BTeacherReplayDropReason.NoMatchingCandidate: return "no_matching_candidate";
                case Stage7BTeacherReplayDropReason.DirectionMismatch: return "direction_mismatch";
                case Stage7BTeacherReplayDropReason.ProduceTypeMismatch: return "produce_type_mismatch";
                case Stage7BTeacherReplayDropReason.RuntimeApplyRejected: return "runtime_apply_rejected";
                default: return reason.ToString();
            }
        }

        [Serializable]
        private sealed class MetricEntry
        {
            public string key;
            public int value;
        }

        [Serializable]
        private sealed class Stage7B7AMhpMismatchAuditReport
        {
            public string generated_at_utc;
            public string status;
            public string summary;
            public string source_path;
            public string decision;
            public string direction_pattern_conclusion;
            public int contract_error_count;

            public int episodes_scanned;
            public int steps_total;
            public int teacher_commands_total;
            public int candidate_match_count;
            public int candidate_drop_count;
            public float candidate_match_rate;
            public int runtime_apply_attempted_count;
            public int runtime_apply_accepted_count;
            public int runtime_apply_rejected_count;
            public float runtime_apply_accept_rate;
            public int state_sync_success_count;
            public int state_sync_failed_count;
            public int no_teacher_command_steps;
            public int candidate_count_min;
            public float candidate_count_mean;
            public int candidate_count_max;

            public int move_commands_total;
            public int move_commands_matched;
            public int move_commands_dropped;
            public float move_match_rate;
            public int move_direction_mismatch_count;
            public float move_direction_mismatch_rate;
            public int move_opposite_direction_count;
            public int move_y_axis_flip_count;
            public int move_x_axis_flip_count;
            public int move_mapping_like_count;
            public int move_legality_or_state_divergence_count;
            public List<MetricEntry> move_mismatch_by_teacher_dir = new List<MetricEntry>();
            public List<MetricEntry> move_mismatch_by_candidate_dir = new List<MetricEntry>();
            public List<string> first_10_move_mismatches = new List<string>();

            public int harvest_commands_total;
            public int harvest_commands_matched;
            public int harvest_commands_dropped;
            public float harvest_match_rate;
            public int harvest_direction_mismatch_count;
            public float harvest_direction_mismatch_rate;
            public int harvest_opposite_direction_count;
            public int harvest_y_axis_flip_count;
            public int harvest_x_axis_flip_count;
            public int harvest_mapping_like_count;
            public int harvest_legality_or_state_divergence_count;
            public List<MetricEntry> harvest_mismatch_by_teacher_dir = new List<MetricEntry>();
            public List<MetricEntry> harvest_mismatch_by_candidate_dir = new List<MetricEntry>();
            public List<string> first_10_harvest_mismatches = new List<string>();

            public int produce_commands_total;
            public int produce_commands_matched;
            public int produce_commands_dropped;
            public float produce_match_rate;
            public int produce_direction_mismatch_count;
            public float produce_direction_mismatch_rate;
            public int produce_opposite_direction_count;
            public int produce_y_axis_flip_count;
            public int produce_x_axis_flip_count;
            public int produce_mapping_like_count;
            public int produce_legality_or_state_divergence_count;
            public int produce_type_mismatch_count;
            public List<MetricEntry> produce_mismatch_by_teacher_dir = new List<MetricEntry>();
            public List<MetricEntry> produce_mismatch_by_candidate_dir = new List<MetricEntry>();
            public List<string> first_10_produce_mismatches = new List<string>();

            public int mhp_direction_mismatch_count;
            public int mhp_opposite_direction_count;
            public int mhp_y_axis_flip_count;
            public float mhp_y_axis_flip_rate;
            public int mhp_x_axis_flip_count;
            public float mhp_x_axis_flip_rate;

            public List<MetricEntry> runtime_reject_reason_histogram = new List<MetricEntry>();
            public List<MetricEntry> state_sync_failure_reasons = new List<MetricEntry>();
            public List<string> notes = new List<string>();

            public static Stage7B7AMhpMismatchAuditReport CreateDefault()
            {
                return new Stage7B7AMhpMismatchAuditReport
                {
                    status = "NO_GO",
                    decision = "HOLD_FOR_STAGE7B_7B_MAPPING_FIX",
                    direction_pattern_conclusion = "not_measured",
                    candidate_match_rate = -1f,
                    runtime_apply_accept_rate = -1f,
                    candidate_count_min = -1,
                    candidate_count_mean = -1f,
                    candidate_count_max = -1,
                    move_match_rate = -1f,
                    move_direction_mismatch_rate = -1f,
                    harvest_match_rate = -1f,
                    harvest_direction_mismatch_rate = -1f,
                    produce_match_rate = -1f,
                    produce_direction_mismatch_rate = -1f,
                    mhp_y_axis_flip_rate = -1f,
                    mhp_x_axis_flip_rate = -1f,
                };
            }
        }

        [Serializable]
        private sealed class Stage7B7AMismatchEntry
        {
            public int episode_id;
            public int step_id;
            public int command_index;
            public int actor_flat;
            public int actor_x;
            public int actor_y;
            public int action_type;
            public string action_type_name;
            public string teacher_dir;
            public string nearest_candidate_dir;
            public int teacher_target_x;
            public int teacher_target_y;
            public int unity_candidate_target_x;
            public int unity_candidate_target_y;
            public bool teacher_target_inside_map;
            public bool unity_candidate_target_inside_map;
            public bool teacher_target_occupied;
            public bool unity_candidate_target_occupied;
            public string teacher_target_occupant_type;
            public string unity_candidate_target_occupant_type;
            public bool teacher_target_has_resource;
            public bool unity_candidate_target_has_resource;
            public bool teacher_target_has_expected_object;
            public bool unity_candidate_target_has_expected_object;
            public string expected_object_rule;
            public bool is_opposite_direction;
            public bool is_y_axis_flip;
            public bool is_x_axis_flip;
            public bool mapping_like_candidate_target;
            public bool legality_or_state_divergence;
            public string drop_reason;
            public string nearest_candidate_reason;
            public int teacher_produce_unit_type;
            public int nearest_candidate_produce_unit_type;
            public int candidate_count;
            public string teacher_command_json;
            public string candidate_list_summary;
        }

        [Serializable]
        private sealed class Stage7B7ARuntimeApplyTraceEntry
        {
            public int episode_id;
            public int step_id;
            public int command_index;
            public int actor_flat;
            public int actor_x;
            public int actor_y;
            public int action_type;
            public string action_type_name;
            public string teacher_dir;
            public bool candidate_match;
            public int candidate_action_index = -1;
            public string nearest_candidate_dir;
            public string nearest_candidate_reason;
            public bool runtime_apply_attempted;
            public bool runtime_apply_accepted;
            public string reject_reason;
            public string action_summary;
        }
    }
}
