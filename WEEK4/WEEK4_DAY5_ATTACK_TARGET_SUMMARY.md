# Week 4 Day 5: attack_target[26] semantics and focused integration

## Historical Note (2026-04-29)

This Day 5 summary describes the then-current Week 4/Week 3 v1 contract context (local 3x3 attack target).

- Current Unity action contract is v2 with 7x7 attack target indexing (`49` branch size).
- The engineering conclusions here remain useful historically, but the 3x3-specific contract statements are superseded.

## Статус
Реализовано (31 March 2026). Finishing pass выполнен (31 March 2026).

---

## Цель Day 5

Сделать канал observation `attack_target[26]` реально вычисляемым и строго определённым,
с привязкой к существующему local 3x3 target space из Week 3 action contract,
без ложных заявлений о полной parity с runtime combat semantics.

Одновременно: локально снизить Day 4 residual dual-build tension в baseline path
без большого рефакторинга `HeuristicPolicyAdapter`.

---

## Финальная semantics канала `attack_target[26]`

### 1) Target space

Канал использует тот же local target space, что и action branch `attack_target`:

- domain local index: `0..8`
- geometry: `ActionContract.AttackOffsets`
- mapping index -> absolute cell: `ActionContractMappings.TryGetAttackTargetPosition(actorPos, localIndex, out targetPos)`
- индекс `4` соответствует центру (self cell)

Это тот же индексный контур, что используется в:

- `ActionContract`
- `ActionDecoder`
- `ActionMaskBuilder`
- heuristic target selection

### 2) Meaning

`attack_target[26]` = observation-side encoded representative target index
для клетки-актора (если в клетке есть живой attack-capable юнит).

Representative target выбирается детерминированно:

- scan local indices по порядку `0..8`
- первый валидный enemy target в local 3x3 становится representative

Валидный target для observation encoding:

- inside map
- не self-cell
- в target cell есть живой юнит
- юнит в target cell является enemy относительно текущей perspective

### 3) Normalization

Нормализация (finishing pass — изменена с `localIndex / 8f`):

- `normalized = (localIndex + 1) / 9.0f`
- domain: `localIndex ∈ [0..8]` → encoded ∈ `[1/9 ≈ 0.111, 1.0]`
- _нет_ valid index, который даёт `0.0f`

### 4) No-target rule

No-target sentinel:

- `0.0f`

**Unambiguous под finishing pass:** под формулой `(localIndex + 1) / 9f` `0.0f`
не является валидным encoded значением для любого index ∈ [0..8].
Disambiguation через контекст observation/mask больше не требуется для этого канала.

Случаи, когда пишется no-target:

- клетка не содержит живого юнита
- юнит не attack-capable (по runtime definition: `attackDamage <= 0` или `attackRange <= 0`)
- attack-capable юнит есть, но валидной enemy цели в local 3x3 сейчас нет

---

## Что изменено в коде

### Initial Day 5 (до finishing pass)

- `ObservationBuilder`:
  - channel `[26]` больше не placeholder/не tactical enemy-presence flag
  - добавлено реальное вычисление на основе local 3x3 target space
  - включено в оба режима (`LegacyGymCompatible`, `UnityMvpTransfer`)
  - добавлена helper-логика:
    - capability gate через `GameConfig.GetDefinition(unitType)`
    - deterministic representative target selection
    - нормализация `index/8` (заменена в finishing pass)

- `ObservationContract`:
  - уточнены комментарии и semantics канала 26
  - явно отмечено: это observation-side targeting signal, не runtime target-preserving truth

### Finishing Pass (31 March 2026)

- `ObservationBuilder.NormalizeAttackTargetLocal`:
  - формула изменена с `localIndex / 8f` на `(localIndex + 1) / 9f`
  - sentinel `0.0f` теперь unambiguous — не пересекается ни с одним валидным index

- `ObservationBuilder.CanEncodeAttackTarget`:
  - fallback при `definition == null` изменён с permissive (`actor.Type != Resource`)
    на conservative (`return false`)
  - обоснование: без `attackDamage`/`attackRange` нельзя подтвердить attack-capable статус;
    лучше не кодировать, чем кодировать для unit-ов, которых runtime не считает атакующими

- `ObservationBuilder.TrySelectRepresentativeAttackTargetLocal` (comment pass):
  - добавлен явный xml-doc / header comment: **OBSERVATION ENCODING RULE — NOT runtime combat selector**
  - явно указано что convention = first-scan, не nearest/most-dangerous

- `ObservationBuilder.ComputeAttackTargetChannelValue` (comment pass):
  - добавлен header: **OBSERVATION-SIDE ONLY** — не влияет на ActionApplier или MatchManager

- `ObservationContract.CH_ATTACK_TARGET` (comment update):
  - отражает новую формулу `(localIndex + 1) / 9f`
  - явно указывает что sentinel `0.0f` теперь unambiguous

- `HeuristicPolicyAdapter`:
  - добавлено поле `_residualOpponentRebuildCount`
  - incrementing при каждом residual rebuild для non-perspective player
  - surfacing в `TryGetPipelineDiagnostics`

- `Day5AttackTargetObservationSmokeTest`:
  - local copies `NormalizeAttackTargetLocal` и `CanEncodeAttackTarget` приведены в соответствие
  - добавлены два новых check: `ValidateNoTargetSentinelUnambiguous`, `ValidateCapabilityFallbackConservative`
  - информационный лог о representative target convention

---

## Consistency с Week 3 action/mask

Согласование выполнено через shared mapping:

- тот же `ActionContract.AttackOffsets`
- тот же `ActionContractMappings.TryGetAttackTargetPosition(...)`
- тот же local index domain `0..8`

Это снижает риск drift:

- off-by-one
- mirrored geometry
- different center conventions

---

## Focused checks (Day 5)

Добавлен focused smoke helper:

- `Day5AttackTargetObservationSmokeTest`

Что проверяет:

- channel `[26]` в `[0,1]`
- совпадение actual channel value с expected value по Day 5 semantics
- no-target behavior для неатакующих/без цели случаев
- geometry consistency index->offset
- normalization round-trip (`index -> normalized -> recovered index`)
- **[finishing pass]** `ValidateNoTargetSentinelUnambiguous`: все 9 valid indices дают значение `> 0`;
  sentinel `0.0f` невозможен для valid target под новой формулой
- **[finishing pass]** `ValidateCapabilityFallbackConservative`: `CanEncodeAttackTarget` с null config
  возвращает `false` для attack-capable types — conservative fallback подтверждён
- **[finishing pass]** Informational log о representative target convention при каждом запуске
- сохранение общей структуры observation (`TotalFloats`)

Ограничение smoke:

- check использует текущую scene state
- если в сцене нет локально доступных enemy targets, это логируется как warning,
  не как hard failure

---

## Локальное уменьшение dual-build tension (Day 4 residual debt)

В baseline path выполнено локальное улучшение без большого рефакторинга:

- `BaselineDecisionSource` теперь передаёт `RlLoopStepInput` в `HeuristicPolicyAdapter`
- `HeuristicPolicyAdapter` умеет потреблять `stepInput.CanonicalObservation` и `stepInput.CanonicalMask`
  для `stepInput.Perspective`
- для этого perspective adapter не rebuild-ит observation/mask

**[finishing pass]** Резидуальный rebuild теперь диагностируется явно:

- поле `_residualOpponentRebuildCount` в `HeuristicPolicyAdapter`
- инкрементируется каждый раз, когда второй игрок (не matching perspective) fallback-ит в rebuild
- виден в `TryGetPipelineDiagnostics` как `residualOpponentRebuilds=N`

Что осталось:

- в self-play baseline второй игрок всё ещё проходит через adapter-internal rebuild
- полное устранение dual-build для обоих игроков требует более широкого рефактора
  `HeuristicPolicyAdapter` (out of Day 5 scope)
- debt теперь наблюдаем и явно ограничен счётчиком

---

## Честные ограничения после finishing pass

Day 5 не делает ложных compatibility claims:

- вычисляемый `attack_target[26]` не означает full reference-identical observation semantics
- observation target signal не означает strict target-preserving runtime combat
- residual gap между explicit attack command и downstream combat runtime остаётся

Устранено finishing pass:

- ~~`0.0f` sentinel overlap с valid index `0`~~ → sentinel теперь unambiguous
- ~~permissive capability fallback при отсутствии definition~~ → теперь conservative
- ~~implicit dual-build debt~~→ теперь явно счётчик `_residualOpponentRebuildCount`

Остающиеся ограничения (сознательно принятые):

- Representative target = first-scan, не nearest/most-dangerous — произвольный determinism
- `attack_target[26]` — observation encoding rule, не runtime combat selector
- Runtime semantic gap остаётся (per HARD CONSTRAINT 29 March 2026)
- Self-play residual rebuild для второго игрока диагностируется, но не устраняется
- Day 6 остаётся: `PolicyDecisionSource` (`NotImplementedException`), reward sanity, rollout

Итог формулируется как:

- improved + now unambiguous observation-side targeting encoding  
- conservative capability gate aligned with runtime attack definition
- better alignment with Week 3 local targeting contract
- residual dual-build debt observable and bounded by counter
- runtime semantic gap remains explicit
