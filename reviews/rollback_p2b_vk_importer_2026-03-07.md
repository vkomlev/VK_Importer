# Откат P2B VK_Importer (canonical write-path через content_hub_client)

**Дата:** 2026-03-07

## Быстрый откат (без смены кода)

1. Установить в окружении: `CONTENT_HUB_WRITE_ENABLED=0` (или удалить переменную).
2. Публикация в VK и запись в `videos.db` продолжают работать; вызовы content_hub_client не выполняются (adapter выходит по флагу).

## Полный откат кода

1. `git revert <commit_p2b>` (коммит с внедрением P2B).
2. Убедиться, что в main.py нет вызовов `write_canonical_if_enabled` и импорта из `src.integrations.content_hub`.
3. При необходимости удалить каталог `src/integrations/content_hub/` (adapter, __init__).
4. Smoke-проверка: `python main.py vk-preflight`, `python main.py upload-one <id>` — поведение как до P2B.

## Риски отката

- Низкие: изменения изолированы в adapter и двух точках вызова в main; legacy flow не менялся.
