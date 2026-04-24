# Teacher Effective Behavior Audit

Generated at (UTC): 2026-04-24T17:21:35Z

## 1) Checkpoint
- Path: `C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher\teacher_models\day5_teacher_hardened_serious_v2_20260420T173711Z\checkpoints\teacher_sb3_ppo_step_000080000.zip`
- Loader: `sb3_contrib.MaskablePPO`
- Step tag: 80000

## 2) Protocol
- Map: `maps/24x24/basesWorkers24x24.xml`
- Opponent: `workerRushAI`
- Requested steps: 50
- Executed steps: 50
- Deterministic: True

## 3) Teacher-Controlled Side Confirmation
- Method: Cross-reference source_unit_mask (mask column 0) with obs owner channels. Actual layout: ch10=neutral, ch11=player0(teacher), ch12=player1(opponent). Player 0 = RL agent (MicroRTSGridModeVecEnv, num_bot_envs=1, ai2s=[opponent]).
- Total source_unit_mask ready cells (step 0): 2
- With teacher owner channel (ch2 > 0.5): 2
- With opponent owner channel (ch3 > 0.5): 0
- With neutral owner channel: 0
- Teacher units on map at start: 2 (Worker, Base)
- Opponent units on map at start: 2
- **Verdict: CONFIRMED: source_unit_mask aligns with teacher owner channel (ch11=player0).**

## 4) Full-Tensor Action Distribution (all cells)
  - NoOp: 8600 (29.86%)
  - Move: 10750 (37.33%)
  - Harvest: 1750 (6.08%)
  - Return: 2050 (7.12%)
  - Produce: 2450 (8.51%)
  - Attack: 3200 (11.11%)
  - Total cell-choices: 28800

## 5) Ready-Actor Chosen Action Distribution (teacher own ready actors only)
  - NoOp: 50 (94.34%)
  - Harvest: 3 (5.66%)
  - Total actor-choices: 53

## 6) Effective Outcome Distribution (state-diff audit)
  - `blocked_or_no_effect`: 3 (5.7%)
  - `no_position_change`: 50 (94.3%)

## 7) Move Effects Summary
- Direct move effects (Move chosen → position changed): 0
- Implicit move via Harvest: 0
- Implicit move via Return: 0
- Implicit move via Attack: 0
- Any movement effect total: 0 (0.0% of ready-actor choices)

## 8) Implicit Movement Hypothesis
- Harvest causes implicit movement: **False**
- Return causes implicit movement: **False**
- Attack causes implicit movement: **False**
- Implicit moves total: 0
- Evidence basis: state-diff: unit not found at original position after step, found at adjacent cell

## 9) Per-Step Trace (Compact)

| step | ready | full_Move | actor_NoOp | actor_Move | actor_Harvest | actor_Return | actor_Produce | actor_Attack | move_effects |
|------|-------|-----------|------------|------------|---------------|--------------|---------------|--------------|--------------|
| 0 | 2 | 215 | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| 1 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 2 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 3 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 4 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 5 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 6 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 7 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 8 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 9 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 10 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 11 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 12 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 13 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 14 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 15 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 16 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 17 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 18 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 19 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 20 | 2 | 215 | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| 21 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 22 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 23 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 24 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 25 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 26 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 27 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 28 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 29 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 30 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 31 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 32 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 33 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 34 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 35 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 36 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 37 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 38 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 39 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 40 | 2 | 215 | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| 41 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 42 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 43 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 44 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 45 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 46 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 47 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 48 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| 49 | 1 | 215 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |

## 10) Method Limits
- **full_tensor**: action_type distribution over ALL spatial cells per step
- **ready_actor_chosen**: action_type distribution over source_unit_mask==1 cells only
- **effective_state_diff**: obs_before vs obs_after per ready actor; position+HP+resource changes
- **execution_claim**: NOT claimed. State-diff audit is an observation proxy, not a confirmed execution stream. Implicit movement is inferred from position change correlation with chosen action type.

## 11) Verdict
> No Move chosen and no position changes on ready actors. Teacher appears passive on these cells.

## 12) Opponent Side Note
> Opponent-side actions are not tracked in this script. All actor-level analysis strictly covers teacher-owned (player 0) ready units only.
