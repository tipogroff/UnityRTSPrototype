# Project-Compatible Gridnet Teacher Plan (Branch B)

## 1) Why Branch B exists
Branch B exists because the current project-compatible Week5 teacher recipe (MaskablePPO + movement_warmup) is not producing stable actor-level effective movement, even though mask semantics and masked-random movement feasibility are confirmed.

The objective is to bring proven Gridnet training ingredients into a project-compatible branch without breaking Unity/BC pipelines or claiming unsupported parity.

## 2) What the Reference branch proved
Reference reproduction proved that the patched paper-style Gridnet pipeline can train and exhibit meaningful behavior in gym_microrts==0.3.2:
- smoke 10k PASS
- staged long 100k PASS
- local-save 100k PASS
- script: ppo_gridnet_diverse_encode_decode_local_save.py
- env: MicrortsDefeatCoacAIShaped-v3
- observation surface actually used: [16,16,27]
- action space: MultiDiscrete([256,6,4,4,4,4,7,49])
- visible behavior: movement, harvesting, barracks construction, unit production, attack
- local artifacts: agent_final.pt, model_metadata.json

## 3) What the Reference branch did NOT prove
Reference branch did NOT prove:
- Unity compatibility of produced checkpoints
- Gym-to-Unity policy transfer parity
- immediate compatibility with current Week5 BC pipeline formats
- correctness under project 24x24 action semantics

The reference checkpoint is explicitly not to be copied into Week5/BC/Unity artifacts.

## 4) What will be ported from Reference into Branch B
Branch B ports architecture and training mechanics, not weights:
- Gridnet encoder-decoder architecture
- paper-style invalid action masking and action sampling
- diverse bot opponent setup
- local checkpoint saving format for reproducible audit
- staged training budgets (smoke then 100k sanity)

## 5) What remains project-compatible
Branch B enforces project-compatible constraints:
- target observation surface remains 24x24 / 27-channel
- project behavior gate vocabulary remains the evaluation language
- artifact discipline under WEEK5R run directories
- no direct checkpoint reuse from reference branch

## 6) Key risks
Main adaptation risks:
- action space mismatch between reference and project-compatible env variants
- 16x16 (reference) versus 24x24 (project target)
- gym raw action flattening [4032]-style vs project actor-level [576,7] interpretation
- attack targeting mismatch: reference 49 global target branch vs Unity 9 local target semantics
- produce-type branch mismatch across env adapters

## 7) Initial success criteria
Initial Branch B success criteria:
- local checkpoint files are saved successfully
- actor-level gate/eval does not collapse into pure no-effect behavior
- effective_position_delta_count > 0
- no_effect_action_share < 1.0
- visual trace confirms movement at actor level

## 8) Execution order (first pass)
1. Smoke run 10k (stability/no-crash only)
2. If stable, run staged 100k
3. Evaluate actor-level movement at checkpoints
4. Compare outcomes against reference and prior project-compatible PPO runs

## 9) Non-goals
Branch B non-goals:
- do not import reference weights
- do not adapt reference checkpoint to Unity
- do not modify Unity-side code
- do not modify BC pipeline
- do not generate BC dataset from first Gridnet run
- do not claim teacher-ready until actor-level gate/eval passes
