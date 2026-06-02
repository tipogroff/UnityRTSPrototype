# Settings Layout Position Fix Report

Дата: 2026-06-02
Ветка: `cleanup/safe-audit-only`

## 1. Проблема

После компактной перестройки Main Menu Settings блок `SettingsContent` оставался расположен слишком высоко внутри `SettingsPanel`.

Параметры до исправления:

- `SettingsPanel`: `700 x 560`;
- `SettingsContent`: `610 x 282`;
- anchored position `SettingsContent`: `(0, -104)`.

Так как anchor находится сверху панели, верхняя граница content-блока вычислялась как:

```text
-104 + 282 / 2 = +37
```

То есть верхняя часть `SettingsContent` выходила на `37 px` выше верхней границы коричневого фона. Из-за этого верхние labels и value-кнопки визуально выезжали за пределы `SettingsPanel`.

## 2. Изменённые файлы

- `Assets/Scripts/Presentation/UI/MainMenuController.cs`
- `SETTINGS_LAYOUT_POSITION_FIX_REPORT.md`

## 3. Исправление

В `MainMenuController.BuildSettingsPanel()` изменена только вертикальная позиция `SettingsContent`.

Первый сдвиг:

```text
(0, -104) -> (0, -164)
```

После дополнительной визуальной проверки выполнен ещё один сдвиг:

```text
(0, -164) -> (0, -214)
```

После проверки скриншота выполнен финальный небольшой сдвиг:

```text
(0, -214) -> (0, -229)
```

Итоговый сдвиг всего блока из шести строк вниз: `125 px`.

Структура меню, строки настроек, value-кнопки, status, footer и поведение callbacks не изменялись.

## 4. Геометрия после исправления

После сдвига `SettingsContent` занимает вертикальный диапазон:

```text
top:    -229 + 282 / 2 = -88
bottom: -229 - 282 / 2 = -370
```

Обе границы находятся внутри `SettingsPanel` высотой `560`.

Строки внутри content-блока сохраняют фиксированную высоту `42` и позиции:

- `Сетка`: `21`
- `Маркеры юнитов`: `69`
- `Подсказки управления`: `117`
- `Качество графики`: `165`
- `Высота камеры`: `213`
- `Масштаб интерфейса`: `261`

Первая строка начинается у верхней границы content-блока, последняя заканчивается у нижней. Value-кнопки остаются строго напротив labels, потому что перемещён общий родительский `SettingsContent`.

Header не изменялся и остаётся сверху.

Status и footer также не изменялись:

- status center: `-410`, height: `30`;
- footer center: `-474`, height: `52`;
- footer range: `-448..-500`.

Footer остаётся внутри нижней границы панели `-560`.

Между нижней границей списка `-370` и верхней границей status `-395` сохраняется зазор `25 px`.

## 5. Горизонтальное разделение labels и value-кнопок

По скриншоту после вертикального сдвига выявлено перекрытие длинных labels и value-кнопок.

Причина: в `CreateSettingsRow()` у `HorizontalLayoutGroup` было отключено `childControlWidth`. Из-за этого preferred width label не резервировалась layout-группой, а текст с `HorizontalWrapMode.Overflow` заходил под value-кнопку.

Исправление:

```text
spacing:            24 -> 30
childControlWidth:  false -> true
childControlHeight: false -> true
```

Геометрия строки после исправления:

```text
label:        390 px
spacing:       30 px
value button: 190 px
total:        610 px
```

Суммарная ширина точно совпадает с шириной строки. Value-кнопка отодвинута вправо и больше не перекрывает подпись.

## 6. Ограничения

Не изменялись:

- структура меню;
- `DemoVisualSettings`;
- режимы запуска;
- `SceneFlowController`;
- `HumanPlayModeController`;
- gameplay/ML/runtime;
- Canvas-архитектура;
- сцены;
- Python/training/checkpoint.

## 7. Проверки

Выполнено:

- Unity script refresh;
- Unity compilation: `0` errors;
- Unity Console: `0` errors;
- статический расчёт границ `SettingsContent`, строк, status и footer;
- проверка scoped diff.

Не выполнялось автоматически:

- пользовательский клик `Settings` в Game View.

Доступный Unity MCP не предоставляет безопасный API для вызова runtime-built `Button.onClick` как пользовательского клика. Для окончательной визуальной проверки нужен ручной Game View smoke-pass:

1. Открыть `Assets/Scenes/MainMenu.unity`.
2. Нажать Play.
3. Нажать `Settings`.
4. Убедиться, что все 6 строк и value-кнопки находятся внутри коричневого фона.
5. Убедиться, что `Применить` и `Назад` остаются видимыми.
