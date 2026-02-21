# Review: Phase 4 — миграция: не гасить лишние OperationalError

**Дата:** 2026-02-21  
**Контекст:** Улучшение миграции добавления колонки `result_json`: не скрывать реальные ошибки БД/окружения.

## Изменение

- **src/storage/job_queue.py**: при `ALTER TABLE jobs ADD COLUMN result_json TEXT` перехватывать только `OperationalError` с текстом "duplicate column" (колонка уже есть); остальные `OperationalError` пробрасывать дальше.

## Diff

[phase4-migration-operational-error-2026-02-21.diff](phase4-migration-operational-error-2026-02-21.diff)
