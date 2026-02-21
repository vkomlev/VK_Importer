# Review: Phase 4 — исправления очереди и смоук-тесты

**Дата:** 2026-02-21  
**Контекст:** Замечания по job_queue: атомарность claim_next при нескольких воркерах, возврат актуального JobRecord, использование result в complete(); плюс минимум 3 смоук-теста.

## Исправления

### 1. Атомарность claim_next
- **src/storage/job_queue.py**: выборка и захват задачи выполняются в одной транзакции с `BEGIN IMMEDIATE`: SELECT → UPDATE по id → повторный SELECT по id → COMMIT. Второй воркер блокируется до освобождения и не может выбрать ту же задачу.

### 2. Возврат актуального JobRecord
- После UPDATE возвращается строка, прочитанная заново по id (status=running, attempt уже увеличен), а не результат первого SELECT.

### 3. complete(result=...)
- Добавлена колонка `result_json` (миграция через ALTER TABLE при инициализации). В `complete(job_id, result=...)` при переданном `result` он сохраняется в `result_json`.

### 4. get_job(job_id)
- Добавлен метод для чтения задачи по id (тесты и отладка).

### 5. Документация
- **docs/PHASE4-JOB-QUEUE.md**: уточнено описание атомарности claim_next (BEGIN IMMEDIATE); complete — при наличии result сохраняется в result_json; в схему таблицы добавлена колонка result_json; раздел «Смоук-тесты очереди» с описанием трёх тестов и командой запуска.

### 6. Смоук-тесты
- **scripts/smoke-phase4-job-queue.py**: три теста на временной SQLite-БД:
  1. Конкурентный claim: 2 процесса, 1 pending job — job забирается ровно один раз.
  2. Retry run_after: после fail_retry(..., run_after=now+2s) до времени claim_next возвращает None, после sleep — задачу.
  3. Состояние после fail_retry: status=pending, attempt=1, error и run_after заполнены.

Запуск: `python scripts/smoke-phase4-job-queue.py`. Ожидание: 3/3 passed.

## Diff

Полный diff: [phase4-job-queue-fixes-2026-02-21.diff](phase4-job-queue-fixes-2026-02-21.diff).
