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
- shaping_event_counts
- movement_warmup_notes

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
