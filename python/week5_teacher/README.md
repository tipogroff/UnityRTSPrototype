# Week 5 Day 2 Teacher Rollout

This folder implements only the Day 2 teacher runtime smoke path.

Canonical Day 2 target is fixed:

- `MicroRTS-Py v0.6.1`-compatible stack;
- observation surface expected as 27 channels (no extra terrain/walls channel);
- shape-level runtime validation only (not semantic parity validation).

Day 2 is intentionally narrow and does not include exporter/adapter/BC layers.

## Validated environment

Validated command was executed successfully in this workspace with:

- Python `3.9.13` (separate Day 2 venv)
- Java `Temurin 17`
- `gym-microrts` from git tag `v0.6.1` (editable install)
- `gym==0.23.1`, `gymnasium==0.29.1`
- `stable-baselines3==2.3.2`, `torch==2.8.0`, `numpy==1.26.4`

See `ENVIRONMENT_DAY2.md` for exact bootstrap/build steps and notes.

## Validated command

```powershell
$env:JAVA_HOME='C:/Program Files/Eclipse Adoptium/jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME/bin;$env:Path"

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/.venv_day2_py39/Scripts/python.exe \
  c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher/run_teacher_rollout.py \
  --episodes 1 \
  --env-id MicrortsSelfPlayShapedReward-v1 \
  --map-path maps/24x24/basesWorkers24x24.xml \
  --seed 17 \
  --allow-random-policy-smoke-fallback \
  --rollout-step-limit 64
```

Validation status:

- runtime reached terminal: yes (`terminated` at step 64);
- observed shape: `[1, 24, 24, 27]`;
- observation surface verification: `27-channel compatible`;
- compatibility scope: `shape-only`;
- semantic parity verified: `false`.

## What `run_teacher_rollout.py` does

- logs runtime versions, seeds, env/action/observation summaries;
- checks shape compatibility for SB3 checkpoint path (`observation_space` + `action_space`);
- runs rollout until terminal or step-limit fail;
- writes `.log` and `.summary.json` to `teacher_logs/`.

## Day 2 scope boundaries

- SB3-only checkpoint loader on Day 2 (`ppo`, `a2c`, `dqn`);
- strict scalar reward assumption (`coerce_scalar_reward`);
- scenario note is approximation-only (no full Unity parity claim);
- `teacher_rollouts/` remains reserved and empty from Day 2 script logic.

Not included in Day 2:

- raw rollout dataset writer;
- Gym->Unity action/observation adapter;
- generalized multi-backend teacher loader;
- semantic parity validator.

## Scenario approximation note (Day 2)

Default map (`maps/24x24/basesWorkers24x24.xml`) is treated only as nearest approximation to Unity `MVP_24x24_Symmetric`.

- `scenario_match_scope`: approximation-only
- `known_matches`: 24x24 size, bases/workers family, symmetric intent
- `known_unknowns`: exact starting resources, exact unit subset, reward shaping behavior, action semantics, step timing
- `parity_claim`: false

## CLI arguments

- `--policy-path`: teacher checkpoint path (SB3 only on Day 2).
- `--policy-algorithm`: one of `ppo`, `a2c`, `dqn`.
- `--checkpoint-env-version`: required with `--policy-path`.
- `--episodes`: number of episodes.
- `--env-id`: requested gym/gymnasium env id.
- `--map-path`: map path (kept explicit to prevent scenario drift).
- `--seed`: base seed.
- `--env-seed`: optional env seed (`seed + 1` by default).
- `--rollout-seed`: optional rollout seed (`seed + 2` by default).
- `--device`: torch/SB3 device.
- `--allow-random-policy-smoke-fallback`: explicit non-canonical fallback mode.
- `--output-dir`: output root (defaults to `python/week5_teacher`).
- `--rollout-step-limit`: hard per-episode safety cap.

## Output artifacts

Per run in `teacher_logs/`:

- `teacher_rollout_<timestamp>.log`
- `teacher_rollout_<timestamp>.summary.json`

Day 2 summary is a runtime + shape smoke artifact only.