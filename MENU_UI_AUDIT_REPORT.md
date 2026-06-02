# Menu / UI / HUD Audit Report

Дата аудита: 2026-06-02  
Целевая ветка по постановке задачи: `cleanup/safe-audit-only`

## 1. Scope и ограничения

Аудит выполнен без изменения C#-кода, prefab и Unity-сцен. Единственное изменение репозитория на этом этапе - создание данного markdown-отчёта.

Подробно проверены:

- `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`
- `Assets/Scenes/MainMenu.unity`
- список всех assets в `Assets/Scenes`
- `Assets/Scripts/Presentation/*`
- `Assets/Scripts/Gameplay/Match/EpisodeController.cs`
- `Assets/Scripts/MLAgents/Stage7B/MlAgentsTrainingBootstrap.cs`
- `Assets/Scripts/MLAgents/Stage7B/StudentMlAgent.cs`
- `Assets/Scripts/MLAgents/Stage7B/TeacherReplay/Stage7BTeacherReplayDemoOrchestrator.cs`
- `Assets/Scripts/ML/Week6StudentPolicyAdapter.cs`
- связанные UI-prefab и Sprite assets.

Важно: в проекте уже есть рабочая Canvas-based UI-ветка. Создавать новую UI-систему или новый Canvas не требуется. Следующие этапы должны расширять существующую реализацию.

## 2. Сцены

В `Assets/Scenes` найдено 14 сцен:

- `AnimationPreview.unity`
- `AnimationShowcase.unity`
- `Bootstrap.unity`
- `GameScene.unity`
- `HumanPlay_Demo_PlayerVsAI.unity`
- `MainMenu.unity`
- `PPO_TrainingSandbox_Player1AI_vs_ScriptedBot.unity`
- `SampleScene.unity`
- `Visual3EC_GameplayAnimatorValidation.unity`
- `VisualPreview.unity`
- `Week6_StudentSanity.unity`
- `Week6_StudentStaticHarvestLayout.unity`
- `Week6_StudentVisualInspection.unity`
- `Week7_MLAgents_StudentVsScriptedBot.unity`

В Build Settings включены:

| Build index | Scene |
| --- | --- |
| 0 | `Assets/Scenes/MainMenu.unity` |
| 1 | `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity` |
| 2 | `Assets/Scenes/SampleScene.unity` |

`Week7_MLAgents_StudentVsScriptedBot.unity` существует, но на следующих этапах изменяться не должна.

## 3. Главное меню

Главное меню реализовано отдельно от игрового HUD:

- сцена: `Assets/Scenes/MainMenu.unity`
- корневой объект: `MenuControllers`
- компоненты: `RTS.Presentation.UI.MainMenuController`, `RTS.Presentation.UI.SceneFlowController`
- код: `Assets/Scripts/Presentation/UI/MainMenuController.cs`
- переходы сцен: `Assets/Scripts/Presentation/UI/SceneFlowController.cs`

`MainMenuController.Awake()` программно строит существующий `MainMenuCanvas`. В сцене не хранится готовое дерево UI-элементов: оно создаётся runtime-кодом поверх сериализованных Sprite и цветов.

Основная панель:

- `MenuPanel`: `760 x 620`
- заголовок: `Unity RTS Prototype / Agent vs Player Demo`
- контейнер кнопок: `460 x 290`
- spacing кнопок: `26`
- размер menu-кнопки: `440 x 70`

Кнопки:

| Кнопка | Действие |
| --- | --- |
| `Start Demo` | `SceneFlowController.LoadDemo()` |
| `Settings` | показывает модальное окно настроек |
| `Quit` | `SceneFlowController.Quit()` |

`SceneFlowController` использует:

- `_mainMenuSceneName = "MainMenu"`
- `_demoSceneName = "HumanPlay_Demo_PlayerVsAI"`
- `LoadDemo()`
- `LoadMainMenu()`
- `RestartCurrentScene()`
- `Quit()`

Отдельный menu controller уже существует. Переносить меню в HUD/controller или создавать новую menu-систему не нужно.

## 4. Игровой HUD

В `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity` одновременно присутствуют две UI-ветки.

### 4.1. Основной runtime HUD

Корневой объект: `HumanPlayCanvas`.

Компоненты:

- `Canvas`
- `CanvasScaler`
- `GraphicRaycaster`
- `RTS.Presentation.UI.HumanPlayCanvasController`

Связанный prefab:

- `Assets/Prefabs/UI/HumanPlayCanvas.prefab`

Prefab содержит один root-объект `HumanPlayCanvas`; дочерние панели программно строятся в `HumanPlayCanvasController.Awake()` методом `BuildHud()`.

Основные файлы:

- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- `Assets/Scripts/Presentation/UI/TopResourceBarView.cs`
- `Assets/Scripts/Presentation/UI/SelectionInfoPanelView.cs`
- `Assets/Scripts/Presentation/UI/CommandPanelView.cs`
- `Assets/Scripts/Presentation/UI/ProductionPanelView.cs`
- `Assets/Scripts/Presentation/UI/MetricsPanelView.cs`
- `Assets/Scripts/Presentation/UI/ContextActionMenuView.cs`
- `Assets/Scripts/Presentation/UI/PanelVisibilityController.cs`

Структура HUD:

| Блок | Содержимое |
| --- | --- |
| `TopResourceBar` | ресурсы P1/P2, phase, step, `Start AI vs P2`, `Menu` |
| `SelectionInfoPanel` | выбранный объект / группа |
| `CommandPanel` | status команд, `Stop`, `Restart`, `Main Menu` |
| `ProductionPanel` | `Worker`, `Light`, `Heavy`, `Ranged` |
| `MetricsPanel` | диагностические метрики, изначально скрыт |
| `PauseMenu` | `Continue`, `Restart Match`, `Settings`, `Toggle Metrics`, `Main Menu`, `Quit` |
| `HudSettingsPanel` | fullscreen, volume, `Back` |
| `ContextActionMenu` | контекстные `Move`, `Build Barracks`, `Gather`, `Attack` |

Дополнительные hotkeys:

- `Escape`: pause menu
- `F1`: HUD visibility
- `F2`: metrics visibility
- `F3`: selection panel visibility
- `F4`: production panel visibility

До старта матча HUD уже может быть построен и показывать phase/resources/status. Во время матча те же view обновляются из `MatchManager`, selection и command controllers.

### 4.2. Legacy IMGUI HUD

На объекте `PresentationControls` также находится:

- `RTS.Presentation.HumanPlayHudController`

Файл:

- `Assets/Scripts/Presentation/HumanPlayHudController.cs`

Этот HUD рисуется через `OnGUI()` / `GUILayout`, а не через Canvas. В demo-сцене:

- `_showHud = true`
- `_leftPanelPosition = (10, 90)`
- `_rightPanelPosition = (500, 90)`
- `_panelWidth = 460`
- `_leftPanelHeight = 560`
- `_rightPanelHeight = 560`

Legacy HUD содержит:

- mode diagnostics
- match phase / step / winner
- resources и alive unit counts
- speed controls
- `Start Player1 vs AI`
- `Start AI vs Player2`
- `Start AI vs AI`
- `Restart`
- `Return to Menu`
- `Quit`
- manual command buttons.

Это главный риск дублирования интерфейса: legacy IMGUI HUD и основной Canvas HUD активны одновременно. На следующем этапе нужно выбрать основной пользовательский HUD и не создавать третью UI-ветку. Предпочтительный кандидат - уже существующий `HumanPlayCanvasController`; legacy HUD можно оставить как диагностический fallback, но не показывать одновременно в обычном demo-flow.

## 5. Компоненты игрового управления

На `PresentationControls` находятся:

- `GameSpeedController`
- `HumanPlayModeController`
- `HumanPlayerController`
- `HumanPlayHudController`
- `PlayerCommandController`
- `PlayerSelectionController`
- `SelectionManager`
- `SelectionMarkerController`

Дополнительно:

- `SceneFlowController` находится на отдельном объекте `SceneFlowController`
- `EpisodeController` находится на отдельном объекте `EpisodeController`
- `MlAgentsTrainingBootstrap` находится на `Stage7B_MLAgentsTrainingBootstrap`.

`HumanPlayModeController` является центральным presentation-controller для переключения режимов матча. `SceneFlowController` отвечает только за переходы сцен.

## 6. Кнопочные текстуры и стили

UI использует сериализованные поля типа `Sprite`, а не прямой `Texture2D`, не prefab-кнопки и не `GUIStyle`.

Общие Sprite:

| Назначение | Asset |
| --- | --- |
| panel | `Assets/Art/UI/Kenney/UI_Pack_RPG_Expansion/PNG/panel_brown.png` |
| normal button | `Assets/Art/UI/Kenney/UI_Pack_RPG_Expansion/PNG/buttonLong_beige.png` |
| pressed button | `Assets/Art/UI/Kenney/UI_Pack_RPG_Expansion/PNG/buttonLong_beige_pressed.png` |

Иконки menu-сцены:

| Назначение | Asset |
| --- | --- |
| settings | `Assets/Art/UI/Kenney/Game_Icons/PNG/White/2x/gear.png` |
| quit | `Assets/Art/UI/Kenney/Game_Icons/PNG/White/2x/power.png` |

Иконки demo HUD:

| Назначение | Asset |
| --- | --- |
| pause/menu | `Assets/Art/UI/Kenney/Game_Icons/PNG/White/2x/pause.png` |
| settings | `Assets/Art/UI/Kenney/Game_Icons/PNG/White/2x/gear.png` |
| main menu | `Assets/Art/UI/Kenney/Game_Icons/PNG/White/2x/home.png` |
| start/target | `Assets/Art/UI/Kenney/Game_Icons/PNG/White/2x/target.png` |

Подключение:

- Sprite хранятся в serialized fields `MainMenuController` и `HumanPlayCanvasController`
- панели создаются как `Image`, `Image.Type.Sliced` при наличии Sprite
- кнопки создаются как `Image + Button`
- `Button.spriteState.pressedSprite` получает `buttonLong_beige_pressed.png`
- контекстное меню получает Sprite через `ContextActionMenuView.Initialize(...)`.

Стили и размеры основного HUD:

- reference resolution: `1920 x 1080`
- top bar offsets: `(16, -72)` / `(-16, -14)`
- top bar padding: `14, 14, 8, 8`
- top bar spacing: `14`
- стандартная HUD-кнопка: обычно высота `42` или `44`
- bottom panel offsets: `(16, 16)` / `(-16, 244)`
- bottom panel spacing: `12`
- context menu width: `230`, строка действия: `42`, padding: `8`
- panel color: `(0.08, 0.09, 0.08, 0.88)`
- button color: `(0.78, 0.67, 0.48, 1.0)`
- text color: `(0.96, 0.92, 0.82, 1.0)`.

В `Assets/Art/UI/Kenney/UI_Pack_RPG_Expansion/PNG` есть дополнительные panel-варианты (`panel_beige`, `panel_beigeLight`, `panel_blue`, inset-варианты), но текущая сериализация меню и HUD использует `panel_brown.png`.

## 7. Автозапуск матча

В demo-сцене автозапуск настроен в нескольких местах.

### 7.1. `MlAgentsTrainingBootstrap`

Файл:

- `Assets/Scripts/MLAgents/Stage7B/MlAgentsTrainingBootstrap.cs`

Логика:

- поле `_autoStartEpisodeOnStart`
- в `Start()` для режима, отличного от `TrainerControlled`, вызывается `StartNewEpisode(...)`, только если `_autoStartEpisodeOnStart == true`
- в `TrainerControlled` выполняется подготовка runtime без обычного auto-start.

Serialized значение в `HumanPlay_Demo_PlayerVsAI.unity`:

- `_stage7BRuntimeMode = InferenceOnly`
- `_autoStartEpisodeOnStart = false`
- `_stepScriptedOpponent = false`.

### 7.2. `EpisodeController`

Файл:

- `Assets/Scripts/Gameplay/Match/EpisodeController.cs`

Логика:

- поле `_autoStartOnPlay`
- `Start()` вызывает `StartNewEpisode()`, только если `_autoStartOnPlay == true`
- `_autoRestartEpisodes` отдельно управляет запуском следующего эпизода после terminal event.

Serialized значение в demo-сцене:

- `_autoStartOnPlay = false`
- `_autoRestartEpisodes = false`.

### 7.3. `HumanPlayModeController`

Файл:

- `Assets/Scripts/Presentation/HumanPlayModeController.cs`

Логика:

- поле `_autoStartOnEnable`
- `OnEnable()` и `Start()` вызывают `BeginInitialAutoStartIfNeeded()`
- coroutine ждёт готовность runtime services
- затем запускает `_initialMode`.

Serialized значение в demo-сцене:

- `_autoStartOnEnable = true`
- `_initialMode = AIvsPlayer2`
- `_autoStartRuntimeReadyTimeoutSeconds = 5`
- `_loadMenuSceneOnReturn = true`
- `_menuSceneName = "MainMenu"`.

Итог: обычный интерактивный автозапуск demo-сцены сейчас выполняется через `HumanPlayModeController`, а не через `MlAgentsTrainingBootstrap` и не через `EpisodeController`.

### 7.4. Косвенные reset/start paths

`StudentMlAgent.OnEpisodeBegin()` вызывает:

- `_bootstrap.StartNewEpisodeForAgentReset()` в `TrainerControlled`
- `_bootstrap.StartNewEpisode("agent_on_episode_begin", "StudentMlAgent.OnEpisodeBegin")` в остальных режимах.

`MlAgentsTrainingBootstrap.EnsureReadyForDecision()` может вызвать recovery-start, если match не находится в `Running`.

`Stage7BTeacherReplayDemoOrchestrator` присутствует в demo-сцене, но его smoke-flow запускается вручную через context menu и не является обычным UI auto-start.

## 8. Запуск режимов

Файл:

- `Assets/Scripts/Presentation/HumanPlayModeController.cs`

### `StartAIvsPlayer2`

- вызывает `StartHumanVsAi(Owner.Player2, HumanPlayMode.AIvsPlayer2)`
- human side получает `Idle`
- AI side получает предпочитаемый AI mode, обычно `StudentInference`
- затем вызывается `_episodeController.StartNewEpisode()`.

### `StartPlayer1VsAI`

- вызывает `StartHumanVsAi(Owner.Player1, HumanPlayMode.Player1vsAI)`
- Player1 получает `Idle`
- AI side получает предпочитаемый AI mode
- затем вызывается `_episodeController.StartNewEpisode()`.

### `StartAIvsAI`

- вызывает `ConfigureWeek6PlayerControlModes(false, Idle, Idle)`
- сбрасывает human command diagnostics
- вызывает `_episodeController.StartNewEpisode()`
- при отключённом student match control `EpisodeController` возвращается к обычному heuristic decision source.

### `RestartMatch`

- для `AIvsPlayer2` повторно вызывает `StartAIvsPlayer2()`
- для `Player1vsAI` / `Player1vsScriptedOrHeuristic` повторно вызывает `StartPlayer1VsAI()`
- для остальных режимов вызывает `_episodeController.ResetEpisode()`
- fallback: `_trainingBootstrap.StartNewEpisode(...)`.

### `ReturnToMenu`

Есть два пути:

- legacy HUD вызывает `HumanPlayModeController.ReturnToMenu()`
- Canvas HUD вызывает `SceneFlowController.LoadMainMenu()`.

В demo-сцене `HumanPlayModeController` настроен на `_loadMenuSceneOnReturn = true`, `_menuSceneName = "MainMenu"`, поэтому оба пути ведут в `MainMenu`.

### `ConfigureWeek6PlayerControlModes`

Находится в:

- `Assets/Scripts/Gameplay/Match/EpisodeController.cs`

Метод сохраняет:

- `enableStudentMatchControl`
- `player1Mode`
- `player2Mode`

и запускает валидацию конфигурации.

## 9. Enum и разрешённые пары control mode

### `HumanPlayMode`

Файл:

- `Assets/Scripts/Presentation/HumanPlayMode.cs`

Значения:

- `AIvsAI = 0`
- `Player1vsAI = 1`
- `AIvsPlayer2 = 2`
- `Player1vsScriptedOrHeuristic = 3`
- `PausedDemo = 4`.

### `Week6PlayerControlMode`

Файл:

- `Assets/Scripts/ML/Week6StudentPolicyAdapter.cs`

Значения:

- `Idle = 0`
- `HeuristicBaseline = 1`
- `StudentInference = 2`.

### Валидация `EpisodeController`

Если `_enableWeek6StudentMatchControl == false`, комбинация принимается без Week6-валидации и используется обычный decision source.

Если `_enableWeek6StudentMatchControl == true`:

- допустимы только `Idle`, `HeuristicBaseline`, `StudentInference`
- запрещено `StudentInference + StudentInference`
- запрещено `HeuristicBaseline + HeuristicBaseline`
- `StudentInference` требует `Week6StudentPolicyAdapter`
- `HeuristicBaseline` требует `HeuristicPolicyAdapter`.

Практически используемые human-vs-AI пары:

- `Idle + StudentInference`
- `StudentInference + Idle`
- fallback при отсутствии student adapter: `Idle + HeuristicBaseline`
- fallback в обратную сторону: `HeuristicBaseline + Idle`
- при отсутствии heuristic adapter AI mode может деградировать до `Idle`.

## 10. Что можно менять безопасно на следующих этапах

Предпочтительная зона изменений:

- `Assets/Scripts/Presentation/UI/MainMenuController.cs`
- `Assets/Scripts/Presentation/UI/SceneFlowController.cs`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- остальные `Assets/Scripts/Presentation/UI/*View.cs`
- `Assets/Scripts/Presentation/HumanPlayModeController.cs`
- `Assets/Scripts/Presentation/HumanPlayHudController.cs`, только для отключения/изоляции legacy diagnostics
- `Assets/Prefabs/UI/HumanPlayCanvas.prefab`
- сериализованные presentation-поля в `Assets/Scenes/MainMenu.unity`
- сериализованные presentation-поля в `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`
- существующие Sprite assets в `Assets/Art/UI/Kenney/*`, без замены архитектуры.

Изменения сцены должны быть минимальными и ограничиваться presentation wiring / visibility / serialized UI settings.

## 11. Что менять нельзя

Не менять:

- Python/training/checkpoint файлы
- observation/action contract
- `ActionDecoder`
- `ActionApplier`
- semantics `MatchManager.ApplyCommand`
- reward/terminal logic
- `Assets/Scenes/Week7_MLAgents_StudentVsScriptedBot.unity`
- teacher/student pipeline
- обучение и checkpoint assets.

Также не рекомендуется менять без отдельной задачи:

- `Assets/Scripts/Gameplay/Match/EpisodeController.cs`
- `Assets/Scripts/MLAgents/Stage7B/MlAgentsTrainingBootstrap.cs`
- `Assets/Scripts/MLAgents/Stage7B/StudentMlAgent.cs`
- `Assets/Scripts/ML/Week6StudentPolicyAdapter.cs`.

Для UI-задачи уже достаточно presentation-слоя и serialized presentation-полей demo-сцены.

## 12. Потенциальные риски

1. Одновременный показ Canvas HUD и legacy IMGUI HUD создаёт дублирование кнопок, диагностики и пользовательских действий.
2. Автозапуск распределён между `HumanPlayModeController`, `EpisodeController`, `MlAgentsTrainingBootstrap` и reset-path `StudentMlAgent`. Нельзя включать дополнительные auto-start flags без проверки двойного reset/start.
3. `HumanPlayCanvasController` строит дочерние UI-объекты runtime-кодом. Добавление вручную сохранённых дочерних панелей в prefab без адаптации `BuildHud()` создаст дубликаты.
4. В `ReturnToMenu` существуют два presentation-пути. Их поведение сейчас совпадает, но дальнейшие изменения должны сохранить единый scene-flow.
5. `StartAIvsAI()` отключает Week6 student match control и тем самым использует другой decision-source path, чем human-vs-AI режимы.
6. `StudentInference` зависит от наличия `Week6StudentPolicyAdapter`; fallback должен оставаться явным и диагностируемым.
7. `MainMenuController` и `HumanPlayCanvasController` используют сериализованные Sprite. Потеря ссылок в сцене/prefab приведёт к fallback `Image.Type.Simple` и визуальной деградации.
8. Локальный shell в ходе аудита не запускался из-за инфраструктурной ошибки `spawn setup refresh`, поэтому `git status` и textual diff не были доступны. Unity Editor сообщил, что активная сцена после read-only проверки возвращена в `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity` и `isDirty = false`.

## 13. Предложенный пошаговый план реализации

1. Зафиксировать `HumanPlayCanvasController` как основной пользовательский HUD для demo-flow.
2. Отключить видимость legacy `HumanPlayHudController` в обычном demo-flow, сохранив его как диагностический fallback при необходимости.
3. Не создавать новый Canvas и не добавлять новую UI-систему.
4. Добавлять недостающие menu/HUD-действия только в существующие runtime builders `MainMenuController.BuildMenu()` и `HumanPlayCanvasController.BuildHud()`.
5. Сохранить существующий `SceneFlowController`: `MainMenu -> HumanPlay_Demo_PlayerVsAI -> MainMenu`.
6. Сохранить единственный интерактивный auto-start path через `HumanPlayModeController._autoStartOnEnable`, пока продуктовая задача явно не потребует стартового экрана внутри demo-сцены.
7. Не включать `_autoStartEpisodeOnStart` и `_autoStartOnPlay` одновременно с presentation auto-start.
8. При изменении состава режимов использовать существующие методы `StartAIvsPlayer2`, `StartPlayer1VsAI`, `StartAIvsAI`, `RestartMatch`, `ReturnToMenu`.
9. Не расширять `Week6PlayerControlMode` и не менять валидацию `EpisodeController` в рамках UI-этапа.
10. После реализации проверить Play Mode flow: `MainMenu -> Start Demo -> AIvsPlayer2`, pause, restart, main menu, quit, fallback при отсутствии student adapter и отсутствие двойного старта эпизода.

## 14. Итог

Проект уже содержит отдельное главное меню, переходы сцен, основной Canvas HUD, pause/settings menu, context action menu, Sprite-based оформление и legacy IMGUI HUD. Новая UI-система не нужна. Следующий этап должен быть точечной очисткой presentation-слоя: убрать одновременный показ двух HUD-веток, сохранить текущий Canvas HUD и не затрагивать ML/training/runtime contracts.
