# Onboarding Checklist: Cursor / P2B / VK_Importer

Дата: 2026-03-07  
Назначение: быстрый старт разработчика перед реализацией P2B.

---

## 0. Главный документ (обязательно)

1. Основное ТЗ для разработки: `docs/TECH-SPEC-CURSOR-P2B-VK-IMPORTER-v1.md`
2. Внешний source-of-truth: `D:\Work\ContentBackbone\docs\tech-spec-cursor-p2b-vk-importer-v1.md`

---

## 1. Базовый контекст VK_Importer

1. Открыть `main.py`:
   - команды `upload-one`, `vk-preflight`,
   - текущие exit-коды и post-publish точки.
2. Открыть `src/adapters/destinations/vk.py`:
   - как формируется `PublicationResult`.
3. Открыть `src/models/content.py`:
   - `PublicationResult` и связанные поля.
4. Открыть `scripts/run_tg_vk_video_pipeline.ps1`:
   - preflight этап,
   - batch вызовы `upload-one`.

---

## 2. Контекст хаба (ContentBackbone)

Все относительные пути из хаб-документов трактовать от: `D:\Work\ContentBackbone\`.

1. Открыть `D:\Work\ContentBackbone\docs\change-plan-hub-orchestration-v1.md`
2. Открыть `D:\Work\ContentBackbone\docs\infra-layer-content-hub-client-v1.md`
3. Открыть `D:\Work\ContentBackbone\docs\contract-notes-p0-db-v1.md`
4. Открыть `D:\Work\ContentBackbone\docs\tech-spec-cursor-p2-canonical-storage-enable-v1.md`
5. Открыть `D:\Work\ContentBackbone\content_hub_client\client.py`
6. Открыть `D:\Work\ContentBackbone\content_hub_client\contracts.py`
7. Открыть `D:\Work\ContentBackbone\content_hub_client\errors.py`
8. Открыть `D:\Work\ContentBackbone\content_hub_client\logging.py`
9. Открыть `D:\Work\ContentBackbone\content_hub_client\db.py`

---

## 3. Инварианты перед кодом

1. Canonical write только через `content_hub_client`.
2. Прямой SQL в `content_hub` из `VK_Importer` запрещен.
3. Локальный DAO/repository слой для canonical write запрещен.
4. Legacy publish-flow + `videos.db` не ломать.
5. Все canonical timestamps — UTC.

---

## 4. Что проверить в рабочем дереве до старта

1. После отката нет старого локального canonical write-path.
2. Папка `src/integrations/content_hub/` не используется для прямых DB writes.
3. Поняты точки встраивания post-publish без изменения внешнего CLI-контракта.

Команда быстрых проверок:

```powershell
rg -n "INSERT INTO content_hub|UPDATE content_hub|DELETE FROM content_hub|psycopg2.connect\(" src
```

---

## 5. Порядок реализации (кратко)

1. Подключить `content_hub_client` зависимость.
2. Сделать доменный mapping `PublicationResult -> payload infra-layer`.
3. Встроить вызов в post-publish шаг.
4. Поддержать dry-run (`CONTENT_HUB_WRITE_DRY_RUN=1`).
5. Обновить runbook/документацию.
6. Собрать validation + review артефакты.

---

## 6. Validation минимум

```powershell
python -m py_compile main.py src/adapters/destinations/vk.py src/models/content.py
python main.py vk-preflight
CONTENT_HUB_WRITE_ENABLED=1 python main.py upload-one <REAL_ID>
CONTENT_HUB_WRITE_ENABLED=1 python main.py upload-one <REAL_ID>
CONTENT_HUB_WRITE_ENABLED=1 CONTENT_HUB_WRITE_DRY_RUN=1 python main.py upload-one <REAL_ID>
rg -n "INSERT INTO content_hub|UPDATE content_hub|DELETE FROM content_hub|psycopg2.connect\(" src
git diff --name-only
```

---

## 7. Артефакты к review gate

1. `reviews/2026-03-07-p2b-vk-importer-audit.md`
2. `reviews/2026-03-07-p2b-vk-importer-review.md`
3. `reviews/validation_p2b_vk_importer_2026-03-07.log`
4. `reviews/smoke_p2b_vk_importer_2026-03-07.log`
5. `reviews/rollback_p2b_vk_importer_2026-03-07.md`
6. `reviews/2026-03-07-p2b-vk-importer.diff`

---

## 8. Definition of Ready

Можно начинать кодинг, если:

1. Прочитано основное ТЗ: `docs/TECH-SPEC-CURSOR-P2B-VK-IMPORTER-v1.md`
2. Прочитан infra-layer контракт `content_hub_client`.
3. Подтверждено отсутствие локального прямого canonical write-path.
4. Согласован способ подключения `content_hub_client` в окружении разработки.
