# Install Reference Environment

How to create and validate the isolated gym-microrts 0.3.2 reference environment.

---

## Prerequisites

### 1. Python 3.8 or 3.9

The reference recipe targets Python 3.8/3.9 (compatible with torch==1.8.0 and gym==0.17.3).

Check available versions:
```powershell
py -3.8 --version
py -3.9 --version
```

If not installed: https://www.python.org/downloads/  
Or via conda: `conda create -n microrts032 python=3.8`

### 2. JDK >= 1.8.0

gym-microrts requires Java to run the MicroRTS engine (via JPype1).

```powershell
java -version
```

Recommended: Eclipse Adoptium JDK 17 (https://adoptium.net/)  
Set `JAVA_HOME` before running any scripts:
```powershell
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot"
$env:Path      = "$env:JAVA_HOME\bin;$env:Path"
```

### 3. Git (optional)

Used to clone `gym-microrts-paper`. If not available, download the ZIP manually from:
https://github.com/vwxyzjn/gym-microrts-paper/archive/refs/heads/master.zip

---

## Setup steps

### Automated (recommended)

Run from repo root:
```powershell
.\python\week5_teacher_reference\scripts\create_reference_env.ps1
```

Force full recreation of the reference venv:
```powershell
.\python\week5_teacher_reference\scripts\create_reference_env.ps1 -ForceRecreate
```

This will:
1. Find Python 3.8 or 3.9
2. Create `.venv_microrts032_reference`
3. Select dependency set automatically:
  - Python 3.8: `reference_env/requirements_reference.txt`
  - Python 3.9: `reference_env/requirements_reference_py39_windows.txt`
4. Install dependencies in staged steps (bootstrap -> numpy -> torch -> gym -> JPype1 -> gym-microrts -> sb3 -> remaining utilities)
5. Write install log to `artifacts/reference_env_install.log`
6. Clone `gym-microrts-paper` into `external/`

The setup script also prints:
- selected Python version
- selected requirements file
- torch install mode (`exact_cpu_wheel` / `fallback_compat` / `failed`)

If torch falls back to `torch>=1.10,<1.12`, the run is marked as compatibility fallback, not exact paper lock.

### Manual (if automated setup fails)

```powershell
# Create env
py -3.8 -m venv python\week5_teacher_reference\.venv_microrts032_reference

# Activate
.\python\week5_teacher_reference\.venv_microrts032_reference\Scripts\Activate.ps1

# Upgrade pip
python -m pip install --upgrade pip setuptools wheel

# Install deps
pip install -r python\week5_teacher_reference\reference_env\requirements_reference.txt

# Clone paper scripts
git clone https://github.com/vwxyzjn/gym-microrts-paper `
    python\week5_teacher_reference\external\gym-microrts-paper
```

---

## Verify the environment

```powershell
# Activate first
.\python\week5_teacher_reference\.venv_microrts032_reference\Scripts\Activate.ps1

# Run verify script
python .\python\week5_teacher_reference\scripts\verify_reference_env.py
```

Check:
- `artifacts/reference_env_verify.json` — machine-readable report
- `artifacts/reference_env_verify.md` — human-readable report

Expected output (if healthy):
```
gym_microrts import: OK
env create: OK
observation_space: [16, 16, 27]
obs_surface_check: FULL_OBS_27_CHANNEL
Overall status: PASS
```

---

## Freeze the environment (optional)

After successful verification, save the exact package versions:
```powershell
pip freeze > python\week5_teacher_reference\reference_env\pip_freeze_reference.txt
```

---

## Known problems and fixes

### Python version not found
```
ERROR: Python 3.8 or 3.9 not found.
```
→ Install Python 3.8/3.9 and ensure the `py` launcher is on PATH.  
→ Or use conda: `conda create -n microrts032 python=3.8`

---

### Java not found / JPype1 install fails
```
JPype1 ... error: Java Development Kit not found
```
→ Install JDK and set `JAVA_HOME` **before** pip install:
```powershell
$env:JAVA_HOME = "C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot"
```

---

### torch==1.8.0 wheel not found
```
ERROR: Could not find a version that satisfies the requirement torch==1.8.0
```
→ For CPU-only, try the PyTorch wheel index:
```powershell
pip install torch==1.8.0+cpu -f https://download.pytorch.org/whl/torch_stable.html
```
→ Or relax to `torch>=1.8,<1.12` which is still compatible with gym-microrts 0.3.2.

---

### gym==0.17.3 + newer setuptools conflict
```
error in gym setup command: 'extras_require' must be a dictionary ...
```
→ Downgrade setuptools before installing gym:
```powershell
pip install "setuptools<66" "wheel<0.38"
pip install gym==0.17.3
```

---

### gym / gymnasium conflict
If `gymnasium` is also installed (e.g., from another package), it may shadow `gym`.
→ This environment should **not** have `gymnasium` installed — it uses the old `gym` API.
→ Check: `pip list | findstr gym`  
→ If `gymnasium` appears, uninstall it: `pip uninstall gymnasium`

---

### numpy / torch version conflict
torch==1.8.0 requires numpy<1.24.  
→ `numpy==1.19.2` is specified in `requirements_reference.txt`.  
→ If another package upgrades numpy, reinstall: `pip install numpy==1.19.2`

---

### Windows/Python 3.9 compatibility fallback

On Windows + Python 3.9, `numpy==1.19.2` may fail by dropping to source build and erroring during Cython metadata generation (`undeclared name not builtin: long`).

For Python 3.9 this reference branch uses compatibility pins:
- `numpy==1.21.6`
- `JPype1>=1.3,<1.5`
- py39-compatible ranges for scipy/pandas/matplotlib/Pillow/tensorboard

Torch is installed in a dedicated staged step:
1. try exact CPU wheel: `torch==1.8.0+cpu`, `torchvision==0.9.0+cpu`
2. if unavailable, fallback: `torch>=1.10,<1.12`, `torchvision>=0.11,<0.13`

This remains a reference reproduction flow, but if fallback is used it is not an exact paper lock.

---

### capture-video requires ffmpeg
```
Error: ffmpeg not found
```
→ Install ffmpeg and ensure it is on PATH:  
  Download from https://ffmpeg.org/download.html (Windows builds at https://www.gyan.dev/ffmpeg/builds/)  
→ Or disable capture-video by editing `run_reference_training_smoke.ps1`:  
  Set `$CAPTURE_VIDEO = $false`

---

## Important isolation note

This environment (`python/week5_teacher_reference/.venv_microrts032_reference/`) is
**completely separate** from the main project environment (`python/week5_teacher/.venv_day2_py39/`).

Do NOT activate both at the same time.  
Do NOT use this env for the main Week5/Week6 pipeline.
