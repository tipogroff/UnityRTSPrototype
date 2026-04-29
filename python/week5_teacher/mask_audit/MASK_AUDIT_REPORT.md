# MASK_AUDIT_REPORT

## Decision

PASS_MASK_BUT_POLICY_COLLAPSE

## Environment

- gym version: 0.29.1
- gym api: gymnasium
- gym_microrts / MicroRTS-Py version: 0.0.0 (gym_microrts)
- env id: MicrortsSelfPlayShapedReward-v1
- map path: maps/24x24/basesWorkers24x24.xml
- backend route: gym_microrts.envs.vec_env.MicroRTSGridModeVecEnv
- opponent pool: passiveAI
- python executable: None
- torch version: 2.8.0+cu128
- sb3/sb3-contrib version: 2.7.1

## Expected contract

- branch layout: [6,4,4,4,4,7,49]
- expected mask shape: [N,H,W,79]

## Findings

1. surface: pass
2. semantics: pass
3. sampling: pass
4. logprob: pass
5. argmax: pass
6. coverage: pass
7. comparison: inconclusive

## Fixes applied

- none

## Next decision

- proceed to scripted BC
- fix PPO mask integration
- fix env wrapper
- compare with legacy pipeline

## Notes

- This report does not claim Unity readiness, BC readiness, or student retraining status.
- If any section is missing or skipped, decision may be INCONCLUSIVE_NEEDS_MANUAL_CHECK.
