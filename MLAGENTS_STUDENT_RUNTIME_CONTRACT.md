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
- The wrapper does not expose actor/action/direction/produce/attack branches directly to ML-Agents.
- It does not expose the full `576`-cell GridNet action output as the ML-Agents action space.

## Runtime Authority

- Candidate masks are pre-sampling hints only.
- `ActionApplier` and `MatchManager` remain the authoritative runtime validation and execution path.
- `StudentMlAgent.OnActionReceived()` converts the selected candidate index to an `AgentAction` and submits it through `ActionApplier`.

## Diagnostics

The dry-run artifact is written as:

`stage7b_mlagents_heuristic_dryrun.json`

It records ML-Agents package version, observation calls, mask calls, selected candidate counts, accepted/rejected commands, reward sum, terminal/reset state, and duplicate spawn detection.
