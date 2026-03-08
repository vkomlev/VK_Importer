# Audit P2B VK_Importer: отсутствие локального canonical write-path

**Дата:** 2026-03-07

## Цель

Подтвердить, что в VK_Importer нет прямого SQL в `content_hub` и нет локального DAO/psycopg2 для canonical write. Запись выполняется только через `content_hub_client`.

## Команда проверки

```powershell
rg -n "INSERT INTO content_hub|UPDATE content_hub|DELETE FROM content_hub|psycopg2.connect\(" src
```

## Результат

**Найдено вхождений: 0.** Прямого canonical write в `src` нет.

## Структура интеграции

- `src/integrations/content_hub/adapter.py` — доменный адаптер: маппинг `VideoRecord` + `PublicationResult` в payload контрактов `content_hub_client` и вызов `ContentHubClient.upsert_publication` / `upsert_link_map`.
- Импорт: `from content_hub_client.client import ContentHubClient`; при недоступности модуля canonical write отключается (warning в лог).
- Локальных модулей repository, models с SQL, db.py с psycopg2 в VK_Importer нет.

## Вывод

Требования ТЗ P2B соблюдены: единая точка canonical write — `content_hub_client`.
