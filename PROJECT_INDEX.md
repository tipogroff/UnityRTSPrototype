# PROJECT INDEX — UnityRTSPrototype

**Last updated:** 2026-05-10  
**Current canonical baseline:** Stage6B3_StaticHarvest_MaskedPolicy_FirstSuccessfulPipeline — **GO**

> Этот файл — навигационный индекс проекта. Документы не перемещались.  
> Статусы: `[CURRENT]` — активный, `[HISTORICAL]` — исторический, `[DEPRECATED]` — устаревший, `[FROZEN]` — зафиксирован как baseline.

---

## Текущий канонический пайплайн

| Документ | Статус | Описание |
|---|---|---|
| [CURRENT_PIPELINE_RUNBOOK.md](CURRENT_PIPELINE_RUNBOOK.md) | **[CURRENT]** | Главный runbook — как запустить Stage6B3 |
| [FIRST_SUCCESSFUL_PIPELINE_BASELINE.md](FIRST_SUCCESSFUL_PIPELINE_BASELINE.md) | **[FROZEN]** | Frozen runtime config, evidence, no-regression checklist |
| [STAGE6B3_SUCCESSFUL_PIPELINE_ARTIFACT_INDEX.md](STAGE6B3_SUCCESSFUL_PIPELINE_ARTIFACT_INDEX.md) | **[FROZEN]** | Полный индекс artifact lineage для baseline |
| [PROJECT_SAFE_CLEANUP_AUDIT.md](PROJECT_SAFE_CLEANUP_AUDIT.md) | **[CURRENT]** | Аудит чистки — предложения без изменений |
| [SAFE_CLEANUP_POLICY.md](SAFE_CLEANUP_POLICY.md) | **[CURRENT]** | Политика и правила безопасной чистки |

### Финальные артефакты baseline (НЕ ТРОГАТЬ)

| Тип | Путь |
|---|---|
| Unity scene | `Assets/Scenes/Week6_StudentStaticHarvestLayout.unity` |
| Bootstrap script | `Assets/Scripts/ML/Week6Stage6B3StaticManualPlayBootstrap.cs` |
| Checkpoint | `python/week6_student/checkpoints/Stage6B3_SemanticObservationFix/legacy032_v2_bc_source_valid_semantic_obs_fix_final.pt` |
| Canonical dataset | `python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_source_valid_semantic_obs_fix_bc_ready_20260507T085607Z/` |

---

## Исторические спринт-документы

> Все документы на своих оригинальных местах. Не перемещены.

| Sprint | Путь | Статус |
|---|---|---|
| Week 1 | [WEEK1/](WEEK1/) | [HISTORICAL] |
| Week 2 | [WEEK2/](WEEK2/) | [HISTORICAL] |
| Week 3 | [WEEK3/](WEEK3/) | [HISTORICAL] |
| Week 4 | [WEEK4/](WEEK4/) | [HISTORICAL] |
| Week 4 Reports | [WEEK4_Reports/](WEEK4_Reports/) | [HISTORICAL] |
| Week 5 | [WEEK5/](WEEK5/) | [HISTORICAL] |
| Week 5R (canonical teacher runs) | [WEEK5R/](WEEK5R/) | [HISTORICAL] |
| Week 6 | [WEEK6/](WEEK6/) | [HISTORICAL] |
| Docs archive | [docs/](docs/) | [HISTORICAL] |

### Ключевые отчёты недель 5-6

| Документ | Статус |
|---|---|
| [UNIFIED_WEEK3_WEEK4_SUMMARY.md](UNIFIED_WEEK3_WEEK4_SUMMARY.md) | [HISTORICAL] |
| [PIPELINE_AUDIT_WEEK5_WEEK6.md](PIPELINE_AUDIT_WEEK5_WEEK6.md) | [HISTORICAL] |
| [MIGRATION_NOTE_27_TO_29.md](MIGRATION_NOTE_27_TO_29.md) | [HISTORICAL] |
| [TLDR_BOTH_WEEKS_COMPLETE.md](TLDR_BOTH_WEEKS_COMPLETE.md) | [HISTORICAL] |
| [MLAGENTS_STUDENT_RUNTIME_CONTRACT.md](MLAGENTS_STUDENT_RUNTIME_CONTRACT.md) | [HISTORICAL] |
| [SMOKETEST_GUIDE.md](SMOKETEST_GUIDE.md) | [HISTORICAL] |
| [CONTEXT.md](CONTEXT.md) | [HISTORICAL] |
| [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) | [HISTORICAL] |
| [DOCUMENTATION_SYNC_REPORT.md](DOCUMENTATION_SYNC_REPORT.md) | [HISTORICAL] |

---

## Teacher pipelines

| Pipeline | Путь | Статус |
|---|---|---|
| Week5 Teacher (main) | [python/week5_teacher/](python/week5_teacher/) | [HISTORICAL] |
| Week5 Teacher GridNet | [python/week5_teacher_gridnet/](python/week5_teacher_gridnet/) | [HISTORICAL] |
| Week5 Teacher Reference | [python/week5_teacher_reference/](python/week5_teacher_reference/) | [HISTORICAL] |
| Week5 Teacher Legacy032 | [python/week5_teacher_legacy032/](python/week5_teacher_legacy032/) | **[ACTIVE lineage]** — Canonical training source |
| Stage7B Teacher Conversion | [python/stage7b_teacher_conversion/](python/stage7b_teacher_conversion/) | [HISTORICAL] |

### Legacy032 ключевые файлы

| Файл | Роль |
|---|---|
| `python/week5_teacher_legacy032/semantic_observation_adapter_legacy032_to_unity_v2.py` | Semantic adapter — canonical |
| `python/week5_teacher_legacy032/ENVIRONMENT_LEGACY032.md` | Environment spec |
| `python/week5_teacher_legacy032/README.md` | Pipeline README |
| `python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_source_valid_semantic_obs_fix_bc_ready_*/` | **CANONICAL BC DATASET** |

---

## Student pipeline

| Компонент | Путь | Статус |
|---|---|---|
| Core scripts | [python/week6_student/](python/week6_student/) | **[CURRENT]** |
| BC Training | `python/week6_student/run_bc_training_student.py` | [CURRENT] |
| Inference server | `python/week6_student/student_inference_server.py` | [CURRENT] |
| Checkpoints | `python/week6_student/checkpoints/` | **[PROTECTED]** |
| Reports (Stage10D) | `python/week6_student/reports/` | [HISTORICAL] |
| BC-ready datasets | `python/week6_student/bc_ready/` | [HISTORICAL] |
| Training runs | `python/week6_student/runs/` | [HISTORICAL] |

---

## Diagnostic reports

| Stage | Путь/документ | Статус |
|---|---|---|
| Stage6B3 playmode freeze | [STAGE6B3_PLAYMODE_PERFORMANCE_DIAGNOSTIC_REPORT.md](STAGE6B3_PLAYMODE_PERFORMANCE_DIAGNOSTIC_REPORT.md) | [HISTORICAL] |
| Stage6B3 soft idle | [STAGE6B3_STATIC_SOFT_IDLE_DIAGNOSTIC_REPORT.md](STAGE6B3_STATIC_SOFT_IDLE_DIAGNOSTIC_REPORT.md) | [HISTORICAL] |
| Stage6B3 playmode stop | [STAGE6B3_STATIC_PLAYMODE_STOP_DIAGNOSTIC_REPORT.md](STAGE6B3_STATIC_PLAYMODE_STOP_DIAGNOSTIC_REPORT.md) | [HISTORICAL] |
| Stage6B3 scripted bot idle | [STAGE6B3_SCRIPTED_BOT_SOFT_IDLE_DIAGNOSTIC_REPORT.md](STAGE6B3_SCRIPTED_BOT_SOFT_IDLE_DIAGNOSTIC_REPORT.md) | [HISTORICAL] |
| Stage7B candidate contract | [stage7b_candidate_action_contract.md](stage7b_candidate_action_contract.md) | [HISTORICAL] |
| Stage7B heuristic dryrun | [stage7b_mlagents_heuristic_dryrun.json](stage7b_mlagents_heuristic_dryrun.json) | [HISTORICAL] |
| Stage6B3 perf summary | [stage6b3_playmode_performance_summary.json](stage6b3_playmode_performance_summary.json) | [HISTORICAL] |
| Stage10D (all) | `python/week6_student/reports/stage10d*/` | [HISTORICAL] |

---

## Unity scenes

| Scene | Путь | Статус |
|---|---|---|
| **Canonical baseline** | `Assets/Scenes/Week6_StudentStaticHarvestLayout.unity` | **[PROTECTED / CURRENT]** |
| Game Scene (legacy) | `Assets/Scenes/GameScene.unity` | [HISTORICAL] |
| Harvest Layout (dev) | `Assets/Scenes/HarvestLayout.unity` | [HISTORICAL] |

---

## Validation artifacts

| Тип | Путь | Статус |
|---|---|---|
| Gate runs (WEEK5R) | `docs/archive/WEEK5R/gate_runs/` | [HISTORICAL] |
| GridNet sweeps | `docs/archive/WEEK5R/gridnet_*` | [HISTORICAL] |
| BC ready datasets | `python/week5_teacher_legacy032/teacher_exports_bc/` | **[ACTIVE lineage]** |
| Adapted datasets | `python/week5_teacher_legacy032/teacher_adapted/` | [HISTORICAL] |
| Teacher exports | `python/week5_teacher_legacy032/teacher_exports/` | [HISTORICAL] |
| Visual episode captures | `python/week5_teacher_legacy032/reports/*_visual_single_episode/` | [HISTORICAL] |
| TensorBoard runs | `runs/` | [HISTORICAL] |

---

## Кандидаты на cleanup (без автоматического удаления)

Подробный аудит: [PROJECT_SAFE_CLEANUP_AUDIT.md](PROJECT_SAFE_CLEANUP_AUDIT.md)  
Политика: [SAFE_CLEANUP_POLICY.md](SAFE_CLEANUP_POLICY.md)

**Только после явного подтверждения:**
1. `__pycache__/` директории (~2 MB)
2. `Temp/`, `Logs/` (Unity generated, ~0.5 MB)
3. `_unity_batch_stage6b3_semantic_obs_fix/` (orphan project, ~2.75 GB)
4. `python/week5_teacher/.venv_day2_py39/` (historical venv, ~7.2 GB)
5. `python/week5_teacher_reference/.venv_microrts032_reference/` (ref env, ~1.4 GB)
6. `Library/` (Unity cache, ~2.07 GB — regenerated automatically)
