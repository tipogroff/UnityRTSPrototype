# Running Reference Training

How to run the Gym-μRTS 0.3.2 reference training experiments.

---

## Prerequisites

1. Reference env created and verified (see `INSTALL_REFERENCE_ENV.md`)
2. `gym-microrts-paper` cloned into `external/gym-microrts-paper/`
3. JAVA_HOME set to JDK >= 1.8.0
4. ffmpeg on PATH (for capture-video; optional)

---

## Step 1: Smoke run

The smoke run is a **very short** training run (10K steps by default).  
Its only purpose is to confirm that dependencies work and training starts.

```powershell
# From repo root (venv does NOT need to be activated — script uses venv directly)
.\python\week5_teacher_reference\scripts\run_reference_training_smoke.ps1
```

**What to expect:**
- Takes ~1–5 minutes
- Creates a timestamped folder in `artifacts/smoke_runs/<timestamp>/`
- Files created:
  - `smoke_command.txt` — exact command used
  - `smoke_train.log` — full stdout/stderr output
  - `smoke_summary.json` — run metadata
  - `videos/` — episode recordings (if capture-video worked)

**Success criteria for smoke run:**
- Script runs without Python exception
- Log shows training loop iterating (e.g. `global_step=`)
- No `JVMNotFoundException`, `ImportError`, or `gym.error`
- Exit code 0

---

## Step 2: Verify smoke results

```powershell
# Activate env
.\python\week5_teacher_reference\.venv_microrts032_reference\Scripts\Activate.ps1

# Run artifact collector
python .\python\week5_teacher_reference\scripts\collect_reference_artifacts.py
```

Check `artifacts/REFERENCE_REPRODUCTION_SUMMARY.md` for a table of all runs.

---

## Step 3: Staged long run

After the smoke run passes, run a longer staged reference run (1M steps by default).

```powershell
.\python\week5_teacher_reference\scripts\run_reference_training_long.ps1
```

**Configuration** (edit the top of `run_reference_training_long.ps1`):
```powershell
$TOTAL_TIMESTEPS = 1000000   # default: 1M
$SEED            = 1
$CAPTURE_VIDEO   = $true
$SCRIPT_TO_RUN   = "ppo_gridnet_diverse_encode_decode.py"
```

**Paper-scale context:**
> The paper uses ~100M timesteps for final published results.  
> 1M is sufficient to see early movement behavior in most envs.  
> 10M is a reasonable intermediate sanity point.  
> **Do NOT set 100M without planning for multi-day compute.**

---

## Where to find artifacts

```
artifacts/
  reference_env_verify.json           ← env verification report
  reference_env_verify.md
  smoke_runs/
    <timestamp>/
      smoke_command.txt               ← exact command
      smoke_train.log                 ← training stdout/stderr
      smoke_summary.json              ← run metadata
      videos/                         ← episode recordings
  long_runs/
    <timestamp>/
      long_run_command.txt
      long_train.log
      long_run_summary.json
      videos/
  REFERENCE_REPRODUCTION_SUMMARY.md  ← aggregated summary table
  reference_reproduction_summary.json
```

---

## Success criteria

| Criterion | How to verify |
|-----------|---------------|
| env starts up | `env_create: OK` in verify JSON |
| observation space correct | `obs_surface_check: FULL_OBS_27_CHANNEL` |
| training runs without crash | exit_code = 0 in smoke summary |
| training loop progresses | `global_step=` lines visible in smoke_train.log |
| video/replay shows movement | videos/ dir is non-empty, review .mp4 files |
| checkpoint saved | `checkpoints_found: True` in summary (long run) |

---

## Which paper script to use?

| Script | Description | Recommendation |
|--------|-------------|----------------|
| `ppo_gridnet_diverse_encode_decode.py` | Best Gridnet agent (encoder-decoder + diverse bots) | **Start here** |
| `ppo_diverse_impala.py` | Best UAS agent (IMPALA-CNN + diverse bots) | Good alternative |
| `ppo_gridnet_diverse_impala.py` | Gridnet + IMPALA-CNN + diverse bots | Good alternative |
| `ppo_gridnet_coacai.py` | Simple Gridnet + masking (no diverse bots) | Fast smoke test |

---

## Common issues during training

### JVM not starting
```
jpype._jvmfinder.JVMNotFoundException: No JVM shared library file (jvm.dll) found.
```
→ Set JAVA_HOME before running:
```powershell
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot"
$env:Path      = "$env:JAVA_HOME\bin;$env:Path"
```

### ffmpeg not found (capture-video)
→ Install ffmpeg or set `$CAPTURE_VIDEO = $false` in the script.

### Out of memory with multiple envs
→ Reduce `$NUM_BOT_ENVS` in `run_reference_training_long.ps1`.

---

## Important notes

- Reference runs produce **Gym-μRTS checkpoints** — these are NOT directly usable
  for BC/Unity export without the observation/action adaptation layer.
- Do NOT copy reference checkpoints into the Week5/Week6 pipeline without explicit adaptation.
- Reference runs run in the `external/gym-microrts-paper/` directory (the paper scripts
  use relative paths for video output).
