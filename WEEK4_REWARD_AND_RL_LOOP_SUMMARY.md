# Week 4: Reward и RL Loop — Итоговый Summary

**Дата:** 2 апреля 2026  
**Статус:** ✅ ЗАВЕРШЕНА как documented engineering milestone  
**Область:** Полная архитектура RL-интерфейса, reward design, terminal pipeline, baseline policy  

---

## I. Обзор Week 4

Week 4 завершена как **documented engineering milestone** — не как production ML training, а как стабильный и внятный RL-ready интерфейс в Unity с рабочей baseline-диагностикой.

### Основные артефакты приходящие из Week 4:

1. **RL Interface Complete**
   - Observation contract (27-канальный spatial grid)
   - Action contract (7-ветвевой decision tree)
   - Invalid action masking
   - Deterministic reset + episode lifecycle

2. **Reward System**
   - Четыре reward категории: economy, combat, terminal, shaping
   - Явная collection-layer архитектура (RuntimeRewardCollector)
   - Sanity-check прошла в diagnostic baseline mode

3. **Terminal Pipeline**
   - Explicit terminal reason enumeration (Win, Loss, Draw, Timeout, InvalidRuntimeState)
   - RL-facing terminal derivable из runtime state
   - Distinction между TerminalEventProcessed и TerminalRewardNonZero

4. **Baseline Policy**
   - Heuristic control-mode policy (economy/combat/fallback logic)
   - Запускается через canonical RL loop
   - Используется только для диагностики и sanity-check валидации

### Ограничения (честно)

- Baseline policy узкая (heuristic), не ML-训练
- Outcome distribution в diagnostic mode timeout-dominated
- Outcome diversity остаётся limited (не blocker для Week 4, но carry-over задача)
- Shaping component не явно оптимизирован (placeholder = 0.0)
- Transfer validation не полная (только контракт, не весовой перенос)

### Что Week 4 НЕ делает

- ❌ Не обучает и не интегрирует ML policy (это Week 5)
- ❌ Не делает ложных claims о transfer-готовности (только контракт-совместимость)
- ❌ Не достигает rich outcome diversity в baseline (это диагностический режим)
- ❌ Не решает полный combat-semantics gap (известная резидуальная проблема)

---

## II. Canonical RL Loop — Архитектура

Week 4 фиксирует **canonical phase order** для всех execution paths: baseline heuristic, fut- ure RL, диагностика.

### Фазы за один step:

```
PRE-STEP
  1. observation_t ← ObservationBuilder(state_t)
  2. mask_t ← ActionMaskBuilder(state_t)

DECISION
  3. action_t ← Policy(observation_t, mask_t)
     [Policy могу быть: heuristic, RL agent, test driver]

APPLY
  4. decoded_action ← ActionDecoder(action_t)
  5. MatchManager.ApplyCommand(decoded_action)

RUNTIME STEP
  6. MatchManager.AdvanceStep()
     [Все game logic: movement, harvest, production, combat]

POST-STEP REWARD
  7. reward_step ← RewardCollector.Collect()
     [Категории: economy, combat, terminal, shaping]
  8. accumulated_reward ← accumulated_reward + reward_step

POST-STEP TERMINAL
  9. terminal_eval ← EpisodeTerminalEvaluator.Evaluate(state_{t+1})
  10. if terminal_eval.IsTerminal:
        episode_done = True
        reward_terminal ← RewardCollector.FinalizeTerminal()
```

### Инварианты

- **Observation всегда до decision**: agent видит текущее состояние
- **Decision-apply-step atomic**: action применяется, потом step, потом смотрим результат
- **Reward accumulates incrementally**: каждый шаг добавляет свой компонент
- **Terminal evaluator deterministic**: результат зависит только от runtime state
- **Reset полный**: новый эпизод начинается с чистого observation

### Authoritariveness

- **Canonical loop не изобретает game truth**: authority остаётся в MatchManager, VictoryResolver, UnitRuntime
- **RL-facing state derivable**: observation и mask строятся из authoritative runtime state
- **Backward-compatibility**: heuristic policy работает через тот же loop, что будет использоваться ML
- **Debug-compatible**: диагностика (logging, trace, validation) встроена в loop, не нарушает фазовый порядок

---

## III. Reward Design

Week 4 фиксирует reward contract для **sanity-check валидации**, не для production ML training.

### Reward Categories (4)

| Категория | Назначение | Семантика | Типичный диапазон |
|-----------|-----------|----------|-------------------|
| **Economy** | Сбор ресурсов, возврат, расходование | Proxy: Δ(resources_returned) - Δ(resources_spent) | [0, 2-3] per step |
| **Combat** | Уничтожение врага, потеря своих | Proxy: weighted diff(killed - lost) | [−1, +1] per occurrence |
| **Terminal** | Finale reward за победу/поражение/timeout | Literal: win/loss/draw/timeout magnitude | [−0.25, +1.0] end of episode |
| **Shaping** | Положительные инцентивы за прогресс | Placeholder: 0.0 в Week 4 | [0] в Week 4 |

### Collection Layer (где считается)

**RuntimeRewardCollector** — единственный источник reward в canonical RL loop.

```
Иерархия:
  RuntimeRewardCollector
    ├─ CollectEconomyReward()
    │  └─ observes ResourceManager events (OnResourceReturned, OnResourceSpent)
    ├─ CollectCombatReward()
    │  └─ observes UnitRegistry events (OnUnitKilled)
    ├─ CollectShapingReward()
    │  └─ observes heuristic progress signals [placeholder = 0.0]
    └─ FinalizeTerminal()
       └─ observes EpisodeTerminalEvaluator result
```

**Не считаются здесь:**
- ❌ Heuristic mask (mask — это RL interface, не reward signal)
- ❌ Decoder semantics (decoder преобразует action, не генерирует reward)
- ❌ Runtime validity (post-validation может отклонить action, но не даёт reward)

### Reward Events

Текущая реализация использует explicit **RewardEventType enum**:

- `EconomyHarvest` — успешная добыча
- `EconomyReturn` — возврат в базу
- `EconomySpent` — трата ресурса на стройку/production
- `CombatKilled` — враг уничтожен
- `CombatLost` — свой юнит уничтожен
- `TerminalWin` — победа (фазовая: MatchEndReason == VictoryDeclared)
- `TerminalLoss` — поражение
- `TerminalDraw` — ничья (neutral winner + non-StepLimitReached)
- `TerminalTimeout` — истекло время (StepLimitReached)
- `TerminalInvalidRuntimeState` — аномальное завершение

### RewardConfig (текущие значения)

```csharp
public class RewardConfig
{
    // Economy
    public float EconomyReturnBase = 1.0f;      // per resource unit returned
    public float EconomySpendMult = 0.1f;       // per resource spent
    
    // Combat
    public float CombatKilledMult = 0.1f;       // per enemy killed
    public float CombatLostMult = -0.1f;        // per own unit lost
    
    // Terminal
    public float TerminalWin = 1.0f;
    public float TerminalLoss = -1.0f;
    public float TerminalDraw = 0.0f;
    public float TerminalTimeout = -0.25f;      // diagnostic penalty placeholder
    public float TerminalInvalidRuntimeState = -0.5f;
    
    // Shaping
    public float ShapingMultiplier = 0.0f;      // placeholder: disabled
}
```

### Caveats и ограничения reward design

1. **Combat proxy-semantics**
   - RewardCollector видит только "юнит убит" в реестре
   - Не видит: кто нанёс урон, distance, intention-vs-outcome gap
   - Это **proxy semantic**, а не point-wise accuracy
   - Резидуальная проблема (Week 5 может уточнить)

2. **Economy proxy-semantics**
   - Считаем "ресурс возвращен" как reward event
   - Не считаем: эффективность маршрута, delay, unused harvest potential
   - Это **aggregate signal**, не детерминированный контракт

3. **Timeout penalty (−0.25) — placeholder**
   - Используется для диагностики, чтобы различить timeout от других outcomes
   - Фактическое significance зависит от length distribution эпизода
   - Week 5 может менять этот параметр для поиска оптимума

4. **Shaping = 0.0 (disabled)**
   - В Week 4 shaping намеренно отключена
   - Будущее добавление shaping не будет breaking change
   - Week 5 может добавить progress-based shaping

5. **Sanity-check прошла в diagnostic baseline mode**
   - Валидация (20 эпизодов) показала:
     - Reward не explode и не starve
     - Terminal reward plumbing работает
     - Invalid action rate = 0% в measured сегменте
   - Ограничение: outcome distribution timeout-dominated (не ошибка, а особенность diagnostic scenario)

---

## IV. Terminal Design

Week 4 фиксирует terminal pipeline как **explicit, deterministic, runtime-derived** layer.

### Terminal Reasons (5 + subtypes)

| Reason | Trigger | RL-facing magnitude | Notes |
|--------|---------|-------------------|-------|
| `Win` | MatchEndReason == VictoryDeclared, Winner == Player | +1.0 | Победа нашего противника |
| `Loss` | MatchEndReason == VictoryDeclared, Winner != Player | -1.0 | Поражение (база врага жива, наша мёртва) |
| `Draw` | Runtime ended, Winner == Neutral, non-StepLimitReached | 0.0 | Simultaneous destruction или другой neutral outcome |
| `Timeout` | Runtime Phase == Ended, MatchEndReason == StepLimitReached | -0.25 | Истекло max steps (placeholder magnitude) |
| `InvalidRuntimeState` | Аномальное состояние | -0.5 | Subdivided: `[AnomalousEndedState]` или `[GuardedReset]` |

### Terminal Truth Source (иерархия)

```
AUTHORITATIVE: MatchManager + VictoryResolver
  ├─ MatchManager.MatchPhase
  ├─ MatchManager.MatchEndReason
  ├─ VictoryResolver.Winner
  └─ step count

RL-DERIVED: EpisodeTerminalEvaluator
  └─ reads ↑ snapshot, emits TerminalReason
     used by:
     ├─ RuntimeRewardCollector.FinalizeTerminal()
     └─ EpisodeController.LastTerminalReport
```

Важно: RL-facing terminal **не выдумывает** свою game truth — только читает runtime state и преобразует в RL-семантику.

### RL-facing Terminal Semantics

Два ортогональных сигнала:

**TerminalEventProcessed: boolean**
- True если evaluator распознал терминальный случай и запустил terminal logic
- Независим от magnitude результирующей reward
- Пример: Draw с config 0.0 → TerminalEventProcessed=true, но TerminalRewardNonZero=false

**TerminalRewardNonZero: boolean**
- True если финальный accumulated reward в terminal bucket ≠ 0.0
- Зависит от config (RewardConfig.TerminalWin, TerminalLoss, etc.)
- Позволяет distinguishing: "терминал обнаружен" vs "терминал с weight в награде"

### Timeout Semantics (особый случай)

Timeout — терминальный случай, отдельный от Draw:

- Trigger: Phase == Ended AND MatchEndReason == StepLimitReached AND Winner == Neutral
- RL-reason: TerminalReason.Timeout (не Draw)
- Reward: RewardConfig.TerminalTimeout (default -0.25, placeholder)
- Интерпретация: "эпизод закончился не по game logic, а по временному лимиту"

Timeout НЕ является forced reset — это полноценный terminal event с evaluation.

### InvalidRuntimeState Subtypes

**[AnomalousEndedState]**
- When: Phase == Ended но MatchEndReason == None
- Cause: runtime жизненный цикл создал неполный терминальный state
- Action: conservatively закрыть эпизод, logged warning

**[GuardedReset]**
- When: EpisodeController.ResetEpisode() вызван пока runtime ещё Running
- Cause: forced episode reset перед runtime завершением
- Action: close episode defensively
- Special: RuntimeWasTerminal = false (distinguishing feature)

### Terminal Evaluation Result

```csharp
public struct TerminalEvaluationResult
{
    public bool IsTerminal;
    public TerminalReason TerminalReason;
    public bool RuntimeWasTerminal;
    public float AggregateRewardForDiagnostics;
    public string DiagnosticDescription;
}
```

Используется как в RuntimeRewardCollector, так и в EpisodeController для alignment.

### Caveats terminal design

1. **Runtime truth downstream** — RL не переписывает MatchManager/VictoryResolver
2. **No separate RL victory system** — only observation layer, not decision layer
3. **Terminal evaluated post-step** — observation_{t+1} already computed when terminal evaluated
4. **Timeout-only outcome in diagnostic scenario** — это residual особенность текущего baseline heuristic и scenario, не bug
5. **Guarded reset vs natural terminal** — различаются в InvalidRuntimeState subtypes и флаге RuntimeWasTerminal

---

## V. Observation Contract: attack_target[26] (Explicit)

Channel [26] encode attack target selection в 3×3 local 邻근地 neighbourhood.

### Encoding

- **Пространство:** 3×3 local grid вокруг attacking unit
- **Метрика:** Chebyshev distance (max(|dx|, |dy|)) = "king move" или смежность
- **Индекс:** 0..8 mapping на 3×3 grid (row-major или аналогичный)
- **No-target value:** индекс 0 или специальное значение (typically 0 = no target / ally cell / self)

### Channel Semantics

```
Channel [26] ∈ [0, 1], интерпретируется как:
  - float value 0.0     → no target / neutral / self / ally
  - float value 0.1..1.0 → one-hot encode на позицию врага в 3×3 grid
                           (точный mapping зависит от implementation)
```

Пример (9-way encoding):
```
grid positions:  indices:
[(0,0) (0,1) (0,2)]   [0 1 2]
[(1,0) (1,1) (1,2)] = [3 4 5]
[(2,0) (2,1) (2,2)]   [6 7 8]

where (1,1) = attacking unit's local center (self, should be no-target или 4)
```

### NOT Runtime Combat Truth

Channel [26] — это **observation-side encoding convention**, не runtime semantics:

- Action decoder может интерпретировать [26] as "attack command → target local position"
- Но runtime ActionApplier will validate: "is target actually in range? is not neutral?"
- Runtime MatchManager решает: "does attack hit? does damage apply?"
- Combat resolution остаётся в MatchManager, не в RL observation

### Key Points

- Observation [26] **intent encoding**, не outcome encoding
- Transfer-compatible с Gym-μRTS attack space (если Gym-μRTS также использует 3×3)
- Attack action masked if no enemies in range → observation [26] мало значит без mask
- **Post-validation** runtime layer catches mismatches (invalid targets, out-of-range, neutral allies)

---

## VI. Baseline Policy Status

### Что это

**Baseline Policy** — heuristic control policy, запущенная через canonical RL loop для диагностики.

- **Execution path:** ObservationBuilder → ActionMaskBuilder → HeuristicPolicyAdapter → ActionDecoder → ActionApplier → MatchManager
- **Behavior:** economy-first (workers, resources), fallback combat, no ML
- **Purpose:** sanity-check pipeline, not research policy, not ML baseline

### Что это НЕ

- ❌ Не обученный ML агент
- ❌ Не optimized для strategy
- ❌ Не proof that transfer works
- ❌ Не production gameplay policy
- ❌ Не подходит для outcome diversity analysis (по дизайну узкая)

### Известные ограничения baseline

1. **Fixed heuristic logic**
   - Prioritizes: harvesting > combat > production fallback
   - No learning from experience
   - No strategy adaptation

2. **Narrow decision set**
   - Все decisions предопределены
   - Multi-actor submission per step (избегает starvation)
   - Decision cycling (worker/combat/building rotation), но deterministic

3. **Combat naïve**
   - Attack selection basic: "nearest enemy in range"
   - No formation, no retreat, no tactical planning
   - Combat often stalemate or minimal

4. **Economy limited**
   - Harvest/return behaviour simple
   - No complex logistics
   - Resource management binary (can afford vs cannot)

5. **Outcome distribution**
   - Diagnostic mode (heuristic-vs-idle): всегда timeout
   - Heuristic vs heuristic (self-play): может быть win/loss, но узко distributed
   - Не репрезентативна для RL-trained behavior ожидаемого

### Diagnostic Baseline Mode (heuristic-vs-idle)

Current default:
- **Player 0 (RL side):** heuristic policy through canonical loop
- **Player 1 (opponent):** idle (no actions, just decay)

Использование:
- ✅ Validate pipeline: observation → mask → decision → reward → terminal flow working
- ✅ Check reward distribution: no explosion, no starvation, terminal plumbing OK
- ✅ Unit invalid action rate: measure real rejection rate
- ❌ NOT: representative agent matchup, outcome diversity, or strategy validation

---

## VII. Sanity-Check Results (Day 6 Validation)

### Validation Setup

- **Mode:** diagnostic baseline (heuristic-vs-idle)
- **Episodes:** 20 (confirmed after 10-episode initial pass)
- **Date:** 31 March – 2 April 2026
- **Artifact:** WEEK4_Reports/WEEK4_DAY6_REWARD_SANITY_BATCH_2026-04-02_20-13-00.md

### Factual Results

| Metric | Value | Status |
|--------|-------|--------|
| Mean total reward | 3.22 | ✅ No explosion, no starvation |
| Std total reward | 0.00 | ✅ Deterministic (expected for diagnostic) |
| Economy avg | 3.19 | ✅ Healthy harvest/return |
| Combat avg | 0.28 | ✅ Minimal combat (opponent idle) |
| Terminal avg | -0.25 | ✅ Timeout penalty working |
| Shaping avg | 0.00 | ✅ As expected (disabled in Week 4) |
| Avg step count | 2000.0 | ✅ All episodes hit step limit |
| Terminal reason distribution | 100% Timeout | ✅ Expected in heuristic-vs-idle |
| Terminal event processed rate | 100% | ✅ Terminal pipeline always fires |
| Terminal reward non-zero rate | 100% | ✅ -0.25 penalty applied to all timeouts |
| Invalid action rate (measured) | 0.0% | ✅ Mask/applier validation working |

### Sanity Warnings (non-blocking)

1. **Outcome imbalance (100% timeout)** — expected in diagnostic mode, not blocker
2. **Suspiciously long low-reward episodes** (steps > 1000, reward < 5.0) — expected for default values
3. **Minimal combat diversity** — expected (opponent idle), not blocker

### Conclusion

✅ **PASSED** with diagnostic-mode caveats. Reward distribution, terminal plumbing, and canonical RL loop semantics validated. Outcome diversity limited by design (diagnostic scenario).

---

## VIII. Known Limitations (Честно)

### Week 4 Resolver

Следующие ограничения известны и зафиксированы. Они НЕ blockers для Week 4 closure, но relevant для Week 5:

1. **Outcome distribution timeout-dominated in diagnostic scenario**
   - Root: baseline heuristic narrow, opponent idle
   - Impact: cannot validate skill-based outcome diversity from baseline alone
   - Carry-over: Week 5 must use richer scenario (e.g., heuristic self-play) or tuned baseline

2. **Combat semantics proxy-only**
   - Root: RewardCollector observes "unit killed" events, not combat mechanics
   - Impact: reward signal doesn't encode intention vs outcome, distance factors
   - Carry-over: combat tuning may need per-event granularity or shaping

3. **Shaping disabled**
   - Root: placeholder values (0.0) in Week 4
   - Impact: no intermediate reward signal for progress
   - Carry-over: Week 5 should explore progress-based shaping if needed

4. **Terminal timeout placeholder (-0.25)**
   - Root: diagnostic configuration, no principled tuning yet
   - Impact: step-limit penalization ad-hoc
   - Carry-over: Week 5 should tune based on episode-length distribution

5. **Transfer validation incomplete**
   - Root: only contract-level compatibility checked, no weight transfer
   - Impact: cannot claim "full transfer ready" yet
   - Carry-over: Week 5 must implement actual model loading/adaptation

6. **Baseline policy narrow and deterministic**
   - Root: heuristic-only, no learning
   - Impact: cannot use baseline as proxy for RL agent quality
   - Carry-over: baseline useful for pipeline validation only

7. **Combat intent-outcome gap remains**
   - Root: runtime MatchManager handles combat, RL only sees "killed" event
   - Impact: attack command success not guaranteed by action mask
   - Carry-over: document as known transfer gap, may require adaptation layer

---

## IX. Week 5 Entry Conditions (Readiness Checklist)

Week 5 может начинаться с следующим статусом Week 4:

### ✅ Ready Components

- [x] Observation pipeline: ObservationBuilder outputs valid 24×24×27 tensor
- [x] Action masking: ActionMaskBuilder outputs valid mask, applier respects it
- [x] Invalid action post-validation: runtime checks catch out-of-contract actions
- [x] Reward collection: RuntimeRewardCollector aggregates events, terminal plumbing works
- [x] Terminal evaluation: EpisodeTerminalEvaluator deterministically derives reason
- [x] RL loop phases: canonical order (observation → mask → decision → reward → terminal) fixed
- [x] Episode lifecycle: reset → run N steps → terminal check → reset works
- [x] Scene setup: GameScene.unity has all required components (Camera, Light, GridManager, etc.)
- [x] Baseline sanity-check infrastructure: tooling for rollout validation ready
- [x] Documentation: Week 4 artifacts (reward, terminal, loop) documented

### ⏳ Not Ready (Week 5 Scope)

- [ ] ML policy integration (load/infer ML-Agents model)
- [ ] Policy training pipeline (training loop, checkpoint save/load)
- [ ] Rich scenario validation (heuristic self-play or tuned opponent)
- [ ] Outcome diversity achieved (need richer baseline or ML policy)
- [ ] Transfer weight loading (model checkpoint adaptation)
- [ ] Large-scale experiment infrastructure (100+ episode runs, metrics aggregation)

### Dependencies

Week 5 assumes:
- Unity scene stable and runnable
- Canonical RL loop unchanged (only policy source code can change)
- Reward/terminal configs remain in RewardConfig and EpisodeTerminalEvaluator
- Reset semantics preserved (clean state between episodes)

---

## X. Week 5 Carry-Over Items

Следующие задачи логично переходят в Week 5, но **не блокируют Week 4 closure**:

### High Priority (early Week 5)

1. **Integrate ML-Agents policy inference**
   - Load .onnx or .pb checkpoint into ML-Agents
   - Replace heuristic path with RL agent decision
   - Run diagnostic eval run (10-20 episodes)
   - Capture outcome distribution vs baseline

2. **Create richer baseline scenario**
   - Self-play (heuristic vs heuristic) for outcome reference
   - Or tuned opponent for controlled testing
   - Goal: establish non-trivial outcome distribution

3. **Implement transfer weight loading**
   - Load Gym-μRTS checkpoint
   - Adaptation layer (if needed) for observation/action remapping
   - Test inference on Unity side (single episode)

### Medium Priority (later Week 5)

4. **Outcome diversity analysis**
   - Measure win/loss/draw/timeout distribution across 50+ episodes
   - Compare RL vs heuristic baseline
   - Validate that RL policy produces non-degenerate strategy

5. **Combat semantics refinement**
   - Review attack success rate (proposal accuracy)
   - Consider per-event reward granularity or shaping
   - Document residual transfer gap

6. **Shaping tuning** (if needed)
   - Define progress signals (e.g., unit count, resource rate)
   - Add shaped rewards to progress
   - Measure impact on learning curve

### Low Priority (later Week 5 or Week 6)

7. **Large-scale experiment infrastructure**
   - Batch run harness (50, 100, 200 episode runs)
   - Aggregated metrics logging
   - Comparative analysis (transfer vs from-scratch-lite)

8. **Scenario extension**
   - Multiple map sizes or layouts
   - Difficulty scaling (unit counts, start resources)
   - Generalization testing

---

## XI. Technical References

### Key Code Files

| Module | File | Purpose |
|--------|------|---------|
| RL Loop | `Assets/Scripts/ML/RlLoopCoordinator.cs` | Phase orchestration |
| Observation | `Assets/Scripts/ML/ObservationBuilder.cs` | Observation generation |
| Action Mask | `Assets/Scripts/ML/ActionMaskBuilder.cs` | Validity constraints |
| Action Decoder | `Assets/Scripts/ML/ActionDecoder.cs` | Policy output → RL semantics |
| Action Applier | `Assets/Scripts/ML/ActionApplier.cs` | RL semantics → game command |
| Reward | `Assets/Scripts/ML/RuntimeRewardCollector.cs` | Event aggregation |
| Reward Config | `Assets/Scripts/ML/RewardTerminalContractTypes.cs` | Coefficients (RewardConfig) |
| Terminal | `Assets/Scripts/ML/EpisodeTerminalPipeline.cs` | Terminal reason derivation |
| Baseline | `Assets/Scripts/ML/HeuristicPolicyAdapter.cs` | Diagnostic heuristic |
| Episode Control | `Assets/Scripts/Gameplay/Match/EpisodeController.cs` | Lifecycle + terminal report |

### Key Artifacts

| Artifact | Scope | Reference |
|----------|-------|-----------|
| Observation Contract | ObservationBuilder output — 24×24×27 tensor | ObservationContract.cs |
| Action Contract | 7-branch discrete action space | ActionContract.cs |
| Reward Config | RewardConfig struct with coefficients | RewardTerminalContractTypes.cs |
| Terminal Reasons | RewardConfig + EpisodeTerminalEvaluator | EpisodeTerminalPipeline.cs |
| Baseline Heuristic | HeuristicPolicyAdapter + multi-actor cycling | HeuristicPolicyAdapter.cs |
| Sanity Tooling | BaselineRolloutRunner + RolloutBatchSummary | Day6RewardSanitySmokeTest.cs |

### Documentation Files

| File | Content |
|------|---------|
| WEEK3_DAY5_SUMMARY.md | Heuristic policy adapter + Day 5 pipeline |
| WEEK4_DAY3_TERMINAL_PIPELINE_SUMMARY.md | Terminal design details |
| WEEK4_DAY6_REWARD_SANITY_SUMMARY.md | Sanity-check run results |
| WEEK4_DAY6_CHECKLIST.md | Day 6 validation status |

### Diagnostic Tools

- **Play Mode Menu:** Right-click Week4RewardSanitySmokeTest context menu → "Execute Reward Sanity Check (Play Mode)"
- **Rollout Reports:** Generated in WEEK4_Reports/ with timestamp + markdown tables
- **Heuristic Modes:** SmokeTestMenuRunner has entries for heuristic-vs-heuristic, heuristic-vs-idle

---

## Выводы

Week 4 завершает **RL interface layer** в Unity как стабильный и документированный engineering milestone:

✅ **Что готово:**
- Observation / mask / decision / reward / terminal все на месте
- Canonical RL loop order фиксирован и задокументирован
- Baseline diagnostic policy и sanity tooling работают
- Reward/terminal design честно описаны с caveats

⏳ **Что ждёт Week 5:**
- Integration с ML-Agents或预训练модели
- Richer scenario / outcome diversity validation
- Transfer weight loading и adaptation
- Large-scale experiment infrastructure

🚫 **Что Week 4 НЕ делает (и не претендует):**
- Не обучает ML policy
- Не доказывает полную transfer readiness
- Не решает все combat-semantics gap'ы
- Не создаёт production gameplay

**Week 4 — это foundation, не завершенный продукт.** Ready for Week 5 RL integration.
