# Week 4 Day 2 - Базовый Reward Collector

Дата: 2026-03-30
Статус: Реализовано (базовый слой), без полной terminal pipeline и без полной ML-Agent интеграции.

## 1) Что сделано

Добавлен единый слой расчета награды по runtime-effect semantics:

- `Assets/Scripts/ML/RuntimeRewardCollector.cs`
- интеграция пост-шагового вычисления в `Assets/Scripts/Gameplay/Match/EpisodeController.cs`

Слой не вмешивается в Week 3 pipeline принятия решения:

`observation -> mask -> decoder -> applier -> MatchManager.ApplyCommand()`

Reward считается только после выполнения runtime шага по pre/post snapshot.

## 2) Source of Truth

Источник истины для reward:

- `MatchManager.GetMatchState()` (ресурсы, юниты, terminal state)
- `UnitRegistry.GetAllUnits()` + runtime HP/alive/carried данные

Подход:

- pre-step snapshot перед `StepMatch()`
- post-step snapshot после `StepMatch()`
- reward = интерпретация diff между pre/post

Это исключает начисление reward за:

- intent выбора действия;
- факт decode;
- факт mask-allow;
- факт accepted attack command без эффекта.

## 3) Реализованные reward-сигналы (v1 Day 2)

### Экономика

- Harvest success (proxy по росту carried resources у перспективного игрока)
- Return success (рост `own resources`)
- Produce success (рост `own unit count`)

### Бой

- Damage dealt (суммарная потеря HP у вражеских юнитов)
- Enemy destroyed (число вражеских юнитов, исчезнувших/погибших между snapshot)
- Self-loss penalty (реализован как optional, по умолчанию выключен)

### Терминальные

- Win / Loss / Draw на переходе `Running -> Ended`
- Timeout penalty как отдельный optional сигнал (по умолчанию выключен)

### Shaping

- Invalid command penalty (optional, по умолчанию выключен)
- Включается через флаг в `EpisodeController`, с per-step cap.

## 4) Breakdown и прозрачность расчета

Добавлены структуры:

- `RewardEvent` (type/category/magnitude/source/attribution)
- `RewardStepTrace` (breakdown + список событий + step meta)
- `RewardEpisodeSummary` (тонкий episode-level accumulation)

`RewardBreakdown` включает:

- `Total`
- `Economy`
- `Combat`
- `Terminal`
- `Shaping`
- `EventCount`
- `IsTerminalStep`
- `TerminalReason`

## 5) Совместимость с baseline path и будущим ML path

На текущем этапе:

- `EpisodeController` вызывает collector после `MatchManager.StepMatch()`
- `LastRewardStepTrace` и `LastRewardBreakdown` доступны как единый результат шага
- `ExperimentLogger.OnStep()` получает `rewardDelta` из collector

Это уже подходит для:

- baseline/heuristic rollout trace
- smoke/debug анализа reward distribution

и создает прямую основу для Day 3/4, где тот же слой можно подключать к RL path.

## 6) Что сознательно НЕ сделано в Day 2

- не реализована полная terminal/reset pipeline;
- не выполнена полная wiring в `OnActionReceived` ML-Agent;
- не введен отдельный event bus;
- не перенесена reward-логика в mask/decode/applier;
- не включены по умолчанию optional penalties.

## 7) Ограничения текущей реализации

- Harvest success в Day 2 считается через snapshot-proxy (рост carried resources), а не через специализированный harvest-event object.
- Produce success определяется по изменению unit count (предполагается, что в шаге это отражает runtime spawn effect).
- Damage и destroy считаются по unit snapshot diff; для глубокой forensic-диагностики может понадобиться отдельный combat event feed (не в Day 2 scope).

## 8) Переход к Day 3/4

Day 3 (terminal semantics и episode loop) и Day 4 (стабилизация RL цикла) должны использовать этот reward layer как общий источник step reward, не создавая параллельный путь расчета.

Ключевой инвариант сохранен:

- reward считается по runtime-authoritative effect semantics;
- breakdown доступен и для baseline, и для будущего ML path.