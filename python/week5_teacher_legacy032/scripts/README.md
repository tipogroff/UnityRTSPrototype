# scripts/ — Planned Entrypoints for Legacy032 Teacher Pipeline
This directory contains scripts for the `gym_microrts==0.3.2` legacy teacher pipeline.

**Stage 1 status**: `legacy032_env_probe.py` created and verified — `PASS_WITH_WARNINGS`.

---

## Scripts

| Script | Stage | Status | Purpose |
|--------|-------|--------|---------|
| `legacy032_env_probe.py` | Stage 1 | ✅ DONE | Probe env contracts, smoke episode, JSON+MD report |
| `train_teacher_legacy032.py` | Stage 2 | ✅ DONE (smoke) | Stage 2 smoke wrapper around reference training script; saves isolated legacy032 artifacts and summary reports |
| `evaluate_teacher_legacy032.py` | Stage 3 | ✅ DONE | Evaluate checkpoint, run behavior gate, write JSON+MD reports |
| `run_staged_teacher_training_legacy032.py` | Stage 3 | ✅ DONE | Run staged main training and evaluate after checkpoints |
| `export_teacher_rollout_legacy032.py` | Stage 4 | planned | Export raw episode trajectories |
| `adapt_legacy032_to_unity_v2.py` | Stage 5–6 | planned | Adapt rollout to Unity v2 `[6,4,4,4,4,7,49]` |

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
- `--env-mode reference_internal|preflight_24x24|auto` (default `auto`)
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
- **Attack target**: global flat 576 (NOT local 7×7 49) — Stage 6 adapter required

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
