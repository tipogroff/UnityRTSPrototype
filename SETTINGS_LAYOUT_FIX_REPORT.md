# Settings Layout Fix Report

Дата: 2026-06-02
Ветка: `cleanup/safe-audit-only`

## 1. Причина визуальной ошибки

В `MainMenuController.BuildSettingsPanel()` панель `SettingsPanel` имела размер `760 x 700` и использовала одну общую `VerticalLayoutGroup`.

В эту вертикальную колонку одновременно попадали:

- header;
- 6 строк настроек;
- status text;
- две menu-кнопки высотой `70`.

Из-за этого layout был слишком высоким для части Game View viewport, нижняя строка уходила вниз, а длинные подписи переносились и визуально ломали сетку. Основной `MenuPanel` оставался активным под Settings modal, поэтому `Start / Settings / Quit` просвечивали через слой настроек.

## 2. Изменённые файлы

- `Assets/Scripts/Presentation/UI/MainMenuController.cs`
- `SETTINGS_LAYOUT_FIX_REPORT.md`

`DemoVisualSettings.cs` не изменялся. `HumanPlayCanvasController.cs` проверен, но не изменялся.

## 3. Новый layout Main Menu Settings

Сохранены существующие:

- `MainMenuCanvas`;
- runtime-built подход;
- `panel_brown.png`;
- `buttonLong_beige.png`;
- `buttonLong_beige_pressed.png`;
- presentation-only `DemoVisualSettings`.

`SettingsPanel` уменьшен с `760 x 700` до `700 x 560`.

Вместо общей вертикальной колонки используются отдельные фиксированные зоны:

1. Header: заголовок `Настройки`.
2. `SettingsContent`: список из 6 строк.
3. `SettingsStatus`: статус применения.
4. `Footer`: горизонтальный ряд `Применить` и `Назад`.

`ScrollRect` не потребовался: компактная фиксированная сетка помещается в панель.

## 4. Строки настроек

Каждая настройка занимает одну горизонтальную строку фиксированной высоты `42`.

Параметры:

- шаг между центрами строк: `48`;
- content-зона: `610 x 282`;
- label-колонка: `390 x 42`;
- value-кнопка: `190 x 42`;
- font size label: `18`;
- alignment label: `TextAnchor.MiddleLeft`;
- для label включён `HorizontalWrapMode.Overflow`.

Используются короткие подписи:

- `Сетка`
- `Маркеры юнитов`
- `Подсказки управления`
- `Качество графики`
- `Высота камеры`
- `Масштаб интерфейса`

## 5. Footer и status

Status расположен отдельно от списка настроек:

- размер: `610 x 30`;
- позиция по вертикали: `-410`.

Footer расположен отдельно:

- размер: `560 x 52`;
- позиция по вертикали: `-474`;
- две Sprite-кнопки: `250 x 48`;
- spacing: `20`.

Header, content, status и footer находятся внутри панели `700 x 560`.

## 6. Просвечивание Main Menu

При открытии Settings:

- `_mainPanel` скрывается;
- `_modeSelectPanel` скрывается;
- `SettingsModal` остаётся полноэкранным blocker overlay;
- `SettingsPanel` отображается поверх overlay.

При `Назад`:

- `SettingsModal` скрывается;
- вызывается `ShowMainPanel()`;
- основной экран меню восстанавливается.

ModeSelect-flow не изменён.

## 7. HUD Settings

`HumanPlayCanvasController.BuildSettingsPanel()` проверен.

HUD Settings уже использует компактные фиксированные координаты:

- panel: `700 x 560`;
- 6 строк с шагом `48`;
- отдельный status;
- отдельные `Применить` и `Назад`.

Overflow-аналог не обнаружен, поэтому HUD-файл не изменялся. `Escape / Continue / Main Menu` не затрагивались.

## 8. Проверки

Выполнено:

- Unity script refresh;
- Unity compilation: `0` errors;
- Unity Console: `0` errors;
- scoped `git diff --check` для `MainMenuController.cs`: чисто;
- итоговый diff просмотрен: изменён только presentation UI layout;
- защищённые gameplay/runtime/ML-файлы не изменялись.

Статически подтверждено:

- все 6 строк находятся внутри `SettingsContent`;
- status находится внутри `SettingsPanel`;
- обе footer-кнопки находятся внутри `SettingsPanel`;
- Settings скрывает основной `MenuPanel`;
- `Назад` восстанавливает основной `MenuPanel`;
- `ShowSettings()` не запускает demo;
- ModeSelect callbacks не изменялись.

Не выполнялось автоматически:

- пользовательский кликовый Game View smoke-pass.

Доступный Unity MCP не предоставляет безопасный API для вызова runtime-built `Button.onClick` как пользовательского клика. Финальная визуальная проверка в Game View остаётся ручной.

## 9. Ограничения

Не изменялись:

- новый Canvas или новая UI-система;
- gameplay/runtime/ML;
- Python/training/checkpoint;
- ONNX/model assets;
- observation/action contract;
- `ActionDecoder`;
- `ActionApplier`;
- `MatchManager`;
- `EpisodeController`;
- `MlAgentsTrainingBootstrap`;
- `Week7_MLAgents_StudentVsScriptedBot.unity`.

До начала задачи в рабочем дереве уже был dirty submodule:

- `python/week5_teacher_legacy032/third_party/gym_microrts_legacy032_source`

Он оставлен нетронутым.
