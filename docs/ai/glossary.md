# Глоссарий

Доменные термины проекта VK_Importer.

## content_hub_client

Пакет из репозитория **ContentBackbone** — единственный разрешённый способ записи результата публикации в общую (canonical) БД `content_hub`. VK_Importer не имеет собственного DAO/repository и не выполняет прямой SQL к `content_hub.publication`/`content_hub.link_map` — только вызовы этого клиента (idempotent upsert, dry-run, structured logging). Устанавливается через `requirements.local.txt` (editable install на `D:\Work\ContentBackbone`) или добавлением корня ContentBackbone в `PYTHONPATH`. См. `src/integrations/content_hub/adapter.py`, `docs/CONTENT-HUB-RUNBOOK.md`.

## Canonical writepath (канонический путь записи)

Архитектурное правило: результат публикации (`PublicationResult`) должен попадать в общее хранилище `content_hub` только одним путём — через `content_hub_client`, без локальных обходных путей записи. Введено тех. заданием `docs/TECH-SPEC-CURSOR-P0-VK-IMPORTER-CANONICAL-WRITEPATH-v1.md` взамен более раннего (архитектурно ошибочного) подхода с локальной DB-инфраструктурой внутри VK_Importer.

## Job queue (очередь задач)

Минимальная очередь заданий на SQLite (`src/storage/job_queue.py`, класс `JobQueue`), таблица `jobs` в той же БД, что и видео (`videos.db`). Задачи (`job_type`, например `upload_video`) ставятся через `enqueue`, атомарно забираются воркером через `claim_next` (транзакция `BEGIN IMMEDIATE`), завершаются `complete`/`fail_retry`/`fail`. Запускается CLI-командой `python main.py worker`. См. `docs/PHASE4-JOB-QUEUE.md`.

## Adapters (адаптеры Source/Destination)

Унифицированный слой интеграции по образцу source/destination (`src/adapters/base.py`):
- **SourceAdapter** — источник контента (`fetch() -> List[ContentItem]`). Реализация: `ExportFilesystemSourceAdapter` (экспорты на диске) — подготовлена, но ещё не подключена к прод-пути `scan` (статус `prepared, not wired`).
- **DestinationAdapter** — приёмник публикации (`publish(item) -> PublicationResult`). Реализация: `VKDestinationAdapter` (обёртка над `VKPublisher`, подключена в `main.py` для всех команд upload-*), `YouTubeDestinationAdapter` — заглушка (`error_code=NOT_IMPLEMENTED`).

Цель — дать возможность добавлять новые источники/направления публикации без изменения основного пайплайна. См. `docs/PHASE3-ADAPTERS.md`.

## ContentItem

Единая доменная модель публикуемой единицы контента (`src/models/content.py`): `source`, `external_id`, `text`, `title`, `published_at`, `media[]`, `metadata`. Конвертируется из записи БД (`from_video_record`) или из результата парсеров (`from_video_data`) и обратно в `VideoData` для VK (`to_video_data`).

## Folder-mapping (маппинг папка → курс)

Соответствие пути к папке с экспортом Telegram и курсом (ЕГЭ, ОГЭ, Python, Excel, Алгоритмы, Комлев, Аналитика данных). Хранится только в БД, управляется CLI-командами `folders list` / `folders set <путь> <курс>` / `folders remove <путь>` — без изменения кода. Используется командой `scan -s mapped` для пересканирования всех известных папок и генераторами заголовков для выбора правил именования (`docs/title-rules.md`).

## VK API 1051 / preflight

Код ошибки VK API «метод недоступен для данного типа профиля/токена» — возникает при попытке вызвать `video.save`/`video.get` с токеном без прав `video` в контексте группы. Обрабатывается fail-fast: `main.py vk-preflight` проверяет доступ до батч-загрузки; при 1051 в цикле `upload-one` команда завершается с exit-кодом `3` (`EXIT_VK_CONTEXT`), не перебирая остальные ID. См. `docs/troubleshooting.md`, `docs/EXIT-CODES-AND-SUMMARY-SPEC.md`.
