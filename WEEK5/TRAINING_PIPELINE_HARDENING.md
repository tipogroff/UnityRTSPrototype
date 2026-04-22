# TRAINING_PIPELINE_HARDENING.md

Date: 2026-04-21
Scope: Week 5 teacher-side pipeline hardening after baseline/smoke implementation.

## Why this change

The baseline path was operational, but several parts were still smoke-grade:
- backend fallback behavior was not explicitly controlled as primary vs emergency;
- action mask calls existed in hot path without guaranteed mask-aware PPO usage;
- opponent regime was effectively single-opponent in legacy fallback path;
- architecture default remained MLP-only in practice;
- no throughput-oriented run profile;
- no phase-level timing summary for env/model bottleneck diagnosis.

This hardening pass keeps the working pipeline intact while making routing, modes, and diagnostics explicit.

## What changed

## 1) Backend cleanup: preferred vs fallback

Implemented explicit backend routing controls in training path:
- preferred backend: gym.make
- emergency fallback backend: gym_microrts.envs.vec_env.MicroRTSGridModeVecEnv

New controls:
- --backend-mode allow_fallback|preferred_only
- --force-legacy-backend

Behavior:
- preferred backend is attempted first by default;
- fallback is used only if preferred fails and backend_mode=allow_fallback;
- forced fallback is explicit and marked as diagnostic/emergency route.

Metadata/logging now records:
- actual backend used;
- backend role (preferred / emergency_fallback_auto / emergency_fallback_forced);
- fallback trigger reason.

## 2) Mask regime split: mask-aware vs non-mask-aware

Implemented explicit mask mode selection:
- --action-mask-mode auto|mask_aware|non_mask_aware

Behavior:
- mask_aware uses sb3_contrib.MaskablePPO (strict requirement for sb3_contrib);
- non_mask_aware uses stable_baselines3.PPO;
- auto prefers mask-aware and falls back to non-mask-aware only with explicit metadata reason.

Hot-path cleanup:
- removed unconditional mask call from legacy adapter step_async;
- mask is now queried only when actually needed by mask-aware algorithm.

Metadata records requested/effective mode and fallback reason (if any).

## 3) Opponent pool and sampling

Added explicit opponent pool support for legacy fallback backend:
- --opponent-pool "coacAI,workerRushAI,lightRushAI,passiveAI"
- --opponent-sampling static|per_reset|per_episode
- --opponent-seed

Implemented:
- pool resolution against gym_microrts.microrts_ai;
- sampling on reset and episode completion (legacy vector adapter);
- runtime tracking of current opponent slots and opponent switch counts.

Metadata/logging include configured pool, runtime regime, and switch diagnostics.

Important honesty:
- this is paper-like opponent diversification direction, not full paper regime reproduction.

## 4) Policy architecture upgrade

Added explicit architecture regime:
- --policy-architecture cnn_preferred|mlp_fallback
- legacy override still possible via --policy MlpPolicy|CnnPolicy for compatibility.

Implemented CNN-capable preferred path:
- CnnPolicy with custom MicroRTSApproxImpalaExtractor.

Important honesty:
- extractor is IMPALA-like approximation, not a paper-identical IMPALA-CNN implementation.
- MLP remains available as fallback/smoke path.

Metadata records requested/effective architecture and notes.

## 5) Throughput-aware profile

Run profiles now include:
- smoke
- throughput_tuned
- overnight (kept as compatible alias with throughput-oriented values)

Profile system now sets effective values for:
- total_timesteps
- num_bot_envs
- n_steps
- batch_size
- n_epochs

This gives a practical next profile without claiming full sweep/benchmark.

## 6) Phase-level profiling instrumentation

Added lightweight timing instrumentation:
- env step time
- mask capture time
- rollout phase time
- update/backward phase time
- estimated policy forward time

Computed summary includes shares:
- env_time_share
- mask_overhead_share
- policy_forward_estimated_share
- update_backward_share

Diagnostic label:
- env-bound / mixed / model-bound

Important honesty:
- this is lightweight phase timing, not full low-level profiler tracing.

## Training modes after hardening

Preferred route for hardened training:
- preferred backend first (gym.make)
- mask-aware PPO when available
- cnn_preferred architecture
- throughput_tuned profile

Fallback/emergency route:
- legacy backend (forced or controlled failover)
- mlp_fallback architecture
- non_mask_aware mode when mask-aware deps are unavailable

## Explicit limitations still present

Not completed in this hardening pass:
- no claim of exact paper IMPALA-CNN parity;
- no claim of full paper opponent curriculum/reproduction;
- opponent pool controls are explicit for legacy fallback backend, while preferred backend may remain backend-managed;
- no BC training, no Unity import path integration, no full benchmark campaign, no large hyperparameter sweep.

## Files changed in this hardening pass

Code:
- python/week5_teacher/train_teacher_smoke.py
- python/week5_teacher/run_teacher_rollout.py

Docs:
- WEEK5/TRAINING_PIPELINE_HARDENING.md

## Suggested hardened command examples

Throughput-oriented run (preferred intent):

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/train_teacher_smoke.py \
  --run-profile throughput_tuned \
  --policy-architecture cnn_preferred \
  --action-mask-mode auto \
  --backend-mode allow_fallback \
  --opponent-pool coacAI,workerRushAI,lightRushAI,passiveAI \
  --opponent-sampling per_episode \
  --device cuda
```

Diagnostic fallback run (explicit emergency):

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/train_teacher_smoke.py \
  --run-profile smoke \
  --backend-mode preferred_only \
  --force-legacy-backend \
  --policy-architecture mlp_fallback \
  --action-mask-mode non_mask_aware \
  --device cpu
```
