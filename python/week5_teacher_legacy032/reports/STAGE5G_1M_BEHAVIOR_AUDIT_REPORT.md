# Stage5G 1M Behavior Audit

- run_id: stage5g_1m_behavior_audit_20260505T174039Z
- timestamp: 2026-05-05T17:40:39Z
- checkpoint_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_1m_20260504T231107Z\stage_001000000\agent_final.pt
- model_metadata_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_resume_1m_20260504T231107Z\stage_001000000\model_metadata.json
- strict_load_status: STRICT_LOAD_ENFORCED
- checkpoint_load_ok: True
- policy_architecture_load_ok: True
- inference_ok: True
- mask_used_during_eval: True
- env_matches_target_24x24: True
- env_matches_training_metadata: True

## Core Decision

- classification: STAGE5G_ZERO_WIN_EARLY_ENV_DONE
- behavior_decision: ZERO_WIN_WITH_EARLY_ENV_DONE

## Horizon Diagnostics

- observed_max_episode_length_at_6000_modes: 1775
- observed_max_episode_length_at_12000_modes: 712
- observed_max_episode_length_increased_with_12000: False
- likely_internal_cap_detected: True
- internal_cap_evidence: Observed max episode length did not increase when requested horizon changed 6000->12000, and episodes ended via env_done before outer loop limit in all core modes.

## Audit Matrix Summary

### A_deterministic_6000

- deterministic: True
- episodes_requested: 16
- episodes_completed: 16
- max_steps_per_episode_requested: 6000
- env_max_steps: 6000
- observed_max_episode_length: 1775
- episode_end_reason_counts: {'env_done': 16, 'env_truncated': 0, 'outer_loop_limit': 0, 'unknown': 0}
- mean_return: -10.0
- std_return: 0.0
- win_rate: 0.0
- all_cell.noop_share: 0.9965765951595159
- all_cell.move_share: 0.0
- all_cell.effective_activity_share: 0.00342340484048409
- source_valid.source_valid_cell_share: 0.0034234048404840484
- source_valid.source_valid_noop_share: 0.0
- source_valid.source_valid_move_share: 0.0
- source_valid.source_valid_effective_activity_share: 1.0

### B_stochastic_6000

- deterministic: False
- episodes_requested: 16
- episodes_completed: 16
- max_steps_per_episode_requested: 6000
- env_max_steps: 6000
- observed_max_episode_length: 712
- episode_end_reason_counts: {'env_done': 16, 'env_truncated': 0, 'outer_loop_limit': 0, 'unknown': 0}
- mean_return: -10.0
- std_return: 0.0
- win_rate: 0.0
- all_cell.noop_share: 0.16618445177851118
- all_cell.move_share: 0.16620290154015402
- all_cell.effective_activity_share: 0.8338155482214888
- source_valid.source_valid_cell_share: 0.003429134580124679
- source_valid.source_valid_noop_share: 0.02282448870471862
- source_valid.source_valid_move_share: 0.0
- source_valid.source_valid_effective_activity_share: 0.9771755112952814

### C_deterministic_12000

- deterministic: True
- episodes_requested: 16
- episodes_completed: 16
- max_steps_per_episode_requested: 12000
- env_max_steps: 12000
- observed_max_episode_length: 712
- episode_end_reason_counts: {'env_done': 16, 'env_truncated': 0, 'outer_loop_limit': 0, 'unknown': 0}
- mean_return: -10.0
- std_return: 0.0
- win_rate: 0.0
- all_cell.noop_share: 0.9965708654198753
- all_cell.move_share: 0.0
- all_cell.effective_activity_share: 0.0034291345801247264
- source_valid.source_valid_cell_share: 0.003429134580124679
- source_valid.source_valid_noop_share: 0.0
- source_valid.source_valid_move_share: 0.0
- source_valid.source_valid_effective_activity_share: 1.0

### D_stochastic_12000

- deterministic: False
- episodes_requested: 16
- episodes_completed: 16
- max_steps_per_episode_requested: 12000
- env_max_steps: 12000
- observed_max_episode_length: 712
- episode_end_reason_counts: {'env_done': 16, 'env_truncated': 0, 'outer_loop_limit': 0, 'unknown': 0}
- mean_return: -10.0
- std_return: 0.0
- win_rate: 0.0
- all_cell.noop_share: 0.16618559772643932
- all_cell.move_share: 0.16620290154015402
- all_cell.effective_activity_share: 0.8338144022735607
- source_valid.source_valid_cell_share: 0.003429134580124679
- source_valid.source_valid_noop_share: 0.023158668627188878
- source_valid.source_valid_move_share: 0.0
- source_valid.source_valid_effective_activity_share: 0.9768413313728112

### E_deterministic_20000

- deterministic: True
- episodes_requested: 8
- episodes_completed: 8
- max_steps_per_episode_requested: 20000
- env_max_steps: 20000
- observed_max_episode_length: 712
- episode_end_reason_counts: {'env_done': 8, 'env_truncated': 0, 'outer_loop_limit': 0, 'unknown': 0}
- mean_return: -10.0
- std_return: 0.0
- win_rate: 0.0
- all_cell.noop_share: 0.9965651659384103
- all_cell.move_share: 0.0
- all_cell.effective_activity_share: 0.003434834061589731
- source_valid.source_valid_cell_share: 0.0034348340615896794
- source_valid.source_valid_noop_share: 0.0
- source_valid.source_valid_move_share: 0.0
- source_valid.source_valid_effective_activity_share: 1.0

### F_stochastic_20000

- deterministic: False
- episodes_requested: 8
- episodes_completed: 8
- max_steps_per_episode_requested: 20000
- env_max_steps: 20000
- observed_max_episode_length: 712
- episode_end_reason_counts: {'env_done': 8, 'env_truncated': 0, 'outer_loop_limit': 0, 'unknown': 0}
- mean_return: -10.0
- std_return: 0.0
- win_rate: 0.0
- all_cell.noop_share: 0.16615136027881813
- all_cell.move_share: 0.16624726903870163
- all_cell.effective_activity_share: 0.8338486397211818
- source_valid.source_valid_cell_share: 0.0034348340615896794
- source_valid.source_valid_noop_share: 0.02218409843823947
- source_valid.source_valid_move_share: 0.0
- source_valid.source_valid_effective_activity_share: 0.9778159015617606

## Decision Reasons

- Both deterministic and stochastic win_rate are 0.0.
- Observed episode horizon did not increase under 12000 request.

## Errors

- none

## Warnings

- none

- json_report: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage5g_1m_behavior_audit_20260505T174039Z.json
- markdown_report: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\reports\stage5g_1m_behavior_audit_20260505T174039Z.md