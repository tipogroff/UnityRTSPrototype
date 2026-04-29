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
| `run_staged_teacher_training_legacy032.py` | Stage 3 (historical line) | ✅ DONE | Run staged main training and evaluate after checkpoints |
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
- `--write-action-trace`
- `--dry-run`

### Outputs

- `python/week5_teacher_legacy032/reports/stage3_smoke_checkpoint_behavior_gate_<timestamp>.json`
- `python/week5_teacher_legacy032/reports/stage3_smoke_checkpoint_behavior_gate_<timestamp>.md`
- `python/week5_teacher_legacy032/reports/stage3_gate_<stage>_<timestamp>.json`
- `python/week5_teacher_legacy032/reports/stage3_gate_<stage>_<timestamp>.md`

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
