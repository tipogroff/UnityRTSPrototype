# Stage7B-6D Runtime State Hook No-Go

- Date (UTC): 2026-05-10
- Scope: legacy032 runtime-state instrumentation feasibility for replay-ready teacher export
- Probe report JSON: python/week5_teacher_legacy032/reports/stage7b_legacy032_runtime_state_api_probe.json
- Probe report MD: python/week5_teacher_legacy032/reports/stage7b_legacy032_runtime_state_api_probe.md
- Result: NO-GO (authoritative runtime state API not exposed in current Python bridge)

## Verified Constraints

- No ML-Agents training executed.
- No PPO training in Unity executed.
- No imitation learning executed.
- No .demo recording executed.
- Stage6B3 baseline/checkpoint/bridge were not modified.
- No fake state synthesized from observation.

## Objects Probed (before and after one env.step)

- env
- env.vec_client
- env.vec_client.clients
- env.vec_client.clients[0]
- env.vec_client.selfPlayClients
- env.render_client

## Candidate Runtime-State Methods Requested

- getState
- getGameState
- getPhysicalGameState
- getUnit
- getUnits
- toJSON
- toXML
- getTrace
- getPlayers
- getResources

## Candidate Runtime-State Method Presence

- getState: not found
- getGameState: not found
- getPhysicalGameState: not found
- getUnit: not found
- getUnits: not found
- toJSON: not found
- toXML: not found
- getTrace: not found
- getPlayers: not found
- getResources: not found

## Keyword Method Scan (state/unit/game/json/xml/physical/player/resource/trace)

- env.vec_client: gameStep
- env.vec_client.clients[0]: gameStep
- env.render_client: gameStep

No method exposing serialized authoritative game state was discovered.

## Why Runtime State Is Unavailable

Current legacy032 Python wrapper (gym_microrts envs vec_env) exposes:

- reset() observation tensor only;
- step()/gameStep() observation, reward, done, and lightweight info raw_rewards;
- action-mask access via vec_client.getMasks.

It does not expose authoritative pre/post step runtime state snapshots (units/resources/queues/terminal metadata) through Python-accessible methods.

## Required Instrumentation Patch Plan

### 1) Python wrapper extension (first patch point)

File to patch:

- python/week5_teacher_reference/.venv_microrts032_reference/Lib/site-packages/gym_microrts/envs/vec_env.py

Minimal additions in MicroRTSGridModeVecEnv:

- Add helper method get_runtime_state_json(self, env_index: int = 0) -> dict
- Add helper method get_runtime_state_batch_json(self) -> list[dict]
- In reset(), capture and store initial state payload per env.
- In step_wait(), capture both:
  - runtime_state_t_json: state before gameStep
  - runtime_state_tp1_json: state after gameStep
- Inject these fields into infos[i] for each env index.

Required info payload contract per step info:

- info["initial_state_json"]
- info["runtime_state_t_json"]
- info["runtime_state_tp1_json"]

### 2) JNI bridge extension (second patch point)

Object to patch:

- ts.JNIGridnetVecClient (Java side and JPype-exposed API)

Add JPype-callable methods:

- getRuntimeStateJSON(int envIdx)
- getRuntimeStateBatchJSON()
- getInitialStateJSON(int envIdx) (optional if reset path stores separately)

Return type options:

- Preferred: java.lang.String (JSON string) for robust JPype transfer.
- Alternative: java.util.Map / structured Java object converted in Python.

### 3) Java-side serialization source (authoritative state)

Add serializer in MicroRTS game/client layer used by JNIGridnetVecClient that reads actual runtime objects (not observation planes):

- map dimensions;
- game step/tick counter;
- players with resources;
- units with stable IDs and owner/type/position/stats;
- resource node remaining values;
- production queues for producing buildings;
- terminal state (done/winner/reason).

### 4) Minimal JSON schema required for Unity replay

```json
{
  "map_width": 24,
  "map_height": 24,
  "step": 0,
  "players": [
    {"player_id": 0, "resources": 0},
    {"player_id": 1, "resources": 0}
  ],
  "units": [
    {
      "id": 0,
      "type": "Worker",
      "owner": 0,
      "x": 0,
      "y": 0,
      "hp": 1,
      "resources": 0,
      "carried_resources": 0,
      "current_action": null,
      "pending_action": null
    }
  ],
  "resource_nodes": [
    {"x": 0, "y": 0, "remaining": 0}
  ],
  "building_queues": [
    {
      "building_id": 0,
      "x": 0,
      "y": 0,
      "producing_unit_type": null,
      "progress": null,
      "remaining": null
    }
  ],
  "terminal": {
    "done": false,
    "winner": null,
    "reason": null
  }
}
```

## Exporter Impact for Stage7B-6D

Until the wrapper/JNI patch above is implemented, exporter must remain honest:

- replay_ready must stay false when state fields are absent;
- no synthetic/fake runtime state should be emitted;
- validation errors for missing state fields are expected and correct.
