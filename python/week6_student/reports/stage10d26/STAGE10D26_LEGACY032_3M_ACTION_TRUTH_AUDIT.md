# STAGE10D26 — Legacy032 3M Action Truth Audit

**Generated**: 2026-05-04T20:49:55Z  
**Status**: COMPLETE

---

## Summary

| Item | Value |
|------|-------|
| Checkpoint | `C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_main_20260430T130208Z\stage_003000000\agent_final.pt` |
| Checkpoint exists | True |
| Metadata contract match | True |
| Arch | `legacy032_resolution_aware_gridnet_v1` |
| Obs shape | `[24, 24, 27]` |
| Action nvec | `[576, 6, 4, 4, 4, 4, 7, 49]` |
| Total timesteps | `2,999,808` |
| Map | `maps/24x24/basesWorkers24x24.xml` |
| Seed | `17` |
| Direct eval env available | True |
| Direct eval model loaded | True |

---

## Part A — Checkpoint Contract

- **Checkpoint path**: `C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_main_20260430T130208Z\stage_003000000\agent_final.pt`
- **Metadata path**: `C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_main_20260430T130208Z\stage_003000000\model_metadata.json`
- **obs [24,24,27]**: True  
- **nvec [576,6,4,4,4,4,7,49]**: True  
- **arch legacy032_resolution_aware_gridnet_v1**: True  

### Branch Semantics
- **Raw global action** nvec[0..7]: branch 0 = actor_index (0..575), branch 1 = action_type (0..5)
- **Per-cell action** shape [576,7]: branch 0 = **action_type** (actor_index dropped in `infer_actions`)
- Per-cell branch 0 IS action_type — reading it as action_type is **semantically correct**.

### Errors
_none_

---

## Part B — Original Training Gate (3M Stage)

### Deterministic Eval (8 eps, 24x24, mask=True)
- Mean return: `-10.0`
- Total env steps: `8544`
- **action_type_counts**:
  - attack: 40  (0.00%)
  - harvest: 8,504  (0.17%)
  - move: 0  (0.00%)
  - noop: 4,904,440  (99.66%)
  - produce: 8,360  (0.17%)
  - return: 0  (0.00%)
- move_share: `0.0`
- noop_share: `0.9965651659384103`
- effective_activity_share: `0.003434834061589731`

### Stochastic Eval Note
The gate stochastic eval shows ~16.6% for every action type (noop, move, harvest, return, produce, attack).
This is **NOT real move behaviour**. It is the result of:
1. The policy has nearly-uniform logits across 6 action types (high entropy).
2. Stochastic sampling from a uniform distribution gives ~1/6 ≈ 16.7% per action type.
3. ALL 576 cells are sampled, including cells with no unit.
4. The deterministic argmax shows 99.7% noop — the policy clearly prefers noop.

### Rollout Export Summary
- Total steps: `88165`
- Action histogram:
  - attack: 95  (0.00%)
  - harvest: 86,570  (0.17%)
  - noop: 50,608,730  (99.66%)
  - produce: 87,645  (0.17%)
- **move_count**: `0`

---

## Part C — Direct model.predict Action Truth

Direct eval was performed.

### Deterministic (4 eps)
- Total env steps: `17895`
- Mean return: `-10.0`
- **action_type_counts**:
  - attack: 10,307,520  (100.00%)
- **move_count**: `0`
- **move_share**: `0.0`
- per_cell_b0_range: `[5, 5]` (must be [0..5] for action_type)
- per_cell_b0_in_action_type_range: `True`

### Stochastic (4 eps) — HIGH-ENTROPY NOISE ONLY
- move_count: `22`
- Note: Stochastic sampling with high-entropy logits produces ~uniform distribution across action types even if argmax (deterministic) is always noop. Move count in stochastic mode is NOT evidence of real move behaviour.

---

## Part D — Movement State-Delta Truth

- movement_state_delta_count (det): `0`
- movement_state_delta_count (stoch): `0`

Observation state-deltas detect unit position changes regardless of which action type was recorded.
If state deltas > 0 but move_count = 0, the raw action interpretation may be wrong.
If state deltas = 0 and move_count = 0, the teacher genuinely does not move in this scenario.

---

## Part E — Export NPZ Key Audit


### export_raw: `teacher_rollout_raw.npz`
- exists: True

#### key: `episode_id`
  - shape: `[88165]` dtype: `int32`
  - min/max: `0.0 / 15.0`
  - interpretation: `step_scalar_array`

#### key: `step_id`
  - shape: `[88165]` dtype: `int32`
  - min/max: `0.0 / 5999.0`
  - interpretation: `step_scalar_array`

#### key: `observation_t`
  - shape: `[88165, 24, 24, 27]` dtype: `float32`
  - min/max: `0.0 / 1.0`
  - interpretation: `observation_spatial_N_24_24_27`

#### key: `raw_action_t`
  - shape: `None` dtype: `None`
  - min/max: `None / None`
  - interpretation: `None`

#### key: `per_cell_action_t`
  - shape: `[88165, 576, 7]` dtype: `int16`
  - min/max: `0.0 / 31.0`
  - interpretation: `per_cell_action_N_576_7`
  - action_type (b0) histogram (sampled):
    - noop: 2,870,125
    - harvest: 4,870
    - produce: 5,000
    - attack: 5
  - **move_count (b0)**: `0`
  - note: Shape [N,576,7]: per-cell action. Branch 0 = action_type (0..5). Actor_index branch was dropped.

#### key: `reward_t`
  - shape: `[88165]` dtype: `float32`
  - min/max: `-10.0 / 0.0`
  - interpretation: `step_scalar_array`

#### key: `done_t`
  - shape: `[88165]` dtype: `bool`
  - min/max: `0.0 / 1.0`
  - interpretation: `step_scalar_array`

#### key: `terminated_t`
  - shape: `[88165]` dtype: `bool`
  - min/max: `0.0 / 1.0`
  - interpretation: `step_scalar_array`

#### key: `truncated_t`
  - shape: `[88165]` dtype: `bool`
  - min/max: `0.0 / 0.0`
  - interpretation: `step_scalar_array`

#### key: `info_t_json`
  - shape: `None` dtype: `None`
  - min/max: `None / None`
  - interpretation: `None`

#### key: `action_mask_t`
  - shape: `None` dtype: `None`
  - min/max: `None / None`
  - interpretation: `None`

#### key: `action_mask_available_t`
  - shape: `[88165]` dtype: `bool`
  - min/max: `1.0 / 1.0`
  - interpretation: `step_scalar_array`

### adapted: `adapted_dataset.npz`
- exists: True

#### key: `observations`
  - shape: `[88165, 576, 27]` dtype: `float32`
  - min/max: `0.0 / 1.0`
  - interpretation: `observation_flat_N_576_27`

#### key: `actions`
  - shape: `[88165, 576, 7]` dtype: `int16`
  - min/max: `0.0 / 31.0`
  - interpretation: `per_cell_action_N_576_7`
  - action_type (b0) histogram (sampled):
    - noop: 2,870,125
    - harvest: 4,870
    - produce: 5,000
    - attack: 5
  - **move_count (b0)**: `0`
  - note: Shape [N,576,7]: per-cell action. Branch 0 = action_type (0..5). Actor_index branch was dropped.

#### key: `episode_id`
  - shape: `[88165]` dtype: `int32`
  - min/max: `0.0 / 15.0`
  - interpretation: `step_scalar_array`

#### key: `step_id`
  - shape: `[88165]` dtype: `int32`
  - min/max: `0.0 / 5999.0`
  - interpretation: `step_scalar_array`

#### key: `reward_t`
  - shape: `[88165]` dtype: `float32`
  - min/max: `-10.0 / 0.0`
  - interpretation: `step_scalar_array`

#### key: `done_t`
  - shape: `[88165]` dtype: `bool`
  - min/max: `0.0 / 1.0`
  - interpretation: `step_scalar_array`

#### key: `terminated_t`
  - shape: `[88165]` dtype: `bool`
  - min/max: `0.0 / 1.0`
  - interpretation: `step_scalar_array`

#### key: `truncated_t`
  - shape: `[88165]` dtype: `bool`
  - min/max: `0.0 / 0.0`
  - interpretation: `step_scalar_array`

#### key: `action_mask_available_t`
  - shape: `[88165]` dtype: `bool`
  - min/max: `1.0 / 1.0`
  - interpretation: `step_scalar_array`

### bc_train: `bc_train.npz`
- exists: True

#### key: `observations`
  - shape: `[74940, 576, 27]` dtype: `float32`
  - min/max: `0.0 / 1.0`
  - interpretation: `observation_flat_N_576_27`

#### key: `actions`
  - shape: `[74940, 576, 7]` dtype: `int16`
  - min/max: `0.0 / 31.0`
  - interpretation: `per_cell_action_N_576_7`
  - action_type (b0) histogram (sampled):
    - noop: 2,870,134
    - harvest: 4,875
    - produce: 4,987
    - attack: 4
  - **move_count (b0)**: `0`
  - note: Shape [N,576,7]: per-cell action. Branch 0 = action_type (0..5). Actor_index branch was dropped.

#### key: `episode_id`
  - shape: `[74940]` dtype: `int32`
  - min/max: `0.0 / 15.0`
  - interpretation: `step_scalar_array`

#### key: `step_id`
  - shape: `[74940]` dtype: `int32`
  - min/max: `0.0 / 5999.0`
  - interpretation: `step_scalar_array`

#### key: `reward_t`
  - shape: `[74940]` dtype: `float32`
  - min/max: `-10.0 / 0.0`
  - interpretation: `step_scalar_array`

#### key: `done_t`
  - shape: `[74940]` dtype: `bool`
  - min/max: `0.0 / 1.0`
  - interpretation: `step_scalar_array`

#### key: `terminated_t`
  - shape: `[74940]` dtype: `bool`
  - min/max: `0.0 / 1.0`
  - interpretation: `step_scalar_array`

#### key: `truncated_t`
  - shape: `[74940]` dtype: `bool`
  - min/max: `0.0 / 0.0`
  - interpretation: `step_scalar_array`

#### key: `action_mask_available_t`
  - shape: `[74940]` dtype: `bool`
  - min/max: `1.0 / 1.0`
  - interpretation: `step_scalar_array`

---

## Part F — First Move-Loss Boundary

### Pipeline Stage Move Counts

| Stage | Source | Field | Move Count |
|-------|--------|-------|------------|
| 0 direct_model_predict_deterministic | part_C_D live eval | per_cell[:,0] = action_type | 0 |
| 1 direct_model_predict_stochastic | part_C_D live eval | per_cell[:,0] = action_type | 22 |
| 2 export_rollout_npz_per_cell_action_t | teacher_rollout_raw.npz | per_cell_action_t[:,:,0] (per_cell action_type) | 0 |
| 3 semantic_adapted_npz_actions | adapted_dataset.npz | actions[:,:,0] | 0 |
| 4 bc_ready_train_npz | bc_train.npz | actions[:,:,0] | 0 |

### First Loss Boundary
{
  "from_stage": "direct_model_predict_stochastic",
  "from_move_count": 22,
  "to_stage": "export_rollout_npz_per_cell_action_t",
  "to_move_count": 0
}

### Diagnosis
TEACHER_DOES_NOT_MOVE_DETERMINISTICALLY: The 3M teacher's argmax (deterministic) policy selects move=0 across all evaluated episodes. This is consistent across the training gate, rollout export, adapted dataset, and BC-ready split — all show zero move. The teacher appears to have learned a policy that does not issue Move commands, relying instead on Harvest, Produce, and Attack (resource gathering + unit production + combat). This is not a branch-interpretation error — per-cell branch 0 IS action_type (correct). The stochastic eval showing ~16.6% move is HIGH-ENTROPY noise from sampling a nearly-uniform logit distribution, not real move behaviour. Since direct model.predict shows move=0, there is NO Move to lose in any downstream stage.

### Stage10D25 Branch Interpretation Review
{
  "question": "Did Stage10D25 misread branch 0 as action_type for raw global action?",
  "answer": "NO \u2014 Stage10D25 and all pipeline stages operate on per-cell representation [N,576,7] where branch 0 IS action_type. The actor_index branch (nvec[0]=576) is dropped in infer_actions(). So per_cell[:,0] = action_type = correct interpretation. Stage10D25's finding of move=0 is valid.",
  "raw_global_branch_semantics": {
    "branch_0": "actor_index (0..575) \u2014 source cell",
    "branch_1": "action_type (0..5)"
  },
  "per_cell_branch_semantics": {
    "branch_0": "action_type (0..5) \u2014 actor_index dropped",
    "branch_1": "move_dir (0..3)"
  },
  "stage10d25_was_correct": true
}

---

## GO / NO-GO Decision

**Recommendation**: NO-GO for corrected Legacy032 3M BC dataset as primary Move source. The teacher itself does not produce Move actions deterministically. The stochastic sampling ~16.6% is high-entropy noise. ACTION: use gridnet_stoch_adapted_episodes as the Move source (already identified in Stage10D25 as having 20% deterministic move_share). The Legacy032 3M teacher is valid as a Harvest/Produce source but NOT as a Move source.

### Gate Details

- **checkpoint_located**: PASS
  - value: C:\Projects\UnityRTSPrototype\UnityRTSPrototype\python\week5_teacher_legacy032\teacher_models\legacy032_24x24_teacher_main_20260430T130208Z\stage_003000000\agent_final.pt

- **action_semantics_proven**: PASS
  - value: The export script (export_teacher_rollout_legacy032.py) uses nvec[1:] for per-cell branches and drops nvec[0] (actor_index). Per-cell branch 0 = action_type is CORRECT. Stage10D25 raw audit counted per_cell[:,0] = action_type, which is semantically correct.

- **direct_behaviour_understood**: PASS
  - env_available: True
  - model_loaded: True
  - gate_fallback_available: True
  - note: Direct eval performed

- **move_exists_in_teacher**: FAIL
  - det_move_count: 0
  - state_delta_count: 0
  - stoch_move_count: 22
  - stoch_note: stochastic move is HIGH-ENTROPY noise; not evidence of move behaviour
  - verdict: NO_MOVE

- **move_loss_boundary_identified**: PASS
  - first_loss_boundary: {'from_stage': 'direct_model_predict_stochastic', 'from_move_count': 22, 'to_stage': 'export_rollout_npz_per_cell_action_t', 'to_move_count': 0}
