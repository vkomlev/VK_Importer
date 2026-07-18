# Project Memory

Project: VK_Importer
Path: `d:\Work\VK_Importer`
Created: 2026-05-26

## Purpose

- What this project is responsible for: превращать экспорты Telegram Desktop (HTML/JSON) в опубликованные видео VK Video — парсинг экспортов, сопоставление видео с сообщениями, генерация заголовков по правилам курса, загрузка через VK API, учёт статусов в SQLite (`videos.db`), очередь фоновых задач (`JobQueue`), запись результата публикации в canonical storage `content_hub` (только через `content_hub_client` из ContentBackbone).
- What it is not responsible for: сам экспорт из Telegram (это `TG_Parser`), схему/владение БД `content_hub` (ContentBackbone), генерацию/методику курсового контента, публикацию на других площадках кроме VK (YouTube — только заглушка `youtube_stub.py`).

## Durable Context

- Product/domain facts that should survive across sessions:
  - Маппинг «папка экспорта → курс» хранится только в БД (`folders` CLI), не в коде; курсы: ЕГЭ, ОГЭ, Python, Excel, Алгоритмы, Комлев, Аналитика данных.
  - Правила заголовков — `docs/title-rules.md`: ЕГЭ/ОГЭ/Алгоритмы — тема/задание + первые 2 предложения; Python/Excel/Аналитика/Комлев — префикс курса + первая строка описания.
  - Между загрузками действует пауза по умолчанию 15 сек (лимиты и антибот-политика VK API).
- Important integration partners and contracts:
  - **ContentBackbone** — источник `content_hub_client` (canonical write в `content_hub.publication`/`link_map`); контракт зафиксирован в `docs/TECH-SPEC-CURSOR-P0-VK-IMPORTER-CANONICAL-WRITEPATH-v1.md` и `docs/CONTENT-HUB-RUNBOOK.md`. Прямой SQL/DAO на canonical DB в этом проекте запрещён.
  - **TG_Parser** — источник экспортов (папки с HTML/JSON + видеофайлами), которые сканирует `main.py scan`.
  - **VK API** — публикация видео через `VKPublisher`/`VKDestinationAdapter`; пользовательский OAuth-токен с правами `video`, `groups` (не токен группы).
- Operational constraints:
  - VK API 1051 (метод недоступен для типа профиля/токена) — fail-fast: `main.py vk-preflight` перед батчем, exit-код 3 (`EXIT_VK_CONTEXT`) при 1051 в цикле upload-one; ретраи не помогают, нужен перевыпуск токена.
  - Токен истекает (раз в сутки или через 1 час при VK ID) — автообновление через `scripts/refresh_vk_token.py` (`docs/VK-TOKEN-REFRESH.md`), lock-файл `.vk_refresh.lock` от параллельного refresh.
  - Canonical write в `content_hub` — по умолчанию выключен (`CONTENT_HUB_WRITE_ENABLED=0`); включается явно с DSN, иначе при недоступном `content_hub_client` — только warning в лог, без ошибки.

## Commands

- Setup: `python -m venv venv` → активировать → `pip install -r requirements.txt` (+ `pip install -r requirements.local.txt` для `content_hub_client` из ContentBackbone).
- Test: `pytest tests/`.
- Lint/typecheck: отдельного конфига (flake8/mypy/pyproject) в проекте нет; синтаксическая проверка адаптеров — `python -m py_compile main.py src/models/content.py src/adapters/base.py src/adapters/destinations/vk.py src/adapters/sources/export_fs.py`.
- Run locally: `python main.py --help`, `python main.py scan -s mapped`, `python main.py upload-next`.
- Smoke checks: `.\scripts\smoke-phase3.ps1` (см. `docs/PHASE3-SMOKE-TESTS.md`); `python main.py vk-preflight <root>` перед батч-загрузкой.

## Architecture Notes

- Core modules: `src/parsers/` (HTML/JSON парсинг экспортов) → `src/models/` (`VideoData`, `ContentItem`) → `src/title_generators/` (заголовки) → `src/adapters/` (`SourceAdapter`/`DestinationAdapter`, `VKDestinationAdapter`) → `src/publisher/vk_publisher.py` (VK API) → `src/integrations/content_hub/adapter.py` (canonical write).
- Data/storage: SQLite `videos.db` — таблица видео (статусы загрузки, маппинг папка→курс) и таблица `jobs` (очередь, `src/storage/job_queue.py`, см. `docs/PHASE4-JOB-QUEUE.md`).
- External services: VK API (загрузка видео), PostgreSQL `content_hub` (ContentBackbone, доступ только через `content_hub_client`).
- Trust boundaries: `content_hub_client` — единственная точка записи в общую БД `content_hub`; VK-токен — пользовательский OAuth (не сервисный), хранится только в `.env`.

## Known Risks

- Reliability: VK API 1051 может остановить весь батч загрузки, если не пройден `vk-preflight`; повторные попытки при 1051 не помогают.
- Security/privacy: VK-токены (`VK_ACCESS_TOKEN`, `VK_CLIENT_SECRET`, `VK_REFRESH_TOKEN`) — только в `.env`, не логировать значения (в логах пишется только факт наличия токена и его тип).
- Data/encoding: экспорты Telegram могут приходить в HTML или JSON, парсеры должны определять формат автоматически (`base.py`/`detect_format`); при смешанных кодировках в исходных сообщениях — риск порчи заголовков.
- Cross-project contract drift: изменение схемы `content_hub` или контракта `content_hub_client` в ContentBackbone требует синхронного обновления `src/integrations/content_hub/adapter.py` в этом проекте — иначе canonical write тихо отключается (warning) при `CONTENT_HUB_WRITE_STRICT=0`.

## Current Decisions

| Date | Decision | Why | Owner/Source |
| --- | --- | --- | --- |

## Prevention Register

| Date | Incident/Risk | Prevention Rule | Related Skill |
| --- | --- | --- | --- |

## Handoff Notes

- Current focus:
- Blockers:
- Follow-ups:

## Maintenance Rules

- Keep durable facts here; keep transient task notes in session summaries or issue docs.
- Do not store credentials, tokens, cookies, personal secrets, or private keys.
- When implementation intentionally diverges from specs, record the decision and update the relevant specs/docs in the same task.
- Prefer links to canonical docs over duplicating long content.
