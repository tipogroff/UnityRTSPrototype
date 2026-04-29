# План реализации RTS-прототипа (8 недель)

Дата фиксации: 2026-03-16

## Актуализация статуса (2026-04-29)

- Этот план сохраняет исходную по-недельную структуру как исторический roadmap.
- Текущий action contract в Unity-коде: per-cell MultiDiscrete, 7 ветвей, branch sizes `[6,4,4,4,4,7,49]`.
- Текущий transfer pipeline: teacher trajectories -> adapter -> BC-ready dataset -> student policy -> Unity inference/fine-tune.
- Legacy Gym teacher (включая `gym_microrts==0.3.2` reference path) может использоваться как teacher-source при подтвержденной стабильности среды и воспроизводимости.
- Даже при структурном сближении branch layout прямой перенос весов не считается автоматически доказанным; semantic/runtime parity требует отдельной валидации.

### Legacy gym_microrts==0.3.2 teacher workspace

- path: `python/week5_teacher_legacy032/`
- purpose: isolated teacher-source lineage for Unity v2 action contract `[6,4,4,4,4,7,49]`
- status: Stage 0 scaffold — no training yet
- note: do not mix v0.6.1 artifacts and legacy032 artifacts in the same output directory

## 1. Цель

Собрать исследовательский RTS-прототип в Unity с управлением противником через перенос знаний из Gym-μRTS.

Основной путь интеграции:
- Behavioral cloning по траекториям teacher policy из Gym-μRTS.

Дополнительный путь (не блокирующий):
- Частичный прямой перенос весов, если подтвердится совместимость.

## 2. Ограничения и фокус

Входит в scope:
- Экономика (сбор ресурсов), строительство, базовая боевая механика.
- Интеграция с ML-Agents.
- Сравнение двух сценариев: transfer vs from-scratch-lite.
- Логирование метрик и пригодность результатов для главы 3 диссертации.

Не входит в scope:
- Коммерческий polish.
- Сложный UI/UX.
- Мультиплеер/сетевая архитектура.
- Большой набор карт и режимов.

## 3. Критерии успеха

1. Unity-среда стабильно воспроизводит матч: ресурсы + строительство + бой.
2. Эпизоды корректно завершаются и сбрасываются.
3. Наблюдения, действия и invalid action mask работают без систематических ошибок.
4. Противник управляется перенесенной политикой (BC-путь).
5. Есть сравнение transfer и from-scratch-lite по заранее выбранным метрикам.

Базовая фиксация сценария для экспериментов:
- Размер карты: 24x24.
- Сценарий: `MVP_24x24_Symmetric`.

## 4. Метрики экспериментов

- Win rate
- Time-to-win
- Episode reward mean/std
- Invalid action rate
- Экономические показатели (например, скорость добычи и число построек к моменту T)

## 5. Roadmap по неделям

## Неделя 1: Контракт эксперимента и baseline

Задачи:
- Зафиксировать один эталонный сценарий карты и юнитов для сравнения.
- Утвердить метрики и шаблон логов.
- Проверить текущий Unity baseline и структуру проекта.
- Зафиксировать требования к совместимости observation/action между Unity и Gym-μRTS.

Результат недели:
- Подписанный технический контракт MVP.
- Понимание входов/выходов для всех основных модулей.

## Неделя 2: Вертикальный срез RTS без ML

Задачи:
- Создать игровую сцену (GameScene) и базовую иерархию объектов (GridManager, MatchManager, MatchBootstrap, UnitRegistry, Camera, Directional Light).
- Создать базовые объекты и префабы юнитов/ресурсов (как минимум Base, Worker, ResourceNode) для визуального и логического прогона.
- Подключить GameConfig к MatchBootstrap и проверить спавн через UnitFactory в Play Mode.
- Ресурсы и базовые строения.
- Базовая боевая логика и условия победы/поражения.
- Reset эпизода.

Результат недели:
- Игровой цикл работает детерминированно без ML.

Операционный чеклист (создание объектов в Unity):
1. Создать сцену GameScene и сохранить ее в проекте.
2. Добавить служебные GameObject-узлы: GridManager, MatchManager, MatchBootstrap, UnitRegistry.
3. Создать и сохранить первые префабы боевых/рабочих юнитов и ресурсов.
4. Привязать ссылки в инспекторе (GameConfig, optional references) и выполнить smoke-test запуска.
5. Зафиксировать результат в контексте проекта (что создано, что осталось).

## Неделя 3: Интерфейс агента (наблюдения/действия)

Цель недели:
- Сделать среду технически готовой для управления агентом через формализованный интерфейс:
	состояние среды -> observation -> action mask -> выбор действия -> декодирование -> применение -> следующий шаг.

Главный инженерный принцип:
- Heuristic policy, будущий ML-Agent и debug/test drivers обязаны использовать один и тот же action pipeline.
- Целевой поток данных: `Policy / Heuristic / Test Driver -> AgentAction -> ActionDecoder / ActionApplier -> MatchManager.ApplyCommand()`.
- Формат недели проектируется не вокруг удобства эвристики, а вокруг transfer-совместимости с Gym-μRTS: reference-compatible слой + Unity MVP слой.

Задачи:
- Зафиксировать двухслойный observation contract:
	- `LegacyGymCompatibleSpec` (референсный слой совместимости);
	- `UnityMvpTransferSpec` (рабочий слой для MVP/fine-tuning);
	- размер карты и порядок каналов;
	- нормализацию признаков;
	- friendly/enemy encoding;
	- отдельный документ соответствия `Unity observation <-> Gym-μRTS observation` + фиксированный список расхождений.
- Реализовать `ObservationBuilder` с разделением на:
	- spatial observation (`W x H x C`);
	- global scalars;
	- API вида `BuildObservation(playerId)`.
- Реализовать две версии action space:
	- `v1_debug_action_space` — упрощённый, удобный для smoke/debug;
	- `v1_transfer_compatible_action_space` — Gym-μRTS-inspired MVP-контракт для переноса с адаптацией.
- Ввести единый `AgentAction` как внутреннюю промежуточную форму между policy и матчевой логикой.
- Реализовать отдельные модули:
	- `ActionDecoder` (`policy output -> AgentAction`);
	- `ActionApplier` (`AgentAction -> MatchCommand / MatchManager`).
- Реализовать invalid action masking как отдельный совместимый модуль:
	- `ActionMaskBuilder`;
	- actor mask;
	- action-type mask;
	- parameter/direction mask;
	- правила маски строятся от Unity-authoritative validation;
	- отдельно маркируются Gym-semantics-compatible и Unity-only runtime rules;
	- post-validation не удаляется даже при наличии маски.
- Формально зафиксировать, какие действия считаются invalid:
	- несуществующий actor;
	- actor противника или уничтоженный actor;
	- невозможное перемещение;
	- harvest без ресурса;
	- return без carry;
	- attack без цели в диапазоне;
	- production без ресурсов или при занятой очереди;
	- действие, не поддерживаемое данным типом сущности.
- Перевести heuristic policy на новый интерфейс:
	- heuristic может читать runtime state,
	- но наружу обязана выдавать тот же `AgentAction`, что и будущая ML policy;
	- heuristic policy не является источником истины для контракта и используется только как инструмент проверки pipeline.
- Подготовить несколько debug-режимов heuristic policy:
	- economy-first;
	- combat-first;
	- mixed.
- Добавить smoke/debug инструменты для проверки observation/action/mask pipeline:
	- Move scenario;
	- Harvest/Return scenario;
	- Attack scenario;
	- Production scenario;
	- Invalid-action fallback scenario.
- Добавить verbose/debug diagnostics:
	- краткий дамп observation;
	- выбранный actor;
	- допустимые action types;
	- выбранное действие;
	- результат применения;
	- причина отклонения invalid action.

Результат недели:
- Среда технически готова принимать решения от агента через единый формализованный интерфейс.
- Observation/action/mask contracts зафиксированы и не расходятся с будущим transfer pipeline.
- Debug heuristic и smoke-инструменты проверяют тот же downstream pipeline, который будет использовать ML-Agent.

Рекомендуемая последовательность по дням:

День 1. Проектирование контракта
- Зафиксировать в markdown/spec-документе:
	- два уровня спецификации: `LegacyGymCompatibleSpec` и `UnityMvpTransferSpec`;
	- формат observation;
	- порядок spatial-каналов;
	- состав global features;
	- состав action branches;
	- правила invalid action;
	- mapping `Unity <-> Gym-μRTS` для observation/action semantics;
	- явный список различий между reference-compatible и Unity MVP слоями.

Документ Day 1:
- `WEEK3_CONTRACT_SPEC.md`

Итог дня:
- Зафиксированы референсный Gym-слой и рабочий Unity-слой, а также их различия.
- Код не пишется без заранее утвержденной модели данных.

День 2. Реализация ObservationBuilder
- Реализовать builder spatial observation с поддержкой двух режимов:
	- compat-mode observation (reference-compatible слой);
	- extended/debug-mode observation (Unity MVP слой).
- Реализовать builder global features для Unity MVP слоя.
- Добавить тестовый dump/debug output observation.
- Добавить базовые проверки размерности, friendly/enemy encoding и стабильности формата.

Итог дня:
- На любом шаге можно получить observation для заданного `playerId`.

День 3. Реализация Action contract
- Реализовать `AgentAction`.
- Зафиксировать два входных action-формата:
	- reference-compatible (для transfer mapping);
	- debug (для smoke/диагностики).
- Реализовать actor selection.
- Реализовать decode discrete branches для обоих входных форматов.
- Реализовать применение действия через `ActionApplier -> MatchManager.ApplyCommand()`.

Итоговое правило дня:
- Оба action-формата сводятся в единый `AgentAction` и проходят один downstream pipeline.

Итог дня:
- Можно вручную сформировать action и корректно применить его в матче.

День 4. Invalid Action Masking
- Реализовать `ActionMaskBuilder`.
- Добавить actor mask.
- Добавить action type mask.
- Добавить direction / parameter masks.
- Строить masking на базе Unity-authoritative validation rules.
- Отдельно фиксировать: какие mask-правила Gym-semantics-compatible, а какие Unity-only runtime.
- Оставить fallback validation при применении действия как обязательный серверный слой.

Итог дня:
- Среда умеет вычислять допустимое множество действий.

День 5. Heuristic policy через новый интерфейс
- Реализовать heuristic agent / adapter.
- Перевести heuristic на выбор `AgentAction` через observation/mask.
- Прогнать базовые эпизоды на `v1_debug_action_space`.
- Явно зафиксировать heuristic policy как инструмент проверки observation/action/mask pipeline, а не как эталон контракта.
- Проверить, что downstream pipeline совпадает с pipeline будущего ML-Agent.

Итог дня:
- Без ML уже можно гонять матчи через агентный интерфейс.

День 6. Smoke-тесты и фиксы
- Добавить сценарии проверки:
	- move;
	- harvest/return;
	- attack;
	- production;
	- invalid action fallback.
- Добавить логирование invalid attempts.
- Исправить расхождения между observation, mask и runtime.

Итог дня:
- Observation/action/mask pipeline стабилен на ключевых сценариях.

День 7. Полировка и подготовка к следующей неделе
- Очистить API.
- Убрать дублирование между debug и transfer-compatible слоями.
- Документировать public methods.
- Зафиксировать ограничения первой версии.
- Финализировать `WEEK3_COMPATIBILITY_GAP_LIST.md`: что совпадает с Gym-μRTS, а что сознательно адаптировано под Unity MVP.
  - Все новые gaps, обнаруженные в дни 2–6, должны быть добавлены в список.
  - Для каждого gap'а зафиксировать mitigation strategy.
- Подготовить основу под интеграцию ML-Agent на Week 4.

Итог дня:
- Система готова к подключению реальной policy.
- Финализирован артефакт `WEEK3_COMPATIBILITY_GAP_LIST.md` для раздела 3.3 диссертации.

## Неделя 4: Награда и стабилизация RL-контура

Общая цель недели:
- Сделать среду не просто "готовой к подключению policy", а реально пригодной для RL-цикла внутри Unity.
- Агент получает observation в стабильном формате.
- Invalid action masking уже работает.
- Действие проходит через decoder/applier/runtime.
- Reward и terminal logic формализованы и диагностируемы.
- Цикл CollectObservations / OnActionReceived / Heuristic/Baseline стабилен.
- Baseline policy можно гонять не только как debug-инструмент, но и как опорную политику для первых RL-запусков.

Главный инженерный принцип недели:
- Week 4 не должен ломать Week 3 контракт.
- Reward не должен вносить hidden shortcut в матчевую логику.
- Terminal logic не должна расходиться с MatchManager/VictoryResolver.
- `attack_target[26]` дорабатывается аккуратно, без ложного claims о полной Gym parity.
- RL loop использует уже существующий pipeline, а не параллельный "агентский путь специально для обучения".

День 1. Проектирование reward contract и terminal contract

Задачи дня:
- Зафиксировать reward design на уровне документа/summary до серьезных кодовых изменений.
- Разделить награды на экономические, боевые, терминальные.
- При необходимости выделить отдельно shaping rewards и sparse rewards.
- Зафиксировать, какие события считаются rewardable, punishable, terminal, informative-only.
- Определить, какие rewards выдаются instant, accumulated-per-step, episode-end only.
- Явно отделить reward semantics для RL, игровые события runtime, диагностические метрики.

Что особенно важно:
- Не делать reward design слишком "умным" и густым с первого дня.
- Не смешивать reward и heuristic goals.
- Не дублировать victory logic вне MatchManager/VictoryResolver.

Минимальный целевой результат дня:
- Есть документ или markdown-артефакт с reward/terminal contract.
- Для каждого reward-сигнала зафиксированы: source event, magnitude/sign, stacking rule, one-time vs repeatable, risk of reward hacking.

Итог дня:
- Зафиксирован reward/terminal contract для Week 4.
- Понятно, какие сигналы будут реализовываться в коде и зачем.

День 2. Реализация базового reward collector

Задачи дня:
- Реализовать модуль/слой сбора reward-событий.
- Ввести базовые reward categories.
- Экономика: harvest success, return success, produce success.
- Бой: attack success / damage dealt / enemy destroyed.
- Опционально: self-loss penalty.
- Терминальные: win / loss / draw.
- Определить, где именно reward должен считаться.
- Не в heuristic.
- Не в mask.
- Не в decoder.
- На стороне runtime event/result collection, совместимой с RL loop.
- Добавить явную структуру диагностик reward по шагу: total reward, contribution breakdown, terminal contribution, economy/combat contribution.

Что хорошо бы получить:
- Условный RewardBreakdown / RewardEvent / RewardCollector, который можно читать в агенте, логировать в smoke/debug и использовать как для baseline, так и затем для ML-Agent.

Риски:
- Reward начнет считаться "по факту выбора действия", а не по факту результата в runtime.
- Смешаются reward за команду и reward за достигнутый эффект.

Итог дня:
- В коде есть базовый reward collector с разложением по категориям.
- Можно получить reward breakdown за шаг/эпизод.

День 3. Терминалы и эпизодный цикл

Задачи дня:
- Формализовать terminal logic в RL-контуре.
- Явно зафиксировать, когда эпизод заканчивается.
- Определить обработку: победа, поражение, ничья, max step timeout, невалидное/ошибочное состояние среды (если предусмотрено).
- Согласовать RL-terminal semantics с MatchManager, VictoryResolver и существующим reset/episode lifecycle.
- Добавить диагностический вывод: почему эпизод завершился, какой terminal code был выдан, какой terminal reward применен.

Важно:
- Не допустить расхождения: runtime считает матч активным, а RL loop уже считает его done.
- Не превращать maxSteps в скрытый источник reward hacking.

Что желательно проверить:
- Win/loss корректно отрабатывает и в baseline-запусках.
- Timeout не маскирует реальные ошибки среды.
- Reset эпизода не оставляет старые reward/terminal state.

Итог дня:
- Episode termination semantics согласованы между матчевой логикой и RL loop.
- Есть диагностируемая terminal pipeline.

День 4. Стабилизация цикла CollectObservations / OnActionReceived / baseline path

Задачи дня:
- Свести в стабильный агентный цикл: CollectObservations, WriteDiscreteActionMask (или аналогичный mask path), OnActionReceived, baseline/heuristic execution path для сравнения.
- Убедиться, что observation собирается ровно в нужный момент.
- Проверить, что mask строится на консистентном state.
- Проверить, что action применяется через production path.
- Проверить, что reward и terminal читаются после runtime step в правильной фазе.
- Подтвердить, что baseline/heuristic path можно использовать как опорный контрольный режим для отладки RL-контура.
- Добавить минимальные step-level diagnostics: observation built, mask built, action decoded/applied, reward emitted, terminal state.

Это ключевой день недели:
- Именно здесь неделя превращается из "есть reward design" в "есть рабочий RL-контур".

Риски:
- Двойное применение шага.
- Reward считается до применения действия.
- Terminal считывается не после шага.
- Heuristic path и будущий RL path расходятся по фазе вызовов.

Итог дня:
- Есть стабильный и диагностируемый RL loop поверх уже существующего Week 3 pipeline.

День 5. Реализация `attack_target[26]` в observation

Задачи дня:
- Реализовать вычисление канала `attack_target[26]` в observation.
- Зафиксировать точную семантику: что именно означает "нормализованный индекс целей в зоне атаки", как он вычисляется, для каких клеток meaningful, что пишется при отсутствии target.
- Согласовать реализацию с актуальным action contract и residual gap между explicit attack command и runtime combat semantics.
- Обновить документацию/spec, чтобы не возникло ложного впечатления, что канал стал полностью reference-identical во всех режимах.
- Добавить focused observation tests/smoke checks именно на этот канал.

Важно:
- Это потенциально опасное место.
- Можно случайно сделать "красивый" канал, который не соответствует action semantics.
- Можно создать ложное впечатление, что observation `attack_target` и runtime combat semantics теперь полностью совпадают.
- Нужно сделать канал полезным для policy, но честно сохранить distinction между observation-side encoding, command-side target intent и runtime-side combat resolution.

Итог дня:
- Канал `attack_target[26]` реально вычисляется и документирован.
- Добавлены проверки его консистентности в observation pipeline.

День 6. Отладка reward distribution и baseline rollout

Задачи дня:
- Прогнать серию baseline/heuristic rollouts с включенными reward и terminal logic.
- Проверить распределение наград.
- Нет ли reward explosion.
- Нет ли reward starvation.
- Не доминируют ли shaping rewards над terminal reward.
- Не возникает ли очевидного reward hacking.
- Проверить, что baseline-поведение дает интерпретируемый reward trace.
- Добавить summary/debug output по эпизоду: total reward, economy contribution, combat contribution, terminal contribution, invalid action rate, episode end reason.

Это день не новой логики, а sanity-check недели:
- Нужно подтвердить, что reward действительно обучаемый.
- Baseline не ломает эпизоды.
- Terminal logic не ведет себя странно.
- RL loop устойчив не только на одном искусственном кейсе.

Итог дня:
- Reward distribution и terminal behavior прошли первичную sanity-проверку.
- Baseline rollouts дают устойчивые и интерпретируемые traces.

День 7. Полировка Week 4 baseline и подготовка к Week 5

Задачи дня:
- Убрать явные шероховатости Week 4 implementation.
- Документировать reward design, terminal design, RL loop assumptions, semantics канала `attack_target[26]`, известные ограничения baseline policy.
- Зафиксировать, что уже готово для реального RL-запуска, какие ограничения остаются, что потребуется на следующей неделе.
- Подготовить итоговый Week 4 artifact, например `WEEK4_REWARD_AND_RL_LOOP_SUMMARY.md`.

Что особенно важно:
- Не начинать заранее задачи Week 5.
- Не раздувать baseline в полноценную исследовательскую систему.
- Оставить понятную, документированную и воспроизводимую основу.

Итог дня:
- В Unity есть рабочий RL-интерфейс и стабильная baseline-политика.
- Week 4 оформлена как завершенный, документированный этап.

Сводка недели по результатам:
- К концу Week 4 reward design реализован и диагностируем.
- Terminal logic согласована с runtime.
- RL loop стабилен.
- Baseline policy можно гонять как контрольный режим.
- `attack_target[26]` вычисляется и документирован.
- Есть summary-артефакт недели, пригодный и для разработки, и для главы 3.

## Неделя 5: Gym-μRTS teacher pipeline

Задачи:
- Подготовить воспроизводимый Python-контур.
- Получить teacher policy и экспортировать траектории для BC.
- Проверить совместимость форматов observation/action с Unity-контуром.
- Зафиксировать документ соответствия `Unity <-> Gym-μRTS` для observation/action/mask semantics.

Результат недели:
- Готов датасет траекторий и подтверждена совместимость входов/выходов на уровне контракта.

## Неделя 6: Интеграция BC в Unity

Задачи:
- Подключить BC/distillation путь управления противником.
- Делать ставку на partial transfer, а не на full direct transfer:
	- перенос encoder/backbone;
	- частичная инициализация policy head;
	- teacher-student / fine-tuning на Unity-траекториях.
- Прогнать тестовые матчи и проверить адекватность поведения.
- Исправить рассинхронизацию таймингов и масок.

Результат недели:
- Противник управляется через реалистичный transfer-подход в Unity без требования полного побитового совпадения с Gym-μRTS.

## Неделя 7: Сравнительные эксперименты

Задачи:
- Провести серию запусков transfer vs from-scratch-lite.
- Собрать таблицы и графики по метрикам.
- Зафиксировать угрозы валидности и ограничения эксперимента.

Результат недели:
- Набор воспроизводимых экспериментальных результатов.

## Неделя 8: Финализация и документация

Задачи:
- Дофиксить критические баги.
- Подготовить материалы для разделов 3.3 и 3.6.
- Подготовить руководство программиста и пользователя.
- Собрать демонстрационный сценарий запуска.

Результат недели:
- Финальный пакет для демонстрации и текста диссертации.

## 6. Технические контрольные точки

Checkpoint A (конец недели 2):
- Игра запускается и завершается без ML.
- В Unity созданы и проверены базовые объекты сцены и MVP-префабы юнитов/ресурсов.

Checkpoint B (конец недели 4):
- RL-интерфейс и action masking стабильны.

Checkpoint C (конец недели 6):
- Transfer через BC реально управляет противником.

Checkpoint D (конец недели 8):
- Есть валидное сравнение transfer и from-scratch-lite.

## 7. Управление рисками

Риск: несовпадение observation space.
Митигатор: ранняя shape-валидация и единый контракт каналов/тензоров.

Риск: несовпадение action space.
Митигатор: ограниченный набор действий для MVP + строгие маски.

Риск: разные tick rate и temporal resolution.
Митигатор: явная синхронизация шага симуляции и частоты принятия решений.

Риск: срыв сроков из-за scope creep.
Митигатор: правило de-scope после 2 заблокированных сессий подряд.

## 8. Рабочий ритм (13+ часов/неделя)

Рекомендуемый cadence:
- Сессия 1: core implementation.
- Сессия 2: интеграция и тесты.
- Сессия 3: логирование, анализ, фиксация результатов в текст.

Каждая неделя завершается коротким review:
- Что завершено.
- Что блокирует.
- Что переносится и почему.

## 9. Stretch Goals (если останется время после недели 8)

### Архитектура для больших карт

Текущая плоская grid-архитектура (flat observations `[H, W, 27]` + per-cell actions) ограничена размером карты ~24×24–32×32 из-за квадратичного роста нагрузки ($O(N^2)$ ячеек, $O(N^2)$ параметров политики).

Если после завершения диплома останется время, можно исследовать альтернативные архитектуры, которые позволяют масштабироваться на карты 48×48, 64×64 и больше:

- **CNN-based policy**: вместо flat MLP, использовать конволюционную сеть для обработки spatial patterns.
- **Localized window approach**: судить не всю карту, а локальное окно вокруг юнита (16×16 или 20×20), рекурсивно обновляя его.
- **Graph Neural Networks**: представить граф как средство управления юнитами и их взаимодействиями.
- **Hierarchical policy**: высокоуровневая политика выбирает регион/цель, низкоуровневая — тактику в этом регионе.
- **Attention mechanism**: динамически выбирать, на какие части карты смотреть в зависимости от состояния игры.

Такие подходы требуют переделки контрактов наблюдений и действий, переподготовки моделей и потребуют дополнительного времени на исследование. Это — **не входит в обязательный scope диплома**, но может быть интересным направлением для будущих работ.
