# 🧪 Play Mode Smoke-Test: Episode Lifecycle Cycle

## Overview
Проверка RL-подобного цикла матча:
- **Start** → Episode 1 начинается
- **Step** → Несколько шагов выполняются автоматически
- **Terminal** → Матч заканчивается (или по лимиту, или по условию победы)
- **Reset** → Episode 2 стартует с нуля

---

## Pre-Test Checklist

### 1. Подготовка сцены
- ✅ Откройте **Assets/Scenes/GameScene.unity**
- ✅ В иерархии убедитесь, что есть:
  - `Bootstrap` (MatchBootstrap, GameConfig ссылка)
  - `MatchManager`
  - `EpisodeController`
  - `VictoryResolver`
  - `GridManager`
  - `UnitRegistry`
  - `ResourceManager`

### 2. Проверьте Inspector для EpisodeController
```
_autoStartOnPlay = TRUE          (↳ автоматический старт эпизода)
_autoStepInFixedUpdate = TRUE   (↳ автоматические шаги каждый FixedUpdate)
_logLifecycleEvents = TRUE       (↳ логи для отладки)
```

### 3. Проверьте MatchManager в Inspector
```
_matchBootstrap = Bootstrap
_gridManager = опция (или Instance)
_unitRegistry = опция (или Instance)
_victoryResolver = опция (или Instance)
```

### 4. Проверьте GameConfig
- ✅ В **Assets/Config/GameConfig** (или где лежит):
  - `mapWidth = 24` (или нужное значение)
  - `mapHeight = 24`
  - `maxSteps = 1000` (достаточно для теста)
  - `startResourcesPerPlayer > 0`

---

## Test Procedure

### Phase 1: Start Game
```
1. Нажмите [ ▶ Play ] в Unity Editor
```

**Expected Console Output:**
```
[MatchManager] BeginMatch. MaxSteps=1000, StartResources=50
[EpisodeController] Episode 1 started. Running=True
[MatchManager] Commands accepted this step: ...
```

**Expected State:**
- EpisodeController.EpisodeIndex = 1
- MatchManager.Phase = Running
- MatchManager.Step = 0
- MatchManager.Winner = Neutral

✅ **Checkpoint 1: PASS if all above is true**

---

### Phase 2: Watch Steps Increment
```
2. Наблюдайте Console в течение 10-20 секунд
   (FixedUpdate вызывает StepMatch ~50 раз в секунду)
```

**Expected Console Output (повторяется каждый шаг):**
```
[MatchManager] Movement phase: X units moved
[MatchManager] Harvest/Deposit phase: X resources changed
[MatchManager] Production phase: X units produced
[MatchManager] Combat phase: X units in combat
```

**Expected State (изменяется каждый FixedUpdate):**
- MatchManager.Step = 1, 2, 3, 4, ... (постоянно растет)
- MatchManager.Phase = Running (остается Running)
- MatchManager.Winner = Neutral (как и было)

✅ **Checkpoint 2: PASS if step counter растет и логи появляются**

---

### Phase 3: Wait for Terminal
```
3. Ждите, пока матч НЕ завершится (один из вариантов):
   A) Часов лимит достигнут (MaxSteps = 1000)
   B) База игрока уничтожена (если есть боевые действия)
   C) Оба játékosa исключены (обе без юнитов и базы)
```

**Expected Console Output при терминале:**
```
[EpisodeController] Episode 1 ended. Winner=Neutral
[MatchManager] Match ended. Winner=Neutral, Reason=StepLimitReached, Step=1000
```

**Expected State при терминате:**
- MatchManager.Phase = Ended (изменилось с Running!)
- MatchManager.Winner = Neutral (или Player1/Player2)
- MatchManager.EndReason = StepLimitReached (или EnemyBaseDestroyed/Elimination)
- MatchManager.EndReasonDetails = "Step limit reached (1000/1000)."

✅ **Checkpoint 3: PASS if phase changed to Ended and console shows terminal message**

---

### Phase 4: Manual Reset Trigger
```
4. В Console в Unity Editor выполните:
   EpisodeController.Instance?.ResetEpisode()
   
   Или нажмите [ ⏎ ] и напечатайте:
   EpisodeController.Instance?.ResetEpisode()
```

**Alternative: Используйте Test Helper (если добавлен)**
```
EpisodeControllerTestHelper.ResetAndCheckPhase2()
```

---

### Phase 5: Check Post-Reset State

**Expected Console Output:**
```
[MatchManager] BeginMatch. MaxSteps=1000, StartResources=50
[EpisodeController] Episode 2 started. Running=True
```

**Expected State после Reset:**
- EpisodeController.EpisodeIndex = 2 (инкрементировался от 1 → 2)
- MatchManager.Phase = Running (вернулся с Ended → Running)
- MatchManager.Step = 0 (сброс счетчика)
- MatchManager.Winner = Neutral (очищено)
- MatchManager.EndReason = None (очищено)

✅ **Checkpoint 4: PASS if all values are reset correctly**

---

## Final Verdict

| Checkpoint | Expected | Got? | Status |
|---|---|---|---|
| 1️⃣ Start (Episode 1 begins) | Phase=Running, Step=0 | ? | ✅/❌ |
| 2️⃣ Steps increment | Step grows 1→2→3... | ? | ✅/❌ |
| 3️⃣ Terminal reached | Phase=Ended, Winner set | ? | ✅/❌ |
| 4️⃣ Reset works | Phase=Running, Step=0, Index=2 | ? | ✅/❌ |

### All Checkpoints Passed?
🎉 **SMOKE-TEST PASSED!** Lifecycle cycle is working correctly.

### Some Failed?
⚠️ **REVIEW**: Check console output and compare with Expected columns.

---

## Automated Test Option (Optional)

Если вы хотите автоматизировать тест (без ручного Reset):

```csharp
// В Console при Play Mode:
var tester = new GameObject("SmokeTestAutomation").AddComponent<RTS.Debug.SmokeTestAutomation>();
tester.StartAutomatedTest(stepsBeforeCheck: 5);
```

Тестер автоматически:
1. Считает шаги до N
2. Ждет терминала
3. Вызывает Reset
4. Проверяет результаты
5. Печатает итоговый отчет в Console

---

## Troubleshooting

### ❌ Ошибка: "EpisodeController is null"
- **Решение**: Убедитесь, что EpisodeController присутствует в сцене и имеет Awake() вызванный. Нажмите Play.

### ❌ Ошибка: "Phase не меняется с Running"
- **Решение**: Проверьте, что `VictoryResolver.Evaluate()` вызывается в `MatchManager.ResolveCompletion()`. Проверьте серолизацию `_victoryResolver` в MatchManager.

### ❌ Шаги не растут
- **Решение**: Убедитесь, что `_autoStepInFixedUpdate = true` в EpisodeController. Проверьте, что FixedUpdate вызывает `MatchManager.StepMatch()`.

### ❌ После Reset Phase остается Ended
- **Решение**: Проверьте, что `MatchBootstrap.Setup()` вызывается в `StartNewEpisode()` и устанавливает `MatchManager.Phase = Running`.

---

## Summary

✅ **Мертвый код удален** из VictoryResolver.cs  
✅ **Lifecycle цикл готов к тестированию**  
✅ **Два вспомогательных скрипта созданы:**
- `EpisodeControllerTestHelper.cs` — для ручного контроля
- `SmokeTestAutomation.cs` — для автоматического прогона

**Следующий шаг**: Откройте GameScene.unity → нажмите Play → следуйте чек-листу выше.
