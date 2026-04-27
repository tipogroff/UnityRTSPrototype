# Reference Reproduction: Gym-μRTS 0.3.2 Training Recipe

## What is this?

This directory (`python/week5_teacher_reference/`) is an **isolated control experiment**
that reproduces the original Gym-μRTS paper training recipe as closely as possible.

It is a **separate, independent** research track from the main UnityRTSPrototype
Week5/Week6 teacher-agent pipeline.

**Primary question this answers:**
> Can we reproduce a working Gym-μRTS agent (one that visibly moves and plays)
> using the original paper recipe, in isolation from the Unity transfer pipeline?

---

## Why a separate reference branch?

The main project pipeline (Week5/Week6) has been adapted for Unity compatibility:
- Project-compatible observation surface targeted at 27 channels ([24, 24, 27])
- Custom action space mapped to Unity RTS actions
- gym-microrts adapted away from the pure Gym-μRTS 0.3.2 API

Over time, the accumulated adaptations may have diverged from the original working recipe.
The reference branch lets us verify what the **original working recipe** looked like,
independent of Unity constraints.

---

## What this IS

- A **control experiment** for comparison
- A reproduction of the original `gym_microrts==0.3.2` training setup
- A way to answer: "Does the old recipe still produce a moving agent?"
- A source of ground-truth observations on:
  - Original observation surface (channels, shape)
  - Original action semantics
  - Architecture used (Gridnet / IMPALA-CNN / UAS)
  - Timesteps required for visible movement behavior

---

## What this is NOT

- NOT a Unity-compatible training run
- NOT a proof of Gym-μRTS → Unity observation/action parity
- NOT a source of checkpoints for direct BC/export to Unity
- NOT a replacement for the current Week5/Week6 pipeline
- NOT a modification of the existing teacher pipeline

---

## Why old checkpoints can't be used directly for BC/Unity

The gym-microrts 0.3.2 observation space uses a **16×16 grid × 27 channels** layout
for standard envs in common paper recipes. The current project-compatible pipeline
also targets a **27-channel** observation surface, but with different grid/configuration
and runtime semantics. Key differences include:
- Grid dimensions (depends on Unity map)
- Environment IDs and wrappers
- Action encoding (Unity action branches differ from gym-microrts flat action space)
- Training architecture/runtime assumptions
- Export and adapter requirements for BC/Unity pipeline

Direct transfer requires an adaptation layer. The current `teacher_adapter` in the
main pipeline handles this, but it was calibrated for the project-compatible recipe,
not the paper recipe checkpoint format.

---

## Comparison checklist

After running the reference setup, compare these dimensions:

| Dimension | Reference (gym-microrts 0.3.2) | Project (Unity pipeline) |
|-----------|-------------------------------|--------------------------|
| Observation shape | Verified by `verify_reference_env.py`; expected full-observation 27 channels, often 16x16x27 depending on env | 24x24x27 |
| Action space | Gym-μRTS env action space (varies by env id/wrappers) | Unity action branches and project-specific semantics |
| Architecture | Gridnet / IMPALA-CNN | Project-adapted |
| Timesteps to movement | ? | ~20K–50K (warmup) |
| Main mismatch source | Grid/env/wrappers/action/export semantics (not primarily channel count) | Grid/env/wrappers/action/export semantics |

This comparison is a control study only and does **not** claim Gym->Unity parity.

---

## Directory structure

```
week5_teacher_reference/
  README_REFERENCE_REPRODUCTION.md     ← this file
  INSTALL_REFERENCE_ENV.md             ← env setup guide
  RUN_REFERENCE_TRAINING.md            ← training guide
  reference_env/
    requirements_reference.txt         ← pinned deps (paper recipe)
    pip_freeze_reference.txt           ← populated after env creation
  scripts/
    create_reference_env.ps1           ← creates .venv_microrts032_reference
    verify_reference_env.py            ← validates env, saves JSON/MD report
    run_reference_training_smoke.ps1   ← short smoke run (10K steps)
    run_reference_training_long.ps1    ← staged long run (1M steps default)
    collect_reference_artifacts.py     ← aggregates run artifacts
  external/
    README.md                          ← git-ignored clones go here
    gym-microrts-paper/                ← (git-ignored) cloned paper repo
  artifacts/
    reference_env_verify.json/md       ← env check results
    smoke_runs/<timestamp>/            ← smoke run outputs
    long_runs/<timestamp>/             ← long run outputs
    REFERENCE_REPRODUCTION_SUMMARY.md  ← aggregated summary
```

---

## Related repositories

| Repo | Purpose |
|------|---------|
| https://github.com/Farama-Foundation/MicroRTS-Py | Active fork of gym-microrts (v0.4+) |
| https://github.com/vwxyzjn/gym-microrts-paper | Paper training scripts (v0.3.2 target) |
| https://github.com/cpuheater/gym-microrts | Earlier community fork |
| https://github.com/Farama-Foundation/MicroRTS | Java MicroRTS engine |

---

## Quick start

```powershell
# From repo root
.\python\week5_teacher_reference\scripts\create_reference_env.ps1

# Activate env
.\python\week5_teacher_reference\.venv_microrts032_reference\Scripts\Activate.ps1

# Verify
python .\python\week5_teacher_reference\scripts\verify_reference_env.py

# Smoke run
.\python\week5_teacher_reference\scripts\run_reference_training_smoke.ps1
```

See `INSTALL_REFERENCE_ENV.md` and `RUN_REFERENCE_TRAINING.md` for details.
