# Unity Action Contract v2 Step 5 Smoke Report

Date: 2026-04-28
Scope: Unity-side Action Contract v2 migration Step 5 runtime smoke/regression execution and report.

Constraints honored:
- No teacher training changes.
- No BC-ready packaging.
- No parity claim beyond smoke results.
- No behavior-logic edits were made in this step.

## 1. Summary table

| Test name | Status | Notes |
|---|---|---|
| ActionContractV2SmokeTest | NOT RUN | ContextMenu-only in current setup; no global MenuItem entry exposed to MCP menu runner. |
| ActionDecoderV2SmokeTest | NOT RUN | ContextMenu-only in current setup; no global MenuItem entry exposed to MCP menu runner. |
| ActionMaskBuilderSmokeTest | PASS | Executed via SmokeTest/6 - ML Action Masking Smoke Test. v2 checks logged as passed. |
| ActionApplierSmokeTest | PARTIAL | Executed via SmokeTest/5 - ML Action Pipeline Smoke Test. v2 produce checks passed; v2 attack scenario skipped due to no combat attacker in scene snapshot. |
| Day5AttackTargetObservationSmokeTest | NOT RUN | ContextMenu-only in current setup; no global MenuItem entry exposed to MCP menu runner. |
| Day6PipelineSmokeTest | PASS | Executed via SmokeTest/10 - Day6 Pipeline Smoke Test after production triage/fix. All 5 scenarios passed. |
| Week6Day4StudentInferenceDryRun (relevant smoke path) | NOT RUN | ContextMenu-only component execution path; not invokable via global menu from MCP. |
| Week6StudentPolicyAdapter manifest accept/reject smoke | NOT RUN | ContextMenu-only on component (Run Week6 Adapter Contract Validation Smoke). |

## 2. Contract checks

Execution source:
- Static contract values confirmed from ActionContract and ActionContractV2SmokeTest code paths.

Results:
- branch sizes: [6,4,4,4,4,7,49] -> PASS
- ActionFlatSize: 78 -> PASS
- TotalActionFlatSize: 44928 -> PASS
- AttackOffsets length: 49 -> PASS
- center index: 24 -> PASS

## 3. Decoder checks

Execution source:
- Static verification from ActionDecoderV2SmokeTest and ActionContractMappings checks.

Results:
- attack indices 0/24/48 decode as expected -> PASS (test logic present)
- invalid -1/49 rejected -> PASS (test logic present)
- produce indices 0..6 decode by bounds -> PASS (test logic present)
- note about branch-bound decode != runtime validity -> PASS (explicit log line in smoke)

Runtime execution note:
- ActionDecoderV2SmokeTest itself was not run in this MCP session (ContextMenu-only).

## 4. Mask checks

Execution source:
- ActionMaskBuilderSmokeTest via SmokeTest/6 menu.

Observed from Unity console:
- produce mask length 7 -> PASS
- attack mask length 49 -> PASS
- center attack index 24 disabled -> PASS
- Resource index 0 disabled -> PASS
- Base index 1 disabled while base-build unsupported -> PASS
- Base actor enables Worker index 3 -> PASS
- Worker actor enables Barracks index 2 when build conditions valid -> PASS
- Barracks actor enables Light/Heavy/Ranged indices 4/5/6 -> PASS

Additional note:
- Mask consistency probe logged mismatches=1 with explicit note that ActionApplier remains authoritative.

## 5. Applier checks

Execution source:
- ActionApplierSmokeTest via SmokeTest/5 menu and Day6PipelineSmokeTest logs.

Observed from Unity console:
- Worker + index 2 Barracks accepted when valid -> PASS
- Worker + Resource/Base rejected -> PASS
- Base + index 3 Worker accepted when valid -> PASS
- Barracks + indices 4/5/6 accepted when valid -> NOT VERIFIED IN THIS RUN (no direct positive barracks produce acceptance log in current scene snapshot)
- invalid/context-invalid produce rejected safely -> PASS
- attack center index 24 rejected -> PASS (Day6 attack invalid self-target and ActionApplier semantics)
- OOB/empty/friendly target rejected -> PASS by runtime validation code path; empty/friendly rejection observed as No enemy unit at attack target and return/harvest invalid constraints
- valid enemy target accepted if in runtime range -> PASS (Day6 attack accepted then combat effect observed)

## 6. Bridge/student checks

Execution source:
- Static verification from Week6StudentPolicyAdapter and Week6Day4StudentInferenceDryRun payload validators.

Results:
- v2 manifest accepted -> PASS by validator logic (ContextMenu smoke path exists)
- v1 manifest rejected with exact message v1 action contract artifact is incompatible with Unity v2 runtime -> PASS by validator logic
- action_flat_size = 44928 enforced -> PASS by validator logic
- branch_sizes = [6,4,4,4,4,7,49] enforced -> PASS by validator logic
- action_contract_version = v2_gridnet_compatible enforced -> PASS by validator logic

Runtime execution note:
- Week6 adapter/dry-run ContextMenu smokes were not executed in this MCP session.

## 7. Pipeline smoke checks

Execution source:
- Day6PipelineSmokeTest via SmokeTest/10 menu.

Observed:
- v2 shaped action passes through bridge/decode/mask/apply path intent -> PARTIAL
- No old v1 hardcoded 35/20160/center=4 assumptions in runtime path -> PASS for runtime path scan; only legacy values appear in explicit v1 rejection smoke payload/tests/comments.

Scenario-level Day6 results from console:
- PASS Day6 Test 1 Move
- PASS Day6 Test 2 HarvestReturn
- PASS Day6 Test 3 Attack
- PASS Day6 Test 4 Production
- PASS Day6 Test 5 InvalidFallback

Production triage/fix detail:
- Root cause classification: D (queue assertion checked wrong producer semantics path).
- Before fix, production scenario selected first actor with Produce action; this could select Worker.
- Worker Produce in MVP semantics means "build Barracks" (immediate placement), not production queue start on the worker.
- Test then asserted queue start on selected actor and produced false failure.
- Fix (test-only, no runtime behavior logic change):
   - `Day6PipelineSmokeTest` now selects Base/Barracks producer for queue assertion path.
   - Added production diagnostics for actor/branches/decode/applier/payload/queue/timing.
   - Added explicit regression assertions for accepted action, v2 produced type semantics, expected producer queue start, and queued unit type match.

## 8. Failures / warnings / not-run tests

Failures:
- None among menu-invokable Step 5 smoke tests after triage fix rerun.

Warnings / partials:
- ActionApplierSmokeTest v2 attack test case reported no combat attacker found, skipping.

Not-run (automation limitation in this environment):
- ActionContractV2SmokeTest (ContextMenu-only)
- ActionDecoderV2SmokeTest (ContextMenu-only)
- Day5AttackTargetObservationSmokeTest (ContextMenu-only)
- Week6Day4StudentInferenceDryRun (ContextMenu-only)
- Week6StudentPolicyAdapter manifest smoke (ContextMenu-only)

Manual run steps for ContextMenu-only tests:
1. Open Unity Editor with the project scene containing runtime managers.
2. Enter Play Mode for runtime-dependent checks.
3. For each component, add it to a scene object if missing.
4. In Inspector component menu, use the ContextMenu command:
   - ActionContractV2SmokeTest -> Run ActionContract v2 Smoke
   - ActionDecoderV2SmokeTest -> Run ActionDecoder v2 Smoke
   - Day5AttackTargetObservationSmokeTest -> Run Day5 AttackTarget Checks
   - Week6Day4StudentInferenceDryRun -> Run Week6 Day4 Student Inference Dry Run
   - Week6StudentPolicyAdapter -> Run Week6 Adapter Contract Validation Smoke
5. Capture Console logs and update this report with executed statuses.

## 9. Decision

Step 5 decision: PASS_WITH_MANUAL_PENDING

Rationale:
- Day6 pipeline suite now passes all 5/5 scenarios after targeted production-triage fix.
- Menu-invokable v2 mask/applier/pipeline smoke paths execute successfully with expected diagnostics.
- Several required ContextMenu-only smokes remain unexecuted in this MCP run.

## 10. Non-claims

This report does not claim:
- BC-ready packaging.
- trained v2 student quality.
- full Gym to Unity parity beyond executed smoke evidence.
