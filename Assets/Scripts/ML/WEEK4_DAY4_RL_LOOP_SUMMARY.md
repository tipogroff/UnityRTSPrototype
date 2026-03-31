# Week 4 Day 4: Стабилизация RL Execution Loop

## Статус
Реализовано и завершено (finishing pass 31 March 2026).

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
| `ActionsAccepted/Rejected` | Счётчики (реальные для baseline-heuristic, unavailable для legacy/idle) |
| `ActionCountsAvailable` | `true` = реальные counts; `false` = counts unavailable на этой границе |
| `MatchStepDelta` | Изменение match step counter вокруг Phase 5 (норма = 1) |
| `RuntimeStepAdvanced` | Был ли вызван StepMatch |
| `DoubleStepPrevented` | Guard флаг (double-step попытка была заблокирована) |
| `RewardEmitted` | Был ли ненулевой reward |
| `RewardTotal` | Сумма reward за шаг |
| `TerminalEvaluated` | Была ли считана terminal оценка |
| `IsTerminal / TerminalReason` | Terminal результат |
| `RewardTrace` | Полный RewardStepTrace |
| `TerminalResult` | Полный TerminalEvaluationResult |

`BuildDiagnosticLine()` — компактная однострочная диагностика для console.
Формат поля action: `accepted:N/rejected:N` когда `ActionCountsAvailable=true`,
либо `unavailable` когда counts не доступны на данной IDecisionSource границе.

### `IDecisionSource` (interface)

Контракт источника действий для Phase 4.

```csharp
public interface IDecisionSource
{
    string SourceMode { get; }
    PolicyExecutionReport Execute(RlLoopStepInput stepInput);
}
```

**Обязательный контракт:** реализации не могут вызывать `MatchManager.StepMatch()`.

Параметр `RlLoopStepInput` — thin pre-step context bundle из координатора.
Содержит `CanonicalObservation`, `CanonicalMask`, `Facade`, `Perspective`.
Baseline sources могут ссылаться на `CanonicalMask`; будущий `PolicyDecisionSource`
**обязан** использовать его напрямую без rebuild.

### `RlLoopStepInput` (struct)

Thin pre-step context bundle. Создаётся координатором перед Phase 4.
Доставляет canonical obs/mask артефакты из фаз 2–3 на Phase 4 границу.

**Dual-build: residual technical debt (не устранён в Day 4).**
Problema остаётся: `HeuristicPolicyAdapter` всё равно строит obs/mask внутри
`DecideAndApplyInternal`. Per cycle происходят 2 полных obs/mask build'а в baseline режиме.
- Оба фасада читают с одного pre-step state → эквивалентные результаты, корректность не нарушена.
- `RlLoopStepInput` локализует и именует transfer point, но не устраняет второй build.
- Future `PolicyDecisionSource` обязан использовать `stepInput.CanonicalMask` без rebuild.
- Полное устранение требует рефактора `HeuristicPolicyAdapter` для приёма pre-built obs/mask — задача Day 5+.

### `BaselineDecisionSource`

Wraps `HeuristicPolicyAdapter.ExecuteDecisionStepWithCounts()`.
Обрабатывает обоих игроков за один вызов (self-play режим).
Возвращает реальные accepted/rejected counts (0–1 на каждого enabled игрока).
`SourceMode = "baseline-heuristic"`.

### `LegacyDecisionSource`

Wraps `HeuristicDriver.MakeAllDecisions()`.
Используется как fallback когда `HeuristicPolicyAdapter` не подключён.
Возвращает `PolicyExecutionReport.Empty` (CountsAvailable=false):
counts недоступны через HeuristicDriver boundary.
`SourceMode = "baseline-legacy"`.

### `IdleDecisionSource`

Singleton. Не подаёт никаких действий.
Возвращает `PolicyExecutionReport.Empty` (CountsAvailable=false).
`SourceMode = "idle"`.

### `PolicyDecisionSource` [FUTURE INTEGRATION POINT — НЕ РЕАЛИЗОВАН]

Placeholder-заглушка для Week 4 Day 5+.
Конструктор бросает `NotImplementedException`.
Добавлен, чтобы честно обозначить будущую точку интеграции ML-Agent политики.
**Не является реализованным path.** Текущий loop использует BaselineDecisionSource или IdleDecisionSource.

---

## Изменения в EpisodeController

### Новые поля
- `private MlPolicyPipelineFacade _policyPipelineFacade` — facade для obs/mask в координаторе
- `private RlLoopCoordinator _rlLoopCoordinator` — канонический loop coordinator
- `[SerializeField] private bool _logRlLoopDiagnostics` — включить per-step лог в консоль
- `[SerializeField] private bool _rewardLoggingEnabled` — гейтит reward breakdown log
  _(переименован с `_enableRuntimeRewardCollector`; computation always-on в Day 4)_

### Новое свойство
- `public RlLoopStepReport LastRlLoopStepReport` — последний отчёт шага

### Рефакторинг `StepMatchWithHeuristics()`
Метод теперь делегирует полностью в `_rlLoopCoordinator.ExecuteFullStep()`.
Вся логика выбора источника действий вынесена в `BuildDecisionSource()`.

### `BuildDecisionSource()`
Фабричный метод: по текущим настройкам `_useHeuristicAI` и `_heuristicExecutionPath`
возвращает нужный `IDecisionSource`. Все источники удовлетворяют фазовому контракту.

---

## Согласование baseline и future RL path

| Путь | IDecisionSource | Фазовый порядок | Action Counts |
|---|---|---|---|
| Baseline (heuristic) | `BaselineDecisionSource` | Фазы 1–9 в координаторе | Реальные (0–2 per cycle) |
| Legacy (direct driver) | `LegacyDecisionSource` | Фазы 1–9 в координаторе | Unavailable |
| Idle | `IdleDecisionSource` | Фазы 1–9 в координаторе | Unavailable (ноль по design) |
| **Future RL (ML-Agent)** | `PolicyDecisionSource` (**не реализован**) | Фазы 1–9 в координаторе | Будут реальными из ActionApplier |

Baseline path является **control mode** для RL loop debugging — проходит через те же
observation/mask/action/reward/terminal фазы, что и будущий RL path.

---

## Anti-Double-Step Guard

В `RlLoopCoordinator`:
- `_runtimeStepAdvancedThisCycle` — bool флаг
- Устанавливается в `true` в начале Phase 5
- Сбрасывается в `false` в конце Phase 9
- Если Phase 5 вызывается повторно внутри одного `ExecuteFullStep` → `Debug.LogError` + step заблокирован
- В `RlLoopStepReport.DoubleStepPrevented = true` — сигнал для диагностики

**Что гарантирует:**
Не более одного `MatchManager.StepMatch()` внутри одного вызова `ExecuteFullStep()`.

**Что НЕ гарантирует:**
Guard не обнаруживает `StepMatch()`, вызванный из другого компонента вне координатора
(например, из `FixedUpdate` другого MonoBehaviour или тестового хелпера).

### Step Progress Invariant (`[StepInvariant]`)

Координатор фиксирует `matchStepBefore` перед Phase 5 и `matchStepDelta` после.
Норма: `delta = 1`. Если `delta != 1` — `Debug.LogWarning([StepInvariant])`.

Значение `MatchStepDelta` доступно в `RlLoopStepReport` для каждого цикла.
Это lightweight invariant check: не детектирует мутации вне coordinator, но
**явно логирует аномальные StepMatch transitions** (silent no-op, multi-step).

---

## Obs/Mask Timing Consistency и Dual-Build Status

**Инвариант:** Фазы 2 и 3 выполняются в одном pre-step окне.
Ни одна мутация runtime state не происходит между ними.

**Dual-build: residual technical debt (не устранён, локализован и задокументирован):**
- Координатор строит canonical obs/mask в фазах 2–3 через свою `MlPolicyPipelineFacade`.
- `HeuristicPolicyAdapter` строит эквивалентные obs/mask внутри `DecideAndApplyInternal` через свою.
- Обе читают с одного pre-step state (тот же `MatchManager`, `GridManager`) → идентичные результаты.
- Корректность не нарушена, но происходят 2 полных obs/mask build'а per baseline cycle.
- `RlLoopStepInput` локализует проблему: named transfer point, canonical артефакты доступны явно.
- **Что не было сделано**: `HeuristicPolicyAdapter` не рефакторен для приёма pre-built obs/mask.
- **Путь к устранению**: Day 5+ — рефакторинг `HeuristicPolicyAdapter.DecideAndApplyInternal` для приёма `ObservationPackage` и `ActionMaskSet` как параметров вместо rebuild.

---

## `_rewardLoggingEnabled` (переименование)

Поле `_enableRuntimeRewardCollector` переименовано в `_rewardLoggingEnabled`.

**Причина:** reward computation был always-on по архитектуре Day 4 (координатор всегда
вычисляет reward trace). Старое название вводило в заблуждение, намекая на enable/disable
самого вычисления.

**Текущая семантика:** оба флага `_rewardLoggingEnabled` и `_logRewardBreakdown` управляют
только выводом в consoleLog. Reward trace вычисляется в каждом цикле независимо от флагов.

---

## Step Diagnostics

Чтобы включить:
- В Inspector EpisodeController → `Log Rl Loop Diagnostics = true`

Формат (пример, baseline-heuristic с реальными counts):
```
[RlLoop] step=42 src=baseline-heuristic obs=True mask=True action=accepted:2/rejected:0 runtimeStep=True(delta=1) doubleGuard=False reward=0.0520 terminal=False(None)
```

Формат (пример, legacy path с unavailable counts):
```
[RlLoop] step=42 src=baseline-legacy obs=True mask=True action=unavailable runtimeStep=True(delta=1) doubleGuard=False reward=0.0520 terminal=False(None)
```

Чтобы отлавливать конкретные проблемы:
| Проблема | Что искать в отчёте |
|---|---|
| Double-step | `doubleGuard=True` → `Debug.LogError` в консоли |
| Аномальный StepMatch | `delta != 1` → `[StepInvariant] Debug.LogWarning` |
| Wrong-phase reward | `reward != 0` когда `runtimeStep=False` |
| Wrong-phase terminal | `terminal=True` когда `runtimeStep=False` |
| Obs/mask mismatch | `obs=True, mask=False` или наоборот |
| Missing action | `src=idle` при ожидаемом heuristic режиме |
| Counts unavailable | `action=unavailable` → legacy/idle path; ожидаемо |
| Counts available но 0 | `action=accepted:0/rejected:0` → heuristic с нулём активных юнитов |

---

## Ограничения Day 4 (сознательно оставлено)

1. **`PolicyDecisionSource` не реализован.** Это честно задокументированный future integration
   point. Конструктор бросает `NotImplementedException`. ML-Agent wiring — Week 4 Day 5.
2. **Dual-build baseline path: residual technical debt (не blocker, но не устранён).**
   `BaselineDecisionSource` передаёт canonical bundle через `RlLoopStepInput`, но
   `HeuristicPolicyAdapter` всё равно строит эквивалентные obs/mask внутри `DecideAndApplyInternal`.
   2 obs/mask build'а per baseline cycle. Оба читают с одного pre-step state → корректность не нарушена.
   Долг локализован и задокументирован. Устранение: Day 5+ (рефакторинг `HeuristicPolicyAdapter`).
3. **Reward design не изменён.** `RewardConfig.CreateV1Defaults()` не тронут.
4. **Attack semantics gap не закрыт.** Hard constraint 29 March 2026:
   attack intent ≠ target-preserving runtime semantics.
5. **LegacyDecisionSource counts unavailable.** `HeuristicDriver.MakeAllDecisions()` не возвращает
   per-action stats. `RlLoopStepReport` честно сообщает `action=unavailable`.
6. **Anti-double-step guard — scope ограничен.** Guard предотвращает двойной StepMatch
   внутри одного `ExecuteFullStep`. Внешние StepMatch вызовы (из других компонентов)
   guard не видит; `[StepInvariant]` check добавляет lightweight детекцию через `delta`.

---

## Проверочные сценарии (соответствие целям дня)

| Сценарий | Ожидаемое поведение |
|---|---|
| Baseline делает ровно один StepMatch на цикл | `RuntimeStepAdvanced=True`, `DoubleStepPrevented=False`, `MatchStepDelta=1` |
| Reward появляется после RuntimeStep | `RewardTrace.Step` совпадает со `StepIndex` |
| Terminal читается после RuntimeStep | `terminalResult` отражает post-step состояние |
| Obs/mask из одного pre-step state | `ObservationBuilt=True AND MaskBuilt=True` всегда вместе |
| Reset не ломает loop state | `ResetLoop()` → `StepIndex=0`, флаги сброшены |
| Baseline имеет реальные action counts | `ActionCountsAvailable=True`, values 0–2 |
| Legacy/idle — честные unavailable counts | `ActionCountsAvailable=False`, `BuildDiagnosticLine` показывает `unavailable` |
| StepMatch не случился (e.g. match ended) | `MatchStepDelta=0`, warning если `runtimeStepAdvanced=True && delta != 1` |
| Попытка создать PolicyDecisionSource | `NotImplementedException` с явным сообщением |

---

## Итог finishing pass (Day 4)

- **Dual-build baseline path: локализован и задокументирован как residual technical debt.**
  `RlLoopStepInput` создаёт явную Phase 4 boundary с named transfer point.
  Двойной obs/mask build остаётся, корректность не нарушена. Устранение — Day 5+.
- **Baseline counts теперь честные**: `BaselineDecisionSource` вызывает
  `ExecuteDecisionStepWithCounts()` → реальные per-player accepted/rejected counts.
- **Legacy/idle counts честно unavailable**: `BuildDiagnosticLine` показывает
  `action=unavailable` вместо ложного `accepted:0/rejected:0`.
- **Step invariant добавлен**: `MatchStepDelta` фиксирует изменение match step counter
  вокруг Phase 5; warning при anomalous delta.
- **Guard scope явно задокументирован**: гарантия ограничена внутренностью `ExecuteFullStep`.
- **Reward toggle переименован**: `_rewardLoggingEnabled` честно описывает, что только логирование
  controllable; вычисление always-on.
- **`PolicyDecisionSource` оформлен как explicit future point**: stub с `NotImplementedException`.

Day 4 закрыт.
