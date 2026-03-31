# Week 4 Day 4: Стабилизация RL Execution Loop

## Статус
Реализовано.

---

## Цель дня

Свести observation / mask / action / reward / terminal в один стабильный и диагностируемый
RL loop поверх уже существующего Week 3 pipeline и Week 4 Day 1–3 слоёв.

Ключевое требование: не добавлять новый execution path, а формализовать явный
фазовый порядок поверх уже существующих компонентов.

---

## Canonical Execution Order (9 фаз)

```
Phase 1: PreStepCapture   — RewardCollector.CaptureSnapshot (reward baseline)
Phase 2: Observation      — Facade.BuildObservationPackage   (pre-step boundary)
Phase 3: Mask             — Facade.BuildTransferCompatibleMask (same pre-step state)
Phase 4: ActionSubmit     — IDecisionSource.Execute
                             → ActionDecoder → ActionApplier → MatchManager.ApplyCommand
Phase 5: RuntimeStep      — MatchManager.StepMatch() РОВНО ОДИН РАЗ
Phase 6: PostStepCapture  — RewardCollector.CaptureSnapshot (post-step state)
Phase 7: RewardEval       — RewardCollector.EvaluateStep (post-step effects)
Phase 8: TerminalEval     — EpisodeTerminalEvaluator.Evaluate (post-step state)
Phase 9: StepReport       — RlLoopStepReport с per-phase диагностикой
```

### Pre-step boundary
Фазы 1–3 все читают runtime state **до** `StepMatch`.
Инвариант: ни одна мутация runtime не происходит между фазами 1 и 3.

### Post-step boundary
Фазы 6–8 читают runtime state **после** `StepMatch`.
Инвариант: reward и terminal никогда не вычисляются из pre-step state.

---

## Новые компоненты

### `RlLoopCoordinator` (Assets/Scripts/ML/RlLoopCoordinator.cs)

Чистый C# класс (не MonoBehaviour). Создаётся и владеется `EpisodeController`.

Обязанности:
- Обеспечить выполнение фаз 1–9 в правильном порядке за один вызов `ExecuteFullStep`.
- Собирать `RlLoopStepReport` как диагностику шага.
- Держать anti-double-step guard (`_runtimeStepAdvancedThisCycle`).
- Сбрасывать состояние между эпизодами через `ResetLoop()`.

```csharp
// Использование (EpisodeController):
RlLoopStepReport report = _rlLoopCoordinator.ExecuteFullStep(_rewardPerspective, decisionSource);
```

### `RlLoopStepReport` (struct)

Диагностический отчёт одного шага. Хранит:

| Поле | Что показывает |
|---|---|
| `StepIndex` | Номер шага в эпизоде |
| `SourceMode` | Режим источника действий |
| `ObservationBuilt` | Был ли построен observation на pre-step |
| `MaskBuilt` | Была ли построена mask на pre-step |
| `ActionApplied` | Было ли принято хотя бы одно действие |
| `ActionsAccepted/Rejected` | Счётчики (точные для RL path, проксированные для baseline) |
| `RuntimeStepAdvanced` | Был ли вызван StepMatch |
| `DoubleStepPrevented` | Guard флаг (double-step попытка была заблокирована) |
| `RewardEmitted` | Был ли ненулевой reward |
| `RewardTotal` | Сумма reward за шаг |
| `TerminalEvaluated` | Была ли считана terminal оценка |
| `IsTerminal / TerminalReason` | Terminal результат |
| `RewardTrace` | Полный RewardStepTrace |
| `TerminalResult` | Полный TerminalEvaluationResult |

Метод `BuildDiagnosticLine()` — компактная однострочная диагностика для console.

### `IDecisionSource` (interface)

Контракт источника действий для Phase 4.

```csharp
public interface IDecisionSource
{
    string SourceMode { get; }
    PolicyExecutionReport Execute(MlPolicyPipelineFacade facade, Owner perspective, ActionMaskSet maskAtBoundary);
}
```

**Обязательный контракт:** реализации не могут вызывать `MatchManager.StepMatch()`.

### `BaselineDecisionSource`

Wraps `HeuristicPolicyAdapter.ExecuteDecisionStep()`.
Обрабатывает обоих игроков за один вызов (self-play режим).
`SourceMode = "baseline-heuristic"`.

### `LegacyDecisionSource`

Wraps `HeuristicDriver.MakeAllDecisions()`.
Используется как fallback когда `HeuristicPolicyAdapter` не подключён,
или при `HeuristicExecutionPath.LegacyDirectDriver`.
`SourceMode = "baseline-legacy"`.

### `IdleDecisionSource`

Singleton. Не подаёт никаких действий.
Используется когда `_useHeuristicAI = false` (пассивный режим наблюдения).
`SourceMode = "idle"`.

---

## Изменения в EpisodeController

### Новые поля
- `private MlPolicyPipelineFacade _policyPipelineFacade` — facade для obs/mask в координаторе
- `private RlLoopCoordinator _rlLoopCoordinator` — канонический loop coordinator
- `[SerializeField] private bool _logRlLoopDiagnostics` — включить per-step лог в консоль

### Новое свойство
- `public RlLoopStepReport LastRlLoopStepReport` — последний отчёт шага

### Рефакторинг `StepMatchWithHeuristics()`
Метод теперь делегирует полностью в `_rlLoopCoordinator.ExecuteFullStep()`.
Вся логика выбора источника действий вынесена в `BuildDecisionSource()`.
Прямые вызовы `_matchManager.StepMatch()`, `_runtimeRewardCollector.CaptureSnapshot()`,
`_runtimeRewardCollector.EvaluateStep()` из EpisodeController **удалены** — они теперь
живут исключительно внутри `RlLoopCoordinator.ExecuteFullStep()`.

### `BuildDecisionSource()`
Фабричный метод: по текущим настройкам `_useHeuristicAI` и `_heuristicExecutionPath`
возвращает нужный `IDecisionSource`. Все варианты удовлетворяют фазовому контракту.

### `ResolveReferences()` добавлено
Создание `_policyPipelineFacade` и `_rlLoopCoordinator` при наличии зависимостей.

---

## Согласование baseline и future RL path

Baseline/heuristic и будущий ML-Agent path — **два разных источника действий** (Phase 4),
но **один и тот же фазовый порядок** (фазы 1–9 в `RlLoopCoordinator`).

| Путь | IDecisionSource | Фазовый порядок |
|---|---|---|
| Baseline (heuristic) | `BaselineDecisionSource` | Фазы 1–9 в координаторе |
| Legacy (direct driver) | `LegacyDecisionSource` | Фазы 1–9 в координаторе |
| Idle | `IdleDecisionSource` | Фазы 1–9 в координаторе |
| Future RL (ML-Agent) | `PolicyDecisionSource` (будущий) | Фазы 1–9 в координаторе |

Baseline path теперь является **control mode** для RL loop debugging:
он проходит через ту же observation/mask/action/reward/terminal фазовую логику.

---

## Anti-Double-Step Guard

В `RlLoopCoordinator`:
- `_runtimeStepAdvancedThisCycle` — bool флаг
- Устанавливается в `true` в начале Phase 5
- Сбрасывается в `false` в конце Phase 9 (начало следующего цикла)
- Если фаза 5 вызывается повторно внутри одного `ExecuteFullStep` → `Debug.LogError` + step заблокирован
- В `RlLoopStepReport.DoubleStepPrevented = true` — сигнал для диагностики

В `EpisodeController`:
- `StepMatchWithHeuristics()` больше не вызывает `_matchManager.StepMatch()` напрямую
- Единственный вызов `StepMatch` живёт в Phase 5 координатора

---

## Obs/Mask Timing Consistency

**Инвариант:** Фазы 2 и 3 (observation и mask) выполняются в одном pre-step окне.
Ни одна мутация runtime state не происходит между ними.

**Dual facade note:** Координатор держит свою `MlPolicyPipelineFacade` для obs/mask.
`HeuristicPolicyAdapter` держит свою. Обе читают с одного и того же runtime state (pre-step),
поэтому дают одинаковые результаты. Для будущего ML-Agent consumer
obs и mask из координатора будут использоваться напрямую (Phase 2, 3 → Phase 4 bridge).

---

## Step Diagnostics

Чтобы включить:
- В Inspector EpisodeController → `Log Rl Loop Diagnostics = true`

Формат (пример):
```
[RlLoop] step=42 src=baseline-heuristic obs=True mask=True action=accepted:0/rejected:0 runtimeStep=True doubleGuard=False reward=0.0520 terminal=False(None)
```

Чтобы отлавливать конкретные проблемы:
| Проблема | Что искать в отчёте |
|---|---|
| Double-step | `doubleGuard=True` → `Debug.LogError` в консоли |
| Wrong-phase reward | `reward != 0` когда `runtimeStep=False` |
| Wrong-phase terminal | `terminal=True` когда `runtimeStep=False` |
| Obs/mask mismatch | `obs=True, mask=False` или наоборот |
| Missing action | `src=idle` при ожидаемом heuristic режиме |
| Baseline vs RL mismatch | Сравнить `SourceMode` между режимами |

---

## Ограничения Day 4 (сознательно не делается)

1. **Нет полной ML-Agent integration.** `PolicyDecisionSource` — заглушка для будущего дня.
2. **Reward design не изменён.** Конфигурация `RewardConfig.CreateV1Defaults()` не тронута.
3. **Нет extended ML-Agent sensor/actuator wiring.** Week 4 Day 5+ тема.
4. **Attack semantics gap не закрыт.** Действует hard constraint из 29 March 2026:
   attack intent ≠ strict target-preserving runtime semantics.
5. **Baseline action counts в `RlLoopStepReport` = 0** для `BaselineDecisionSource` и
   `LegacyDecisionSource`: AuthoritativeApplier counts accessible через
   `MatchManager.InvalidCommandsLastStep`, не через IDecisionSource boundary.
6. **Нет нового reward design.** Выходит за рамки этого дня.

---

## Проверочные сценарии (соответствие целям дня)

| Сценарий | Ожидаемое поведение |
|---|---|
| Baseline делает ровно один StepMatch на цикл | `RuntimeStepAdvanced=True`, `DoubleStepPrevented=False` |
| Reward появляется после RuntimeStep | `RewardTrace.Step` совпадает со `StepIndex` |
| Terminal читается после RuntimeStep | `terminalResult` отражает post-step состояние |
| Obs/mask из одного pre-step state | `ObservationBuilt=True AND MaskBuilt=True` всегда вместе |
| Reset не ломает loop state | `ResetLoop()` → `StepIndex=0`, флаги сброшены |
| Baseline и idle имеют одинаковую фазовую логику | Оба идут через фазы 1–9, `SourceMode` различается |

---

## Итог дня

- Есть стабильный и диагностируемый RL loop поверх Week 3 pipeline.
- Baseline/heuristic path является контрольным режимом того же RL-ready loop.
- Observation, mask, action, reward и terminal выполняются в явном согласованном
  фазовом порядке, видимом в `RlLoopCoordinator`.
- `RlLoopStepReport` позволяет per-step диагностику любой фазы.
- Производственный pipeline Week 3 не изменён.
