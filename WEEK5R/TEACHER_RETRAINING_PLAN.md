# Teacher Behavior-First Retraining Plan

## Goal

Obtain a teacher checkpoint that passes actor-level behavior gate checks before any rollout/export usage.

Primary acceptance target:
- checkpoint has non-collapsed actor behavior (not only reward/full-tensor artifacts)
- checkpoint passes `teacher_behavior_gate.py`
- replay artifacts are available for fast human sanity confirmation

## Why Not Train 100k/200k Immediately

Long runs without intermediate behavior audits can hide collapsed behavior for many hours.

Known failure pattern already observed:
- full-tensor Move looked non-trivial
- actor-level Move was zero
- effective position deltas were zero

Therefore, intermediate gated checkpoints are mandatory to prevent wasting compute on behaviorally collapsed policies.

## Checkpoint Schedule

Mandatory schedule:
- 5k
- 10k
- 20k
- 50k
- 100k (optional)

After each checkpoint:
1. Run `teacher_behavior_gate.py`
2. Enable replay (`--make-replay`)
3. Update comparison (`compare_teacher_behavior_gates.py`)

## Mandatory Post-Checkpoint Gate Workflow

For each checkpoint `CKPT.zip`:
1. `teacher_behavior_gate.py --checkpoint CKPT.zip --make-replay ...`
2. collect gate JSON/MD + replay artifacts in gate run directory
3. include gate JSON in comparison table with `compare_teacher_behavior_gates.py`

Gate and comparison artifacts are stored under:
- `WEEK5R/gate_runs/<run_id>/`

Training artifacts are stored under:
- `WEEK5R/retraining_runs/<run_id>/`

## Abort Criteria

Abort run early if any of these conditions are met:
- `FAIL_COLLAPSED_NOOP` at both 5k and 10k checkpoints
- `actor_level_move_share == 0` while `ready_movable_actor_choice_count > 0`
- `effective_position_delta_count == 0`
- `no_effect_action_share > 0.80`

## Continue Criteria

Continue to next checkpoint if all hold:
- no FAIL status
- `actor_level_move_share > 0`
- `effective_position_delta_count > 0`

## Candidate Criteria

Checkpoint is candidate for downstream usage only if all hold:
- gate status is `PASS`
- `actor_level_move_share >= 0.05`
- `actor_noop_share < 0.75`
- replay verdict is not passive standing (`visually_passive`)

## Methodology Constraints

- reward and full-tensor action histogram are not sufficient
- only actor-level gate is authoritative for checkpoint viability
- visual replay is human-readable sanity layer, not gate replacement
- no Gym->Unity semantic parity claims
- do not modify Unity adapter or `Assets/`

## First Minimal Experiment (Behavior-First)

Recommended first run:
- total timesteps: 20k
- checkpoint steps: 5k,10k,20k
- gate episodes: 4
- gate max steps: 256
- effective steps: 100
- replay steps: 150
- device: cpu (or cuda only if current runtime is stable)

Expected outcome:
- either early abort with explicit reasons
- or first checkpoint with both:
  - `actor_level_move_share > 0`
  - `effective_position_delta_count > 0`

## Example Command

```powershell
python python/week5_teacher/train_teacher_behavior_first.py \
  --total-timesteps 20000 \
  --checkpoint-steps 5000,10000,20000 \
  --episodes-gate 4 \
  --max-steps-gate 256 \
  --effective-steps-gate 100 \
  --replay-steps 150 \
  --seed 170 \
  --device cpu \
  --make-replay \
  --output-dir WEEK5R/retraining_runs \
  --gate-output-dir WEEK5R/gate_runs
```
