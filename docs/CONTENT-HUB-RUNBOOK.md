# Content Hub canonical write-path (P2B): runbook

Дата: 2026-03-07  
ТЗ: [TECH-SPEC-CURSOR-P2B-VK-IMPORTER-v1.md](TECH-SPEC-CURSOR-P2B-VK-IMPORTER-v1.md)

Запись в `content_hub.publication` и `content_hub.link_map` выполняется **только через** `content_hub_client` (инфра-слой ContentBackbone). В VK_Importer нет прямого SQL и локального DAO для canonical write.

---

## 1. Зависимость content_hub_client

Источник: репозиторий ContentBackbone, пакет `content_hub_client`.

### Установка пакета (рекомендуется)

Из корня VK_Importer (путь к ContentBackbone задан в `requirements.local.txt`):

```powershell
pip install -r requirements.local.txt
```

Или напрямую из корня ContentBackbone:

```powershell
pip install -e D:\Work\ContentBackbone
```

В `requirements.local.txt` указан editable install (`-e D:\Work\ContentBackbone`); при другом расположении репозитория путь нужно поправить. После установки импорт `content_hub_client` работает без PYTHONPATH.

### Альтернатива: PYTHONPATH

Если пакет не установлен, добавить корень ContentBackbone в `PYTHONPATH` (в .env PYTHONPATH не подхватывается интерпретатором до старта — задать в сессии):

```powershell
$env:PYTHONPATH = "D:\Work\ContentBackbone;$env:PYTHONPATH"
python main.py upload-one 123
```

Без доступного `content_hub_client` при `CONTENT_HUB_WRITE_ENABLED=1` в лог пишется предупреждение и запись не выполняется.

---

## 2. Переменные окружения

| Переменная | По умолчанию | Описание |
|------------|--------------|----------|
| `CONTENT_HUB_WRITE_ENABLED` | `0` | `1` — включить canonical write после каждой публикации (через content_hub_client). |
| `CONTENT_HUB_WRITE_DRY_RUN` | `0` | `1` — dry-run: клиент не коммитит в БД. |
| `CONTENT_HUB_WRITE_STRICT` | `0` | `1` — сбой canonical write считать фатальной ошибкой шага. |
| `CONTENT_HUB_PG_DSN` | — | DSN PostgreSQL, например `postgresql://user:pass@host:5432/Learn`. |
| `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD` | — | Альтернатива DSN (собирается DSN, если `CONTENT_HUB_PG_DSN` не задан; `PGDATABASE` по умолчанию `Learn`). |

---

## 3. Включение write-path

1. Убедиться, что в окружении доступен `content_hub_client` (PYTHONPATH = корень ContentBackbone).
2. Задать `CONTENT_HUB_WRITE_ENABLED=1` и `CONTENT_HUB_PG_DSN=...` (или составные PG-переменные).
3. Запускать публикацию как обычно: `upload-one`, пайплайн и т.д. После каждого publish вызывается клиент: всегда upsert в `publication`; в `link_map` — только при успешной публикации (есть remote_url/remote_id), чтобы не перезаписывать связь на NULL.

---

## 4. Dry-run

`CONTENT_HUB_WRITE_DRY_RUN=1` — клиент не выполняет commit; в логах фиксируется операция (dry_run). Данные в БД не меняются.

---

## 5. Откат

1. `CONTENT_HUB_WRITE_ENABLED=0` (или удалить переменную).
2. Публикация в VK и `videos.db` работают как раньше; canonical write не вызывается.

При полном откате кода: `git revert <commit>`, затем smoke-проверка publish-flow.

---

## 6. Маппинг (PublicationResult → client payload)

- **global_uid / source_global_uid:** `vk_importer:video_record:<id>` или `vk_importer:path:<normalized_file_path>`.
- **destination:** `vk`.
- **remote_url, remote_id:** из `result.remote_url`; remote_id — парсинг VK URL (`owner_id_video_id`).
- **status:** `published` | `failed`; **error:** `result.error_code` при ошибке.
- **published_at:** UTC ISO-8601 при успехе.

---

## 7. Валидация

```powershell
python -m py_compile main.py src/adapters/destinations/vk.py src/models/content.py
python main.py vk-preflight
# С реальным ID и доступом к БД Learn:
$env:CONTENT_HUB_WRITE_ENABLED="1"; $env:PYTHONPATH="D:\Work\ContentBackbone"; python main.py upload-one <REAL_ID>
# Повтор (идемпотентность)
$env:CONTENT_HUB_WRITE_ENABLED="1"; $env:PYTHONPATH="D:\Work\ContentBackbone"; python main.py upload-one <REAL_ID>
# Dry-run
$env:CONTENT_HUB_WRITE_ENABLED="1"; $env:CONTENT_HUB_WRITE_DRY_RUN="1"; $env:PYTHONPATH="D:\Work\ContentBackbone"; python main.py upload-one <REAL_ID>
# Аудит: не должно быть прямого canonical write в src
rg -n "INSERT INTO content_hub|UPDATE content_hub|DELETE FROM content_hub|psycopg2.connect\(" src
```

Ожидаемо: в `src` нет вхождений прямого SQL в content_hub и psycopg2.connect.
