# Stage5P2 — Legacy032 3M Main Rollout Export Report

**Date:** 2026-05-06
**Project:** UnityRTSPrototype Thesis
**Stage:** 5P2 — Legacy032 3M Main Rollout Export (16 episodes)

## 1. Executive summary

Stage5P2 main rollout export completed successfully from the preferred Legacy032 3M checkpoint using stochastic export with required mask and training-compatible stepping.

Hard validation checks passed for schema, action-path bounds, manifest contract, step consistency, and mask availability.

**Final classification:** `STAGE5P2_MAIN_EXPORT_PASS_READY_FOR_ADAPTER`

## 2. Exact command executed

```powershell
$env:JAVA_HOME='C:\Program Files\Eclipse Adoptium\jdk-17.0.18.8-hotspot'
$env:Path="$env:JAVA_HOME\bin;$env:Path"

c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/export_teacher_rollout_legacy032.py `
  --checkpoint-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/agent_final.pt `
  --model-metadata-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/model_metadata.json `
  --trainer-state-path python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/trainer_state_final.pt `
  --map-path maps/24x24/basesWorkers24x24.xml `
  --run-label legacy032_3m_unity_v2_rollout_export `
  --episodes 16 `
  --max-steps-per-episode 6000 `
  --seed 17 `
  --device cpu `
  --export-mode stochastic `
  --step-mode training_compatible `
  --require-mask true `
  --num-bot-envs 1 `
  --output-root python/week5_teacher_legacy032/teacher_rollouts
```

## 3. Output directory and files

**Run directory:**

`python/week5_teacher_legacy032/teacher_rollouts/legacy032_3m_unity_v2_rollout_export_20260506T144700Z/`

**Files present:**

1. `teacher_rollout_raw.npz`
2. `teacher_rollout_manifest.json`
3. `teacher_rollout_summary.json`

## 4. Checkpoint / metadata / trainer state

- Checkpoint: `python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/agent_final.pt`
- Metadata: `python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/model_metadata.json`
- Trainer state: `python/week5_teacher_legacy032/teacher_models/legacy032_24x24_teacher_resume_3m_from_1m_postfix/trainer_state_final.pt`
- Strict load report: `STRICT_LOAD_ENFORCED`, with zero missing and zero unexpected keys.

## 5. Export mode and step mode

- Export mode: `stochastic`
- Step mode: `training_compatible`
- Mask required: `true`
- Mask source: `env.vec_client.getMasks(0)`
- Num bot envs: `1`
- Device: `cpu`

## 6. Schema validation results

Validator command used:

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/validate_stage5p1_smoke_export.py `
  --rollout-dir python/week5_teacher_legacy032/teacher_rollouts/legacy032_3m_unity_v2_rollout_export_20260506T144700Z
```

Schema checks:

- Required NPZ arrays: PASS
- `observation_t`: shape `[37343,24,24,27]`, dtype `float32` (PASS)
- `per_cell_action_t`: shape `[37343,576,7]`, dtype `int16` (PASS)
- Metadata arrays length consistency (all `T=37343`): PASS
- NaN/Inf checks: PASS

## 7. Manifest validation results

Manifest contract checks:

- `schema_version`: `legacy032.teacher_rollout_raw.v2` (PASS)
- `teacher_lineage`: `legacy032` (PASS)
- `architecture`: `legacy032_resolution_aware_gridnet_v1` (PASS)
- `gym_microrts_version`: `0.3.2` (PASS)
- `map_path`: `maps/24x24/basesWorkers24x24.xml` (PASS)
- `raw_action_nvec`: `[576,6,4,4,4,4,7,49]` (PASS)
- `stored_action_branch_sizes`: `[6,4,4,4,4,7,49]` (PASS)
- `step_mode`: `training_compatible` (PASS)
- `export_mode`: `stochastic` (PASS)
- `step_mode_is_final_evidence_valid`: `true` (PASS)
- `semantic_parity_claim`: `false` (PASS)
- `direct_weight_transfer_claim`: `false` (PASS)

## 8. Action branch bounds validation

Branch sizes validated against `[6,4,4,4,4,7,49]` with global mins/maxes:

- Branch 0 (`action_type`) range: `[0,5]` PASS
- Branch 1 (`move_dir`) range: `[0,3]` PASS
- Branch 2 (`harvest_dir`) range: `[0,3]` PASS
- Branch 3 (`return_dir`) range: `[0,3]` PASS
- Branch 4 (`produce_dir`) range: `[0,3]` PASS
- Branch 5 (`produce_unit_type`) range: `[0,6]` PASS
- Branch 6 (`attack_target`) range: `[0,48]` PASS

## 9. Episode / step consistency validation

- Episode count: `16`
- Total steps: `37343`
- Episode lengths: `[2185,1999,1750,2489,3309,1442,2595,2749,3402,1839,3347,2686,1656,2147,2033,1715]`
- `step_id` starts at 0 and is contiguous inside every episode: PASS
- Terminal count: `16`
- Terminated count: `16`
- Truncated count: `0`

## 10. Mask availability validation

- `action_mask_available_share`: `1.0` (100.00%)
- `mask_available_count`: `37343`
- `mask_unavailable_count`: `0`
- Result: PASS

## 11. Behavior diagnostics

- Episode mean return: `197.875`
- Episode returns:
  `[200.2,204.2,190.2,211.2,203.4,137.4,219.2,215.2,219.2,189.2,205.4,197.4,201.2,199.2,171.2,202.2]`
- NoOp share: `16.984%`
- Action type histogram:
  `{0: 3653187, 1: 3643439, 2: 3551791, 3: 3551892, 4: 3558493, 5: 3550766}`
- Selected non-noop total: `17856381`
- Source-valid non-noop total: `103848`
- Source-valid total: `209357`
- Selected source-valid non-noop share (manifest): `0.4960330918001309`

Behavior is not fully degenerate and remains within expected constrained-action dynamics. No warning trigger required.

## 12. Comparison with Stage5P1 smoke export

Baseline (Stage5P1 smoke run):
`python/week5_teacher_legacy032/teacher_rollouts/legacy032_3m_unity_v2_rollout_smoke_20260506T142730Z/`

Comparison:

- Episodes: `2 -> 16`
- Steps: `4349 -> 37343`
- Observation schema: unchanged (`[T,24,24,27]`, `float32`)
- Action schema: unchanged (`[T,576,7]`, integer)
- Step mode: unchanged (`training_compatible`)
- Export mode: unchanged (`stochastic`)
- Mask availability: unchanged (`100% -> 100%`)
- NoOp share: `16.935% -> 16.984%` (stable)
- Mean return: `199.20 -> 197.875` (minor shift, not a contract concern)
- `semantic_parity_claim`: unchanged (`false`)
- `direct_weight_transfer_claim`: unchanged (`false`)

## 13. Warnings

None. Hard contract checks passed and behavior diagnostics do not indicate complete degeneracy.

## 14. Final decision

`STAGE5P2_MAIN_EXPORT_PASS_READY_FOR_ADAPTER`

## 15. Recommended next step

Proceed to:

**Stage5P3 — Adapt Main Legacy032 3M Rollout To Unity v2**

Recommended command (do not run in Stage5P2):

```powershell
c:/Projects/UnityRTSPrototype/UnityRTSPrototype/python/week5_teacher_reference/.venv_microrts032_reference/Scripts/python.exe `
  python/week5_teacher_legacy032/scripts/adapt_legacy032_to_unity_v2.py `
  --input-dir python/week5_teacher_legacy032/teacher_rollouts/legacy032_3m_unity_v2_rollout_export_20260506T144700Z
```

---

Stage boundary confirmation:

- BC training was not run.
- Unity was not launched.
- Adapter was not run.
