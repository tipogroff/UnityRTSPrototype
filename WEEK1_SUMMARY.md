# Summary за первую неделю

> 📄 See also: [WEEK1_EXPERIMENT_CONTRACT_SUMMARY.md](WEEK1_EXPERIMENT_CONTRACT_SUMMARY.md) — итоговый engineering summary Week 1.

## Период
Неделя 1 (контракт MVP / baseline).

## Цель недели
Сформировать и зафиксировать технический контракт эксперимента для RTS-прототипа, чтобы обеспечить воспроизводимость сравнений и подготовить основу для следующих этапов реализации.

## Выполненные работы
1. Зафиксирован baseline-сценарий эксперимента:
   - карта `24x24`;
   - симметричный старт;
   - фиксированный лимит шагов;
   - единый конфиг для повторяемых запусков.
2. Подготовлены базовые доменные контракты и конфигурация:
   - глобальные константы;
   - enums типов юнитов, владельцев и действий;
   - `UnitDefinition` и `GameConfig` для описания сценария и параметров сущностей.
3. Формализован `ObservationContract`:
   - формат `24 x 24 x 27`;
   - общий размер: `15552` float-признака;
   - канальная структура согласована с линией совместимости Gym-muRTS (без terrain-канала).
4. Формализован `ActionContract`:
   - 7 ветвей действий на клетку;
   - 35 параметров на клетку;
   - общий размер: `20160` для всей карты.
5. Реализован `ExperimentLogger`:
   - CSV-логирование ключевых метрик (`win`, `steps`, `reward`, `invalid_rate`, `resources`, `builds`).
6. Добавлены редакторные и конфигурационные артефакты:
   - утилита создания MVP-конфига в Editor;
   - создан эталонный конфиг-ассет для сценария.

## Ключевые артефакты недели
- `Assets/Scripts/Core/GameConstants.cs`
- `Assets/Scripts/Core/UnitType.cs`
- `Assets/Scripts/Core/UnitDefinition.cs`
- `Assets/Scripts/Core/GameConfig.cs`
- `Assets/Scripts/ML/ObservationContract.cs`
- `Assets/Scripts/ML/ActionContract.cs`
- `Assets/Scripts/Logging/ExperimentLogger.cs`
- `Assets/Scripts/Editor/GameConfigCreator.cs`
- `Assets/ML/GameConfig_MVP.asset`

## Результат недели
Неделя 1 завершена полностью (`DONE`).

Сформирован стабильный и воспроизводимый MVP-контракт эксперимента:
- зафиксированы входы/выходы ключевых модулей;
- определены метрики и формат логирования;
- подготовлена техническая база для Week 2 (вертикальный срез RTS без ML) и дальнейшей интеграции ML-контура.
