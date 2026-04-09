Неделя 5: Gym-μRTS teacher pipeline

Общая цель недели:

Перейти от “RL-ready Unity interface” к реальному transfer-подготовительному контуру на стороне Gym-μRTS.
Не обучать ещё Unity-агента напрямую, а подготовить качественный teacher-side pipeline для behavioral cloning.
Получить не просто сырые rollout’ы, а воспроизводимый, документированный и совместимый с Unity датасет траекторий.
Формально зафиксировать, какие части Gym-μRTS переносятся напрямую, какие адаптируются, а какие отфильтровываются.

Главный инженерный принцип недели:

Week 5 не должен делать ложный “full direct transfer”.
Основная ставка недели — на teacher policy + dataset adapter + compatibility-verified trajectory export.
Источником истины для Unity-контракта остаются Week 3 и Week 4 артефакты, а Gym-пайплайн должен подстраиваться под них через явный adapter layer.
Любая несовместимость между Gym-μRTS и Unity должна не замалчиваться, а оформляться как documented conversion rule или explicit data loss.
На выходе недели нужен не “почти готовый ML-агент”, а надежный вход для Week 6, где уже будет подключаться BC/distillation путь.

Задачи недели:

Подготовить воспроизводимый Python-контур для Gym-μRTS teacher pipeline.
Получить рабочую teacher policy или зафиксировать воспроизводимый путь её получения/загрузки.
Реализовать экспорт траекторий teacher policy для behavioral cloning.
Подготовить dataset adapter между Gym-μRTS и UnityMvpTransferSpec.
Проверить совместимость observation/action/mask semantics на уровне контракта, а не только на уровне “похоже работает”.
Зафиксировать документ соответствия Unity <-> Gym-μRTS для observation/action/mask semantics.
Зафиксировать, какие compatibility gaps реально влияют на траектории, а какие только на диагностику.

Результат недели:

Есть воспроизводимый teacher-side Python pipeline.
Есть экспортируемый и проверенный датасет траекторий для BC.
Есть adapter layer для ключевых compatibility gaps.
Есть документированное соответствие Unity <-> Gym-μRTS.
Есть понятный вход в Week 6: BC/distillation можно начинать не “с идей”, а с уже подготовленных артефактов.

Рекомендуемая последовательность по дням:

День 1. Проектирование teacher pipeline и freeze входного контракта

Задачи дня:

Зафиксировать отдельным markdown-артефактом, что именно Week 5 считает teacher pipeline.
Подтвердить, что Unity-side целевой контракт берётся из LegacyGymCompatibleSpec и Week 3/4 артефактов, а не переизобретается заново.
Зафиксировать минимальный состав teacher trajectory:
observation;
action;
valid action mask или её эквивалентная teacher-side форма;
reward;
done / terminal;
step index;
optional info for diagnostics.
Зафиксировать формат хранения траекторий:
episode-based;
step-based;
npz / parquet / pickle / jsonl — выбрать один основной формат и один отладочный.
Определить, какой именно policy source считается допустимым teacher:
готовая предобученная policy;
воспроизводимо загружаемая policy;
воспроизводимо дообучаемая policy при необходимости.
Явно зафиксировать, что global vector Unity не является обязательной частью teacher encoder.
Импортировать в план Week 5 все критичные gaps из WEEK3_COMPATIBILITY_GAP_LIST.md, которые требуют dataset adapter:
global vector;
normalization;
attack target parameterization;
reduced producible unit types;
missing action types;
temporal resolution.

Документ Day 1:

WEEK5_TEACHER_PIPELINE_SPEC.md

Что особенно важно:

Не начинать сразу писать экспортёр, пока не зафиксирован формат траектории.
Не подменять target contract реальным Gym-форматом “как есть”.
Сразу определить, какие поля будут обязательны для BC, а какие только диагностические.

Итог дня:

Есть утверждённый Week 5 contract для teacher pipeline.
Ясно, какие данные экспортируются, в каком формате и какие adapter rules понадобятся дальше.
День 2. Подготовка воспроизводимого Python-контура Gym-μRTS

Задачи дня:

Подготовить отдельное Python-окружение или зафиксировать существующее как canonical.
Зафиксировать версии:
Python;
Gym-μRTS / MicroRTS-Py;
Stable-Baselines3;
torch;
numpy и прочих зависимостей.
Проверить запуск среды на эталонном сценарии, максимально близком к Unity MVP_24x24_Symmetric.
Реализовать минимальный reproducible entrypoint:
загрузка среды;
запуск policy;
прогон N эпизодов;
сбор базовой статистики.
Подготовить структуры каталогов:
teacher_models/
teacher_rollouts/
teacher_logs/
teacher_exports/
Зафиксировать seed policy:
random seed;
env seed;
rollout seed.
Добавить smoke-check:
policy загружается;
среда не падает;
observation/action shape читаются;
один эпизод проходит до терминала.

Что желательно получить:

Один скрипт вида run_teacher_rollout.py, который уже может воспроизводимо прогонять teacher в Gym-μRTS.
Один markdown или README с командой запуска и описанием выходных файлов.

Риски:

Потратить день на “идеальную” инфраструктуру вместо минимально рабочего контура.
Смешать legacy-формат старых моделей с новым форматом среды без явной проверки shape compatibility.

Итог дня:

Python teacher pipeline воспроизводимо запускается.
Есть минимальный rollout path без ещё полноценного экспортёра.
День 3. Teacher rollout exporter и базовый сбор траекторий

Задачи дня:

Реализовать экспорт траекторий по эпизодам.
Для каждого шага сохранять:
observation_t;
action_t;
reward_t;
done_t;
optional info/debug;
episode_id;
step_id.
Отдельно решить вопрос с mask:
либо сохранять teacher-side valid action mask напрямую;
либо сохранять достаточный state/info для её последующего восстановления;
приоритетнее — сохранять mask явно, если это возможно без ломки пайплайна.
Собирать rollout’ы в reproducible batches:
небольшой debug batch;
основной training batch.
Ввести первичную валидацию экспортируемых данных:
одинаковая длина массивов;
корректные step transitions;
отсутствуют NaN/Inf;
done корректно закрывает эпизод.
Добавить лёгкую статистику по rollout batch:
число эпизодов;
mean episode length;
action type histogram;
reward mean/std.

Что особенно важно:

Пока не заниматься преобразованием Gym → Unity.
Сначала получить сырой, но чистый и самосогласованный teacher dataset.

Риски:

Экспортировать только action и observation, а потом понять, что нет диагностик для выяснения несовместимостей.
Сразу “подгонять” данные под Unity и потерять исходный teacher truth.

Итог дня:

Есть сырой teacher rollout dataset.
Можно открыть экспорт и убедиться, что teacher trajectory действительно собирается шаг за шагом.
День 4. Dataset adapter: observation/action conversion под Unity-контракт

Задачи дня:

Реализовать Python-side adapter между Gym teacher data и Unity target contract.
Начать с observation conversion:
приводить teacher observation к spatial tensor [24, 24, 27], где это возможно;
исключить Unity-only global vector из strict BC encoder path;
зафиксировать normalization formula;
явно логировать случаи, где преобразование только approximate.
Затем реализовать action conversion:
mapping action types;
mapping directions;
mapping produce unit subset;
remap / filter unsupported action types;
remap attack target в local 3×3 representation;
логировать dropped / remapped actions.
Для каждого типа несовместимости завести conversion report:
сколько примеров перенесено без изменений;
сколько адаптировано;
сколько отброшено;
по какой причине.
Согласовать adapter с ранее зафиксированными gaps:
global vector excluded;
normalization adapted;
attack target reduced;
extra unit types filtered or mapped;
missing action types filtered.

Что особенно важно:

Не скрывать потери данных.
Любой фильтр должен быть явным и репортируемым.
Adapter — это центральный артефакт Week 5, потому что именно он делает возможным Week 6.

Итог дня:

Есть рабочий dataset adapter Gym → UnityMvpTransferSpec/LegacyGymCompatibleSpec.
По каждому основному gap есть кодовое или документированное mitigation rule.
День 5. Contract-level validation и sanity checks на адаптированном датасете

Задачи дня:

Проверить адаптированный датасет на строгую совместимость с Unity-side контрактом.
Ввести validator, который проверяет:
правильную shape observation;
диапазоны значений;
one-hot slices;
branch sizes для action;
диапазон attack target;
отсутствие unsupported action values.
Сверить policy-side semantics с Week 3/4 Unity layer:
observation соответствует LegacyGymCompatibleSpec;
global vector не подмешивается случайно;
action semantics не противоречат Unity decoder;
mask semantics трактуется как diagnostic/pre-sampling layer, а не authoritative runtime truth.
Подготовить короткие sanity-эксперименты:
выборка нескольких эпизодов;
проверка распределения action types;
доля отброшенных/ремапленных действий;
наличие attack/local-target кейсов;
доля production actions, переживших conversion.
Сформировать первый quality report по датасету:
usable samples;
dropped samples;
conversion loss;
class imbalance.

Что важно:

Здесь ещё не надо запускать BC в Unity.
День нужен, чтобы не тащить плохой датасет в Week 6.

Итог дня:

Адаптированный teacher dataset проходит contract-level validation.
Понятно, насколько он пригоден для BC и где остаются слабые места.
День 6. Подготовка BC-ready артефактов и dry run будущего Week 6

Задачи дня:

Сформировать финальные BC-ready exports:
train split;
validation split;
optional debug split.
Определить canonical sample structure для student-side потребления:
input tensor;
optional mask;
target action branches;
metadata.
Подготовить минимальный dry run:
student-side loader читает export;
batch shape корректен;
branches декодируются;
нет неожиданных missing fields.
Проверить, что teacher dataset действительно можно использовать как supervised target:
target branches детерминированы;
нет конфликтующих label’ов для одного и того же sample id;
action distribution не вырождена в один доминирующий класс.
Подготовить список технических задач, которые сразу перейдут в Week 6:
student encoder;
BC loss per branch;
mask-aware training or evaluation;
partial transfer of backbone/head.

Что особенно важно:

Не пытаться уже в этот день строить полноценный student.
Достаточно dry run на уровне совместимости данных и будущего train loader.

Итог дня:

Есть BC-ready dataset и подтверждение, что Week 6 может начинаться без рефакторинга Week 5 артефактов.
День 7. Полировка, документация и фиксация ограничений Week 5

Задачи дня:

Очистить Python API teacher pipeline.
Убрать ad-hoc код из rollout/export/adapter path.
Документировать public entrypoints:
как запускать rollout;
как собирать exports;
как валидировать dataset;
где лежат conversion reports.
Подготовить итоговый summary-артефакт недели, например:
WEEK5_TEACHER_PIPELINE_SUMMARY.md
Зафиксировать честные ограничения недели:
teacher quality ограничена доступной policy;
adapter в некоторых местах approximation, а не bijective mapping;
часть действий фильтруется;
mask semantics не полностью переносится как runtime truth;
direct weight transfer всё ещё blocked и не является задачей Week 5.
Отдельно подготовить bridge в Week 6:
какие файлы считаются canonical input;
какие checkpoints ждут student-side;
какие риски нужно мониторить на BC integration.

Итог дня:

Week 5 оформлена как завершённый и воспроизводимый teacher-data этап.
Есть готовый вход в Week 6 без расплывчатости и без ручной “магии”.
Сводка недели по результатам

К концу Week 5 должно быть так:

teacher pipeline запускается воспроизводимо;
teacher trajectories экспортируются стабильно;
Gym → Unity dataset adapter реализован;
ключевые compatibility gaps переведены в явные conversion rules;
BC-ready dataset собран и проверен;
документ Unity <-> Gym-μRTS для observation/action/mask semantics оформлен;
Week 6 можно начать с интеграции student/BC path, а не с доразбора форматов.