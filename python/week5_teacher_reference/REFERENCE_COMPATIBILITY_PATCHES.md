# Reference Environment Compatibility Patches

**Scope**: `python/week5_teacher_reference/` only.  
**Isolation**: None of these patches touch `python/week5_teacher`, Unity, or any BC pipeline.  
**Purpose**: Document every compatibility fix needed to run gym-microrts 0.3.2 paper recipe
on Python 3.9 / numpy 1.25 / Windows, vs. the original paper environment (Python 3.8 / numpy 1.19.2 / Linux).

---

## 1. numpy `np.int` Removal (numpy >= 1.24)

### Symptom
```
AttributeError: module 'numpy' has no attribute 'int'.
`np.int` was a deprecated alias for the builtin `int`.
```
Raised at: `gym_microrts/envs/vec_env.py`, line in `_encode_obs`.

### Root cause
`np.int` (and `np.float`, `np.bool`, etc.) were deprecated in numpy 1.20 and
**removed in numpy 1.24**. The reference env installs numpy 1.25.2 (compatibility
pin; original paper used 1.19.2 which pre-dates the deprecation).

### Files patched (inside .venv_microrts032_reference only)

| File | Change |
|------|--------|
| `gym_microrts/envs/vec_env.py` | `dtype=np.int` → `dtype=np.int32` |
| `gym_microrts/envs/global_agent_env.py` | `dtype=np.int` → `dtype=np.int32` |
| `gym_microrts/envs/local_agent_env.py` | `dtype=np.int` → `dtype=np.int32` |

### Why `np.int32`?
The original code produced a plain-int array of one-hot observation planes.
`np.int32` matches the original semantics and is safe for downstream torch conversion.

### Reproduction command
```powershell
# Verify patch is applied
Select-String -Path 'python\week5_teacher_reference\.venv_microrts032_reference\lib\site-packages\gym_microrts\envs\*.py' -Pattern 'np\.int[^0-9e]'
# Should return no matches.
```

---

## 2. PowerShell Script Fixes

### 2a. `$Args` Automatic Variable Collision

#### Symptom
PowerShell silently uses its built-in `$Args` automatic variable (holds unbound
positional parameters) instead of the script's local `$Args = @(...)` array.
This caused the wrong arguments to be passed to the Python process.

#### Fix
Renamed all local parameter arrays from `$Args` to `$TrainArgs` in:
- `scripts/run_reference_training_smoke.ps1`
- `scripts/run_reference_training_long.ps1`

#### Rule
Never name a PowerShell local variable `$Args`, `$PSBoundParameters`, `$MyInvocation`,
or any other [automatic variable](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_automatic_variables).

### 2b. Em-dash / Unicode in String Literals

#### Symptom
```
В строке отсутствует завершающий символ: "
Отсутствует закрывающий знак "}" в блоке операторов
```
PowerShell 5.1 on Windows-1252 locale misinterprets UTF-8 em-dash (`—`, U+2014)
inside a double-quoted string as a Windows-1252 right quote (`\x94`), breaking
the string terminator detection.

#### Fix
Replaced em-dashes inside string literals with ASCII `--` in smoke and long scripts.
Em-dashes in `<# ... #>` comment blocks and `# ...` line comments are safe and unchanged.

---

## 3. `--num-bot-envs` Minimum Value

### Symptom
```
AssertionError: for each environment, a microrts ai should be provided
```

### Root cause
`ppo_gridnet_diverse_encode_decode.py` builds `ai2s` list with this formula:

```python
ai2s = [coacAI      for _ in range(num_bot_envs - 6)]   # 0 when num_bot_envs < 6
     + [randomBiasedAI for _ in range(min(num_bot_envs, 2))]
     + [lightRushAI    for _ in range(min(num_bot_envs, 2))]
     + [workerRushAI   for _ in range(min(num_bot_envs, 2))]
```

When `num_bot_envs < 6`: `len(ai2s) = 0+2+2+2 = 6`, but `num_envs = num_bot_envs`
→ assert fails.  
When `num_bot_envs == 6`: `len(ai2s) = 0+2+2+2 = 6 = num_envs` → OK.

### Fix
Set `--num-bot-envs 6` as the minimum in both smoke and long scripts.  
The smoke script was originally set to 1 (failed), then corrected to 6.

### Valid `num_bot_envs` values
- `6`: minimum (0 coacAI + 2 random + 2 lightRush + 2 workerRush)
- `8`: 2 coacAI + 2 random + 2 lightRush + 2 workerRush
- `24`: original paper default

---

## 4. `WANDB_MODE=disabled`

### Symptom
If wandb is not installed or not logged-in, paper script crashes when `--prod-mode`
is accidentally passed.

### Fix
All scripts explicitly set `$env:WANDB_MODE = "disabled"` before invoking the
paper script. This ensures the `if args.prod_mode: import wandb` branch is never
taken during reference runs.

---

## 5. Checkpoint Saving Without `--prod-mode`

### Observation
The paper script saves `agent.pt` **only** inside a `if args.prod_mode:` block
(which requires wandb). Without `--prod-mode`, only TensorBoard `runs/` data is
written to disk.

### Workaround in long run script
`run_reference_training_long.ps1` runs a post-training Python one-liner that:
1. Searches `external/gym-microrts-paper/models/<experiment_name>/` for `agent.pt`
   (written if the run used prod-mode previously).
2. Searches `external/gym-microrts-paper/runs/<experiment_name>/` for TensorBoard
   event files (written unconditionally).
3. Records all discovered paths in `long_run_summary.json` under `artifact_paths`.

The `collect_reference_artifacts.py` collector reads these paths and includes them
in the master summary.

---

## 6. `collect_reference_artifacts.py`: UTF-8 BOM

### Symptom
PowerShell's `ConvertTo-Json | Out-File -Encoding utf8` writes a UTF-8 BOM
(`\xEF\xBB\xBF`). Python's `open(f, encoding="utf-8")` does not strip the BOM,
causing `json.load` to raise a decode error (caught silently by `except Exception: pass`),
leaving all summary fields as `None`.

### Fix
Changed `encoding="utf-8"` to `encoding="utf-8-sig"` in `collect_reference_artifacts.py`.
`utf-8-sig` automatically strips the BOM on read.

---

## Summary Table

| # | Issue | Affected file(s) | Fix |
|---|-------|-----------------|-----|
| 1 | `np.int` removed in numpy 1.24 | `gym_microrts/envs/*.py` in venv | `dtype=np.int` → `dtype=np.int32` |
| 2a | `$Args` PS variable collision | smoke + long PS scripts | renamed to `$TrainArgs` |
| 2b | Em-dash in string literal | smoke + long PS scripts | `--` (ASCII) |
| 3 | `num_bot_envs < 6` breaks ai2s | smoke + long PS scripts | default `--num-bot-envs 6` |
| 4 | wandb not configured | smoke + long PS scripts | `WANDB_MODE=disabled` |
| 5 | No checkpoint without prod-mode | long PS script | post-run artifact search |
| 6 | UTF-8 BOM in PS-generated JSON | `collect_reference_artifacts.py` | `encoding="utf-8-sig"` |
