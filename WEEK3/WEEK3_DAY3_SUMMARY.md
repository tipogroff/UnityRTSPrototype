# Week 3, Day 3: Action Pipeline — Multi-Command Semantics + Refinements

## Статус: ✓ Реализовано

---

## Что сделано

### 1. AgentAction (без изменений)
Единая промежуточная модель действия — preserved as-is.
- `ActorPosition`, `ActionType`, `Direction`, `ProduceUnitType`, `AttackTargetPosition`
- `IsValid`, `InvalidationReason`, `SourceType` (TransferCompatible | Debug)
- `CreateNoOp()`, `CreateInvalid()` — factory helpers

### 2. ActionDecoder — Multi-Command Decoding

**Новый основной метод:**
```csharp
List<AgentAction> DecodeTransferCompatibleBatch(int[] actionFlat, Owner playerPerspective)
```
- Сканирует **все** `TotalCells = 576` клеток action input
- Для каждой клетки, где `action_type != NoOp`, формирует `AgentAction` через `TryDecodeCell()`
- Возвращает `List<AgentAction>` — все ненулевые действия за шаг
- Дедупликация актора **НЕ** выполняется здесь — см. ActionApplier

**Обратная совместимость:**
```csharp
AgentAction DecodeTransferCompatible(int[] actionFlat, Owner playerPerspective)
```
Wrapper вокруг `DecodeTransferCompatibleBatch()` — возвращает первое действие из батча или NoOp. Сохранён для совместимости с уже существующими вызовами.

**Debug format** — без изменений:
```csharp
AgentAction DecodeDebug(int actorIndexFlat, int actionType, int direction, int produceUnitType, int attackTargetLocal)
```
Возвращает один `AgentAction`, проходит через тот же downstream pipeline.

### 3. ActionApplier — Conflict Resolution + Batch Apply

**`ApplyActions(IReadOnlyList<AgentAction> actions, Owner playerPerspective)`** — расширен:

#### Phase Gate
Первой проверкой после NoOp-skip в `ApplyAction()` идёт gate:
```csharp
if (_matchManager.Phase != MatchPhase.Running)
    → RecordRejection($"Match is not in Running phase (current: {phase})")
```
Гарантирует, что команды принимаются только в фазе `Running`.

#### Conflict Resolution Policy: First-Wins
- Каждый актор (по `GridPosition`) получает **не более одной команды за шаг**
- Tracking через `HashSet<GridPosition> processedActors` — заполняется при обработке batch
- Первая команда для актора: обрабатывается (`ApplyAction()`)
- Повторная команда для того же актора: отклоняется с reason:
  `"Duplicate command for actor at {pos}: already processed this step (first-wins policy)"`
- NoOp-действия не занимают слот (пропускаются без записи в processedActors)

#### Порядок применения команд внутри батча
Команды применяются в порядке `List<AgentAction>`, который соответствует scan-order `TryDecodeCell()`:
`cell 0 → cell 1 → ... → cell 575` (flat index, row-major Y-major).

**`ApplyAction(AgentAction action, Owner playerPerspective)`** — validation pipeline:
1. NoOp → skip
2. Phase check: `_matchManager.Phase != MatchPhase.Running` → reject
3. GridManager.GetOccupant() — проверка наличия актора
4. Owner match
5. IsAlive
6. IsActionSupportedByUnitType()
7. Action-specific validation (Move/Harvest/Return/Produce/Attack)
8. MatchManager.ApplyCommand()

**Queue busy validation (Produce):** в `ValidateProduceAction()` добавлена проверка:
```csharp
var queue = unit.GetComponent<BuildingRuntime>()?.GetProductionQueue();
if (queue != null && queue.IsProducing)
    → RecordRejection($"Production queue is busy (already producing {queue.CurrentProducingType})")
```

**Coordinate convention — унификация:**
`GetPositionInDirection()` делегирует к `GridPosition.Neighbour(Direction)`. Конвенция:
- North = **+Y**, South = **−Y**, East = **+X**, West = **−X**
- FlatIndex = `Y * MapWidth + X`; `FromFlatIndex(i)` ≡ `new GridPosition(i % W, i / W)`

### 4. AgentAction — `IsValid` уточнён

`IsValid` — это **диагностические метаданные декодера**, не гарантия принятия команды:
```
// IsValid == true означает только, что декодер распознал действие как синтаксически корректное.
// ActionApplier использует цепочку независимых validation-правил и МОЖЕТ отклонить «valid» action.
```
Отклонение `ApplyAction()` — авторитетно. `IsValid` — информативно.

### 5. Smoke Tests — расширены до 12 тестов

| # | Тест | Цель |
|---|------|------|
| 1 | InitialState | Проверка наличия юнита на (2,2) |
| 2 | DebugActionMove | Debug format — Move |
| 3 | DebugActionHarvest | Debug format — Harvest |
| 4 | DebugActionAttack | Debug format — Attack (invalid target = self) |
| 5 | DebugActionProduce | Debug format — Produce |
| 6 | InvalidActorAction | Debug — NoActor marker = NoOp |
| 7 | TransferCompatibleFormat | All-NoOp baseline → NoOp returned |
| **8** | **TransferCompatibleBatch** | **Multi-unit batch: 2 Player1 units → batch size = 2** |
| **9** | **BatchConflictResolution** | **Два действия для одного актора → second rejected** |
| **10** | **PhaseValidation** | **Если phase != Running → действие отклоняется** |
| **11** | **ProduceQueueBusy** | **Если BuildingRuntime.IsProducing → Produce отклоняется** |
| **12** | **CoordinateConvention** | **FlatIndex round-trip + North=+Y assertion** |

---

## Spatial Lookup: разделение ответственности

| Задача | API |
|--------|-----|
| Найти юнита в клетке | `GridManager.GetOccupant(pos)` |
| Найти ресурс в клетке | `ResourceManager.GetResourceNode(pos)` |
| Перечислить всех юнитов | `UnitRegistry.GetAllUnits()` |
| Spatial validation | GridManager (occupancy table) |

`UnitRegistry.GetUnitAt()` — не использовался, т.к. не существует в текущей архитектуре.

---

## Ограничения, которые остаются (Day 4+)

| # | Ограничение | Статус |
|---|-------------|--------|
| 1 | Конфликт целей движения (два юнита хотят занять одну клетку) | ❌ Не реализовано — MatchManager отклонит второй Move |
| 2 | Attack target validation после того, как юнит в этой же клетке уже уничтожен предыдущей командой в батче | ❌ State snapshot не создаётся — применяется к live state |
| 3 | Production cost validation использует захардкоженное значение `unitCost = 50` | ❌ Нужно загружать из UnitDefinition |
| 4 | Batch для Player2 (два игрока в одном шаге) | ❌ Нужно вызывать ApplyActions() дважды |
| 5 | Invalid action masking (policy-side) | ❌ Не реализовано на стороне ML |

---

## Пример использования (transfer-compatible pipeline)

```csharp
// 1. Decode all non-NoOp actions from policy output
var decoder = new ActionDecoder(gridManager, unitRegistry);
List<AgentAction> batch = decoder.DecodeTransferCompatibleBatch(actionFlat, Owner.Player1);

// 2. Apply with conflict resolution (first-wins)
var applier = new ActionApplier(gridManager, unitRegistry, matchManager, resourceManager);
int accepted = applier.ApplyActions(batch, Owner.Player1);

// 3. Read diagnostics
Debug.Log($"Accepted: {accepted}, Rejected: {applier.RejectedActionsLastStep}");
foreach (var reason in applier.RejectionReasonsLastStep)
    Debug.LogWarning($"  Rejection: {reason}");
```

## Пример использования (debug pipeline — без изменений)

```csharp
// Single action — wraps into same downstream pipeline
AgentAction action = decoder.DecodeDebug(actorFlatIndex, actionType, dir, produceType, attackLocal);
bool ok = applier.ApplyAction(action, Owner.Player1);
```
