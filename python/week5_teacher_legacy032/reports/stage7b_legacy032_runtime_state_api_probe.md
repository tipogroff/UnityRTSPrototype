# Stage7B Legacy032 Runtime-State API Probe

- generated_at_utc: 2026-05-10T01:45:51Z
- map_path: maps/24x24/basesWorkers24x24.xml
- num_bot_envs: 1
- max_steps: 64
- runtime_state_api_found: False

## Step Smoke
- reset_obs_shape: [1, 24, 24, 27]
- step_status: ok
- reward_sample: 0.0
- done_sample: False
- truncated_sample: False
- next_obs_shape: [1, 24, 24, 27]
- mask_source: env.vec_client.getMasks(0)

## Candidate Methods
- getState: before=[] after=[]
- getGameState: before=[] after=[]
- getPhysicalGameState: before=[] after=[]
- getUnit: before=[] after=[]
- getUnits: before=[] after=[]
- toJSON: before=[] after=[]
- toXML: before=[] after=[]
- getTrace: before=[] after=[]
- getPlayers: before=[] after=[]
- getResources: before=[] after=[]

## Conclusion
- No explicit runtime-state API candidate methods were discovered on probed objects.
- Authoritative replay state snapshots are currently unavailable from Python without JNI/Java bridge extension.
