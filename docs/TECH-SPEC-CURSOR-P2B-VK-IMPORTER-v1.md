# ТЗ для Cursor-агента: P2B / VK_Importer -> `content_hub_client` (адаптировано под текущий репозиторий)

Дата: 2026-03-07  
Источник истины: `D:\Work\ContentBackbone\docs\tech-spec-cursor-p2b-vk-importer-v1.md`  
Статус: **актуально, начать работы заново после отката**

---

## 1. Цель

Перевести canonical write-path (`content_hub.publication` + `content_hub.link_map`) в `VK_Importer` на единый инфраструктурный слой `content_hub_client`, без локального дублирования DB-логики и без регрессий legacy publish-flow.

---

## 2. Текущий контекст VK_Importer (после отката)

1. Публикация идет через:
   - `main.py`
   - `src/adapters/destinations/vk.py`
   - `src/models/content.py` (`PublicationResult`)
2. Защитные механизмы уже есть и сохраняются:
   - `main.py vk-preflight`
   - `EXIT_VK_CONTEXT = 3` для fail-fast на 1051
   - preflight в `scripts/run_tg_vk_video_pipeline.ps1`
3. Локальный контур состояния (`videos.db`) остается операционным.
4. Референсный infra-layer находится в `D:\Work\ContentBackbone\content_hub_client\`:
   - `client.py`, `contracts.py`, `errors.py`, `logging.py`, `db.py`.
5. В хаб-документации некоторые пути указываются в проектной нотации; трактовать их относительно корня `D:\Work\ContentBackbone\`.
6. Локальная интеграция в `VK_Importer` после отката стартует заново (без опоры на старые ошибочные правки).

---

## 3. Scope

### In Scope

1. Подключение `content_hub_client` как **единственной точки canonical write**.
2. Встраивание write-path в post-publish этап (`upload-one`/batch через общий publish путь).
3. Доменный mapping `PublicationResult` -> payload клиента.
4. Dry-run режим через контракт/флаги `content_hub_client`.
5. Обновление проектной документации и runbook.
6. Подготовка review/validation артефактов.

### Out of Scope

1. Изменение схемы `content_hub`.
2. Изменения в `TG_Parser`, `ParseCourse`, `QSMImport`.
3. Развитие `P1+` задач.
4. Реализация локального SQL/DAO write слоя в `VK_Importer`.

---

## 4. Жесткие ограничения

1. Никаких прямых SQL `INSERT/UPDATE/DELETE` в `content_hub` внутри `VK_Importer`.
2. Никаких новых `psycopg2.connect(...)` для canonical write в `VK_Importer`.
3. Не трогать `public.alembic_version`.
4. Все канонические даты — UTC.
5. Не ломать внешний контракт CLI/пайплайна.

---

## 5. Архитектурные правила

1. `content_hub_client` — единый infra-layer для:
   - upsert,
   - idempotency,
   - dry-run,
   - error classification,
   - structured logging.
2. В `VK_Importer` допускается только доменный адаптер/обертка вызовов клиента.
3. Любая попытка добавить локальный canonical repository/DAO считается нарушением ТЗ.

---

## 6. План реализации (пошагово)

1. Инвентаризация точек интеграции:
   - где формируется `PublicationResult`,
   - где post-publish точка в `main.py`,
   - где удобнее встраивать вызов клиента без изменения бизнес-результата публикации.

2. Подключение зависимости `content_hub_client`:
   - согласованный способ (`PYTHONPATH` / editable install / dependency pin),
   - источник модулей: `D:\Work\ContentBackbone\content_hub_client\`,
   - документировать в runbook.

3. Реализовать доменный адаптер вызова infra-layer:
   - map в `PublicationPayload`: `global_uid`, `destination`, `remote_id`, `remote_url`, `status`, `error`, `published_at`;
   - map в `LinkMapPayload`: `source_global_uid`, `destination`, `remote_id`, `remote_url`.

4. Встроить вызов клиента в post-publish:
   - baseline,
   - repeat scenario,
   - dry-run (`CONTENT_HUB_WRITE_DRY_RUN=1`).

5. Проверить и зафиксировать отсутствие локального canonical write слоя:
   - никаких прямых canonical SQL,
   - никаких локальных canonical DAO модулей.

6. Обновить документацию:
   - создать/обновить `docs/CONTENT-HUB-RUNBOOK.md`,
   - описать включение/отключение write-path, dry-run, диагностику.

---

## 7. Acceptance Criteria

1. Запись в `content_hub.publication` и `content_hub.link_map` выполняется только через `content_hub_client`.
2. Повторный запуск того же publish сценария не создает дублей.
3. Dry-run не меняет данные в БД.
4. Legacy publish-flow и `videos.db` не сломаны.
5. В кодовой базе нет локального прямого canonical DB write слоя.
6. Документация достаточна для оператора без контекста хаба.

---

## 8. Validation Commands

Выполнять из корня `VK_Importer`:

1. `python -m py_compile main.py src/adapters/destinations/vk.py src/models/content.py`
2. `python main.py vk-preflight`
3. `CONTENT_HUB_WRITE_ENABLED=1 python main.py upload-one <REAL_ID>`
4. Повтор шага 3 с тем же `<REAL_ID>`
5. `CONTENT_HUB_WRITE_ENABLED=1 CONTENT_HUB_WRITE_DRY_RUN=1 python main.py upload-one <REAL_ID>`
6. `rg -n "INSERT INTO content_hub|UPDATE content_hub|DELETE FROM content_hub|psycopg2.connect\\(" src`
7. `git diff --name-only`

Ожидаемо:

1. baseline/repeat/dry-run проходят по контракту;
2. дублей нет;
3. прямого canonical write в коде нет;
4. изменения ограничены `VK_Importer`.

---

## 9. Обязательные review-артефакты

1. `reviews/2026-03-07-p2b-vk-importer-audit.md`
2. `reviews/2026-03-07-p2b-vk-importer-review.md`
3. `reviews/validation_p2b_vk_importer_2026-03-07.log`
4. `reviews/smoke_p2b_vk_importer_2026-03-07.log`
5. `reviews/rollback_p2b_vk_importer_2026-03-07.md`
6. `reviews/2026-03-07-p2b-vk-importer.diff`

---

## 10. Формат итогового отчета исполнителя

1. `Agent Selected`
2. `Stage Map`
3. `Contract Changes`
4. `Что удалено/деактивировано из локального canonical write-path`
5. `Validation Checklist`
6. `Validation Evidence`
7. `Review Gate Artifacts`
8. `Gate Status`
9. `Risks / Follow-ups`

---

## 11. Риски и откат

Риски:

1. Частичная миграция (часть вызовов останется вне `content_hub_client`).
2. Регресс publish-flow при встраивании write-path.
3. Рассинхрон документации и реализации.

Контроль:

1. grep-аудит на прямой canonical write,
2. baseline/repeat/dry-run с raw evidence,
3. review-gate без пропусков.

Откат:

1. `git revert <commit>`
2. `CONTENT_HUB_WRITE_ENABLED=0`
3. smoke-проверка publish-flow после отката.

---

## 12. Supersedes

Для новых работ использовать этот документ вместо ранних локальных ТЗ по canonical write-path.
