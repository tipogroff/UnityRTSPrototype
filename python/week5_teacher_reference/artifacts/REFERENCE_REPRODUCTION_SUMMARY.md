# Reference Reproduction Summary

**Generated**: 2026-04-27T12:07:28.657119+00:00

## Environment Verification

- Status: **PASS**
- gym_microrts import: `OK`
- env create: `OK (env_id=MicrortsMining-v1)`
- observation_space: `[10, 10, 27]`
- obs surface check: `FULL_OBS_27_CHANNEL`

## Training Runs

Total runs: 4 (smoke: 3, long: 1)

| Type | Timestamp | Timesteps | Seed | Logs | Video | Checkpoint | Exit |
|------|-----------|-----------|------|------|-------|------------|------|
| smoke | 20260427T184129Z | 10000 | 1 | Y | N | N | 1 |
| smoke | 20260427T184202Z | 10000 | 1 | Y | N | N | 1 |
| smoke | 20260427T184310Z | 10000 | 1 | Y | N | N | 0 |
| long | 20260427T185325Z | 100000 | 1 | Y | N | N | 0 |

## Success Criteria

| Criterion | Status |
|-----------|--------|
| env starts up | OK (env_id=MicrortsMining-v1) |
| observation space | [10, 10, 27] |
| obs surface | FULL_OBS_27_CHANNEL |
| training runs without crash | YES |
| video/replay created | NOT YET |
| checkpoint saved | NOT YET |

---
_This is a reference reproduction summary — not a Unity parity report._
_Old Gym-μRTS checkpoints are NOT directly compatible with the Unity transfer pipeline._