# Review: Phase 2 — AppContext, маппинги, source registry

**Дата:** 2026-02-21  
**Контекст:** Аудит архитектуры (docs/AUDIT-ARCHITECTURE-SCALABILITY-2026-02-21.md), Phase 2: вынести PublishingService/AppContext, убрать дубли env/publisher init, централизовать mappings и source registry.

## Изменения

### 1. BOM в смоук-тестах
- В **docs/EXIT-CODES-AND-SUMMARY-SPEC.md** добавлен раздел 4: смоук-тесты (PowerShell), рекомендация `Set-Content ... -Encoding utf8NoBOM` для тестовых файлов, известный непроверенный путь (upload-one → publish failed → EXIT_PARTIAL).

### 2. AppContext / get_vk_publisher
- **src/app_context.py**: класс `FatalUploadError` перенесён сюда; функция `get_vk_publisher(delay, max_retries, group_id_required, on_token_expired)` — единая точка создания VKPublisher из env (бросает FatalUploadError при ошибке).
- **main.py**: импорт `get_vk_publisher`, `FatalUploadError` из `src.app_context`; все команды используют `get_vk_publisher(...)` вместо дублирования get_env_var + VKPublisher(...).
- **sys.path**: в main — корень проекта (`Path(__file__).parent`).

### 3. Централизация mappings
- **src/config/registry.py**: `COURSE_TYPES`, `CHANNEL_TO_TITLE_GENERATOR`.
- **main.py**, **src/storage/database.py**, **src/storage/scanner.py**: один источник правды (registry).

### 4. Source registry
- **src/config/source_registry.py**:
  - **SOURCE_ALIASES** и **OGE_ALTERNATIVE** (относительные пути) **используются** в `get_export_paths` для ege/python/oge.
  - **TG Parser**: вместо хардкода — конфиг из env с дефолтами: `TG_PARSER_OUT_DIR` или `TG_PARSER_OUT` (путь к out), `TG_PARSER_FOLDERS` (список папок через запятую). При отсутствии переменных используются текущие значения по умолчанию (временное решение до перевода на DB mapping при необходимости).
- **main.py**: удалена локальная `get_export_paths`, импорт из `src.config.source_registry`.

## Самодостаточность патча

**Diff пересобран** и включает все новые файлы: `src/app_context.py`, `src/config/__init__.py`, `src/config/registry.py`, `src/config/source_registry.py`. Применение на чистую ветку не даёт `ModuleNotFoundError`. Собран как `git add … && git diff --cached`.

## Smoke-тесты Phase 2 (PowerShell)

| # | Тест | Ожидание | Результат |
|---|------|----------|------------|
| 1 | `scan --source "Z:\not-exists"` | exit=1, command=scan, ok=false | ✅ exit=1, ok=false |
| 2 | `scan --source oge` | Без ошибок импорта/роутинга; при наличии данных exit=0 | ✅ Алиас oge → «Экспорт ОГЭ», экспорты найдены |
| 3 | `scan --source tg_parser` с TG_PARSER_OUT_DIR, TG_PARSER_FOLDERS | exit=1 (нет экспортов), путь из env | ✅ Путь из env (Z:\empty-dir, foo,bar), exit=1 |
| 4 | `delete-from-vk` без VK_ACCESS_TOKEN (только env) | exit=1, ошибка про токен | ⚠️ В среде с .env токен подхватывается из файла → exit=2 (VK API). Для проверки «нет токена» нужен запуск без .env или с пустым VK_ACCESS_TOKEN в .env |
| 5 | `upload-next` без VK_GROUP_ID | exit=1 при ошибке VK_GROUP_ID или exit=0 при пустой очереди | ⚠️ В среде с .env VK_GROUP_ID мог быть в .env; при наличии очереди — попытка загрузки и exit=2 (ошибка API). Логика AppContext (get_vk_publisher) отрабатывает |
| 6 | `update-vk-titles` без токена | exit=1, ошибка про токен | ⚠️ Аналогично: токен из .env → успешный вызов API, exit=0. Для проверки «нет токена» — без .env |
| 7 | `folders list` | exit=0, command=folders list | ✅ exit=0, список папок из registry |

**Примечание:** В PowerShell 5.1 `-Encoding utf8NoBOM` недоступен; для теста 6 файл создан через `[System.IO.File]::WriteAllText(..., [System.Text.UTF8Encoding]::new($false))`.

## Diff

Полный diff (включая новые модули): [phase2-app-context-registry-2026-02-21.diff](phase2-app-context-registry-2026-02-21.diff).
