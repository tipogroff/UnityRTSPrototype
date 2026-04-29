# Stage 2 Reference Script Audit (legacy032)

## Scope

Audit target:

- python/week5_teacher_reference/patched_paper_scripts/ppo_gridnet_diverse_encode_decode_local_save.py
- python/week5_teacher_reference/scripts/run_reference_training_smoke.ps1
- python/week5_teacher_reference/scripts/run_reference_training_long.ps1
- python/week5_teacher_reference/scripts/verify_reference_env.py
- python/week5_teacher_reference/RUN_REFERENCE_TRAINING.md
- python/week5_teacher_reference/REFERENCE_REPRODUCTION_RESULT.md

Goal of this audit:

- confirm practical training entrypoint already used for legacy 0.3.2 runs;
- document env creation and PPO wiring path;
- document checkpoint/log behavior;
- investigate invalid action mask path in training code.

This audit does not claim Unity v2 parity and does not claim final teacher quality.

---

## Which script was used in prior successful legacy runs

Confirmed from reference docs and artifacts:

- primary smoke script in reference workspace historically called:
  - ppo_gridnet_diverse_encode_decode.py (through run_reference_training_smoke.ps1)
- patched local-save variant used for checkpoint-producing run:
  - ppo_gridnet_diverse_encode_decode_local_save.py

Evidence in docs:

- REFERENCE_REPRODUCTION_RESULT.md states 100k local-save sanity run PASS using ppo_gridnet_diverse_encode_decode_local_save.py with checkpoints found.
- run_reference_training_long.ps1 explicitly switches to patched local-save script when -LocalSaveModel is passed.

Conclusion:

- For Stage 2 smoke in legacy032, the practical reusable reference entrypoint is the patched script:
  ppo_gridnet_diverse_encode_decode_local_save.py.

---

## How env is created in reference training script

In ppo_gridnet_diverse_encode_decode_local_save.py:

- env object is created directly via MicroRTSGridModeVecEnv;
- map path is hardcoded to maps/16x16/basesWorkers16x16.xml;
- reward weights are hardcoded to [10.0, 1.0, 1.0, 0.2, 1.0, 4.0];
- wrappers applied:
  - MicroRTSStatsRecorder
  - VecMonitor
  - optional VecVideoRecorder when --capture-video.

Important constraint:

- this reference script does not expose --env-id or --map-path CLI for direct override;
- it uses internal vec env construction (MicroRTSGridModeVecEnv) instead of gym.make(env_id,...).

Implication for Stage 2 wrapper:

- wrapper can preflight-check target env_id/map_path separately;
- actual reference training subprocess may still run with the script-internal env configuration.

---

## PPO wiring in reference script

Training stack in ppo_gridnet_diverse_encode_decode_local_save.py:

- custom PPO implementation (not SB3 PPO class);
- encoder-decoder policy network;
- custom CategoricalMasked distribution;
- rollout storage and PPO update loop implemented in-script;
- tensorboard via SummaryWriter.

Observed key runtime controls:

- --total-timesteps
- --seed
- --num-bot-envs
- --num-selfplay-envs
- --cuda
- --capture-video
- --local-save-model
- --local-save-dir
- --local-save-every

Compatibility note from reference scripts:

- num_bot_envs must be >= 6 to satisfy ai2s setup used by the paper recipe wrapper.

---

## Checkpoint and logs behavior

From patched script and reference wrappers:

- local checkpoint/model saving is available through:
  - --local-save-model true
  - --local-save-dir <dir>
  - --local-save-every <N>
- final model artifact path:
  - <local-save-dir>/agent_final.pt
- metadata path:
  - <local-save-dir>/model_metadata.json
- optional intermediate checkpoints:
  - <local-save-dir>/agent_step_XXXXXXXXX.pt

Logging behavior:

- tensorboard logs in runs/<experiment_name>;
- stdout includes progress lines (including global_step and SPS);
- no wandb required when WANDB_MODE=disabled and prod mode not enabled.

---

## Mask path investigation

### Result

Mask path is confirmed in reference training pipeline.

### Where it is found

In ppo_gridnet_diverse_encode_decode_local_save.py:

- class CategoricalMasked applies masks to logits via torch.where;
- get_action(...) retrieves masks from envs.vec_client.getMasks(0);
- mask tensor is split by envs.action_space.nvec[1:] branch sizes;
- masked categorical sampling is used to sample branch actions;
- invalid_action_masks are propagated for rollout/update calculations.

### Interpretation

- mask is not exposed through simple probe APIs used in Stage 1;
- training code accesses masking through vec-client internals in the reference env pipeline;
- therefore absence of a public env.get_action_mask API is not evidence that masking is absent.

Canonical Stage 2 wording:

- Mask was not exposed through env probe APIs, but training pipeline uses it through envs.vec_client.getMasks(0) and CategoricalMasked masking in the reference script.

---

## Reuse strategy for legacy032 Stage 2

Chosen strategy:

- create thin wrapper in python/week5_teacher_legacy032/scripts/train_teacher_legacy032.py;
- invoke patched reference script as subprocess;
- force all artifacts into legacy032 directories;
- capture stdout/stderr and machine-readable summary;
- keep week5_teacher_reference as read-only source.

Reason:

- avoids rewriting complex paper PPO logic;
- preserves known-working legacy training behavior;
- isolates artifacts away from reference and main pipelines.

---

## Stage 2 caveats recorded

- Stage 2 checkpoint is a smoke artifact only and is not a final teacher.
- Stage 2 does not run adapter, BC export, or semantic parity checks.
- Stage 3 behavior gate should use Stage 2 checkpoint only as readiness artifact.
