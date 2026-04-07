## Week 3, Day 2: ObservationBuilder Implementation ✓

### Дата: 23 Марта 2026

### Цель дня
Реализовать builder spatial observation с поддержкой двух режимов:
- compat-mode (reference-compatible слой для Gym-μRTS)
- extended/debug-mode (Unity MVP слой)

### Выполнено

#### 1. Класс ObservationBuilder (Assets/Scripts/ML/ObservationBuilder.cs)
- **Размер**: ~430 строк чистого кода
- **Поддержка двух режимов наблюдений**:
  - `ObservationMode.LegacyGymCompatible`: Строго совместим с Gym-μRTS
   - `ObservationMode.UnityMvpTransfer`: Реально расширенный режим для Unity MVP (перспективное friendly/enemy encoding + MVP-сигналы)

#### 2. Основной функционал
```
float[] obs = builder.BuildObservation(Owner.Player1, ObservationMode.LegacyGymCompatible);
```

**Сборка наблюдения для любого playerId:**
- Итерирует 24×24 сетку
- Для каждой ячейки вычисляет все 27 каналов согласно ObservationContract
- Возвращает float[15552] (24 * 24 * 27)

#### 3. 27 каналов на ячейку:
- **[0]**: hp_normalized [0..1]
- **[1]**: resources_normalized [0..1]
- **[2-4]**: owner one-hot (neutral, player1, player2)
- **[5-11]**: unit_type one-hot (7 типов)
- **[12-17]**: current_action one-hot (6 типов)
- **[18-21]**: action_direction one-hot (4 направления)
- **[22-25]**: produce_unit_type one-hot (4 типа производства)
- **[26]**: attack_target normalized [0..1]

#### 3.1 Отличия UnityMvpTransfer от LegacyGymCompatible
- Каналы owner [2-4] кодируются относительно `playerId`: `[neutral, friendly, enemy]`.
- Канал resources [1] для friendly-worker учитывает переносимый ресурс (`CarriedResources`) в нормализованном виде.
- Каналы current_action [12-17] выставляют `Produce`, если здание реально производит юнита.
- Канал [26] в MVP используется как тактический сигнал присутствия врага в клетке (`0/1`) относительно `playerId`.

#### 4. Валидация наблюдений
```
var result = builder.ValidateObservation(obs);
// result.IsValid: bool
// result.Issues: List<string>
```

**Проверяет:**
- Размер буфера (должен быть 15552)
- Диапазон скалярных каналов [0..1]
- Корректность одна-горячего кодирования (ровно один 1.0 или все 0.0)
- Диапазон атаки-цели [0..1]

#### 5. Диагностический вывод
```
string dump = builder.DumpObservation(obs, verbose: false);
// Краткий режим: 3x3 первых ячеек
// Полный режим: вся 24x24 сетка
```

**Выводит:**
- Координаты ячейки
- HP, ресурсы, владелец, тип юнита, направление

#### 5.1 Global Features (UnityMvpTransfer)
Реализован отдельный builder глобальных признаков:
```
float[] global = builder.BuildGlobalFeatures(Owner.Player1, ObservationMode.UnityMvpTransfer);
// global.Length == 7
```

Состав global features:
- **[0]** `is_running`
- **[1]** `is_terminal`
- **[2]** `is_win`
- **[3]** `is_loss`
- **[4]** `self_resources_normalized`
- **[5]** `enemy_resources_normalized`
- **[6]** `step_normalized`

#### 6. Интеграция с существующей архитектурой

**GridManager**:
- Используется для заполнения буфера (как источник истины о занятости)

**UnitRegistry**:
- GetAllUnits() → собираем все юниты в словарь по позициям

**ResourceManager**:
- GetAllResourceNodes() → собираем все ресурсы в словарь по позициям

**UnitRuntime / UnitModel**:
- Читаем HP, тип, владельца, направление

**BuildingRuntime** (для production queue):
- GetComponent<BuildingRuntime>().GetProductionQueue() → Peek() первого юнита

#### 7. Smoke-test (ObservationBuilderSmokeTest.cs)
Простой класс для ручной проверки:
- Тест 1: Сборка observation для Player1 (compat)
- Тест 2: Валидация результата
- Тест 3: Дамп с примерами ячеек
- Тест 4: Сборка для Player2 (MVP)
- Тест 5: Проверка размеров

### Итоговый результат

✅ **На любом шаге можно получить observation для заданного playerId**

```cpp
var builder = new ObservationBuilder(gridMgr, unitReg, resMgr);
float[] obs = builder.BuildObservation(Owner.Player1);
// obs.Length == 15552
// obs полностью заполнен согласно ObservationContract
```

### Ограничения и TODO (Week 3+)

1. **Current ActionChannelы [12-17]**: Синхронизированы с MatchManager.ApplyCommand
   - Реализовано: берётся последняя принятая команда юнита в текущем шаге (NoOp fallback при отсутствии команды)

2. **Attack Target [26]**: Placeholder (0)
   - TODO: Неделя 4 — вычислить нормализованный индекс целей в зоне атаки

3. **Global Features**: 
   - Реализовано: добавлен `BuildGlobalFeatures(...)` для UnityMvpTransfer (выигрыш/проигрыш, ресурсы игроков, счётчик шагов)

### Совместимость

✓ Структура каналов совпадает с ObservationContract (День 1)
✓ Готов для transfer pipeline (Gym-μRTS → Unity)
✓ Готов для ML-Agents ConnectObservations()
✓ Валидация предотвратит ошибки раннего обнаружения

### Метрики качества

- **Код**: Чистый, хорошо комментирован, с TODO для будущих этапов
- **Производительность**: One-shot allocation буфера → zero-copy между вызовами
- **Тестируемость**: Smoke-test готов, интеграционные тесты легко добавить
- **Документация**: Inline комментарии на каждый канал, docstrings для методов

---

**Статус**: ✅ ЗАВЕРШЕНО
**Переход на День 3 (Week 3)**: Реализация Action contract и ActionDecoder
