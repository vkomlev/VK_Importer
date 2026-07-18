# Claude Code — VK_Importer

## Стек
- Python
- Pipeline: импорт данных в VK и соцсети

## Контекст проекта
Импорт данных в VK и соцсети.

Канонический путь записи результата публикации — `content_hub.publication`/`link_map`
только через `content_hub_client` (инфра-слой ContentBackbone), без локального DAO/SQL.
См. [docs/TECH-SPEC-CURSOR-P0-VK-IMPORTER-CANONICAL-WRITEPATH-v1.md](../docs/TECH-SPEC-CURSOR-P0-VK-IMPORTER-CANONICAL-WRITEPATH-v1.md)
и [docs/CONTENT-HUB-RUNBOOK.md](../docs/CONTENT-HUB-RUNBOOK.md).

---

## Профиль: Python разработчик

**MCP PostgreSQL:**
- Алиас: `postgresql`, read-only по умолчанию
- Write SQL — только при явном требовании + rollback note

**Контракт вывода:**
- `Plan`
- `Changed Files`
- `Validation Commands`
- `DB Findings` (при работе с БД)
- `Risks / Follow-ups`

---

## Профиль: отладчик

**Debug loop:**
1. Воспроизвести с точной командой и input
2. Зафиксировать логи и runtime output
3. Проверить DB state через MCP (read-only)
4. Добавить failing test до фикса (если применимо)
5. Применить минимальный root-cause фикс
6. Повторить smoke + смежные сценарии

**Контракт вывода (отладка):**
- `Reproduction`
- `Observed vs Expected`
- `Root Cause`
- `Fix Plan`
- `Changed Files`
- `Validation (before/after)`
- `Residual Risk`

---

## Review-changes — ОБЯЗАТЕЛЬНО

**Перед завершением ответа** — всегда сохранять:
1. Markdown: `reviews/YYYY-MM-DD-краткое-описание.md`
2. Diff: `reviews/YYYY-MM-DD-краткое-описание.diff`
   ```powershell
   git diff | Out-File -FilePath "reviews\имя.diff" -Encoding utf8
   git add <файлы> && git diff --cached | Out-File -FilePath "reviews\имя.diff" -Encoding utf8
   ```
Ответ без `reviews/` — незавершён.

---

## Общие правила
- Secrets только в `.env`, не в коде
- `/review-gate` обязателен перед интеграцией в main/master
- При изменениях БД — сначала `/db-check`
- Глобальный контекст: `~/.claude/CLAUDE.md`
