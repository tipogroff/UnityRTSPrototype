# External Reference Repositories

This directory contains local clones of reference repositories used for
**control experiment reproduction only**.

These repositories are:
- **NOT** part of the main UnityRTSPrototype project
- **NOT** used by the Week5/Week6 Unity transfer pipeline
- **NOT** committed to the main repo (see `.gitignore`)

They are here solely to allow reproducing the original Gym-μRTS training recipe
as a comparison baseline against the current project-compatible pipeline.

## Contents (after setup)

| Directory | Source | Purpose |
|-----------|--------|---------|
| `gym-microrts-paper/` | https://github.com/vwxyzjn/gym-microrts-paper | Paper training scripts (ppo_gridnet_*.py, ppo_diverse_*.py) |

## Setup

Run the setup script from the repo root:

```powershell
.\python\week5_teacher_reference\scripts\create_reference_env.ps1
```

Or clone manually:

```bash
git clone https://github.com/vwxyzjn/gym-microrts-paper external/gym-microrts-paper
```

## Key paper scripts

- `ppo_gridnet_diverse_encode_decode.py` — Best Gridnet agent (encoder-decoder + diverse bots)
- `ppo_diverse_impala.py` — Best UAS agent (IMPALA-CNN + diverse bots)
- `ppo_gridnet_diverse_impala.py` — Gridnet + IMPALA-CNN + diverse bots

## Important notes

- These scripts use `gym_microrts==0.3.2` which requires **JDK >= 1.8.0** on PATH.
- The paper-scale runs use ~100M timesteps; smoke runs use 10K–50K.
- Old checkpoints from these runs are **NOT** directly transferable to Unity
  without an observation/action space adaptation layer.
- See `../README_REFERENCE_REPRODUCTION.md` for full context.
