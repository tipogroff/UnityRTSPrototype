# Legacy032 Trainer Checkpoint Pipeline Audit

Date: 2026-05-05
Scope: Legacy032 teacher pipeline only (gym_microrts==0.3.2, Java 17, 24x24 GridMode contract)

## 1) How orchestrator invokes trainer

Orchestrator script:
- python/week5_teacher_legacy032/scripts/run_24x24_staged_teacher_training_legacy032.py

Observed orchestration behavior:
- Builds per-stage output dirs under teacher_models/<run_id>/stage_<step>.
- Invokes trainer script python/week5_teacher_legacy032/scripts/ppo_gridnet_legacy032_24x24_local_save.py with:
  - --total-timesteps <stage>
  - --map-path maps/24x24/basesWorkers24x24.xml
  - --expected-map-size 24
  - --max-steps 6000
  - --verify-contract true
  - --local-save-model true
  - --local-save-dir <stage_dir>
  - --local-save-every <stage>
- After training, orchestrator chooses checkpoint path with fallback logic:
  - preferred: agent_step_<stage>.pt
  - fallback: agent_final.pt

## 2) Where stage_003000000 is created

Path pattern used by orchestrator:
- python/week5_teacher_legacy032/teacher_models/<run_id>/stage_003000000/

For the target run:
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260430T130208Z/stage_003000000/

## 3) How agent_final.pt is saved

Trainer script:
- python/week5_teacher_legacy032/scripts/ppo_gridnet_legacy032_24x24_local_save.py

Saving logic:
- save_local_model(...) writes:
  - agent_final.pt via torch.save(agent.state_dict(), model_path)
  - model_metadata.json as sidecar JSON.
- save_local_checkpoint(...) writes:
  - agent_step_<global_step>.pt via torch.save(agent.state_dict(), checkpoint_path)

Important technical fact:
- Checkpoint payloads are plain agent.state_dict() tensors only.

## 4) Whether agent_step_*.pt exists

Pipeline behavior:
- Trainer supports periodic agent_step_<step>.pt writes via --local-save-every.
- Orchestrator explicitly checks both:
  - agent_step_<stage>.pt
  - agent_final.pt

Implication:
- Existence is run-dependent; both naming schemes are part of the pipeline contract.

## 5) Whether optimizer/global_step/RNG are saved

Evidence from trainer save logic:
- Optimizer state:
  - Not stored in checkpoint payload (no optimizer.state_dict() in local checkpoint files).
- RNG state:
  - Not serialized in checkpoint payload (no torch/numpy/python RNG snapshot in local saves).
- Global step:
  - Present in model_metadata.json (global_step field), but not as resume-ready trainer state in checkpoint payload.

Consequence:
- Local checkpoint files are inference-weight snapshots, not full training-state snapshots.

## 6) Whether local resume exists

Trainer resume path observed:
- Resume branch is tied to prod_mode + wandb.run.resumed.
- It loads models/<experiment_name>/agent.pt from W&B context.

Not observed for local stage checkpoints:
- No robust local CLI resume path that restores training from stage_*.pt/agent_final.pt plus optimizer and RNG.

Conclusion:
- Local resume support is not evidence-grade for exact training continuation.

## 7) Where strict=False is currently used

Confirmed strict=False load_state_dict usage in Legacy032 diagnostics/export stack:
- python/week5_teacher_legacy032/scripts/evaluate_teacher_legacy032.py
- python/week5_teacher_legacy032/scripts/export_teacher_rollout_legacy032.py
- python/week5_teacher_legacy032/scripts/evaluate_teacher_large_map_diagnostics.py
- python/week5_teacher_legacy032/scripts/evaluate_teacher_large_map_win_diagnostics.py
- python/week5_teacher_legacy032/scripts/run_legacy032_3m_visual_single_episode.py

## 8) Why this is insufficient for evidence-grade checkpoint verification

Reasons:
- strict=False permits partial parameter loads and silent key mismatch drift.
- Weight-only checkpoints do not prove train-time state reproducibility.
- Deterministic and stochastic action selection paths can diverge while both appear valid.
- all-cell NoOp share alone can hide source-cell behavior differences on 24x24.

Evidence-grade minimum needed:
- strict=True checkpoint load with hard-fail on missing/unexpected keys.
- Save/load roundtrip on fixed observation batch with logits/action equivalence checks.
- Deterministic and stochastic evaluation reported separately.
- Action histograms split into:
  - all-cell shares
  - source-valid-cell shares
- Explicit behavior proxies (state delta, production/harvest/return/attack counts, reward, terminal reason, episode length).

## 9) Resulting audit artifact

Implemented script:
- python/week5_teacher_legacy032/scripts/audit_legacy032_checkpoint_roundtrip.py

Script outputs to:
- python/week5_teacher_legacy032/reports/<run_label>_<timestamp>.json
- python/week5_teacher_legacy032/reports/<run_label>_<timestamp>.md

This script enforces strict=True for load checks and classifies:
- SAVE_LOAD_OK / SAVE_LOAD_FAIL
- RESUME_SUPPORTED / RESUME_NOT_SUPPORTED / RESUME_NOT_TESTED
- DETERMINISTIC_STOCHASTIC_MISMATCH_YES / NO
- CHECKPOINT_PATH_CONFIRMED / NOT_CONFIRMED
- NEXT_ACTION
