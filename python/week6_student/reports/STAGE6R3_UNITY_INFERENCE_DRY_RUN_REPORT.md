# STAGE6R3 UNITY INFERENCE DRY-RUN REPORT

## Final classification

STAGE6R3_UNITY_INFERENCE_DRY_RUN_PASS_READY_FOR_CONTROLLED_SCENE_SANITY

## Scope guardrails

- Dry-run scope only: Unity observation to student adapter output to Unity payload validation.
- No match-quality evaluation was run.
- No behavior-quality claim is made.
- No semantic parity claim is made.
- No direct weight-transfer claim is made.

## Canonical checkpoint

- Path used: python/week6_student/runs/legacy032_v2_bc_short_stage6a2/legacy032_v2_bc_short_stage6a2_smoke_checkpoint.pt
- Exists: true
- Extension: .pt
- checkpoint_model_variant: transfer

## Task 1: Pre-dry-run static checks

- Week6StudentPolicyAdapter default checkpoint path points to Stage6A2: true
- Week6Day4StudentInferenceDryRun default checkpoint path points to Stage6A2: true
- v1 rejection guard remains present: true
- Old filename-family allowlist is authoritative gate: false
- Compatibility gate present: true (.pt extension + bridge startup + payload validation)
- Fake/heuristic/random fallback introduced in Stage6R3 path: false

## Task 2: Python adapter/server dry-run

- Adapter CLI used: python/week6_student/student_inference_adapter.py
- Artifact: python/week6_student/runs/legacy032_v2_unity_dryrun_stage6r3/python_adapter_dryrun_report.json
- status: ok
- action_contract_version: v2_gridnet_compatible
- branch_sizes: [6,4,4,4,4,7,49]
- produce head size: 7
- attack head size: 49
- action_flat_size: 44928
- observation_shape: [24,24,27]
- output logits shapes: [1,576,branch] per 7 branches
- NaN/Inf detected: false
- v1 regression detected: false
- predicted_noop_count: 1
- predicted_noop_share: 0.001736111111111111

## Task 3: Unity dry-run execution

- Unity Play Mode run: true
- Entrypoint used: SmokeTest/11 - Unity Action Contract v2 Full Evidence Smoke
- Dry-run component: Week6Day4StudentInferenceDryRun
- Bridge startup: pass
- Adapter ready handshake: pass
- checkpoint_model_variant: transfer
- Payload received and validated: pass
- action_contract_version: v2_gridnet_compatible
- branch_sizes: [6,4,4,4,4,7,49]
- produce head size: 7
- attack head size: 49
- action_flat_size: 44928
- Decoded output inspected: true
- command_built_count: 8
- commands_accepted_count: 1
- commands_rejected_count: 7
- v1 payload rejection guard active: true
- v1 regression detected: false
- fallback used: false
- fake logits used: false
- heuristic policy used: false

## Task 4: Artifacts

- Main markdown report: python/week6_student/reports/STAGE6R3_UNITY_INFERENCE_DRY_RUN_REPORT.md
- Main JSON report: python/week6_student/reports/stage6r3_unity_inference_dry_run_report.json
- Python adapter dry-run report: python/week6_student/runs/legacy032_v2_unity_dryrun_stage6r3/python_adapter_dryrun_report.json
- Unity dry-run smoke report: python/week6_student/tmp/day4_unity_playmode_smoke_report.json
- Unity adapter output snapshot: WEEK6/artifacts/day4_student_inference/student_inference_result.json
- stage6r3_unity_dryrun_snapshot.json: python/week6_student/reports/stage6r3_unity_dryrun_snapshot.json
- stage6r3_bridge_startup_report.json: python/week6_student/reports/stage6r3_bridge_startup_report.json
- stage6r3_payload_validation_report.json: python/week6_student/reports/stage6r3_payload_validation_report.json

## Required safety assertions

- ActionApplier and MatchManager.ApplyCommand remain authoritative runtime enforcement.
- Mask was treated as pre-submit/diagnostic only.
- No BC training run in Stage6R3.
- No PPO fine-tuning run in Stage6R3.
- No teacher training run in Stage6R3.
- Week 5 artifacts were not modified in Stage6R3.

## Next stage recommendation (not executed)

Stage6R4 — Controlled Unity scene sanity run with global diagnostics
