# Teacher checkpoint evaluation summary

- generated_at_utc: 2026-04-24T12:40:02Z
- checkpoint_requested: python\week5_teacher\teacher_models\day5_teacher_hardened_serious_v2_20260420T173711Z\checkpoints\teacher_sb3_ppo_step_000080000.zip
- checkpoint_used: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher\teacher_models\day5_teacher_hardened_serious_v2_20260420T173711Z\checkpoints\teacher_sb3_ppo_step_000080000.zip
- checkpoint_sha256: 06af5b7af7650b91a00da7edbcc7a74d2eee5765f2305408532fb1ac2d638846
- episodes: 8
- opponents: coacAI,workerRushAI,lightRushAI,passiveAI
- render_probe: attempted=True success=False

## Win/Loss summary
- wins: 0
- losses: 0
- draws: 8
- win_rate: 0.000%

## Action type distribution (overall)
- NoOp: 694568 (29.848%)
- Move: 868232 (37.311%)
- Harvest: 141400 (6.076%)
- Return: 165944 (7.131%)
- Produce: 198336 (8.523%)
- Attack: 258560 (11.111%)

## Early-game action distribution (first 20 steps)
- NoOp: 27520 (29.861%)
- Move: 34400 (37.326%)
- Harvest: 5600 (6.076%)
- Return: 6560 (7.118%)
- Produce: 7840 (8.507%)
- Attack: 10240 (11.111%)

## Early-game action distribution (first 50 steps)
- NoOp: 68800 (29.861%)
- Move: 86000 (37.326%)
- Harvest: 14000 (6.076%)
- Return: 16400 (7.118%)
- Produce: 19600 (8.507%)
- Attack: 25600 (11.111%)

## Move presence diagnostics
- steps_with_any_move: 4040 / 4040 (100.000%)
- episodes_with_any_move: 8 / 8 (100.000%)

## Visual behavior note
- Render probe failed; evaluation remained non-visual.
- render_error: NameNotFound: Environment `MicrortsSelfPlayShapedReward` doesn't exist.

## Diagnostic conclusion
- Teacher is move-capable in Gym-microRTS under this checkpoint/protocol; investigation should continue on transfer/adaptation/student path.
