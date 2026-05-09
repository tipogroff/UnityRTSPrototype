# Stage7B ML-Agents Student Runtime Contract

Stage7B adds a Unity-native ML-Agents wrapper around the RTS student without changing the Stage6B3 baseline, checkpoint, Python bridge, or successful runtime pipeline.

## Scene

- Scene: `Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity`
- Runtime bootstrap: `Assets/Scripts/MLAgents/Stage7B/MlAgentsTrainingBootstrap.cs`
- Agent: `Assets/Scripts/MLAgents/Stage7B/StudentMlAgent.cs`

## Observation

- `StudentMlAgent.CollectObservations()` uses the existing `RTS.ML.ObservationBuilder`.
- First pass observation is spatial vector only:
  - shape source: `24 * 24 * 27`
  - vector length: `15552`
  - no global feature vector is appended
- The wrapper validates:
  - exact length
  - NaN / Infinity
  - value range `[0, 1]`
- Observation mode is `ObservationMode.UnityMvpTransfer`, preserving the current Unity player-perspective owner encoding and normalization already used by the student runtime contract.

## Action

- ML-Agents `BehaviorParameters` are configured as one discrete branch:
  - branch `0`: `candidate_action_index`
  - branch size: `128`
- Stage7B follows the current Stage6B3/v2-compatible attack target contract:
  - `attack_target_local` size: `49`
  - local window: `7x7`
  - center index: `24`
- The wrapper does not expose actor/action/direction/produce/attack branches directly to ML-Agents.
- It does not expose the full `576`-cell GridNet action output as the ML-Agents action space.

## Decision Source

- Preferred decision source: `DecisionRequester`
- Manual `FixedUpdate` decision requests are disabled by default and available only through an explicit serialized debug flag.
- Stage7B contains a one-source-at-a-time watchdog fallback for runtime hardening:
  - if `DecisionRequester` stalls before producing actions in Play Mode,
  - it is disabled,
  - Stage7B switches to `manual_fixed_update` requests exclusively,
  - and the dry-run artifact records `decision_source = decision_requester_watchdog_manual_fallback`
- This guard exists to prevent silent stalls while still preventing concurrent dual decision loops.

## Runtime Authority

- Candidate masks are pre-sampling hints only.
- `ActionApplier` and `MatchManager` remain the authoritative runtime validation and execution path.
- `StudentMlAgent.OnActionReceived()` converts the selected candidate index to an `AgentAction` and submits it through `ActionApplier`.

## Diagnostics

The dry-run artifact is written as:

`stage7b_mlagents_heuristic_dryrun.json`

It records ML-Agents package version, decision source, behavior/action metadata, observation calls, mask calls, selected candidate counts, candidate fallback counters, accepted/rejected commands, reward sum, terminal/reset state, duplicate spawn detection, and `stage6b3_files_touched`.
