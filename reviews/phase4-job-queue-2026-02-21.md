# Review: Phase 4 — очередь задач (SQLite)

**Дата:** 2026-02-21  
**Контекст:** Аудит Phase 4 — минимальная рабочая очередь внутри монолита: контракт API в коде, таблица jobs в SQLite, воркер CLI, док с миграцией на Redis.

## Изменения

### 1. Модуль очереди
- **src/storage/job_queue.py** (новый): таблица `jobs` (id, type, payload_json, status, attempt, run_after, error, created_at, updated_at); класс `JobQueue` с методами `enqueue()`, `claim_next()`, `complete()`, `fail_retry()`, `fail()`; статусы pending/running/done/failed.
- **src/storage/__init__.py**: экспорт JobQueue, JobRecord, константы статусов.

### 2. CLI воркер
- **main.py**: команда `worker --once | --loop` (опции `--interval`, `--types`); тип задачи `upload_video` (payload `video_id`); обработчик вызывает _upload_video, при partial — fail_retry с run_after +5 мин, при фатале — fail.

### 3. Документация
- **docs/PHASE4-JOB-QUEUE.md**: контракт API, схема таблицы, описание воркера и типа upload_video, правила миграции на Redis (тот же интерфейс, другой backend).
- **docs/AUDIT-ARCHITECTURE-SCALABILITY-2026-02-21.md**: Phase 4 отмечен как реализован, ссылка на док и модуль.

## Начало diff

```diff
diff --git a/src/storage/job_queue.py b/src/storage/job_queue.py
new file mode 100644
...
diff --git a/main.py b/main.py
...
```

## Diff

Полный diff: [phase4-job-queue-2026-02-21.diff](phase4-job-queue-2026-02-21.diff).
