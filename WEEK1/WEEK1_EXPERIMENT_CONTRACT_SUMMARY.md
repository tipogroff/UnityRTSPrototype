# Week 1: Контракт эксперимента и Baseline — Итоговый Summary

**Дата:** 16 марта 2026 (Финализация 2 апреля 2026)  
**Статус:** ✅ ЗАВЕРШЕНА как documented experiment contract layer  
**Область:** Технический контракт MVP — сценарий, типы, observation space, action space, logging  

---

## I. Обзор Week 1

Week 1 завершена как **фундаментальный технический контракт** всего проекта. Никакого Unity gameplay, никакой ML-логики — только формализация входов/выходов, сценарного базиса и метрических соглашений.

Главная инженерная задача: **зафиксировать однозначные boundary conditions** до написания серьёзного кода, чтобы Week 2–8 опирались на стабильный, не расходящийся фундамент.

### Основные артефакты Week 1:

1. **GameConstants.cs** — единственный источник числовых констант (размер карты, лимит шагов, параметры ресурсов)
2. **UnitType.cs** — domain enums (UnitType, Owner, UnitActionType, Direction, ProducibleUnit)
3. **UnitDefinition.cs** — ScriptableObject-параметры одного типа юнита
4. **GameConfig.cs** — ScriptableObject эталонного сценария
5. **ObservationContract.cs** — канальная спецификация [24, 24, 27]
6. **ActionContract.cs** — ветвевая спецификация 7 branches / 35 flat per cell
7. **ExperimentLogger.cs** — CSV-логгер метрик эпизода
8. **GameConfigCreator.cs** — Editor-утилита создания GameConfig_MVP
9. **GameConfig_MVP.asset** — эталонный конфигурационный ассет

### Рамки Week 1 (честно)

Week 1 **не делает**:
- ❌ Игровой движок или сцену — это Week 2
- ❌ ML-агентный интерфейс — это Week 3
- ❌ RL-контур (reward/terminal) — это Week 4
- ❌ Обучение или transfer — это Week 5+
- ❌ Реальный gameplay — Week 1 содержит только статические контракты без исполняемой логики

---

## II. Контракт эксперимента

### 2.1 Эталонный сценарий

| Параметр | Значение |
|----------|---------|
| Имя | `MVP_24x24_Symmetric` |
| Размер карты | 24×24 клетки |
| Старт | Симметричный 180°: 1 база + 2 воркера на каждой стороне |
| Начальные ресурсы | 5 на каждого игрока |
| Лимит шагов | 2000 |
| MaxWorkerLimit | 2 |

> Сценарий зафиксирован в `Assets/ML/GameConfig_MVP.asset` и является единственным эталонным конфигом для сравнения `transfer vs from-scratch-lite` (глава 3 диссертации).

### 2.2 Метрики эксперимента

Зафиксированы в разделе 4 `IMPLEMENTATION_PLAN.md` и реализованы в `ExperimentLogger`:

| Метрика | Описание |
|---------|---------|
| `win` | Победитель эпизода (Player1 / Player2 / Draw) |
| `steps` | Число шагов до терминала |
| `reward` | Суммарный episode reward |
| `invalid_rate` | Доля невалидных действий от общего числа |
| `resources_p1_at_ref` / `resources_p2_at_ref` | Ресурсы каждой стороны на шаге `referenceStep` |
| `builds_p1_at_ref` / `builds_p2_at_ref` | Постройки каждой стороны на шаге `referenceStep` |

Дополнительные метрики (считаются внешними скриптами по CSV):
- Win rate (по серии эпизодов)
- Time-to-win mean/std
- Episode reward mean/std
- Harvest speed proxy

### 2.3 Критерии успеха всего проекта

Зафиксированы в `IMPLEMENTATION_PLAN.md` §3:
1. Unity-среда воспроизводит матч: ресурсы + строительство + бой
2. Эпизоды корректно завершаются и сбрасываются
3. Observation/action/mask без систематических ошибок
4. Противник управляется перенесённой политикой (BC-путь)
5. Есть сравнение transfer и from-scratch-lite по заранее выбранным метрикам

---

## III. Core Domain Types

**Namespace:** `RTS.Core`

### 3.1 GameConstants

Статический класс — единственный источник числовых констант:

| Константа | Значение | Назначение |
|-----------|---------|-----------|
| `MapWidth` | 24 | Ширина карты (клеток) |
| `MapHeight` | 24 | Высота карты (клеток) |
| `CellSize` | 1f | Unity-единицы на клетку |
| `MaxEpisodeSteps` | 2000 | Лимит до принудительного сброса |
| `DecisionPeriod` | 0.1f | Интервал принятия решений агентом (с) |
| `InitialResources` | 5 | Стартовые ресурсы каждой стороны |
| `MaxResourcesPerPatch` | 20 | Ресурсов в одном патче |
| `HarvestAmount` | 1 | Ресурсов за одну операцию Harvest |
| `MaxCarryCapacity` | 5 | Максимум в руках воркера |
| `MaxHitPoints` | 10 | Для нормализации HP в observation |

> Любое изменение `GameConstants` автоматически затрагивает все зависимые модули. Не дублировать числа в коде.

### 3.2 UnitType.cs — Domain Enums

Все enums выровнены с индексами Observation/Action контракта:

**UnitType** (каналы [5–11] в ObservationContract):
```
Resource=0, Base=1, Barracks=2, Worker=3, Light=4, Heavy=5, Ranged=6
```

**Owner** (каналы [2–4] в ObservationContract):
```
Neutral=0, Player1=1, Player2=2
```

**UnitActionType** (каналы [12–17] в ObservationContract):
```
NoOp=0, Move=1, Harvest=2, Return=3, Produce=4, Attack=5
```

**Direction** (каналы [18–21] в ObservationContract):
```
North=0, East=1, South=2, West=3
```

**ProducibleUnit** (каналы [22–25] в ObservationContract):
```
Worker=0, Light=1, Heavy=2, Ranged=3
```

> ⚠️ Порядок значений enum = индексы one-hot каналов в observation. Изменение порядка требует синхронного обновления ObservationContract и Python-стороны.

### 3.3 UnitDefinition (ScriptableObject)

Параметры одного типа юнита:

| Поле | Тип | Назначение |
|------|-----|-----------|
| `unitType` | UnitType | Тип, которому принадлежит ассет |
| `displayName` | string | Человекочитаемое имя |
| `maxHitPoints` | int | Базовые HP (default: 5) |
| `attackDamage` | int | Урон за атаку (default: 1) |
| `attackRange` | int | Дальность в клетках (default: 1) |
| `moveSpeed` | int | Клеток за тик (default: 1) |
| `productionCost` | int | Стоимость производства (default: 1) |
| `isBuilding` | bool | Строение (статично, не перемещается) |
| `productionTime` | int | Тиков для производства (default: 5) |
| `prefab` | GameObject | Визуальный prefab |

Создаётся через: `Assets > Create > RTS > Unit Definition`

Эталонные ассеты:
- `Assets/ML/UnitDefs/UnitDef_Base.asset`
- `Assets/ML/UnitDefs/UnitDef_Worker.asset`
- `Assets/ML/UnitDefs/UnitDef_Resource.asset`

### 3.4 GameConfig (ScriptableObject)

Эталонный сценарий матча — один ассет = один воспроизводимый вариант:

| Поле | Тип | Назначение |
|------|-----|-----------|
| `scenarioName` | string | Имя в логах/CSV (default: `MVP_24x24_Symmetric`) |
| `scenarioNotes` | string | Текстовое описание |
| `mapWidth` / `mapHeight` | int | Размер карты (из GameConstants) |
| `startResources` | int | Стартовые ресурсы (из GameConstants) |
| `maxEpisodeSteps` | int | Лимит шагов (из GameConstants) |
| `unitDefinitions[7]` | UnitDefinition[] | По одному на каждый UnitType enum |

Утилита: `GetDefinition(UnitType)` — возвращает UnitDefinition по типу.  
Валидация в `OnValidate()`: предупреждение если `unitDefinitions.Length != 7`.

---

## IV. Observation Contract

**Файл:** `Assets/Scripts/ML/ObservationContract.cs`  
**Namespace:** `RTS.ML`

### 4.1 Размеры тензора

| Параметр | Значение |
|----------|---------|
| Shape | [24, 24, 27] (height × width × channels) |
| Data type | float32 |
| Range | [0, 1] normalized |
| Total floats | 15552 |
| Flatten order | Row-major by cell, then channel |

```
flat_index = (row * 24 + col) * 27 + channel
```

Вспомогательный метод: `ObservationContract.FlatIndex(row, col, ch)`

### 4.2 Canal Map (27 каналов)

| Канал | Имя | Тип | Нормализация |
|-------|-----|-----|-------------|
| [0] | `hit_points` | Scalar | hp / MaxHitPoints |
| [1] | `resources` | Scalar | r / MaxResourcesPerPatch |
| [2–4] | `owner` | One-hot | Neutral / Player1 / Player2 |
| [5–11] | `unit_type` | One-hot | Resource..Ranged (7 значений) |
| [12–17] | `current_action` | One-hot | NoOp..Attack (6 значений) |
| [18–21] | `action_direction` | One-hot | North..West (4 значения) |
| [22–25] | `produce_unit_type` | One-hot | Worker..Ranged (4 значения) |
| [26] | `attack_target` | Scalar | (localIndex+1)/9f, 0=no-target |

Итого: 2 + 3 + 7 + 6 + 4 + 4 + 1 = **27 каналов**.

### 4.3 Совместимость с Gym-μRTS

- Структура выровнена с Gym-μRTS v0.6.1
- Terrain/walls-канал **намеренно исключён** (нет стен в MVP сценарии)
- `attack_target[26]`: observation-side encoding, не runtime-preserving truth (зафиксировано в Week 4)
- Reference layer vs Unity MVP layer формализованы в Week 3 (`LegacyGymCompatibleSpec` / `UnityMvpTransferSpec`)

### 4.4 Вспомогательные методы ObservationContract

| Метод | Назначение |
|-------|-----------|
| `FlatIndex(row, col, ch)` | Плоский индекс в буфере [15552] |
| `SetOneHot(obs, base, count, hotIndex)` | Заполнение one-hot среза |

---

## V. Action Contract

**Файл:** `Assets/Scripts/ML/ActionContract.cs`  
**Namespace:** `RTS.ML`

### 5.1 Структура пространства действий

Глобальная политика с действием на **каждую клетку** сетки:

| Параметр | Значение |
|----------|---------|
| Ветвей на клетку | 7 (`ActionBranchCount`) |
| Flat размер на клетку | 35 (`ActionFlatSize`) |
| Ячеек | 576 (24 × 24) |
| Итого flat за шаг | 20160 (`TotalActionFlatSize`) |

### 5.2 Ветви действий

| Ветвь | Индекс | Размер | Значения |
|-------|--------|--------|---------|
| `BRANCH_ACTION_TYPE` | 0 | 6 | 0=NoOp, 1=Move, 2=Harvest, 3=Return, 4=Produce, 5=Attack |
| `BRANCH_MOVE_DIR` | 1 | 4 | 0=N, 1=E, 2=S, 3=W |
| `BRANCH_HARVEST_DIR` | 2 | 4 | 0=N, 1=E, 2=S, 3=W |
| `BRANCH_RETURN_DIR` | 3 | 4 | 0=N, 1=E, 2=S, 3=W |
| `BRANCH_PRODUCE_DIR` | 4 | 4 | 0=N, 1=E, 2=S, 3=W |
| `BRANCH_PRODUCE_UNIT_TYPE` | 5 | 4 | 0=Worker, 1=Light, 2=Heavy, 3=Ranged |
| `BRANCH_ATTACK_TARGET` | 6 | 9 | индекс в local 3×3 (0..8, центр=4) |

### 5.3 Attack Target Local 3×3

```
0 1 2
3 4 5
6 7 8
```

`AttackOffsets[(idx)]` → `(dRow, dCol)` смещение относительно атакующего юнита.

### 5.4 BranchOffset — Flat encoding

Совместимо с Gym-μRTS flat action encoding:
```
flat = sum(branch_sizes[0..i-1]) + branch_value[i]
```

Метод `ActionContract.BranchOffset(branch)` возвращает смещение ветви в flat-векторе.

### 5.5 Ограничения (зафиксированы в контракте)

- Attack targeting намеренно ограничен local 3×3 (не full map)
- Барраки и более широкое production space — за пределами MVP контракта
- Контракт — это transfer-compatible MVP surface, не claim о полной Gym parity

---

## VI. Logging

**Файл:** `Assets/Scripts/Logging/ExperimentLogger.cs`  
**Namespace:** `RTS.Logging`

### 6.1 Устройство логгера

Singleton MonoBehaviour, пишет CSV в `Application.persistentDataPath/Logs/`:

```
{scenarioName}_{runName}_{yyyyMMdd_HHmmss}.csv
```

### 6.2 CSV-схема

```
episode, steps, reward, win, invalid_rate,
resources_p1_at_ref, resources_p2_at_ref,
builds_p1_at_ref, builds_p2_at_ref, timestamp_utc
```

### 6.3 Публичный API

| Метод / Поле | Назначение |
|--------------|-----------|
| `scenarioName` | Имя сценария (в каждой строке CSV) |
| `runName` | Имя эксперимента (`transfer` / `from_scratch`) |
| `referenceStep` | Шаг для snapshot ресурсов/построек (default: 500) |
| `LogEpisodeBegin()` | Сброс счётчиков нового эпизода |
| `LogStep(reward, isInvalid, p1res, p2res, p1builds, p2builds)` | Накопление шага |
| `LogEpisodeEnd(win)` | Запись строки CSV |

### 6.4 Статус сцены

> ⚠️ ExperimentLogger реализован в коде, но не подключён в `GameScene.unity` на протяжении Week 1–2 (поле `_experimentLogger: {fileID: 0}`). Подключение — задача Stage 4 интеграции.

---

## VII. Editor Tools

**Файл:** `Assets/Scripts/Editor/GameConfigCreator.cs`  
**Namespace:** `RTS.Editor`

### 7.1 GameConfigCreator

Утилита создания эталонного GameConfig через меню `RTS > Create MVP GameConfig`:
- Создаёт `Assets/ML/GameConfig_MVP.asset`
- Заполняет scenarioName, mapWidth/Height, startResources, maxEpisodeSteps
- Прописывает ссылки на UnitDefinition ассеты (если найдены)

### 7.2 GameConfig_MVP.asset

Эталонный конфигурационный ассет:

| Параметр | Значение |
|----------|---------|
| scenarioName | `MVP_24x24_Symmetric` |
| mapWidth / mapHeight | 24 / 24 |
| startResources | 5 |
| maxEpisodeSteps | 2000 |
| unitDefinitions | Wired for Resource / Base / Worker |

> Это `единственный` канонический конфиг для всех экспериментальных запусков. Не создавать альтернативных конфигов без явного обоснования.

---

## VIII. Совместимость с Gym-μRTS

Week 1 закладывает baseline совместимость, которую Week 3 формализует:

### Гарантированная совместимость (Week 1)

| Аспект | Статус |
|--------|--------|
| Observation shape [H, W, 27] | ✅ Выровнен с Gym-μRTS v0.6.1 |
| Channel order (hp, res, owner, unit_type, action, dir, produce, attack) | ✅ Совпадает с reference |
| UnitType enum order (Resource=0..Ranged=6) | ✅ Совпадает |
| Action branches (7 ветвей per cell) | ✅ Совпадает |
| Action flat encoding convention | ✅ Совпадает |
| Total flat sizes (15552 obs / 20160 action) | ✅ Совпадает |

### Намеренные расхождения (зафиксированы)

| Аспект | Расхождение | Обоснование |
|--------|------------|-------------|
| Terrain / walls channel | Отсутствует | Нет стен в MVP сценарии |
| Attack targeting | Local 3×3 вместо full-map | MVP reduction |
| Barracks / additional production | Не в MVP action space | Scope ограничен |

> Полный список gap'ов формализован в `WEEK3_COMPATIBILITY_GAP_LIST.md`.

---

## IX. Известные ограничения Week 1

| Ограничение | Последствие |
|-------------|------------|
| **Контракты без исполняемой логики** | ObservationContract и ActionContract — документация, а не working code. Реализация в Week 2–3. |
| **ExperimentLogger не подключён в сцену** | CSV-логирование не работает из коробки (нет сцены в Week 1) |
| **GameConfig не валидируется против реального спавна** | Проверка только через `OnValidate()` — runtime verification в Week 2 |
| **attack_target[26] семантика не полностью определена** | Окончательная семантика канала финализирована в Week 4 Day 5 |
| **Global features (observation)** | Не включены в Week 1 контракт — добавлены в `UnityMvpTransferSpec` Week 3 |

---

## X. Условия входа в Week 2

Week 2 опирается на все Week 1 артефакты как **стабильный фундамент**:

### Что Week 2 предполагает как гарантию от Week 1:

| Артефакт | Ожидание Week 2 |
|----------|----------------|
| `GameConstants` | Все числовые константы берутся отсюда (не хардкодятся) |
| `UnitType` / `Owner` / enums | Единственный источник истины для типов |
| `UnitDefinition` | ScriptableObject-параметры юнитов готовы и выровнены с enum |
| `GameConfig` / `GameConfig_MVP.asset` | Конфиг-ассет готов, подключается в MatchBootstrap |
| `ObservationContract` — канальная структура | Не изменяется в Week 2 (runtime data filling — Week 3) |
| `ActionContract` — ветвевая структура | Не изменяется в Week 2 (decoder/applier — Week 3) |
| `ExperimentLogger` | Код готов, требует только подключения в сцену |

### Handoff summary:

> Week 1 передаёт в Week 2 **полностью зафиксированный технический контракт**: типы данных, числовые константы, формат observation/action и схему логирования. Week 2 не меняет эти контракты — она только добавляет gameplay logic поверх них. Принцип: контракт фиксируется до кода, а не после.

---

## See Also

- [WEEK1_SUMMARY.md](WEEK1_SUMMARY.md) — краткий summary выполненных работ Week 1
- [WEEK2_GAME_FOUNDATION_SUMMARY.md](WEEK2_GAME_FOUNDATION_SUMMARY.md) — следующий (Week 2) слой поверх этого контракта
- [WEEK3_OBSERVATION_AND_ACTION_SUMMARY.md](WEEK3_OBSERVATION_AND_ACTION_SUMMARY.md) — реализация observation/action pipeline (Week 3)
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — полный roadmap проекта, §1–4 (цели, метрики, критерии успеха)

---

*Файл создан при финализации Week 1 как engineering milestone. Не редактировать ретроактивно — фиксирует состояние на 2026-03-16.*
