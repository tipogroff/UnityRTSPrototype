# STAGE5D GPU Prep Report

## Summary

- CUDA available: false
- torch version: 1.8.0+cpu
- torch CUDA version: None
- GPU device name: NO CUDA
- final recommendation: BLOCKED_GPU_UNAVAILABLE

## CUDA check

Command:

```powershell
$PY="c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe"
& $PY -c "import torch; print('torch_version=', torch.__version__); print('cuda_available=', torch.cuda.is_available()); print('torch_cuda=', torch.version.cuda); print('device_count=', torch.cuda.device_count()); print('device_name=', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'NO CUDA')"
```

Output:

- torch_version= 1.8.0+cpu
- cuda_available= False
- torch_cuda= None
- device_count= 0
- device_name= NO CUDA

Decision from CUDA check:

- BLOCKED_GPU_UNAVAILABLE
- GPU smoke was not executed because CUDA is unavailable in the active legacy032 venv.

## Device plumbing audit

Files audited:

- python/week5_teacher_legacy032/scripts/run_24x24_staged_teacher_training_legacy032.py
- python/week5_teacher_legacy032/scripts/ppo_gridnet_legacy032_24x24_local_save.py
- python/week5_teacher_legacy032/scripts/train_teacher_legacy032_24x24.py

What --device and --cuda do:

- Orchestrator accepts `--device cpu|cuda`.
- Orchestrator maps `--device` to trainer `--cuda`:
  - `--device cpu` -> `--cuda false`
  - `--device cuda` -> `--cuda true`
- Trainer computes runtime device as:
  - `torch.device('cuda' if torch.cuda.is_available() and args.cuda else 'cpu')`

GPU plumbing status:

- model/tensors are moved with `.to(device)` in trainer.
- No hardcoded CPU-only model/tensor path was found for the core training flow.
- If `--device cuda` is requested but CUDA is unavailable, effective runtime remains CPU by design.

Fixes applied in legacy032 scripts:

- Added device diagnostics to trainer metadata (`model_metadata.json`):
  - requested_device
  - effective_device
  - torch_version
  - torch_cuda_version
  - cuda_available
  - cuda_device_name
  - cuda_device_count
- Added orchestrator extraction of those diagnostics into per-stage report data (`device_diagnostics`).
- Added orchestrator warning when requested device is CUDA but effective device is not CUDA.

## GPU smoke result

- Not executed.
- Reason: BLOCKED_GPU_UNAVAILABLE (torch is CPU-only in active venv).

## CPU smoke result (comparison baseline)

Run id:

- stage5d_cpu_smoke_compare_20260430T125352Z

Command:

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/run_24x24_staged_teacher_training_legacy032.py `
  --run-label stage5d_cpu_smoke_compare `
  --stages 10000 `
  --seed 17 `
  --device cpu `
  --map-path maps/24x24/basesWorkers24x24.xml `
  --training-max-steps 6000 `
  --episodes-per-gate 2 `
  --max-steps-per-gate 6000 `
  --evaluate-after-each `
  --no-wandb `
  --require-contract-check true
```

Artifacts:

- stage report json: python/week5_teacher_legacy032/reports/stage5_24x24_training_20260430T125352Z.json
- checkpoint path: python/week5_teacher_legacy032/teacher_models/stage5d_cpu_smoke_compare_20260430T125352Z/stage_000010000/agent_final.pt
- metadata path: python/week5_teacher_legacy032/teacher_models/stage5d_cpu_smoke_compare_20260430T125352Z/stage_000010000/model_metadata.json
- gate json report: python/week5_teacher_legacy032/reports/stage5_gate_000010000_20260430T125555Z.json

CPU smoke metrics:

- training_duration_seconds: 121.20327138900757
- last_global_step: 9150
- derived_steps_per_second: 75.49301182335786
- crash: no (training_exit_code=0)
- effective_device: cpu
- gate_result: PASS

## CPU vs GPU comparison

GPU smoke was not run because CUDA is unavailable.

| metric | CPU smoke | GPU smoke | interpretation |
|---|---:|---:|---|
| total_timesteps | 10000 | N/A | GPU blocked |
| training_duration_seconds | 121.20327138900757 | N/A | lower is better |
| steps_per_second | 75.49301182335786 | N/A | higher is better |
| effective_device | cpu | N/A | GPU blocked |
| gate_decision | PASS | N/A | GPU blocked |
| crash/no crash | no crash | N/A | GPU blocked |

## Recommendation for Stage 5D

- BLOCKED_GPU_UNAVAILABLE

Rationale:

- Current active legacy032 venv has CPU-only torch (`1.8.0+cpu`) with `cuda_available=False`.
- Running Stage 5D 3M with `--device cuda` now would not provide real GPU acceleration and is unsafe to assume.

Next safe step (separate approval required):

- Create/validate a CUDA-compatible legacy032 venv first, then run a short Stage 5D GPU smoke (10k-20k) and compare against the CPU baseline above before any 3M run.
