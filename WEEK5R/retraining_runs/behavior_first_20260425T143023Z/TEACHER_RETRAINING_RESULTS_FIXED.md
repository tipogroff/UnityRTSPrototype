# Teacher Retraining Results (Fixed Gate Recheck)

- run_id: behavior_first_20260425T143023Z
- run_status: completed_with_failures (original training run status)
- retraining_dir: WEEK5R/retraining_runs/behavior_first_20260425T143023Z
- fixed_gate_json_dir: WEEK5R/gate_runs/recheck_20260425
- fixed_gate_comparison_md: WEEK5R/gate_runs/behavior_first_20260425T143023Z/TEACHER_BEHAVIOR_GATE_COMPARISON_FIXED.md

## Fixed Gate Checkpoints (after mask handling fix)

| step | status | actor_level_move_share | actor_noop_share | effective_position_delta_count | no_effect_action_share |
|---|---|---:|---:|---:|---:|
| 5000 | SUSPICIOUS | 0.010375 | 0.986433 | 1 | 0.991935 |
| 10000 | FAIL_COLLAPSED_NOOP | 0.000000 | 0.998651 | 0 | 1.000000 |
| 20000 | SUSPICIOUS | 0.000680 | 0.996263 | 1 | 0.992481 |

## Correction Note (10k artifact)

- Old 10k value actor_move=0.6667 in WEEK5R/gate_runs/behavior_first_20260425T143023Z/step_000010000/gate_teacher_sb3_ppo_step_000010000.json was a diagnostic artifact from incorrect mask handling in teacher_behavior_gate.py.
- Root cause: gate passed 3D action mask into model.predict; exception path silently fell back to prediction without mask, which invalidated actor-level interpretation.
- Fixed 10k verdict from recheck is FAIL_COLLAPSED_NOOP with:
  - actor_level_move_share = 0.0
  - actor_noop_share = 0.998651
  - effective_position_delta_count = 0
  - no_effect_action_share = 1.0

## Final Conclusion

- Final corrected conclusion is unchanged in substance: current PPO recipe does not produce meaningful actor-level movement by 20k.
- Evidence:
  - 10k is explicit collapse (FAIL_COLLAPSED_NOOP).
  - 5k and 20k are only SUSPICIOUS, with extremely high noop/no-effect rates and near-zero actor-level move share.
  - Effective behavior remains mostly inert (1 position delta in 100 effective audit steps at both 5k and 20k).

## Fixed Source Files

- WEEK5R/gate_runs/recheck_20260425/gate_teacher_sb3_ppo_step_000005000.json
- WEEK5R/gate_runs/recheck_20260425/gate_teacher_sb3_ppo_step_000010000.json
- WEEK5R/gate_runs/recheck_20260425/gate_teacher_sb3_ppo_step_000020000.json
- WEEK5R/gate_runs/behavior_first_20260425T143023Z/TEACHER_BEHAVIOR_GATE_COMPARISON_FIXED.md
