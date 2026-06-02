# Camera Control Regression Fix Report

Дата: 2026-06-03
Ветка: `cleanup/safe-audit-only`

## 1. Проверка match-start focus

`RtsCameraController` проверен после добавления focus.

Focus уже является одноразовым:

1. `FocusOnOwnerAfterMatchStart()` запускает coroutine.
2. `FocusAfterMatchStart()` ожидает один кадр.
3. Один раз вызывает `ApplyGroundFocus()`.
4. Обновляет `transform.position` и `_targetPosition`.
5. Coroutine завершается.

В `LateUpdate()` focus point повторно не применяется. Каждый кадр продолжают вызываться:

- `ReadMovement()`;
- `ReadZoom()`;
- `ReadMiddleMouseDrag()`.

Match-start focus сохранён.

## 2. Причина регрессии mouse input

До исправления `ReadZoom()` и `ReadMiddleMouseDrag()` блокировали input при любом:

```text
EventSystem.current.IsPointerOverGameObject()
```

HUD построен через Canvas и содержит `Image`-панели. Даже пассивный HUD-элемент под курсором мог считаться UI hit и отключать wheel zoom или middle-mouse drag.

Дополнительно проверены fullscreen overlays:

- `ContextActionMenuView` создаёт fullscreen blocker, но выключает его через `gameObject.SetActive(false)` после инициализации;
- blocker активируется только при открытом context menu;
- `PauseMenu` изначально inactive;
- `HudSettingsPanel` изначально inactive;
- selection rectangle использует `raycastTarget = false`.

Постоянного invisible fullscreen blocker во время обычного матча не обнаружено.

## 3. Исправление

Изменены:

- `Assets/Scripts/Presentation/Camera/RtsCameraController.cs`
- `Assets/Scripts/Presentation/UI/HumanPlayCanvasController.cs`
- `CAMERA_CONTROL_REGRESSION_FIX_REPORT.md`

### Modal UI state

В `HumanPlayCanvasController` добавлено read-only свойство:

```text
IsCameraInputBlocked
```

Оно возвращает `true`, только когда открыт:

- pause menu;
- HUD settings;
- context action menu.

### Keyboard movement

`ReadMovement()`:

- не зависит от pointer-over-UI;
- продолжает менять `_targetPosition` по WASD;
- блокируется только при открытом modal UI или активном text input.

### Mouse wheel zoom и middle-mouse drag

Общий `EventSystem.current.IsPointerOverGameObject()` заменён на:

```text
IsPointerOverInteractiveUi()
```

Метод выполняет UI raycast и блокирует mouse camera input только если курсор находится над `Selectable`, например:

- `Button`;
- `Toggle`;
- `Slider`;
- fullscreen outside-click button открытого context menu.

Пассивные HUD `Image` больше не блокируют wheel zoom и middle-mouse drag.

## 4. Неизменённые части

Не изменялись:

- match-start camera focus algorithm;
- `HumanPlayModeController`;
- camera serialized focus параметры;
- gameplay/ML/runtime;
- `ActionDecoder`;
- `ActionApplier`;
- `MatchManager`;
- `EpisodeController`;
- `MlAgentsTrainingBootstrap`;
- Python/training/checkpoints;
- ONNX/model assets;
- `Week7_MLAgents_StudentVsScriptedBot.unity`;
- сцены.

## 5. Проверки

Выполнено:

- Unity script refresh;
- Unity compilation: `0` errors;
- Unity Console: `0` errors;
- scoped `git diff --check`: чисто;
- статически подтверждено: focus coroutine одноразовый;
- статически подтверждено: WASD не зависит от pointer-over-UI;
- статически подтверждено: wheel zoom и middle drag игнорируют пассивные HUD Images;
- статически подтверждено: pause/settings/context menu блокируют camera input;
- protected runtime diff пуст.

До начала задачи существовал dirty submodule:

- `python/week5_teacher_legacy032/third_party/gym_microrts_legacy032_source`

Он оставлен нетронутым.

## 6. Ручной Game View smoke-pass

Нужна ручная проверка реального input:

1. `MainMenu -> Start -> AI против игрока`.
2. Убедиться, что камера фокусируется над `Player2`.
3. Проверить WASD, wheel zoom и middle-mouse drag.
4. Открыть pause/settings: camera input должен блокироваться.
5. Закрыть pause/settings: camera input должен снова работать.
6. Повторить focus и управление для `AI против бота` и `AI против AI`.
7. Проверить Console на `NullReferenceException`.
