# WEEK5_TEACHER_PIPELINE_SPEC.md
# Teacher Pipeline Contract — Day 1 Specification

**Date:** 2026-04-09  
**Status:** ✅ Day 1 contract frozen — код не пишется до утверждения этого документа  
**Scope:** Teacher-side Gym-μRTS rollout pipeline для будущего behavioral cloning в Week 6  
**Upstream:** WEEK3_CONTRACT_SPEC.md, WEEK3_COMPATIBILITY_GAP_LIST.md, WEEK4_REWARD_CONTRACT.md, WEEK4_REWARD_AND_RL_LOOP_SUMMARY.md  
**Downstream:** Week 6 BC/distillation path (student не реализуется в Week 5)

---

## 0. Что этот документ фиксирует и чего не делает

Этот документ фиксирует **teacher-side contract** — то, что Week 5 обязуется произвести на стороне Gym-μRTS как входной материал для будущего Week 6 BC пути.

Этот документ **не**:
- не пишет Python-код exporter или rollout collector;
- не определяет student-side architecture;
- не утверждает direct weight transfer;
- не подменяет Unity-side target contract реальным Gym-форматом «as is»;
- не строит BC loss или training loop;
- не меняет ни один артефакт Week 3 / Week 4.

Unity-side target contract остаётся зафиксированным в **Week 3 / Week 4 артефактах**. Gym-side pipeline читает их как источник истины и **адаптируется к ним**, а не наоборот.

---

## 1. Purpose и Scope Week 5

### 1.1 Что такое teacher pipeline в контексте этого проекта

Teacher pipeline — это воспроизводимый Python-контур, который:
1. запускает обученную (или воспроизводимо загружаемую) policy в среде Gym-μRTS;
2. собирает trajectory rollouts по эпизодам;
3. экспортирует их в формате, совместимом с Unity-side target contract (через explicit adapter);
4. предоставляет проверяемый, задокументированный и BC-ready датасет.

Teacher pipeline **не является частью Unity-среды**. Он существует полностью на стороне Python / Gym-μRTS и соединяется с Unity-контуром только через exported dataset и adapter layer.

### 1.2 Связь с Week 6 BC/distillation path

Week 5 производит **входной материал** для Week 6:
- адаптированный датасет траекторий;
- document conversion rules (адаптер gaps);
- contract-level validation report.

Week 6 потребляет этот материал для:
- supervised BC loss (teacher action → student action);
- optional: knowledge distillation (teacher logits → student logits);
- optional: warm-start before RL fine-tuning.

Граница clear: Week 5 не должен пытаться строить student или запускать BC training. Это ломает область ответственности.

### 1.3 Явное ограничение: это не direct full transfer

Week 5 **не достигает** и **не утверждает**:
- полноценный direct weight transfer между Gym-μRTS policy и Unity ML-Agents;
- побитовую совместимость observation spaces;
- унификацию action semantics без потерь.

Правильная формулировка цели Week 5:
> «Получить воспроизводимый, честно задокументированный учительский датасет, в котором несовместимости явно закодированы как conversion rules или explicit data loss — и который служит корректным входом для Week 6 BC pipeline.»

---

## 2. Source of Truth

| Слой | Документ | Что фиксирует |
|------|----------|----------------|
| Unity target observation | `WEEK3_CONTRACT_SPEC.md` §3.1 | LegacyGymCompatibleSpec: [24,24,27], channels 0–26 |
| Unity target action | `WEEK3_CONTRACT_SPEC.md` §4.1 | 7 branches, 35 flat per cell, attack_target 0–8 |
| Compatibility gaps | `WEEK3_COMPATIBILITY_GAP_LIST.md` | 8 активных gap, 2 resolved |
| Reward semantics | `WEEK4_REWARD_CONTRACT.md` | 4 категории, event classification matrix |
| RL loop assumptions | `WEEK4_REWARD_AND_RL_LOOP_SUMMARY.md` | Phase order, canon path, known limitations |
| Action contract detail | `WEEK3_OBSERVATION_AND_ACTION_SUMMARY.md` | Branch sizes, encoding rules, mask semantics |

**Операциональное правило:** Gym-side teacher pipeline не имеет права переопределять Unity-side contract. Любое несоответствие — это gap, который документируется как conversion rule или explicit data loss. Не как новый contract.

---

## 3. Minimal Teacher Trajectory Schema

### 3.1 Два слоя observation и action в trajectory

**Критически важное разграничение:** Trajectory schema содержит два логических слоя для observation и action, которые нельзя смешивать:

| Слой | Описание | Кто производит | Где хранится |
|------|----------|---------------|-------------|
| **Raw teacher layer** | Gym-native форматы как есть из env.step() | rollout collector (Day 2–3) | `teacher_rollouts/` |
| **Adapter-target layer** | Конвертированные поля, совместимые с LegacyGymCompatibleSpec | adapter (Day 4) | `teacher_exports/` |

Minimal trajectory schema §3.2 описывает **raw teacher layer**. Adapter-target layer возникает позже, в Day 4, и является отдельным артефактом. Читать поля §3.2 как уже Unity-compatible — **ошибка**.

### 3.2 Обязательные поля (BC-required) — raw teacher layer

Эти поля обязательно присутствуют в каждом шаге trajectory. Отсутствие любого из них делает шаг непригодным для BC (он должен быть отброшен, а не угадан).

| Поле | Тип | Описание | Примечание |
|------|-----|----------|------------|
| `episode_id` | `int` | Уникальный идентификатор эпизода | Монотонно возрастает в пределах run |
| `step_index` | `int` | Номер шага внутри эпизода, 0-based | Не глобальный, а per-episode |
| `observation_raw` | `float32[H, W, C_gym]` | Spatial observation в Gym-native encoding | C_gym верифицируется при запуске; **не предполагается равным 27 без проверки** |
| `action_raw` | Gym-native encoding (см. примечание ниже) | Teacher action в Gym-native формате | НЕ int[7]; формат зависит от версии среды |
| `reward` | `float32` | Scalar reward от Gym-среды | Gym-native; семантически отличается от Unity reward |
| `done` | `bool` | Эпизод завершён на этом шаге | Gym-style terminal flag |

**Примечание об `observation_raw`:**  
Gym-native observation — это то, что возвращает `env.step()` / `env.reset()` без какой-либо обработки. Channel count `C_gym` фиксируется при верификации env version (День 2). Для MicroRTS-Py v0.6.1 ожидается C_gym=27 (без terrain channel), но это **должно проверяться явно**, а не предполагаться. Если C_gym ≠ 27 — это blocker для совместимости с LegacyGymCompatibleSpec и должен быть зафиксирован как critical gap до начала rollout сбора.

Adapter-target observation (`observation_adapted: float32[24, 24, 27]`) производится из `observation_raw` в Day 4 adapter и хранится отдельно в `teacher_exports/`. Читать `observation_raw` как уже совпадающий с Unity spatial tensor — это **false compatibility claim**.

**Примечание об `action_raw`:**  
Gym-μRTS action format версии-зависим. Он может быть flat integer (единый дискретный выбор), multi-discrete tuple, или иной структурой в зависимости от task и env wrapper. Описание `int[7]` было бы architectural shortcut, имплицитно предполагающим Unity-like branch tuple. Вместо этого:
- `action_raw` сохраняется в Gym-native формате без преобразования;
- фактический тип и shape фиксируются при env verif в Day 2 (`action_space.shape`, `action_space.nvec`);
- adapter-target action (`action_adapted: int[7]` в Unity-branch encoding) производится в Day 4.

Adapter layer (Day 4) несёт полную ответственность за mapping action_raw → action_adapted. Смешивать эти два уровня в rollout collector — ошибка архитектуры.

### 3.3 Маска действий: always-save-if-available

Valid action mask **не является BC-required** для plain CE loss, но должна сохраняться всегда, если она доступна без дополнительных затрат из Gym-среды. Правило «приоритетная опциональная» заменяется более строгим:

> **Если Gym-среда предоставляет action mask в `info` или как отдельный return value — она сохраняется всегда, в обоих форматах (`.npz` и `.jsonl`).**

Rationale: Day 5 contract-level validation теряет значительную часть диагностической силы без mask. Mask-aware BC (Week 6) также требует её наличия. Стоимость сохранения маски при наличии — близка к нулю; стоимость её отсутствия на Day 5 — ненулевая.

Единственное основание не сохранять маску — если Gym API не предоставляет её без существенного overhead (например, требует полного env reset или отдельного expensive call). Это должно быть явно задокументировано в Day 2, если такое ограничение обнаружено.

| Поле | Тип | BC-required | Политика сохранения | Если недоступна |
|------|-----|-------------|--------------------|-----------------|
| `action_mask_raw` | `bool[N_actions]` | No | **Always save if available** | Явно документировать причину; не допускать молчаливого skip |

**Семантика маски:** Gym-side action mask — это pre-sampling layer, не authoritative runtime truth. Это точно та же семантика, что зафиксирована в Week 3 для Unity-side mask. Маска не заменяет post-hoc валидацию в Unity. **Нельзя утверждать, что Gym mask и Unity mask эквивалентны** — это отдельный gap, требующий adapter analysis (Gap §7.8).

### 3.3 Диагностические поля (informational only)

Эти поля записываются per-step или per-episode, используются для анализа и отладки, но не участвуют напрямую в BC training input.

| Поле | Уровень | Описание |
|------|---------|----------|
| `info` | per-step | Raw info dict от Gym-среды (partial Win, units count, etc.) |
| `policy_source_id` | per-episode | Идентификатор teacher policy (имя, версия, checkpoint hash) |
| `env_version` | per-episode | Версия MicroRTS-Py / Gym-μRTS среды |
| `env_map_id` | per-episode | Имя карты или сценарий (eg. `maps/16x16/basesWorkers16x16.xml`) |
| `env_seed` | per-episode | Seed среды для воспроизводимости |
| `rollout_seed` | per-episode | Seed политики/rollout runner |
| `action_type_histogram` | per-episode | Гистограмма типов действий (диагностика action distribution) |
| `episode_length` | per-episode | Число шагов до terminal |
| `episode_return` | per-episode | Суммарный reward эпизода |
| `adapter_conversion_report` | per-batch | Статистика conversion (passed/remapped/dropped per gap) |

**Правило:** диагностические поля могут быть absent в primary training export (см. §4). Они обязательны в debug export.

---

## 4. Storage Format Decision

### 4.1 Решение

| Роль | Формат | Расширение |
|------|--------|------------|
| **Primary (training)** | NumPy compressed | `.npz` |
| **Debug (inspection)** | JSON Lines | `.jsonl` |

### 4.2 Rationale — Primary Format: `.npz`

- Native для NumPy/PyTorch; нет runtime dependency кроме numpy.
- Поддерживает structured arrays: каждое поле как отдельный named array в одном файле.
- Компрессия по умолчанию для float32 arrays существенна (observation tensors крупные).
- Random access по episode slice: загрузкой нужного `.npz` файла, а не всего датасета.
- Прямая передача в `torch.from_numpy()` без copy.
- Версионная совместимость: numpy 1.x → 2.x backward compatible для `.npz`.

**Структура файла:** один `.npz` per batch (или per episode, TBD Day 2). Keys: `observations`, `actions`, `rewards`, `dones`, `episode_ids`, `step_indices`. Optional keys: `action_masks`.

### 4.3 Rationale — Debug Format: `.jsonl`

- Human-readable: каждая строка — один шаг, валидный JSON.
- Не требует numpy/torch для инспекции.
- Совместим с `jq`, `grep`, текстовыми редакторами.
- Позволяет читать partial файл при больших rollouts.
- Включает все диагностические поля, которые убираются из primary `.npz`.

**Ограничение:** `.jsonl` debug файлы значительно больше `.npz` из-за float serialization. Не использовать `.jsonl` как основной хранилищный формат для large batches.

### 4.4 Отклонённые кандидаты

| Формат | Причина отклонения | Риск при использовании |
|--------|-------------------|------------------------|
| `parquet` | Требует `pyarrow` или `pandas` — дополнительная зависимость вне ML-стека | Version conflicts в training envs |
| `pickle` | Небезопасен при десериализации из посторонних источников; хрупок к версиям Python/PyTorch | Security risk (arbitrary code exec); cross-version fragility |
| `hdf5` | Требует `h5py`; сложнее deployment; overkill для текущего масштаба | Extra dep; порог вхождения выше для воспроизведения |

**Explicit assumption:** Датасет Week 5 не превысит размер, при котором `.npz` per-batch становится неудобным. Если Week 6 покажет обратное — это повод пересмотреть формат в Week 6, а не переархитектурировать сейчас.

---

## 5. Teacher Policy Source

### 5.1 Допустимые классы teacher policy

В порядке предпочтения:

**Класс A — Воспроизводимо загружаемая policy:**  
- Checkpoint загружается из фиксированного источника (git tag, Hugging Face release, local path + hash verification).
- Версия среды и архитектура policy зафиксированы и совместимы.
- Нет необходимости дообучать до начала rollout.
- **Preferred:** наименьший риск нестабильности и версионных несовместимостей.

**Класс B — Воспроизводимо обучаемая policy:**  
- Обдучивается с нуля в зафиксированном окружении (Python env + env version + seed).
- Training run документирован: hyperparams, seed, число steps, метрики сходимости.
- Применяется только если Класс A недоступен или несовместим.
- **Риск:** дополнительное время на обучение; возможная нестабильность run-to-run без явного seed control.

**Класс C — Готовая предобученная policy (без верификации совместимости):**  
- Используется только как временный заменитель для Day 2 smoke-check.
- **Недопустима как canonical teacher policy** если не пройдена shape compatibility verification.

### 5.2 Что НЕ считается допустимым teacher policy source

- Policy, обученная на версии среды с другим channel count observation (eg. с terrain channel) без explicit channel-drop adapter.
- Policy, архитектура которой неизвестна (нет state_dict структуры, нет input shape).
- Policy из paper experiments без верификации на текущей env version (известная проблема: `gym_microrts==0.3.2` vs `MicroRTS-Py v0.6.1` несовместимы по observation tensor).
- Любой checkpoint, для которого нет hash или явной фиксации источника.

**Это не формализм.** Datapoisoning риск в BC контексте реален: если teacher policy «обучена» в существенно другой среде — student научится ошибочным поведениям. Это должно быть explictly caught, а не обнаружено постфактум в Week 6.

### 5.3 Обязательные metadata о teacher policy

Для каждой policy, используемой как teacher, обязательно логируются:

| Поле | Значение | Необходимо потому что |
|------|----------|----------------------|
| `policy_name` | Имя / идентификатор | Воспроизводимость |
| `policy_version` | Версия / git tag / release | Дисциплина изменений |
| `checkpoint_hash` | SHA256 файла checkpoint | Верификация целостности |
| `env_version` | MicroRTS-Py/Gym-μRTS version | Совместимость channels |
| `obs_shape_verified` | bool | Подтверждение [H,W,C] перед rollout |
| `action_space_verified` | bool | Подтверждение размерности actions |
| `training_seed` | int или "unknown" | Воспроизводимость (unknown допускается) |
| `training_steps` | int или "pretrained" | Контекст quality |
| `map_scenario` | Имя карты при обучении | Domain match с Unity MVP_24x24 |

---

## 6. Encoder / Observation Decision

### 6.1 Global vector Unity — не часть teacher encoder

**Зафиксировано явно:** Unity-side `UnityMvpTransferSpec` содержит optional global feature vector (resources, step progress, game phase). Этого вектора **не существует** в Gym-μRTS observation space.

**Следствие:** Strict BC encoder path **не должен** ожидать global vector как обязательный input. Spatial tensor `[H, W, 27]` — это единственная обязательная encoder input поверхность для transfer-compatible BC path.

**Правило:** Если student encoder в Week 6 будет использовать global vector — он должен:
1. Либо получать его из Unity-рантайма (не из teacher dataset);
2. Либо явно маркировать global vector как auxiliary input, а не как часть matched BC target.

Смешение global vector из teacher dataset и Unity-runtime global vector **не допускается без explicit conversion**. Это создаёт ложную совместимость.

### 6.2 BC-required vs auxiliary distinction

| Observation component | BC-required | Допускается как auxiliary | Откуда берётся |
|----------------------|-------------|--------------------------|----------------|
| Spatial tensor [H,W,27] | ✅ Да | — | Teacher dataset (raw Gym obs) |
| Global vector (resources, step_t) | ❌ Нет | Optional diagnostic | Unity-runtime only; не из Gym |
| Action mask | ❌ Нет (для plain CE) | Yes (для mask-aware BC) | Teacher dataset (если записан) |

### 6.3 Compatibility warning

Если учительская policy использовала global vector в своей encoder architecture (например, concatenated после spatial backbone) — это **дополнительный arch gap**, который должен быть задокументирован в adapter report и не замалчиваться.

---

## 7. Compatibility Gaps Imported from Week 3

Следующие gaps импортированы из `WEEK3_COMPATIBILITY_GAP_LIST.md` и структурированы для Week 5 adapter planning. Для каждого gap указано: затрагивает что, блокирует что, ожидаемый класс mitigation, adapter-required vs diagnostics-only.

### 7.1 Gap: Global Vector (Week 3 Gap #1)

| Атрибут | Значение |
|---------|---------|
| Category | Observation surface extension |
| Affects | Encoder compatibility; feature surface match |
| Blocks | Direct encoder reuse (if global vec used in teacher arch) |
| Mitigation class | Exclusion: global vector исключается из BC encoder path |
| Adapter required | Нет (исключение, а не перевод) |
| Status | Documented exclusion; handled by §6 of this spec |

**Residual risk:** если teacher policy использует global vec — её backbone несовместима, нужна partial transfer с head-only adaptation.

### 7.2 Gap: Normalization Formulas (Week 3 Gap #1, observation semantics)

| Атрибут | Значение |
|---------|---------|
| Category | Observation value range / normalization |
| Affects | HP normalization; resource normalization per-cell |
| Blocks | Не блокирует transfer полностью, но создаёт value distribution mismatch |
| Mitigation class | Adapter: явные normalization formulas в dataset converter |
| Adapter required | ✅ Да |
| Status | Требует кодового adapter в Day 4 |

**Конкретика:** Gym-μRTS нормализует HP и ресурсы по maxHP/maxRes конкретной карты. Unity нормализует по GameConstants (глобальные max). Без явной formulas — distribution mismatch → bias in BC.

### 7.3 Gap: Attack Target Parameterization Reduced to Local 3×3 (Week 3 Gap #3)

| Атрибут | Значение |
|---------|---------|
| Category | Action-space reduction |
| Affects | BRANCH_ATTACK_TARGET encoding; valid target semantics |
| Blocks | Direct action head reuse; any teacher attack action outside 3×3 |
| Mitigation class | Adapter: filter/drop out-of-window attack actions; remap в-range actions |
| Adapter required | ✅ Да |
| Status | Каждое dropped attack action → explicit log с причиной |

**Data loss risk:** Gym может выдавать attack actions на цели на расстоянии > Chebyshev 1. Все такие примеры отбрасываются. Это explicit data loss, не silent filter.

### 7.4 Gap: Reduced Producible Unit Types (Week 3 Gap #5)

| Атрибут | Значение |
|---------|---------|
| Category | Action-space subset |
| Affects | produce_unit_type branch; unit type count |
| Blocks | Teacher produce actions с unit types вне Unity MVP subset |
| Mitigation class | Adapter: filter unsupported produce types; log dropped production actions |
| Adapter required | ✅ Да |
| Status | Unity MVP subset: Worker, Light, Heavy, Ranged (из Base/Barracks) |

**Explicit assumption:** Unity MVP producible subset соответствует Week 4 `ProducibleUnit` enum. Если Gym-μRTS teacher производит юниты вне этого subset — они отбрасываются с логом.

### 7.5 Gap: Missing Action Types (Week 3 Gap #5, partial)

| Атрибут | Значение |
|---------|---------|
| Category | Action type coverage |
| Affects | Action type branch; любые Gym action types вне {NoOp, Move, Harvest, Return, Produce, Attack} |
| Blocks | Teacher actions с gap action types |
| Mitigation class | Filter: unsupported action types отбрасываются; log включает action type |
| Adapter required | ✅ Да |
| Status | Unity MVP action types фиксированы в Week 3 ActionContract |

### 7.6 Gap: Temporal Resolution (Week 3 Gap #7)

| Атрибут | Значение |
|---------|---------|
| Category | Runtime coordination gap |
| Affects | Step-level semantics; multi-actor timing; dataset step index |
| Blocks | Прямую синхронизацию step timing между Gym и Unity |
| Mitigation class | Documentation: явная фиксация что per-step semantics не идентичны |
| Adapter required | ❌ Не требует code adapter, но требует doc conversion rule |
| Status | Диагностически важен; не блокирует BC loss |

**Conversion rule:** Teacher step index из Gym-μRTS не является прямым аналогом Unity step index. В BC training step index используется только как episode-relative offset, не как cross-environment sync point.

### 7.7 Gap: Attack Command vs Runtime Combat Semantics (Week 3 Gap #4)

| Атрибут | Значение |
|---------|---------|
| Category | Runtime semantic mismatch |
| Affects | BC quality для attack actions; policy evaluation |
| Blocks | Strict target-preserving attack transfer |
| Mitigation class | Documentation: явная фиксация gap в adapter annotation |
| Adapter required | ❌ (не кодовый), ✅ (в conversion report) |
| Status | **Residual architectural gap.** Зафиксировано в CONTEXT.md HARD CONSTRAINT |

**Explicit limitation:** Даже после adapter conversion, teacher attack action → Unity attack command может не гарантировать идентичный combat outcome из-за runtime combat resolution в CombatResolver. Это **не ошибка адаптера**, это документированный semantic gap проекта.

### 7.8 Gap: Mask Semantics — Pre-sampling vs Authoritative (Week 3 Gap #6)

| Атрибут | Значение |
|---------|---------|
| Category | Mask semantic mismatch |
| Affects | Mask-aware BC variants; offline policy evaluation |
| Blocks | Утверждения о полной mask parity между Gym и Unity |
| Mitigation class | Documentation + diagnostic-only labeling of mask data |
| Adapter required | ❌ напрямую, но ✅ semantic label в metadata |
| Status | Диагностический gap; не блокирует plain CE BC loss |

**Explicit rule:** Gym-side action mask ≠ Unity runtime mask. Они могут отличаться из-за different runtime constraints. Mask из dataset используется только как diagnostic / soft constraint layer, **не как authoritative filter** в Unity production path.

### 7.9 Gap Summary Table

| Gap | Adapter code required | Data loss risk | Blocks BC | Mitigation class |
|-----|----------------------|----------------|-----------|-----------------|
| 7.1 Global vector | No (exclusion) | No | No | Exclude from BC path |
| 7.2 Normalization | Yes | Low (bias) | No | Explicit formula in adapter |
| 7.3 Attack target 3×3 | Yes | Medium (attack examples) | Partial | Filter + log |
| 7.4 Produce subset | Yes | Low (rare unit types) | Partial | Filter + log |
| 7.5 Missing action types | Yes | Low–Medium | Partial | Filter + log |
| 7.6 Temporal resolution | No | No | No | Doc conversion rule |
| 7.7 Combat semantics | No (doc) | Semantic only | Partial | Explicit limitation doc |
| 7.8 Mask semantics | No (label) | No | No | Diagnostic-only labeling |

---

## 8. Contract Boundaries — Что Day 1 НЕ Делает

**Не пишется в Day 1:**
- Python rollout runner или entrypoint скрипт
- Dataset exporter (`.npz` writer)
- Observation / action adapter code
- BC student или training loop
- Dataset validator
- Любой C# код в Unity

**Не утверждается в Day 1:**
- Что direct weight transfer достигнут или близок
- Что Gym mask и Unity mask семантически эквивалентны
- Что адаптированный датасет не будет иметь data loss
- Что teacher policy quality гарантированно достаточна для BC

**Не подменяется:**
- Unity target contract (LegacyGymCompatibleSpec / UnityMvpTransferSpec) реальным Gym-форматом «as is»
- Authoritative runtime truth в ActionApplier / MatchManager / VictoryResolver

Всё, что делает Day 1 — это **замораживает контракт**, с которым будут работать Day 2–7.

---

## 9. Deliverable / Acceptance Criteria

### «Day 1 done when...»

- [x] Teacher pipeline определён как отдельный этап с явными boundaries относительно Unity и Week 6
- [x] Минимальный состав trajectory schema зафиксирован: observation_raw, action_raw, reward, done, step_index, episode_id
- [x] Два слоя trajectory разделены явно: raw teacher layer (роллаут) vs adapter-target layer (экспорт)
- [x] `observation_raw` не заявлен как уже совместимый с Unity spatial tensor; channel count верифицируется в Day 2
- [x] `action_raw` не int[7]; Gym-native format фиксируется в Day 2 (не является Unity branch tuple)
- [x] BC-required vs diagnostic-only поля разделены явно
- [x] Action mask политика: always-save-if-available (не BC-required, но сохраняется всегда при наличии)
- [x] Primary storage format выбран: `.npz` с explicit rationale
- [x] Debug storage format выбран: `.jsonl` с explicit rationale
- [x] Три класса teacher policy source определены (A: load, B: train, C: placeholder only)
- [x] Недопустимые sources описаны явно (no-hash checkpoint, wrong env version, unknown arch)
- [x] Teacher policy metadata schema зафиксирована (8 обязательных полей)
- [x] Global vector exclusion из BC encoder path зафиксирована явно
- [x] 8 compatibility gaps импортированы из Week 3 и структурированы для adapter planning
- [x] Для каждого gap: adapter-required vs diagnostics-only, data loss risk, blocks what
- [x] Contract boundaries Week 5 Day 1 перечислены без ambiguity
- [x] Нет противоречий с Week 3/4 contract (проверено по source документам)

**Дополнительная проверка:** Открыть `WEEK3_COMPATIBILITY_GAP_LIST.md` и убедиться, что все 8 активных gaps отражены в §7 этого документа. ✅

---

## 10. Decision Log

### D-01: Storage Format — npz vs parquet vs pickle vs jsonl

| Атрибут | Значение |
|---------|---------|
| Decision | Primary: `.npz`; Debug: `.jsonl` |
| Reason | npz: native numpy/torch, компрессия, нет extra deps; jsonl: human-readable, no deps |
| Alternatives rejected | parquet (extra dep pyarrow); pickle (security risk, fragile); hdf5 (overkill) |
| Risk | npz random-access по-step неудобен (нет per-row index без дополнительной структуры) |
| Follow-up | Day 2: решить per-episode vs per-batch npz structure; добавить episode index metadata |

### D-02: Teacher Policy Source Classification

| Атрибут | Значение |
|---------|---------|
| Decision | Три класса: A (load, preferred), B (train, fallback), C (placeholder, smoke only) |
| Reason | Отделяет воспроизводимость от exploratory use; предотвращает tainted teacher risk |
| Alternatives rejected | Единый класс «любой policy» без верификации — неприемлем для BC dataset quality |
| Risk | Класс A может быть недоступен для нужной env version; тогда fallback на B требует training time |
| Follow-up | Day 2: верифицировать доступность Класс A policy для MicroRTS-Py v0.6.1; зафиксировать результат |

### D-03: Global Vector Exclusion

| Атрибут | Значение |
|---------|---------|
| Decision | Global vector НЕ является частью teacher encoder для BC path |
| Reason | Global vector отсутствует в Gym-μRTS; включение не-параллельного поля создаёт ложную compatibility |
| Alternatives rejected | Заполнить нулями из Unity-source — нарушает teacher/student input parity; создаёт semantic drift |
| Risk | Student encoder Week 6 может случайно включить global vector без explicit flag — этот риск надо проверять в Week 6 |
| Follow-up | Week 6: при проектировании student encoder явно проверить auxiliary vs required input split |

### D-04: Mask Semantics — diagnostic-only + always-save-if-available

| Атрибут | Значение |
|---------|--------|
| Decision | Gym-side action mask: pre-sampling / diagnostic layer (не authoritative); сохраняется всегда, если API предоставляет mask без overhead |
| Reason | Week 3 mask semantics contract — pre-sampling only; always-save позволяет Day 5 валидацию и mask-aware BC в Week 6 без повторного rollout |
| Alternatives rejected | «prioritized optional» (можно skip молча) — создаёт риск тихого пропуска маски; маска как жёсткий BC фильтр — creates false parity claim |
| Risk | Day 2: Gym API может не exposing mask напрямую; если так — явно задокументировать ограничение, не скрывать |
| Follow-up | Day 2: проверить `env.action_masks` / `info["action_mask"]` доступность; Week 6: mask-aware BC — Gym mask как soft prior, не ground truth |

### D-06: Two-Layer Trajectory Schema (raw vs adapter-target)

| Атрибут | Значение |
|---------|--------|
| Decision | Trajectory schema разделена на raw teacher layer (роллаут) и adapter-target layer (экспорт). `observation_raw`, `action_raw` — Gym-native; `observation_adapted`, `action_adapted` — Unity-compatible, производится в Day 4. |
| Reason | Избегает semantic drift: нельзя прочитать `observation_raw` как уже Unity-compatible (false compatibility claim). rollout collector не должен делать conversion. |
| Alternatives rejected | Единый слой (сразу пишем в Unity-формате в rollout) — смешивает ответственностью, предопределяет action format без env verification. |
| Risk | Имплементация Day 2–3 должна явно хранить raw fields отдельно; нельзя in-place перезаписывать observation_raw adapter-converted версией. |
| Follow-up | Day 4: adapter принимает raw fields, выдаёт adapted fields; raw сохраняется как арܬив для debug; export содержит только adapted fields + metadata |

### D-05: Attack Examples — Filter vs Remap

| Атрибут | Значение |
|---------|---------|
| Decision | Attack actions с target вне local 3×3 (Chebyshev > 1) отбрасываются; не ремапятся |
| Reason | Remap произвольно изменяет teacher intent; explicit drop + log честнее |
| Alternatives rejected | Remap к ближайшему valid target — изменяет семантику teacher action; создаёт false BC signal |
| Risk | Если teacher часто атакует дальний target — data loss может быть значительным; нужна histogram в Day 3 |
| Follow-up | Day 3: добавить attack_range_histogram в rollout stats; если loss > 30% — переосмыслить mitigation |

---

## 11. Appendix: Week 5 Directory Structure (Planned)

Следующая структура каталогов используется (создаётся) начиная с Day 2:

```
python/
└── week5_teacher/
    ├── teacher_models/          # Сохранённые policy checkpoints (Класс A/B)
    ├── teacher_rollouts/        # Сырые rollout данные (.npz per batch)
    ├── teacher_exports/         # Адаптированные BC-ready датасеты
    ├── teacher_logs/            # Rollout stats, conversion reports
    ├── adapter/                 # Observation/action adapter modules (Day 4)
    ├── validation/              # Contract validators (Day 5)
    └── README.md               # Entrypoints, commands, output descriptions
```

Эта структура не является частью Unity Assets. Она полностью Python-side.

---

*Документ готов к использованию как frozen Day 1 contract.*  
*Следующий шаг: Day 2 — Подготовка воспроизводимого Python-контура Gym-μRTS.*
