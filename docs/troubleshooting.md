# Устранение неполадок

Типовые проблемы при работе с VK API и пайплайном публикации. Для настройки токена и переменных окружения см. [QUICKSTART.md](QUICKSTART.md) и [VK-TOKEN-REFRESH.md](VK-TOKEN-REFRESH.md).

## VK API 1051 — «метод недоступен для данного типа профиля/токена»

**Симптом:** загрузка видео падает с ошибкой VK API `1051`, `main.py upload-one` завершается с кодом `3` (`EXIT_VK_CONTEXT`).

**Причина:** используется не тот тип токена — токен группы или токен без права `video`. Метод загрузки видео требует **пользовательский OAuth-токен** с правами `video` и `groups`.

**Решение:**
1. Перевыпустить токен через `python scripts/get_vk_token_by_code.py` (пользовательский OAuth, права `video`, `groups`).
2. Перед батч-загрузкой всегда запускать `python main.py vk-preflight <root>` — эта проверка ловит 1051 до цикла загрузки, а не после первого же видео.
3. Ретраи не помогают: при 1051 публикатор сразу бросает `VKApi1051Error` без повторных попыток (см. `src/publisher/vk_publisher.py`).

Подробности инцидента и фикса: `reviews/vk-preflight-and-failfast-1051-2026-02-21.md`.

## VK API 5 — «истёк токен» (User authorization failed)

**Симптом:** ошибка VK API с кодом `5` во время загрузки видео или обновления заголовка.

**Причина:** пользовательский токен истёк (обычно раз в сутки, при VK ID — уже через 1 час).

**Решение:**
- Если настроен `on_token_expired` (автообновление через `refresh_token`) — публикатор сам обновит токен и повторит операцию один раз.
- Вручную: `python scripts/refresh_vk_token.py` (обновляет `VK_ACCESS_TOKEN` в `.env`, если до истечения меньше порога `--expires-within`).
- Если `VK_REFRESH_TOKEN`/`VK_DEVICE_ID` не настроены — обновление невозможно, нужно заново пройти OAuth: `python scripts/get_vk_token_by_code.py`.

## Ошибка SSL: CERTIFICATE_VERIFY_FAILED / self-signed certificate

**Симптом:** запросы к VK OAuth/API падают с ошибкой проверки сертификата.

**Причина:** обычно корпоративный прокси или антивирус подменяет сертификат.

**Решение:** только в доверенной сети — отключить проверку SSL для запросов к VK: `.env` → `VK_SSL_VERIFY=0`, либо переменная окружения перед запуском (`set VK_SSL_VERIFY=0` в Windows, `export VK_SSL_VERIFY=0` в Linux/macOS).

## Превышена частота запросов / антибот-блокировка VK

**Симптом:** ошибки при массовой загрузке (`upload-all`, `upload-range` с большим `--count`).

**Причина:** VK ограничивает частоту запросов к API.

**Решение:**
- Не уменьшать паузу между загрузками — по умолчанию `--delay 15` (секунд), это учитывает рекомендации VK API.
- При частичных ошибках публикатор сам повторяет попытку через `retry_delay` (настраивается `--max-retries`).
- Подробнее: раздел «Ограничения VK API и паузы между загрузками» в [USAGE.md](USAGE.md).

## `content_hub_client` недоступен (canonical write пропущен)

**Симптом:** в логе предупреждение `content_hub_client недоступен (PYTHONPATH?): canonical write пропущен`, запись в `content_hub.publication`/`link_map` не происходит, но публикация в VK при этом отрабатывает нормально.

**Причина:** пакет `content_hub_client` (из ContentBackbone) не установлен и не виден в `PYTHONPATH`, при этом `CONTENT_HUB_WRITE_ENABLED=1`.

**Решение:**
1. Установить пакет: `pip install -r requirements.local.txt` (editable install на `D:\Work\ContentBackbone`) или `pip install -e D:\Work\ContentBackbone`.
2. Либо задать `PYTHONPATH` на корень ContentBackbone перед запуском в текущей сессии.
3. Если canonical write обязателен — включить `CONTENT_HUB_WRITE_STRICT=1`, тогда отсутствие клиента станет фатальной ошибкой шага, а не тихим warning.

Подробнее: [CONTENT-HUB-RUNBOOK.md](CONTENT-HUB-RUNBOOK.md).

## `content_hub_client` не пишет — не задан DSN

**Симптом:** предупреждение `CONTENT_HUB_PG_DSN не задан: canonical write пропущен`.

**Причина:** при `CONTENT_HUB_WRITE_ENABLED=1` не указан ни `CONTENT_HUB_PG_DSN`, ни составные `PGHOST`/`PGPORT`/`PGDATABASE`/`PGUSER`/`PGPASSWORD`.

**Решение:** задать `CONTENT_HUB_PG_DSN` (например `postgresql://user:pass@host:5432/Learn`) или полный набор `PG*`-переменных в `.env`.

## Видео из экспорта не подхватывается сканером

**Симптом:** `python main.py scan` не находит новые видео из ожидаемой папки экспорта.

**Причина:** папка не добавлена в маппинг «папка → курс» (маппинг хранится только в БД, не в коде), либо файл экспорта в неожиданном формате.

**Решение:**
```bash
python main.py folders list                          # проверить текущий маппинг
python main.py folders set "<путь_к_экспорту>" <курс> # добавить папку
python main.py scan -s mapped                          # пересканировать
```
Поддерживаемые форматы экспорта — HTML и JSON (см. «Структура экспорта Telegram» в [QUICKSTART.md](QUICKSTART.md)).
