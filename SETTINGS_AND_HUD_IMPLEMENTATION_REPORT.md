# Settings and HUD Implementation Report

Дата: 2026-06-02
Ветка: `cleanup/safe-audit-only`

## 1. Изменённые файлы этого этапа

- `Assets/Scripts/Presentation/UI/DemoVisualSettings.cs`
- `Assets/Scripts/Presentation/UI/DemoVisualSettings.cs.meta`
- `Assets/Scripts/Presentation/UI/MainMenuController.cs`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- `Assets/Scripts/Presentation/UI/CommandPanelView.cs`

Сцены, gameplay, ML, Python, training и checkpoint-файлы на этом этапе не изменялись.

В рабочем дереве сохранены изменения предыдущего UI-этапа:

- `Assets/Scripts/Presentation/UI/DemoLaunchOptions.cs`
- `Assets/Scripts/Presentation/UI/SceneFlowController.cs`
- `Assets/Scripts/Presentation/HumanPlayMode.cs`
- `Assets/Scripts/Presentation/HumanPlayModeController.cs`
- `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`: только `_showHud: 1 -> 0`

## 2. Общий presentation-only holder настроек

Добавлен статический `DemoVisualSettings`. Он хранит runtime-значения:

1. `ShowGrid`
2. `ShowUnitMarkers`
3. `ShowControlHints`
4. `GraphicsQuality`: `Low / Medium / High`
5. `CameraHeight`: `Low / Medium / High`
6. `InterfaceScale`: `Small / Normal / Large`

Это только UI-placeholder model. Значения переключаются и доступны из главного меню и pause HUD, но намеренно не меняют gameplay, камеру, рендеринг, сетку, маркеры или масштаб Canvas: безопасная точка применения этих эффектов не входит в текущий scope.

## 3. Main Menu Settings

Существующий runtime-built `MainMenuCanvas` сохранён. Новый Canvas и новая UI-система не создавались.

`MainMenuController.BuildSettingsPanel()` теперь строит стилизованную панель `Настройки` на существующих Sprite:

- `panel_brown.png`
- `buttonLong_beige.png`
- `buttonLong_beige_pressed.png`

Старые `Volume` и `Fullscreen` controls заменены шестью placeholder-настройками. Каждая строка использует beige Sprite-кнопку со сменой значения. Добавлены:

- `Применить`: выводит `Настройки применены`
- `Назад`: закрывает modal и возвращает к основному меню

Русские runtime-строки записаны через `\u`-escape, чтобы исходники не зависели от кодировки shell.

## 4. Pause HUD Settings

`HumanPlayCanvasController.BuildSettingsPanel()` использует тот же `DemoVisualSettings` и тот же Sprite-based стиль.

Pause-flow сохранён:

- `Escape` открывает и закрывает pause menu
- если открыт `HudSettingsPanel`, первый `Escape` закрывает settings
- `Continue` возобновляет матч
- `Restart Match`, `Main Menu`, `Quit` сохранены

`HudSettingsPanel` содержит те же шесть placeholder-настроек, `Применить` и `Назад`.

## 5. HUD по режимам

### AI против игрока

- верхняя строка ресурсов видима
- selection panel видим
- command panel видим
- production panel работает для выбранных `Base / Barracks`
- context menu и ручные команды доступны только для `Player2`
- status явно показывает:
  - `Режим: AI против игрока`
  - `Игрок: Player2`
  - `Управление: активно` или ожидание старта матча
  - при пустом выборе: `Выберите юнит Player2 для отдачи приказа`

Существующий pipeline команд не изменён: selection, move, gather, build, production, attack, group orders и stop продолжают идти через presentation/order layer.

### AI против бота

- верхняя строка ресурсов видима
- command panel видим как информационный блок
- selection panel скрыт
- production panel скрыт
- context menu скрыт
- stale context callback отклоняется до order pipeline
- status показывает `Режим: AI против бота`, `Управление: недоступно`, `Human control inactive`

### AI против AI

Поведение HUD совпадает с AI против бота, но status показывает `Режим: AI против AI`.

## 6. Возврат в меню

Canvas-кнопка `Main Menu` по-прежнему вызывает `SceneFlowController.LoadMainMenu()`.

`SceneFlowController.LoadMainMenu()` вызывает `DemoLaunchOptions.Clear()`, поэтому выбранный режим не залипает при следующем запуске. Legacy IMGUI HUD остаётся отключённым serialized-полем `_showHud: 0`.

## 7. Проверки

Выполнено:

- Unity `AssetDatabase` full refresh
- Unity script compilation: `0` errors
- Unity Console после компиляции: `0` errors
- scoped `git diff --check` для изменённых UI-файлов: чисто
- точечный diff защищённых файлов пуст:
  - `ActionDecoder.cs`
  - `ActionApplier.cs`
  - `MatchManager.cs`
  - `EpisodeController.cs`
  - `MlAgentsTrainingBootstrap.cs`
  - `Week7_MLAgents_StudentVsScriptedBot.unity`
- demo scene diff проверен: сохранено только предыдущее `_showHud: 1 -> 0`
- статически подтверждено: `LoadMainMenu()` очищает `DemoLaunchOptions`

Не выполнялось автоматически:

- кликовый Game View проход по всем Settings-кнопкам
- переходы `MainMenu -> AI против игрока / бота / AI -> Main Menu`
- runtime-проверка pause/settings и ручных команд
- runtime-проверка отсутствия `NullReferenceException` и validation errors во всех трёх режимах

Причина: доступный Unity MCP не предоставляет безопасный API пользовательского клика по runtime-built `Button.onClick`, а Play Mode в этом рабочем дереве обновляет уже dirty runtime trace-файлы. Для сохранения существующих пользовательских изменений эти файлы не перезаписывались.

## 8. Существующее dirty-состояние вне scope

До начала этапа уже были изменены timer, runtime trace и Python report-файлы. Они оставлены нетронутыми.

Общий `git diff --check` всё ещё сообщает существовавшие trailing whitespace в:

- `python/stage7b_teacher_replay/stage7b_8b6_episode_boundary_fix_report.md`
- `python/stage7b_teacher_replay/stage7b_8d1_decision_scheduling_fix_report.md`

Scoped UI diff этих ошибок не содержит.

## 9. Соблюдённые ограничения

Не изменялись:

- Python/training/checkpoint файлы
- observation/action contract
- `ActionDecoder`
- `ActionApplier`
- semantics `MatchManager.ApplyCommand`
- reward/terminal logic
- `Week7_MLAgents_StudentVsScriptedBot.unity`
- teacher/student pipeline
- ML Agents bootstrap semantics
- `EpisodeController` validation semantics

## 10. Следующая проверка

Нужен ручной Game View smoke-pass:

1. Открыть MainMenu Settings, переключить все значения, нажать `Применить`, затем `Назад`.
2. Запустить `AI против игрока`, проверить status Player2, ручные команды, pause settings, `Continue`, `Main Menu`.
3. Запустить `AI против бота`, проверить скрытие ручных панелей и отсутствие config errors.
4. Запустить `AI против AI`, проверить то же поведение.
5. Проверить Unity Console на `NullReferenceException` и `ValidateWeek6ControlConfiguration`.
