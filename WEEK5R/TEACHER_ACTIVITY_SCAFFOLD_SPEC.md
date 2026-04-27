# Teacher Activity Scaffold Spec

## Purpose

Teacher-side behavior-first training currently shows weak or absent actor-level movement at early and mid checkpoints. This scaffold introduces minimal activity-focused shaping to improve optimization dynamics without changing Unity-side systems, adapter semantics, BC pipeline, or gate thresholds.

## Why Scaffold Was Needed

Observed behavior in behavior_first training showed policy passivity/collapse patterns despite valid action masks:

- actor-level movement near zero at key checkpoints
- effective_position_delta_count often zero
- no_effect_action_share often near 1.0
- actions biased toward non-movement behavior with low effective state change

This indicates a learning dynamics problem (objective shaping / curriculum), not a mask transport failure.

## Diagnostics That Excluded Mask/Env Root Cause

The following diagnostics were used before introducing scaffold:

- diagnose_training_mask_semantics.py verdict: MASK_OK
- masked random actor baseline verdict: BASELINE_CAN_MOVE
- fixed teacher_behavior_gate recheck at 10k: FAIL_COLLAPSED_NOOP (artifact-corrected)
- fixed gate runs confirmed low actor-level movement and high no-effect rates under current recipe

Conclusion: movement is physically reachable and mask semantics are present; optimization recipe needed targeted warmup.

## New Curriculum Controls

Added CLI option in behavior-first training:

- --curriculum-mode none|movement_warmup|economy_warmup|mixed
- default: none

movement_warmup defaults (applied only if user did not explicitly provide the specific flag):

- opponent_pool = passiveAI
- opponent_sampling = static
- checkpoint_steps = 2000,5000,10000,20000
- total_timesteps = 20000

## Activity Shaping (Teacher-Side)

Shaping is explicit opt-in:

- --activity-shaping
- default: False

Shaping coefficients:

- --shape-move-reward (default 0.01)
- --shape-noop-penalty (default 0.001)
- --shape-no-effect-penalty (default 0.002)

Minimal shaping signals:

- positive reward for effective teacher position delta
- penalty for repeated NoOp when a ready movable teacher actor exists
- penalty for no-effect action on a ready actor

The shaping wrapper is applied on the teacher-side training VecEnv only.

### Shaping Alignment Modes

To align shaping diagnostics with gate semantics, behavior-first training now supports:

- --shape-reward-only-move-action / --no-shape-reward-only-move-action (default: true)
- --shape-no-effect-ready-action-only / --no-shape-no-effect-ready-action-only (default: true)

When reward-only-move-action is true, move reward is granted only if both are true:

- ready movable actor selected Move (action_type branch index 0 equals Move=1)
- teacher position delta occurred

When disabled, legacy reward behavior is used (any teacher position delta can receive shaping reward).

When no-effect-ready-action-only is true, no-effect penalty is granted only if both are true:

- ready actor selected non-NoOp
- no teacher position delta occurred

This makes no-effect penalty scope explicit and auditable in manifests.

### Detailed Alignment Counters

shaping_event_counts now records detailed diagnostics:

- position_delta_steps_total
- move_reward_events_total
- move_action_on_ready_actor_events
- move_action_position_delta_events
- nonmove_position_delta_events
- noop_with_ready_movable_events
- repeated_noop_penalty_events
- ready_actor_nonnoop_steps
- no_effect_ready_action_events
- no_effect_penalty_events
- action_decode_skipped_steps

Why this was added:

- Separate any position delta from Move-caused position delta.
- Detect when reward credit was granted for non-Move dynamics.
- Verify whether activity shaping promotes actor-level useful movement that gate metrics track.

## Why This Is Not Final Reward Function

This scaffold is an optimization aid intended to bootstrap activity and break inert local minima. It is not intended as the final task reward definition and does not replace downstream policy quality criteria.

## Why This Does Not Prove Gym -> Unity Parity

Scaffolded improvements in Gym-microRTS training signal do not imply semantic parity with Unity execution. Gym-side actor activity and state deltas remain proxy metrics for training dynamics, not engine-equivalence proof.

## Replay Workflow Note

Checkpoint workflow remains:

- teacher_behavior_gate.py after each checkpoint
- compare_teacher_behavior_gates.py after checkpoint set

Replay generation is run as a separate subprocess (not inside gate) to reduce JVM restart conflicts such as "JVM cannot be restarted".

## Manifest Additions

Behavior-first manifest now includes:

- curriculum_mode
- activity_shaping_enabled
- shaping_config
- shaping_alignment_mode
- shaping_event_counts
- movement_warmup_notes

shaping_alignment_mode fields:

- reward_only_move_action: true/false
- no_effect_ready_action_only: true/false

## movement_warmup Success Criteria

movement_warmup is considered to show activity if checkpoint signals satisfy:

- actor_level_move_share > 0
- effective_position_delta_count > 0
- no_effect_action_share < 1.0

These criteria are activity-focused and do not alone certify final policy quality.

## Disable Scaffold

To disable scaffold behavior completely:

- use --curriculum-mode none
- do not pass --activity-shaping

This keeps training on baseline behavior-first settings (unless other CLI overrides are applied).

## movement_warmup Coefficient Sweep

For short warmup comparison (10k), use:

- python/week5_teacher/run_movement_warmup_sweep.py

Default sweep configs:

- baseline_mild: move=0.01 noop=0.001 no_effect=0.002
- stronger_balanced: move=0.05 noop=0.005 no_effect=0.01
- stronger_noeffect: move=0.03 noop=0.003 no_effect=0.02
- move_heavy: move=0.10 noop=0.002 no_effect=0.005

Run characteristics:

- curriculum-mode movement_warmup
- activity-shaping enabled
- total-timesteps 10000
- checkpoint-steps 2000,5000,10000
- collect-all-checkpoints
- replay optional (default off)

Sweep artifacts:

- WEEK5R/movement_warmup_sweeps/<sweep_id>/SWEEP_RESULTS.md
- WEEK5R/movement_warmup_sweeps/<sweep_id>/sweep_results.json

Ranking preference:

1. pos_delta > 0 at 10k
2. lower no_effect at 10k
3. actor_move > 0.05 at 10k
4. lower actor_noop without no-effect collapse
5. move_action_position_delta_events > 0

Expected next experiment:

- Run sweep to 10k, choose best config by ranking, then rerun full 20k movement_warmup with selected coefficients.
