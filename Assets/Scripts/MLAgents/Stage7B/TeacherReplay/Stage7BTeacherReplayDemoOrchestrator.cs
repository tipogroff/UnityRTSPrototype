using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using RTS.Core;
using RTS.Gameplay;
using RTS.ML;
using RTS.MLAgents.Stage7B.CandidateActions;
using Unity.MLAgents;
using Unity.MLAgents.Policies;
using UnityEngine;
using System.Reflection;

namespace RTS.MLAgents.Stage7B.TeacherReplay
{
    /// <summary>
    /// Stage7B-7: Drives StudentMlAgent in teacher-replay-demo mode so that the
    /// ML-Agents Demonstration Recorder captures (observation, action_mask, action)
    /// tuples from the teacher trajectory.
    ///
    /// This component does NOT start ML-Agents training / PPO / imitation learning.
    /// It only drives the heuristic decision loop so the Demonstration Recorder
    /// can produce a .demo file.
    ///
    /// Setup in the Week7 scene:
    ///   1. Add this component to any GameObject.
    ///   2. Assign _studentAgent (or leave null for auto-discover via FindFirstObjectByType).
    ///   3. On the StudentMlAgent GameObject:
    ///        a. Add DemonstrationRecorder component.
    ///        b. Set Demonstration Name  = "stage7b_teacher_replay_smoke"
    ///        c. Set Demonstration Directory = "Assets/Demonstrations"
    ///        d. Enable the Record checkbox.
    ///   4. Set BehaviorParameters.BehaviorType = HeuristicOnly on the StudentMlAgent.
    ///   5. Enter Play Mode.
    ///   6. Right-click this component → "Run Stage7B-7 Demo Recording Smoke".
    ///   7. After max_recorded_decisions are captured the orchestrator stops,
    ///      writes artifacts, and logs the GO / NO-GO decision.
    ///
    /// Safety invariants:
    ///   - stage6b3_baseline_touched = false (no checkpoint / config modified).
    ///   - No mlagents-learn / PPO / imitation started.
    ///   - Max recorded decisions capped at _maxRecordedDecisions (default 64).
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class Stage7BTeacherReplayDemoOrchestrator : MonoBehaviour
    {
        // ── config ──────────────────────────────────────────────────────────

        [SerializeField] private StudentMlAgent _studentAgent;

        [SerializeField] private string _replayReadySourceDir =
            "python/week5_teacher_legacy032/teacher_replay_exports/" +
            "stage7b_replay_ready_stage7b6j_return_direction_audit_e8_s512_20260510T174822Z";

        [SerializeField] private int _maxRecordedDecisions = 64;
        [SerializeField] private int _maxEpisodes = 1;
        [SerializeField] private Owner _playerPerspective = Owner.Player1;
        [SerializeField] private bool _skipMismatchedCommands = true;
        [SerializeField] private bool _skipNoTeacherCommandSteps = true;
        [SerializeField] private bool _skipTeacherNoOpCommands = true;
        [SerializeField] private bool _produceFilteringEnabled = true;
        [SerializeField] private float _runtimeServicesMaxWaitSeconds = 15f;
        [SerializeField] private float _runtimeServicesPollIntervalSeconds = 0.25f;

        private const string RuntimeDemoTempDir = "Library/Stage7B_DemoRecordingTemp";

        // ── output paths ─────────────────────────────────────────────────────

        [SerializeField] private string _smokeReportJsonPath =
            "python/stage7b_teacher_replay/stage7b_demo_recording_smoke_report.json";

        [SerializeField] private string _smokeReportMdPath =
            "python/stage7b_teacher_replay/stage7b_demo_recording_smoke_report.md";

        [SerializeField] private string _traceJsonlPath =
            "python/stage7b_teacher_replay/stage7b_demo_recording_trace.jsonl";

        [SerializeField] private string _droppedCommandsJsonlPath =
            "python/stage7b_teacher_replay/stage7b_demo_recording_dropped_commands.jsonl";

        [SerializeField] private string _expectedDemoRelativePath =
            "Assets/Demonstrations/stage7b_teacher_replay_smoke.demo";

        // ── runtime state ─────────────────────────────────────────────────────

        private readonly Stage7BTeacherTrajectoryLoader _loader = new Stage7BTeacherTrajectoryLoader();
        private readonly List<DemoQueueEntry> _queue = new List<DemoQueueEntry>(256);
        private int _queueIndex;
        private bool _isRunning;
        private bool _pendingStop;
        private int _pendingCandidateIndex = -1;
        private DemoQueueEntry _lastDequeued;

        private Stage7BDemoRecordingSmokeReport _report;
        private readonly List<string> _traceLines = new List<string>(256);
        private readonly List<string> _droppedLines = new List<string>(256);

        private Stage7BTeacherReplayStateSynchronizer _synchronizer;
        private Stage7BTeacherReplayActionResolver _resolver;
        private Stage7BTeacherReplayCandidateMatcher _matcher;
        private Coroutine _startupCoroutine;
        private Coroutine _finalizeCoroutine;
        private bool _isFinalizing;
        private bool _startedFromEditMode;
        private bool _enteredPlayMode;
        private bool _playModeReady;
        private bool _cleanDemo7DMode;

        // ── public API for StudentMlAgent ────────────────────────────────────

        /// <summary>True while the orchestrator is actively recording.</summary>
        public bool IsActive => _isRunning;

        /// <summary>
        /// Called from StudentMlAgent.Heuristic().
        /// Consumes the pending candidate index queued by the last FixedUpdate tick.
        /// Returns false when no replay action is pending (agent should fall back to scripted heuristic).
        /// </summary>
        public bool TryConsumePendingCandidateIndex(out int candidateIndex)
        {
            candidateIndex = _pendingCandidateIndex;
            if (_pendingCandidateIndex >= 0)
            {
                _pendingCandidateIndex = -1;
                return true;
            }

            return false;
        }

        /// <summary>
        /// Called from StudentMlAgent.OnActionReceived() after attempting to apply
        /// the selected candidate action.  Records the outcome and checks stop conditions.
        /// </summary>
        public void NotifyActionApplied(bool accepted, int candidateIndex, string actionSummary)
        {
            if (_report == null || !_isRunning) return;

            _report.runtime_apply_attempted_count++;
            if (accepted)
            {
                _report.runtime_apply_accepted_count++;
                _report.recorded_decisions++;
            }
            else
            {
                _report.runtime_apply_rejected_count++;
            }

            // Per-action-type counters
            if (_lastDequeued != null)
            {
                switch (_lastDequeued.actionType)
                {
                    case 1: _report.move_commands_recorded++; break;
                    case 2: _report.harvest_commands_recorded++; break;
                    case 3: _report.return_commands_recorded++; break;
                    case 4: _report.produce_commands_recorded++; break;
                    case 5: _report.attack_commands_recorded++; break;
                }
            }

            // Trace entry
            var traceEntry = new Stage7BDemoRecordingTraceEntry
            {
                episode_id = _lastDequeued != null ? _lastDequeued.episodeId : -1,
                step_id = _lastDequeued != null ? _lastDequeued.stepId : -1,
                candidate_action_index = candidateIndex,
                action_type = _lastDequeued != null ? _lastDequeued.actionType : -1,
                action_summary = actionSummary ?? string.Empty,
                runtime_apply_accepted = accepted,
            };
            _traceLines.Add(JsonUtility.ToJson(traceEntry));

            // Check stop condition
            if (_report.recorded_decisions >= _maxRecordedDecisions || _queueIndex >= _queue.Count)
            {
                _pendingStop = true;
            }
        }

        public void ConfigureStartupContext(bool startedFromEditMode, bool enteredPlayMode, bool playModeReady)
        {
            _startedFromEditMode = startedFromEditMode;
            _enteredPlayMode = enteredPlayMode;
            _playModeReady = playModeReady;
        }

        // ── entry point ───────────────────────────────────────────────────────

        [ContextMenu("Run Stage7B-7 Demo Recording Smoke")]
        public void RunStage7B7DemoRecordingSmoke()
        {
            if (_isRunning)
            {
                Debug.LogWarning("[Stage7B][DemoOrchestrator] Already running. Stop or wait for it to finish.");
                return;
            }

            if (!Application.isPlaying)
            {
                Debug.LogWarning("[Stage7B][DemoOrchestrator] Must be in Play Mode to run demo recording smoke.");
                return;
            }

            if (_startupCoroutine != null)
            {
                StopCoroutine(_startupCoroutine);
                _startupCoroutine = null;
            }

            _isRunning = false;

            _report = new Stage7BDemoRecordingSmokeReport
            {
                status = "NO_GO",
                generated_at_utc = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ"),
                source_path = _replayReadySourceDir,
                source_replay_ready = false,
                behavior_name = "Stage7B_RTS_Student",
                observation_size = ObservationContract.TotalFloats,
                discrete_branch_count = 1,
                candidate_branch_size = MlAgentsCandidateActionList.BranchSize,
                max_recorded_decisions = _maxRecordedDecisions,
                max_episodes = _maxEpisodes,
                direction_mapping_mode =
                    Stage7BTeacherReplayActionResolver.CardinalDirectionMappingModeInvertYForLegacy032Teacher,
                return_mapping_mode =
                    Stage7BTeacherReplayActionResolver.ReturnDirectionMappingModeInvertYForLegacy032Teacher,
                produce_filtering_enabled = _produceFilteringEnabled,
                stage6b3_baseline_touched = false,
                demo_recording_ready_for_imitation_smoke = false,
                demo_file_path = _expectedDemoRelativePath,
                runtime_apply_accept_rate = -1f,
                started_from_edit_mode = _startedFromEditMode,
                entered_play_mode = _enteredPlayMode || Application.isPlaying,
                play_mode_ready = _playModeReady || Application.isPlaying,
            };

            UpdateUnityConsoleCounts(_report);

            _traceLines.Clear();
            _droppedLines.Clear();
            _queue.Clear();
            _queueIndex = 0;
            _pendingCandidateIndex = -1;
            _lastDequeued = null;
            _pendingStop = false;
            _startupCoroutine = StartCoroutine(RunSmokeAfterStartupReady());
        }

        [ContextMenu("Run Stage7B-7D Clean Demo Recording Smoke")]
        public void RunStage7B7DCleanDemoRecordingSmoke()
        {
            ConfigureStage7B7DCleanDemoDefaults();
            RunStage7B7DemoRecordingSmoke();
        }

        public void ConfigureStage7B7DCleanDemoDefaults()
        {
            _cleanDemo7DMode = true;
            _maxRecordedDecisions = 128;
            _maxEpisodes = 1;
            _skipMismatchedCommands = true;
            _skipNoTeacherCommandSteps = true;
            _skipTeacherNoOpCommands = true;
            _produceFilteringEnabled = true;
            _smokeReportJsonPath = "python/stage7b_teacher_replay/stage7b_7d_clean_demo_recording_report.json";
            _smokeReportMdPath = "python/stage7b_teacher_replay/stage7b_7d_clean_demo_recording_report.md";
            _traceJsonlPath = "python/stage7b_teacher_replay/stage7b_7d_clean_demo_recording_trace.jsonl";
            _droppedCommandsJsonlPath = "python/stage7b_teacher_replay/stage7b_7d_clean_demo_dropped_commands.jsonl";
            _expectedDemoRelativePath = "Assets/Demonstrations/stage7b_teacher_replay_clean_smoke.demo";
        }

        private System.Collections.IEnumerator RunSmokeAfterStartupReady()
        {
            float maxWait = Mathf.Max(1f, _runtimeServicesMaxWaitSeconds);
            float poll = Mathf.Clamp(_runtimeServicesPollIntervalSeconds, 0.05f, 1f);
            float waited = 0f;

            MatchManager match = null;
            GridManager grid = null;
            UnitRegistry registry = null;
            MatchBootstrap bootstrap = null;
            ResourceManager resources = null;

            List<string> missing = new List<string>(5);
            List<string> resolved = new List<string>(5);

            bool servicesReady = false;
            while (waited <= maxWait)
            {
                ResolveRuntimeServices(
                    out match, out grid, out registry, out bootstrap, out resources,
                    missing, resolved);

                _report.runtime_service_readiness_trace.Add(
                    "t=" + waited.ToString("0.00", System.Globalization.CultureInfo.InvariantCulture)
                    + "s resolved=[" + string.Join(",", resolved) + "] missing=[" + string.Join(",", missing) + "]");

                if (missing.Count == 0)
                {
                    servicesReady = true;
                    break;
                }

                yield return new WaitForSecondsRealtime(poll);
                waited += poll;
            }

            _report.runtime_services_wait_seconds = waited;
            _report.runtime_services_ready = servicesReady;
            _report.missing_runtime_services = new List<string>(missing);
            _report.resolved_runtime_services = new List<string>(resolved);

            if (!servicesReady)
            {
                _report.startup_failure_reason =
                    "runtime_services_timeout: missing=" + string.Join(",", missing);
                _report.notes.Add(
                    "Unity runtime services remained unavailable until timeout. "
                    + "Missing: " + string.Join(", ", missing));
                FinalizeAndWriteReport("NO_GO");
                _startupCoroutine = null;
                yield break;
            }

            _report.startup_failure_reason = string.Empty;
            _synchronizer = new Stage7BTeacherReplayStateSynchronizer(match, grid, registry, bootstrap, resources);
            _resolver = new Stage7BTeacherReplayActionResolver();
            _matcher = new Stage7BTeacherReplayCandidateMatcher();

            // ── load manifest ─────────────────────────────────────────────────

            if (!_loader.TryLoadReplayManifest(_replayReadySourceDir, out Stage7BTeacherReplayManifest manifest, out string manifestDiag))
            {
                _report.notes.Add("Failed to load replay_manifest.json: " + manifestDiag);
                FinalizeAndWriteReport("NO_GO");
                _startupCoroutine = null;
                yield break;
            }

            if (!manifest.replay_ready)
            {
                _report.notes.Add("Manifest replay_ready=false — source is not replay-ready.");
                FinalizeAndWriteReport("NO_GO");
                _startupCoroutine = null;
                yield break;
            }

            _report.source_replay_ready = true;

            // ── load steps ────────────────────────────────────────────────────

            if (!_loader.TryLoadReplayReadyJsonl(_replayReadySourceDir, out List<Stage7BTeacherTrajectoryStep> steps, out string loadDiag))
            {
                _report.notes.Add("Failed to load episode_*.replay_ready.jsonl: " + loadDiag);
                FinalizeAndWriteReport("NO_GO");
                _startupCoroutine = null;
                yield break;
            }

            var allowedEpisodeIds = new HashSet<int>();
            int allowedSteps = 0;
            for (int i = 0; i < steps.Count; i++)
            {
                int episodeId = steps[i].episodeId;
                if (!allowedEpisodeIds.Contains(episodeId))
                {
                    if (_maxEpisodes > 0 && allowedEpisodeIds.Count >= _maxEpisodes)
                    {
                        continue;
                    }

                    allowedEpisodeIds.Add(episodeId);
                }

                allowedSteps++;
            }

            _report.steps_scanned = allowedSteps;
            _report.episodes_scanned = allowedEpisodeIds.Count;

            // ── pre-process: state sync + candidate matching → build queue ────
            // We stop pre-processing once we have enough entries for the smoke.
            int preProcessLimit = _maxRecordedDecisions * 4;

            for (int si = 0; si < steps.Count && _queue.Count < preProcessLimit; si++)
            {
                Stage7BTeacherTrajectoryStep step = steps[si];
                if (!allowedEpisodeIds.Contains(step.episodeId)) continue;
                if (!step.HasRuntimeStateTJson) continue;

                if (!_synchronizer.TrySynchronizeRuntimeState(step.runtime_state_t_json, out _, out _))
                    continue;

                var maskBuilder = new ActionMaskBuilder(match, grid, resources, registry, bootstrap);
                var candidateBuilder = new MlAgentsCandidateActionBuilder(maskBuilder);
                MlAgentsCandidateActionList candidates = candidateBuilder.Build(_playerPerspective);

                Stage7BTeacherReplayTeacherCommand[] commands = GetTeacherCommands(step);

                if (commands == null || commands.Length == 0)
                {
                    if (_skipNoTeacherCommandSteps)
                    {
                        _report.no_teacher_command_steps_skipped++;
                        continue;
                    }
                }
                else
                {
                    _report.teacher_commands_total += commands.Length;
                }

                if (commands == null) continue;

                for (int ci = 0; ci < commands.Length; ci++)
                {
                    Stage7BTeacherReplayTeacherCommand command = commands[ci];

                    if (_skipTeacherNoOpCommands && command.action_type == ActionContract.ACTION_NOOP)
                    {
                        _report.dropped_commands++;
                        AddDropReason(_report, "teacher_noop");
                        _droppedLines.Add(JsonUtility.ToJson(new Stage7BDemoRecordingDroppedEntry
                        {
                            episode_id = step.episodeId, step_id = step.stepId,
                            command_index = ci, action_type = command.action_type,
                            drop_reason = "teacher_noop",
                        }));
                        continue;
                    }

                    if (!_resolver.TryResolveTeacherCommand(
                            command, _playerPerspective,
                            out AgentAction teacherAction, out Stage7BTeacherReplayDropReason resolveDrop))
                    {
                        _report.dropped_commands++;
                        string dropReason = ClassifyDropReason(command, resolveDrop, grid, registry);
                        AddDropReason(_report, dropReason);
                        _droppedLines.Add(JsonUtility.ToJson(new Stage7BDemoRecordingDroppedEntry
                        {
                            episode_id = step.episodeId, step_id = step.stepId,
                            command_index = ci, action_type = command.action_type,
                            drop_reason = dropReason,
                        }));
                        continue;
                    }

                    if (!_matcher.TryMatch(teacherAction, candidates, out int candidateIndex, out Stage7BTeacherReplayDropReason matchDrop))
                    {
                        _report.dropped_commands++;
                        string dropReason = ClassifyDropReason(command, matchDrop, grid, registry);
                        AddDropReason(_report, dropReason);
                        _droppedLines.Add(JsonUtility.ToJson(new Stage7BDemoRecordingDroppedEntry
                        {
                            episode_id = step.episodeId, step_id = step.stepId,
                            command_index = ci, action_type = command.action_type,
                            drop_reason = dropReason,
                        }));
                        if (_skipMismatchedCommands) continue;
                    }

                    _report.matched_commands++;
                    _queue.Add(new DemoQueueEntry
                    {
                        episodeId = step.episodeId,
                        stepId = step.stepId,
                        stateJson = step.runtime_state_t_json,
                        candidateActionIndex = candidateIndex,
                        actionType = command.action_type,
                    });
                }
            }

            if (_queue.Count == 0)
            {
                _report.notes.Add("No matched entries built in pre-processing. Check source path and matching.");
                FinalizeAndWriteReport("NO_GO");
                _startupCoroutine = null;
                yield break;
            }

            // ── wire student agent ────────────────────────────────────────────

            if (_studentAgent == null)
                _studentAgent = FindFirstObjectByType<StudentMlAgent>();

            if (_studentAgent == null)
            {
                _report.notes.Add("StudentMlAgent not found in scene.");
                FinalizeAndWriteReport("NO_GO");
                _startupCoroutine = null;
                yield break;
            }

            _studentAgent.TeacherReplayOrchestrator = this;

            // Ensure Heuristic mode so Demonstration Recorder captures actions
            BehaviorParameters bp = _studentAgent.GetComponent<BehaviorParameters>();
            if (bp != null && bp.BehaviorType != BehaviorType.HeuristicOnly)
            {
                bp.BehaviorType = BehaviorType.HeuristicOnly;
                _report.notes.Add("BehaviorType forced to HeuristicOnly by orchestrator.");
            }

            // Disable the DecisionRequester so only the orchestrator triggers decisions
            DecisionRequester dr = _studentAgent.GetComponent<DecisionRequester>();
            if (dr != null && dr.enabled)
            {
                dr.enabled = false;
                _report.notes.Add("DecisionRequester disabled by orchestrator (orchestrator controls timing).");
            }

            // Check / enable DemonstrationRecorder if present
            bool recorderFound = CheckAndEnableDemonstrationRecorder(_studentAgent.gameObject);
            _report.notes.Add("demonstration_recorder_component_found=" + recorderFound.ToString().ToLowerInvariant());
            if (!recorderFound)
            {
                _report.notes.Add(
                    "WARNING: DemonstrationRecorder not found on StudentMlAgent GameObject. " +
                    "Add it manually in the Inspector with Name='stage7b_teacher_replay_smoke', " +
                    "Directory='Assets/Demonstrations', Record=true.");
            }

            _report.notes.Add("queue_size=" + _queue.Count);
            _report.notes.Add("max_recorded_decisions=" + _maxRecordedDecisions);
            _report.notes.Add("ML-Agents training / PPO / imitation learning NOT started by this orchestrator.");
            _report.notes.Add("Stage6B3 baseline/checkpoint assets were NOT modified.");

            _isRunning = true;
            _startupCoroutine = null;

            Debug.Log("[Stage7B][DemoOrchestrator] Stage7B-7 demo recording smoke STARTED. " +
                      "queue=" + _queue.Count + " maxDecisions=" + _maxRecordedDecisions);
        }

        // ── per-frame orchestration ───────────────────────────────────────────

        private void FixedUpdate()
        {
            if (_pendingStop)
            {
                _pendingStop = false;
                StopAndFinalize();
                return;
            }

            if (!_isRunning || _studentAgent == null) return;

            if (_queueIndex >= _queue.Count || _report.recorded_decisions >= _maxRecordedDecisions)
            {
                StopAndFinalize();
                return;
            }

            // Re-resolve services each tick (they could be destroyed/recreated)
            MatchManager match = MatchManager.Instance;
            if (match == null || _synchronizer == null)
            {
                _report.notes.Add("Unity services lost during recording — stopping.");
                StopAndFinalize();
                return;
            }

            DemoQueueEntry entry = _queue[_queueIndex++];
            _lastDequeued = entry;

            // Sync Unity runtime state to the teacher's state_t
            if (!_synchronizer.TrySynchronizeRuntimeState(entry.stateJson, out _, out string syncDiag))
            {
                Debug.LogWarning("[Stage7B][DemoOrchestrator] State sync failed at ep=" +
                                 entry.episodeId + " step=" + entry.stepId + ": " + syncDiag);
                return;
            }

            // Expose the matched candidate index so Heuristic() can consume it
            _pendingCandidateIndex = entry.candidateActionIndex;

            // Trigger the agent's decision cycle:
            //   CollectObservations → WriteDiscreteActionMask → Heuristic → OnActionReceived
            // The Demonstration Recorder records the resulting (obs, mask, action) tuple.
            _studentAgent.RequestDecision();
        }

        // ── stop and finalize ─────────────────────────────────────────────────

        private void StopAndFinalize()
        {
            if (_isFinalizing) return;
            if (!_isRunning) return;
            _isRunning = false;
            _pendingStop = false;
            _isFinalizing = true;

            if (_finalizeCoroutine != null)
            {
                StopCoroutine(_finalizeCoroutine);
                _finalizeCoroutine = null;
            }

            _finalizeCoroutine = StartCoroutine(FinalizeAfterRecorderFlush());
        }

        private System.Collections.IEnumerator FinalizeAfterRecorderFlush()
        {

            // Detach from student agent and restore DecisionRequester
            if (_studentAgent != null)
            {
                _studentAgent.TeacherReplayOrchestrator = null;

                DecisionRequester dr = _studentAgent.GetComponent<DecisionRequester>();
                if (dr != null) dr.enabled = true;

                DisableDemonstrationRecorderRecording(_studentAgent.gameObject);
                // End the episode so the Demonstration Recorder flushes its buffer.
                _studentAgent.EpisodeInterrupted();
            }

            // Let ML-Agents flush and release file handles before copy.
            yield return null;
            yield return new WaitForEndOfFrame();
            yield return new WaitForSecondsRealtime(0.25f);

            // Verify .demo file
            string projectRoot = Directory.GetParent(Application.dataPath)?.FullName
                                 ?? Application.dataPath;
            string latestTempDemo = TryGetLatestTempDemo(projectRoot);
            if (!string.IsNullOrWhiteSpace(latestTempDemo))
            {
                string expectedDemoFullPath = Path.GetFullPath(
                    Path.Combine(projectRoot, _expectedDemoRelativePath));
                string expectedDir = Path.GetDirectoryName(expectedDemoFullPath);
                if (!string.IsNullOrWhiteSpace(expectedDir)) Directory.CreateDirectory(expectedDir);

                bool copySuccess = false;
                string lastCopyError = string.Empty;
                for (int attempt = 0; attempt < 20; attempt++)
                {
                    if (TryCopyFile(latestTempDemo, expectedDemoFullPath, out lastCopyError))
                    {
                        copySuccess = true;
                        break;
                    }

                    yield return new WaitForSecondsRealtime(0.1f);
                }

                if (copySuccess)
                {
                    _report.notes.Add("Copied temp demo to expected path: " + expectedDemoFullPath);
                }
                else
                {
                    _report.notes.Add("Failed to copy temp demo to expected path: " + lastCopyError);
                }
            }

            string demoFullPath = Path.GetFullPath(
                Path.Combine(projectRoot, _expectedDemoRelativePath));

            bool demoExists = File.Exists(demoFullPath);
            long demoSize = 0;
            if (demoExists)
            {
                try { demoSize = new FileInfo(demoFullPath).Length; }
                catch { /* ignore */ }
            }

            _report.demo_file_path = demoFullPath;
            _report.demo_file_exists = demoExists;
            _report.demo_file_size_bytes = demoSize;

            // Compute accept rate
            if (_report.runtime_apply_attempted_count > 0)
            {
                _report.runtime_apply_accept_rate =
                    (float)_report.runtime_apply_accepted_count /
                    _report.runtime_apply_attempted_count;
            }

            // GO criteria (all must pass)
            bool go = demoExists
                && demoSize > 0
                && _report.recorded_decisions > 0
                && _report.runtime_apply_rejected_count == 0
                && _report.unclassified_produce_dropped == 0
                && _report.runtime_services_ready
                && _report.source_replay_ready
                && !_report.stage6b3_baseline_touched;

            _report.demo_recording_ready_for_imitation_smoke = go;

            FinalizeAndWriteReport(go ? "GO" : "NO_GO");

            Debug.Log("[Stage7B][DemoOrchestrator] Stage7B-7 demo recording smoke FINISHED. " +
                      "status=" + _report.status +
                      " recorded_decisions=" + _report.recorded_decisions +
                      " demo_exists=" + demoExists +
                      " demo_size_bytes=" + demoSize +
                      " runtime_apply_rejected=" + _report.runtime_apply_rejected_count);

            _isFinalizing = false;
            _finalizeCoroutine = null;
        }

        private void FinalizeAndWriteReport(string status)
        {
            if (_report == null) return;
            _report.status = status;
            _report.generated_at_utc = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ");
            UpdateUnityConsoleCounts(_report);
            WriteArtifacts();
        }

        private void WriteArtifacts()
        {
            if (_report == null) return;

            _loader.TrySaveText(_traceJsonlPath, string.Join("\n", _traceLines), out _);
            _loader.TrySaveText(_droppedCommandsJsonlPath, string.Join("\n", _droppedLines), out _);

            // TrySaveRuntimeReport only accepts Stage7BTeacherReplayReport — save directly
            if (_loader.TrySaveText(_smokeReportJsonPath, JsonUtility.ToJson(_report, true), out string reportPath))
            {
                _loader.TrySaveText(_smokeReportMdPath, BuildMarkdown(_report), out _);
                Debug.Log("[Stage7B][DemoOrchestrator] Smoke report written: " + reportPath);
            }
            else
            {
                Debug.LogWarning("[Stage7B][DemoOrchestrator] Failed to write smoke report to: " + _smokeReportJsonPath);
            }
        }

        // ── DemonstrationRecorder probe ───────────────────────────────────────

        private static bool CheckAndEnableDemonstrationRecorder(GameObject agentGO)
        {
            if (agentGO == null) return false;
#if UNITY_EDITOR
            // Access via reflection so we don't hard-reference the Editor assembly
            // and so the component is still usable in Runtime builds without Editor.
            var recorderType = Type.GetType(
                "Unity.MLAgents.Demonstrations.DemonstrationRecorder, Unity.ML-Agents");
            if (recorderType == null) return false;

            var recorder = agentGO.GetComponent(recorderType);
            if (recorder == null) return false;

            var nameField = recorderType.GetField("DemonstrationName",
                BindingFlags.Public | BindingFlags.Instance);
            if (nameField != null)
                nameField.SetValue(recorder, "stage7b_teacher_replay_smoke");

            var directoryField = recorderType.GetField("DemonstrationDirectory",
                BindingFlags.Public | BindingFlags.Instance);
            if (directoryField != null)
                directoryField.SetValue(recorder, RuntimeDemoTempDir);

            // Enable Record flag via reflection
            var recordField = recorderType.GetField("Record",
                BindingFlags.Public | BindingFlags.Instance);
            if (recordField != null)
                recordField.SetValue(recorder, true);

            return true;
#else
            return false;
#endif
        }

        private static void DisableDemonstrationRecorderRecording(GameObject agentGO)
        {
            if (agentGO == null) return;
#if UNITY_EDITOR
            var recorderType = Type.GetType(
                "Unity.MLAgents.Demonstrations.DemonstrationRecorder, Unity.ML-Agents");
            if (recorderType == null) return;

            var recorder = agentGO.GetComponent(recorderType);
            if (recorder == null) return;

            var recordField = recorderType.GetField("Record",
                BindingFlags.Public | BindingFlags.Instance);
            if (recordField != null)
                recordField.SetValue(recorder, false);
#endif
        }

        private static void ResolveRuntimeServices(
            out MatchManager match,
            out GridManager grid,
            out UnitRegistry registry,
            out MatchBootstrap bootstrap,
            out ResourceManager resources,
            List<string> missing,
            List<string> resolved)
        {
            missing.Clear();
            resolved.Clear();

            match = MatchManager.Instance;
            grid = GridManager.Instance;
            registry = UnitRegistry.Instance;
            bootstrap = MatchBootstrap.Instance;
            resources = ResourceManager.Instance;

            if (match == null) missing.Add("MatchManager"); else resolved.Add("MatchManager");
            if (grid == null) missing.Add("GridManager"); else resolved.Add("GridManager");
            if (registry == null) missing.Add("UnitRegistry"); else resolved.Add("UnitRegistry");
            if (bootstrap == null) missing.Add("MatchBootstrap"); else resolved.Add("MatchBootstrap");
            if (resources == null) missing.Add("ResourceManager"); else resolved.Add("ResourceManager");
        }

        private static string TryGetLatestTempDemo(string projectRoot)
        {
            try
            {
                string tempDir = Path.GetFullPath(Path.Combine(projectRoot, RuntimeDemoTempDir));
                if (!Directory.Exists(tempDir)) return string.Empty;
                string[] demos = Directory.GetFiles(tempDir, "*.demo", SearchOption.TopDirectoryOnly);
                if (demos == null || demos.Length == 0) return string.Empty;

                string latest = demos[0];
                DateTime latestWrite = File.GetLastWriteTimeUtc(latest);
                for (int i = 1; i < demos.Length; i++)
                {
                    DateTime candidateWrite = File.GetLastWriteTimeUtc(demos[i]);
                    if (candidateWrite > latestWrite)
                    {
                        latest = demos[i];
                        latestWrite = candidateWrite;
                    }
                }

                return latest;
            }
            catch
            {
                return string.Empty;
            }
        }

        private static bool TryCopyFile(string sourcePath, string targetPath, out string error)
        {
            try
            {
                File.Copy(sourcePath, targetPath, true);
                error = string.Empty;
                return true;
            }
            catch (Exception ex)
            {
                error = ex.Message;
                return false;
            }
        }

        private static void UpdateUnityConsoleCounts(Stage7BDemoRecordingSmokeReport report)
        {
            if (report == null) return;
            // Keep counts conservative. Editor log count APIs can include stale historical entries
            // and produce misleading values for this smoke report.
            report.unity_console_error_count = Math.Max(0, report.unity_console_error_count);
            report.unity_console_warning_count = Math.Max(0, report.unity_console_warning_count);
        }

        // ── helpers ──────────────────────────────────────────────────────────

        private static Stage7BTeacherReplayTeacherCommand[] GetTeacherCommands(Stage7BTeacherTrajectoryStep step)
        {
            if (step == null) return Array.Empty<Stage7BTeacherReplayTeacherCommand>();
            if (step.HasTeacherCommandList) return step.teacher_commands_list;
            if (!string.IsNullOrWhiteSpace(step.teacher_commands_t_json))
                return ParseCommandArray(step.teacher_commands_t_json);
            if (!string.IsNullOrWhiteSpace(step.teacher_commands))
                return ParseCommandArray(step.teacher_commands);
            return Array.Empty<Stage7BTeacherReplayTeacherCommand>();
        }

        private static Stage7BTeacherReplayTeacherCommand[] ParseCommandArray(string jsonArray)
        {
            if (string.IsNullOrWhiteSpace(jsonArray))
                return Array.Empty<Stage7BTeacherReplayTeacherCommand>();
            string wrapped = "{\"items\":" + jsonArray + "}";
            Stage7BTeacherReplayTeacherCommandArrayWrapper wrapper =
                JsonUtility.FromJson<Stage7BTeacherReplayTeacherCommandArrayWrapper>(wrapped);
            return wrapper?.items ?? Array.Empty<Stage7BTeacherReplayTeacherCommand>();
        }

        private static string ToSnakeCase(Stage7BTeacherReplayDropReason reason)
        {
            string s = reason.ToString();
            var sb = new StringBuilder(s.Length + 4);
            for (int i = 0; i < s.Length; i++)
            {
                if (i > 0 && char.IsUpper(s[i])) sb.Append('_');
                sb.Append(char.ToLowerInvariant(s[i]));
            }

            return sb.ToString();
        }

        private string ClassifyDropReason(
            Stage7BTeacherReplayTeacherCommand command,
            Stage7BTeacherReplayDropReason fallbackReason,
            GridManager grid,
            UnitRegistry registry)
        {
            string fallback = ToSnakeCase(fallbackReason);
            if (!_produceFilteringEnabled
                || command == null
                || command.action_type != ActionContract.ACTION_PRODUCE)
            {
                return fallback;
            }

            GridPosition actorPos = ResolveActorPosition(command);
            UnitRuntime actor = null;
            if (actorPos.IsInsideMap() && grid != null)
            {
                grid.TryGetOccupant(actorPos, out actor);
            }

            int rawProduceType = command.produce_unit_type;
            if (actor != null && actor.Type == UnitType.Worker && rawProduceType == 1)
            {
                _report.unsupported_worker_build_base_dropped++;
                return "unsupported_worker_build_base";
            }

            if (actor != null
                && actor.Type == UnitType.Worker
                && rawProduceType == 2
                && HasAliveBarracks(registry, actor.Owner))
            {
                _report.unity_one_barracks_cap_dropped++;
                return "runtime_state_semantics_gap_unity_one_barracks_cap";
            }

            _report.unclassified_produce_dropped++;
            return "unclassified_produce_" + fallback;
        }

        private static GridPosition ResolveActorPosition(Stage7BTeacherReplayTeacherCommand command)
        {
            if (command != null && command.actor_flat >= 0 && command.actor_flat < ActionContract.TotalCells)
            {
                return GridPosition.FromFlatIndex(command.actor_flat);
            }

            return command != null
                ? new GridPosition(command.actor_x, command.actor_y)
                : GridPosition.Zero;
        }

        private static bool HasAliveBarracks(UnitRegistry registry, Owner owner)
        {
            if (registry == null) return false;
            List<UnitRuntime> units = registry.GetUnitsByOwner(owner);
            for (int i = 0; i < units.Count; i++)
            {
                UnitRuntime unit = units[i];
                if (unit != null && unit.IsAlive && unit.Type == UnitType.Barracks)
                {
                    return true;
                }
            }

            return false;
        }

        private static string ActionTypeToString(int t)
        {
            switch (t)
            {
                case 0: return "noop";
                case 1: return "move";
                case 2: return "harvest";
                case 3: return "return";
                case 4: return "produce";
                case 5: return "attack";
                default: return "unknown_" + t;
            }
        }

        private static void AddDropReason(Stage7BDemoRecordingSmokeReport report, string key)
        {
            if (string.IsNullOrWhiteSpace(key)) return;
            for (int i = 0; i < report.drop_reason_histogram.Count; i++)
            {
                if (report.drop_reason_histogram[i].key == key)
                {
                    report.drop_reason_histogram[i].value++;
                    return;
                }
            }

            report.drop_reason_histogram.Add(
                new Stage7BTeacherReplayMetricEntry { key = key, value = 1 });
        }

        private static string BuildMarkdown(Stage7BDemoRecordingSmokeReport r)
        {
            var sb = new StringBuilder(4096);
            sb.AppendLine("# Stage7B-7D Clean Demo Recording Smoke Report");
            sb.AppendLine();
            sb.AppendLine("- status: " + r.status);
            sb.AppendLine("- generated_at_utc: " + r.generated_at_utc);
            sb.AppendLine("- demo_file_path: " + r.demo_file_path);
            sb.AppendLine("- demo_file_exists: " + r.demo_file_exists.ToString().ToLowerInvariant());
            sb.AppendLine("- demo_file_size_bytes: " + r.demo_file_size_bytes);
            sb.AppendLine("- behavior_name: " + r.behavior_name);
            sb.AppendLine("- observation_size: " + r.observation_size);
            sb.AppendLine("- discrete_branch_count: " + r.discrete_branch_count);
            sb.AppendLine("- candidate_branch_size: " + r.candidate_branch_size);
            sb.AppendLine("- source_path: " + r.source_path);
            sb.AppendLine("- source_replay_ready: " + r.source_replay_ready.ToString().ToLowerInvariant());
            sb.AppendLine("- direction_mapping_mode: " + r.direction_mapping_mode);
            sb.AppendLine("- produce_filtering_enabled: " + r.produce_filtering_enabled.ToString().ToLowerInvariant());
            sb.AppendLine("- started_from_edit_mode: " + r.started_from_edit_mode.ToString().ToLowerInvariant());
            sb.AppendLine("- entered_play_mode: " + r.entered_play_mode.ToString().ToLowerInvariant());
            sb.AppendLine("- play_mode_ready: " + r.play_mode_ready.ToString().ToLowerInvariant());
            sb.AppendLine("- runtime_services_ready: " + r.runtime_services_ready.ToString().ToLowerInvariant());
            sb.AppendLine("- runtime_services_wait_seconds: " + r.runtime_services_wait_seconds.ToString("0.###", System.Globalization.CultureInfo.InvariantCulture));
            sb.AppendLine("- missing_runtime_services: [" + string.Join(", ", r.missing_runtime_services) + "]");
            sb.AppendLine("- resolved_runtime_services: [" + string.Join(", ", r.resolved_runtime_services) + "]");
            sb.AppendLine("- startup_failure_reason: " + r.startup_failure_reason);
            sb.AppendLine("- unity_console_error_count: " + r.unity_console_error_count);
            sb.AppendLine("- unity_console_warning_count: " + r.unity_console_warning_count);
            sb.AppendLine();
            sb.AppendLine("## Recording Metrics");
            sb.AppendLine();
            sb.AppendLine("- episodes_scanned: " + r.episodes_scanned);
            sb.AppendLine("- steps_scanned: " + r.steps_scanned);
            sb.AppendLine("- teacher_commands_total: " + r.teacher_commands_total);
            sb.AppendLine("- matched_commands: " + r.matched_commands);
            sb.AppendLine("- recorded_decisions: " + r.recorded_decisions);
            sb.AppendLine("- dropped_commands: " + r.dropped_commands);
            sb.AppendLine("- no_teacher_command_steps_skipped: " + r.no_teacher_command_steps_skipped);
            sb.AppendLine();
            sb.AppendLine("## Produce Filtering");
            sb.AppendLine();
            sb.AppendLine("- unsupported_worker_build_base_dropped: " + r.unsupported_worker_build_base_dropped);
            sb.AppendLine("- unity_one_barracks_cap_dropped: " + r.unity_one_barracks_cap_dropped);
            sb.AppendLine("- unclassified_produce_dropped: " + r.unclassified_produce_dropped);
            sb.AppendLine();
            sb.AppendLine("## Runtime Apply");
            sb.AppendLine();
            sb.AppendLine("- runtime_apply_attempted_count: " + r.runtime_apply_attempted_count);
            sb.AppendLine("- runtime_apply_accepted_count: " + r.runtime_apply_accepted_count);
            sb.AppendLine("- runtime_apply_rejected_count: " + r.runtime_apply_rejected_count);
            string rateStr = r.runtime_apply_accept_rate < 0f
                ? "n/a"
                : r.runtime_apply_accept_rate.ToString("0.######",
                    System.Globalization.CultureInfo.InvariantCulture);
            sb.AppendLine("- runtime_apply_accept_rate: " + rateStr);
            sb.AppendLine();
            sb.AppendLine("## Action Type Breakdown");
            sb.AppendLine();
            sb.AppendLine("- return_commands_recorded: " + r.return_commands_recorded);
            sb.AppendLine("- move_commands_recorded: " + r.move_commands_recorded);
            sb.AppendLine("- harvest_commands_recorded: " + r.harvest_commands_recorded);
            sb.AppendLine("- produce_commands_recorded: " + r.produce_commands_recorded);
            sb.AppendLine("- attack_commands_recorded: " + r.attack_commands_recorded);
            sb.AppendLine();
            sb.AppendLine("## Drop Reason Histogram");
            sb.AppendLine();
            if (r.drop_reason_histogram.Count == 0)
            {
                sb.AppendLine("- (none)");
            }
            else
            {
                for (int i = 0; i < r.drop_reason_histogram.Count; i++)
                    sb.AppendLine("- " + r.drop_reason_histogram[i].key + ": " +
                                  r.drop_reason_histogram[i].value);
            }

            sb.AppendLine();
            sb.AppendLine("## GO / NO-GO Decision");
            sb.AppendLine();
            sb.AppendLine("- **status: " + r.status + "**");
            sb.AppendLine("- demo_recording_ready_for_imitation_smoke: " +
                          r.demo_recording_ready_for_imitation_smoke.ToString().ToLowerInvariant());
            sb.AppendLine("- stage6b3_baseline_touched: " +
                          r.stage6b3_baseline_touched.ToString().ToLowerInvariant());
            sb.AppendLine("- return_mapping_mode: " + r.return_mapping_mode);
            sb.AppendLine("- direction_mapping_mode: " + r.direction_mapping_mode);
            sb.AppendLine();

            if (r.status == "GO")
            {
                sb.AppendLine("**Stage7B-8 small imitation smoke can proceed.**");
            }
            else
            {
                sb.AppendLine("**HOLD — Review NO-GO criteria above before proceeding.**");
            }

            sb.AppendLine();
            sb.AppendLine("## Notes");
            sb.AppendLine();
            for (int i = 0; i < r.notes.Count; i++)
                sb.AppendLine("- " + r.notes[i]);

            return sb.ToString();
        }

        // ── inner types ──────────────────────────────────────────────────────

        private sealed class DemoQueueEntry
        {
            public int episodeId;
            public int stepId;
            public string stateJson;
            public int candidateActionIndex;
            public int actionType;
        }
    }

    // ── serializable report and trace types (used by orchestrator + reports) ──

    [Serializable]
    public sealed class Stage7BDemoRecordingSmokeReport
    {
        public string status;
        public string generated_at_utc;
        public string demo_file_path;
        public bool demo_file_exists;
        public long demo_file_size_bytes;
        public string behavior_name;
        public int observation_size;
        public int discrete_branch_count;
        public int candidate_branch_size;
        public string source_path;
        public bool source_replay_ready;
        public int episodes_scanned;
        public int steps_scanned;
        public int teacher_commands_total;
        public int matched_commands;
        public int recorded_decisions;
        public int dropped_commands;
        public int no_teacher_command_steps_skipped;
        public int runtime_apply_attempted_count;
        public int runtime_apply_accepted_count;
        public int runtime_apply_rejected_count;
        public float runtime_apply_accept_rate = -1f;
        public string direction_mapping_mode;
        public string return_mapping_mode;
        public bool produce_filtering_enabled;
        public int unsupported_worker_build_base_dropped;
        public int unity_one_barracks_cap_dropped;
        public int unclassified_produce_dropped;
        public int return_commands_recorded;
        public int move_commands_recorded;
        public int harvest_commands_recorded;
        public int produce_commands_recorded;
        public int attack_commands_recorded;
        public bool demo_recording_ready_for_imitation_smoke;
        public bool stage6b3_baseline_touched;
        public int max_recorded_decisions;
        public int max_episodes;
        public bool started_from_edit_mode;
        public bool entered_play_mode;
        public bool play_mode_ready;
        public bool runtime_services_ready;
        public float runtime_services_wait_seconds;
        public List<string> missing_runtime_services = new List<string>();
        public List<string> resolved_runtime_services = new List<string>();
        public List<string> runtime_service_readiness_trace = new List<string>();
        public string startup_failure_reason = string.Empty;
        public int unity_console_error_count;
        public int unity_console_warning_count;
        public List<Stage7BTeacherReplayMetricEntry> drop_reason_histogram =
            new List<Stage7BTeacherReplayMetricEntry>();
        public List<string> notes = new List<string>();
    }

    [Serializable]
    public sealed class Stage7BDemoRecordingTraceEntry
    {
        public int episode_id;
        public int step_id;
        public int candidate_action_index;
        public int action_type;
        public string action_summary;
        public bool runtime_apply_accepted;
    }

    [Serializable]
    public sealed class Stage7BDemoRecordingDroppedEntry
    {
        public int episode_id;
        public int step_id;
        public int command_index;
        public int action_type;
        public string drop_reason;
    }
}
