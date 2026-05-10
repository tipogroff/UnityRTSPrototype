# SAFE_CLEANUP_POLICY.md

**Date:** 2026-05-10  
**Version:** 1.0  
**Scope:** UnityRTSPrototype дипломный проект

---

## Цель

Этот документ определяет политику безопасной чистки проекта, сохраняя:
- рабочий Stage6B3 baseline (первый успешный pipeline);
- полную историю исследований для диссертации (глава 3);
- трассируемость всех решений через артефакты.

---

## Абсолютные запреты (без исключений)

Никогда не выполнять автоматически:

| Что | Почему |
|---|---|
| `git rm` / `Remove-Item` для `*.pt`, `*.npz`, `*.onnx` | Checkpoint и dataset lineage — irreversible |
| `git mv` / перемещение WEEK1-WEEK6 | Исторические sprint docs для диссертации |
| Удаление `*.md`, `*.json`, `*.jsonl` | Отчёты, validation artifacts, pipeline contracts |
| Удаление `teacher_exports*`, `teacher_rollouts*`, `bc_ready*`, `checkpoints/` | Dataset и checkpoint lineage |
| Изменение `Assets/Scripts/ML/` | Active runtime — Stage6B3 baseline зависит |
| Изменение `Assets/Scenes/Week6_StudentStaticHarvestLayout.unity` | Финальная сцена |
| Изменение `python/week6_student/` core scripts | Student inference contract |
| Retraining, dataset rebuild, PPO | Может сломать baseline |
| Массовый `git mv` / архивирование | Нарушает историческую трассируемость |
| Добавление в `.gitignore` patterns для `*.md`, `*.py`, `*.cs`, `*.json` | Скроет tracked artifacts |

---

## Что разрешено без approve

- Чтение любых файлов, инвентаризация, создание отчётов.
- Добавление навигационных файлов (`PROJECT_INDEX.md`, `SAFE_CLEANUP_POLICY.md`, `ARTIFACT_INDEX.md`).
- Добавление статусных баннеров в **отдельные** документы (точечно, не массово).
- Обновление `.gitignore` только для строго generated patterns (Python cache, Unity temp).
- Создание audit CSV/TXT файлов.

---

## Что разрешено только с явным approve

**Каждый шаг — отдельное подтверждение. Не объединять в один commit.**

| Шаг | Что удаляется | Размер | Риск |
|---|---|---|---|
| 1 | `__pycache__/` + `Temp/` + `Logs/` | ~2 MB | Минимальный — regenerated |
| 2 | `_unity_batch_stage6b3_semantic_obs_fix/` (orphan project) | ~2.75 GB | Низкий — нет ссылок |
| 3 | `python/week5_teacher/.venv_day2_py39/` | ~7.2 GB | Средний — документирован в 51 месте |
| 4 | `python/week5_teacher_reference/.venv_microrts032_reference/` | ~1.4 GB | Средний — 224 упоминания |
| 5 | `Library/` (Unity cache) | ~2.07 GB | Средний — Unity пересоберёт |

**Commit naming conventions:**
```
cleanup: remove generated cache files only
cleanup: remove orphan batch unity project directory
cleanup: remove historical legacy python venvs
cleanup: remove unity library cache (will regenerate)
cleanup: update gitignore for generated files
docs: add project navigation and safe cleanup policy
```

---

## Правила классификации

| Признак файла | Категория | Действие |
|---|---|---|
| `.py`, `.cs`, `.md`, `.json`, `.yaml` | KEEP | Никогда не удалять автоматически |
| `.pt`, `.pth`, `.npz`, `.npy`, `.onnx`, `.pkl` | KEEP / NEEDS_REVIEW | Только ручное подтверждение |
| `.unity`, `.prefab`, `.asset` | KEEP | Никогда |
| `__pycache__/`, `*.pyc`, `*.pyo` | GENERATED_CAN_DELETE | После approve Шага 1 |
| `Library/`, `Temp/`, `Logs/` (Unity) | CACHE_CAN_DELETE | После approve |
| `.venv*/`, `venv/`, `env/` | LARGE_ARTIFACT_NEEDS_REVIEW | Только ручное подтверждение |
| `_unity_batch*/` | LARGE_ARTIFACT_NEEDS_REVIEW | Только ручное подтверждение |
| Путь содержит `reports/`, `runs/`, `exports/` | HISTORICAL_KEEP | Не трогать |
| Путь содержит `checkpoints/`, `bc_ready/` | PROTECTED_KEEP | Никогда |
| Путь содержит `WEEK1`-`WEEK6`, `docs/` | HISTORICAL_KEEP | Не трогать |
| Файл не опознан | UNKNOWN_KEEP | По умолчанию сохранить |

---

## Защищённые файлы (абсолютный список)

```
Assets/Scenes/Week6_StudentStaticHarvestLayout.unity
Assets/Scripts/ML/Week6Stage6B3StaticManualPlayBootstrap.cs
python/week6_student/checkpoints/Stage6B3_SemanticObservationFix/legacy032_v2_bc_source_valid_semantic_obs_fix_final.pt
python/week5_teacher_legacy032/teacher_exports_bc/legacy032_3m_source_valid_semantic_obs_fix_bc_ready_20260507T085607Z/
CURRENT_PIPELINE_RUNBOOK.md
FIRST_SUCCESSFUL_PIPELINE_BASELINE.md
STAGE6B3_SUCCESSFUL_PIPELINE_ARTIFACT_INDEX.md
Assets/Scripts/ML/Week6StudentPolicyAdapter.cs
Assets/Scripts/ML/MlPolicyPipelineFacade.cs
Assets/Scripts/ML/ActionDecoder.cs
Assets/Scripts/ML/ActionApplier.cs
Assets/Scripts/ML/ActionMaskBuilder.cs
Assets/Scripts/ML/ObservationBuilder.cs
Assets/Scripts/ML/ObservationContract.cs
Assets/Scripts/ML/ActionContract.cs
Assets/Scripts/ML/ActionContractMappings.cs
Assets/Scripts/ML/AgentAction.cs
python/week6_student/student_branch_contract.py
python/week6_student/student_bc_contract.py
python/week6_student/student_bc_loader.py
python/week6_student/student_architecture_transfer.py
python/week6_student/student_inference_adapter.py
python/week6_student/load_student_checkpoint.py
python/week6_student/student_bc_model_minimal.py
python/week6_student/student_bc_metrics.py
python/week6_student/student_inference_server.py
python/week6_student/run_bc_training_student.py
python/week6_student/evaluate_student_checkpoint.py
python/week5_teacher_legacy032/semantic_observation_adapter_legacy032_to_unity_v2.py
python/week5_teacher_legacy032/ENVIRONMENT_LEGACY032.md
python/week5_teacher_legacy032/README.md
```

---

## История и диссертация

Для главы 3 диссертации (исследовательская трассировка) необходимо:
- Сохранить все промежуточные отчёты Stage10D (D1–D27).
- Сохранить все comparison artifacts и validation JSON.
- Сохранить все baseline/candidate datasets для ablation.
- Сохранить Gate Run outputs в `docs/archive/WEEK5R/`.
- Сохранить все GridNet/Reference sweep артефакты.

Это не мусор — это **evidence chain** дипломной работы.
