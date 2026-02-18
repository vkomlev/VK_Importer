# План внедрения кастомного формата выгрузки

## Обзор

Кастомный формат выгрузки (TG Parser) описан в [output-formats.md](output-formats.md). Структура:

- Один файл **export.json** в корне каталога экспорта
- Поля: `channel_info`, `messages[]`, `export_date`, `total_messages`
- У каждого сообщения: `id`, `date` (ISO UTC), `text`, `media_files[]`
- У медиа: `type` (photo/video/document), `path` (относительно корня, например `media/videos/...`), `filename`, `size`, `sha256`

Первая выгрузка: курс **«Алгоритмы и структуры данных»** (channel_slug `AlgorithmPythonStruct`), путь к экспорту:
`d:\Work\TG_Parser\out\AlgorithmPythonStruct__2026-02-17_19-32`.

---

## Что уже сделано

1. **Тип курса «Алгоритмы»**
   - В БД и CLI добавлен тип курса `Алгоритмы` (VALID_COURSE_TYPES, команда `folders set`).

2. **Маппинг папки → курс**
   - В таблицу `folder_course_mapping` при инициализации БД добавляется (INSERT OR IGNORE):
     - `d:/Work/TG_Parser/out/AlgorithmPythonStruct` → `Алгоритмы`
   - На другой машине или при другом пути выполнить:
     - `python main.py folders set "ПУТЬ_К_ПАПКЕ_ЭКСПОРТА_ИЛИ_ЕЁ_ПРЕФИКС" "Алгоритмы"`
     - Пример: `python main.py folders set "d:\Work\TG_Parser\out\AlgorithmPythonStruct" "Алгоритмы"`

3. **Парсер кастомного формата**
   - Класс **CustomExportParser** (`src/parsers/custom_export_parser.py`):
     - `detect_format()`: наличие `export.json` с полями `channel_info` и `messages`
     - `parse()`: чтение сообщений, дедупликация по `id`, извлечение видео из `media_files` (type=video, path задан), путь к файлу = корень экспорта + `path`
   - В сканере проверка формата выполняется **до** общего JSON-парсера (чтобы каталоги с `export.json` обрабатывались кастомным парсером).

4. **Сканер и заголовки**
   - Для канала `Алгоритмы` используется тот же генератор заголовков, что и для Python (`python_auto`). При необходимости можно добавить отдельный генератор `algorithms_auto`.

---

## Как использовать

1. **Проверить маппинг**
   ```bash
   python main.py folders list
   ```
   Должна быть строка с путём, содержащим `AlgorithmPythonStruct`, и типом `Алгоритмы`. Если нет — выполнить `folders set` (см. выше).

2. **Сканировать выгрузку**
   ```bash
   python main.py scan --source "d:\Work\TG_Parser\out\AlgorithmPythonStruct__2026-02-17_19-32"
   ```
   Либо передать путь к любому каталогу с `export.json` кастомного формата, для которого в маппинге задан тип курса.

3. **Дальнейшие выгрузки того же канала**
   - При появлении новых каталогов вида `AlgorithmPythonStruct__YYYY-MM-DD_HH-mm` маппинг по префиксу `.../AlgorithmPythonStruct` продолжит работать.
   - Сканировать можно так:
     ```bash
     python main.py scan --source "d:\Work\TG_Parser\out\AlgorithmPythonStruct__НОВАЯ_ДАТА"
     ```

---

## Опциональные доработки

| Задача | Описание |
|--------|----------|
| Источник `algorithms` в `get_export_paths` | В `main.py` добавить ветку `source_filter == "algorithms"`: сканировать все подкаталоги в `d:\Work\TG_Parser\out` (или путь из конфига/переменной окружения), чтобы не указывать путь вручную. |
| Генератор заголовков для Алгоритмы | Создать `algorithms_auto` по аналогии с `python_auto`, если нужен отдельный шаблон заголовков для курса «Алгоритмы и структуры данных». |
| Медиа без `path` | В формате при ошибке загрузки у медиа может быть `path: null`. Такие записи парсер уже пропускает. |
| Дедупликация по `sha256` | При желании можно использовать `media-index.json` (sha256 → path) для учёта дедупликации медиа при сканировании. |

---

## Структура формата (напоминание)

```
{channel_slug}__YYYY-MM-DD_HH-mm/
├── export.json      # channel_info, messages[].media_files
├── state.json
├── media-index.json
├── summary.json
├── logs/
└── media/
    ├── photos/
    ├── videos/      # видео по путям из media_files[].path
    └── documents/
```

Парсер использует только `export.json` и файлы в `media/` по путям из `path`.
