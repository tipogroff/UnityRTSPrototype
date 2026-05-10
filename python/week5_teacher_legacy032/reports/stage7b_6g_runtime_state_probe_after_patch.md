# Stage7B Legacy032 Runtime-State API Probe

- generated_at_utc: 2026-05-10T13:15:55Z
- map_path: maps/24x24/basesWorkers24x24.xml
- num_bot_envs: 1
- max_steps: 64
- runtime_state_api_found: True

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
- getRuntimeStateJSON: before=['env.vec_client', 'env.vec_client.clients[0]', 'env.render_client'] after=['env.vec_client', 'env.vec_client.clients[0]', 'env.render_client']
- getRuntimeStateBatchJSON: before=['env.vec_client'] after=['env.vec_client']
- getInitialStateJSON: before=['env.vec_client'] after=['env.vec_client']

## Conclusion
- Runtime-state API candidate methods were discovered; inspect JSON report invocation results.
