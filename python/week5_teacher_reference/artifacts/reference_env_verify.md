# Reference Environment Verification Report

**Date**: 2026-04-27T11:33:10.552172+00:00
**Python**: 3.9.13 (tags/v3.9.13:6de2ca5, May 17 2022, 16:36:42) [MSC v.1929 64 bit (AMD64)]
**Platform**: Windows-10-10.0.26200-SP0
**VIRTUAL_ENV**: NOT_SET

## Package Versions

| Package | Version |
|---------|---------|
| gym | 0.17.3 |
| gym_microrts | 0.3.2 |
| stable_baselines3 | 1.0 |
| torch | 1.8.0+cpu |
| numpy | 1.25.2 |
| JPype1 | 1.4.1 |
| wandb | NOT_INSTALLED |

## Java

- JAVA_HOME: `C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot\`
- java version string: `openjdk version "17.0.18" 2026-01-20`

## Checks

- gym_microrts import: `OK`
- env create: `OK (env_id=MicrortsMining-v1)`
- observation_space shape: `[10, 10, 27]`
- action_space: `MultiDiscrete([100   6   4   4   4   4   7 100])`
- obs surface check: `FULL_OBS_27_CHANNEL`
- exact_reference_pins: `False`
- compatibility_fallback_used: `True`

## Notes

- Compatibility fallback detected: numpy != 1.19.2 or torch does not start with 1.8.0.

## Overall Status

**PASS**

---
_This is a reference environment check — not a Unity parity check._