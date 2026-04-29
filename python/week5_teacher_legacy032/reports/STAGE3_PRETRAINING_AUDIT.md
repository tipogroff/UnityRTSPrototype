# Stage 3 Pre-Training Audit (legacy032)

Date: 2026-04-29
Stage name (fixed): Stage 3 - Staged teacher training with behavior gates

## Baseline checkpoint from Stage 2

- smoke baseline run_id: legacy032_smoke_20260429T113844Z
- checkpoint used for Stage 3 smoke gate:
  - python/week5_teacher_legacy032/teacher_models/legacy032_smoke_20260429T113844Z/agent_final.pt
- metadata used:
  - python/week5_teacher_legacy032/teacher_models/legacy032_smoke_20260429T113844Z/model_metadata.json

## Reference script audited

- script path:
  - python/week5_teacher_reference/patched_paper_scripts/ppo_gridnet_diverse_encode_decode_local_save.py

### Checkpoint save behavior in reference script

- final checkpoint save:
  - save_local_model(...) writes agent_final.pt and model_metadata.json
- staged/intermediate checkpoint save:
  - save_local_checkpoint(...) writes agent_step_<global_step>.pt
  - controlled by CLI flag --local-save-every (if > 0)
- local save enable switch:
  - --local-save-model true
  - --local-save-dir <dir>

### Resume support status

- explicit local resume-from-checkpoint CLI: not present
- script has crash/resume logic tied to wandb prod_mode and wandb.run.resumed
- conclusion:
  - robust local non-wandb resume is unsupported in this script

### Can map/env be configured via CLI?

- parser has --gym-id argument, but actual training env is created by direct MicroRTSGridModeVecEnv(...) call with hardcoded map_path.
- internal env creation in script currently uses:
  - map_path = maps/16x16/basesWorkers16x16.xml
  - action contract from internal grid mode env
- conclusion:
  - main training currently runs through internal reference config regardless of legacy wrapper preflight env/map

## Mask path audit

Mask path is confirmed in reference script:

- mask source during action selection:
  - envs.vec_client.getMasks(0)
- mask split by branches:
  - torch.split(invalid_action_masks[:, 1:], envs.action_space.nvec[1:].tolist(), dim=1)
- mask application:
  - CategoricalMasked uses torch.where(self.masks, logits, -1e8)

## Environment and action-space contracts involved

- preflight target (legacy Stage 1 probe):
  - env_id: MicrortsRandomEnemyShapedReward1-v1
  - map: maps/24x24/basesWorkers24x24.xml
  - observation: (24, 24, 27)
  - action_space.nvec: [576, 6, 4, 4, 4, 4, 7, 576]
  - representation: global single-action mode

- internal reference training (observed in Stage 2 metadata and script):
  - env_id in metadata: MicrortsDefeatCoacAIShaped-v3
  - map in script: maps/16x16/basesWorkers16x16.xml
  - observation: [16, 16, 27]
  - action_space in metadata: MultiDiscrete([256, 6, 4, 4, 4, 4, 7, 49])
  - representation: grid-mode internal reference contract

## Stage 3 compatibility implications

The Stage 3 behavior gate must validate actual inference compatibility with the internal reference env/action space and explicitly report mismatch against preflight 24x24.

Observed and expected outcomes:

- checkpoint loading and policy inference are valid on reference internal 16x16 env/action space
- checkpoint is not directly evaluable on preflight 24x24 global-single-action contract

## Risks for Stage 5/6 export and adaptation

- env/action mismatch risk:
  - teacher checkpoints from this path represent 16x16 internal grid mode behavior; direct claim of 24x24 legacy target compatibility is invalid
- adaptation risk:
  - Stage 5/6 export and adapter logic must explicitly document source contract before producing Unity v2 artifacts
- evaluation risk:
  - gate PASS on 16x16 internal env does not imply readiness for 24x24 target preflight contract
- pipeline risk:
  - if future stages require 24x24 behavior parity, training script must be changed or replaced; this Stage 3 does not modify reference script behavior

## Stage 3 strategy decision for this repository state

Selected safe strategy:

- Stage 3A run 100k sanity training checkpoint and run behavior gate
- keep staged plan and commands for 500k/1M/3M/5M
- avoid false resume claims
- do not claim final teacher selection at Stage 3A
