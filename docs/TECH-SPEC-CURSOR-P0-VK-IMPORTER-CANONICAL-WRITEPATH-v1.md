# ТЗ для Cursor-агента (VK_Importer): P0 Canonical Write-Path в Content Hub

Дата: 2026-03-05  
Основание: `D:\Work\ContentBackbone\docs\tech-spec-cursor-p0-vk-importer-v1.md`  
Режим: `publisher-integration`  
Язык реализации: Python (текущий стек `VK_Importer`)

---

## 1. Цель

После успешной публикации в VK добавлять/обновлять canonical-записи в PostgreSQL:

- `content_hub.publication`
- `content_hub.link_map`

Свойства решения:

1. Идемпотентность при ретраях/повторных прогонах.
2. Dry-run режим для нового write-path.
3. Наблюдаемость (structured logs + понятные ошибки DB записи).
4. Без поломки текущего VK publish-потока.

---

## 2. Контекст текущего проекта (важно для Cursor)

1. Публикация идет через `main.py` + `VKDestinationAdapter` (`src/adapters/destinations/vk.py`).
2. Результат публикации уже унифицирован в `PublicationResult` (`src/models/content.py`).
3. Fail-fast по VK 1051 и preflight уже реализованы:
   - `main.py` (`vk-preflight`, `EXIT_VK_CONTEXT=3`)
   - `scripts/run_tg_vk_video_pipeline.ps1` (preflight перед batch publish).
4. Нельзя ломать:
   - существующие коды выхода,
   - preflight/retry логику,
   - текущую запись статуса в SQLite (`videos.db`).

---

## 3. In Scope / Out of Scope

### In Scope

1. Canonical write-path в Postgres для publish-result.
2. Репозиторий/DAO-слой для `content_hub.publication` и `content_hub.link_map`.
3. Идемпотентный upsert.
4. Dry-run для canonical write-path.
5. Structured logs по canonical write.
6. Smoke + repeat-smoke + dry-run проверки.

### Out of Scope

1. Миграции/изменение схемы `content_hub` (схема предполагается уже примененной).
2. Изменения в `TG_Parser`.
3. Рефактор всей CLI-архитектуры.

### No-Touch

1. Не удалять/не обходить `vk-preflight`.
2. Не менять контракт `upload-one`/pipeline exit-codes в сторону несовместимости.
3. Не вставлять SQL напрямую в боевой код без repository-слоя.

---

## 4. Целевой контракт данных

Минимальный mapping publish-result -> canonical:

1. `destination` -> `vk`
2. `remote_url` -> URL опубликованного видео (`https://vk.com/video...`)
3. `status`:
   - `published` при `result.ok=True`
   - `failed` при `result.ok=False`
4. `error`:
   - `error_code` из `PublicationResult.error_code` (если есть)
5. `published_at`:
   - UTC timestamp (при успехе)

Требуется добавить вычисление:

1. `global_uid` (стабильный source key для одного и того же объекта публикации)
2. `remote_id` (парсинг из `remote_url`, если применимо; для VK: `owner_id_video_id`)

Рекомендуемая стратегия `global_uid` (минимально инвазивно):

1. База: `video_record.id` (когда публикуем из БД).
2. Формат: `vk_importer:video_record:<id>`.
3. Если `id` недоступен: fallback `vk_importer:path:<normalized_file_path>`.

---

## 5. Технические требования реализации

## 5.1 Новые модули

Добавить слой интеграции, например:

1. `src/integrations/content_hub/models.py`
2. `src/integrations/content_hub/repository.py`
3. `src/integrations/content_hub/service.py`

Допускается иная структура, но с разделением:

1. Config/connection
2. Repository (upsert API)
3. Service (бизнес-мэппинг из publish-result)

## 5.2 Конфигурация (env)

Добавить безопасные флаги:

1. `CONTENT_HUB_WRITE_ENABLED=0|1`
2. `CONTENT_HUB_WRITE_DRY_RUN=0|1`
3. `CONTENT_HUB_PG_DSN=postgresql://...` (или составные PG-переменные)

Поведение:

1. По умолчанию write-path выключен (`enabled=0`).
2. При `enabled=1` и `dry_run=1` писать только логи, без commit.

## 5.3 Идемпотентность

Для `publication`:

1. Upsert по ключу идемпотентности (по согласованному уникальному ключу схемы).
2. Повторный запуск того же события не создает новую запись.

Для `link_map`:

1. Upsert source->destination связь.
2. Повторный запуск обновляет/подтверждает связь, без дублей.

## 5.4 Классификация DB-ошибок

Минимум 2 класса:

1. Retryable (временные сетевые/lock/connectivity).
2. Non-retryable (schema mismatch, invalid payload, constraint misuse).

В логах обязательно:

1. `run_id`
2. `global_uid`
3. `destination`
4. `status`
5. `error_class`
6. `dry_run`

---

## 6. Точки встраивания в текущий код

Основной write-hook должен вызываться в post-publish участке, где уже есть:

1. `VideoRecord` (или эквивалентный контекст source)
2. `PublicationResult` из `VKDestinationAdapter.publish(...)`

Критично:

1. Нельзя менять бизнес-решение об успехе/провале загрузки в VK.
2. Canonical write-path не должен ломать legacy-путь:
   - при сбое canonical write — лог + контролируемое поведение по флагу (см. ниже).

Режимы обработки сбоя canonical write:

1. `strict=0` (по умолчанию): не валим upload-команду, только warning/error log.
2. `strict=1` (опционально): трактуем как фатальную ошибку шага.

Если `strict` будет добавлен, задокументировать и по умолчанию оставить `0`.

---

## 7. План реализации (для Cursor)

1. Добавить env-конфиг и feature flags для canonical write-path.
2. Добавить repository/DAO слой для `publication` и `link_map`.
3. Добавить сервис мэппинга `VideoRecord + PublicationResult -> canonical payload`.
4. Встроить вызов сервиса в post-publish путь (`upload-one` и batch-ветки через общий участок).
5. Добавить dry-run режим (логирует payload/ключи, не пишет в БД).
6. Добавить smoke script (1 публикация) и repeat-smoke (та же публикация повторно).
7. Добавить dry-run smoke.
8. Обновить docs с краткой инструкцией включения/отката.

---

## 8. Навигационный контракт (статусы выполнения)

1. `VK_S0_CONTEXT` -> изучен контекст текущего publish flow.
2. `VK_S1_ADAPTER_READY` -> добавлен canonical adapter/service слой.
3. `VK_S2_WRITE_PATH_ENABLED` -> write-path подключен за feature flag.
4. `VK_S3_DRY_RUN_OK` -> dry-run подтвержден.
5. `VK_S4_SMOKE_OK` -> 1-й smoke подтвержден.
6. `VK_S5_IDEMPOTENCY_OK` -> repeat-smoke без дублей подтвержден.

---

## 9. Acceptance Criteria

1. При успешной публикации в VK создается/обновляется запись в `content_hub.publication`.
2. Создается/обновляется `content_hub.link_map` для source->VK.
3. Повторный запуск того же publish не создает дублей.
4. Dry-run не изменяет данные в Postgres.
5. Structured logs содержат обязательные ключи.
6. Текущий pipeline (`scan -> eligible -> vk-preflight -> upload-one`) продолжает работать.

---

## 10. Validation / Smoke

Команды проверки после реализации:

1. `python -m py_compile <измененные_модули>`
2. `python main.py vk-preflight`
3. `<команда_smoke_publish_limit_1>` при `CONTENT_HUB_WRITE_ENABLED=1`
4. Повтор пункта 3 (repeat-smoke)
5. Пункт 3 с `CONTENT_HUB_WRITE_DRY_RUN=1`
6. SQL-проверки в Postgres:
   - запись в `publication` создана/обновлена
   - запись в `link_map` создана/обновлена
   - после repeat-smoke дублей нет
   - после dry-run изменений нет

Примечание: использовать реальные команды проекта, без псевдо-плейсхолдеров, в финальном отчете Cursor.

---

## 11. Handoff-артефакты от Cursor

1. Diff по измененным модулям `VK_Importer`.
2. Явный mapping полей в canonical payload.
3. Логи smoke/repeat-smoke/dry-run.
4. Короткий runbook:
   - как включить write-path,
   - как включить dry-run,
   - как откатить (выключить флаг).

---

## 12. Риски и откат

Риски:

1. Дубли в canonical-таблицах.
2. Рассинхрон source->destination link.
3. Ложные фейлы пайплайна из-за недоступности Postgres.

Контроль:

1. Upsert + уникальные ключи.
2. Repeat-smoke на тех же данных.
3. Нестрогий режим (`strict=0`) по умолчанию.

Откат:

1. `CONTENT_HUB_WRITE_ENABLED=0`
2. Возврат к текущему legacy publish без canonical write.

---

## 13. Уточнение по skill

Запрошенный skill `tech-spec-composer` не был доступен в списке skills текущей сессии, поэтому ТЗ составлено вручную в проектном формате с привязкой к фактическому коду репозитория.
