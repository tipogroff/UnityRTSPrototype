# PRE_BC_SANITY_REPORT

- Decision: INCONCLUSIVE_NEEDS_MANUAL_CHECK

## Sub-decisions
- mask_audit: PASS_MASK_BUT_POLICY_COLLAPSE
- reward_sanity: PARTIAL_PASS_REWARD_SANITY
- dataset_validation: INCONCLUSIVE_NEEDS_MANUAL_CHECK
- overfit: PARTIAL_PASS_OVERFIT_LIMITED_CLASSES

## Readiness
- can_proceed_to_full_scripted_bc_dataset_exporter: False
- can_run_full_scripted_bc_training_now: False
- can_run_ppo_fine_tune_now: False

## Caveats
- Reward sanity is partial: verify scripted vs random policy reward behavior before large scripted export.
- Overfit gate is partial due to limited class support in minimal dataset.
- PASS/PARTIAL here means only readiness for teacher-side scripted BC warm-start, not teacher-ready and not Unity-ready.
- PPO fine-tune is blocked until scripted BC checkpoint passes deterministic behavior gate.
