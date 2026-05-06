# Stage5O - 3M Continuation From 1M (Post-Fix)

- Date (UTC): 2026-05-06
- Stage: Stage5O
- Working directory: C:/Projects/UnityRTSPrototype/UnityRTSPrototype
- Python: c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe

## 1) Files Changed/Created

Training output directory:
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/agent_final.pt
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/model_metadata.json
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/trainer_state_final.pt
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/latest_trainer_state.json
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/training_machine_report.json
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/agent_step_001500000.pt
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/agent_step_002000000.pt
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/agent_step_002500000.pt
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/trainer_state_step_001500000.pt
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/trainer_state_step_002000000.pt
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/trainer_state_step_002500000.pt

3M post-fix evaluation outputs:
- python/week5_teacher_legacy032/reports/stage5n_postfix_behavior_revalidation_20260506T034334Z.json
- python/week5_teacher_legacy032/reports/stage5n_postfix_behavior_revalidation_20260506T034334Z.md
- python/week5_teacher_legacy032/reports/STAGE5N_POSTFIX_BEHAVIOR_REVALIDATION_REPORT.md

Stage5O report:
- python/week5_teacher_legacy032/reports/STAGE5O_3M_CONTINUATION_FROM_1M_REPORT.md

## 2) Exact Training Command

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/ppo_gridnet_legacy032_24x24_local_save.py `
  --exp-name legacy032_24x24_teacher_resume_3m_from_1m_postfix `
  --seed 17 `
  --cuda false `
  --prod-mode false `
  --local-save-model true `
  --local-save-dir python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix `
  --local-save-every 500000 `
  --save-full-training-state true `
  --resume-from-local-checkpoint python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/trainer_state_final.pt `
  --resume-required true `
  --strict-resume-config true `
  --resume-allow-total-timesteps-increase true `
  --resume-allow-save-dir-change true `
  --map-path maps/24x24/basesWorkers24x24.xml `
  --max-steps 6000 `
  --expected-map-size 24 `
  --verify-contract true `
  --num-bot-envs 6 `
  --num-selfplay-envs 0 `
  --num-steps 256 `
  --total-timesteps 3000000 `
  --schedule-total-timesteps 3000000 `
  --capture-video false
```

## 3) Resume Checkpoint Path

- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/trainer_state_final.pt

## 4) Output Checkpoint Paths

- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/agent_final.pt
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/model_metadata.json
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/trainer_state_final.pt
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/latest_trainer_state.json
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/training_machine_report.json

## 5) training_machine_report Summary

From:
- python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/training_machine_report.json

Required fields:
- RESUME_STATUS: RESUMED_FROM_FULL_CHECKPOINT
- CHECKPOINT_STATUS: FULL_CHECKPOINT_SAVED
- global_step_start: 999936
- global_step_end: 2999808
- target_total_timesteps: 3000000
- schedule_total_timesteps: 3000000
- optimizer_state_restored: true
- rng_state_restored: true
- strict_agent_load: true
- resumed_from_checkpoint: C:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_1m_20260504T231107Z/stage_001000000/trainer_state_final.pt
- full training checkpoint exists: true
- scratch fallback indicators: all false

Resume gate verdict:
- PASS (full checkpoint resume confirmed, no scratch fallback)

## 6) Post-Fix 3M Behavior Metrics (training_compatible)

Evaluation command used:
```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/evaluate_stage5n_postfix_behavior.py `
  --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/agent_final.pt `
  --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/model_metadata.json `
  --device cpu `
  --episodes 8 `
  --max-steps-per-episode 6000 `
  --seeds 17,123 `
  --include-deterministic `
  --include-stochastic `
  --step-mode training_compatible `
  --strict-load
```

From:
- python/week5_teacher_legacy032/reports/stage5n_postfix_behavior_revalidation_20260506T034334Z.json

Deterministic (seed 17) aggregate:
- mean_reward: 216.825
- win_rate: 1.0
- mean_obs_changed_share: 0.819202225017104
- mean_source_valid_non_noop_share: 0.26603969190917404

Stochastic (seed 17) aggregate:
- mean_reward: 211.575
- win_rate: 1.0
- mean_obs_changed_share: 0.8944376547040508
- mean_source_valid_non_noop_share: 0.5346441100976961

Stochastic (seed 123) aggregate:
- mean_reward: 202.85
- win_rate: 1.0
- mean_obs_changed_share: 0.8759030759153723
- mean_source_valid_non_noop_share: 0.5360810040484956

## 7) Compare 1M vs 3M

1M baseline (Stage5N):
- deterministic mean_reward = 99.45
- stochastic seed17 mean_reward = 209.7
- stochastic seed123 mean_reward = 208.2
- deterministic source-valid non-noop share = 0.1299
- stochastic source-valid non-noop share ~= 0.46

3M current:
- deterministic mean_reward = 216.825
- stochastic seed17 mean_reward = 211.575
- stochastic seed123 mean_reward = 202.85
- deterministic source-valid non-noop share = 0.26604
- stochastic source-valid non-noop share ~= 0.535

Delta summary:
- deterministic reward: strong improvement
- stochastic reward: near-flat overall (seed17 slightly up, seed123 slightly down)
- deterministic activity (source-valid non-noop share): strong improvement
- stochastic activity (source-valid non-noop share): improvement

## 8) 3M Improvement Statement

- deterministic reward/stability: improved materially
- stochastic reward/stability: mostly flat with mild seed variance; remains strong
- obs_changed_share: deterministic improved vs 1M baseline profile; stochastic still high
- source-valid non-noop share: improved for deterministic and stochastic
- win_rate: remains 1.0 across evaluated modes/seeds

## 9) Final Classification

- STAGE5O_3M_RESUME_TRAINING_PASS_BEHAVIOR_IMPROVED

## 10) Final Recommendation

- Use 3M checkpoint as preferred teacher candidate.
- Keep post-fix evidence policy in training_compatible mode.
- For rollout export policy selection, stochastic remains valid and strong; deterministic no longer appears weak relative to 1M.
- Do not proceed to BC decisions based on any raw-step evidence.
