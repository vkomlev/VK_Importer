# ТЗ для Cursor-агента (VK_Importer): P0 через общий infra-layer

Дата: 2026-03-06  
Основание (источник истины): `D:\Work\ContentBackbone\docs\tech-spec-cursor-p0-vk-importer-v1.md`

---

## 1. Objective

В `VK_Importer` подключить запись publish-result в canonical storage (`content_hub.publication` + `content_hub.link_map`) **только через общий infra-layer** (`content_hub_client`) с поддержкой:

1. идемпотентности,
2. dry-run,
3. наблюдаемости.

---

## 2. Ключевое изменение относительно предыдущего ТЗ

Предыдущее ТЗ считается архитектурно ошибочным в части локальной DB-инфраструктуры внутри `VK_Importer`.

Новый обязательный принцип:

1. Никакого локального DAO/repository для canonical DB write в `VK_Importer`.
2. Никаких прямых SQL-вставок в `publication/link_map`.
3. Только вызовы общего `infra-layer` из `ContentBackbone`.

---

## 3. Context

1. Текущий publish-путь в проекте:
   - `main.py`
   - `src/adapters/destinations/vk.py`
   - `src/models/content.py` (`PublicationResult`)
2. Preflight/fail-fast уже есть и не подлежит удалению:
   - `main.py vk-preflight`
   - `EXIT_VK_CONTEXT=3`
   - preflight-шаг в `scripts/run_tg_vk_video_pipeline.ps1`
3. DB schema `content_hub` должна быть уже применена по DB-ТЗ внешнего проекта.
4. Общий `infra-layer` (`content_hub_client`) должен быть доступен как зависимость.

---

## 4. Domain Mode

`publisher-integration`

---

## 5. Scope

### In Scope

1. Маппинг результата публикации в unified publish-result:
   - `destination`, `remote_id`, `remote_url`, `published_at`, `status`, `error`.
2. Вызов общего `infra-layer` для записи в `publication` и `link_map`.
3. Корректное использование контрактов `infra-layer`:
   - idempotent behavior,
   - dry-run,
   - logging contract.
4. Structured logs доменного уровня:
   - `run_id`, `global_uid`, `destination`, `status`, `error_class`.

### Out of Scope

1. Изменения в `TG_Parser`.
2. Создание/изменение DB-схемы.
3. `P1+` задачи.
4. Реализация нового repository/DAO внутри `VK_Importer`.
5. Локальная реализация upsert/retry/dry-run инфраструктуры в обход `infra-layer`.

### No-Touch

1. Не ломать текущий publish flow в VK.
2. Не убирать preflight/retry механизмы.
3. Не менять рабочие exit-code контракты без необходимости.

---

## 6. Stack and Constraints

1. Python + текущий стек `VK_Importer`.
2. PostgreSQL `content_hub` только через `content_hub_client`.
3. Без прямого SQL и без локального DB write слоя для canonical.
4. `published_at` в UTC.

---

## 7. Required Rules

1. Сначала подключение `infra-layer`, затем доменный mapping.
2. Классификация DB-ошибок делается в `infra-layer`; в `VK_Importer` только корректная обработка статусов/исключений клиента.
3. Повторный запуск того же publish-события не создает дубликаты (подтверждается контрактом `infra-layer`).
4. Любая попытка добавить локальный DAO/client для `content_hub` — нарушение ТЗ.

---

## 8. Implementation Steps (для Cursor)

1. Подключить зависимость `content_hub_client` в `VK_Importer`.
2. Реализовать доменный mapping `PublicationResult` + контекст записи -> payload вызова `infra-layer`.
3. Подключить вызов `infra-layer` в post-publish шаг (без изменения бизнес-логики публикации в VK).
4. Поддержать dry-run режим через контракт/флаг `infra-layer`.
5. Добавить smoke script на 1 публикацию.
6. Добавить repeat-smoke script (повтор того же publish).
7. Добавить проверку, что в кодовой базе не появился локальный canonical DAO/repository.

---

## 9. Navigation Contract

1. `VK_S0_CONTEXT` -> `VK_S1_ADAPTER_READY`
2. `VK_S1_ADAPTER_READY` -> `VK_S2_WRITE_PATH_ENABLED`
3. `VK_S2_WRITE_PATH_ENABLED` -> `VK_S3_DRY_RUN_OK`
4. `VK_S3_DRY_RUN_OK` -> `VK_S4_SMOKE_OK`
5. `VK_S4_SMOKE_OK` -> `VK_S5_IDEMPOTENCY_OK`

---

## 10. Forbidden Controls

1. Прямой INSERT/UPDATE в `publication`/`link_map` в обход `infra-layer`.
2. Отключение dedup-проверок ради "быстрого фикса".
3. Merge без smoke + repeat-smoke доказательства.
4. Добавление дублирующего локального DB client/DAO для `content_hub` в `VK_Importer`.

---

## 11. Acceptance Criteria

1. После успешного publish через `infra-layer` создается/обновляется запись `publication`.
2. Для опубликованного объекта через `infra-layer` создается/обновляется `link_map`.
3. Повторный запуск не создает дублей.
4. Dry-run не пишет в БД.
5. Логи содержат обязательные ключи (`run_id`, `global_uid`, `destination`, `status`, `error_class`).
6. Legacy publish-путь в VK продолжает работать.
7. В проекте отсутствует локальный canonical DAO/repository слой.

---

## 12. Validation Commands

1. `python -m py_compile <vk_importer_changed_modules>`
2. `<vk_importer_command> --smoke --limit 1`
3. `<vk_importer_command> --smoke --limit 1` (повтор)
4. `<vk_importer_command> --smoke --limit 1 --dry-run`
5. `<db_query_check_publication_and_link_map>`
6. `<code_search_command_forbidden_local_dao>`

Expected:

1. 1-й smoke создает/обновляет записи.
2. 2-й smoke не создает дублей.
3. dry-run не меняет состояние БД.
4. В кодовой базе `VK_Importer` нет локального canonical DB write слоя.

---

## 13. Handoff Artifacts

1. Diff по модулям `VK_Importer`.
2. Mapping publish-result -> API `infra-layer` -> `publication/link_map`.
3. Логи smoke/repeat-smoke/dry-run.
4. Короткая инструкция включения/отката write-path.
5. Подтверждение отсутствия локального DAO/repository дублирования.

---

## 14. Risks and Rollback

1. Риск дублей или рассинхрона link_map.
2. Риск drift между проектами при обходе `infra-layer`.
3. Контроль: единый `infra-layer` + repeat-smoke + code search на запрет локального DAO.
4. Rollback: выключить feature flag write-path, вернуть legacy publish-режим, зафиксировать incident.

---

## 15. Примечание по skills

Запрошенный skill `tech-spec-composer` не был доступен в списке skills текущей сессии, поэтому ТЗ обновлено вручную по внешнему документу-источнику истины.
