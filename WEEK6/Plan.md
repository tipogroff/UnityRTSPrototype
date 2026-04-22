Неделя 6. Интеграция BC в Unity
День 1. Student-side data loader и BC training contract в Unity/Python слое

Задачи дня

Подключить чтение canonical BC-ready артефактов Week 5:
bc_train.npz
bc_validation.npz
bc_manifest.json
Зафиксировать student-side training contract:
какой input подаётся;
какие target branches обучаются;
как трактуется optional mask;
какие metadata используются только диагностически.
Определить минимальный student BC training entrypoint.
Зафиксировать, что Week 6 работает от BC-ready dataset, а не от raw/adapted artifacts напрямую.

Что особенно важно

Не начинать ещё переносить всё подряд в Unity runtime.
Сначала зафиксировать именно student training contract.
Не ломать Week 5 schema.

Итог дня

Есть рабочий student-side loader для BC-ready dataset.
Есть явный BC training contract поверх артефактов Week 5.
День 2. Минимальный BC training loop по branch-wise objective

Задачи дня

Реализовать минимальный supervised training loop для student policy.
Сделать loss по action branches:
action type;
direction branches;
produce type;
local attack target.
Явно решить:
какие branch losses активны всегда;
какие branch losses активны conditionally;
как обрабатываются inactive branches.
Подготовить train/validation метрики первого уровня.

Что особенно важно

Не пытаться уже в этот день делать хороший transfer.
Не путать BC loop и RL/fine-tuning.
Сразу честно решить вопрос inactive branches и optional mask.

Итог дня

Есть минимальный BC training loop, который реально учится на Week 5 dataset.
День 3. Student architecture и partial transfer strategy

Задачи дня

Определить student architecture в терминах Unity-side observation/action contract.
Подготовить partial transfer strategy:
что считается encoder/backbone;
какие части head можно инициализировать частично;
какие части не переносятся напрямую.
Зафиксировать, что direct full transfer не требуется и не является целью.
Подготовить mapping между Week 5 BC branch targets и student output heads.

Что особенно важно

Не делать ложный full direct transfer claim.
Не переносить веса туда, где нет совместимого контракта.
Если partial init только частично возможен — зафиксировать это честно.

Итог дня

Есть оформленная student network structure и зафиксированная partial transfer strategy.
День 4. Экспорт student policy в Unity-side inference path

Задачи дня

Подключить student model к Unity-side inference path.
Реализовать минимальный adapter между student outputs и Unity decoder.
Проверить, что:
observation из Unity собирается корректно;
model output читается корректно;
branch decoding согласован с Week 5 BC contract.
Сделать первый dry run без требования хорошего игрового поведения.

Что особенно важно

Не оценивать пока “силу” противника по первым inference запускам.
Нужна сначала просто корректная связка:
Unity observation -> student -> decoder -> command.

Итог дня

Student policy технически подключена к Unity-side action path.
День 5. Первые тестовые матчи и sanity-check поведения

Задачи дня

Прогнать тестовые матчи student-controlled opponent vs baseline opponents.
Проверить:
есть ли осмысленные действия;
нет ли постоянного NoOp/залипания;
нет ли явного развала produce/attack logic;
нет ли грубых decoder ошибок.
Собрать минимальную поведенческую диагностику:
action histogram;
produce frequency;
attack frequency;
invalid/ignored command share;
episode summaries.

Что особенно важно

Не требовать ещё “хорошей игры”.
Цель дня — sanity of transferred control path.
Отличать плохой policy от сломанного decoder/inference pipeline.

Итог дня

Есть первые матчи и понятна базовая адекватность student behavior в Unity.
День 6. Рассинхронизация таймингов, масок и Unity-side execution semantics

Задачи дня

Проанализировать рассинхронизации между:
BC target semantics;
Unity step timing;
mask timing;
command application timing.
Исправить основные проблемы:
stale observation;
mask/decision timing mismatch;
repeated invalid action pressure;
divergence between predicted branch meaning and runtime applicability.
Зафиксировать, какие маски остаются diagnostic, а какие реально участвуют в student-side logic.

Что особенно важно

Не замалчивать semantic drift.
Не делать вид, что mask = runtime truth.
Исправлять именно тайминговые и execution-level рассинхронизации, а не “лечить” всё teacher quality.

Итог дня

Основные проблемы таймингов и масок в Unity-side BC integration уменьшены и задокументированы.
День 7. Полировка Week 6, evaluation notes и мост к следующему этапу

Задачи дня

Подчистить integration path Week 6.
Документировать:
canonical student-side entrypoint;
как запускать BC model в Unity;
какие артефакты Week 5/6 считаются canonical;
какие ограничения остаются.
Подготовить итоговый артефакт недели, например:
WEEK6_BC_UNITY_INTEGRATION_SUMMARY.md
Зафиксировать, что получилось:
рабочая интеграция BC path;
partial transfer strategy;
текущие ограничения поведения;
что пойдёт в следующий этап.

Что особенно важно

Не пытаться в последний день переделать всю архитектуру.
Закрыть Week 6 как integration stage, а не как “почти готовую финальную систему”.

Итог дня

Week 6 оформлена как завершённый этап интеграции BC в Unity.
Есть ясный переход к следующей стадии улучшения поведения/дообучения.
Сводка Week 6 по результату

К концу недели должно быть так:

BC-ready dataset реально используется student-side;
есть минимальный BC training loop;
student policy подключена к Unity;
partial transfer strategy оформлена и применена там, где это возможно;
проведены первые тестовые матчи;
основные проблемы таймингов и масок выявлены и частично исправлены;
Week 6 завершена как integration stage, а не как попытка сразу получить идеального противника.