# Review: Phase 3 — ContentItem и адаптеры

**Дата:** 2026-02-21  
**Контекст:** Аудит архитектуры (docs/AUDIT-ARCHITECTURE-SCALABILITY-2026-02-21.md), Phase 3: ввести ContentItem и adapters interface, переиспользовать TG parser + VK publisher как первые адаптеры, skeleton для YouTube.

## Изменения

### 1. Модель контента
- **src/models/content.py** (новый): `ContentItem`, `MediaRef`, `PublicationResult`; конвертеры `from_video_record`, `from_video_data`, `to_video_data`.
- **src/models/__init__.py**: экспорт ContentItem, PublicationResult, MediaRef.

### 2. Интерфейсы и реализации адаптеров
- **src/adapters/base.py** (новый): `SourceAdapter` (source_id, fetch), `DestinationAdapter` (destination_id, publish).
- **src/adapters/destinations/vk.py** (новый): `VKDestinationAdapter` — обёртка над VKPublisher, publish(ContentItem) → PublicationResult.
- **src/adapters/destinations/youtube_stub.py** (новый): заглушка YouTube, error_code=NOT_IMPLEMENTED.
- **src/adapters/sources/export_fs.py** (новый): `ExportFilesystemSourceAdapter` — get_export_paths + парсеры, fetch() → List[ContentItem].

### 3. Подключение в CLI
- **main.py**: импорт ContentItem, VKDestinationAdapter; в `_upload_video` и `_upload_batch` загрузка идёт через VKDestinationAdapter.publish(ContentItem.from_video_record(record)); post_url при успехе не сохраняется (остаётся None).
- **upload-one partial/fatal:** коды ошибок адаптера (`PUBLISH_FAILED`, `NO_VIDEO`) и legacy `UPLOAD_ERROR_PUBLISH_FAILED` объединены в `PARTIAL_UPLOAD_ERROR_CODES`; при ошибке публикации одного элемента exit = EXIT_PARTIAL (Phase 1 политика сохранена).

### 3.1 Source adapter: prepared, not wired
- **ExportFilesystemSourceAdapter** реализован и готов к использованию, но **прод-путь `scan` его не использует** — `scan` по-прежнему вызывается через `VideoScanner` (main.py). Подключение в pipeline (fetch → store или fetch → publish) — отдельная задача.

### 4. Документация
- **docs/AUDIT-ARCHITECTURE-SCALABILITY-2026-02-21.md**: Phase 3 отмечен как реализован, добавлена ссылка на модули и PHASE3-ADAPTERS.md.
- **docs/PHASE3-ADAPTERS.md** (новый): описание модели, адаптеров, структуры файлов и дальнейших шагов.

## Начало diff (полный патч в .diff)

```diff
diff --git a/docs/AUDIT-ARCHITECTURE-SCALABILITY-2026-02-21.md b/docs/AUDIT-ARCHITECTURE-SCALABILITY-2026-02-21.md
...
diff --git a/docs/PHASE3-ADAPTERS.md b/docs/PHASE3-ADAPTERS.md
new file mode 100644
...
diff --git a/main.py b/main.py
...
diff --git a/src/models/content.py b/src/models/content.py
new file mode 100644
...
diff --git a/src/adapters/... b/src/adapters/...
```

## Diff

Полный diff (включая новые файлы): [phase3-contentitem-adapters-2026-02-21.diff](phase3-contentitem-adapters-2026-02-21.diff).
