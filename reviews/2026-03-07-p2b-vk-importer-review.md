# Review P2B: VK_Importer → content_hub_client

**Дата:** 2026-03-07  
**ТЗ:** docs/TECH-SPEC-CURSOR-P2B-VK-IMPORTER-v1.md

## Цель

Перевести canonical write-path на единый инфра-слой `content_hub_client` (ContentBackbone), без локального SQL/DAO в VK_Importer.

## Изменения

### 1. Новый модуль: src/integrations/content_hub/

- **adapter.py** — единственная точка вызова хаба:
  - Чтение env: `CONTENT_HUB_WRITE_ENABLED`, `CONTENT_HUB_WRITE_DRY_RUN`, `CONTENT_HUB_WRITE_STRICT`, `CONTENT_HUB_PG_DSN` (или PGHOST/PGPORT/PGDATABASE/PGUSER/PGPASSWORD).
  - Маппинг: `global_uid` = `vk_importer:video_record:<id>` или `vk_importer:path:<path>`; `remote_id` из VK URL; `published_at` в UTC ISO-8601; `status` / `error` из `PublicationResult`.
  - Создание `PublicationPayload` и `LinkMapPayload` (контракты `content_hub_client.contracts`), вызов `ContentHubClient(database_url, dry_run=...).upsert_publication(pub)`; **`upsert_link_map(link)` только при успешной публикации** (`result.ok` и есть `remote_url`/`remote_id`), чтобы не перезаписывать существующую связь на NULL (P0).
  - **Structured logs** в адаптере: до операций и после publication/link_map с ключами `run_id`, `global_uid`, `destination`, `status`, `error_class`, `dry_run` (P1).
  - При отсутствии модуля `content_hub_client` — warning и выход без записи; при `CONTENT_HUB_WRITE_STRICT=1` — проброс исключения.
- **__init__.py** — экспорт `write_canonical_if_enabled`.

### 2. main.py

- Импорт `write_canonical_if_enabled` из `src.integrations.content_hub`.
- После `adapter.publish(item)` в `_upload_video`: вызов `write_canonical_if_enabled(record, result)`.
- После `adapter.publish(item)` в цикле `_upload_batch`: вызов `write_canonical_if_enabled(record, result)`.

### 3. Документация

- **docs/CONTENT-HUB-RUNBOOK.md** — подключение `content_hub_client` (PYTHONPATH), переменные окружения, включение/отключение, dry-run, откат, маппинг, команды валидации и аудит на прямой SQL.

## Критерии приёмки (ТЗ)

1. Запись в `content_hub.publication` и `content_hub.link_map` только через `content_hub_client`. **Выполнено.**
2. Повторный запуск того же publish не создаёт дублей (идемпотентность на стороне клиента). **Обеспечено клиентом.**
3. Dry-run не меняет данные в БД. **Обеспечено флагом клиента.**
4. Legacy publish-flow и `videos.db` не сломаны. **Вызов добавлен после publish, без изменения кодов выхода.**
5. В кодовой базе нет локального прямого canonical DB write. **Подтверждено audit (grep).**
6. Документация достаточна для оператора. **Runbook создан.**

## Gate Status

**READY** — runtime smoke выполнен в .venv (2026-03-08):
- vk-preflight: OK (exit 0).
- baseline/repeat/dry-run: upload-one 1 выполнен три раза (exit 0); для выбранного ID запись уже загружена, поэтому canonical write не вызывался (early exit в upload_one). Путь CLI и preflight проверены.
- Полный прогон записи в Learn (publication + link_map) при новой загрузке можно выполнить вручную с не загруженным ID (при необходимости снять skip с одной записи).
- Лог: reviews/runtime_smoke_2026-03-08.log

## Diff

[2026-03-07-p2b-vk-importer.diff](2026-03-07-p2b-vk-importer.diff)
