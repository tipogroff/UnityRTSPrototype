# Legacy032 Checkpoint Roundtrip Audit

- timestamp_utc: 2026-05-04T22:20:32Z
- checkpoint_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_main_20260430T130208Z\stage_003000000\agent_final.pt
- metadata_path: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_main_20260430T130208Z\stage_003000000\model_metadata.json
- status: OK

## Contract Assertions

- expected_observation_space: [24, 24, 27]
- expected_raw_action_nvec: [576, 6, 4, 4, 4, 4, 7, 49]
- expected_architecture: legacy032_resolution_aware_gridnet_v1
- expected_map_path: maps/24x24/basesWorkers24x24.xml
- expected_max_steps: 6000
- metadata_contract: {'observation_space': [24, 24, 27], 'raw_action_nvec': [576, 6, 4, 4, 4, 4, 7, 49], 'architecture_name': 'legacy032_resolution_aware_gridnet_v1'}

## Strict Load And Roundtrip

- strict_true_load_ok: True
- copy_load_strict_true_ok: True
- logits_max_abs_diff: 0.0
- logits_mean_abs_diff: 0.0
- logits_allclose_exact: True
- deterministic_actions_equal: True
- stochastic_actions_equal_fixed_seed: True

## Deterministic vs Stochastic Eval

- deterministic_all_cell_action_shares: {'NoOp': 0.9965651659384103, 'Move': 0.0, 'Harvest': 0.0017279832501040366, 'Return': 0.0, 'Produce': 0.0016987229504785684, 'Attack': 8.127861007074491e-06}
- deterministic_source_valid_cell_action_shares: {'NoOp': 0.0, 'Move': 0.0, 'Harvest': 0.5030761949834359, 'Return': 0.0, 'Produce': 0.4945575011831519, 'Attack': 0.00236630383341221}
- stochastic_all_cell_action_shares: {'NoOp': 0.16614404520391177, 'Move': 0.16599124141697877, 'Harvest': 0.16789194171348315, 'Return': 0.16606114102163963, 'Produce': 0.16787812434977112, 'Attack': 0.16603350629421557}
- stochastic_source_valid_cell_action_shares: {'NoOp': 0.048272598201609083, 'Move': 0.0, 'Harvest': 0.5030761949834359, 'Return': 0.0, 'Produce': 0.44628490298154283, 'Attack': 0.00236630383341221}

## Final Classifications

- SAVE_LOAD: SAVE_LOAD_OK
- RESUME: RESUME_NOT_SUPPORTED
- DETERMINISTIC_STOCHASTIC_MISMATCH: DETERMINISTIC_STOCHASTIC_MISMATCH_YES
- CHECKPOINT_PATH: CHECKPOINT_PATH_CONFIRMED
- NEXT_ACTION: ALIGN_DETERMINISTIC_AND_STOCHASTIC_EVAL_PATHS_AND_COMPARE_BOTH