# Week 2: Game Foundation — Итоговый Summary

**Дата:** 19 марта 2026 (Финализация 2 апреля 2026)  
**Статус:** ✅ ЗАВЕРШЕНА как documented game foundation layer  
**Область:** Vertical slice RTS без ML — сцена, сетка, юниты, экономика, бой, эпизодный цикл  

---

## I. Обзор Week 2

Week 2 завершена как **автономный игровой срез RTS** без ML-управления. Основная цель — построить минимальный детерминированный матч, который корректно инициализируется, проходит через экономику и бой, и сбрасывается для следующего эпизода.

### Основные артефакты Week 2:

1. **GameScene.unity** — рабочая сцена с полной иерархией объектов
2. **Grid System** — GridManager (24×24), GridPosition, валидация занятости
3. **Unit System** — UnitModel (данные) / UnitRuntime (MonoBehaviour) / UnitFactory / UnitRegistry
4. **Economy System** — ResourceNode / ResourceManager / PlayerState / ProductionQueue
5. **Match Lifecycle** — MatchManager / MatchBootstrap / EpisodeController / VictoryResolver
6. **Combat** — CombatResolver, атака, уничтожение юнитов, победные условия
7. **Logging** — ExperimentLogger (CSV) — код готов, в сцену не подключён на момент аудита

### Рамки Week 2 (честно)

Week 2 **не делает**:
- ❌ ML-интерфейс (observation/action/mask) — это Week 3
- ❌ RL-контур (reward/terminal logic) — это Week 4
- ❌ Stable multi-episode auto loop без ручного вмешательства (известный пробел)
- ❌ Full smoke test CI — smoke helpers имеют баги логики

---

## II. Архитектура сцены

### 2.1 Корневые GameObject-объекты (GameScene.unity)

| GameObject | Назначение | MonoBehaviour |
|------------|-----------|---------------|
| `GridManager` | Сетка занятости | `GridManager` |
| `MatchManager` | Основной MatchPhase + ресурсы сторон | `MatchManager` |
| `MatchBootstrap` | Инициализация матча из GameConfig | `MatchBootstrap` |
| `UnitRegistry` | Активный реестр юнитов | `UnitRegistry` |
| `ResourceManager` | Реестр ресурсных патчей | `ResourceManager` |
| `EpisodeController` | Главный игровой цикл / сброс | `EpisodeController` *(нужна ручная настройка)* |
| `VictoryResolver` | Проверка победных условий | `VictoryResolver` *(нужна ручная настройка)* |
| `Main Camera` | Камера сцены | — |
| `Directional Light` | Освещение | — |

> ⚠️ На момент аудита (2026-03-19): `EpisodeController` и `VictoryResolver` реализованы в коде, но ещё **не добавлены в сцену** как компоненты.

### 2.2 Prefabs

| Файл | Назначение |
|------|-----------|
| `Assets/Prefabs/Base.prefab` | Строение-база |
| `Assets/Prefabs/Worker.prefab` | Рабочий юнит |
| `Assets/Prefabs/ResourceNode.prefab` | Ресурсный патч |
| `Assets/Prefabs/Resource.prefab` | Визуальный ресурсный куб (0.6×0.6×0.6, зелёный) |

### 2.3 Config и UnitDefinition Assets

| Файл | Содержимое |
|------|-----------|
| `Assets/ML/GameConfig_MVP.asset` | Сценарий: 24×24, 5 ресурсов, 2000 шагов, maxWorkerLimit=2 |
| `Assets/ML/UnitDefs/UnitDef_Base.asset` | Параметры базы |
| `Assets/ML/UnitDefs/UnitDef_Worker.asset` | Параметры рабочего |
| `Assets/ML/UnitDefs/UnitDef_Resource.asset` | Параметры ресурсного патча |

---

## III. Grid System

**Файлы:**
- `Assets/Scripts/Gameplay/Grid/GridPosition.cs`
- `Assets/Scripts/Gameplay/Grid/GridManager.cs`

### 3.1 GridPosition

Структура данных (чистая, без MonoBehaviour):
- `int X`, `int Y` — координаты клетки
- Вспомогательные методы: `IsValid(width, height)`, `Equals`, `ToString`
- Используется повсеместно как canonical grid coordinate type

### 3.2 GridManager

Singleton-компонент, управляет сеткой занятости и разрешением перемещений:

| Метод | Назначение |
|-------|-----------|
| `InitGrid(w, h)` | Создаёт массив занятости [w, h] |
| `IsOccupied(pos)` | Проверяет занятость клетки |
| `GetUnitAt(pos)` | Возвращает юнит в клетке (или null) |
| `RegisterUnit(unit, pos)` | Занимает клетку |
| `UnregisterUnit(unit, pos)` | Освобождает клетку |
| `MoveUnit(unit, from, to)` | Атомарное перемещение с проверками |
| `GetFreeAdjacentCell(pos)` | Для автоспавна производимых юнитов |

### 3.3 Правила валидации перемещения

- Целевая клетка должна быть свободна
- Целевая клетка должна быть в пределах карты
- Юнит в `from` должен совпадать с тем, что зарегистрировано (иначе — occupancy desync ошибка)

> ⚠️ Известная проблема: при двойном старте матча (`MatchBootstrap.Start` + `EpisodeController.Start` оба вызывают `Setup()`) возникает occupancy drift — GridManager видит несоответствие между зарегистрированным и запрашиваемым юнитом.

---

## IV. Unit System

**Файлы:**
- `Assets/Scripts/Gameplay/Entities/UnitModel.cs`
- `Assets/Scripts/Gameplay/Entities/UnitRuntime.cs`
- `Assets/Scripts/Gameplay/Entities/UnitFactory.cs`
- `Assets/Scripts/Gameplay/Entities/UnitRegistry.cs`
- `Assets/Scripts/Gameplay/Entities/BuildingRuntime.cs`

### 4.1 Двухслойная модель юнита

**UnitModel** — чистая data model (без Unity dependency, без MonoBehaviour):
- `UnitType Type`, `Owner Owner`
- `int CurrentHP`, `int MaxHP`
- `GridPosition GridPosition`
- `int CarriedResources`
- `bool IsAlive`
- Методы: `TakeDamage(amount)`, `AddCarried(amount)`, `DropCarried()`, `ResetForEpisode()`

**UnitRuntime** — MonoBehaviour-адаптер над UnitModel:
- Синхронизирует `transform.position` при изменении `GridPos`
- Предоставляет backward-compatible API: `Type`, `Owner`, `HP`, `GridPos`, `TakeDamage()`
- `MoveTo(GridPosition, GridManager?)` — перемещение с опциональной проверкой через GridManager
- `SetFacing(Direction)` — ориентация юнита (для визуала)
- `OnDestroy()` — автоматически снимает регистрацию из UnitRegistry

### 4.2 UnitFactory

Единый централизованный путь спавна юнитов:
```
UnitFactory.Spawn(type, owner, position, definitions, config)
  → создаёт UnitRuntime (Instantiate prefab)
  → валидирует определение + клетку
  → регистрирует в GridManager
  → регистрирует в UnitRegistry
```

Возвращает `UnitRuntime`. Бросает исключение, если клетка занята или тип не найден.

### 4.3 UnitRegistry

Реестр всех активных юнитов в матче:

| Метод | Назначение |
|-------|-----------|
| `Register(unit)` | Добавить юнит |
| `Unregister(unit)` | Убрать юнит |
| `GetAllUnits()` | Все активные юниты |
| `GetUnitsByOwner(owner)` | Юниты по стороне |
| `GetBuildingsByOwner(owner)` | Строения по стороне |
| `Clear()` | Полный сброс для ResetEpisode |

### 4.4 BuildingRuntime

MonoBehaviour для баз с поддержкой производства:
- `StartProducingUnit(unitType, config)` — начало производства (проверяет ресурсы)
- `TickProduction()` — шаг производства за тик
- Автоспавн произведённого юнита в свободную соседнюю клетку
- `OnUnitProduced` event → регистрация в PlayerState

---

## V. Economy System

**Файлы:**
- `Assets/Scripts/Gameplay/Entities/ResourceNode.cs`
- `Assets/Scripts/Gameplay/Economy/ResourceManager.cs`
- `Assets/Scripts/Gameplay/Economy/PlayerState.cs`
- `Assets/Scripts/Gameplay/Economy/ProductionQueue.cs`

### 5.1 ResourceNode

Чистая data model ресурсного патча:
- `GridPosition`, `int MaxResources` (`GameConstants.MaxResourcesPerPatch = 20`)
- `int CurrentResources`, `bool IsExhausted`
- `Harvest(amount)` → возвращает фактически добытое количество
- `ResetForEpisode()`, `SetGridPosition()`
- `OnResourceExhausted` event при полном истощении

### 5.2 ResourceManager

Singleton-реестр всех ResourceNode в сцене:

| Метод | Назначение |
|-------|-----------|
| `RegisterResourceNode(node, pos)` | Зарегистрировать патч |
| `GetResourceNode(pos)` | Найти патч по позиции |
| `GetAllResourceNodes()` | Все патчи |
| `GetActiveResourceCount()` | Сколько патчей с ресурсами |
| `GetTotalAvailableResources()` | Суммарно доступно ресурсов |

### 5.3 PlayerState

Централизованное хранение экономических данных стороны:
- `Owner Owner`
- `int CurrentResources`, `int BuildingCount`, `int UnitCount`
- `int EnemyUnitsKilled`, `int OwnUnitsLost`
- `CanAfford(cost)`, `SpendResources(cost)`, `AddResources(amount)`
- `RegisterUnit*()`, `RegisterBuilding*()` — счётчики
- `ResetForEpisode()`
- `OnResourcesChanged(newAmount)`, `OnInsufficientResources(cost)` events

### 5.4 ProductionQueue

Очередь производства для строения (упрощённая, 1 юнит одновременно):
- `StartProduction(unitType, definition)` — старт с базовыми проверками
- `AdvanceProduction()` → возвращает `true` при завершении
- `CancelProduction()`, `ResetForEpisode()`
- `IsProducing`, `ProductionProgress [0, 1]`
- `OnProductionComplete(unitType, buildingPos)` event

### 5.5 Экономический цикл (целевой)

```
Worker harvest adjacent ResourceNode
→ ResourceNode.Harvest(1) → worker carries +1
→ Worker return to base
→ PlayerState.AddResources(carried)
→ BuildingRuntime.StartProducingUnit() if affordable
→ BuildingRuntime.TickProduction() каждый шаг
→ OnProductionComplete → UnitFactory.Spawn()
```

> ⚠️ Известная проблема: HeuristicDriver проверяет ресурс в клетке под воркером, а команда Harvest действует на соседнюю клетку — несоответствие контракта нарушает автоматический экономический цикл в heuristic-режиме.

---

## VI. Match Lifecycle

**Файлы:**
- `Assets/Scripts/Gameplay/Match/MatchManager.cs`
- `Assets/Scripts/Gameplay/Match/MatchBootstrap.cs`
- `Assets/Scripts/Gameplay/Match/EpisodeController.cs`
- `Assets/Scripts/Gameplay/Match/VictoryResolver.cs`

### 6.1 MatchManager

Центральный стейт-машина матча:

| Часть API | Назначение |
|-----------|-----------|
| `MatchPhase` enum | `Preparing / Active / Ended` |
| `resources[2]` | Ресурсы каждой стороны `[Owner.Player1, Owner.Player2]` |
| `BeginMatch()` | Перейти в `Active` |
| `ResetMatch()` | Очистить стейт, вернуться в `Preparing` |
| `AdvanceStep()` | Один игровой тик |
| `GetResources(owner)` | Ресурсы стороны |
| `AddResources(owner, amount)` | Пополнение ресурсов |
| `DeclareWinner(owner)` | Завершить матч с победителем |
| `OnMatchEnded` event | Подписка на завершение матча |
| `ApplyCommand(command)` | Применение команды юнита |

### 6.2 MatchBootstrap

Инициализирует матч из `GameConfig`:
- `Setup()` — точка входа: ValidateConfig → InitGrid → SpawnStartingUnits → SpawnResourcePatches
- `ValidateConfig()` — проверка конфига и UnitDefinitions
- `InitGrid(w, h)` — инициализация GridManager
- `SpawnStartingUnits()` — 180°-симметричный спавн: 1 база + 2 воркера на каждой стороне
- `SpawnResourcePatches()` — расстановка ресурсных патчей
- `Instance` singleton + `GetConfig()` для доступа из других систем

### 6.3 EpisodeController

Главный игровой цикл (singleton):
- `TickProductions()` — шаг производства всех строений за тик
- `CheckEndConditions()` — победа / лимит шагов
- `ResetEpisode()` — полная очистка: UnitRegistry.Clear(), GridManager reset, respawn
- `StartNewEpisode()` — вызывает MatchBootstrap.Setup() и начинает новый матч

> ⚠️ Известная проблема: `MatchBootstrap.Start()` и `EpisodeController.Start()` **оба** вызывают инициализацию при запуске Play Mode, что приводит к двойному спавну и drift занятости сетки.

### 6.4 VictoryResolver

Singleton-чекер победных условий:
- `CheckVictoryConditions()` — проверка каждый шаг
- Победа: все базы оппонента уничтожены (`GetBuildingCount(opponent) == 0`)
- `GetBuildingCount(owner)` — счёт строений для статистики

---

## VII. Combat

**Файл:** `Assets/Scripts/Gameplay/Combat/CombatResolver.cs`

### 7.1 Механика атаки

- Команда атаки передаётся через `MatchManager.ApplyCommand()`
- `CombatResolver` разрешает результат атаки: урон, уничтожение
- Уничтоженный юнит удаляется из сцены и снимает регистрацию из UnitRegistry
- `UnitRuntime.OnDestroy()` автоматически вызывает `UnitRegistry.Unregister()`

### 7.2 Победное условие

- `VictoryResolver.CheckVictoryConditions()` проверяет после каждого шага
- Победная логика: `GetBuildingsByOwner(opponent).Count == 0`
- При победе вызывает `MatchManager.DeclareWinner(winner)` → `OnMatchEnded` event

### 7.3 Терминация по лимиту шагов

- `EpisodeController` отслеживает число шагов эпизода
- При достижении `GameConfig.MaxSteps (2000)` → ничья / forced terminal
- Сброс через `ResetEpisode()`

---

## VIII. Logging

**Файл:** `Assets/Scripts/Logging/ExperimentLogger.cs`

### 8.1 Формат CSV

| Поле | Содержимое |
|------|-----------|
| `episode` | Номер эпизода |
| `steps` | Число шагов |
| `win` | Победитель (Player1 / Player2 / Draw) |
| `reward` | Суммарный reward (заполняется Week 4) |
| `invalid_rate` | Доля невалидных действий |
| `resources` | Экономические показатели |
| `builds` | Число производств |

### 8.2 Статус подключения в сцене

> ❌ На момент аудита 2026-03-19: `GameScene.unity` содержит `_experimentLogger: {fileID: 0}` — компонент **не добавлен** и CSV-логирование **не гарантировано** в текущем состоянии сцены.

Для подключения необходимо:
1. Создать GameObject `ExperimentLogger` в сцене
2. Добавить компонент `ExperimentLogger`
3. Подключить ссылку в инспектор поля `MatchBootstrap._experimentLogger`

---

## IX. Известные проблемы и ограничения

Все проблемы зафиксированы в аудите 2026-03-19. Ни одна из них не является блокером для перехода к Week 3.

| # | Проблема | Симптом | Серьёзность |
|---|----------|---------|-------------|
| P1 | **Double bootstrap** | `MatchBootstrap.Start` + `EpisodeController.Start` оба вызывают `Setup()` → duplicate spawn + occupancy drift | Высокая |
| P2 | **Occupancy desync** | `GridManager.MoveUnit` сообщает "registered different unit" во время симуляции | Высокая |
| P3 | **Harvest loop contract mismatch** | `HeuristicDriver` проверяет ресурс в клетке воркера, а `Harvest` команда применяется к соседней клетке | Высокая |
| P4 | **Нет авто-цикла эпизодов** | После terminal-шага следующий эпизод не стартует автоматически без ручного вмешательства | Средняя |
| P5 | **ExperimentLogger не подключён** | CSV-файл не создаётся при стандартном запуске сцены | Средняя |
| P6 | **ManualStepController — legacy Input** | `UnityEngine.Input` бросает `InvalidOperationException` при активном Input System пакете | Низкая |
| P7 | **Баги smoke-test helpers** | `SmokeTestAutomation` останавливает Update после достижения целевых шагов; `SmokeTestMenuRunner` неверно интерпретирует возвращаемое значение `StepMatch()` | Низкая |

### IX.A EpisodeController и VictoryResolver: статус сцены

```
[ ] Assets/Scenes/GameScene.unity — добавить GameObject "EpisodeController"
[ ] Assets/Scenes/GameScene.unity — добавить GameObject "VictoryResolver"
[ ] Опционально: добавить BuildingRuntime к Base-объектам для авто-производства
```

### IX.B Что Week 2 намеренно упростила

- **ProductionQueue**: один юнит одновременно, без очереди ожидания
- **Combat**: базовая атака без модификаторов дальности / брони / terrain
- **Resource balance**: один тип ресурсов, без добычи на расстоянии
- **Victory**: только `all bases destroyed`, без очков или экономической победы
- **Reset**: детерминированный respawn без рандомизации позиций

---

## X. Условия входа в Week 3

Week 3 опирается на Week 2 foundation. Ниже — что должно быть стабильным на момент старта Week 3:

### Что Week 3 предполагает как гарантию от Week 2:

| Компонент | Ожидание Week 3 |
|-----------|----------------|
| `GridManager` | Инициализирован, API `IsOccupied / GetUnitAt` стабильны |
| `UnitRegistry` | `GetAllUnits() / GetUnitsByOwner()` возвращают актуальный список |
| `MatchManager` | `MatchPhase` читается, `ApplyCommand()` принимает команды |
| `ResourceManager` | `GetAllResourceNodes()` возвращает ресурсные патчи |
| `BuildingRuntime` | Читаем `ProductionQueue.IsProducing / CurrentProducingType` |
| `UnitModel.GridPosition` | Позиция юнита консистентна с занятостью GridManager |

### Известные gaps, унаследованные Week 3:

- Double bootstrap (P1) — Week 3 observation pipeline стабильна только если спавн завершён ровно один раз
- Harvest contract mismatch (P3) — heuristic policy Week 3 должна использовать `AgentAction` путь, а не `HeuristicDriver.Update()` логику, чтобы избежать того же бага
- No auto-loop (P4) — smoke tests Week 3 запускаются вручную, multi-episode smoke автоматически не работает

### Handoff summary:

> Week 2 передаёт в Week 3 **работоспособный, но не полностью отлаженный** игровой движок. Observation/Action/Mask pipeline Week 3 строится поверх Grid + UnitRegistry + MatchManager API, не поверх heuristic logic Week 2. Это намеренное проектное решение — рассоединить debug heuristic от ML-facing pipeline.

---

## See Also

- [WEEK2_CLOSURE_CHECKLIST.md](WEEK2_CLOSURE_CHECKLIST.md) — критерий приёмки и протокол верификации Week 2
- [SMOKETEST_GUIDE.md](SMOKETEST_GUIDE.md) — процедура дымового теста эпизодного цикла
- [WEEK3_OBSERVATION_AND_ACTION_SUMMARY.md](WEEK3_OBSERVATION_AND_ACTION_SUMMARY.md) — следующий (Week 3) слой поверх этого foundation
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — полный roadmap проекта

---

*Файл создан при финализации Week 2 как engineering milestone. Не редактировать ретроактивно — фиксирует состояние на 2026-03-19.*
