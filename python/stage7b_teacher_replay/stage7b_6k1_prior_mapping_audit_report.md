# Stage7B-6K.1 Prior Mapping Audit Report

## Scope

Audit-only comparison of prior Stage6B3/Stage10D semantic mapping work against the current Stage7B TeacherReplay resolver. No resolver/runtime code was changed, no training was run, and no demo was recorded.

Generated at UTC: `2026-05-10T18:44:17Z`

## Files Inspected

- Unity action/runtime contract: `Assets/Scripts/ML/ActionContract.cs`, `ActionContractMappings.cs`, `ActionDecoder.cs`, `ActionMaskBuilder.cs`, `ActionApplier.cs`, `Week6StudentPolicyAdapter.cs`
- Unity direction/grid truth: `Assets/Scripts/Core/UnitType.cs`, `Assets/Scripts/Gameplay/Grid/GridPosition.cs`
- Stage7B replay/candidate path: `Stage7BTeacherReplayActionResolver.cs`, `MlAgentsCandidateActionBuilder.cs`, `Stage7BTeacherActionConverter.cs`
- Python adapter path: `student_inference_adapter.py`, `student_branch_contract.py`, `stage10d6_run_semantic_adapter_rebuild.py`, `stage10d13a_current_action_direction_fix_candidate_audit.py`
- Legacy032 export/action path: `legacy032_policy_action.py`, `export_replay_ready_teacher_rollout_stage7b.py`, `adapt_legacy032_to_unity_v2*.py`
- Legacy032 source truth: `gym_microrts/types.py`, `microrts/src/rts/UnitAction.java`, `microrts/src/rts/units/Unit.java`
- Reports/docs: Stage10D reports, Stage7B-6J report, pipeline baseline docs

## Old Mapping Fix Found

Found: yes, but it is an observation-side semantic mapping fix, not a reusable action-branch direction remap.

The prior Stage6B3/Stage10D work fixed semantic observation mismatches by making `unity_v2_runtime_semantic_obs_fix` explicit. The relevant files are:

- `python/week5_teacher_legacy032/observation_semantics/legacy032_to_unity_v2_observation_mapping.json`
- `python/week5_teacher_legacy032/semantic_observation_adapter_legacy032_to_unity_v2.py`
- `python/week5_teacher_legacy032/scripts/adapt_legacy032_to_unity_v2_observation_semantics.py`
- `python/week6_student/stage10d6_run_semantic_adapter_rebuild.py`
- `python/week6_student/stage10d13a_current_action_direction_fix_candidate_audit.py`

Important distinction: the old fix maps observation channels and probes current_action/direction observation sensitivity. I did not find an existing function that converts legacy032 action branch directions into Unity `Direction` values for Move/Harvest/Return/Produce.

## Direction Conventions

Unity canonical direction convention:

| Value | Direction | Grid effect |
|---:|---|---|
| 0 | North | `Y + 1` |
| 1 | East | `X + 1` |
| 2 | South | `Y - 1` |
| 3 | West | `X - 1` |

Sources:

- `UnitType.cs`: `Direction { North=0, East=1, South=2, West=3 }`
- `GridPosition.Neighbour`: North is `Y + 1`, South is `Y - 1`
- `ActionApplier`: comment confirms `North=+Y, South=-Y, East=+X, West=-X`
- `ActionContract.cs`: branch direction order is `0=N, 1=E, 2=S, 3=W`

Legacy032/microRTS action direction convention:

| Value | Legacy032 name | Grid effect |
|---:|---|---|
| 0 | UP | `Y - 1` |
| 1 | RIGHT | `X + 1` |
| 2 | DOWN | `Y + 1` |
| 3 | LEFT | `X - 1` |

Sources:

- `gym_microrts/types.py`: `UP=0`, `RIGHT=1`, `DOWN=2`, `LEFT=3`
- `UnitAction.java`: `DIRECTION_OFFSET_X = {0,1,0,-1}`, `DIRECTION_OFFSET_Y = {-1,0,1,0}`
- `Unit.java`: Move/Harvest/Return/Produce all use the same direction constants

Conclusion: Unity and legacy032 use the same integer order shape but opposite Y-axis semantics for the vertical directions.

## Stage7B Current Mapping Problem

`Stage7BTeacherReplayActionResolver` currently maps teacher direction branches directly into Unity directions:

- `move_dir`: raw `command.move_dir` -> `TryDirectionFromIndex`
- `harvest_dir`: raw `command.harvest_dir` -> `TryDirectionFromIndex`
- `return_dir`: raw `command.return_dir` -> `TryDirectionFromIndex`
- `produce_dir`: raw `command.produce_dir` -> `TryDirectionFromIndex`

The single-actor path also casts raw per-cell branch values directly:

- `(Direction)perCellBranchesFlat[BRANCH_MOVE_DIR]`
- `(Direction)perCellBranchesFlat[BRANCH_HARVEST_DIR]`
- `(Direction)perCellBranchesFlat[BRANCH_RETURN_DIR]`
- `(Direction)perCellBranchesFlat[BRANCH_PRODUCE_DIR]`

This is missing a legacy032-to-Unity y-axis conversion for action branch directions.

## 6J Mismatch Evidence

Source:

`python/week5_teacher_legacy032/teacher_replay_exports/stage7b_replay_ready_stage7b6j_return_direction_audit_e8_s512_20260510T174822Z`

Key metrics:

- episodes_scanned: 8
- steps_total: 4096
- teacher_commands_total: 2952
- state_sync_success_count: 4096
- state_sync_failed_count: 0
- runtime_apply_accept_rate: 1.0
- return_commands_total: 134
- return_commands_matched: 72
- return_commands_dropped: 62
- return_match_rate: 0.5373134613
- return_direction_mismatch_count: 62
- return_direction_mismatch_rate: 0.4626865685
- return_mismatch_by_teacher_dir: South = 62
- return_mismatch_by_candidate_dir: North = 62
- y_axis_flip_suspected_count: 62
- x_axis_flip_suspected_count: 0
- target_cell_has_base_teacher_side_count: 0
- target_cell_has_base_unity_side_count: 62

Representative example:

- episode 0, step 30
- actor `(2,1)`
- teacher Return direction currently interpreted as South -> target `(2,0)`, no base
- Unity legal candidate Return direction is North -> target `(2,2)`, friendly base

That is direct occupant proof for Return y-axis inversion.

## Recommended Fix Scope

Recommended for Stage7B-6K.2: `return_only`.

Exact mapping to apply to Stage7B Return replay resolution:

| Teacher legacy032 direction | Raw value | Unity direction | Unity value |
|---|---:|---|---:|
| UP / teacher North | 0 | South | 2 |
| RIGHT / teacher East | 1 | East | 1 |
| DOWN / teacher South | 2 | North | 0 |
| LEFT / teacher West | 3 | West | 3 |

Rationale:

- Return has strong 6J target-cell proof.
- The old Stage10D fix does not provide an action-branch adapter function to reuse.
- Legacy032 source suggests the same conversion may eventually apply to all cardinal action branches, but 6J only proves Return with friendly-base semantics.
- A broad Move/Harvest/Produce remap should be a follow-up only if Return-only validation leaves systematic y-axis mismatch evidence for those branches.

## Risks

- Return-only may leave Move/Harvest/Produce direction mismatch counts unresolved.
- All-branch remap is tempting from source-code semantics, but it has a larger regression surface and lacks 6J-equivalent target proof for every branch.
- Do not change `ActionApplier`, `MatchManager`, `MlAgentsCandidateActionBuilder`, teacher policy, or Stage6B3 assets for this fix; runtime truth should remain authoritative.

## Validation Plan After Stage7B-6K.2

Rerun on the same 6J source:

`python/week5_teacher_legacy032/teacher_replay_exports/stage7b_replay_ready_stage7b6j_return_direction_audit_e8_s512_20260510T174822Z`

Expected success metrics:

- `state_sync_failed_count = 0`
- `runtime_apply_accept_rate` remains `1.0` or near `1.0`
- `return_direction_mismatch_count_after_6k ~= 0`
- `return_match_rate_after_6k` improves from `0.5373`
- overall `candidate_match_rate` improves from `0.79065`
- no regression in Move/Harvest/Produce matching
- Stage6B3 baseline untouched
- no ML-Agents training, PPO, imitation learning, or `.demo` recording

## Explicit Confirmations

- `stage6b3_baseline_touched`: false
- `ml_agents_training_started`: false
- `ppo_started`: false
- `imitation_learning_started`: false
- `demo_recording_started`: false
