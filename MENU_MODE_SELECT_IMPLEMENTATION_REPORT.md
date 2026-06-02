# Menu Mode Select Implementation Report

Дата: 2026-06-02  
Ветка: `cleanup/safe-audit-only`

## 1. Изменённые файлы

- `Assets/Scripts/Presentation/UI/DemoLaunchOptions.cs` - добавлен presentation-only holder выбранного режима.
- `Assets/Scripts/Presentation/UI/DemoLaunchOptions.cs.meta` - создан Unity при импорте нового скрипта.
- `Assets/Scripts/Presentation/UI/MainMenuController.cs` - главное меню и экран выбора режима.
- `Assets/Scripts/Presentation/UI/SceneFlowController.cs` - методы запуска demo для трёх режимов.
- `Assets/Scripts/Presentation/HumanPlayMode.cs` - добавлен `AIvsBot = 5` без изменения существующих значений.
- `Assets/Scripts/Presentation/HumanPlayModeController.cs` - обработка выбранного режима и `StartAIvsBot()`.
- `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity` - legacy IMGUI HUD отключён одной serialized-строкой: `_showHud: 0`.

Также сохранён аудит предыдущего этапа:

- `MENU_UI_AUDIT_REPORT.md`

## 2. Главное меню

Существующий `MainMenuController` сохранён как единственная реализация главного меню. Новый Canvas не создавался.

Основной экран теперь содержит:

- заголовок `Unity RTS Prototype`
- `Start`
- `Settings`
- `Quit`

Кнопка `Start` больше не загружает demo-сцену сразу. Она показывает второй экран внутри того же runtime-built `MainMenuCanvas`.

Сохранены текущие serialized Sprite и стиль:

- `panel_brown.png`
- `buttonLong_beige.png`
- `buttonLong_beige_pressed.png`
- sliced `Image`
- текущие размеры menu-кнопок `440 x 70`.

## 3. Экран выбора режима

В `MainMenuController` добавлена вторая runtime-built панель `ModeSelectPanel`.

Заголовок:

- `Выбор режима`

Кнопки:

- `AI против AI`
- `AI против бота`
- `AI против игрока`
- `Назад`

`Назад` скрывает `ModeSelectPanel` и возвращает основной `MenuPanel`.

## 4. Передача режима в demo-сцену

Добавлен `DemoLaunchOptions`:

```text
DemoLaunchMode.AIvsPlayer
DemoLaunchMode.AIvsBot
DemoLaunchMode.AIvsAI
```

Это статический presentation-level holder без `ScriptableObject`, без изменения ML/runtime contracts.

В `SceneFlowController` добавлены:

- `LoadDemoAIvsPlayer()`
- `LoadDemoAIvsBot()`
- `LoadDemoAIvsAI()`

Каждый метод записывает `DemoLaunchOptions.SetMode(...)` и вызывает существующий `LoadDemo()`.

Старый `LoadDemo()` сохранён. Если режим не задан явно, он выставляет default `AIvsPlayer`, затем загружает `HumanPlay_Demo_PlayerVsAI`.

При возврате в главное меню `LoadMainMenu()` очищает holder.

## 5. Запуск выбранного режима

`HumanPlayModeController` при auto-start сначала проверяет `DemoLaunchOptions.HasExplicitMode`.

Если режим передан из меню:

| Demo launch mode | Runtime method |
| --- | --- |
| `AIvsPlayer` | `StartAIvsPlayer2()` |
| `AIvsBot` | `StartAIvsBot()` |
| `AIvsAI` | `StartAIvsAI()` |

После чтения выбора holder очищается, чтобы режим не залипал при последующих переходах.

Если demo-сцена открыта напрямую из Editor и явного выбора нет, сохранён прежний fallback через serialized `_initialMode`.

## 6. AI против бота

В `HumanPlayMode` добавлено:

- `AIvsBot = 5`

В `HumanPlayModeController` добавлен `StartAIvsBot()`.

Основной путь:

- Player1: `StudentInference`
- Player2: `HeuristicBaseline`
- human side: отсутствует
- manual control: выключен
- `enableStudentMatchControl: true`

Fallback при отсутствии student adapter:

- используется существующий baseline AI-vs-AI path
- `ConfigureWeek6PlayerControlModes(false, Idle, Idle)`
- `EpisodeController` использует обычный heuristic decision source
- запрещённая текущей валидацией пара `HeuristicBaseline + HeuristicBaseline` при включённом student control не создаётся.

`RestartMatch()` расширен для повторного запуска `AIvsBot`.

## 7. Legacy IMGUI HUD

`HumanPlayHudController.cs` не удалён.

В `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity` изменено только:

```text
_showHud: 1 -> 0
```

Основным интерфейсом остаётся существующий Canvas HUD:

- `Assets/Prefabs/UI/HumanPlayCanvas.prefab`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`

## 8. Выполненные проверки

### Компиляция

- выполнен Unity AssetDatabase refresh и повторная компиляция
- C# compile errors: `0`

### Runtime главного меню

В Play Mode из `Assets/Scenes/MainMenu.unity` подтверждено:

- создаётся `MainMenuCanvas`
- `MenuPanel` активен
- `ModeSelectPanel` создан и изначально скрыт
- `StartButton` создан
- `StartButton` использует `buttonLong_beige.png`
- pressed Sprite: `buttonLong_beige_pressed.png`
- ошибок и предупреждений menu-flow не обнаружено.

### Runtime прямого запуска demo

В Play Mode из `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity` подтверждено:

- Canvas HUD создаётся
- `HumanPlayHudController._showHud = false`
- compile errors: `0`
- `NullReferenceException`: `0`
- `ValidateWeek6ControlConfiguration` errors: `0`.

В runtime были видны существующие warnings ML inference / visual runtime. Они не вызваны новым menu-flow и не исправлялись в рамках данного этапа.

### Git diff

- `git diff --check` не обнаружил whitespace errors
- `Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity` не изменена
- `ActionDecoder` не изменён
- `ActionApplier` не изменён
- `MatchManager` не изменён
- Python/training/checkpoint файлы не входят в итоговый diff данного этапа
- runtime trace/report файлы, созданные Play Mode проверкой, возвращены в исходное состояние.

Pre-existing dirty state оставлен нетронутым:

- `python/week5_teacher_legacy032/third_party/gym_microrts_legacy032_source`

### Ручная проверка

Unity MCP подтвердил runtime-иерархию меню, но не предоставляет безопасный API для вызова `Button.onClick` как пользовательского клика. Ручной Game View проход остаётся нужен для финальной визуальной проверки:

1. `Start -> Назад`
2. `Start -> AI против игрока`
3. `Start -> AI против бота`
4. `Start -> AI против AI`
5. возврат в `Main Menu` после каждого запуска.

## 9. Соблюдённые ограничения

Не создавался новый Canvas или третья UI-ветка. Не добавлен обходной путь команд. Не изменялись:

- Python training pipeline
- checkpoints / ONNX models
- observation/action contracts
- `ActionDecoder`
- `ActionApplier`
- `MatchManager.ApplyCommand` semantics
- reward/terminal logic
- `Week7_MLAgents_StudentVsScriptedBot.unity`
- teacher/student pipeline.
