# scripts/ — Planned Entrypoints for Legacy032 Teacher Pipeline
This directory contains scripts for the `gym_microrts==0.3.2` legacy teacher pipeline.

**Stage 1 status**: `legacy032_env_probe.py` created and verified — `PASS_WITH_WARNINGS`.

---

## Scripts

| Script | Stage | Status | Purpose |
|--------|-------|--------|---------|
| `legacy032_env_probe.py` | Stage 1 | ✅ DONE | Probe env contracts, smoke episode, JSON+MD report |
| `train_teacher_legacy032.py` | Stage 2 | ✅ DONE (smoke) | Stage 2 smoke wrapper around reference training script; saves isolated legacy032 artifacts and summary reports |
| `evaluate_teacher_legacy032.py` | Stage 3-4R | ✅ UPDATED | Evaluate checkpoint, run behavior gate, includes corrected `target_24x24_gridmode` compatibility (`[...,49]`) |
| `evaluate_teacher_large_map_diagnostics.py` | Stage 5C diagnostics | ✅ NEW | Extended large-map diagnostics for 24x24 GridMode; reports all-cell vs source-cell limits, economy/production/combat proxies, and explicit limitations |
| `run_staged_teacher_training_legacy032.py` | Stage 3 (historical line) | ✅ DONE | Run staged main training and evaluate after checkpoints |
| `run_24x24_staged_teacher_training_legacy032.py` | Stage 5 | ✅ NEW | Corrected 24x24 staged orchestrator (preflight -> train -> gate) under legacy032-only artifact roots |
| `ppo_gridnet_legacy032_24x24_local_save.py` | Stage 4R | ✅ UPDATED | Patched trainer with corrected GridMode contract (`[...,49]`) and resolution-aware actor head |
| `verify_legacy032_24x24_training_contract.py` | Stage 4R | ✅ UPDATED | Contract+architecture probe for 24x24 GridMode with explicit mode separation (global-single vs gridmode) |
| `train_teacher_legacy032_24x24.py` | Stage 4R | ✅ UPDATED | Thin 24x24 smoke wrapper: runs Stage 4R probe first, then training only on PASS |
| `export_teacher_rollout_legacy032.py` | Stage 6 | planned | Export raw episode trajectories from corrected 24x24 GridMode path |
| `adapt_legacy032_to_unity_v2.py` | Stage 7 | planned | Adapt rollout to Unity v2 `[6,4,4,4,4,7,49]` |

---

## `train_teacher_legacy032.py` — Stage 2 smoke wrapper

### Purpose

Runs short legacy032 smoke training using the reference patched paper script, but writes
all outputs only into `python/week5_teacher_legacy032/`.

### Example command

```powershell
$env:JAVA_HOME = 'C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path = "$env:JAVA_HOME\bin;$env:Path"
.\python\week5_teacher_reference\.venv_microrts032_reference\Scripts\python.exe `
		python/week5_teacher_legacy032/scripts/train_teacher_legacy032.py `
		--run-label legacy032_smoke `
		--env-id MicrortsRandomEnemyShapedReward1-v1 `
		--map-path maps/24x24/basesWorkers24x24.xml `
		--seed 17 `
		--total-timesteps 10000 `
		--device cpu `
		--no-wandb `
		--allow-unmasked-smoke
```

### Outputs

- `python/week5_teacher_legacy032/teacher_models/<run_id>/`
	- `agent_final.pt`
	- `model_metadata.json`
- `python/week5_teacher_legacy032/teacher_logs/<run_id>/`
	- `training_stdout.log`
	- `training_stderr.log`
	- `training_metrics.jsonl`
- `python/week5_teacher_legacy032/reports/`
	- `stage2_smoke_training_<timestamp>.json`
	- `stage2_smoke_training_<timestamp>.md`

### Stage 2 warning

The Stage 2 checkpoint is a smoke-validation artifact only and must not be treated
as a final teacher checkpoint.

---

## `evaluate_teacher_legacy032.py` — Stage 3 behavior gate

### Purpose

- loads `agent_final.pt` or `agent_step_*.pt`
- reconstructs policy architecture from `model_metadata.json`
- evaluates checkpoint with behavior-first metrics
- writes gate decision and compatibility diagnostics

### Example command (Stage 2 smoke checkpoint)

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
	python/week5_teacher_legacy032/scripts/evaluate_teacher_legacy032.py `
	--checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_smoke_20260429T113844Z/agent_final.pt `
	--model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_smoke_20260429T113844Z/model_metadata.json `
	--run-label stage3_smoke_checkpoint_behavior_gate `
	--episodes 8 --seed 101 --device cpu `
	--output-dir python/week5_teacher_legacy032/reports `
	--eval-mode both --env-mode auto --require-mask true
```

### Core flags

- `--checkpoint-path`
- `--model-metadata-path`
- `--run-label`
- `--episodes` (default `8`)
- `--seed` (default `101`)
- `--device` (default `cpu`)
- `--output-dir` (default `python/week5_teacher_legacy032/reports`)
- `--eval-mode deterministic|stochastic|both` (default `both`)
- `--env-mode reference_internal|preflight_24x24|target_24x24_gridmode|auto` (default `auto`)
- `--require-mask true|false` (default `true`)
- `--max-steps-per-episode` (default `2000`)
- `--env-max-steps` (default: mirrors `--max-steps-per-episode`; controls internal `MicroRTSGridModeVecEnv(max_steps=...)` cap)
- `--write-action-trace`
- `--dry-run`

Horizon semantics:

- `--max-steps-per-episode` controls the outer evaluation loop limit.
- `--env-max-steps` controls the internal environment episode cap.
- For Stage 5C large-map gate, pass both as `6000` to avoid hidden truncation at `T=2000`.
- If visualizer reaches `T=2000` then immediately restarts episode, internal env cap is still `2000`.

### Outputs

- `python/week5_teacher_legacy032/reports/stage3_smoke_checkpoint_behavior_gate_<timestamp>.json`
- `python/week5_teacher_legacy032/reports/stage3_smoke_checkpoint_behavior_gate_<timestamp>.md`
- `python/week5_teacher_legacy032/reports/stage3_gate_<stage>_<timestamp>.json`
- `python/week5_teacher_legacy032/reports/stage3_gate_<stage>_<timestamp>.md`

---

## `evaluate_teacher_large_map_diagnostics.py` — Stage 5C extended diagnostics

### Purpose

- evaluates Stage 5C checkpoint on target 24x24 GridMode with long horizon (`max_steps_per_episode=6000`)
- records all-cell action metrics and explicit source-cell limitations when mask semantics are ambiguous
- records economy/production/combat proxy metrics and writes machine + markdown diagnostic reports

### Example command (Stage 5C 1M checkpoint)

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
	python/week5_teacher_legacy032/scripts/evaluate_teacher_large_map_diagnostics.py `
	--checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260429T195603Z/stage_001000000/agent_final.pt `
	--model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_main_20260429T195603Z/stage_001000000/model_metadata.json `
	--run-label stage5c_large_map_diagnostics_001000000 `
	--episodes 8 `
	--seed 17 `
	--device cpu `
	--output-dir python/week5_teacher_legacy032/reports `
	--env-mode target_24x24_gridmode `
	--require-mask true `
	--max-steps-per-episode 6000 `
	--eval-mode both `
	--write-action-trace `
	--sample-frame-interval 25
```

### Why this exists

- On large 24x24 GridMode maps, all-cell `noop_share` can be misleading because most cells are empty while meaningful actions may still happen on controllable unit cells.
- Stage 5C diagnostic therefore fixes horizon to `max_steps_per_episode=6000` and reports explicit limitations whenever source-cell mask semantics cannot be validated safely.

### Outputs

- `python/week5_teacher_legacy032/reports/stage5c_large_map_diagnostics_<timestamp>.json`
- `python/week5_teacher_legacy032/reports/stage5c_large_map_diagnostics_<timestamp>.md`
- optional: `python/week5_teacher_legacy032/reports/stage5c_large_map_action_trace_<timestamp>.jsonl`
- `python/week5_teacher_legacy032/reports/STAGE5C_LARGE_MAP_DIAGNOSTICS_REPORT.md`

---

## `run_staged_teacher_training_legacy032.py` — Stage 3 staged main training

### Purpose

- runs staged teacher training checkpoints
- stores outputs under legacy032-only paths
- optionally runs behavior gates after each stage
- writes consolidated stage training report

### Example command (Stage 3A 100k sanity)

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
	python/week5_teacher_legacy032/scripts/run_staged_teacher_training_legacy032.py `
	--run-label legacy032_teacher_main `
	--stages 100000 `
	--seed 17 --device cpu `
	--episodes-per-gate 8 `
	--evaluate-after-each --no-wandb
```

### Core flags

- `--run-label`
- `--stages` (default `100000,500000,1000000,3000000,5000000`)
- `--seed`
- `--device`
- `--output-root`
- `--reference-script-path`
- `--evaluate-after-each`
- `--episodes-per-gate`
- `--dry-run`
- `--no-wandb`
- `--continue-on-gate-warning`
- `--stop-on-gate-fail`

### Outputs

- `python/week5_teacher_legacy032/teacher_models/<run_id>/stage_000100000/...`
- `python/week5_teacher_legacy032/teacher_logs/<run_id>/stage_000100000/...`
- `python/week5_teacher_legacy032/reports/stage3_training_<timestamp>.json`
- `python/week5_teacher_legacy032/reports/stage3_training_<timestamp>.md`

Important note:

- `run_staged_teacher_training_legacy032.py` is historical/reference-internal (Stage 3 lineage).
- Do not use it for Stage 5 24x24 transfer-readiness decisions.

---

## `run_24x24_staged_teacher_training_legacy032.py` — Stage 5 corrected path

### Purpose

- runs mandatory 24x24 contract preflight (`stage5a_24x24_contract_probe.json`)
- runs corrected 24x24 GridMode trainer `ppo_gridnet_legacy032_24x24_local_save.py`
- stores per-stage outputs under `python/week5_teacher_legacy032/teacher_models` and `python/week5_teacher_legacy032/teacher_logs`
- runs post-stage gate in `target_24x24_gridmode`
- writes machine + markdown reports (`stage5_24x24_training_<timestamp>.json/.md`)

### Example command (Stage 5A 100k)

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
	python/week5_teacher_legacy032/scripts/run_24x24_staged_teacher_training_legacy032.py `
	--run-label legacy032_24x24_teacher_main `
	--stages 100000 `
	--seed 17 `
	--device cpu `
	--map-path maps/24x24/basesWorkers24x24.xml `
	--episodes-per-gate 8 `
	--evaluate-after-each `
	--no-wandb `
	--require-contract-check true
```

### Example command (Stage 5B 500k)

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
	python/week5_teacher_legacy032/scripts/run_24x24_staged_teacher_training_legacy032.py `
	--run-label legacy032_24x24_teacher_main `
	--stages 500000 `
	--seed 17 `
	--device cpu `
	--map-path maps/24x24/basesWorkers24x24.xml `
	--episodes-per-gate 8 `
	--evaluate-after-each `
	--no-wandb `
	--require-contract-check true
```

### Example command (Stage 5C 1M with extended gate horizon)

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
	python/week5_teacher_legacy032/scripts/run_24x24_staged_teacher_training_legacy032.py `
	--run-label legacy032_24x24_teacher_main `
	--stages 1000000 `
	--seed 17 `
	--device cpu `
	--map-path maps/24x24/basesWorkers24x24.xml `
	--training-max-steps 6000 `
	--episodes-per-gate 8 `
	--max-steps-per-gate 6000 `
	--evaluate-after-each `
	--no-wandb `
	--require-contract-check true
```

Why `6000` for Stage 5C gate on 24x24:

- On large 24x24 maps, development often progresses through longer pre-contact phases (economy, barracks, production).
- A short gate horizon can terminate episodes before meaningful combat contact and underreport behavior quality.
- Stage 5C therefore uses extended gate horizon (`max_steps_per_episode=6000`) to capture late-phase interactions.

Training vs gate horizon semantics:

- `--training-max-steps` controls internal episode cap in training env creation (`MicroRTSGridModeVecEnv(max_steps=...)`).
- `--max-steps-per-gate` controls evaluator outer loop and evaluator env cap (`--max-steps-per-episode` and `--env-max-steps`).
- For Stage 5C large-map experiments, set both to `6000`.
- If visualizer resets at `T=2000` during training, training env is still using `max_steps=2000`.

Stage 5B comparison rule:

- Stage 5B (500k) must be compared against Stage 5A 100k baseline gate report:
	`python/week5_teacher_legacy032/reports/stage5_gate_000100000_20260429T164521Z.json`.
- If resume is not explicitly implemented/validated, treat 500k as from-scratch with larger `--total-timesteps`, not as resumed continuation from 100k.
- Use corrected 24x24 GridMode path only for transfer-readiness decisions.

Stage 5C final decision flow:

- Use all three together before deciding on 3M readiness:
	- standard gate report: `python/week5_teacher_legacy032/reports/stage5_gate_001000000_20260429T232455Z.json`
	- large-map diagnostics report: `python/week5_teacher_legacy032/reports/stage5c_large_map_diagnostics_20260430T123128Z.json`
	- cross-checkpoint comparison: `python/week5_teacher_legacy032/reports/STAGE5_100K_500K_1M_COMPARISON.md`
- Do not use naive raw count comparisons across 5A/5B vs 5C without horizon caveat (`2000` vs `6000`).
- Treat orchestrator `decision` labels as generic pipeline labels only.
- For Stage 5C closure, the final human-reviewed class is `READY_FOR_3M_WITH_WARNINGS`.

### Core flags

- `--run-label`
- `--stages` (default `100000,500000,1000000,3000000,5000000`)
- `--seed`
- `--device`
- `--map-path`
- `--output-root`
- `--evaluate-after-each`
- `--training-max-steps` (default `6000`; passed to trainer as `--max-steps`)
- `--episodes-per-gate`
- `--max-steps-per-gate` (default `6000`; passed to evaluator as both `--max-steps-per-episode` and `--env-max-steps`)
- `--no-wandb`
- `--dry-run`
- `--continue-on-gate-warning`
- `--stop-on-gate-fail`
- `--require-contract-check`

Evaluation-horizon comparability warning:

- Stage 5A/5B gates were executed with the old horizon (`max_steps_per_episode=2000`).
- Stage 5C gates use `6000` by design on 24x24 large-map settings.
- When comparing Stage 5C 1M gate metrics against Stage 5A/5B, explicitly account for the horizon difference.

### Outputs

- `python/week5_teacher_legacy032/teacher_models/<run_id>/stage_000100000/agent_final.pt`
- `python/week5_teacher_legacy032/teacher_models/<run_id>/stage_000100000/model_metadata.json`
- `python/week5_teacher_legacy032/teacher_logs/<run_id>/stage_000100000/training_stdout.log`
- `python/week5_teacher_legacy032/teacher_logs/<run_id>/stage_000100000/training_stderr.log`
- `python/week5_teacher_legacy032/teacher_logs/<run_id>/stage_000100000/training_metrics.jsonl`
- `python/week5_teacher_legacy032/teacher_logs/<run_id>/stage_000100000/evaluation_stdout.log`
- `python/week5_teacher_legacy032/teacher_logs/<run_id>/stage_000100000/evaluation_stderr.log`
- `python/week5_teacher_legacy032/reports/stage5a_24x24_contract_probe.json`
- `python/week5_teacher_legacy032/reports/stage5_24x24_training_<timestamp>.json`
- `python/week5_teacher_legacy032/reports/stage5_24x24_training_<timestamp>.md`
- `python/week5_teacher_legacy032/reports/stage5_gate_000100000_<timestamp>.json`
- `python/week5_teacher_legacy032/reports/stage5_gate_000100000_<timestamp>.md`
- `python/week5_teacher_legacy032/reports/STAGE5A_100K_TRAINING_REPORT.md`
- `python/week5_teacher_legacy032/reports/STAGE5A_COMPLETION_REPORT.md`

### Stage 5D GPU prep (before 3M)

Use this check before attempting any Stage 5D 3M GPU run.

CUDA availability check in the active legacy032 venv:

```powershell
$PY="c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe"
& $PY -c "import torch; print('torch_version=', torch.__version__); print('cuda_available=', torch.cuda.is_available()); print('torch_cuda=', torch.version.cuda); print('device_count=', torch.cuda.device_count()); print('device_name=', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO CUDA')"
```

Important notes:

- CUDA must be available inside `.venv_microrts032_reference`.
- `--device cuda` in orchestrator is translated to trainer `--cuda true`; `--device cpu` maps to trainer `--cuda false`.
- Trainer metadata (`model_metadata.json`) now records requested/effective device and torch CUDA diagnostics.
- GPU may not materially accelerate MicroRTS training when Java/env stepping is the bottleneck.

Example Stage 5D GPU command (reference only, do not run blindly):

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
	python/week5_teacher_legacy032/scripts/run_24x24_staged_teacher_training_legacy032.py `
	--run-label legacy032_24x24_teacher_main_gpu `
	--stages 3000000 `
	--seed 17 `
	--device cuda `
	--map-path maps/24x24/basesWorkers24x24.xml `
	--training-max-steps 6000 `
	--episodes-per-gate 8 `
	--max-steps-per-gate 6000 `
	--evaluate-after-each `
	--no-wandb `
	--require-contract-check true
```

---

## Critical warning: internal 16x16 vs preflight 24x24

- Preflight probe confirmed target env/action space for legacy 24x24.
- Reference training script currently trains/evaluates on internal 16x16 grid-mode config.
- Stage 3 gate reports therefore include compatibility warning when checkpoint is only evaluable on internal reference action space.
- Do not claim direct 24x24 target compatibility from these checkpoints without explicit pipeline changes.

Stage 4 rule:

- Do not continue 500k/1M/3M/5M on the legacy 16x16 reference path for Unity-transfer decisions.
- Continue long training only after Stage 4 alignment is resolved for 24x24 target contract.
- For Stage 5 transfer-readiness decisions, use corrected 24x24 GridMode path only.

Stage 4R correction note:

- Stage 4 original `BLOCKED_CONTRACT_MISMATCH` classification was superseded.
- For `MicroRTSGridModeVecEnv` on 24x24, expected nvec is `[576,6,4,4,4,4,7,49]`.
- Attack branch `49` is correct for GridMode (local 7x7 target).
- Remaining blocker in Stage 4 was architecture shape mismatch, now fixed via resolution-aware actor head.

Post-Stage-4R sequence:

- Stage 5: 24x24 staged teacher training (corrected GridMode path)
- Stage 6: raw rollout export
- Stage 7: adapter to Unity v2
- Stage 8: v2 validation and BC-ready packaging

---

## Stage 4 scripts

### `verify_legacy032_24x24_training_contract.py`

Purpose:

- Creates `MicroRTSGridModeVecEnv` on requested map.
- Verifies observation/action contract, mask availability through `env.vec_client.getMasks(0)`, policy forward and masked sampling.
- Separates contracts explicitly:
	- global single-action reference: `[576,6,4,4,4,4,7,576]`
	- gridmode expected: `[576,6,4,4,4,4,7,49]`
- Writes JSON report with PASS/BLOCKED decision.

Example command:

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
	python/week5_teacher_legacy032/scripts/verify_legacy032_24x24_training_contract.py `
	--map-path maps/24x24/basesWorkers24x24.xml `
	--num-bot-envs 6 --num-selfplay-envs 0 --seed 17 `
	--output-json python/week5_teacher_legacy032/reports/stage4r_24x24_contract_probe.json
```

### `train_teacher_legacy032_24x24.py`

Purpose:

- Thin wrapper around `ppo_gridnet_legacy032_24x24_local_save.py`.
- Writes outputs only under `python/week5_teacher_legacy032`.
- Supports `--require-contract-check true` so training is skipped when probe fails.
- This wrapper targets corrected 24x24 GridMode contract (`[...,49]`) only.

Example command:

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
	python/week5_teacher_legacy032/scripts/train_teacher_legacy032_24x24.py `
	--run-label legacy032_24x24_smoke `
	--map-path maps/24x24/basesWorkers24x24.xml `
	--seed 17 --total-timesteps 10000 --device cpu --no-wandb `
	--require-contract-check true
```

### `ppo_gridnet_legacy032_24x24_local_save.py`

Purpose:

- Stage 4R patched legacy032 training script derived from reference source.
- Adds configurable `--map-path`, `--max-steps`, `--expected-map-size`, `--verify-contract`.
- Uses corrected GridMode expectation (`[...,49]` for attack branch).
- Uses `legacy032_resolution_aware_gridnet_v1` actor head to force actor logits spatial size == env HxW.
- Emits contract/architecture failure report and exits when mismatch is detected.
- This is the active Stage 4R trainer for Stage 5 24x24 staged training.

### `evaluate_teacher_legacy032.py` in `target_24x24_gridmode`

`--env-mode target_24x24_gridmode` validates target 24x24 GridMode behavior and mask usage.
It does not evaluate gym.make/global single-action contract mode.

---

## `legacy032_env_probe.py` — Stage 1

### Purpose

Instantiates a `gym_microrts==0.3.2` env on the 24×24 training map, probes obs shape,
action space nvec, mask availability, attack target semantics, and runs a 128-step
smoke episode.  Writes JSON + Markdown reports to `reports/`.

### Example command

```powershell
$env:JAVA_HOME = 'C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path = "$env:JAVA_HOME\bin;$env:Path"
.\python\week5_teacher_reference\.venv_microrts032_reference\Scripts\python.exe `
	python/week5_teacher_legacy032/scripts/legacy032_env_probe.py `
	--env-id MicrortsRandomEnemyShapedReward1-v1 `
	--map-path maps/24x24/basesWorkers24x24.xml `
	--steps 128 --seed 17 `
	--output-json python/week5_teacher_legacy032/reports/legacy032_env_probe.json `
	--write-markdown-report
```

### Expected outputs

| File | Description |
|------|-------------|
| `reports/legacy032_env_probe.json` | Machine-readable probe artifact |
| `reports/legacy032_env_probe.md` | Auto-generated markdown companion |

**Expected status**: `PASS_WITH_WARNINGS` (two known non-blocking warnings).

### Key confirmed results

- **Action representation**: `GYM_MICRORTS_032_GLOBAL_SINGLE_ACTION` — 8-element nvec,
  one action per step: `[src_cell=576, action_type=6, move=4, harvest=4, return=4,
  produce_dir=4, produce_unit=7, attack_global=576]`
- **Observation shape**: `(24, 24, 27)` — H × W × C
- **Attack target**: global flat 576 (NOT local 7×7 49) for gym.make/global-single mode only
- Corrected Stage 4R GridMode training path already uses local 7×7 attack target 49

### Troubleshooting

**`AttributeError: ... 'GlobalAgentCombinedRewardSelfPlayEnv'`**  
→ `MicrortsSelfPlayShapedReward-v1` is broken in this 0.3.2 build.  
→ Fix: use `--env-id MicrortsRandomEnemyShapedReward1-v1`.

**JVM errors**  
→ Set `$env:JAVA_HOME = 'C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'`.

**Wrong Python**  
→ Use `.\python\week5_teacher_reference\.venv_microrts032_reference\Scripts\python.exe`.  
→ Do NOT use `python/week5_teacher/.venv_day2_py39/`.

---

## Note

Do **not** call scripts from `python/week5_teacher/` without review — those assume
v0.6.1 runtime or have hardcoded v1 contract `[6,4,4,4,4,4,9]`.
See `../LEGACY032_STAGE0_AUDIT.md` for migration items.
