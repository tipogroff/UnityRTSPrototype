# PIPELINE_AUDIT_WEEK5_WEEK6.md

> STATUS: CURRENT CANONICAL

Generated: 2026-05-06
Scope: Week 5 / Week 6 pipeline, code, datasets, checkpoints, Unity bridge, and documentation inventory.
Method: repository scan, targeted file reads, contract grep audit, no long training or Unity autoruns.

## 1. Executive Summary

- Current canonical contract in active Unity + Week6 student path is v2: [6,4,4,4,4,7,49].
- Week5 teacher tooling is mixed: adapter supports v2, but two Day5/Day6 validators are still hardcoded to v1.
- Week6 student core modules (branch contract, loader, transfer architecture, inference adapter) are v2-aligned.
- Stage10D tree is predominantly diagnostic/audit/augmentation tooling, not a single canonical training entrypoint.
- Legacy032 lineage is active as a retained baseline and as current source lineage for many Week6 Stage10D artifacts.
- No evidence supports direct Gym->Unity semantic parity or direct full weight transfer; existing docs already contain explicit non-claims in key manifests/reports.

## 2. Current Canonical Pipeline

### Week 5 canonical (current practical path)

1. Teacher rollout/export: python/week5_teacher/run_teacher_rollout.py + teacher_export.py.
2. Adapter conversion to Unity-target format: python/week5_teacher/adapt_teacher_dataset.py with target-action-contract=v2_gridnet_compatible (required for current contract).
3. Validation and packaging:
   - Legacy canonical v2 lineage is currently centered around python/week5_teacher_legacy032/* tooling and manifests.
   - python/week5_teacher/validate_adapted_dataset.py and build_bc_ready_dataset_day6.py are not safe as v2 canonical without override/migration because of v1 constants.
4. BC-ready handoff to Week6 student.

### Week 6 canonical (current practical path)

1. Contracted loader path:
   - python/week6_student/student_bc_contract.py
   - python/week6_student/student_bc_loader.py
   - python/week6_student/inspect_bc_dataset.py
2. BC training path:
   - python/week6_student/train_student_bc_minimal.py (transfer variant preferred for active lineage)
   - architectures: student_architecture_transfer.py and student_bc_model_minimal.py
3. Inference bridge path:
   - python/week6_student/student_inference_adapter.py
   - python/week6_student/load_student_checkpoint.py
   - Unity C# bridge: Week6StudentPolicyAdapter.cs -> MlPolicyPipelineFacade.cs -> ActionDecoder.cs -> ActionApplier.cs.
4. Stage10D: diagnostic, remediation, augmentation, checkpoint-binding, runtime mismatch analysis.

## 3. Current Canonical Files

- Python contract/loader core:
  - python/week6_student/student_branch_contract.py
  - python/week6_student/student_bc_contract.py
  - python/week6_student/student_bc_loader.py
  - python/week6_student/student_architecture_transfer.py
  - python/week6_student/student_inference_adapter.py
  - python/week6_student/load_student_checkpoint.py
- Unity contract/runtime core:
  - Assets/Scripts/ML/ActionContract.cs
  - Assets/Scripts/ML/ObservationContract.cs
  - Assets/Scripts/ML/ActionDecoder.cs
  - Assets/Scripts/ML/ActionApplier.cs
  - Assets/Scripts/ML/ActionMaskBuilder.cs
  - Assets/Scripts/ML/MlPolicyPipelineFacade.cs
  - Assets/Scripts/ML/Week6StudentPolicyAdapter.cs

## 4. Current Canonical Datasets/Checkpoints

Primary dataset lineage currently used in Week6 Stage10D and remediation path:

- python/week5_teacher_legacy032/teacher_exports_bc/day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z
  - branch_sizes: [6,4,4,4,4,7,49]
  - split counts: train 74940, validation 13225, debug 512

Derived Week6 BC-ready augmentation lineages:

- python/week6_student/bc_ready/legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z
- python/week6_student/bc_ready/legacy032_3m_unity_v2_stage10d14_unity_like_augmented_bc_ready_20260503T145301Z
- python/week6_student/bc_ready/legacy032_v2_stage10d17_movement_augmented_bc_ready_20260503T162905Z
- python/week6_student/bc_ready/legacy032_v2_stage10d19b_valid_move_augmented_bc_ready_20260503T191829Z
- python/week6_student/bc_ready/legacy032_v2_stage10d19c_mask_aware_failure_augmented_bc_ready_20260503T200935Z

Observed active checkpoints in Week6 runs include semantic/augmented students (stage10d8, stage10d14, stage10d17, stage10d19b/c).

## 5. Historical Baselines Retained

Keep for dissertation traceability (do not delete):

- WEEK5/ old v1-era baseline summaries and comparisons.
- WEEK5R migration/smoke reports.
- python/week5_teacher_reference/ reproduction stack and reports.
- python/week5_teacher_gridnet/ sweep scripts and WEEK5R outputs.
- python/week5_teacher_legacy032 reports and staged run evidence.
- runs/ historical training directories.

## 6. Deprecated / Do-Not-Use As Current

- python/week5_teacher/validate_adapted_dataset.py (hardcoded EXPECTED_ACTION_BRANCH_SIZES = v1).
- python/week5_teacher/build_bc_ready_dataset_day6.py (hardcoded EXPECTED_BRANCH_SIZES = v1).
- WEEK6/DAY2_STUDENT_INPUT_SOURCE.md content block that declares old Week5 non-legacy path as current canonical Day2 source.
- Any v1 branch-size claim as current in active instructions.

## 7. Diagnostic-Only Files

- Stage10D*.py scripts under python/week6_student are primarily diagnostic/remediation/audit/report builders.
- Unity visual/smoke runners are diagnostic harnesses, not production runtime policy orchestration:
  - Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs
  - Assets/Scripts/ML/Week6VisualInspectionRunner.cs
  - ActionContractV2 smoke components.

## 8. Contract Version Matrix

| Component | Observation contract | Action contract | Status |
|---|---|---|---|
| Unity runtime core (ActionContract/Decoder/Applier/MaskBuilder) | [24,24,27] | [6,4,4,4,4,7,49] | current |
| Week6 student branch contract | expects [24,24,27] spatial input | [6,4,4,4,4,7,49] | current |
| Week5 adapter (adapt_teacher_dataset.py) | target [24,24,27] | supports v1 and v2; default v1 | mixed |
| Week5 validator (validate_adapted_dataset.py) | [24,24,27] | hardcoded [6,4,4,4,4,4,9] | deprecated for v2 |
| Week5 BC packager (build_bc_ready_dataset_day6.py) | [24,24,27] | hardcoded [6,4,4,4,4,4,9] | deprecated for v2 |
| Legacy032 v2 manifests | [576,27] per-sample flat cell-major | [6,4,4,4,4,7,49] | current lineage artifact |

Action flat size verification:
- Per cell: 6+4+4+4+4+7+49 = 78.
- Total: 576 * 78 = 44928.

Model/logits contract verification:
- action_type: [B,576,6]
- move_dir: [B,576,4]
- harvest_dir: [B,576,4]
- return_dir: [B,576,4]
- produce_dir: [B,576,4]
- produce_unit_type: [B,576,7]
- attack_target_local: [B,576,49]

## 9. Documentation Status Matrix

| Area | Currentness | Notes |
|---|---|---|
| IMPLEMENTATION_PLAN.md | mostly current | states v2 current contract and transfer caveats |
| DOCUMENTATION_SYNC_REPORT.md | current snapshot | already records mixed v1/v2 strata and migration TODOs |
| WEEK5 docs | mixed historical/current | several files are v1-baseline heavy; require explicit status banners |
| WEEK5R docs | largely historical migration evidence | keep for traceability |
| WEEK6 docs | mixed | core day1/day3/day4 docs largely v2; Day2 input-source file is stale/historical |
| python/week5_teacher/README.md | mixed but mostly current narrative | still references v1-era baseline artifacts as preferred historical entries |
| python/week5_teacher_reference docs | historical baseline/repro | keep |
| python/week6_student/reports | diagnostic/historical evidence | not canonical runbook |

## 10. Known Risks And Unresolved Decisions

- Unresolved whether to formally retire python/week5_teacher Day5/Day6 v1 validator/packager scripts or migrate them to v2 and keep as active path.
- Multiple checkpoint defaults are pinned in diagnostics and Unity runner fields; selection can silently drift if not governed by one canonical registry doc.
- Stage10D dataset augmentation chain is deep; risk of confusion over which dataset is canonical for training vs diagnostics.
- Observation semantic parity between gym lineage and Unity runtime remains unproven by design.
- Mask semantics remain pre-sampling diagnostic layer, not runtime truth.

## 11. Recommended Cleanup Plan

1. Freeze canonical lineage pointers in one authoritative runbook (dataset + checkpoint + adapter mode).
2. Mark v1-hardcoded Week5 validator/packager as deprecated in-file (or migrate and add explicit version switch defaulting to v2).
3. Keep Stage10D scripts but tag as diagnostic-only by convention in a top-level Week6 index doc.
4. Normalize Unity diagnostic runner defaults to a clearly labeled active checkpoint family.
5. Add explicit "historical baseline" banners to remaining v1-era docs that still appear operational.

## 12. Safe Next Steps

- No architecture rewrite required now.
- Perform documentation-first alignment:
  - resolve stale "current canonical" references to old v1 paths,
  - preserve all historical artifacts,
  - enforce status banners.
- Then run lightweight contract smoke checks only (already done here via grep and static read).

---

## A. Repository-Level Area Audit

| area | purpose | currentness | pipeline stage | used now | should be referenced by |
|---|---|---|---|---|---|
| WEEK5/ | Week5 teacher planning, run records, baseline decisions | mixed (historical-heavy) | teacher rollout/adapter/packaging docs | partly | PIPELINE_AUDIT_WEEK5_WEEK6.md, Week5 index docs |
| WEEK5R/ | retraining/migration/sweeps/output reports | historical + diagnostic | migration and experiment evidence | yes (as evidence) | migration notes, dissertation traceability docs |
| WEEK6/ | Week6 BC/inference integration docs | mixed; mostly current with some stale day2 pin | BC + Unity bridge | yes | current pipeline runbook, this audit |
| python/week5_teacher/ | main Week5 teacher scripts (v0.6.1 era) | mixed | teacher rollout/adapter/validation/packaging | partly | python/week5_teacher/README.md, Week5 docs |
| python/week5_teacher_gridnet/ | gridnet experiments/sweeps | historical/diagnostic | alternative teacher experiments | optional | WEEK5R gridnet plans/reports |
| python/week5_teacher_reference/ | reference reproduction (legacy stack) | historical baseline keep | baseline reproducibility | optional | reference reproduction docs |
| python/week6_student/ | student BC + Stage10D diagnostics | current core + large diagnostic subtree | student BC, inference adapter, stage10d diagnostics | yes | WEEK6 docs, stage reports, this audit |
| Assets/Scripts/ML/ | Unity ML contract, decode/apply/mask/bridge/runners | current runtime core + diagnostic runners | Unity inference/diagnostics | yes | IMPLEMENTATION_PLAN.md, WEEK6 docs |
| Assets/Scripts/Gameplay/ | gameplay runtime systems | current runtime substrate | authoritative command application context | yes | gameplay architecture docs |
| runs/ | historical training run outputs | historical baseline keep | experimental evidence | yes | dissertation traceability docs |
| root docs (CONTEXT, IMPLEMENTATION_PLAN, DOCUMENTATION_SYNC_REPORT, TLDR, migration notes) | project-level orientation and migration state | mostly current but partly historical notes | all stages | yes | top-level onboarding + canonical audit |

## B. Script Inventory

| path | area | role | status | contract version | inputs | outputs | notes | action required |
|---|---|---|---|---|---|---|---|---|
| python/week5_teacher/run_teacher_rollout.py | Week5 | entrypoint rollout/export | historical baseline keep | source gym layouts; no fixed v2 target | env, checkpoint/policy | teacher_rollouts + logs | export-stage source collector | keep, label historical baseline in runbooks |
| python/week5_teacher/teacher_export.py | Week5 | helper library | historical baseline keep | source-layer helper | rollout records | npz/jsonl validation helpers | utility module | keep |
| python/week5_teacher/adapt_teacher_dataset.py | Week5 | entrypoint adapter | current with caveat | supports v1 and v2; default v1 | Day3 rollout batch | adapted batch + conversion report | must pass target-action-contract=v2_gridnet_compatible for current path | set explicit v2 in canonical commands |
| python/week5_teacher/day4_dataset_adapter.py | Week5 | helper core adapter | current | v1/v2 selectable | raw rollout | adapted tensors/reports | core conversion logic | keep |
| python/week5_teacher/validate_adapted_dataset.py | Week5 | entrypoint validator | deprecated for current v2 | hardcoded v1 | adapted batch | strict/quality reports | v1 contract constant | migrate or mark deprecated strongly |
| python/week5_teacher/build_bc_ready_dataset_day6.py | Week5 | entrypoint packager | deprecated for current v2 | hardcoded v1 | adapted batch | bc_manifest + splits | v1 contract constant | migrate or mark deprecated strongly |
| python/week5_teacher/dry_run_bc_loader.py | Week5 | entrypoint dry-run validator | historical baseline keep | follows packaged manifest | bc_ready dir | dry_run report | useful generic checker | keep |
| python/week5_teacher/train_teacher_smoke.py | Week5 | entrypoint smoke trainer | historical baseline keep | training-side, not v2 handoff proof | env, profile | checkpoints/logs | teacher training smoke | keep as historical/diagnostic |
| python/week5_teacher/resume_training.py | Week5 | entrypoint resume trainer | historical baseline keep | training-side | checkpoint + env | resumed checkpoints | not canonical handoff path | keep |
| python/week5_teacher/evaluate_teacher_actor_level.py | Week5 | entrypoint diagnostic eval | diagnostic-only | actor-level behavior eval | checkpoint | WEEK6 eval json/md | writes into WEEK6 paths | keep diagnostic-only |
| python/week5_teacher/evaluate_teacher_checkpoint.py | Week5 | entrypoint checkpoint eval | diagnostic-only | rollout/eval contract | checkpoint | summary json/md | behavior summary tool | keep diagnostic-only |
| python/week5_teacher/render_teacher_checkpoint_replay.py | Week5 | entrypoint replay renderer | diagnostic-only | replay diagnostics | checkpoint | replay traces/reports | not packaging path | keep diagnostic-only |
| python/week5_teacher_gridnet/train_teacher_gridnet_project.py | Week5 gridnet | entrypoint trainer | historical baseline keep | gridnet-style | config/checkpoints | WEEK5R gridnet runs | alternative branch | keep historical |
| python/week5_teacher_gridnet/run_gridnet_reference_parity_sweep.py | Week5 gridnet | entrypoint sweep | diagnostic-only | parity sweep logic | configs | WEEK5R parity reports | hardcoded sweep roots in WEEK5R | keep diagnostic-only |
| python/week5_teacher_gridnet/run_gridnet_recipe_redesign_sweep.py | Week5 gridnet | entrypoint sweep | diagnostic-only | recipe sweep logic | configs | WEEK5R recipe reports | hardcoded WEEK5R roots | keep diagnostic-only |
| python/week5_teacher_reference/scripts/run_reference_training_smoke.ps1 | Week5 reference | entrypoint reference smoke | historical baseline keep | legacy reference | reference env | reference artifacts | reproduction path | keep |
| python/week5_teacher_reference/scripts/run_reference_training_long.ps1 | Week5 reference | entrypoint long reference | historical baseline keep | legacy reference | reference env | long-run artifacts | reproduction path | keep |
| python/week6_student/student_branch_contract.py | Week6 | contract source | current | v2 [6,4,4,4,4,7,49] | none | constants/spec tables | authoritative branch spec | keep canonical |
| python/week6_student/student_bc_contract.py | Week6 | contract dataclasses | current | manifest-driven; v2 ready | manifest/splits | typed contract objects | no v1 lock | keep canonical |
| python/week6_student/student_bc_loader.py | Week6 | loader entrypoint/helper | current | manifest-driven; v2 compatible | bc_ready dir | LoadedBCDataset | strict fail-fast | keep canonical |
| python/week6_student/inspect_bc_dataset.py | Week6 | entrypoint inspector | current | reads manifest contract | bc_ready dir | inspection summary | diagnostic but canonical tooling | keep |
| python/week6_student/train_student_bc_minimal.py | Week6 | entrypoint trainer | current | expects v2 manifest checks | bc_ready dataset | checkpoints + histories | pinned to legacy032 v2 path now | keep canonical |
| python/week6_student/student_bc_model_minimal.py | Week6 | model helper | current (smoke model) | v2 heads 7/49 | tensors | logits dict | now v2-correct | keep with caution note |
| python/week6_student/student_architecture_transfer.py | Week6 | model architecture core | current | v2 heads from BRANCH_SPECS | tensors | logits dict | transfer-capable architecture | keep canonical |
| python/week6_student/partial_transfer_strategy.py | Week6 | transfer policy helper | current | v2-aligned mapping | branch specs | transfer rule tables | honesty-first non-claim rules | keep |
| python/week6_student/student_inference_adapter.py | Week6 | entrypoint inference bridge | current | v2 branch checks, action_flat 44928 | checkpoint + obs bin | json with logits/actions | canonical Python adapter to Unity | keep canonical |
| python/week6_student/load_student_checkpoint.py | Week6 | checkpoint loader helper | current | strict transfer model load | checkpoint | model + metadata | strict state dict check | keep canonical |
| python/week6_student/stage10d*.py | Week6 Stage10D | many entrypoints | diagnostic-only (overall) | mostly v2 constants + audits | reports/datasets/checkpoints | reports, augmented datasets, eval artifacts | large remediation tree, not single canonical trainer | keep, tag as diagnostic suite |
| Assets/Scripts/ML/ActionContract.cs | Unity ML | runtime contract source | current | v2 [6,4,4,4,4,7,49] | constants | contract API | ActionFlatSize 78, total 44928 | keep canonical |
| Assets/Scripts/ML/ObservationContract.cs | Unity ML | runtime observation source | current with noted asymmetry | [24,24,27], total 15552 | constants | contract API | produce observation channels still 4 (by observation design) | keep; document asymmetry |
| Assets/Scripts/ML/ActionDecoder.cs | Unity ML | runtime decode core | current | v2 branch decode | action_flat | AgentAction list | attack/prod branches use 49/7 | keep canonical |
| Assets/Scripts/ML/ActionApplier.cs | Unity ML | runtime authoritative apply | current | runtime semantics | AgentAction | MatchManager command submissions | authoritative truth layer | keep canonical |
| Assets/Scripts/ML/ActionMaskBuilder.cs | Unity ML | pre-sampling mask builder | current diagnostic layer | v2 mask shapes | runtime state | ActionMaskSet | not authoritative truth | keep canonical |
| Assets/Scripts/ML/MlPolicyPipelineFacade.cs | Unity ML | pipeline facade | current | depends on v2 internals | observations/actions/masks | execution report | core bridge entry | keep canonical |
| Assets/Scripts/ML/Week6StudentPolicyAdapter.cs | Unity ML | student runtime bridge | current + config-sensitive | expects v2 checkpoint family | Unity obs + checkpoint path | adapter artifacts + commands | has serialized checkpoint defaults | keep; maintain default path registry |
| Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs | Unity ML | dry-run component | diagnostic-only | checks v2 and checkpoint filename | scene runtime + adapter call | smoke report | hardcoded checkpoint relative default | keep diagnostic-only |
| Assets/Scripts/ML/Week6VisualInspectionRunner.cs | Unity ML | visual diagnostic component | diagnostic-only | stage10r visual diagnostics | scene runtime + adapter snapshots | reports/snapshots | rich debug telemetry, not production loop | keep diagnostic-only |

## C. Documentation Inventory

| path | status | topic | currentness | conflicts | action required |
|---|---|---|---|---|---|
| CONTEXT.md | current canonical | global project context | current | none critical | keep |
| IMPLEMENTATION_PLAN.md | current canonical | roadmap + current status | current | none critical | keep |
| DOCUMENTATION_SYNC_REPORT.md | current canonical snapshot | doc/code sync record | current | notes mixed v1/v2 tooling | keep |
| WEEK5/WEEK5_TEACHER_PIPELINE_SUMMARY.md | historical baseline | Week5 closeout | stale as current | points to old week5 non-legacy preferred lineage | banner added; avoid as canonical now |
| WEEK5/WEEK5_TEACHER_PIPELINE_SPEC.md | historical baseline keep | day1 teacher contract | mostly historical | includes v1-era assumptions | keep historical |
| WEEK5/PREFERRED_TEACHER_BASELINE_UPDATE.md | historical baseline keep | baseline switch record | historical | v1-era branch comparisons | keep historical |
| WEEK5/BC_READY_DATASET_DAY6.md | historical baseline keep | day6 package notes | historical | v1 branch expectations | keep historical |
| WEEK5R/UNITY_ACTION_CONTRACT_V2_MIGRATION_PLAN.md | historical baseline keep | migration plan | historical | superseded by implemented v2 | banner added |
| WEEK5R/GRIDNET_ACTION_CONTRACT_V2_MIGRATION_PLAN.md | historical baseline keep | gridnet migration planning | historical | planning vs current runtime | mark historical if reused |
| WEEK6/WEEK6_DAY1_BC_TRAINING_CONTRACT.md | current canonical | week6 BC contract | current | none significant | banner added |
| WEEK6/WEEK6_DAY3_STUDENT_ARCHITECTURE_AND_TRANSFER.md | current canonical | architecture/transfer | current | none significant | keep |
| WEEK6/WEEK6_DAY4_STUDENT_INFERENCE_DRYRUN.md | diagnostic-supporting | dry-run wiring | mostly current | checkpoint lineage references can stale | keep with checkpoint update note |
| WEEK6/DAY2_STUDENT_INPUT_SOURCE.md | historical baseline | day2 pinned source | stale as current | declares old week5 path as canonical while file itself says historical | banner added; replace with current source note |
| python/week5_teacher/README.md | mixed | week5 tooling + notes | mixed | includes historical preferred runs | add clearer split current vs historical section in follow-up |
| python/week5_teacher_reference/*.md | historical baseline keep | reference reproduction | historical | none | keep |
| python/week6_student/reports/*.md | diagnostic-only | stage reports/evidence | historical/diagnostic | not canonical runbook | keep, do not treat as current spec |
| PIPELINE_AUDIT_WEEK5_WEEK6.md | current canonical | audit matrix | current | none | keep as top-level pointer |

## D. Dataset / Checkpoint Inventory

| path | status | source lineage | contract | sample count if available | used by | keep/delete decision | notes |
|---|---|---|---|---|---|---|---|
| python/week5_teacher_legacy032/teacher_exports_bc/day6_bc_ready_legacy032_3m_unity_v2_20260501T164317Z | current canonical source lineage | legacy032 gym_microrts==0.3.2 | v2 [6,4,4,4,4,7,49] | train 74940, val 13225, debug 512 | week6 loader/train/stage10d | keep | primary handoff dataset for active legacy032-v2 path |
| python/week6_student/bc_ready/legacy032_3m_unity_v2_semantic_bc_ready_stage10d7_20260503T090659Z | current derived | stage10d6 semantic adapted | v2 | train 79348, val 8817, debug 1024 | stage10d8+ training | keep | semantic rebuild path |
| python/week6_student/bc_ready/legacy032_3m_unity_v2_stage10d14_unity_like_augmented_bc_ready_20260503T145301Z | current derived | stage10d14 augmentation | v2 | in manifest | stage10d14+ | keep | augmentation branch |
| python/week6_student/bc_ready/legacy032_v2_stage10d17_movement_augmented_bc_ready_20260503T162905Z | current derived | stage10d17 movement augment | v2 | in manifest | stage10d17+ | keep | movement-focused augmentation |
| python/week6_student/bc_ready/legacy032_v2_stage10d19b_valid_move_augmented_bc_ready_20260503T191829Z | current derived | stage10d19b | v2 | in manifest | stage10d19b/c | keep | valid-move remediation |
| python/week6_student/bc_ready/legacy032_v2_stage10d19c_mask_aware_failure_augmented_bc_ready_20260503T200935Z | current derived | stage10d19c | v2 | in manifest | mask-aware training/eval | keep | mask-aware failure augmentation |
| python/week6_student/runs/legacy032_v2_semantic_bc_stage10d8_20260503T093718Z | current checkpoint family | stage10d8 training | v2 heads | n/a | stage10d9+ diagnostics | keep | includes student_bc_semantic_best.pt |
| python/week6_student/runs/legacy032_v2_stage10d19c_mask_aware_failure_augmented_bc_20260503T202258Z | current checkpoint family | stage10d19c training | v2 heads | n/a | stage10d19c+ diagnostics | keep | includes student_bc_stage10d19c_mask_aware_best.pt |
| python/week6_student/runs/day3_transfer_bc_main_20260423 | historical baseline keep | early week6 transfer run | likely v2 heads but old dataset lineage | n/a | old dry-runs/docs | keep | do not treat as canonical current checkpoint |
| python/week5_teacher/teacher_exports_bc/day6_bc_ready_teacher_adapted_day5_hardened_v2_teacher_candidate_corrective_sl2000_ep8_cpu_20260422T085809Z | historical baseline keep | week5 non-legacy path | v1-era package expectations | in docs | historical week6 day2 docs | keep | retained for comparison/dissertation |
| runs/MicrortsDefeatCoacAIShaped-v3__* | historical training outputs | multiple legacy032 stages | mixed | n/a | audit/evidence | keep | do not delete without archival policy |

## E. Contract Mismatch Table

| file | observed contract | expected current contract | mismatch type | severity | fix recommendation |
|---|---|---|---|---|---|
| python/week5_teacher/validate_adapted_dataset.py | EXPECTED_ACTION_BRANCH_SIZES=(6,4,4,4,4,4,9) | [6,4,4,4,4,7,49] | hardcoded v1 in validator | high | migrate constants + checks for v2, or mark deprecated and stop using for current runs |
| python/week5_teacher/build_bc_ready_dataset_day6.py | EXPECTED_BRANCH_SIZES=(6,4,4,4,4,4,9) | [6,4,4,4,4,7,49] | hardcoded v1 in packager | high | migrate constants + manifest labels for v2, or mark deprecated |
| python/week5_teacher/adapt_teacher_dataset.py | default target-action-contract=v1_mvp | v2 default for current path | default-mode drift | medium | change canonical commands to explicit v2; optionally change default |
| WEEK6/DAY2_STUDENT_INPUT_SOURCE.md | labels old Week5 path as current canonical and lists v1 branch sizes | legacy032 v2 lineage currently used | doc currentness conflict | high | keep as historical with banner; add replacement current-source doc |
| WEEK5/WEEK5_TEACHER_PIPELINE_SUMMARY.md | presents Week5 non-legacy path as canonical handoff | active lineage now legacy032 v2 + stage10d derivatives | doc lineage drift | medium | mark historical baseline; point to audit doc for current canonical path |
| Assets/Scripts/ML/Week6Day4StudentInferenceDryRun.cs | serialized default checkpoint path pinned to specific run family | canonical checkpoint should be centrally governed | config pinning/hardcoded run path | medium | maintain explicit registry doc and update inspector default when canonical checkpoint changes |
| Assets/Scripts/ML/ObservationContract.cs | CH_PRODUCE_COUNT=4 observation channels vs action produce branch size 7 | v2 action branch has produce size 7 | representational asymmetry (not necessarily bug) | low | document clearly as observation-vs-action semantic difference; avoid parity claim |
