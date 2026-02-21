# Phase 3: ContentItem и адаптеры

**Дата:** 2026-02-21  
**Контекст:** Аудит архитектуры (AUDIT-ARCHITECTURE-SCALABILITY-2026-02-21.md), Phase 3 — унифицированная доменная модель и контракты Source/Destination.

## Что сделано

### 1. Модель контента (`src/models/content.py`)

- **ContentItem** — единая сущность публикации: `source`, `external_id`, `text`, `title`, `published_at`, `media[]`, `metadata`. Конвертеры:
  - `from_video_record(...)` — из записи БД (для upload из текущего pipeline).
  - `from_video_data(...)` — из результата парсеров.
  - `to_video_data()` — в VideoData для VK (первое видео из `media`).
- **MediaRef** — тип + path/url для медиа.
- **PublicationResult** — результат публикации: `destination`, `ok`, `remote_url`, `error_code`, `retry_count`.

### 2. Интерфейсы адаптеров (`src/adapters/base.py`)

- **SourceAdapter** — `source_id`, `fetch(**options) -> List[ContentItem]`.
- **DestinationAdapter** — `destination_id`, `publish(item: ContentItem, **options) -> PublicationResult`.

### 3. Реализации

- **VKDestinationAdapter** (`src/adapters/destinations/vk.py`) — обёртка над `VKPublisher`: принимает `ContentItem`, конвертирует в `VideoData`, вызывает `publish()`, возвращает `PublicationResult`. Подключён в `main.py`: загрузка (upload-one, upload-next, upload-range, upload-many, upload-all) идёт через адаптер.
- **YouTubeDestinationAdapter** (`src/adapters/destinations/youtube_stub.py`) — заглушка: `publish()` возвращает `ok=False`, `error_code="NOT_IMPLEMENTED"`.
- **ExportFilesystemSourceAdapter** (`src/adapters/sources/export_fs.py`) — источник «экспорты на диске»: использует `get_export_paths`, те же парсеры (HTML/JSON/Custom) и генераторы заголовков, возвращает `List[ContentItem]`. Опционально принимает `storage` для `get_course_for_folder`.  
  **Статус: prepared, not wired** — команда `scan` в CLI по-прежнему идёт через `VideoScanner` (main.py), а не через `SourceAdapter.fetch()`. Адаптер готов к использованию в будущем pipeline (fetch → normalize → store/publish) или в тестах; подключение в прод-путь scan — отдельный шаг.

### 4. Поведение CLI

- Текущий сценарий не менялся: scan → БД → upload по записям. В upload вместо прямого вызова `VKPublisher.publish(video_data)` используется `VKDestinationAdapter.publish(ContentItem.from_video_record(record))`.
- Добавление нового направления (YouTube, Rutube и т.д.) — реализовать `DestinationAdapter` и при необходимости выбирать адаптер по конфигу/команде.

## Структура файлов

```
src/
  models/
    content.py       # ContentItem, PublicationResult, MediaRef
  adapters/
    base.py          # SourceAdapter, DestinationAdapter (ABC)
    sources/
      export_fs.py   # ExportFilesystemSourceAdapter
    destinations/
      vk.py          # VKDestinationAdapter
      youtube_stub.py # YouTubeDestinationAdapter (stub)
```

## Дальнейшие шаги (при необходимости)

- Выбор destination по конфигу или флагу CLI (например `--destination youtube`).
- Подключение ExportFilesystemSourceAdapter в единый pipeline (например «fetch → normalize → store или publish»).
- Реализация YouTube (или другого) destination поверх API.
