# Play Mode Startup Menu Fix Report

Дата: 2026-06-02
Ветка: `cleanup/safe-audit-only`

## 1. Проблема

При прямом запуске `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity` из Editor компонент `HumanPlayModeController` выполнял fallback:

```text
StartConfiguredInitialMode()
```

Если `DemoLaunchOptions.HasExplicitMode == false`, fallback использовал serialized `_initialMode` и запускал матч через один из presentation-методов режима. Для demo-сцены `_initialMode` был равен `AIvsPlayer2`, поэтому Play Mode сразу стартовал матч.

## 2. Изменённые файлы

- `Assets/Scripts/Presentation/HumanPlayModeController.cs`
- `PLAYMODE_STARTUP_MENU_FIX_REPORT.md`

Сцены не изменялись.

## 3. Новый startup flow

В `HumanPlayModeController` добавлено serialized presentation-поле:

```text
bool _redirectToMainMenuWhenNoLaunchMode = true
```

В начале `StartInitialModeWhenRuntimeReady()` теперь проверяется `DemoLaunchOptions.HasExplicitMode`.

### Явный режим присутствует

Flow сохранён:

1. Controller ожидает готовность runtime services.
2. Читает `DemoLaunchOptions.RequestedMode`.
3. Вызывает `DemoLaunchOptions.Clear()`.
4. Вызывает `StartRequestedDemoMode(requestedMode)`.

Mapping не изменён:

| Demo launch mode | Runtime presentation method |
| --- | --- |
| `AIvsPlayer` | `StartAIvsPlayer2()` |
| `AIvsBot` | `StartAIvsBot()` |
| `AIvsAI` | `StartAIvsAI()` |

### Явный режим отсутствует

Flow изменён:

1. Runtime services не ожидаются.
2. `_initialMode` не запускается.
3. `StartAIvsPlayer2()`, `StartAIvsAI()` и `StartNewEpisode()` не вызываются.
4. Вызывается `HandleMissingLaunchMode()`.
5. При включённом `_redirectToMainMenuWhenNoLaunchMode` загружается `_menuSceneName`.

Если redirect отключён или имя сцены пустое, demo остаётся в безопасном idle-состоянии `PausedDemo`.

Старый метод `StartConfiguredInitialMode()` удалён, чтобы fallback auto-start нельзя было вызвать случайно.

## 4. Защита от бесконечной загрузки

Перед redirect проверяется:

```text
SceneManager.GetActiveScene().name != _menuSceneName
```

`HumanPlayModeController` находится в demo-сцене, а не в `MainMenu`, поэтому обычный flow:

```text
HumanPlay_Demo_PlayerVsAI -> MainMenu
```

выполняется один раз.

`SceneFlowController` не изменялся. Main Menu не загружает demo без пользовательского действия.

## 5. Serialized flags demo-сцены

Проверены значения в `Assets/Scenes/HumanPlay_Demo_PlayerVsAI.unity`:

```text
MlAgentsTrainingBootstrap._autoStartEpisodeOnStart = 0
EpisodeController._autoStartOnPlay = 0
HumanPlayModeController._autoStartOnEnable = 1
HumanPlayModeController._initialMode = AIvsPlayer2
HumanPlayModeController._menuSceneName = MainMenu
```

`_autoStartOnEnable` сохранён: он теперь обрабатывает явный `DemoLaunchOptions` или redirect в меню. `_initialMode` больше не является fallback-запуском.

## 6. Runtime smoke-test

Выполнено:

1. Активная Editor-сцена перед тестом: `HumanPlay_Demo_PlayerVsAI`.
2. Запущен Play Mode.
3. Активная runtime-сцена после старта: `MainMenu`.
4. Unity Console: `0` errors.
5. Play Mode остановлен.
6. Editor вернулся к `HumanPlay_Demo_PlayerVsAI`.

Smoke-test подтвердил: прямой запуск demo-сцены больше не стартует матч и перенаправляет пользователя в главное меню.

Runtime diagnostic trace/report-файлы, обновлённые Play Mode проверкой, восстановлены до исходного состояния.

## 7. Дополнительные проверки

Выполнено:

- Unity script refresh;
- Unity compilation: `0` errors;
- Unity Console после compilation: `0` errors;
- scoped `git diff --check`: чисто;
- статически подтверждён mapping трёх явных menu-режимов;
- protected runtime diff пуст.

Не выполнялось автоматически:

- пользовательский кликовый проход `MainMenu -> Start -> выбор режима` для всех трёх кнопок.

Доступный Unity MCP не предоставляет безопасный API для пользовательского клика по runtime-built `Button.onClick`. Mapping и scene-flow проверены статически; финальный click-through остаётся ручным.

## 8. Соблюдённые ограничения

Не изменялись:

- `DemoLaunchOptions`;
- `SceneFlowController`;
- camera focus logic;
- gameplay/ML/runtime semantics;
- `ActionDecoder`;
- `ActionApplier`;
- `MatchManager`;
- `EpisodeController`;
- `MlAgentsTrainingBootstrap`;
- Python/training/checkpoints;
- ONNX/model assets;
- `Week7_MLAgents_StudentVsScriptedBot.unity`;
- сцены.

До начала задачи существовал dirty submodule:

- `python/week5_teacher_legacy032/third_party/gym_microrts_legacy032_source`

Он оставлен нетронутым.
