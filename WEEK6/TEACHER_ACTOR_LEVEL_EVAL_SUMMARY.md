# Teacher Actor-Level Evaluation Summary

Generated at (UTC): 2026-04-24T15:04:20Z

## 1) Checkpoint
- Path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher\teacher_models\day5_teacher_hardened_serious_v2_20260420T173711Z\checkpoints\teacher_sb3_ppo_step_000080000.zip
- Loader: sb3_contrib.MaskablePPO

## 2) Environment and Opponent Protocol
- Episodes: 3
- Max steps per episode: 800
- Map: maps/24x24/basesWorkers24x24.xml
- Opponent pool: workerRushAI
- Opponent sampling requested: static
- Opponent sampling effective: static
- Effective opponent for all episodes: workerRushAI
- Note: Legacy gym_microrts backend runs under a single JVM per process. To avoid JVM restart failures, this evaluator reuses one env/opponent for all episodes.

## 3) Full-Tensor Action Distribution (Teacher Output Tensor)
- NoOp: count=260463 share=29.85%
- Move: count=325587 share=37.31%
- Harvest: count=53025 share=6.08%
- Return: count=62229 share=7.13%
- Produce: count=74376 share=8.52%
- Attack: count=96960 share=11.11%

## 4) Actor-Level Teacher Action Distribution (Ready Own Actors)
- NoOp: count=1440 share=94.86%
- Move: count=0 share=0.00%
- Harvest: count=78 share=5.14%
- Return: count=0 share=0.00%
- Produce: count=0 share=0.00%
- Attack: count=0 share=0.00%

## 5) Early-Game Actor-Level Distribution
- First 20 steps:
  - NoOp: count=60 share=95.24%
  - Move: count=0 share=0.00%
  - Harvest: count=3 share=4.76%
  - Return: count=0 share=0.00%
  - Produce: count=0 share=0.00%
  - Attack: count=0 share=0.00%
- First 50 steps:
  - NoOp: count=150 share=94.34%
  - Move: count=0 share=0.00%
  - Harvest: count=9 share=5.66%
  - Return: count=0 share=0.00%
  - Produce: count=0 share=0.00%
  - Attack: count=0 share=0.00%

## 6) Teacher Actor-Level Move Presence
- Steps with any teacher actor selecting Move: 0 / 1515 (0.00%)
- Episodes with any teacher actor selecting Move: 0 / 3 (0.00%)

## 7) Ready-Actor Summary
- Avg ready own actors per ready step: 1.050
- Steps with movable-ready actors but no Move selected: 78 / 78 (100.00%)

## 8) Full-Tensor vs Actor-Level Move Share
- Full-tensor Move share: 37.31%
- Actor-level Move share: 0.00%
- Delta (actor - full): -37.31%

## 9) Diagnostic Conclusion
- move signal mostly lives in raw tensor and is weak on actor level
- Executed/effective action facts are not claimed where env API does not expose them directly.
